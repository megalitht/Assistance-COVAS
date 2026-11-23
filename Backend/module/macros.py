"""
Touches envoyées au jeu.

Les touches sont lues automatiquement dans le fichier de raccourcis d'Elite Dangerous
(voir touches.py). Une touche choisie dans Réglages > Commandes passe avant ; le tableau de
secours (commandes.py) sert pour les commandes que le fichier du jeu ne donne pas.
Les séquences de menus (apontage, décollage, ravitaillement...) se règlent au même endroit.
"""
import os
import threading
import time
import unicodedata

import pydirectinput

from module import commandes
from module import pips
from module import reglages
from module import touches

pydirectinput.PAUSE = 0.05

# pydirectinput ne connaît pas F13 à F24 (les touches virtuelles de touches.py) :
# on lui donne leurs codes matériels.
for _n, _code in zip(range(13, 25), (0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x6B,
                                     0x6C, 0x6D, 0x6E, 0x76)):
    pydirectinput.KEYBOARD_MAPPING.setdefault(f"f{_n}", _code)
# Ni le pavé numérique
for _n, _code in enumerate((0x52, 0x4F, 0x50, 0x51, 0x4B, 0x4C, 0x4D, 0x47, 0x48, 0x49)):
    pydirectinput.KEYBOARD_MAPPING.setdefault(f"numpad{_n}", _code)

TOUCHES = dict(commandes.TOUCHES_SECOURS)
# VRS et pied à terre : la touche vient du jeu ou des réglages, jamais d'une valeur devinée
TOUCHES.update({nom: None for nom in touches.COMMANDES_SOL})

# Touches que tu veux imposer, quoi que dise le fichier du jeu. Ex. : {"nvg": "f9"}
TOUCHES_FORCEES = {}

# Les raccourcis du jeu remplacent le tableau de secours
TOUCHES.update(touches.charger(assigner=True, sauf=TOUCHES_FORCEES))
TOUCHES.update(TOUCHES_FORCEES)

# Décollage d'une planète : durée max. de poussée verticale pour quitter le sol, puis
# durée de montée supplémentaire avant de rentrer le train (secondes).
DECOLLAGE_PLANETE_MAX = 15
DECOLLAGE_PLANETE_MONTEE = 2.5

# --- VOYAGE AUTOMATIQUE (route tracée dans la carte de la galaxie) ----------
# À chaque arrivée, le vaisseau fait face à l'étoile. Le COVAS pique du nez d'environ
# 90°, avance pour s'écarter de l'étoile (plus longtemps si le vaisseau chauffe), puis
# cabre exactement autant pour revenir face à la direction d'arrivée (là où se trouve
# en général le système suivant). Le retour est symétrique : même si la durée ne fait
# pas pile 90°, le nez revient dans l'axe d'arrivée.
# Ensuite, le FSD n'est lancé que quand la voie est libre : pas d'étoile au centre de
# l'écran et pas de chaleur, depuis VOYAGE_DELAI_VOIE_LIBRE secondes. Si l'étoile est
# toujours dans l'axe, le COVAS refait un écart (piquer, avancer, cabrer).
VOYAGE_DUREE_TANGAGE = 4.0      # secondes de tangage pour ~90° (vaisseau lourd : augmenter)
VOYAGE_DUREE_AVANCE = 30        # secondes de vol (au moins) pour s'écarter de l'étoile
VOYAGE_DUREE_AVANCE_MAX = 90    # ... prolongé tant que le vaisseau chauffe, jusqu'à ce maximum
VOYAGE_DELAI_VOIE_LIBRE = 3     # secondes de voie libre (ni étoile devant, ni chaleur) avant le FSD
VOYAGE_DUREE_CONTOURNEMENT = 12 # secondes de vol de chaque écart supplémentaire
VOYAGE_CONTOURNEMENTS_MAX = 3   # écarts automatiques ; au-delà, le COVAS te laisse contourner
VOYAGE_ATTENTE_VOIE_LIBRE = 180 # sans voie libre au bout de ce temps, le voyage s'arrête
VOYAGE_ATTENTE_ALIGNEMENT = 40  # secondes après l'appui sur le FSD (la charge en prend ~20) :
                                # sans saut d'ici là, le COVAS te demande de t'aligner
VOYAGE_CARBURANT_MIN = 0.25     # sous cette part du réservoir, le voyage s'arrête

# Détection de l'étoile à l'écran (module/ecran.py ; jeu en plein écran fenêtré).
# Calibrage : `python -m module.ecran` depuis Backend/, le jeu au premier plan.
ETOILE_ZONE = 0.20              # côté du carré central analysé (part de la hauteur d'écran)
ETOILE_SEUIL_LUMIERE = 235      # un pixel compte comme « étoile » si R, G et B dépassent ça
ETOILE_PART_OBSTRUCTION = 0.02  # au-delà de cette part de pixels blancs : étoile devant

# Sortir le train tout seul dès que la station autorise l'apontage
TRAIN_AUTO_APONTAGE = True

# Drones : numéro du groupe de tir (1 = le premier) et gâchette ("principal" ou
# "secondaire") où tu as rangé chaque contrôleur. None = pas encore réglé.
DRONES = {
    "prospection": {"groupe": None, "tir": "principal"},
    "collecte": {"groupe": None, "tir": "principal"},
}

# Réactions automatiques (désactivées au lancement ; « COVAS, active les réactions »)
REACTIONS_AU_DEMARRAGE = False
REACTIONS = {
    "surchauffe": True,       # surchauffe -> puce thermique
    "bouclier_tombe": True,   # boucliers hors ligne -> énergie aux systèmes
    "interdiction": True,     # arraché de supercroisière -> énergie aux systèmes
}

# Annonces vocales de ce que tu fais toi-même (touche, HOTAS). False = il se tait pour ce module.
ANNONCES_MANUELLES = {
    "fsd": True, "train": True, "armes": True, "soute": True,
    "phares": True, "nvg": True, "silencieux": True, "analyse": True,
}

ATTENTE_ECRAN = 2.5     # secondes laissées au jeu pour afficher l'écran des services
# ---------------------------------------------------------------------------

DUREE_APPUI = 0.06      # Elite rate parfois les appuis trop brefs
PAUSE_ENTRE = 0.12

# Macros simples : nom de l'action -> [(touche, nombre d'appuis), ...]
MACROS = {
    "train_atterrissage": [("train", 1)],
    "soute": [("soute", 1)],
    "reset": [("pips_equilibre", 1)],
    "lock": [("cible", 1)],
    "boost": [("boost", 1)],
    # Énergie à fond : étapes réglées dans Réglages > Commandes
    **{cle: [] for cle in commandes.SEQUENCES_MACROS},
}

# Les modes d'énergie (combat, esquive, croisière...) sont réglés dans l'interface : voir
# reglages.py. Touches à presser avant de placer les pips :
AVANT_PIPS = {"fsd": [("saut", 1)]}


# Branchés par actions.py (ce module ne lit pas l'état du jeu lui-même)
def lire_pips():
    return None


def vaisseau_actuel():
    return None


def normaliser(nom: str) -> str:
    """'mode_Croisière' -> 'mode_croisiere' (minuscules, sans accents)."""
    sans_accents = unicodedata.normalize("NFKD", nom or "").encode("ascii", "ignore").decode()
    return sans_accents.lower().strip()


STOP = threading.Event()      # levé par la commande « stop » : les appuis s'interrompent
_enfoncees = set()
DERNIERS_APPUIS = {}          # touche -> heure du dernier appui du COVAS (voir annonces.py)


def touche_de(nom):
    """(touche, [modificateurs]) pour une commande, ou None s'il n'y en a pas. Par priorité :
    Réglages > Commandes, TOUCHES_FORCEES, fichier actuel du jeu, tableau de secours."""
    perso = reglages.touche_perso(nom)
    if perso:
        return perso
    jeu = None if nom in TOUCHES_FORCEES else commandes.touches_jeu().get(nom)
    if jeu:
        return jeu[0], list(jeu[1])
    valeur = TOUCHES.get(nom, nom)
    if not valeur:
        return None
    return (valeur, []) if isinstance(valeur, str) else (valeur[0], list(valeur[1]))


def touche_connue(nom) -> bool:
    return touche_de(nom) is not None


def nom_touche(nom) -> str:
    """La touche telle qu'on l'affiche : 'ctrlleft + f9'."""
    valeur = touche_de(nom)
    return " + ".join(valeur[1] + [valeur[0]]) if valeur else "aucune"


def _enfoncer(touche):
    _enfoncees.add(touche)
    pydirectinput.keyDown(touche)


def _relacher(touche):
    pydirectinput.keyUp(touche)
    _enfoncees.discard(touche)


def relacher_tout():
    """Relâche ce qui serait resté enfoncé (après un « stop »)."""
    for touche in list(_enfoncees):
        _relacher(touche)


def appuyer(nom: str, fois: int = 1, duree: float = None) -> bool:
    """Appuie sur une touche du tableau TOUCHES (ou une touche brute).
    Renvoie False si la touche n'existe pas ou si un « stop » est arrivé."""
    valeur = touche_de(nom)
    if not valeur:
        print(f"[Macros] Pas de touche pour « {nom} » ({touches.libelle(nom)}).")
        return False
    touche, modificateurs = valeur
    for _ in range(fois):
        if STOP.is_set():
            return False
        DERNIERS_APPUIS[nom] = time.monotonic()
        for m in modificateurs:
            _enfoncer(m)
        _enfoncer(touche)
        fin = time.monotonic() + (duree or DUREE_APPUI)
        while time.monotonic() < fin and not STOP.is_set():
            time.sleep(0.02)
        _relacher(touche)
        for m in reversed(modificateurs):
            _relacher(m)
        time.sleep(PAUSE_ENTRE)
    return True


def jouer_etapes(etapes) -> bool:
    """Joue une séquence (commandes et pauses). False si une touche manque ou sur « stop »."""
    for etape in etapes:
        pause = commandes.duree_pause(etape)
        if pause is not None:
            if STOP.wait(pause):
                return False
        elif not appuyer(etape):
            return False
    return True


def executer_touches(action: str) -> bool:
    """Exécute la macro simple ou le mode d'énergie associé à l'action.
    Renvoie False si elle n'existe pas ou n'a pas abouti."""
    cle = normaliser(action)
    if reglages.est_mode(cle):
        return appliquer_mode(cle) in ("ok", "sans_verification")
    if cle in commandes.SEQUENCES_MACROS:
        return jouer_etapes(reglages.sequence(cle))
    etapes = MACROS.get(cle)
    if not etapes:
        print(f"[Macros] Aucune touche associée à l'action : {action}")
        return False
    for touche, fois in etapes:
        if not appuyer(touche, fois):
            return False
    return True


def appliquer_mode(cle: str) -> str:
    """Place les pips du mode pour le vaisseau actuel. Renvoie le résultat de pips.appliquer."""
    for touche, fois in AVANT_PIPS.get(cle, ()):
        if not appuyer(touche, fois):
            return "interrompu"
    return pips.appliquer(reglages.pips_pour(cle, vaisseau_actuel()), lire_pips, appuyer)


FENETRE_JEU = "FrontierDevelopmentsAppWinClass"


def jeu_au_premier_plan() -> bool:
    """True si la fenêtre du jeu a déjà le clavier (sans rien changer)."""
    if os.name != "nt":
        return True
    import ctypes
    user32 = ctypes.windll.user32
    fenetre = user32.FindWindowW(FENETRE_JEU, None)
    return bool(fenetre) and user32.GetForegroundWindow() == fenetre


TITRE_INTERFACE = "COVAS — Assistance de bord"     # <title> de Frontend/interface.html


def _premier_plan(fenetre) -> bool:
    """Met une fenêtre Windows au premier plan (la restaure si elle est réduite)."""
    import ctypes
    user32 = ctypes.windll.user32
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


def focaliser_interface() -> bool:
    """Ramène au premier plan la fenêtre du navigateur qui affiche l'interface.
    Renvoie False si aucune fenêtre ne la montre (fermée, ou onglet pas affiché)."""
    if os.name != "nt":
        return False
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    trouvees = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def examiner(fenetre, _):
        longueur = user32.GetWindowTextLengthW(fenetre)
        if longueur and user32.IsWindowVisible(fenetre):
            titre = ctypes.create_unicode_buffer(longueur + 1)
            user32.GetWindowTextW(fenetre, titre, longueur + 1)
            if titre.value.startswith(TITRE_INTERFACE):
                trouvees.append(fenetre)
        return True

    user32.EnumWindows(examiner, 0)
    return bool(trouvees) and _premier_plan(trouvees[0])


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
    return _premier_plan(fenetre)
