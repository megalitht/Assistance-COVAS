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

from module import edsm
from module.serveur_ws import definir_instantane, envoyer_donnees_web

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

# Drapeaux de Status.json utilisés ici (la liste complète est décodée par l'interface)
DRAPEAU_CARBURANT_BAS = 1 << 19
DRAPEAU_SURCHAUFFE = 1 << 20

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


def _combat_vierge():
    return {"eliminations": 0, "primes": 0, "bons": 0, "coups_coque": 0, "boucliers_tombes": 0,
            "interdictions": 0, "morts": 0, "assaillant": None}


def _reinitialiser_etat():
    ETAT.clear()
    ETAT.update({
        "session": {"jeu_actif": False, "journal": None, "version": None},
        "commandant": {"nom": None, "credits": None, "mode_jeu": None,
                       "rangs": {}, "progression": {}},
        "vaisseau": {"type": None, "modele": None, "nom": None, "immat": None, "coque": None,
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
    })


_reinitialiser_etat()
_corps_scannes = set()
_puissances = {}          # emplacement -> MW (ModulesInfo.json)

# Ce que le gestionnaire d'événement en cours veut publier
_lot = {"sections": set(), "lignes": [], "repliques": []}


def _instantane():
    return {"type": "etat", "etat": ETAT, "historique": list(HISTORIQUE)}


async def _publier(*sections):
    for section in sections:
        await envoyer_donnees_web({"type": "maj", "section": section, "donnees": ETAT[section]})


def _touche(*sections):
    """Signale que ces sections de ETAT ont changé."""
    _lot["sections"].update(sections)


def _note(e, categorie, texte, gravite="info", hostile=False, fusion=False):
    """Ajoute une ligne au journal de bord de l'interface.

    gravite : info | succes | attention | alerte
    hostile : True = l'interface bascule en vue combat
    fusion  : True = remplace la ligne précédente si c'est le même événement (compteur ×n)
    """
    ligne = {"id": next(_identifiants), "h": e.get("timestamp"), "nom": e.get("event"),
             "categorie": categorie, "gravite": gravite, "texte": texte,
             "hostile": hostile, "n": 1}
    if fusion and HISTORIQUE and HISTORIQUE[-1]["nom"] == ligne["nom"]:
        precedente = HISTORIQUE.pop()
        ligne["id"], ligne["n"] = precedente["id"], precedente["n"] + 1
    HISTORIQUE.append(ligne)
    _lot["lignes"].append(ligne)


def _parle(cle):
    """Demande une réplique vocale (clé de barks.json)."""
    _lot["repliques"].append(cle)


# --- Petits outils de mise en forme ---
def _nombre(n):
    return f"{int(n or 0):,}".replace(",", " ")


def _pourcent(x):
    return f"{(x or 0) * 100:.0f}\u00a0%"


def _credits(n):
    return f"{_nombre(n)} cr"


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
    if maintenant - _derniere_replique.get(cle, -1e9) < DELAI_ENTRE_REPLIQUES:
        return
    _derniere_replique[cle] = maintenant

    chemin_audio = await _voix["generer"](cle)
    if not chemin_audio:
        if cle not in _cles_sans_son:
            _cles_sans_son.add(cle)
            print(f'[Voix] Aucune réplique audio pour "{cle}" dans barks.json.')
        return
    if maintenant - _dernier_son.get(chemin_audio, -1e9) < DELAI_MEME_SON:
        return
    _dernier_son[chemin_audio] = maintenant
    await _voix["file"].put(chemin_audio)


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
        _touche("combat", "missions")
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
    ETAT["vaisseau"].update(type=e.get("Ship"), modele=e.get("Ship_Localised"),
                            nom=e.get("ShipName"), immat=e.get("ShipIdent"))
    _touche("session", "commandant", "vaisseau")
    _note(e, "systeme", f"Session ouverte — CMDR {e.get('Commander', '?')}", "succes")
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
        coque=e.get("HullHealth"), portee_saut=e.get("MaxJumpRange"),
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
    _touche("vaisseau", "modules")


def _modules_par_objet(nom_objet):
    cle = (nom_objet or "").lower().strip("$;").replace("_name", "")
    return [m for m in ETAT["modules"]["liste"] if m["objet"] == cle]


@_sur("HullDamage")
def _degats_coque(e):
    sante = e.get("Health", 1.0)
    if e.get("Fighter"):
        _note(e, "combat", f"Chasseur touché — coque {_pourcent(sante)}", "attention", hostile=True)
        return
    ETAT["vaisseau"]["coque"] = sante
    ETAT["combat"]["coups_coque"] += 1
    _touche("vaisseau", "combat")
    critique = sante <= 0.30
    _note(e, "combat", f"Coque touchée — intégrité {_pourcent(sante)}",
          "alerte" if critique else "attention", hostile=True)
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
        _note(e, "combat", "Boucliers hors ligne", "alerte", hostile=True)
        _parle("alerte_bouclier")


@_sur("UnderAttack")
def _sous_le_feu(e):
    cible = {"Fighter": "chasseur", "Mothership": "vaisseau mère"}.get(e.get("Target"))
    _note(e, "combat", f"Sous le feu ({cible})" if cible else "Sous le feu ennemi",
          "alerte", hostile=True, fusion=True)
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
    ETAT["vaisseau"]["verriere_brisee"] = True
    _touche("vaisseau")
    _note(e, "combat", "Verrière brisée — oxygène de secours", "alerte", hostile=True)
    _parle("verriere_brisee")


@_sur("Died")
def _mort(e):
    tueurs = [t.get("Name") for t in e.get("Killers") or []] or [e.get("KillerName_Localised")
                                                                 or e.get("KillerName")]
    tueurs = [t for t in tueurs if t]
    ETAT["combat"]["morts"] += 1
    ETAT["vaisseau"]["coque"] = 0
    _touche("combat", "vaisseau")
    _note(e, "combat", "Vaisseau détruit" + (f" par {', '.join(tueurs)}" if tueurs else ""),
          "alerte")


@_sur("Resurrect")
def _resurrection(e):
    ETAT["vaisseau"].update(coque=1.0, verriere_brisee=False)
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
    _note(e, "vaisseau", f"Redémarrage/réparation : {len(e.get('Modules') or [])} module(s)",
          "attention")


@_sur("RepairAll")
def _reparation_totale(e):
    ETAT["vaisseau"].update(coque=1.0, verriere_brisee=False)
    for module in ETAT["modules"]["liste"]:
        module["sante"] = 1.0
    _touche("vaisseau", "modules")
    _note(e, "station", f"Réparation complète — {_credits(e.get('Cost'))}", "succes")


@_sur("Repair")
def _reparation(e):
    objets = e.get("Items") or [e.get("Item")]
    for objet in objets:
        if (objet or "").lower() in ("hull", "all"):
            ETAT["vaisseau"]["coque"] = 1.0
        if (objet or "").lower() == "all":
            for module in ETAT["modules"]["liste"]:
                module["sante"] = 1.0
        for module in _modules_par_objet(objet):
            module["sante"] = 1.0
    _touche("vaisseau", "modules")
    _note(e, "station", f"Réparation — {_credits(e.get('Cost'))}")


@_sur("LaunchFighter")
def _chasseur_lance(e):
    ETAT["vaisseau"]["chasseur"] = "deploye"
    _touche("vaisseau")
    _note(e, "combat", "Chasseur déployé")


@_sur("DockFighter")
def _chasseur_rentre(e):
    ETAT["vaisseau"]["chasseur"] = "a_bord"
    _touche("vaisseau")
    _note(e, "combat", "Chasseur récupéré")


@_sur("FighterDestroyed")
def _chasseur_detruit(e):
    ETAT["vaisseau"]["chasseur"] = "detruit"
    _touche("vaisseau")
    _note(e, "combat", "Chasseur détruit", "alerte", hostile=True)


@_sur("FighterRebuilt")
def _chasseur_reconstruit(e):
    ETAT["vaisseau"]["chasseur"] = "a_bord"
    _touche("vaisseau")
    _note(e, "combat", "Chasseur reconstruit", "succes")


@_sur("LaunchSRV")
def _vrs_sorti(e):
    _note(e, "vaisseau", "VRS déployé")


@_sur("DockSRV")
def _vrs_rentre(e):
    _note(e, "vaisseau", "VRS récupéré")


@_sur("SRVDestroyed")
def _vrs_detruit(e):
    _note(e, "vaisseau", "VRS détruit", "alerte")


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


@_sur("Bounty")
def _prime(e):
    recompense = e.get("TotalReward", e.get("Reward", 0))
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
        }
        if e.get("ScanStage") == 3 and e.get("LegalStatus") == "Wanted":
            _note(e, "combat", f"Cible recherchée : {_loc(e, 'PilotName') or _loc(e, 'Ship')}"
                               f" — prime {_credits(e.get('Bounty'))}", "attention", fusion=True)
    _touche("cible")


@_sur("CommitCrime")
def _infraction(e):
    montant = e.get("Fine") or e.get("Bounty") or 0
    _note(e, "combat", f"Infraction ({e.get('CrimeType', '?')}) — {_credits(montant)}",
          "attention")


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
    if e.get("PlayerControlled", True):
        _note(e, "navigation", f"Posé sur {e.get('Body', 'la surface')}", "succes")


@_sur("Liftoff")
def _decollage(e):
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


@_sur("DockingDenied")
def _appontage_refuse(e):
    _note(e, "station", f"Appontage refusé ({e.get('Reason', '?')})", "attention")


@_sur("DockingCancelled", "DockingTimeout")
def _appontage_annule(e):
    _note(e, "station", "Autorisation d'appontage annulée", "attention")


@_sur("Docked")
def _amarre(e):
    plateforme = (ETAT["position"]["station"] or {}).get("plateforme")
    ETAT["position"].update(amarre=True, station=_fiche_station(e, plateforme))
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


@_sur("Scan")
def _scan(e):
    nom = e.get("BodyName")
    if nom and "Belt Cluster" not in nom:
        _corps_scannes.add(nom)
        ETAT["position"]["corps_scannes"] = len(_corps_scannes)
        _touche("position")
    nature = e.get("PlanetClass") or (f"étoile {e['StarType']}" if e.get("StarType") else "")
    details = [nature] if nature else []
    if e.get("TerraformState"):
        details.append("terraformable")
    if e.get("WasDiscovered") is False:
        details.append("première découverte")
    _note(e, "exploration", f"Scan : {nom}" + (f" — {', '.join(details)}" if details else ""),
          fusion=True)


@_sur("FSSAllBodiesFound")
def _systeme_complet(e):
    _note(e, "exploration", f"Système entièrement scanné ({e.get('Count', '?')} corps)", "succes")


@_sur("SAAScanComplete")
def _cartographie(e):
    _note(e, "exploration", f"Cartographie terminée — {e.get('BodyName', '?')}", "succes")


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
                }
                await _publier("status")

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