"""
second_ecran.py — L'interface sur un téléphone ou une tablette, sur le même réseau (Wi-Fi) que le PC.

Le serveur de l'interface (serveur_ws.py) écoute alors sur toutes les cartes réseau du PC, et sert
sur un seul port les pages de Frontend/ (http://<adresse du PC>:<port>/) ET la liaison WebSocket.

Sécurité :
  - réseau local seulement : une adresse publique (Internet) est refusée d'office ;
  - un site web ouvert dans un navigateur ne peut pas parler au COVAS (contrôle de l'origine et de
    l'adresse demandée, contre le « DNS rebinding ») ;
  - regarder l'interface est libre ; les boutons, les phrases écrites et les réglages venant d'un
    autre appareil demandent le PIN de data/config.toml ([second_ecran] pin). Sans PIN réglé, ils
    sont refusés. Trop d'erreurs : l'appareil est bloqué quelques minutes ;
  - le PC lui-même (127.0.0.1) n'a pas de PIN à donner.
Le son reste sur le PC : la page ne joue aucune réplique.

Module sans dépendance au jeu : il se teste seul (tests/test_second_ecran.py).
"""
import hmac
import ipaddress
import mimetypes
import os
import socket
import time
from urllib.parse import unquote, urlsplit

DOSSIER_FRONTEND = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))), "Frontend")
PAGE_ACCUEIL = "interface.html"
# Seuls ces types de fichiers sont servis (jamais de .py, de .json de réglages...)
TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png",
         ".jpg": "image/jpeg", ".ico": "image/x-icon", ".woff2": "font/woff2", ".webmanifest":
         "application/manifest+json"}
TAILLE_MAX = 8 * 1024 * 1024


# =====================================================================
#  RÉSEAU LOCAL
# =====================================================================
def _ip(adresse):
    """Adresse IP (IPv4 dans IPv6 « ::ffff:192.168.1.5 » ramenée à l'IPv4), None si invalide."""
    try:
        ip = ipaddress.ip_address((adresse or "").split("%")[0])
    except ValueError:
        return None
    return ip.ipv4_mapped or ip if isinstance(ip, ipaddress.IPv6Address) else ip


def est_ce_pc(adresse):
    ip = _ip(adresse)
    return bool(ip and ip.is_loopback)


def est_reseau_local(adresse):
    """Ce PC, ou un appareil du réseau local (192.168.x.x, 10.x.x.x, 172.16-31.x.x, fe80::...)."""
    ip = _ip(adresse)
    if ip is None:
        return False
    return ip.is_loopback or ip.is_link_local or (ip.is_private and not ip.is_unspecified)


def adresses_locales():
    """Adresses IPv4 de ce PC sur le réseau local (192.168... d'abord). Aucune requête envoyée."""
    trouvees = []
    try:
        infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
    except OSError:
        infos = []
    for info in infos:
        adresse = info[4][0]
        ip = _ip(adresse)
        if ip and ip.is_private and not ip.is_loopback and not ip.is_link_local \
                and adresse not in trouvees:
            trouvees.append(adresse)
    # Le Wi-Fi d'une box est presque toujours en 192.168.x.x ; les adaptateurs virtuels
    # (WSL, Hyper-V, VPN) sont souvent en 172.x ou 10.x.
    trouvees.sort(key=lambda a: (not a.startswith("192.168."), a))
    return trouvees


def adresses_page(port):
    return [f"http://{adresse}:{port}/" for adresse in adresses_locales()]


def hote_autorise(hote):
    """L'adresse demandée (en-tête Host) est-elle une adresse IP ou « localhost » ? Un nom de domaine
    est refusé : c'est la marque d'une attaque par « DNS rebinding » depuis un site web."""
    if not hote:
        return False
    hote = hote.strip()
    if hote.startswith("["):                        # [::1]:8765
        hote = hote[1:hote.find("]")] if "]" in hote else hote[1:]
    elif hote.count(":") == 1:
        hote = hote.rsplit(":", 1)[0]
    return hote.lower() == "localhost" or _ip(hote) is not None


def origine_autorisee(origine, hote):
    """WebSocket ouvert par une page de ce COVAS ? Origine absente ou « null » (fichier local),
    page de ce PC (fenêtre de l'application, autre port), ou page servie par le même serveur."""
    if not origine or origine == "null":
        return True
    try:
        nom = urlsplit(origine).hostname or ""
    except ValueError:
        return False
    if nom.lower() == "localhost" or est_ce_pc(nom):
        return True
    hote_seul = (hote or "").rsplit(":", 1)[0].strip("[]").lower()
    return hote_autorise(hote) and nom.lower() == hote_seul


# =====================================================================
#  PIN
# =====================================================================
class GardePin:
    """Vérifie le PIN des commandes venues d'un autre appareil, et bloque après trop d'erreurs."""

    def __init__(self, horloge=time.monotonic):
        self.horloge = horloge
        self.erreurs = {}            # adresse -> (nombre d'erreurs, bloqué jusqu'à)

    def bloque_pour(self, adresse):
        """Secondes de blocage restantes pour cet appareil (0 : libre)."""
        _, jusqua = self.erreurs.get(adresse, (0, 0.0))
        return max(0.0, jusqua - self.horloge())

    def verifier(self, adresse, saisi, attendu, tentatives=5, blocage=300):
        """"ok", "faux", "bloque" ou "absent" (aucun PIN réglé : commandes refusées)."""
        if not attendu:
            return "absent"
        if self.bloque_pour(adresse):
            return "bloque"
        if isinstance(saisi, str) and hmac.compare_digest(saisi.strip().encode(), str(attendu).encode()):
            self.erreurs.pop(adresse, None)
            return "ok"
        nombre, _ = self.erreurs.get(adresse, (0, 0.0))
        nombre += 1
        if nombre >= tentatives:
            self.erreurs[adresse] = (0, self.horloge() + blocage)
            return "bloque"
        self.erreurs[adresse] = (nombre, 0.0)
        return "faux"


# =====================================================================
#  PAGES
# =====================================================================
def fichier_demande(chemin_url, racine=DOSSIER_FRONTEND):
    """Chemin du fichier de Frontend/ demandé par l'adresse, None s'il est interdit ou absent.
    « / » donne l'interface. Jamais de fichier hors de Frontend/ ni de type non prévu."""
    chemin = unquote(urlsplit(chemin_url or "/").path or "/")
    if chemin in ("", "/"):
        chemin = "/" + PAGE_ACCUEIL
    if "\\" in chemin or "\0" in chemin:
        return None
    morceaux = [m for m in chemin.split("/") if m]
    if any(m in (".", "..") or m.startswith(".") for m in morceaux):
        return None
    racine = os.path.realpath(racine)
    complet = os.path.realpath(os.path.join(racine, *morceaux))
    if os.path.commonpath([racine, complet]) != racine:
        return None
    if os.path.splitext(complet)[1].lower() not in TYPES or not os.path.isfile(complet):
        return None
    return complet


def lire_fichier(chemin):
    """(type, contenu) d'un fichier autorisé."""
    if os.path.getsize(chemin) > TAILLE_MAX:
        raise OSError("fichier trop gros")
    with open(chemin, "rb") as f:
        contenu = f.read()
    extension = os.path.splitext(chemin)[1].lower()
    return TYPES.get(extension) or mimetypes.guess_type(chemin)[0] or "application/octet-stream", contenu


# =====================================================================
#  QR CODE
# =====================================================================
def qr_svg(adresse):
    """QR code de l'adresse, en SVG (bibliothèque segno). None si segno est absent."""
    try:
        import segno
    except ImportError:
        return None
    # Modules sombres sur fond clair : tous les appareils photo le lisent
    return segno.make(adresse, error="m").svg_inline(scale=5, border=3, dark="#070403", light="#ffe9cf")
