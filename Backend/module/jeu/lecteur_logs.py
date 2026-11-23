"""
lecteur_logs.py — Lecture des fichiers écrits par Elite Dangerous.

Trois tâches asynchrones, lancées par main.py :
  - surveiller_logs()                 : Journal.*.log (événements : sauts, dégâts, kills...)
  - surveiller_status_json()          : Status.json   (instantané : pips, carburant, drapeaux)
  - surveiller_fichiers_auxiliaires() : NavRoute.json, ModulesInfo.json, Cargo.json

Chaque tâche met à jour ETAT (dernier état connu, rangé par sections) et prévient
l'interface web. Les répliques vocales partent des événements du journal et de Status.json.

Messages envoyés à l'interface :
  {"type": "etat", "etat": {...}, "historique": [...]}           état complet (à la connexion)
  {"type": "maj", "section": "vaisseau", "donnees": {...}}       une section a changé
  {"type": "evenement", "evenement": {...}}                      une ligne du journal de bord
"""
import asyncio
import glob
import itertools
import json
import math
import os
import time
from collections import deque
from datetime import datetime, timezone

from module.jeu import chasse
from module.jeu import edsm
from module.jeu import exploration
from module.dialogue import morceaux
from module.jeu import sol
from module.jeu.avaries import nommer
from module.interface.serveur_ws import definir_instantane, envoyer_donnees_web

# --- CHEMINS D'ACCÈS ---
# Dossier standard du jeu. S'il a été déplacé, indique le bon chemin dans la
# variable d'environnement COVAS_DOSSIER_ED.
DOSSIER_ED = os.environ.get("COVAS_DOSSIER_ED") or os.path.join(
    os.path.expanduser("~"), "Saved Games", "Frontier Developments", "Elite Dangerous")

CHEMIN_STATUS = os.path.join(DOSSIER_ED, "Status.json")
CHEMIN_LOGS = os.path.join(DOSSIER_ED, "Journal.*.log")
CHEMIN_NAVROUTE = os.path.join(DOSSIER_ED, "NavRoute.json")
CHEMIN_MODULES = os.path.join(DOSSIER_ED, "ModulesInfo.json")
CHEMIN_SOUTE = os.path.join(DOSSIER_ED, "Cargo.json")

# --- RÉGLAGES ---
SYSTEMES_PROCHES_ACTIF = True    # interroge EDSM (envoie le nom du système actuel à edsm.net)
SYSTEMES_PROCHES_MAX = 120       # nombre de systèmes transmis à l'interface
DELAI_ENTRE_REPLIQUES = 15       # secondes avant de redire la même alerte
DELAI_MEME_SON = 8               # secondes avant de rejouer le même fichier audio
TAILLE_HISTORIQUE = 200          # lignes de journal de bord gardées en mémoire
SEUIL_VOIX_CORPS = 1_000_000     # cr une fois cartographié : en dessous, le scan reste à l'écran
FILE_MAX_ANNONCES = 2            # annonces en attente : au-delà, une nouvelle serait déjà périmée
# Annonces de chasse et de scan : elles s'enchaînent bien plus vite que les alertes
DELAIS_REPLIQUES = {"chasse_recherchee": 2, "chasse_clean": 2, "chasse_autorite": 2,
                    "chasse_sans_loi": 2, "chasse_joueur": 4, "chasse_gros_gibier": 4,
                    "chasse_dangereux": 6, "chasse_tir_clean": 8, "scan_valeur": 3, "scan_bio": 3,
                    "scan_premiere": 3, "exo_analyse": 3, "exo_distance_ok": 3}

# Drapeaux de Status.json utilisés ici (la liste complète est décodée par l'interface)
DRAPEAU_BOUCLIERS = 1 << 3
DRAPEAU_CARBURANT_BAS = 1 << 19
DRAPEAU_SURCHAUFFE = 1 << 20
DRAPEAU_DANS_LE_VAISSEAU = 1 << 24

CLASSES_RAVITAILLABLES = set("KGBFOAM")
EMPLACEMENTS_COSMETIQUES = ("paintjob", "decal", "shipname", "shipid", "shipkit", "bobble",
                            "weaponcolour", "enginecolour", "vesselvoice", "stringlights")

if not os.path.exists(DOSSIER_ED):
    print(f"[Erreur Critique] Le dossier Elite n'a pas été trouvé à : {DOSSIER_ED}")
else:
    print(f"[Système] Pointage des logs confirmé sur : {DOSSIER_ED}")


# =====================================================================
#  ÉTAT PARTAGÉ
# =====================================================================
ETAT = {}
HISTORIQUE = deque(maxlen=TAILLE_HISTORIQUE)
_identifiants = itertools.count(1)
_carnet = exploration.Carnet()   # corps du système et données à vendre
_veille = chasse.Veille()        # pilotes déjà annoncés
_corps_annonces = set()          # (système, corps, "valeur" ou "bio") déjà dits à voix haute


def _combat_vierge():
    return {"eliminations": 0, "primes": 0, "bons": 0, "coups_coque": 0, "boucliers_tombes": 0,
            "interdictions": 0, "morts": 0, "assaillant": None}


def _pilotage_vierge():
    """Ce que le commandant pilote hors du vaisseau mère : 'chasseur', 'nomade' ou rien."""
    return {"genre": None, "modele": None, "coque": None}


def _reinitialiser_etat():
    ETAT.clear()
    ETAT.update({
        "session": {"jeu_actif": False, "journal": None, "version": None},
        "commandant": {"nom": None, "credits": None, "mode_jeu": None,
                       "rangs": {}, "progression": {}},
        # coque_palier : la coque vient d'un HullDamage (écrit seulement à 80, 60, 40, 20 %) ;
        # dernier_coup : horodatage du dernier coup reçu sur la coque (relevé des modules dépassé ?)
        "vaisseau": {"type": None, "modele": None, "nom": None, "immat": None, "coque": None,
                     "coque_palier": False, "dernier_coup": None,
                     "boucliers": None, "portee_saut": None, "soute_max": None,
                     "carburant_max": None, "reserve_max": None, "rachat": None, "masse": None,
                     "verriere_brisee": False, "chasseur": None},
        "position": {"systeme": None, "coordonnees": None, "corps": None, "allegeance": None,
                     "economie": None, "gouvernement": None, "securite": None,
                     "population": None, "faction": None, "amarre": False, "station": None,
                     "corps_total": None, "corps_scannes": 0, "dernier_saut": None},
        "status": {},
        "route": {"etapes": [], "distance_totale": 0, "indice_actuel": None, "prochain": None},
        "modules": {"liste": [], "releve": None},
        "soute": {"total": 0, "inventaire": []},
        "cible": {"verrouillee": False},
        "combat": _combat_vierge(),
        "missions": {"liste": [], "anterieures": 0},
        "proches": {"etat": "attente", "systeme": None, "rayon": None, "total": 0, "liste": []},
        "sol": sol.vierge(),      # VRS et pied à terre : voir module/jeu/sol.py
        "chasse": chasse.vierge(),            # mode chasseur de primes : voir module/jeu/chasse.py
        "exploration": _carnet.vue(),         # valeur des corps : voir module/jeu/exploration.py
        "pilotage": _pilotage_vierge(),
    })


_reinitialiser_etat()
_corps_scannes = set()
_puissances = {}          # emplacement -> MW (ModulesInfo.json)

# Ce que le gestionnaire d'événement en cours veut publier
_lot = {"sections": set(), "lignes": [], "repliques": []}


_ecouteurs = set()


def ecouter_evenements(fonction):
    """Appelle fonction(evenement) pour chaque nouvel événement du journal.
    Renvoie une fonction à appeler pour arrêter l'écoute."""
    _ecouteurs.add(fonction)
    return lambda: _ecouteurs.discard(fonction)


async def annoncer(texte, gravite="info", categorie="covas"):
    """Message du COVAS lui-même, affiché dans le journal de bord de l'interface."""
    ligne = {"id": next(_identifiants),
             "h": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "nom": "COVAS", "categorie": categorie, "gravite": gravite, "texte": texte,
             "hostile": False, "n": 1}
    HISTORIQUE.append(ligne)
    print(f"[COVAS] {texte}")
    await envoyer_donnees_web({"type": "evenement", "evenement": ligne})


async def dialogue(locuteur, texte, detail=None):
    """Une réplique de conversation (« CMDR » ou « COVAS »), affichée dans le panneau
    Communications de l'interface. `detail` : précision chiffrée (carburant, solde...)."""
    ligne = {"id": next(_identifiants),
             "h": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "nom": locuteur, "categorie": "comms", "gravite": "info",
             "texte": f"{locuteur} : {texte}" if texte else locuteur,
             "hostile": False, "n": 1, "locuteur": locuteur.lower()}
    if detail:
        ligne["detail"] = detail
    HISTORIQUE.append(ligne)
    await envoyer_donnees_web({"type": "evenement", "evenement": ligne})


def _instantane():
    return {"type": "etat", "etat": ETAT, "historique": list(HISTORIQUE)}


async def _publier(*sections):
    for section in sections:
        await envoyer_donnees_web({"type": "maj", "section": section, "donnees": ETAT[section]})


def _touche(*sections):
    """Signale que ces sections de ETAT ont changé."""
    _lot["sections"].update(sections)


def _note(e, categorie, texte, gravite="info", hostile=False, fusion=False, impact=None):
    """Ajoute une ligne au journal de bord de l'interface.

    gravite : info | succes | attention | alerte
    hostile : True = l'interface bascule en vue combat
    fusion  : True = remplace la ligne précédente si c'est le même événement (compteur ×n)
    impact  : coup reçu par le vaisseau, montré sur l'hologramme :
              "bouclier" (absorbé), "effondrement" (boucliers tombés) ou "coque"
    """
    ligne = {"id": next(_identifiants), "h": e.get("timestamp"), "nom": e.get("event"),
             "categorie": categorie, "gravite": gravite, "texte": texte,
             "hostile": hostile, "n": 1}
    if impact:
        ligne["impact"] = impact
    if fusion and HISTORIQUE and HISTORIQUE[-1]["nom"] == ligne["nom"]:
        precedente = HISTORIQUE.pop()
        ligne["id"], ligne["n"] = precedente["id"], precedente["n"] + 1
    HISTORIQUE.append(ligne)
    _lot["lignes"].append(ligne)


def _parle(cle):
    """Demande une réplique vocale (clé de barks.json)."""
    _lot["repliques"].append(cle)


def _parle_morceaux(ids, secours):
    """Phrase chiffrée faite de morceaux enregistrés ; s'il en manque un, la réplique `secours`."""
    _lot["repliques"].append({"morceaux": ids, "secours": secours})


# --- Petits outils de mise en forme ---
def _nombre(n):
    return f"{int(n or 0):,}".replace(",", " ")


def _pourcent(x):
    return f"{(x or 0) * 100:.0f}\u00a0%"


def _credits(n):
    return f"{_nombre(n)} cr"


def _credits_courts(n):
    """12 400 cr, 3,4 M cr, 1,2 Md cr."""
    n = n or 0
    for seuil, unite in ((1e9, "Md"), (1e6, "M")):
        if n >= seuil:
            return f"{n / seuil:.1f}".replace(".", ",") + f"\u00a0{unite}\u00a0cr"
    return _credits(n)


def _loc(e, cle):
    """Texte traduit par le jeu si disponible, sinon l'identifiant brut nettoyé."""
    valeur = e.get(cle + "_Localised") or e.get(cle)
    if isinstance(valeur, str) and valeur.startswith("$"):
        valeur = valeur.strip("$;").replace("_name", "").replace("_", " ")
    return valeur


def _ravitaillable(classe):
    return (classe or "").split("_")[0] in CLASSES_RAVITAILLABLES


def _distance(a, b):
    return math.dist(a, b) if a and b else 0.0


# =====================================================================
#  VOIX
# =====================================================================
_voix = {"file": None, "generer": None}
_derniere_replique = {}
_dernier_son = {}
_cles_sans_son = set()


async def _dire(cle):
    if not _voix["generer"]:
        return
    maintenant = time.monotonic()
    delai = DELAIS_REPLIQUES.get(cle, DELAI_ENTRE_REPLIQUES)
    if maintenant - _derniere_replique.get(cle, -1e9) < delai:
        return
    if cle in DELAIS_REPLIQUES and _voix["file"].qsize() >= FILE_MAX_ANNONCES:
        return
    _derniere_replique[cle] = maintenant

    chemin_audio = await _voix["generer"](cle)
    if not chemin_audio:
        if cle not in _cles_sans_son:
            _cles_sans_son.add(cle)
            print(f'[Voix] Aucune réplique audio pour "{cle}" dans barks.json.')
        return
    if maintenant - _dernier_son.get(chemin_audio, -1e9) < min(delai, DELAI_MEME_SON):
        return
    _dernier_son[chemin_audio] = maintenant
    await _voix["file"].put(chemin_audio)


async def _dire_morceaux(ids, secours):
    """Dit une phrase assemblée (prime, valeur d'un corps) sans jamais laisser la file s'allonger."""
    if not _voix["generer"] or _voix["file"].qsize() >= FILE_MAX_ANNONCES:
        return
    chemin = await asyncio.to_thread(morceaux.assembler, ids)
    if chemin:
        await _voix["file"].put(chemin)
    else:
        await _dire(secours)


# =====================================================================
#  GESTIONNAIRES D'ÉVÉNEMENTS DU JOURNAL
#  Pour gérer un nouvel événement : une fonction décorée par @_sur("NomEvenement").
# =====================================================================
_GESTIONNAIRES = {}


def _sur(*noms):
    def decorateur(fonction):
        for nom in noms:
            _GESTIONNAIRES[nom] = fonction
        return fonction
    return decorateur


# ---------- Session & commandant ----------
@_sur("Fileheader")
def _entete(e):
    ETAT["session"].update(jeu_actif=True, version=e.get("gameversion"))
    if e.get("part", 1) == 1:          # nouvelle session de jeu : compteurs remis à zéro
        ETAT["combat"] = _combat_vierge()
        ETAT["missions"] = {"liste": [], "anterieures": 0}
        chasse.arreter(ETAT["chasse"])
        _veille.oublier()
        _corps_annonces.clear()
        _carnet.nouvelle_session()
        ETAT["exploration"] = _carnet.vue()
        ETAT["pilotage"] = _pilotage_vierge()
        _touche("combat", "missions", "chasse", "exploration", "pilotage")
    _touche("session")


@_sur("Commander")
def _commandant(e):
    ETAT["commandant"]["nom"] = e.get("Name")
    _touche("commandant")


@_sur("LoadGame")
def _chargement(e):
    ETAT["session"]["jeu_actif"] = True
    ETAT["commandant"].update(nom=e.get("Commander"), credits=e.get("Credits"),
                              mode_jeu=e.get("GameMode"))
    engin = (e.get("Ship") or "").lower()
    # Partie reprise à pied, en VRS ou en Nomad : le vaisseau du commandant reste le dernier connu
    if not ("suit" in engin or engin.startswith("lander") or "buggy" in engin or "_srv" in engin):
        ETAT["vaisseau"].update(type=e.get("Ship"), modele=e.get("Ship_Localised"),
                                nom=e.get("ShipName"), immat=e.get("ShipIdent"))
    if engin.startswith("lander"):
        _piloter("nomade", e.get("Ship_Localised") or "Nomad")
    else:
        _piloter(None)
    _touche("session", "commandant", "vaisseau")
    _note(e, "systeme", f"Session ouverte — CMDR {e.get('Commander', '?')}", "succes")
    if "suit" not in engin:      # pas à pied
        _parle("bienvenue")


@_sur("Rank")
def _rangs(e):
    ETAT["commandant"]["rangs"] = {c: v for c, v in e.items() if isinstance(v, int)}
    _touche("commandant")


@_sur("Progress")
def _progression(e):
    ETAT["commandant"]["progression"] = {c: v for c, v in e.items() if isinstance(v, int)}
    _touche("commandant")


@_sur("Promotion")
def _promotion(e):
    for domaine, rang in e.items():
        if isinstance(rang, int):
            ETAT["commandant"]["rangs"][domaine] = rang
    _touche("commandant")
    _note(e, "systeme", "Promotion obtenue", "succes")


@_sur("Shutdown")
def _fermeture(e):
    ETAT["session"]["jeu_actif"] = False
    _touche("session")
    _note(e, "systeme", "Jeu fermé")


# ---------- Vaisseau ----------
@_sur("Loadout")
def _equipement(e):
    carburant = e.get("FuelCapacity") or {}
    ETAT["vaisseau"].update(
        type=e.get("Ship"), nom=e.get("ShipName"), immat=e.get("ShipIdent"),
        coque=e.get("HullHealth"), coque_palier=False, portee_saut=e.get("MaxJumpRange"),
        soute_max=e.get("CargoCapacity"), carburant_max=carburant.get("Main"),
        reserve_max=carburant.get("Reserve"), rachat=e.get("Rebuy"), masse=e.get("UnladenMass"))
    liste = []
    for module in e.get("Modules") or []:
        emplacement = module.get("Slot", "")
        if emplacement.lower().startswith(EMPLACEMENTS_COSMETIQUES):
            continue
        ingenierie = module.get("Engineering")
        liste.append({
            "emplacement": emplacement,
            "objet": (module.get("Item") or "").lower(),
            "actif": module.get("On", True),
            "priorite": module.get("Priority"),
            "sante": module.get("Health"),
            "puissance": _puissances.get(emplacement),
            "ingenierie": {"plan": ingenierie.get("BlueprintName"),
                           "niveau": ingenierie.get("Level"),
                           "effet": ingenierie.get("ExperimentalEffect_Localised")}
            if ingenierie else None,
        })
    ETAT["modules"] = {"liste": liste, "releve": e.get("timestamp")}
    ETAT["chasse"]["profil"] = chasse.profil(liste)
    _touche("vaisseau", "modules", "chasse")


def _modules_par_objet(nom_objet):
    cle = (nom_objet or "").lower().strip("$;").replace("_name", "")
    return [m for m in ETAT["modules"]["liste"] if m["objet"] == cle]


def _coup_sur_la_coque(e):
    """Retient l'heure du coup : un relevé des modules plus ancien n'est plus fiable."""
    ETAT["vaisseau"]["dernier_coup"] = e.get("timestamp")
    _touche("vaisseau")


@_sur("HullDamage")
def _degats_coque(e):
    # Écrit seulement au passage des paliers 80, 60, 40 et 20 % (pas à chaque coup)
    sante = e.get("Health", 1.0)
    if e.get("Fighter"):
        if e.get("PlayerPilot") and ETAT["pilotage"]["genre"] == "chasseur":
            ETAT["pilotage"]["coque"] = sante
            _touche("pilotage")
        _note(e, "combat", f"Chasseur touché — coque {_pourcent(sante)}", "attention", hostile=True)
        return
    ETAT["vaisseau"].update(coque=sante, coque_palier=True)
    ETAT["combat"]["coups_coque"] += 1
    _coup_sur_la_coque(e)
    _touche("vaisseau", "combat")
    critique = sante <= 0.30
    _note(e, "combat", f"Coque touchée — intégrité {_pourcent(sante)}",
          "alerte" if critique else "attention", hostile=True, impact="coque")
    _parle("alerte_blindage" if critique else "alerte_degats")


@_sur("ShieldState")
def _etat_boucliers(e):
    actifs = bool(e.get("ShieldsUp"))
    ETAT["vaisseau"]["boucliers"] = actifs
    _touche("vaisseau")
    if actifs:
        _note(e, "combat", "Boucliers rétablis", "succes")
        _parle("bouclier_retabli")
    else:
        ETAT["combat"]["boucliers_tombes"] += 1
        _touche("combat")
        _note(e, "combat", "Boucliers hors ligne", "alerte", hostile=True, impact="effondrement")
        _parle("alerte_bouclier")


def _impact_sur_le_vaisseau(cible):
    """Ce qu'encaisse le vaisseau quand on lui tire dessus : "bouclier", "coque" ou None.
    Le jeu ne le dit pas : on le déduit des boucliers (Status.json, en temps réel)."""
    drapeaux = ETAT["status"].get("flags") or 0
    if cible == "Fighter":
        return None                                   # c'est le chasseur qui est visé
    if cible != "Mothership" and drapeaux and not drapeaux & DRAPEAU_DANS_LE_VAISSEAU:
        return None                                   # « You » : à pied, en VRS ou en chasseur
    boucliers = bool(drapeaux & DRAPEAU_BOUCLIERS) if drapeaux else ETAT["vaisseau"]["boucliers"]
    return "coque" if boucliers is False else "bouclier"


@_sur("UnderAttack")
def _sous_le_feu(e):
    # Écrit à chaque salve reçue (souvent plusieurs fois par seconde), sans dire où
    cible = {"Fighter": "chasseur", "Mothership": "vaisseau mère"}.get(e.get("Target"))
    impact = _impact_sur_le_vaisseau(e.get("Target"))
    if impact == "coque":
        _coup_sur_la_coque(e)
    _note(e, "combat", f"Sous le feu ({cible})" if cible else "Sous le feu ennemi",
          "alerte", hostile=True, fusion=True, impact=impact)
    _parle("alerte_attaque")


@_sur("HeatWarning")
def _alerte_chaleur(e):
    _note(e, "vaisseau", "Surchauffe — température critique", "attention", fusion=True)
    _parle("alerte_surchauffe")


@_sur("HeatDamage")
def _degats_chaleur(e):
    _note(e, "vaisseau", "Dégâts thermiques sur les modules", "alerte", fusion=True)


@_sur("SystemsShutdown")
def _arret_systemes(e):
    _note(e, "combat", "Systèmes du vaisseau coupés", "alerte", hostile=True)


@_sur("CockpitBreached")
def _verriere(e):
    # La verrière casse quand son intégrité tombe à zéro : seul module dont on apprend
    # l'état au moment même où il est touché.
    ETAT["vaisseau"]["verriere_brisee"] = True
    for module in ETAT["modules"]["liste"]:
        if module["emplacement"].lower() == "shipcockpit":
            module["sante"] = 0.0
            _touche("modules")
    _coup_sur_la_coque(e)
    _note(e, "combat", "Verrière brisée — oxygène de secours", "alerte", hostile=True,
          impact="coque")
    _parle("verriere_brisee")


@_sur("Died")
def _mort(e):
    tueurs = [t.get("Name") for t in e.get("Killers") or []] or [e.get("KillerName_Localised")
                                                                 or e.get("KillerName")]
    tueurs = [t for t in tueurs if t]
    ETAT["combat"]["morts"] += 1
    ETAT["vaisseau"]["coque"] = 0
    _fin_chasse(e, forcer=True)
    chasse.perdre_primes(ETAT["chasse"])       # primes et données non vendues sont perdues
    _carnet.perdre_donnees()
    _publier_exploration()
    _piloter(None)
    _touche("combat", "vaisseau", "chasse")
    _note(e, "combat", "Vaisseau détruit" + (f" par {', '.join(tueurs)}" if tueurs else ""),
          "alerte")


@_sur("Resurrect")
def _resurrection(e):
    ETAT["vaisseau"].update(coque=1.0, coque_palier=False, dernier_coup=None, verriere_brisee=False)
    _touche("vaisseau")
    _note(e, "systeme", f"Vaisseau racheté — {_credits(e.get('Cost'))}", "attention")


@_sur("AfmuRepairs")
def _reparation_afmu(e):
    candidats = sorted(_modules_par_objet(e.get("Module")), key=lambda m: m["sante"] or 0)
    if candidats:
        candidats[0]["sante"] = e.get("Health", 1.0)
        _touche("modules")
    _note(e, "vaisseau", f"Réparation : {_loc(e, 'Module')} à {_pourcent(e.get('Health', 1.0))}",
          fusion=True)


@_sur("RebootRepair")
def _redemarrage(e):
    # Le jeu donne les emplacements des modules à 0 % remis en route (santé inconnue ensuite)
    emplacements = {(s or "").lower() for s in e.get("Modules") or []}
    noms = [nommer(m["objet"])[0] for m in ETAT["modules"]["liste"]
            if m["emplacement"].lower() in emplacements]
    detail = ", ".join(noms) if noms else f"{len(emplacements)} module(s)"
    _note(e, "vaisseau", f"Redémarrage/réparation : {detail}", "attention")


@_sur("RepairAll")
def _reparation_totale(e):
    ETAT["vaisseau"].update(coque=1.0, coque_palier=False, dernier_coup=None, verriere_brisee=False)
    for module in ETAT["modules"]["liste"]:
        module["sante"] = 1.0
    ETAT["modules"]["releve"] = e.get("timestamp")      # tout est à 100 % : relevé à jour
    _touche("vaisseau", "modules")
    _note(e, "station", f"Réparation complète — {_credits(e.get('Cost'))}", "succes")


@_sur("Repair")
def _reparation(e):
    objets = e.get("Items") or [e.get("Item")]
    for objet in objets:
        if (objet or "").lower() in ("hull", "all"):
            ETAT["vaisseau"].update(coque=1.0, coque_palier=False)
        if (objet or "").lower() == "all":
            for module in ETAT["modules"]["liste"]:
                module["sante"] = 1.0
        for module in _modules_par_objet(objet):
            module["sante"] = 1.0
    _touche("vaisseau", "modules")
    _note(e, "station", f"Réparation — {_credits(e.get('Cost'))}")


def _piloter(genre, modele=None):
    """Le commandant prend (ou quitte) les commandes d'un chasseur ou d'un Nomad."""
    nouveau = {"genre": genre, "modele": modele, "coque": 1.0 if genre else None}
    if nouveau != ETAT["pilotage"]:
        ETAT["pilotage"] = nouveau
        _touche("pilotage")


def _lache_commandes(genre):
    if ETAT["pilotage"]["genre"] == genre:
        _piloter(None)


@_sur("LaunchFighter")
def _chasseur_lance(e):
    # Les anciennes versions du jeu annonçaient le Nomad comme un chasseur (équipement base/starter)
    if e.get("Loadout") in ("base", "starter") and not e.get("") and e.get("PlayerControlled"):
        _piloter("nomade", "Nomad")
        _note(e, "exploration", "Nomad déployé")
        return
    ETAT["vaisseau"]["chasseur"] = "deploye"
    _touche("vaisseau")
    if e.get("PlayerControlled"):
        _piloter("chasseur", e.get("_Localised") or e.get("Type_Localised") or "Chasseur")
    _note(e, "combat", "Chasseur déployé")


@_sur("LaunchVessel")
def _vehicule_lance(e):
    if str(e.get("VesselType") or "").lower().startswith("lander"):
        if e.get("PlayerControlled", True):
            _piloter("nomade", e.get("VesselType_Localised") or "Nomad")
        _note(e, "exploration", "Nomad déployé")


@_sur("VehicleSwitch")
def _changement_poste(e):
    if e.get("To") == "Fighter":
        _piloter("chasseur", "Chasseur")
        _note(e, "combat", "Commandes du chasseur")
    elif e.get("To") == "Mothership":
        _lache_commandes("chasseur")
        _note(e, "combat", "Retour aux commandes du vaisseau")


@_sur("DockFighter")
def _chasseur_rentre(e):
    ETAT["vaisseau"]["chasseur"] = "a_bord"
    _lache_commandes("chasseur")
    _touche("vaisseau")
    _note(e, "combat", "Chasseur récupéré")


@_sur("FighterDestroyed")
def _chasseur_detruit(e):
    ETAT["vaisseau"]["chasseur"] = "detruit"
    _lache_commandes("chasseur")
    _touche("vaisseau")
    _note(e, "combat", "Chasseur détruit", "alerte", hostile=True)


@_sur("FighterRebuilt")
def _chasseur_reconstruit(e):
    ETAT["vaisseau"]["chasseur"] = "a_bord"
    _touche("vaisseau")
    _note(e, "combat", "Chasseur reconstruit", "succes")


@_sur("LaunchSRV")
def _vrs_sorti(e):
    ETAT["sol"]["vrs"] = {"modele": e.get("SRVType_Localised") or e.get("SRVType")}
    if e.get("PlayerControlled", True):
        sol.reperer_vaisseau(ETAT["sol"], ETAT["status"])
    _touche("sol")
    _note(e, "vaisseau", "VRS déployé")


@_sur("DockSRV")
def _vrs_rentre(e):
    ETAT["sol"]["vrs"] = None
    _touche("sol")
    nomad = str(e.get("SRVType") or "").lower().startswith("lander")
    if nomad:
        _lache_commandes("nomade")
    _note(e, "vaisseau", f"{'Nomad' if nomad else 'VRS'} récupéré — retour à bord")
    _parle("bienvenue")


@_sur("Embark")
def _embarquement(e):
    if e.get("SRV"):         # le jeu écrit aussi SRV pour le Nomad
        _note(e, "vaisseau", f"À bord du {'Nomad' if ETAT['pilotage']['genre'] == 'nomade' else 'VRS'}")
    elif e.get("Taxi") or e.get("Multicrew"):
        _note(e, "vaisseau", "Embarquement (taxi ou équipage)")
    else:
        engin = "du Nomad" if ETAT["pilotage"]["genre"] == "nomade" else "du vaisseau"
        _note(e, "vaisseau", f"Retour à bord {engin}", "succes")
        _parle("bienvenue")


@_sur("Disembark")
def _debarquement(e):
    if e.get("Taxi") or e.get("Multicrew"):
        sol.vaisseau_oublie(ETAT["sol"])      # arrivé autrement : le vaisseau n'est pas ici
        _touche("sol")
    elif not e.get("SRV") and e.get("OnPlanet"):
        sol.reperer_vaisseau(ETAT["sol"], ETAT["status"], e.get("Body"))
        _touche("sol")
    nomad = ETAT["pilotage"]["genre"] == "nomade"
    _note(e, "vaisseau", "Débarquement du Nomad" if nomad else
          "Débarquement du VRS" if e.get("SRV") else "Débarquement à pied")


@_sur("SuitLoadout", "SwitchSuitLoadout")
def _combinaison(e):
    sol.combinaison(ETAT["sol"], e)
    _touche("sol")


@_sur("ScanOrganic")
def _scan_organique(e):
    sol.scan_organique(ETAT["sol"], e, ETAT["status"])
    sol.actualiser(ETAT["sol"], ETAT["status"])
    analyse = _carnet.organique(e)
    exo = ETAT["sol"]["exobio"]
    prix = (exploration._especes_par_id().get(e.get("Species")) or {}).get("valeur")
    exo["valeur"] = prix
    exo["premier_pas"] = (((_carnet.corps.get(e.get("Body")) or {}).get("scan") or {})
                          .get("WasFootfalled") is False) and not e.get("WasLogged")
    _publier_exploration()
    _touche("sol")
    if exo["termine"]:
        detail = ""
        if analyse:
            total, bonus = analyse
            if total:
                detail = f" — {_credits_courts(total)}" + (" avec bonus du premier pas" if bonus else "")
                _parle_morceaux(morceaux.pour_analyse(total, bonus), "exo_analyse")
            else:
                _parle("exo_analyse")
        _note(e, "exploration", f"Analyse terminée — {exo['espece']}{detail}", "succes")
    else:
        valeur = f" — {_credits_courts(prix)}" if prix else ""
        _note(e, "exploration", f"Prélèvement {exo['echantillons']}/{sol.ECHANTILLONS} — {exo['espece']}{valeur}")


@_sur("SRVDestroyed")
def _vrs_detruit(e):
    ETAT["sol"]["vrs"] = None
    _touche("sol")
    nomad = str(e.get("SRVType") or "").lower().startswith("lander")
    if nomad:
        _lache_commandes("nomade")
    _note(e, "vaisseau", f"{'Nomad' if nomad else 'VRS'} détruit", "alerte")


# ---------- Combat ----------
@_sur("Interdicted")
def _interdit(e):
    ETAT["combat"]["interdictions"] += 1
    ETAT["combat"]["assaillant"] = e.get("Interdictor")
    _touche("combat")
    mode = "soumission" if e.get("Submitted") else "arraché de supercroisière"
    _note(e, "combat", f"Interdiction par {e.get('Interdictor', 'inconnu')} ({mode})",
          "alerte", hostile=True)
    _parle("alerte_interdiction")


@_sur("EscapeInterdiction")
def _interdiction_esquivee(e):
    _note(e, "combat", f"Interdiction esquivée ({e.get('Interdictor', 'inconnu')})", "succes")


@_sur("Interdiction")
def _interdiction_lancee(e):
    resultat = "réussie" if e.get("Success") else "échouée"
    _note(e, "combat", f"Interdiction {resultat} sur {e.get('Interdicted', 'la cible')}")


def _elimination(e, recompense, cle_total, texte):
    ETAT["combat"]["eliminations"] += 1
    ETAT["combat"][cle_total] += recompense or 0
    _touche("combat")
    _note(e, "combat", texte, "succes")
    _parle("kill_confirme")


# ---------- Mode chasseur de primes ----------
def _demarrer_chasse(e, zone=None, zone_nom=None, manuel=False):
    if chasse.activer(ETAT["chasse"], e.get("timestamp"), zone, zone_nom, manuel):
        _veille.oublier()
        lieu = f" — {zone_nom}" if zone_nom else ""
        _note(e, "combat", f"Mode chasseur de primes activé{lieu}", "succes")
        _parle("chasse_active")
    _touche("chasse")


def _fin_chasse(e, forcer=False):
    """Fin de la zone de chasse. Un mode allumé à la voix reste allumé jusqu'à l'ordre contraire."""
    if ETAT["chasse"]["manuel"] and not forcer:
        return
    bilan = chasse.arreter(ETAT["chasse"])
    if bilan is None:
        return
    _touche("chasse")
    _note(e, "combat", f"Fin de chasse — {bilan['eliminations']} élimination(s), "
                       f"{_credits_courts(bilan['gains'])}", "succes")
    if bilan["eliminations"]:
        _parle("chasse_fin")


async def commander_chasse(actif):
    """Ordre vocal ou bouton : allume ou coupe le mode chasseur de primes."""
    e = {"timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "event": "Chasse"}
    _lot["sections"], _lot["lignes"], _lot["repliques"] = set(), [], []
    if actif:
        _demarrer_chasse(e, manuel=True)
    else:
        _fin_chasse(e, forcer=True)
    sections, lignes, repliques = _lot["sections"], _lot["lignes"], _lot["repliques"]
    await _publier(*sections)
    for entree in lignes:
        await envoyer_donnees_web({"type": "evenement", "evenement": entree})
    for cle in repliques or ([] if actif else ["chasse_coupee"]):
        await _dire(cle)


@_sur("SupercruiseDestinationDrop")
def _arrivee_destination(e):
    zone, zone_nom = chasse.type_zone(e.get("Type"))
    if zone and ETAT["chasse"]["profil"]["pret"]:
        _demarrer_chasse(e, zone, zone_nom)


@_sur("Bounty")
def _prime(e):
    if not ETAT["chasse"]["actif"] and ETAT["chasse"]["profil"]["pret"]:
        _demarrer_chasse(e)                 # une prime touchée : on est en chasse, où qu'on soit
    recompense = chasse.prime(ETAT["chasse"], e)
    _touche("chasse")
    cible = _loc(e, "Target") or "Cible"
    _elimination(e, recompense, "primes", f"{cible} détruit — prime {_credits(recompense)}")


@_sur("FactionKillBond")
def _bon_de_combat(e):
    _elimination(e, e.get("Reward"), "bons",
                 f"Ennemi détruit — bon de combat {_credits(e.get('Reward'))}")


@_sur("PVPKill")
def _kill_joueur(e):
    _elimination(e, 0, "primes", f"CMDR {e.get('Victim', '?')} détruit")


@_sur("ShipTargeted")
def _cible(e):
    if not e.get("TargetLocked"):
        ETAT["cible"] = {"verrouillee": False}
    else:
        ETAT["cible"] = {
            "verrouillee": True, "vaisseau": _loc(e, "Ship"), "scan": e.get("ScanStage", 0),
            "pilote": _loc(e, "PilotName"), "rang": e.get("PilotRank"),
            "boucliers": e.get("ShieldHealth"), "coque": e.get("HullHealth"),
            "faction": e.get("Faction"), "statut": e.get("LegalStatus"),
            "prime": e.get("Bounty"), "sous_systeme": _loc(e, "Subsystem"),
            "sous_systeme_sante": e.get("SubsystemHealth"),
            "verdict": chasse.verdict(e),
        }
        if e.get("ScanStage") == 3 and _veille.nouvelle(e, time.monotonic()):
            _annoncer_cible(e, ETAT["cible"]["verdict"])
    _touche("cible")


def _annoncer_cible(e, fiche):
    """Première fois qu'on finit de scanner ce pilote : journal de bord et, en chasse, à voix haute."""
    chasse.compter_scan(ETAT["chasse"], fiche)
    _touche("chasse")
    nom = _loc(e, "PilotName") or _loc(e, "Ship") or "Contact"
    if fiche["code"] in ("recherche", "mandat"):
        _note(e, "combat", f"Cible recherchée : {nom} — prime {_credits(fiche['prime'])}", "attention")
    elif ETAT["chasse"]["actif"] and fiche["tirer"] is False and fiche["code"] != "allie":
        _note(e, "combat", f"{fiche['libelle']} : {nom} — {fiche['conseil'].lower()}")
    if not ETAT["chasse"]["actif"]:
        return
    for cle in chasse.repliques_cible(fiche):
        if cle == "chasse_recherchee" and fiche["prime"]:
            _parle_morceaux(morceaux.pour_cible(fiche["prime"]), cle)
        else:
            _parle(cle)


@_sur("CommitCrime")
def _infraction(e):
    montant = e.get("Fine") or e.get("Bounty") or 0
    tir_ami = ETAT["chasse"]["actif"] and e.get("CrimeType") in ("assault", "murder")
    _note(e, "combat", f"Infraction ({e.get('CrimeType', '?')}) — {_credits(montant)}",
          "alerte" if tir_ami else "attention")
    if tir_ami:
        _parle("chasse_tir_clean")


@_sur("CrimeVictim")
def _victime(e):
    ETAT["combat"]["assaillant"] = e.get("Offender")
    _touche("combat")
    _note(e, "combat", f"Agression par {e.get('Offender', 'inconnu')}", "alerte", hostile=True)


@_sur("Scanned")
def _scanne(e):
    _note(e, "combat", f"Vaisseau scanné ({e.get('ScanType', '?')})", "attention")


# ---------- Navigation ----------
def _maj_systeme(e):
    faction = e.get("SystemFaction") or {}
    ancien = ETAT["position"]["systeme"]
    ETAT["position"].update(
        systeme=e.get("StarSystem"), coordonnees=e.get("StarPos"),
        allegeance=e.get("SystemAllegiance") or None, economie=_loc(e, "SystemEconomy"),
        gouvernement=_loc(e, "SystemGovernment"), securite=_loc(e, "SystemSecurity"),
        population=e.get("Population"), faction=faction.get("Name"),
        corps=e.get("Body"), amarre=bool(e.get("Docked")), station=None)
    if ancien != e.get("StarSystem"):
        _corps_scannes.clear()
        ETAT["position"].update(corps_total=None, corps_scannes=0)
    _carnet.assurer_systeme(e.get("SystemAddress"), e.get("StarSystem"))
    _publier_exploration()
    _maj_progression_route()
    _touche("position", "route")


def _fiche_station(e, plateforme=None):
    return {"nom": e.get("StationName"), "type": e.get("StationType"),
            "economie": _loc(e, "StationEconomy"), "gouvernement": _loc(e, "StationGovernment"),
            "allegeance": e.get("StationAllegiance"),
            "faction": (e.get("StationFaction") or {}).get("Name"),
            "distance_ls": e.get("DistFromStarLS"), "plateforme": plateforme,
            "services": e.get("StationServices") or []}


def _maj_progression_route():
    route = ETAT["route"]
    noms = [etape["systeme"] for etape in route["etapes"]]
    systeme = ETAT["position"]["systeme"]
    route["indice_actuel"] = noms.index(systeme) if systeme in noms else None


@_sur("Location")
def _localisation(e):
    _maj_systeme(e)
    if e.get("Docked"):
        ETAT["position"]["station"] = _fiche_station(e)


@_sur("FSDJump", "CarrierJump")
def _saut(e):
    if e.get("event") == "FSDJump":
        _fin_chasse(e)
        _piloter(None)
    _maj_systeme(e)
    ETAT["position"]["dernier_saut"] = e.get("JumpDist")
    if e.get("Docked"):
        ETAT["position"]["station"] = _fiche_station(e)
    distance = f" — {e['JumpDist']:.1f} al" if e.get("JumpDist") else ""
    _note(e, "navigation", f"Arrivée dans {e.get('StarSystem', '?')}{distance}", "succes")


@_sur("StartJump")
def _depart_saut(e):
    if e.get("JumpType") == "Hyperspace":
        classe = f" (classe {e['StarClass']})" if e.get("StarClass") else ""
        _note(e, "navigation", f"Saut hyperespace vers {e.get('StarSystem', '?')}{classe}")
    else:
        _note(e, "navigation", "Passage en supercroisière")


@_sur("FSDTarget")
def _cible_fsd(e):
    ETAT["route"]["prochain"] = {
        "systeme": e.get("Name"), "classe": e.get("StarClass"),
        "ravitaillable": _ravitaillable(e.get("StarClass")),
        "sauts_restants": e.get("RemainingJumpsInRoute")}
    _touche("route")


@_sur("NavRouteClear")
def _route_effacee(e):
    ETAT["route"] = {"etapes": [], "distance_totale": 0, "indice_actuel": None, "prochain": None}
    _touche("route")
    _note(e, "navigation", "Route effacée")


@_sur("SupercruiseEntry")
def _entree_supercroisiere(e):
    ETAT["position"].update(corps=None, station=None, amarre=False)
    _fin_chasse(e)
    _piloter(None)
    _touche("position")


@_sur("SupercruiseExit")
def _sortie_supercroisiere(e):
    ETAT["position"]["corps"] = e.get("Body")
    _touche("position")
    _note(e, "navigation", f"Sortie de supercroisière — {e.get('Body', '?')}")


@_sur("ApproachBody")
def _approche_corps(e):
    ETAT["position"]["corps"] = e.get("Body")
    _touche("position")
    _note(e, "navigation", f"Approche orbitale — {e.get('Body', '?')}")


@_sur("LeaveBody")
def _depart_corps(e):
    ETAT["position"]["corps"] = None
    _touche("position")


@_sur("Touchdown")
def _pose(e):
    if not (e.get("Taxi") or e.get("Multicrew")):     # un taxi posé n'est pas notre vaisseau
        sol.vaisseau_pose(ETAT["sol"], e.get("Latitude"), e.get("Longitude"), e.get("Body"))
        _touche("sol")
    if e.get("PlayerControlled", True):
        _note(e, "navigation", f"Posé sur {e.get('Body', 'la surface')}", "succes")


@_sur("Liftoff")
def _decollage(e):
    # Sans pilote : renvoyé en orbite pendant que le commandant est au sol
    if not (e.get("Taxi") or e.get("Multicrew")):
        sol.vaisseau_oublie(ETAT["sol"], None if e.get("PlayerControlled", True) else "parti")
        _touche("sol")
    if e.get("PlayerControlled", True):
        _note(e, "navigation", "Décollage de la surface")


@_sur("JetConeBoost")
def _surcharge_fsd(e):
    _note(e, "navigation", f"FSD surchargé ×{e.get('BoostValue', '?')}", "succes")


@_sur("FuelScoop")
def _collecte_carburant(e):
    _note(e, "navigation", f"Carburant collecté — réservoir à {e.get('Total', 0):.1f} t",
          fusion=True)


# ---------- Stations ----------
@_sur("DockingRequested")
def _appontage_demande(e):
    _note(e, "station", f"Demande d'appontage — {e.get('StationName', '?')}")


@_sur("DockingGranted")
def _appontage_accorde(e):
    ETAT["position"]["station"] = {"nom": e.get("StationName"), "type": e.get("StationType"),
                                   "plateforme": e.get("LandingPad"), "services": []}
    _touche("position")
    _note(e, "station", f"Appontage autorisé — plateforme {e.get('LandingPad', '?')}", "succes")


RAISONS_REFUS_APPONTAGE = {
    "NoSpace": "aucune plateforme libre",
    "TooLarge": "vaisseau trop grand pour cette station",
    "Hostile": "la station vous est hostile",
    "Offences": "infractions en cours dans ce système",
    "Distance": "trop loin, approche à moins de 7,5 km",
    "ActiveFighter": "rappelle d'abord ton chasseur",
    "NoReason": "sans raison donnée",
    "RestrictedAccess": "accès restreint",
    "JumpImminent": "le porte-vaisseaux va sauter",
}


@_sur("DockingDenied")
def _appontage_refuse(e):
    raison = RAISONS_REFUS_APPONTAGE.get(e.get("Reason"), e.get("Reason", "raison inconnue"))
    _note(e, "station", f"Appontage refusé : {raison}", "alerte")


@_sur("DockingCancelled", "DockingTimeout")
def _appontage_annule(e):
    _note(e, "station", "Autorisation d'appontage annulée", "attention")


@_sur("Docked")
def _amarre(e):
    plateforme = (ETAT["position"]["station"] or {}).get("plateforme")
    ETAT["position"].update(amarre=True, station=_fiche_station(e, plateforme))
    _fin_chasse(e, forcer=True)
    _piloter(None)
    _touche("position")
    _note(e, "station", f"Amarré à {e.get('StationName', '?')}", "succes")


@_sur("Undocked")
def _desamarre(e):
    ETAT["position"].update(amarre=False, station=None)
    _touche("position")
    _note(e, "station", f"Départ de {e.get('StationName', 'la station')}")


@_sur("RefuelAll", "RefuelPartial")
def _plein(e):
    _note(e, "station", f"Ravitaillement +{e.get('Amount', 0):.1f} t — {_credits(e.get('Cost'))}")


@_sur("BuyAmmo")
def _munitions(e):
    _note(e, "station", f"Réarmement — {_credits(e.get('Cost'))}")


@_sur("RedeemVoucher")
def _bons_encaisses(e):
    if chasse.encaisser(ETAT["chasse"], e):
        _touche("chasse")
    _note(e, "station", f"Bons encaissés ({e.get('Type', '?')}) — {_credits(e.get('Amount'))}",
          "succes")


@_sur("ShipyardSwap")
def _changement_vaisseau(e):
    _note(e, "station", f"Changement de vaisseau : {_loc(e, 'ShipType')}")


# ---------- Exploration ----------
@_sur("FSSDiscoveryScan")
def _balayage(e):
    ETAT["position"]["corps_total"] = e.get("BodyCount")
    _touche("position")
    _note(e, "exploration", f"Balayage du système — {e.get('BodyCount', '?')} corps détectés")


def _publier_exploration():
    ETAT["exploration"] = _carnet.vue()
    _touche("exploration")


def _annoncer_valeur(fiche):
    """Un corps qui vaut le détour : le COVAS dit combien, une seule fois par corps."""
    cle = (_carnet.adresse, fiche["id"], "valeur")
    if cle in _corps_annonces or fiche["etoile"] or fiche["balise"] \
            or (fiche["valeur_carto"] or 0) < SEUIL_VOIX_CORPS:
        return
    _corps_annonces.add(cle)
    _parle_morceaux(morceaux.pour_corps(fiche),
                    "scan_premiere" if fiche["premiere_decouverte"] else "scan_valeur")


def _annoncer_bio(fiche):
    bio = fiche["bio"]
    cle = (_carnet.adresse, fiche["id"], "bio")
    if not bio or not fiche["connu"] or cle in _corps_annonces:
        return
    _corps_annonces.add(cle)
    if bio["max_bonus"]:
        _parle_morceaux(morceaux.pour_bio(bio), "scan_bio")
    else:
        _parle("scan_bio")


def _texte_bio(bio):
    if bio["max_bonus"]:
        ecart = _credits_courts(bio["max_bonus"]) if bio["min_bonus"] == bio["max_bonus"] else (
            f"{_credits_courts(bio['min_bonus'])} à {_credits_courts(bio['max_bonus'])}")
        return f"{bio['signaux']} forme(s) de vie, {ecart}" + (" (bonus du premier pas)" if bio["bonus"] else "")
    return f"{bio['signaux']} forme(s) de vie"


@_sur("Scan")
def _scan(e):
    nom = e.get("BodyName")
    if nom and "Belt Cluster" not in nom:
        _corps_scannes.add(nom)
        ETAT["position"]["corps_scannes"] = len(_corps_scannes)
        _touche("position")
    fiche, _neuf = _carnet.scan(e)
    if not fiche:
        _note(e, "exploration", f"Scan : {nom}", fusion=True)
        return
    _publier_exploration()
    details = [fiche["classe"]]
    if fiche["terraformable"]:
        details.append("terraformable")
    if fiche["balise"]:
        details.append("données de balise")
    else:
        details.append(f"≈ {_credits_courts(fiche['valeur'])}")
        if not fiche["etoile"] and fiche["valeur_carto"] != fiche["valeur"]:
            details.append(f"cartographié ≈ {_credits_courts(fiche['valeur_carto'])}")
        details.append("première découverte" if fiche["premiere_decouverte"] else "déjà découvert")
    if fiche["bio"]:
        details.append(_texte_bio(fiche["bio"]))
    _note(e, "exploration", f"Scan : {nom} — {', '.join(details)}", fusion=True)
    _annoncer_valeur(fiche)
    _annoncer_bio(fiche)


@_sur("FSSBodySignals")
def _signaux_corps(e):
    fiche = _carnet.signaux_fss(e)
    _publier_exploration()
    if fiche["bio"]:
        _note(e, "exploration", f"Biologie sur {e.get('BodyName', '?')} — {_texte_bio(fiche['bio'])}")
        _annoncer_bio(fiche)


@_sur("SAASignalsFound")
def _signaux_cartographie(e):
    fiche = _carnet.signaux_saa(e)
    _publier_exploration()
    if fiche["bio"] and e.get("Genuses"):
        genres = ", ".join(g.get("Genus_Localised") or "?" for g in e["Genuses"])
        _note(e, "exploration", f"Vie sur {e.get('BodyName', '?')} : {genres} — {_texte_bio(fiche['bio'])}", "succes")


@_sur("FSSAllBodiesFound")
def _systeme_complet(e):
    total = ETAT["exploration"]["total_carto"]
    suffixe = f" — jusqu'à ≈ {_credits_courts(total)} cartographié" if total else ""
    _note(e, "exploration", f"Système entièrement scanné ({e.get('Count', '?')} corps){suffixe}", "succes")


@_sur("SAAScanComplete")
def _cartographie(e):
    fiche = _carnet.cartographie(e)
    _publier_exploration()
    _note(e, "exploration", f"Cartographie terminée — {e.get('BodyName', '?')}"
                            f" ≈ {_credits_courts(fiche['valeur'])}", "succes")


@_sur("MultiSellExplorationData", "SellExplorationData")
def _vente_exploration(e):
    _carnet.vente_exploration(e)
    _publier_exploration()
    _note(e, "station", f"Données d'exploration vendues — {_credits(e.get('TotalEarnings'))}", "succes")


@_sur("SellOrganicData")
def _vente_exobio(e):
    _carnet.vente_exobio(e)
    _publier_exploration()
    total = sum((b.get("Value") or 0) + (b.get("Bonus") or 0) for b in e.get("BioData") or [])
    _note(e, "station", f"Données d'exobiologie vendues — {_credits(total)}", "succes")


@_sur("CodexEntry")
def _codex(e):
    _note(e, "exploration", f"Codex : {_loc(e, 'Name')}")


# ---------- Soute & commerce ----------
@_sur("Cargo")
def _soute_journal(e):
    if e.get("Vessel") == "Ship" and "Inventory" in e:
        _maj_soute(e)
        _touche("soute")


def _maj_soute(donnees):
    ETAT["soute"] = {
        "total": donnees.get("Count", 0),
        "inventaire": [{"nom": _loc(objet, "Name"), "quantite": objet.get("Count", 0),
                        "vole": bool(objet.get("Stolen"))}
                       for objet in donnees.get("Inventory") or []]}


@_sur("MarketBuy")
def _achat(e):
    _note(e, "soute", f"Achat : {e.get('Count')} × {_loc(e, 'Type')} — {_credits(e.get('TotalCost'))}")


@_sur("MarketSell")
def _vente(e):
    _note(e, "soute", f"Vente : {e.get('Count')} × {_loc(e, 'Type')} — {_credits(e.get('TotalSale'))}",
          "succes")


@_sur("CollectCargo")
def _collecte(e):
    _note(e, "soute", f"Collecté : {_loc(e, 'Type')}", fusion=True)


@_sur("EjectCargo")
def _largage(e):
    _note(e, "soute", f"Largué : {e.get('Count', 1)} × {_loc(e, 'Type')}", "attention")


@_sur("MiningRefined")
def _raffinage(e):
    _note(e, "soute", f"Raffiné : {_loc(e, 'Type')}", fusion=True)


@_sur("MaterialCollected")
def _materiau(e):
    _note(e, "soute", f"Matériau : {_loc(e, 'Name')} ×{e.get('Count', 1)}", fusion=True)


# ---------- Missions ----------
@_sur("Missions")
def _missions_en_cours(e):
    connues = {m["id"] for m in ETAT["missions"]["liste"]}
    ETAT["missions"]["anterieures"] = sum(
        1 for m in e.get("Active") or [] if m.get("MissionID") not in connues)
    _touche("missions")


@_sur("MissionAccepted")
def _mission_acceptee(e):
    ETAT["missions"]["liste"].append({
        "id": e.get("MissionID"), "nom": e.get("LocalisedName") or e.get("Name"),
        "faction": e.get("Faction"), "systeme": e.get("DestinationSystem"),
        "station": e.get("DestinationStation"), "echeance": e.get("Expiry"),
        "recompense": e.get("Reward")})
    _touche("missions")
    _note(e, "station", f"Mission acceptée : {e.get('LocalisedName') or e.get('Name')}")


def _retirer_mission(e):
    avant = len(ETAT["missions"]["liste"])
    ETAT["missions"]["liste"] = [m for m in ETAT["missions"]["liste"]
                                 if m["id"] != e.get("MissionID")]
    if len(ETAT["missions"]["liste"]) == avant and ETAT["missions"]["anterieures"] > 0:
        ETAT["missions"]["anterieures"] -= 1
    _touche("missions")


@_sur("MissionCompleted")
def _mission_accomplie(e):
    _retirer_mission(e)
    _note(e, "station", f"Mission accomplie — {_credits(e.get('Reward'))}", "succes")


@_sur("MissionFailed", "MissionAbandoned")
def _mission_perdue(e):
    _retirer_mission(e)
    _note(e, "station", "Mission échouée" if e["event"] == "MissionFailed"
          else "Mission abandonnée", "attention")


@_sur("MissionRedirected")
def _mission_redirigee(e):
    for mission in ETAT["missions"]["liste"]:
        if mission["id"] == e.get("MissionID"):
            mission.update(systeme=e.get("NewDestinationSystem"),
                           station=e.get("NewDestinationStation"))
    _touche("missions")


# ---------- Communications ----------
@_sur("ReceiveText")
def _message_recu(e):
    expediteur = _loc(e, "From") or "Inconnu"
    _note(e, "comms", f"{expediteur} : {_loc(e, 'Message')}")


@_sur("SendText")
def _message_envoye(e):
    _note(e, "comms", f"→ {e.get('To', '?')} : {e.get('Message', '')}")


# =====================================================================
#  SYSTÈMES À PORTÉE DE SAUT (EDSM)
# =====================================================================
_taches = set()
_derniere_recherche_proches = None


def _demander_systemes_proches():
    global _derniere_recherche_proches
    systeme, portee = ETAT["position"]["systeme"], ETAT["vaisseau"]["portee_saut"]
    if not SYSTEMES_PROCHES_ACTIF:
        ETAT["proches"]["etat"] = "desactive"
        return
    if not systeme or not portee or (systeme, round(portee)) == _derniere_recherche_proches:
        return
    _derniere_recherche_proches = (systeme, round(portee))
    tache = asyncio.create_task(_chercher_systemes_proches(systeme, portee))
    _taches.add(tache)                       # garde une référence tant que la tâche tourne
    tache.add_done_callback(_taches.discard)


async def _chercher_systemes_proches(systeme, portee):
    ETAT["proches"] = {"etat": "recherche", "systeme": systeme, "rayon": portee,
                       "total": 0, "liste": []}
    await _publier("proches")
    try:
        trouves = await asyncio.to_thread(edsm.systemes_dans_un_rayon, systeme, portee)
        resultat = {"etat": "ok", "total": len(trouves), "liste": trouves[:SYSTEMES_PROCHES_MAX]}
    except Exception as erreur:
        print(f"[EDSM] Systèmes proches indisponibles : {erreur!r}")
        resultat = {"etat": "erreur", "total": 0, "liste": []}
    if ETAT["position"]["systeme"] == systeme:      # on n'a pas ressauté entre-temps
        ETAT["proches"] = {"systeme": systeme, "rayon": portee, **resultat}
        await _publier("proches")


# =====================================================================
#  TÂCHE 1 — JOURNAL
# =====================================================================
def obtenir_dernier_journal():
    """Journal le plus récent (date de création), ou None si le jeu n'en a encore écrit aucun."""
    try:
        return max(glob.glob(CHEMIN_LOGS), key=os.path.getctime, default=None)
    except OSError:
        return None


def _lire_lignes_completes(fichier, reste):
    """Lit les nouvelles lignes. Une ligne sans saut de ligne final = le jeu n'a pas fini
    de l'écrire : elle est gardée dans `reste` et complétée au prochain passage."""
    lignes = []
    while True:
        morceau = fichier.readline()
        if not morceau:
            break
        if not morceau.endswith("\n"):
            reste += morceau
            break
        lignes.append(reste + morceau)
        reste = ""
    return lignes, reste


async def _traiter_ligne(ligne, en_direct):
    try:
        evenement = json.loads(ligne)
    except json.JSONDecodeError:
        return
    if en_direct:
        for fonction in list(_ecouteurs):
            try:
                fonction(evenement)
            except Exception as erreur:
                print(f"[Logs] Écouteur en erreur : {erreur!r}")
    gestionnaire = _GESTIONNAIRES.get(evenement.get("event"))
    if not gestionnaire:
        return

    _lot["sections"], _lot["lignes"], _lot["repliques"] = set(), [], []
    try:
        gestionnaire(evenement)
    except Exception as erreur:
        print(f"[Logs] Événement {evenement.get('event')} ignoré : {erreur!r}")
        return
    if not en_direct:
        return        # rattrapage : on reconstruit l'état en silence

    sections, lignes, repliques = _lot["sections"], _lot["lignes"], _lot["repliques"]
    await _publier(*sections)
    for entree in lignes:
        await envoyer_donnees_web({"type": "evenement", "evenement": entree})
    for cle in repliques:
        if isinstance(cle, dict):           # phrase chiffrée, en morceaux
            await _dire_morceaux(cle["morceaux"], cle["secours"])
            continue
        print(f"[Logs] {evenement.get('event')} -> réplique \"{cle}\"")
        await _dire(cle)
    if sections & {"position", "vaisseau"}:
        _demander_systemes_proches()


async def _relire_journaux_precedents(dernier, combien=2):
    """Au lancement, relit en silence les journaux juste avant le dernier : l'état reste
    complet même si le jeu vient de scinder son journal ou d'ouvrir une nouvelle session."""
    try:
        journaux = sorted(glob.glob(CHEMIN_LOGS), key=os.path.getctime)
    except OSError:
        return
    for chemin in [j for j in journaux if j != dernier][-combien:]:
        try:
            with open(chemin, "r", encoding="utf-8", errors="replace") as f:
                for numero, ligne in enumerate(f, 1):
                    await _traiter_ligne(ligne, en_direct=False)
                    if numero % 500 == 0:
                        await asyncio.sleep(0)
        except OSError:
            pass


async def surveiller_logs(tts_queue, generer_replique_func):
    _voix["file"], _voix["generer"] = tts_queue, generer_replique_func
    definir_instantane(_instantane)

    journal = None            # fichier actuellement suivi
    chemin_actuel = None
    reste = ""
    rattrapage = False        # True pendant la relecture du journal existant au lancement
    premiere_ouverture = True
    prochaine_recherche = 0.0
    attente_signalee = False

    while True:
        try:
            if journal:
                lignes, reste = _lire_lignes_completes(journal, reste)
                if lignes:
                    for numero, ligne in enumerate(lignes, 1):
                        await _traiter_ligne(ligne, en_direct=not rattrapage)
                        if numero % 500 == 0:
                            await asyncio.sleep(0)     # laisse respirer les autres tâches
                    continue
                if rattrapage:
                    rattrapage = False
                    print(f"[Logs] État du vaisseau reconstruit, suivi en direct "
                          f"({len(HISTORIQUE)} événements en mémoire).")
                    await envoyer_donnees_web(_instantane())
                    _demander_systemes_proches()

            # Rien de neuf : le jeu a-t-il ouvert un journal plus récent ?
            # (jeu lancé après le COVAS, nouvelle session, ou journal scindé en plusieurs parties)
            if time.monotonic() >= prochaine_recherche:
                prochaine_recherche = time.monotonic() + 2
                plus_recent = obtenir_dernier_journal()
                if plus_recent and plus_recent != chemin_actuel:
                    if journal:
                        journal.close()
                    if premiere_ouverture:
                        await _relire_journaux_precedents(plus_recent)
                    journal = open(plus_recent, "r", encoding="utf-8", errors="replace")
                    chemin_actuel, reste = plus_recent, ""
                    rattrapage, premiere_ouverture = premiere_ouverture, False
                    ETAT["session"]["journal"] = os.path.basename(plus_recent)
                    print(f"[Logs] Surveillance activée sur : {os.path.basename(plus_recent)}")
                    continue
                if not plus_recent and not attente_signalee:
                    attente_signalee = True
                    premiere_ouverture = False     # le prochain journal sera lu en direct
                    print("[Logs] Aucun journal Elite Dangerous trouvé : en attente du jeu...")

            await asyncio.sleep(0.5)   # Polling léger, zéro impact CPU
        except Exception as erreur:
            print(f"[Logs] Erreur de lecture du journal : {erreur!r}")
            await asyncio.sleep(2)


# =====================================================================
#  FICHIERS JSON RÉÉCRITS EN ENTIER PAR LE JEU
# =====================================================================
class _FichierSurveille:
    """Relit un fichier JSON du jeu quand sa date de modification change."""

    def __init__(self, chemin):
        self.chemin = chemin
        self.derniere_modif = None

    def lire_si_modifie(self):
        try:
            modif = os.path.getmtime(self.chemin)
        except OSError:
            return None                 # fichier absent
        if modif == self.derniere_modif:
            return None
        try:
            with open(self.chemin, "r", encoding="utf-8") as f:
                donnees = json.load(f)
        except (OSError, json.JSONDecodeError):
            return None                 # le jeu est en train d'écrire : on réessaie au prochain tour
        self.derniere_modif = modif
        return donnees if isinstance(donnees, dict) else None


# =====================================================================
#  TÂCHE 2 — FICHIERS AUXILIAIRES
# =====================================================================
def _maj_route(donnees):
    etapes, precedent, total = [], None, 0.0
    for saut in donnees.get("Route") or []:
        position = saut.get("StarPos")
        distance = _distance(precedent, position)
        total += distance
        etapes.append({"systeme": saut.get("StarSystem"), "classe": saut.get("StarClass"),
                       "distance": round(distance, 2),
                       "ravitaillable": _ravitaillable(saut.get("StarClass"))})
        precedent = position
    ETAT["route"].update(etapes=etapes, distance_totale=round(total, 2))
    if not etapes:
        ETAT["route"]["prochain"] = None
    _maj_progression_route()


def _maj_puissances(donnees):
    _puissances.clear()
    for module in donnees.get("Modules") or []:
        _puissances[module.get("Slot")] = module.get("Power")
    for module in ETAT["modules"]["liste"]:
        module["puissance"] = _puissances.get(module["emplacement"])


async def surveiller_fichiers_auxiliaires():
    """Surveille NavRoute.json, ModulesInfo.json et Cargo.json."""
    fichiers = [
        (_FichierSurveille(CHEMIN_NAVROUTE), _maj_route, "route"),
        (_FichierSurveille(CHEMIN_MODULES), _maj_puissances, "modules"),
        (_FichierSurveille(CHEMIN_SOUTE), _maj_soute, "soute"),
    ]
    print("[Logs] Surveillance de NavRoute, ModulesInfo et Cargo activée.")

    while True:
        for fichier, mettre_a_jour, section in fichiers:
            try:
                donnees = fichier.lire_si_modifie()
                if donnees is None:
                    continue
                if section == "soute" and donnees.get("Vessel", "Ship") != "Ship":
                    continue
                mettre_a_jour(donnees)
                await _publier(section)
            except Exception as erreur:
                print(f"[Logs] Erreur sur {os.path.basename(fichier.chemin)} : {erreur!r}")
        await asyncio.sleep(1.0)   # Check toutes les secondes, très léger


# =====================================================================
#  TÂCHE 3 — STATUS.JSON
# =====================================================================
async def surveiller_status_json():
    fichier = _FichierSurveille(CHEMIN_STATUS)
    drapeaux_precedents = None
    print("[Logs] Surveillance de Status.json activée (avec WebSockets).")

    while True:
        try:
            status = fichier.lire_si_modifie()
            if status is not None:
                drapeaux = status.get("Flags", 0)
                pips = status.get("Pips") or [0, 0, 0]       # absents à pied
                carburant = status.get("Fuel") or {}
                destination = status.get("Destination") or {}
                ETAT["status"] = {
                    "horodatage": status.get("timestamp"),
                    "flags": drapeaux,
                    "flags2": status.get("Flags2", 0),
                    "pips": pips,                             # en demi-pips : [SYS, ENG, WEP]
                    "groupe_tir": status.get("FireGroup"),
                    "focus": status.get("GuiFocus"),
                    "carburant": carburant.get("FuelMain"),
                    "reserve": carburant.get("FuelReservoir"),
                    "soute": status.get("Cargo"),
                    "statut_legal": status.get("LegalState"),
                    "credits": status.get("Balance"),
                    "destination": destination.get("Name_Localised") or destination.get("Name"),
                    "latitude": status.get("Latitude"),
                    "longitude": status.get("Longitude"),
                    "altitude": status.get("Altitude"),
                    "cap": status.get("Heading"),
                    "corps": status.get("BodyName"),
                    "rayon": status.get("PlanetRadius"),
                    # À pied seulement : niveaux de 0 à 1, kelvins, g
                    "oxygene": status.get("Oxygen"),
                    "sante": status.get("Health"),
                    "temperature": status.get("Temperature"),
                    "gravite": status.get("Gravity"),
                    "arme": status.get("SelectedWeapon_Localised") or status.get("SelectedWeapon"),
                }
                await _publier("status")
                exo = ETAT["sol"].get("exobio")
                etait_libre = exo["libre"] if exo else None
                if sol.actualiser(ETAT["sol"], ETAT["status"]):
                    await _publier("sol")
                    if exo and etait_libre is False and exo["libre"]:   # assez loin : prélèvement possible
                        await _dire("exo_distance_ok")

                # Alertes vocales : seulement quand le drapeau vient de s'allumer sous nos yeux
                if drapeaux_precedents is not None:
                    apparus = drapeaux & ~drapeaux_precedents
                    if apparus & DRAPEAU_CARBURANT_BAS:
                        await _dire("alerte_carburant")
                    if apparus & DRAPEAU_SURCHAUFFE:
                        await _dire("alerte_surchauffe")
                drapeaux_precedents = drapeaux
        except Exception as erreur:
            print(f"[Logs] Erreur sur Status.json : {erreur!r}")
        await asyncio.sleep(0.5)