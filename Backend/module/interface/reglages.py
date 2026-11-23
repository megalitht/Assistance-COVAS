"""
reglages.py — Réglages modifiés depuis l'interface (icône d'engrenage).

Enregistrés dans data/reglages.json. Pour l'énergie :
  modes      : les modes créés par le commandant (ceux de MODES_BASE existent toujours)
  defaut     : {mode: [SYS, MOT, ARM]}, valeurs de tous les vaisseaux (en demi-pips)
  vaisseaux  : {type de vaisseau: {mode: [SYS, MOT, ARM]}}, seulement ce qui diffère du défaut
Pour les commandes (voir commandes.py), seulement ce qui diffère de l'origine :
  touches    : {commande: [touche, [modificateurs]]}
  sequences  : {séquence: [étapes]}
Pour le son (voir audio.py) :
  audio      : {entree: micro, sortie: casque ou haut-parleurs (None : Windows), volume: 0 à 100}

Tout ce qui arrive de l'interface est revérifié ici. Aucune touche, aucun import de macros.py.
"""
import copy
import json
import math
import os
import re

from module import commandes as clavier
from module import pips as moteur

DOSSIER_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHEMIN = os.path.join(DOSSIER_BACKEND, "data", "reglages.json")

# Valeurs de départ : ce que donnaient les anciennes macros à partir d'une répartition équilibrée.
# applicable=False : le bouton « Appliquer » n'existe pas (la commande ferait autre chose : un saut).
MODES_BASE = (
    {"id": "mode_combat", "nom": "Combat", "pips": (4, 0, 8), "declencheur": "« mode combat »"},
    {"id": "mode_esquive", "nom": "Esquive", "pips": (6, 6, 0), "declencheur": "« mode esquive »"},
    {"id": "mode_croisiere", "nom": "Croisière", "pips": (4, 8, 0),
     "declencheur": "« mode croisière »"},
    {"id": "mode_recuperation", "nom": "Récupération", "pips": (8, 4, 0),
     "declencheur": "« récupération »"},
    {"id": "pips_defense", "nom": "Défense", "pips": (8, 4, 0),
     "declencheur": "Fuite et interdiction"},
    {"id": "fsd", "nom": "Saut FSD", "pips": (4, 8, 0), "declencheur": "Au lancement du FSD",
     "applicable": False},
)
_BASE = {m["id"]: m for m in MODES_BASE}

# Commandes vocales des modes qui n'ont pas d'entrée dans barks.json
VOIX_BASE = {"mode_esquive": ["esquive", "mode esquive"]}

MODES_PERSO_MAX = 12
VAISSEAUX_MAX = 80
LONGUEUR_NOM = 24
LONGUEUR_PERIPHERIQUE = 200
_ID_PERSO = re.compile(r"^mode_perso_[a-z0-9]{1,16}$")
_TYPE_VAISSEAU = re.compile(r"^[a-z0-9_]{1,40}$")

_doc = None
_barks = None              # commandes vocales en mémoire (main.py), tenues à jour ici
_cles_vocales = set()


def _nom_propre(nom):
    return " ".join(nom.split())[:LONGUEUR_NOM].strip() if isinstance(nom, str) else ""


def _vierge():
    return nettoyer({})


def _description_base(mode):
    return {"id": mode["id"], "nom": mode["nom"], "base": True,
            "declencheur": mode["declencheur"], "applicable": mode.get("applicable", True)}


def _modes_perso(brut):
    """Modes du commandant : identifiant valide, nom non vide et unique."""
    noms = {m["nom"].casefold() for m in MODES_BASE}
    vus, modes = set(), []
    for mode in brut if isinstance(brut, list) else []:
        if len(modes) >= MODES_PERSO_MAX:
            break
        if not isinstance(mode, dict) or mode.get("base"):
            continue
        identifiant, nom = mode.get("id"), _nom_propre(mode.get("nom"))
        if not isinstance(identifiant, str) or not _ID_PERSO.match(identifiant):
            continue
        if not nom or identifiant in vus or nom.casefold() in noms:
            continue
        vus.add(identifiant)
        noms.add(nom.casefold())
        modes.append({"id": identifiant, "nom": nom, "base": False,
                      "declencheur": f"« mode {nom.lower()} »", "applicable": True})
    return modes


def _audio_propre(brut):
    """Micro, sortie et volume valides (un nom de périphérique absent reste permis : débranché)."""
    brut = brut if isinstance(brut, dict) else {}

    def peripherique(valeur):
        return valeur if isinstance(valeur, str) and 0 < len(valeur) <= LONGUEUR_PERIPHERIQUE else None

    volume = brut.get("volume")
    valide = isinstance(volume, (int, float)) and not isinstance(volume, bool) and math.isfinite(volume)
    return {"entree": peripherique(brut.get("entree")), "sortie": peripherique(brut.get("sortie")),
            "volume": max(0, min(100, round(volume))) if valide else 100}


def nettoyer(brut):
    """Document complet et valide à partir de n'importe quoi (le reste est ignoré)."""
    pips = brut.get("pips") if isinstance(brut, dict) else None
    pips = pips if isinstance(pips, dict) else {}
    perso = _modes_perso(pips.get("modes"))
    ids = list(_BASE) + [m["id"] for m in perso]

    recu = pips.get("defaut") if isinstance(pips.get("defaut"), dict) else {}
    defaut = {}
    for identifiant in ids:
        valeur = moteur.valide(recu.get(identifiant))
        depart = _BASE[identifiant]["pips"] if identifiant in _BASE else moteur.EQUILIBRE
        defaut[identifiant] = list(valeur or depart)

    vaisseaux = {}
    recus = pips.get("vaisseaux") if isinstance(pips.get("vaisseaux"), dict) else {}
    for type_vaisseau, valeurs in recus.items():
        cle = type_vaisseau.lower() if isinstance(type_vaisseau, str) else ""
        if len(vaisseaux) >= VAISSEAUX_MAX or not _TYPE_VAISSEAU.match(cle):
            continue
        valeurs = valeurs if isinstance(valeurs, dict) else {}
        vaisseaux[cle] = {i: list(moteur.valide(valeurs[i])) for i in ids
                          if moteur.valide(valeurs.get(i)) is not None}

    return {"pips": {"modes": [_description_base(m) for m in MODES_BASE] + perso,
                     "defaut": defaut, "vaisseaux": vaisseaux},
            "commandes": clavier.nettoyer(brut.get("commandes") if isinstance(brut, dict) else None),
            "audio": _audio_propre(brut.get("audio") if isinstance(brut, dict) else None)}


def _sur_disque(doc):
    """Ce qui est écrit : les modes de base sont dans le code, pas dans le fichier."""
    pips = doc["pips"]
    return {"version": 1, "pips": {
        "modes": [{"id": m["id"], "nom": m["nom"]} for m in pips["modes"] if not m["base"]],
        "defaut": pips["defaut"], "vaisseaux": pips["vaisseaux"]},
        "commandes": doc["commandes"], "audio": doc["audio"]}


def charger(chemin=None):
    """Lit le fichier. Illisible : il est mis de côté et les valeurs de départ reprennent."""
    global _doc, CHEMIN
    if chemin:
        CHEMIN = chemin
    try:
        with open(CHEMIN, "r", encoding="utf-8") as f:
            _doc = nettoyer(json.load(f))
    except FileNotFoundError:
        _doc = _vierge()
    except (OSError, ValueError) as erreur:
        print(f"[Réglages] {os.path.basename(CHEMIN)} illisible : {erreur}")
        try:
            os.replace(CHEMIN, CHEMIN + ".illisible")
        except OSError:
            pass
        _doc = _vierge()
    _maj_commandes()
    return document()


def _actuel():
    if _doc is None:
        charger()
    return _doc


def document():
    """Les réglages, plus le catalogue des commandes pour l'interface (jamais enregistré)."""
    return {**copy.deepcopy(_actuel()), "catalogue": clavier.catalogue()}


def enregistrer(brut):
    """Remplace les réglages. Renvoie (document valide, message d'erreur ou None)."""
    global _doc
    nouveau = nettoyer(brut)
    _doc = nouveau
    _maj_commandes()
    temporaire = CHEMIN + ".tmp"
    try:
        with open(temporaire, "w", encoding="utf-8") as f:
            json.dump(_sur_disque(nouveau), f, ensure_ascii=False, indent=2)
        os.replace(temporaire, CHEMIN)
    except OSError as erreur:
        print(f"[Réglages] Écriture impossible : {erreur}")
        return document(), "Écriture du fichier de réglages impossible"
    return document(), None


# ---------- Lecture par les commandes ----------
def est_mode(cle):
    return any(m["id"] == cle for m in _actuel()["pips"]["modes"])


def nom_mode(cle):
    return next((m["nom"] for m in _actuel()["pips"]["modes"] if m["id"] == cle), cle)


def pips_pour(cle, type_vaisseau=None):
    """Répartition d'un mode pour ce vaisseau : la sienne, sinon celle par défaut."""
    pips = _actuel()["pips"]
    propre = pips["vaisseaux"].get((type_vaisseau or "").lower(), {})
    return tuple(propre.get(cle) or pips["defaut"][cle])


def touche_perso(nom):
    """(touche, [modificateurs]) choisie dans l'interface pour cette commande, ou None."""
    valeur = _actuel()["commandes"]["touches"].get(nom)
    return (valeur[0], list(valeur[1])) if valeur else None


def audio():
    """Micro, sortie et volume choisis dans Réglages > Son."""
    return dict(_actuel()["audio"])


def sequence(cle):
    """Étapes d'une séquence : celles du commandant, sinon celles d'origine."""
    propre = _actuel()["commandes"]["sequences"].get(cle)
    return list(clavier.SEQUENCES[cle]["etapes"] if propre is None else propre)


# ---------- Commandes vocales ----------
def _commandes():
    commandes = {cle: {"mots_cles": list(mots), "reponses": []} for cle, mots in VOIX_BASE.items()}
    for mode in _actuel()["pips"]["modes"]:
        if not mode["base"]:
            commandes[mode["id"]] = {"mots_cles": [f"mode {mode['nom'].lower()}"], "reponses": []}
    return commandes


def _maj_commandes():
    global _cles_vocales
    if _barks is None:
        return
    for cle in _cles_vocales:
        _barks.pop(cle, None)
    commandes = _commandes()
    _barks.update(commandes)
    _cles_vocales = set(commandes)


def lier_commandes(barks):
    """Ajoute les modes aux commandes vocales, et les y garde à jour après chaque changement."""
    global _barks, _cles_vocales
    _barks, _cles_vocales = barks, set()
    _actuel()
    _maj_commandes()
