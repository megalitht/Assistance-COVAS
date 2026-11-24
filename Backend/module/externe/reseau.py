"""
reseau.py — Requêtes HTTP vers les services externes. Fonctions bloquantes : à appeler dans un thread
(asyncio.to_thread), jamais dans la boucle principale.

Aucun nom ni adresse de l'utilisateur n'est envoyé : le User-Agent n'identifie que le projet.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "COVAS-Assistance/1.0 (assistant de bord Elite Dangerous, usage personnel)"
DELAI = 5                 # s par défaut (config.toml [externe] delai_secondes)
TAILLE_MAX = 5_000_000    # octets : une réponse plus grosse est refusée


class ErreurExterne(Exception):
    """Service injoignable, réponse illisible ou refus : « Données indisponibles »."""

    def __init__(self, message, statut=None, corps=None):
        super().__init__(message)
        self.statut = statut
        self.corps = corps


def requete_json(url, parametres=None, methode="GET", corps=None, delai=DELAI):
    """Renvoie (statut HTTP, JSON). Statuts 2xx seulement ; sinon ErreurExterne (avec le JSON
    d'erreur s'il y en a un)."""
    if parametres:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(parametres)
    entetes = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    donnees = None
    if corps is not None:
        donnees = json.dumps(corps).encode("utf-8")
        entetes["Content-Type"] = "application/json"
    elif methode == "POST":
        donnees = b""
    requete = urllib.request.Request(url, data=donnees, headers=entetes, method=methode)
    try:
        with urllib.request.urlopen(requete, timeout=delai) as reponse:
            brut = reponse.read(TAILLE_MAX + 1)
            statut = reponse.status
    except urllib.error.HTTPError as erreur:
        try:
            contenu = json.loads(erreur.read(100_000) or b"null")
        except ValueError:
            contenu = None
        raise ErreurExterne(f"HTTP {erreur.code}", erreur.code, contenu) from None
    except (urllib.error.URLError, TimeoutError, OSError) as erreur:
        raise ErreurExterne(f"injoignable ({getattr(erreur, 'reason', erreur)})") from None
    if len(brut) > TAILLE_MAX:
        raise ErreurExterne("réponse trop grosse")
    try:
        return statut, json.loads(brut or b"null")
    except ValueError:
        raise ErreurExterne("réponse illisible") from None
