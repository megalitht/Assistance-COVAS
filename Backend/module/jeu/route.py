"""
route.py — La route tracée dans la carte de la galaxie (NavRoute.json) : distances, sauts restants,
progression, et les annonces du voyage.

NavRoute.json donne la liste des systèmes, du départ (le système où la route a été tracée) à la
destination, avec leurs coordonnées (StarPos, en années-lumière) et leur classe d'étoile.

Sauts restants : vérifié sur les journaux du commandant, RemainingJumpsInRoute (événement FSDTarget,
écrit pendant le saut) vaut le nombre de sauts qui resteront une fois arrivé, comme le décompte
fait ici à partir de la position dans la liste. Si les deux diffèrent, le jeu a raison.

Annonces (une seule fois par route) : route tracée, mi-parcours, N sauts restants, dernier saut,
arrivée. Une route recalculée vers la même destination (le jeu le fait en cours de voyage) n'est
pas une nouvelle route.

Arrivée : vérifié sur 268 voyages des journaux du commandant, le jeu EFFACE la route au départ du
dernier saut (StartJump, NavRouteClear, puis FSDJump dans la destination). L'arrivée est donc
attendue dès cet effacement, et annoncée au FSDJump suivant s'il mène bien à la destination.

Module pur : ni touches, ni micro, ni réseau. Il se teste seul (tests/test_route.py).
"""
import math

CLASSES_RAVITAILLABLES = set("KGBFOAM")


def ravitaillable(classe):
    """Étoile où l'on peut écoper : classes K, G, B, F, O, A, M (« KGBFOAM »)."""
    return (classe or "").split("_")[0] in CLASSES_RAVITAILLABLES


def _distance(a, b):
    return math.dist(a, b) if a and b else 0.0


def lire_navroute(donnees):
    """NavRoute.json -> [{systeme, adresse, classe, distance (depuis l'étape précédente),
    ravitaillable}]. Une route vide ou effacée donne []."""
    etapes, precedent = [], None
    for saut in (donnees or {}).get("Route") or []:
        position = saut.get("StarPos")
        etapes.append({"systeme": saut.get("StarSystem"), "adresse": saut.get("SystemAddress"),
                       "classe": saut.get("StarClass"),
                       "distance": round(_distance(precedent, position), 2) if precedent else 0.0,
                       "ravitaillable": ravitaillable(saut.get("StarClass"))})
        precedent = position
    return etapes


def indice(etapes, systeme=None, adresse=None):
    """Position du système actuel dans la route (adresse d'abord : deux systèmes peuvent porter
    le même nom), None s'il n'y est pas. En cas de doublon, la dernière occurrence."""
    trouve = None
    for i, etape in enumerate(etapes):
        if adresse is not None and etape.get("adresse") is not None:
            meme = etape["adresse"] == adresse
        else:
            meme = bool(systeme) and etape["systeme"] == systeme
        if meme:
            trouve = i
    return trouve


def resume(etapes, position, cible=None):
    """Où en est le voyage.
    position : indice du système actuel (None : hors de la route).
    cible    : dernier FSDTarget {"systeme", "sauts_restants"} (sauts restants à l'arrivée dans le
               système d'où l'on vise `systeme`), pour recouper le décompte."""
    if len(etapes) < 2:
        return None
    total = sum(e["distance"] for e in etapes)
    sauts, source = _sauts_restants(etapes, position, cible)
    fiche = {"sauts_restants": sauts, "nombre_sauts": len(etapes) - 1, "source": source,
             "distance_totale": round(total, 2), "distance_restante": None,
             "distance_parcourue": None, "progression": None, "destination": etapes[-1]["systeme"]}
    if sauts is None:
        return fiche
    # Les « sauts » dernières étapes restent à parcourir
    restante = sum(e["distance"] for e in etapes[len(etapes) - sauts:]) if sauts else 0.0
    parcourue = max(0.0, total - restante)
    if total:
        progression = parcourue / total
    else:
        progression = 0.0 if sauts else 1.0
    fiche.update(distance_restante=round(restante, 2), distance_parcourue=round(parcourue, 2),
                 progression=round(progression, 4))
    return fiche


def _sauts_restants(etapes, position, cible):
    """(sauts restants, "route" ou "jeu"). Le décompte du jeu (FSDTarget) l'emporte quand il vise
    bien une étape de cette route et qu'il diffère, ou quand on est hors de la route."""
    compte = None if position is None else len(etapes) - 1 - position
    jeu = (cible or {}).get("sauts_restants")
    noms = [e["systeme"] for e in etapes]
    if not isinstance(jeu, int) or jeu < 0 or (cible or {}).get("systeme") not in noms[1:]:
        return compte, "route" if compte is not None else None
    if position is None:
        return min(jeu, len(etapes) - 1), "jeu"        # système actuel absent de la liste
    if compte and cible["systeme"] == noms[position + 1] and jeu != compte:
        return jeu, "jeu"
    return compte, "route"


class Annonceur:
    """Décide quoi annoncer pendant le voyage, une seule fois par route.

    Réglages (data/config.toml, section [route]) : sauts_restants (le « 5 sauts restants »),
    sauts_min_mi_parcours (pas de mi-parcours sur une route courte)."""

    def __init__(self):
        self.destination = None       # destination de la route suivie (None : pas de route)
        self.dites = set()            # annonces déjà faites pour cette route
        self.calibre = False          # la première route vue (au démarrage) n'est pas annoncée
        self.arrivee_attendue = None  # route effacée pendant le dernier saut : sa destination

    def nouvelle_route(self, etapes, parler=True):
        """NavRoute.json a changé. Renvoie "route_tracee" s'il faut l'annoncer, sinon None."""
        destination = etapes[-1]["systeme"] if len(etapes) >= 2 else None
        premiere = not self.calibre
        self.calibre = True
        if destination is None:
            # Fichier vidé : c'est l'événement NavRouteClear (route_effacee) qui oublie la route,
            # pour savoir si elle a été effacée pendant le dernier saut (l'ordre des deux varie).
            return None
        if destination == self.destination:
            return None               # route recalculée en chemin : même voyage
        self.destination, self.dites = destination, set()
        if premiere or not parler:
            self.dites.add("route_tracee")
            return None
        self.dites.add("route_tracee")
        return "route_tracee"

    def route_effacee(self, saut_vers=None):
        """NavRouteClear. saut_vers : système visé par le saut en cours (StartJump), s'il y en a un.
        Si c'est la destination, c'est le jeu qui efface la route du dernier saut."""
        if saut_vers and saut_vers == self.destination and "arrivee" not in self.dites:
            self.arrivee_attendue = saut_vers
        self.destination, self.dites = None, set()

    def arrivee(self, etat, reglages, parler=True, systeme=None):
        """Après un saut dans `systeme` : [(annonce, sauts restants)], au plus une."""
        attendue, self.arrivee_attendue = self.arrivee_attendue, None
        if attendue:
            return [("arrivee", 0)] if parler and systeme == attendue else []
        if not etat or etat.get("sauts_restants") is None or self.destination != etat.get("destination"):
            return []
        restants, nombre = etat["sauts_restants"], etat["nombre_sauts"]
        seuil = reglages.get("sauts_restants", 5)
        candidates = []
        if restants == 0:
            candidates.append("arrivee")
        elif restants == 1 and nombre > 1:
            candidates.append("dernier_saut")
        else:
            mi = (nombre >= reglages.get("sauts_min_mi_parcours", 6)
                  and (etat.get("progression") or 0) >= 0.5)
            if mi:
                candidates.append("mi_parcours")
            if restants == seuil and nombre > seuil:
                candidates.append("sauts_restants")
        a_dire = [c for c in candidates if c not in self.dites]
        self.dites.update(candidates)            # mi-parcours et « 5 sauts » le même saut : une phrase
        if not parler or not a_dire:
            return []
        return [(a_dire[0], restants)]
