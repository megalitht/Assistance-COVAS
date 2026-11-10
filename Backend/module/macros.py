# macros.py
"""
Touches envoyées au jeu.

Les touches ci-dessous sont celles par défaut d'Elite Dangerous. Si tu as changé
un raccourci dans le jeu (Options > Commandes), modifie seulement le tableau TOUCHES.
"""
import os
import time
import unicodedata

import pydirectinput

pydirectinput.PAUSE = 0.05

TOUCHES = {
    # Vol
    "train": "l",
    "soute": "home",
    "cible": "t",
    "boost": "tab",
    "saut": "j",
    # Répartition d'énergie (pips)
    "pips_sys": "left",
    "pips_moteurs": "up",
    "pips_armes": "right",
    "pips_equilibre": "down",
    # Navigation dans les menus du jeu
    "ui_haut": "w",
    "ui_bas": "s",
    "ui_gauche": "a",
    "ui_droite": "d",
    "ui_selection": "space",
    "ui_retour": "backspace",
}

# --- RAVITAILLEMENT À QUAI -------------------------------------------------
# Touches pour ouvrir les services de la station depuis le menu d'amarrage.
# Par défaut : remonter tout en haut du menu, descendre d'un cran (« Services
# de la station »), valider. Si ton menu est dans un autre ordre, ajuste ici.
SEQUENCE_OUVRIR_SERVICES = ["ui_haut"] * 4 + ["ui_bas", "ui_selection"]

# Une fois dans les services : Ravitailler, Réparer, Réarmer (boutons en haut à gauche).
SEQUENCE_RAVITAILLEMENT = ["ui_haut", "ui_gauche", "ui_gauche", "ui_selection",
                           "ui_droite", "ui_selection",
                           "ui_droite", "ui_selection"]

ATTENTE_ECRAN = 2.5     # secondes laissées au jeu pour afficher l'écran des services
# ---------------------------------------------------------------------------

DUREE_APPUI = 0.06      # Elite rate parfois les appuis trop brefs
PAUSE_ENTRE = 0.12

# Macros simples : nom de l'action -> [(touche, nombre d'appuis), ...]
MACROS = {
    "train_atterrissage": [("train", 1)],
    "soute": [("soute", 1)],
    "energie_mtr": [("pips_equilibre", 1), ("pips_moteurs", 4)],
    "energie_sys": [("pips_equilibre", 1), ("pips_sys", 4)],
    "energie_arm": [("pips_equilibre", 1), ("pips_armes", 4)],
    "reset": [("pips_equilibre", 1)],
    "lock": [("cible", 1)],
    "boost": [("boost", 1)],
    "mode_combat": [("pips_sys", 4), ("pips_armes", 4)],
    "mode_croisiere": [("pips_sys", 4), ("pips_moteurs", 4)],
    "mode_recuperation": [("pips_moteurs", 4), ("pips_sys", 4)],
    "fsd": [("saut", 1), ("pips_sys", 4), ("pips_moteurs", 4)],
}


def normaliser(nom: str) -> str:
    """'mode_Croisière' -> 'mode_croisiere' (minuscules, sans accents)."""
    sans_accents = unicodedata.normalize("NFKD", nom or "").encode("ascii", "ignore").decode()
    return sans_accents.lower().strip()


def appuyer(nom: str, fois: int = 1):
    """Appuie sur une touche du tableau TOUCHES (ou une touche brute)."""
    touche = TOUCHES.get(nom, nom)
    for _ in range(fois):
        pydirectinput.keyDown(touche)
        time.sleep(DUREE_APPUI)
        pydirectinput.keyUp(touche)
        time.sleep(PAUSE_ENTRE)


def executer_touches(action: str) -> bool:
    """Exécute la macro simple associée à l'action. Renvoie False si elle n'existe pas."""
    etapes = MACROS.get(normaliser(action))
    if not etapes:
        print(f"[Macros] Aucune touche associée à l'action : {action}")
        return False
    for touche, fois in etapes:
        appuyer(touche, fois)
    return True


FENETRE_JEU = "FrontierDevelopmentsAppWinClass"


def focaliser_jeu() -> bool:
    """Met la fenêtre d'Elite Dangerous au premier plan pour que les touches arrivent
    bien au jeu (par exemple après un clic sur l'interface du 2e écran).
    Renvoie False si le jeu n'est pas lancé ou si Windows refuse."""
    if os.name != "nt":
        return True
    import ctypes
    user32 = ctypes.windll.user32
    fenetre = user32.FindWindowW(FENETRE_JEU, None)
    if not fenetre:
        return False
    if user32.GetForegroundWindow() == fenetre:
        return True
    if user32.IsIconic(fenetre):
        user32.ShowWindow(fenetre, 9)          # restaure la fenêtre réduite
    # Windows bloque SetForegroundWindow pour un programme en arrière-plan ;
    # un appui sur Alt lève ce verrou.
    user32.keybd_event(0x12, 0, 0, 0)
    user32.keybd_event(0x12, 0, 2, 0)
    user32.SetForegroundWindow(fenetre)
    time.sleep(0.3)
    return user32.GetForegroundWindow() == fenetre