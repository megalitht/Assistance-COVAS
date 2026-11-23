"""
commandes.py — Touches et séquences réglables dans l'interface (Réglages > Commandes).

  - TOUCHES : une touche choisie ici remplace, pour le COVAS seulement, celle lue dans le
    fichier du jeu. Le fichier .binds n'est jamais écrit depuis ce module : pour que le jeu
    réagisse, la même touche doit être assignée dans Options > Commandes.
  - SÉQUENCES : la suite d'appuis des menus (apontage, décollage, ravitaillement...). Une étape
    est le nom d'une commande (« ui_bas ») ou une attente (« pause:0.5 », en secondes).

Module léger : ni micro, ni envoi de touches, pas d'import de macros.py.
"""
import os
import re
import time
import xml.etree.ElementTree as ET

from module import touches

# Utilisé pour les commandes que le fichier du jeu ne donne pas.
# None = pas de touche connue : le COVAS refusera la commande en expliquant quoi régler.
TOUCHES_SECOURS = {
    # Vol
    "train": "l",
    "soute": "home",
    "cible": "t",
    "boost": "tab",
    "saut": "j",
    "supercroisiere": None,
    "vitesse_zero": "x",
    "vitesse_75": None,
    "vitesse_max": None,
    "poussee_haut": "r",
    "tangage_haut": None,
    "tangage_bas": None,
    "assistance_vol": "z",      # emplacement physique : la touche W d'un clavier AZERTY
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
    "ui_onglet_gauche": "q",
    "ui_onglet_droite": "e",
    "ui_selection": "space",
    "ui_retour": "backspace",
    # Écran
    "ec_nav": "1",
    "ec_com": "2",
    "ec_deploy": "3",
    "ec_sys": "4",
    "carte_galaxie": None,
    "carte_systeme": None,
    # Cockpit
    "nvg": None,
    "phares": "insert",
    "armement": "u",
    "hud": None,
    "silencieux": "delete",
    # Combat
    "puce_thermique": "v",
    "leurres": None,
    "cible_menace": "h",
    "cible_hostile": None,
    "sous_systeme_suivant": "y",
    "sous_systeme_precedent": None,
    "tir_principal": None,
    "tir_secondaire": None,
    "groupe_suivant": "n",
    "groupe_precedent": None,
    # Chasseur embarqué
    "chasseur_defense": None,
    "chasseur_attaque": None,
    "chasseur_feu_libre": None,
    "chasseur_position": None,
    "chasseur_suivre": None,
    "chasseur_cessez": None,
    "chasseur_rappel": None,
}

GROUPES = (
    ("vol", "Vol", ("train", "soute", "cible", "boost", "saut", "supercroisiere", "vitesse_zero",
                    "vitesse_75", "vitesse_max", "poussee_haut", "tangage_haut", "tangage_bas",
                    "assistance_vol")),
    ("energie", "Énergie", ("pips_sys", "pips_moteurs", "pips_armes", "pips_equilibre")),
    ("menus", "Menus du jeu", ("ui_haut", "ui_bas", "ui_gauche", "ui_droite", "ui_onglet_gauche",
                               "ui_onglet_droite", "ui_selection", "ui_retour")),
    ("panneaux", "Panneaux et cartes", ("ec_nav", "ec_com", "ec_deploy", "ec_sys",
                                        "carte_galaxie", "carte_systeme")),
    ("cockpit", "Cockpit", ("nvg", "phares", "armement", "hud", "silencieux")),
    ("combat", "Combat", ("puce_thermique", "leurres", "cible_menace", "cible_hostile",
                          "sous_systeme_suivant", "sous_systeme_precedent", "tir_principal",
                          "tir_secondaire", "groupe_suivant", "groupe_precedent")),
    ("chasseur", "Chasseur", ("chasseur_defense", "chasseur_attaque", "chasseur_feu_libre",
                              "chasseur_position", "chasseur_suivre", "chasseur_cessez",
                              "chasseur_rappel")),
)
# VRS et pied à terre : touches du jeu uniquement (pas de secours, une touche devinée pourrait
# déclencher autre chose), et absentes des séquences de menus.
GROUPES_SOL = (
    ("vrs", "VRS", tuple(n for n in touches.COMMANDES_SOL if n.startswith("vrs_"))),
    ("pied", "À pied", tuple(n for n in touches.COMMANDES_SOL if n.startswith("pied_"))),
)

# « pause » : attente après chaque appui, propre à la séquence (les menus du jeu sont lents)
SEQUENCES = {
    "apontage": {
        "nom": "Demande d'apontage",
        "note": "Depuis le cockpit : panneau de navigation, onglet des contacts, demande d'apontage.",
        "pause": 0.25,
        "etapes": ["ec_nav"] + ["ui_onglet_droite"] * 2 + ["ui_droite", "ui_selection"],
    },
    "decollage": {
        "nom": "Décollage",
        "note": "Dans le menu d'amarrage : aller sur « Décollage » et valider.",
        "pause": 0.15,
        "etapes": ["ui_haut"] * 4 + ["ui_bas"] * 2 + ["ui_selection"],
    },
    "services": {
        "nom": "Ouvrir les services",
        "note": "Dans le menu d'amarrage : aller sur « Services de la station » et valider.",
        "pause": 0.15,
        "etapes": ["ui_haut"] * 4 + ["ui_bas", "ui_selection"],
    },
    "ravitaillement": {
        "nom": "Ravitaillement",
        "note": "Jouée juste après « Ouvrir les services », depuis la position du curseur à "
                "l'ouverture de l'écran : Ravitailler, Réparer, Réarmer.",
        "pause": 0.25,
        "etapes": ["ui_selection", "ui_droite", "ui_selection", "ui_droite", "ui_selection"],
    },
    "amarrage_nomade": {
        "nom": "Amarrage du Nomad",
        "note": "Demande au vaisseau principal de récupérer le Nomad. Par défaut : la touche "
                "« rappel » du chasseur. Remplace-la ici si ton jeu demande une autre combinaison.",
        "pause": 0.25,
        "etapes": ["chasseur_rappel"],
    },
    "assistance_sc": {
        "nom": "Assistance de supercroisière",
        "note": "Autopilote station. Vide : le COVAS te demande de l'activer toi-même, car la ligne "
                "de la destination change d'un système à l'autre.",
        "pause": 0.3,
        "etapes": [],
    },
    "energie_sys": {
        "nom": "Énergie aux systèmes",
        "note": "Commande « énergie aux systèmes » et réaction aux boucliers tombés.",
        "pause": 0.0,
        "etapes": ["pips_equilibre"] + ["pips_sys"] * 4,
    },
    "energie_mtr": {
        "nom": "Énergie aux moteurs",
        "note": "Commande « énergie aux moteurs ».",
        "pause": 0.0,
        "etapes": ["pips_equilibre"] + ["pips_moteurs"] * 4,
    },
    "energie_arm": {
        "nom": "Énergie aux armes",
        "note": "Commande « énergie aux armes ».",
        "pause": 0.0,
        "etapes": ["pips_equilibre"] + ["pips_armes"] * 4,
    },
}
SEQUENCES_MACROS = ("energie_sys", "energie_mtr", "energie_arm")   # commandes simples de macros.py

ETAPES_MAX = 60
PAUSE_MIN, PAUSE_MAX = 0.1, 5.0
_PAUSE = re.compile(r"^pause:(\d(?:\.\d)?)$")

# Ce que le COVAS sait réellement envoyer. Ctrl droit et Alt Gr en sont exclus : mal transmis.
MODIFICATEURS = ("ctrlleft", "shiftleft", "shiftright", "altleft")
TOUCHES_VALIDES = frozenset(
    list("abcdefghijklmnopqrstuvwxyz0123456789") + list("'`,-./;=[\\]")
    + [f"f{n}" for n in range(1, 21)] + [f"numpad{n}" for n in range(10)]
    + ["space", "tab", "enter", "backspace", "capslock", "insert", "delete", "home", "end",
       "pageup", "pagedown", "up", "down", "left", "right",
       "add", "subtract", "multiply", "divide", "decimal"]
    + list(MODIFICATEURS))


# ---------- Validation (tout ce qui vient de l'interface ou du fichier) ----------
def duree_pause(etape):
    """Secondes d'attente si l'étape est une pause valide, sinon None."""
    m = _PAUSE.match(etape) if isinstance(etape, str) else None
    if not m:
        return None
    duree = float(m.group(1))
    return duree if PAUSE_MIN <= duree <= PAUSE_MAX else None


def touche_valide(valeur):
    """[touche, [modificateurs]] propre, ou None."""
    if not isinstance(valeur, (list, tuple)) or len(valeur) != 2:
        return None
    touche, mods = valeur
    if not isinstance(touche, str) or touche not in TOUCHES_VALIDES:
        return None
    if not isinstance(mods, (list, tuple)) or len(mods) > 2:
        return None
    if any(not isinstance(m, str) or m not in MODIFICATEURS or m == touche for m in mods):
        return None
    return [touche, [m for m in MODIFICATEURS if m in mods]]


def sequence_valide(etapes):
    """Liste d'étapes propre, ou None : une séquence abîmée n'est jamais jouée à moitié."""
    if not isinstance(etapes, list) or len(etapes) > ETAPES_MAX:
        return None
    if all(isinstance(e, str) and (e in TOUCHES_SECOURS or duree_pause(e) is not None)
           for e in etapes):
        return list(etapes)
    return None


def nettoyer(brut):
    """Personnalisations valides ; ce qui revient à la valeur d'origine n'est pas gardé."""
    brut = brut if isinstance(brut, dict) else {}
    recues = brut.get("touches") if isinstance(brut.get("touches"), dict) else {}
    propres = {}
    for nom, valeur in recues.items():
        connue = nom in TOUCHES_SECOURS or nom in touches.COMMANDES_SOL
        touche = touche_valide(valeur) if connue else None
        if touche:
            propres[nom] = touche

    recues = brut.get("sequences") if isinstance(brut.get("sequences"), dict) else {}
    sequences = {}
    for cle, modele in SEQUENCES.items():
        etapes = sequence_valide(recues.get(cle))
        if etapes is not None and etapes != modele["etapes"]:
            sequences[cle] = etapes
    return {"touches": propres, "sequences": sequences}


# ---------- Touches du jeu (relues quand le fichier change, sans jamais l'écrire) ----------
_jeu = {"signature": None, "verifie": -1e9, "fichier": None, "azerty": False, "lues": {}}
RELECTURE = 2.0                 # secondes entre deux contrôles du fichier


def oublier_jeu():
    _jeu.update(signature=None, verifie=-1e9, fichier=None, azerty=False, lues={})


def _lire_jeu():
    maintenant = time.monotonic()
    if maintenant - _jeu["verifie"] < RELECTURE:
        return _jeu
    _jeu["verifie"] = maintenant
    try:
        signature = tuple((f, os.path.getmtime(f)) for f in touches.fichiers_utilises()) or None
        if signature != _jeu["signature"] or signature is None:
            fichier, azerty, lues = touches.lire_sans_ecrire()
            _jeu.update(signature=signature, fichier=fichier, azerty=azerty, lues=lues)
    except (OSError, ET.ParseError):
        pass                    # le jeu est en train de l'écrire : on garde la dernière lecture
    return _jeu


def touches_jeu():
    """{commande: (touche, [modificateurs])} d'après le fichier actuel du jeu."""
    return _lire_jeu()["lues"]


def catalogue():
    """Ce que l'onglet Commandes doit afficher."""
    jeu = _lire_jeu()
    groupes = []
    for identifiant, nom, noms in GROUPES + GROUPES_SOL:
        lignes = []
        for commande in noms:
            lue = jeu["lues"].get(commande)
            secours = TOUCHES_SECOURS.get(commande)
            lignes.append({"id": commande, "libelle": touches.libelle(commande),
                           "jeu": [lue[0], list(lue[1])] if lue else None,
                           "secours": [secours, []] if secours else None})
        groupes.append({"id": identifiant, "nom": nom, "commandes": lignes,
                        "sequences": (identifiant, nom, noms) in GROUPES})
    return {
        "fichier": os.path.basename(jeu["fichier"]) if jeu["fichier"] else None,
        "azerty": jeu["azerty"],
        "groupes": groupes,
        "sequences": [{"id": cle, "nom": s["nom"], "note": s["note"], "pause": s["pause"],
                       "etapes": list(s["etapes"])} for cle, s in SEQUENCES.items()],
        "etapes_max": ETAPES_MAX,
        "pause_min": PAUSE_MIN,
        "pause_max": PAUSE_MAX,
    }
