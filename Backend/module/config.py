"""
config.py — Réglages à modifier à la main : Backend/data/config.toml.

  - Le fichier est créé au premier lancement du COVAS (preparer()), avec toutes les valeurs par
    défaut et un commentaire en français pour chacune.
  - Il est relu dès qu'il change : inutile de relancer le COVAS (sauf pour le port du second écran).
  - Une section qui manque (ajoutée par une mise à jour du COVAS) est écrite à la fin du fichier,
    sans toucher au reste.
  - Une valeur invalide (texte à la place d'un nombre...) est ignorée : la valeur par défaut la
    remplace et le journal du COVAS le signale. Un fichier illisible garde les derniers réglages lus.

Lecture :  config.valeur("carburant", "seuil_bas")   ou   config.section("carburant")

Ce fichier n'est JAMAIS envoyé à l'interface : il contiendra le PIN du second écran et la clé Inara.
(Les réglages faits dans l'interface, eux, sont dans data/reglages.json : voir interface/reglages.py.)
"""
import copy
import os
import threading
import time
import tomllib
from datetime import date

DOSSIER_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHEMIN = os.path.join(DOSSIER_BACKEND, "data", "config.toml")
DELAI_VERIFICATION = 1.0        # s entre deux coups d'œil à la date du fichier

ENTETE = """\
# =====================================================================
#  COVAS — Configuration
#  Modifie les valeurs après le signe =, puis enregistre : le COVAS relit ce fichier
#  tout seul (pas besoin de le relancer, sauf pour le port du second écran).
#  Une ligne qui commence par # est un commentaire.
#  Ce fichier reste sur ce PC : il n'est jamais envoyé à l'interface ni au téléphone.
# =====================================================================
"""

# Une section par fonction. Le texte sert à la fois de modèle du fichier et de valeurs par
# défaut (DEFAUTS est lu dans ce même texte) : un seul endroit à modifier.
SECTIONS = {
    "carburant": """\
[carburant]
# Alertes de carburant, en pourcentage du réservoir principal.
seuil_bas = 25            # première alerte (réplique « alerte_carburant »), jauge orange
seuil_critique = 10       # alerte critique, jauge rouge clignotante
rearmement = 3            # points de % à regagner au-dessus d'un seuil pour qu'il puisse resonner
# Estimation du nombre de sauts restants : consommation moyenne des derniers sauts du vaisseau.
sauts_moyenne = 10        # nombre de derniers sauts pris pour la moyenne
# Sans historique, le COVAS prend la consommation maximale du FSD (valeur prudente).
# Si le FSD n'est pas encore connu non plus : cette valeur, en tonnes par saut.
secours_par_saut = 5.0
# Alerte prioritaire : le carburant ne suffit pas pour finir la route (ou atteindre la prochaine
# étoile récupérable si le vaisseau a un collecteur). Besoin estimé multiplié par cette marge.
marge_route = 1.1         # 1.1 = 10 % de sécurité
""",
    "route": """\
[route]
# Annonces pendant un voyage tracé dans la carte de la galaxie :
# route tracée, mi-parcours, sauts restants, dernier saut, arrivée.
annonces = true           # false : la route reste à l'écran, sans annonce vocale
sauts_restants = 5        # « Il reste 5 sauts » quand il en reste ce nombre (0 : jamais)
sauts_min_mi_parcours = 6 # pas d'annonce de mi-parcours pour une route plus courte
""",
    "second_ecran": """\
[second_ecran]
# L'interface sur un téléphone ou une tablette connecté au même Wi-Fi que ce PC.
# L'adresse à taper (et un QR code) est dans l'interface du PC : bouton « Second écran ».
# Il faut aussi autoriser ce port dans le pare-feu de Windows (voir le bouton « Second écran »).
actif = true              # false : l'interface reste réservée à ce PC
port = 8765               # port des pages et de la liaison (relancer le COVAS après un changement)
# Code demandé par le téléphone pour les boutons qui agissent sur le jeu (consulter reste libre).
# Entre guillemets, 4 à 8 chiffres, par exemple : pin = "4821". Vide : commandes refusées.
pin = ""
tentatives = 5            # erreurs de code avant de bloquer l'appareil
blocage_minutes = 5       # durée du blocage
""",
    "exploration": """\
[exploration]
# Données d'exploration et biologiques pas encore vendues (gardées dans data/suivi/exploration.json).
# Montants en millions de crédits.
paliers_millions = [10, 50, 100]  # annonce quand le total non vendu dépasse chacun de ces montants
rappel_min_millions = 1.0         # rappel à l'amarrage (station qui achète les données) au-delà de ce montant
rappel_bio = true                 # rappel aussi dans une station Vista Genomics (analyses biologiques)
annonce_corps_millions = 1.0      # un corps qui vaudra plus que ça une fois cartographié est annoncé au scan
""",
    "minage": """\
[minage]
# Drones de prospection : quels astéroïdes annoncer.
annoncer_noyau = true          # annonce spéciale quand l'astéroïde a un noyau (minage en profondeur)
annoncer_sans_interet = false  # true : annonce aussi les astéroïdes sans minerai intéressant
ignorer_deja_mines = true      # un astéroïde déjà entamé (moins de 100 % restant) n'est pas annoncé

[minage.minerais]
# Minerai (nom du journal, en minuscules) = pourcentage minimum pour annoncer l'astéroïde.
# Ajoute ou retire des lignes. Autres noms : silver, samarium, opal, monazite, rhodplumsite...
platinum = 15
painite = 20
osmium = 20
palladium = 20
gold = 25
lowtemperaturediamond = 15
tritium = 15
bromellite = 15
""",
    "materiaux": """\
[materiaux]
# Matériaux d'ingénieur (gardés dans data/suivi/materiaux.json). Limites du jeu par grade :
# 1 = 300, 2 = 250, 3 = 200, 4 = 150, 5 = 100.
seuil_presque_plein = 90  # % de la limite : annonce « stock presque plein » (puis « stock plein »)
""",
}

DEFAUTS = {}
for _nom, _texte in SECTIONS.items():
    DEFAUTS.update(tomllib.loads(_texte))

# Tables libres : le commandant y met les clés qu'il veut (ex. minerai -> pourcentage).
# Chaque valeur doit avoir le type des valeurs par défaut de la table.
LIBRES = {("minage", "minerais")}

_verrou = threading.Lock()
_etat = {"valeurs": None, "date": None, "verifie": 0.0}


# =====================================================================
#  LECTURE
# =====================================================================
def _meme_type(defaut, valeur):
    """La valeur lue a-t-elle le type de la valeur par défaut ? (entier et décimal acceptés
    l'un pour l'autre, jamais un booléen pour un nombre)"""
    if isinstance(defaut, bool):
        return isinstance(valeur, bool)
    if isinstance(defaut, (int, float)):
        return isinstance(valeur, (int, float)) and not isinstance(valeur, bool)
    return isinstance(valeur, type(defaut))


def _table_libre(defaut, lue, nom, erreurs):
    modele = next(iter(defaut.values()), None)
    propre = {}
    for cle, valeur in lue.items():
        if modele is None or _meme_type(modele, valeur):
            propre[cle] = valeur
        else:
            erreurs.append(f"{nom}.{cle} : valeur invalide, ignorée")
    return propre


def _fusionner(lu, erreurs):
    """Valeurs par défaut, remplacées par celles du fichier quand elles sont valides."""
    valeurs = copy.deepcopy(DEFAUTS)
    for section, contenu in lu.items():
        if section not in DEFAUTS:
            erreurs.append(f"section [{section}] inconnue, ignorée")
        elif not isinstance(contenu, dict):
            erreurs.append(f"[{section}] n'est pas une section, ignorée")
        else:
            _fusionner_section(section, contenu, valeurs[section], erreurs)
    return valeurs


def _fusionner_section(section, contenu, valeurs, erreurs):
    for cle, valeur in contenu.items():
        if cle not in DEFAUTS[section]:
            erreurs.append(f"{section}.{cle} : réglage inconnu, ignoré")
            continue
        defaut = DEFAUTS[section][cle]
        if (section, cle) in LIBRES and isinstance(valeur, dict):
            valeurs[cle] = _table_libre(defaut, valeur, f"{section}.{cle}", erreurs)
        elif _meme_type(defaut, valeur):
            valeurs[cle] = float(valeur) if isinstance(defaut, float) else valeur
        elif isinstance(defaut, str) and isinstance(valeur, int) and not isinstance(valeur, bool):
            valeurs[cle] = str(valeur)              # pin = 4821 sans guillemets : accepté
        else:
            erreurs.append(f"{section}.{cle} : valeur invalide ({valeur!r}), "
                           f"valeur par défaut utilisée ({defaut!r})")


def _lire():
    """Relit le fichier s'il a changé. Absent : valeurs par défaut. Illisible : on garde l'ancien."""
    try:
        date_fichier = os.path.getmtime(CHEMIN)
    except OSError:
        date_fichier = None
    if _etat["valeurs"] is not None and date_fichier == _etat["date"]:
        return
    _etat["date"] = date_fichier
    if date_fichier is None:
        _etat["valeurs"] = copy.deepcopy(DEFAUTS)
        return
    try:
        with open(CHEMIN, "rb") as f:
            lu = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as erreur:
        print(f"[Config] {os.path.basename(CHEMIN)} illisible ({erreur}) : "
              f"{'réglages précédents gardés' if _etat['valeurs'] else 'valeurs par défaut'}.")
        if _etat["valeurs"] is None:
            _etat["valeurs"] = copy.deepcopy(DEFAUTS)
        return
    erreurs = []
    _etat["valeurs"] = _fusionner(lu, erreurs)
    for erreur in erreurs:
        print(f"[Config] {erreur}")


def _actuelles():
    with _verrou:
        maintenant = time.monotonic()
        if _etat["valeurs"] is None or maintenant - _etat["verifie"] >= DELAI_VERIFICATION:
            _etat["verifie"] = maintenant
            _lire()
        return _etat["valeurs"]


def section(nom):
    """Copie des réglages d'une section (dict)."""
    return copy.deepcopy(_actuelles()[nom])


def valeur(nom_section, cle):
    return copy.deepcopy(_actuelles()[nom_section][cle])


def recharger():
    """Oublie les valeurs en mémoire : la prochaine lecture relit le fichier (tests)."""
    with _verrou:
        _etat.update(valeurs=None, date=None, verifie=0.0)


# =====================================================================
#  CRÉATION ET COMPLÉMENT DU FICHIER
# =====================================================================
def preparer():
    """Au démarrage du COVAS : crée le fichier, ou y ajoute les sections qui manquent.
    Renvoie la liste des sections écrites."""
    try:
        with open(CHEMIN, "rb") as f:
            lu = tomllib.load(f)
    except FileNotFoundError:
        lu = None
    except (OSError, tomllib.TOMLDecodeError) as erreur:
        print(f"[Config] {os.path.basename(CHEMIN)} illisible ({erreur}) : "
              "corrige-le, le COVAS utilise les valeurs par défaut en attendant.")
        return []
    try:
        os.makedirs(os.path.dirname(CHEMIN), exist_ok=True)
        if lu is None:
            texte = ENTETE + "".join("\n" + t for t in SECTIONS.values())
            provisoire = CHEMIN + ".tmp"
            with open(provisoire, "w", encoding="utf-8", newline="\r\n") as f:
                f.write(texte)
            os.replace(provisoire, CHEMIN)
            ecrites = list(SECTIONS)
        else:
            ecrites = [nom for nom in SECTIONS if nom not in lu]
            if ecrites:
                with open(CHEMIN, "a", encoding="utf-8", newline="\r\n") as f:
                    f.write(f"\n# --- Ajouté par le COVAS le {date.today():%d/%m/%Y} ---\n")
                    f.write("".join("\n" + SECTIONS[nom] for nom in ecrites))
    except OSError as erreur:
        print(f"[Config] Écriture de {os.path.basename(CHEMIN)} impossible : {erreur}")
        return []
    recharger()
    return ecrites
