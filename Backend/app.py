"""
app.py — Application COVAS (fenêtre native, plus de navigateur).

Au lancement, la fenêtre affiche l'écran d'accueil (Frontend/interface.html?app) : le COVAS
n'est PAS encore actif (ni modèle vocal, ni micro, ni touches). Le bouton central appelle
Api.activer() : main.demarrer() tourne alors dans un thread, chaque étape du démarrage est
affichée à l'écran, puis l'interface devient le panneau de contrôle (liaison WebSocket
habituelle, voir module/serveur_ws.py).

Lancement : COVAS.bat (sans console) ou  .venv\\Scripts\\python.exe Backend\\app.py
Variable COVAS_DEBUG=1 : ouvre les outils de développement de la fenêtre.
"""
import json
import os
import socket
import sys
import threading
import traceback

DOSSIER_BACKEND = os.path.dirname(os.path.abspath(__file__))
DOSSIER_FRONTEND = os.path.join(os.path.dirname(DOSSIER_BACKEND), "Frontend")
TITRE = "COVAS — Assistance de bord"      # même titre que main.TITRE / macros.TITRE_INTERFACE
PORT_WS = 8765                            # liaison du panneau (module/serveur_ws.py)
PORT_PAGE = 8766                          # serveur local de la page
DOSSIER_PROFIL = os.path.join(DOSSIER_BACKEND, "data", "fenetre")   # profil WebView2 (préférences)

# Lancé par pythonw (sans console) : print() et traceback n'ont nulle part où écrire.
if sys.stdout is None or sys.stderr is None:
    _journal = open(os.path.join(DOSSIER_BACKEND, "data", "covas.log"), "w",
                    encoding="utf-8", buffering=1)
    sys.stdout = sys.stdout or _journal
    sys.stderr = sys.stderr or _journal

sys.path.insert(0, DOSSIER_BACKEND)

import webview  # noqa: E402


class Api:
    """Fonctions appelables depuis la page : window.pywebview.api.<nom>()."""

    def __init__(self):
        self._fenetre = None
        self._verrou = threading.Lock()
        self._etat = "veille"          # veille -> activation -> actif (ou retour en veille si erreur)

    def _pousser(self, texte, etat="etape"):
        """Envoie une étape du démarrage à l'écran d'accueil."""
        if etat == "pret":
            self._etat = "actif"
        message = json.dumps({"texte": texte, "etat": etat}, ensure_ascii=False)
        try:
            self._fenetre.evaluate_js(f"window.COVAS_ACCUEIL && window.COVAS_ACCUEIL.recevoir({message})")
        except Exception:
            pass

    def _activation(self):
        try:
            # Un autre COVAS (main.py en console, autre fenêtre...) tient déjà la liaison :
            # deux COVAS écouteraient le même micro et appuieraient deux fois sur les touches.
            if not _port_libre(PORT_WS):
                raise RuntimeError(f"un autre COVAS est déjà lancé (port {PORT_WS} occupé). "
                                   "Ferme-le, puis réessaie.")
            self._pousser("Chargement des modules de bord")
            import main                             # importe macros, actions... (pas avant le clic)
            from module import actions
            actions.MODE_APPLICATION = True
            main.demarrer(progression=self._pousser)     # ne rend la main qu'à l'arrêt
        except BaseException as erreur:            # SystemExit compris : la fenêtre doit le dire
            traceback.print_exc()
            actif = self._etat == "actif"
            self._etat = "veille"
            self._pousser(("COVAS arrêté : " if actif else "Activation impossible : ")
                          + (str(erreur) or type(erreur).__name__), "erreur")

    def activer(self):
        """Bouton central de l'écran d'accueil. Renvoie l'état après l'appel."""
        with self._verrou:
            if self._etat == "veille":
                self._etat = "activation"
                threading.Thread(target=self._activation, name="COVAS", daemon=True).start()
            return self._etat

    def etat(self):
        return self._etat

    def plein_ecran(self):
        """F11 dans la fenêtre : quitte ou retrouve le plein écran."""
        self._fenetre.toggle_fullscreen()


def _ecran_secondaire():
    """L'écran qui n'est pas le principal (le principal a toujours son coin en 0,0 sous
    Windows). Plusieurs écrans secondaires : le plus grand. Un seul écran : celui-là."""
    ecrans = list(webview.screens)
    secondaires = [e for e in ecrans if (e.x, e.y) != (0, 0)]
    if secondaires:
        return max(secondaires, key=lambda e: e.width * e.height)
    return ecrans[0] if ecrans else None


def _port_libre(port):
    """True si aucun programme n'écoute sur ce port de ce PC (IPv4 comme IPv6)."""
    for famille, hote in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
        with socket.socket(famille) as essai:
            try:
                essai.bind((hote, port))
            except OSError as erreur:
                if famille == socket.AF_INET6 and erreur.errno == 10049:   # pas d'IPv6 sur ce PC
                    continue
                return False
    return True


def _port_page():
    """Port du petit serveur local qui sert Frontend/ à la fenêtre. Toujours le même si
    possible : les préférences de l'interface (vue choisie...) sont liées à l'adresse."""
    return PORT_PAGE if _port_libre(PORT_PAGE) else None   # pris : pywebview en choisit un autre


def _ramener_fenetre_existante():
    """Application déjà ouverte : on ramène sa fenêtre devant et on renvoie True.
    (Deux fenêtres ne peuvent pas partager le même profil WebView2.)"""
    if os.name != "nt":
        return False
    import ctypes
    user32 = ctypes.windll.user32
    user32.FindWindowW.restype = ctypes.c_void_p
    fenetre = user32.FindWindowW(None, TITRE)
    if not fenetre:
        return False
    fenetre = ctypes.c_void_p(fenetre)
    if user32.IsIconic(fenetre):
        user32.ShowWindow(fenetre, 9)              # restaure la fenêtre réduite
    user32.keybd_event(0x12, 0, 0, 0)              # Alt : lève le verrou de SetForegroundWindow
    user32.keybd_event(0x12, 0, 2, 0)
    user32.SetForegroundWindow(fenetre)
    return True


def lancer():
    if _ramener_fenetre_existante():
        return
    api = Api()
    # Servie en http (et non en file://) : WebView2 garde ainsi le « ?app » de l'adresse.
    page = os.path.join(DOSSIER_FRONTEND, "interface.html") + "?app"
    # Toujours en plein écran sur l'écran secondaire (le jeu reste sur le principal).
    # La fenêtre est d'abord centrée sur cet écran : le plein écran prend l'écran où elle se trouve.
    ecran = _ecran_secondaire()
    largeur, hauteur = (min(1600, ecran.width), min(900, ecran.height)) if ecran else (1600, 900)
    fenetre = webview.create_window(TITRE, url=page, js_api=api, background_color="#070403",
                                    width=largeur, height=hauteur, min_size=(1100, 650),
                                    screen=ecran, fullscreen=True, text_select=True)
    api._fenetre = fenetre
    webview.start(gui="edgechromium", debug=os.environ.get("COVAS_DEBUG") == "1",
                  http_server=True, http_port=_port_page(), private_mode=False,
                  storage_path=DOSSIER_PROFIL)
    # Fenêtre fermée : on coupe tout (threads du micro, de l'audio, des journaux...)
    os._exit(0)


if __name__ == "__main__":
    lancer()
