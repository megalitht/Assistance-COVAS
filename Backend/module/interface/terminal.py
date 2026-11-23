"""Habillage du terminal façon « console de bord » : bannière, balises [ TAG ],
barre de chargement et panneau d'état.

`activer()` doit être appelé tout au début du programme : il active les couleurs
ANSI sous Windows et restyle automatiquement les anciens print("[Tag] message")
des autres modules, pour que tout le terminal ait le même look.
"""
import ctypes
import os
import re
import sys
import threading
import time

# --- PALETTE (mêmes codes que la maquette) ---
JAUNE = "\033[0;33m"
JAUNE_VIF = "\033[1;33m"
BLANC = "\033[0;37m"
VERT = "\033[0;32m"
CYAN = "\033[0;36m"
ROUGE = "\033[0;31m"
GRIS = "\033[0;90m"
RAZ = "\033[0m"

LARGEUR = 46          # largeur intérieure de la bannière
LARGEUR_BARRE = 40

_verrou = threading.RLock()
_sortie = sys.stdout            # flux brut (avant restylage)
_couleurs = True


def _activer_console_windows():
    """Active les séquences ANSI et l'UTF-8 dans la console Windows."""
    if os.name != "nt":
        return
    try:
        noyau = ctypes.windll.kernel32
        noyau.SetConsoleOutputCP(65001)
        poignee = noyau.GetStdHandle(-11)          # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if noyau.GetConsoleMode(poignee, ctypes.byref(mode)):
            noyau.SetConsoleMode(poignee, mode.value | 0x0004)  # VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        pass


def _c(couleur):
    return couleur if _couleurs else ""


def _ecrire(texte):
    with _verrou:
        _sortie.write(texte + (_c(RAZ)) + "\n")
        _sortie.flush()


# --- ÉLÉMENTS GRAPHIQUES ---

def banniere(titre):
    _ecrire("")
    _ecrire(f"{_c(JAUNE)}╭{'─' * LARGEUR}╮")
    _ecrire(f"{_c(JAUNE)}│{titre.center(LARGEUR)}│")
    _ecrire(f"{_c(JAUNE)}╰{'─' * LARGEUR}╯")
    _ecrire("")


def balise(tag):
    return f"[ {tag:^6} ]"


def ligne(tag, message, couleur=JAUNE):
    """[ TAG ] message  — balise blanche, message coloré."""
    _ecrire(f"{_c(BLANC)}{balise(tag)}{_c(couleur)} {message}")


def ok(message, couleur=VERT):
    ligne("OK", message, couleur)


def erreur(tag, message):
    ligne(tag, message, ROUGE)


def etat(tag, valeur, couleur=VERT):
    """[ STATUS ] ONLINE  — balise jaune, valeur colorée."""
    _ecrire(f"{_c(JAUNE)}[ {tag} ] {_c(couleur)}{valeur}")


def separateur():
    _ecrire("")
    _ecrire(f"{_c(JAUNE)}{'─' * (LARGEUR + 2)}")
    _ecrire("")


def vide():
    _ecrire("")


def titre_central(titre, sous_titre=""):
    _ecrire(f"{_c(JAUNE_VIF)}{titre.center(LARGEUR + 2)}")
    if sous_titre:
        _ecrire(f"{_c(BLANC)}{sous_titre.center(LARGEUR + 2)}")
    _ecrire("")


def note(premiere, *suivantes):
    """╰─ Texte d'aide sur plusieurs lignes."""
    _ecrire(f"{_c(JAUNE)}╰─{_c(BLANC)} {premiere}")
    for texte in suivantes:
        _ecrire(f"{_c(JAUNE)}   {texte}")


def _barre(fraction):
    pleins = int(LARGEUR_BARRE * fraction)
    return (f"{_c(VERT)}{'█' * pleins}{_c(GRIS)}{'░' * (LARGEUR_BARRE - pleins)}"
            f"{_c(VERT)} {int(fraction * 100):>3}%{_c(RAZ)}")


class Chargement:
    """Barre de progression animée pendant une opération bloquante :

        with Chargement():
            modele = WhisperModel(...)
    """

    def __init__(self):
        self._fin = threading.Event()
        self._fil = None
        self._anime = _couleurs

    def _animer(self):
        debut = time.monotonic()
        while not self._fin.wait(0.08):
            # Avance vite puis ralentit : on ne connaît pas la durée réelle.
            fraction = 0.95 * (1 - 1 / (1 + (time.monotonic() - debut) / 2.5))
            with _verrou:
                _sortie.write("\r" + _barre(fraction))
                _sortie.flush()

    def __enter__(self):
        if self._anime:
            self._fil = threading.Thread(target=self._animer, daemon=True)
            self._fil.start()
        return self

    def __exit__(self, type_erreur, *_):
        self._fin.set()
        if self._fil:
            self._fil.join()
        with _verrou:
            if type_erreur is None:
                _sortie.write(("\r" if self._anime else "") + _barre(1.0) + "\n")
            elif self._anime:
                _sortie.write("\n")
            _sortie.write("\n")
            _sortie.flush()
        return False


# --- RESTYLAGE DES ANCIENS print("[Tag] message") ---

_MOTIF = re.compile(r"^\[([^\]]+)\]\s*(.*)$")
_MOTS_ERREUR = ("erreur", "impossible", "introuvable", "attention", "abîmée")
_MOTS_SUCCES = ("prêt", "activée", "connectée", "confirmé", "chargé", "lues")


def _styliser(texte):
    if "\033[" in texte:
        return texte
    trouve = _MOTIF.match(texte)
    if not trouve:
        return texte
    tag, message = trouve.groups()
    minuscule = f"{tag} {message}".lower()
    if any(mot in minuscule for mot in _MOTS_ERREUR):
        couleur = ROUGE
    elif tag.upper() == "COVAS":
        couleur = CYAN
    elif any(mot in minuscule for mot in _MOTS_SUCCES):
        couleur = VERT
    else:
        couleur = JAUNE
    return f"{_c(BLANC)}{balise(tag.upper())}{_c(couleur)} {message}{_c(RAZ)}"


class _SortieStylisee:
    """Remplace sys.stdout : restyle chaque ligne complète, laisse passer le reste."""

    def __init__(self, flux):
        self._flux = flux
        self._tampon = ""

    def write(self, texte):
        with _verrou:
            self._tampon += texte
            while "\n" in self._tampon:
                contenu, self._tampon = self._tampon.split("\n", 1)
                self._flux.write(_styliser(contenu) + "\n")
            self._flux.flush()
        return len(texte)

    def flush(self):
        with _verrou:
            if self._tampon:
                self._flux.write(self._tampon)
                self._tampon = ""
            self._flux.flush()

    def __getattr__(self, nom):
        return getattr(self._flux, nom)


def activer():
    global _sortie, _couleurs
    _activer_console_windows()
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    _couleurs = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
    _sortie = sys.stdout
    sys.stdout = _SortieStylisee(_sortie)
    # Masque le message d'accueil de pygame (importé par module/son/voix.py)
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
