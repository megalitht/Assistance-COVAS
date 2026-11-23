"""
pips.py — Amène la répartition d'énergie du vaisseau sur une valeur précise.

Les valeurs sont en DEMI-pips, comme dans Status.json : [SYS, MOT, ARM], total 12, 8 au maximum
par ligne (3 pips aux systèmes et 3 aux armes = [6, 0, 6]).

Le trajet est calculé sur un modèle du répartiteur, puis le résultat est relu dans le jeu : si le
jeu n'a pas donné ce que le modèle prévoyait, le trajet est recalculé depuis la valeur réelle.

Aucune touche n'est envoyée ici : appliquer() reçoit ses fonctions (voir macros.appliquer_mode).
"""
import time
from collections import deque

TOTAL = 12
MAXIMUM = 8
EQUILIBRE = (4, 4, 4)
TOUCHES = ("pips_sys", "pips_moteurs", "pips_armes")
TOUCHE_EQUILIBRE = "pips_equilibre"

DELAI_LECTURE = 1.0     # secondes laissées au jeu pour écrire Status.json après les appuis
PAS_LECTURE = 0.05
APPUIS_CORRECTION = 20  # appuis au plus pour rattraper un écart entre le modèle et le jeu


def valide(pips):
    """La répartition sous forme de tuple, ou None si elle n'est pas possible dans le jeu."""
    if not isinstance(pips, (list, tuple)) or len(pips) != 3:
        return None
    if not all(isinstance(p, int) and not isinstance(p, bool) and 0 <= p <= MAXIMUM for p in pips):
        return None
    return tuple(pips) if sum(pips) == TOTAL else None


def apres_appui(etat, ligne):
    """Répartition après un appui sur une ligne : +1 pip, pris à moitié sur chacune des deux
    autres (en entier sur l'autre si l'une est vide). À 3,5 pips, seul un demi-pip reste à
    prendre : il vient de la plus petite ligne non vide."""
    nouveau = list(etat)
    gain = min(2, MAXIMUM - nouveau[ligne])
    if not gain:
        return tuple(nouveau)
    autres = [i for i in range(3) if i != ligne]
    nouveau[ligne] += gain
    if gain == 1:
        nouveau[min((i for i in autres if nouveau[i]), key=lambda i: nouveau[i])] -= 1
    elif all(nouveau[i] for i in autres):
        for i in autres:
            nouveau[i] -= 1
    else:
        nouveau[max(autres, key=lambda i: nouveau[i])] -= 2
    return tuple(nouveau)


def chemin(depart, cible, observe=None):
    """Plus courte suite de touches de `depart` à `cible` (l'équilibrage en fait partie).
    observe : {(état, ligne): état obtenu} vus dans le jeu, prioritaires sur le modèle.
    None si la cible est inatteignable."""
    depart, cible = tuple(depart), tuple(cible)
    observe = observe or {}
    if depart == cible:
        return []
    vus = {depart}
    file = deque([(depart, [])])
    while file:
        etat, suite = file.popleft()
        voisins = [(observe.get((etat, i)) or apres_appui(etat, i), TOUCHES[i]) for i in range(3)]
        voisins.append((EQUILIBRE, TOUCHE_EQUILIBRE))
        for suivant, touche in voisins:
            if suivant in vus:
                continue
            if suivant == cible:
                return suite + [touche]
            vus.add(suivant)
            file.append((suivant, suite + [touche]))
    return None


def _attendre(avant, lire, pause, delai, fini):
    """Relit le jeu jusqu'à ce que fini(valeur) soit vrai ; renvoie la dernière valeur lue."""
    derniere = avant
    for _ in range(max(1, int(delai / PAS_LECTURE))):
        pause(PAS_LECTURE)
        lue = valide(lire())
        if lue is not None:
            derniere = lue
            if fini(lue):
                break
    return derniere


def appliquer(cible, lire, appuyer, pause=time.sleep, delai=DELAI_LECTURE,
              corrections=APPUIS_CORRECTION):
    """Amène le vaisseau sur `cible`.

    lire()         : répartition actuelle du jeu, ou None si elle est inconnue
    appuyer(nom)   : appuie sur une touche, renvoie False si l'appui est annulé (« stop »)

    Tout le trajet part d'un coup (rapide en combat). Si le jeu n'arrive pas sur la cible, la
    correction se fait appui par appui, en retenant ce que chaque touche a réellement donné.

    Renvoie "ok", "sans_verification" (jeu illisible : touches envoyées depuis l'équilibre),
    "sans_reaction" (le jeu n'a pas bougé), "ecart" (cible non atteinte) ou "interrompu".
    """
    cible = valide(cible)
    if cible is None:
        raise ValueError("répartition de pips impossible")

    actuel = valide(lire())
    if actuel is None:
        envoye = all(appuyer(t) for t in [TOUCHE_EQUILIBRE] + chemin(EQUILIBRE, cible))
        return "sans_verification" if envoye else "interrompu"
    if actuel == cible:
        return "ok"
    if not all(appuyer(t) for t in chemin(actuel, cible)):
        return "interrompu"
    actuel = _attendre(actuel, lire, pause, delai, lambda lue: lue == cible)
    if actuel == cible:
        return "ok"
    return _corriger(actuel, cible, lire, appuyer, pause, delai, corrections)


def _a_reagi(touche, avant, apres):
    """False si le jeu aurait dû bouger et n'a pas bougé (menu ouvert, touche sans effet)."""
    if touche == TOUCHE_EQUILIBRE:
        return apres == EQUILIBRE
    return apres != avant or apres_appui(avant, TOUCHES.index(touche)) == avant


def _corriger(actuel, cible, lire, appuyer, pause, delai, corrections):
    """Un appui à la fois : ce que chaque touche a donné remplace le modèle pour la suite."""
    observe = {}
    for _ in range(corrections):
        suite = chemin(actuel, cible, observe)
        if not suite:
            return "ecart"
        touche, avant = suite[0], actuel
        if not appuyer(touche):
            return "interrompu"
        actuel = _attendre(avant, lire, pause, delai, lambda lue, depuis=avant: lue != depuis)
        if not _a_reagi(touche, avant, actuel):
            return "sans_reaction"
        if actuel == cible:
            return "ok"
        if touche != TOUCHE_EQUILIBRE:
            observe[(avant, TOUCHES.index(touche))] = actuel
    return "ecart"
