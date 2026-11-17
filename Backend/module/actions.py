"""
actions.py — Commandes « intelligentes ».

Avant d'appuyer sur une touche, le COVAS regarde l'état du vaisseau (Status.json) :
  - il refuse ce qui n'a pas de sens (« sors le train » alors qu'il est déjà sorti) ;
  - il refuse ce que le jeu interdit (train en supercroisière, FSD à quai...) ;
  - après l'appui, il vérifie que le jeu a bien réagi, sinon il le signale.
Chaque refus est dit à voix haute (barks.json) et affiché dans l'interface.

Deux sortes de commandes :
  - les commandes courtes (une ou quelques touches) s'exécutent tout de suite ;
  - les PROGRAMMES (décollage, apontage, fuite, autopilote, ravitaillement) durent
    longtemps : ils tournent en tâche de fond, un seul à la fois, et « stop » les annule.

Point d'entrée : executer_commande(action, texte, dire, poli)
  action : clé de barks.json détectée dans la phrase (ex. "train_atterrissage")
  texte  : la phrase entendue (pour savoir si on veut sortir ou rentrer)
  dire   : fonction async dire(*cles, poli=False) qui joue la première réplique trouvée
"""
import asyncio
import time
import traceback

from module import lecteur_logs as logs
from module import macros
from module import touches
from module.macros import normaliser

# Bits de Status.json utilisés ici
BIT = {"amarre": 0, "pose": 1, "train": 2, "boucliers": 3, "supercroisiere": 4, "armes": 6,
       "feux": 8, "ecope": 9, "silencieux": 10, "masse": 16, "fsd_charge": 17,
       "fsd_refroid": 18, "surchauffe": 20, "danger": 22, "interdiction": 23, "vaisseau": 24,
       "chasseur": 25, "vrs": 26, "analyse": 27, "nvg": 28, "saut": 30}

# Débuts de mots qui indiquent ce que veut le commandant
MOTS_RENTRER = ("rentr", "rang", "remont", "ferm", "etein", "desactiv", "coup", "repli", "retract")
MOTS_SORTIR = ("sor", "deploi", "deploy", "descend", "baiss", "ouvr", "allum", "activ")

_SC = ("supercroisiere", None, "refus_supercroisiere", "en supercroisière")
_AMARRE = ("amarre", None, "refus_amarre", "quand le vaisseau est amarré")

# Ce qui se bascule avec une seule touche, et dont le jeu donne l'état
BASCULES = {
    "train_atterrissage": {
        "touche": "train", "bit": "train", "nom": "Train d'atterrissage",
        "etats": ("sorti", "rentré"), "deja": ("train_deja_sorti", "train_deja_rentre"),
        # (drapeau qui interdit, intention concernée ou None = toujours, réplique, raison)
        "interdit": [_SC, _AMARRE,
                     ("pose", "rentrer", "refus_pose", "quand le vaisseau est posé")],
    },
    "soute": {
        "touche": "soute", "bit": "ecope", "nom": "Écope de soute",
        "etats": ("ouverte", "fermée"), "deja": ("soute_deja_ouverte", "soute_deja_fermee"),
        "interdit": [("supercroisiere", "sortir", "refus_supercroisiere", "en supercroisière"),
                     _AMARRE],
    },
    "nvg": {
        "touche": "nvg", "bit": "nvg", "nom": "Vision nocturne", "vrs": True,
        "etats": ("activée", "coupée"), "deja": ("nvg_deja_active", "nvg_deja_coupee"),
        "interdit": [],
    },
    "phares": {
        "touche": "phares", "bit": "feux", "nom": "Phares", "vrs": True,
        "etats": ("allumés", "éteints"), "deja": ("phares_deja_allumes", "phares_deja_eteints"),
        "interdit": [],
    },
    "armement": {
        "touche": "armement", "bit": "armes", "nom": "Points d'emport",
        "etats": ("déployés", "rentrés"), "deja": ("armement_deja_sorti", "armement_deja_rentre"),
        "interdit": [("supercroisiere", "sortir", "refus_supercroisiere", "en supercroisière"),
                     ("amarre", "sortir", "refus_amarre", "quand le vaisseau est amarré")],
    },
    "silencieux": {
        "touche": "silencieux", "bit": "silencieux", "nom": "Mode silencieux",
        "etats": ("activé", "coupé"), "deja": ("silencieux_deja_actif", "silencieux_deja_coupe"),
        "interdit": [_AMARRE],
    },
    "hud": {
        "touche": "hud", "bit": "analyse", "nom": "Cockpit",
        "etats": ("en mode analyse", "en mode combat"),
        "deja": ("hud_deja_analyse", "hud_deja_combat"),
        # ici ce sont les mots « analyse » / « combat » qui donnent le sens voulu
        "mots": (("analys", "scan", "explor"), ("combat",)),
        "interdit": [],
    },
}

# Une touche, quelques conditions, pas d'état à vérifier
SIMPLES = {
    "vitesse_zero": {"touche": "vitesse_zero", "nom": "Vitesse zéro", "interdit": [_AMARRE]},
    "plein_gaz": {"touche": "vitesse_max", "nom": "Plein gaz", "interdit": [_AMARRE]},
    "cible_menace": {"touche": "cible_menace", "nom": "Plus grande menace", "interdit": [_SC, _AMARRE]},
    "cible_hostile": {"touche": "cible_hostile", "nom": "Hostile suivant", "interdit": [_SC, _AMARRE]},
    "puce_thermique": {"touche": "puce_thermique", "nom": "Puce thermique",
                       "module": "heatsinklauncher", "interdit": [_AMARRE]},
    "leurres": {"touche": "leurres", "nom": "Leurres",
                "module": "chafflauncher", "interdit": [_SC, _AMARRE]},
}

# Cartes : touche et numéro du panneau (GuiFocus de Status.json)
CARTES = {"carte_galaxie": ("carte_galaxie", 6, "Carte de la galaxie"),
          "carte_systeme": ("carte_systeme", 7, "Carte du système")}

# Ordres au chasseur : (débuts de mots dans la phrase, touche, texte affiché)
ORDRES_CHASSEUR = [
    (("rappel", "revien", "rentr", "retour"), "chasseur_rappel", "rappel au vaisseau"),
    (("cess", "halte", "arret"), "chasseur_cessez", "cessez-le-feu"),
    (("volonte", "libre", "agress"), "chasseur_feu_libre", "tir à volonté"),
    (("attaqu", "engag", "cible"), "chasseur_attaque", "attaque de ma cible"),
    (("defen", "proteg", "couvr"), "chasseur_defense", "défense"),
    (("position", "tien", "rest", "attend"), "chasseur_position", "tenir la position"),
    (("sui", "formation", "escort"), "chasseur_suivre", "en formation"),
]

# Sous-systèmes : (mots dans la phrase, morceaux du nom donné par le jeu)
SOUS_SYSTEMES = [
    (("fsd", "saut", "hyper"), ("fsd", "hyperdrive", "frame", "saut")),
    (("reacteur", "generateur", "centrale"), ("powerplant", "power plant", "generateur", "centrale")),
    (("moteur", "propuls"), ("engine", "propuls", "thruster", "drive")),
    (("bouclier",), ("shieldgen", "bouclier", "shield")),
    (("distribut",), ("powerdistributor", "distribut")),
    (("survie",), ("lifesupport", "survie", "life support")),
    (("capteur", "senseur", "radar"), ("sensor", "capteur", "radar")),
    (("soute", "cargo"), ("cargohatch", "cargo", "soute")),
]

ACHATS = ("RefuelAll", "RefuelPartial", "RepairAll", "Repair", "BuyAmmo")


# =====================================================================
#  OUTILS
# =====================================================================
def _flags():
    return logs.ETAT["status"].get("flags") or 0


def etat_connu():
    """False si le jeu n'a pas encore écrit Status.json (ou est au menu principal)."""
    return bool(_flags())


def drapeau(nom):
    return bool(_flags() & (1 << BIT[nom]))


def intention(texte):
    """'sortir', 'rentrer' ou None (= basculer) d'après les verbes de la phrase."""
    for mot in normaliser(texte).replace("'", " ").split():
        if mot.startswith(MOTS_RENTRER):
            return "rentrer"
        if mot.startswith(MOTS_SORTIR):
            return "sortir"
    return None


def _mots(texte):
    return normaliser(texte).replace("'", " ").replace("-", " ").split()


def _contient(texte, debuts):
    return any(mot.startswith(debuts) for mot in _mots(texte))


async def attendre(condition, delai):
    """Attend jusqu'à `delai` secondes que condition() devienne vraie."""
    fin = time.monotonic() + delai
    while time.monotonic() < fin:
        if condition():
            return True
        await asyncio.sleep(0.15)
    return condition()


async def appuyer(nom, fois=1, duree=None):
    return await asyncio.to_thread(macros.appuyer, nom, fois, duree)


async def refuser(dire, cle, texte):
    await logs.annoncer(texte, "attention")
    await dire(cle, "refus")


async def confirmer(dire, action, poli=False):
    """Réplique de la commande ; à défaut, un simple « Bien, commandant »."""
    await dire(action, "affirmation", poli=poli)


async def preparer_jeu(dire):
    """Le jeu doit être au premier plan, sinon les touches partent ailleurs."""
    if await asyncio.to_thread(macros.focaliser_jeu):
        return True
    await refuser(dire, "refus_jeu_absent",
                  "Fenêtre d'Elite Dangerous introuvable : commande annulée")
    return False


async def touche_prete(dire, nom_touche, nom_commande):
    """Refuse proprement une commande dont la touche n'existe pas dans le jeu."""
    if macros.touche_connue(nom_touche):
        return True
    await refuser(dire, "refus_touche_absente",
                  f"{nom_commande} : aucune touche clavier dans le jeu. Donne-en une à "
                  f"« {touches.libelle(nom_touche)} » (Options > Commandes), puis relance le COVAS")
    return False


def _module_present(morceau):
    """True/False si la liste des modules est connue, None sinon."""
    liste = logs.ETAT["modules"]["liste"]
    if not liste:
        return None
    return any(morceau in (m.get("objet") or "").lower() for m in liste)


async def _interdits(dire, nom, interdit, direction=None):
    """Vérifie les drapeaux qui interdisent la commande. True = on a refusé."""
    for nom_drapeau, seulement, cle, raison in interdit:
        if drapeau(nom_drapeau) and seulement in (None, direction):
            await refuser(dire, cle, f"{nom} : impossible {raison}")
            return True
    return False


# =====================================================================
#  PROGRAMMES (longues séquences en tâche de fond) ET « STOP »
# =====================================================================
_programme = {"tache": None, "nom": None}


def programme_en_cours():
    tache = _programme["tache"]
    return tache is not None and not tache.done()


async def _lancer_programme(nom, coroutine, dire):
    if programme_en_cours():
        coroutine.close()
        return await refuser(dire, "refus_programme_en_cours",
                             f"{nom} : « {_programme['nom']} » est déjà en cours "
                             "(dis « stop » pour l'annuler)")

    async def enveloppe():
        try:
            await coroutine
        except asyncio.CancelledError:
            await asyncio.to_thread(macros.relacher_tout)
            await logs.annoncer(f"{nom} : interrompu", "attention")
            raise
        except Exception:
            traceback.print_exc()
            await asyncio.to_thread(macros.relacher_tout)
            await logs.annoncer(f"{nom} : erreur interne, programme arrêté", "alerte")
            await dire("macro_echec", "refus")

    _programme["nom"] = nom
    _programme["tache"] = asyncio.create_task(enveloppe(), name=nom)


async def _stop(dire):
    if not programme_en_cours():
        await logs.annoncer("Stop : aucun programme en cours")
        return await dire("stop_rien", "affirmation")
    tache = _programme["tache"]
    macros.STOP.set()               # coupe aussi les appuis déjà partis
    tache.cancel()
    await asyncio.wait([tache], timeout=3)
    macros.STOP.clear()
    await asyncio.to_thread(macros.relacher_tout)
    await dire("stop", "affirmation")


# =====================================================================
#  POINT D'ENTRÉE
# =====================================================================
async def executer_commande(action, texte, dire, poli=False):
    cle = normaliser(action)

    if cle == "stop":
        return await _stop(dire)
    if cle in BASCULES:
        return await _bascule(action, BASCULES[cle], texte, dire, poli)
    if cle in SIMPLES:
        return await _simple(action, SIMPLES[cle], dire, poli)
    if cle in CARTES:
        return await _carte(action, *CARTES[cle], dire, poli)
    if cle in PROGRAMMES:
        nom, fabrique = PROGRAMMES[cle]
        return await _lancer_programme(nom, fabrique(dire, poli), dire)
    if cle in SPECIALES:
        return await SPECIALES[cle](action, texte, dire, poli)

    if cle == "fsd" and etat_connu():
        if not drapeau("vaisseau"):
            return await refuser(dire, "refus_hors_vaisseau", "FSD : impossible hors du vaisseau")
        if drapeau("amarre"):
            return await refuser(dire, "refus_amarre", "FSD : impossible quand le vaisseau est amarré")
        if drapeau("pose"):
            return await refuser(dire, "refus_pose", "FSD : décolle d'abord")
        if drapeau("masse"):
            return await refuser(dire, "refus_masse",
                                 "FSD bloqué : masse verrouillée, éloigne-toi de l'objet massif")

    # Commande simple (pips, verrouillage, boost...)
    if cle not in macros.MACROS:
        await dire(action, poli=poli)
        return
    if not await preparer_jeu(dire):
        return
    await confirmer(dire, action, poli)
    await asyncio.to_thread(macros.executer_touches, cle)


# =====================================================================
#  TRAIN, SOUTE, NVG, PHARES, ARMEMENT, MODE SILENCIEUX, COCKPIT
# =====================================================================
async def _bascule(action, cfg, texte, dire, poli):
    if "mots" in cfg:
        voulu = ("sortir" if _contient(texte, cfg["mots"][0])
                 else "rentrer" if _contient(texte, cfg["mots"][1]) else None)
    else:
        voulu = intention(texte)

    if not await touche_prete(dire, cfg["touche"], cfg["nom"]):
        return

    if etat_connu():
        if not (drapeau("vaisseau") or (cfg.get("vrs") and drapeau("vrs"))):
            return await refuser(dire, "refus_hors_vaisseau",
                                 f"{cfg['nom']} : impossible hors du vaisseau")
        actuel = drapeau(cfg["bit"])
        if voulu and actuel == (voulu == "sortir"):
            etat = cfg["etats"][0 if actuel else 1]
            return await refuser(dire, cfg["deja"][0 if actuel else 1], f"{cfg['nom']} déjà {etat}")
        direction = voulu or ("rentrer" if actuel else "sortir")
        if await _interdits(dire, cfg["nom"], cfg["interdit"], direction):
            return
    else:
        actuel = None      # état inconnu : on bascule à l'aveugle, comme avant

    if not await preparer_jeu(dire):
        return
    await confirmer(dire, action, poli)
    await appuyer(cfg["touche"])

    if actuel is None:
        return
    if await attendre(lambda: drapeau(cfg["bit"]) != actuel, 3):
        await logs.annoncer(f"{cfg['nom']} {cfg['etats'][0 if not actuel else 1]}")
    else:
        await logs.annoncer(f"{cfg['nom']} : le jeu n'a pas réagi (touche « "
                            f"{macros.nom_touche(cfg['touche'])} » ?)", "alerte")
        await dire("macro_echec", "refus")


# =====================================================================
#  COMMANDES À UNE TOUCHE : vitesse, ciblage, puce thermique, leurres
# =====================================================================
async def _simple(action, cfg, dire, poli):
    if not await touche_prete(dire, cfg["touche"], cfg["nom"]):
        return
    if etat_connu():
        if not drapeau("vaisseau"):
            return await refuser(dire, "refus_hors_vaisseau",
                                 f"{cfg['nom']} : impossible hors du vaisseau")
        if await _interdits(dire, cfg["nom"], cfg["interdit"]):
            return
    if cfg.get("module") and _module_present(cfg["module"]) is False:
        return await refuser(dire, "refus_pas_de_module",
                             f"{cfg['nom']} : ce module n'est pas installé sur le vaisseau")
    if not await preparer_jeu(dire):
        return
    await confirmer(dire, action, poli)
    await appuyer(cfg["touche"])
    await logs.annoncer(cfg["nom"])


async def _carte(action, touche, focus, nom, dire, poli):
    if not await touche_prete(dire, touche, nom):
        return
    if not await preparer_jeu(dire):
        return
    deja_ouverte = _focus() == focus
    await confirmer(dire, action, poli)
    if not deja_ouverte and not await fermer_panneaux():
        return await refuser(dire, "macro_echec", f"{nom} : un menu reste ouvert")
    await appuyer(touche)
    if not etat_connu():
        return
    if await attendre(lambda: (_focus() == focus) != deja_ouverte, 6):
        await logs.annoncer(f"{nom} {'fermée' if deja_ouverte else 'ouverte'}")
    else:
        await logs.annoncer(f"{nom} : le jeu n'a pas réagi (touche « "
                            f"{macros.nom_touche(touche)} » ?)", "alerte")
        await dire("macro_echec", "refus")


# =====================================================================
#  CIBLAGE D'UN SOUS-SYSTÈME
# =====================================================================
async def _sous_systeme(action, texte, dire, poli):
    if not await touche_prete(dire, "sous_systeme_suivant", "Sous-système"):
        return
    if etat_connu() and not logs.ETAT["cible"].get("verrouillee"):
        return await refuser(dire, "refus_pas_de_cible", "Sous-système : aucune cible verrouillée")
    if not await preparer_jeu(dire):
        return

    cherche = next((noms for mots, noms in SOUS_SYSTEMES if _contient(texte, mots)), None)
    await confirmer(dire, action, poli)
    if not cherche:                       # pas de module nommé : simplement le suivant
        touche = ("sous_systeme_precedent" if _contient(texte, ("preced",))
                  and macros.touche_connue("sous_systeme_precedent") else "sous_systeme_suivant")
        return await appuyer(touche)

    def vise():
        nom = normaliser(logs.ETAT["cible"].get("sous_systeme") or "")
        return any(morceau in nom for morceau in cherche)

    vus = set()
    for _ in range(14):
        if vise():
            return await logs.annoncer(f"Sous-système visé : {logs.ETAT['cible'].get('sous_systeme')}")
        await appuyer("sous_systeme_suivant")
        await asyncio.sleep(0.45)
        vus.add(logs.ETAT["cible"].get("sous_systeme"))
    if vise():
        return await logs.annoncer(f"Sous-système visé : {logs.ETAT['cible'].get('sous_systeme')}")
    if vus <= {None}:
        await logs.annoncer("Sous-système : le jeu ne dit pas lequel est visé (cible pas encore "
                            "scannée ?). Choisis-le à la main", "attention")
    else:
        await logs.annoncer("Sous-système : cette cible n'a pas ce module", "attention")
    await dire("macro_echec", "refus")


# =====================================================================
#  CHASSEUR EMBARQUÉ
# =====================================================================
async def _chasseur(action, texte, dire, poli):
    ordre = next(((t, n) for mots, t, n in ORDRES_CHASSEUR if _contient(texte, mots)), None)
    if not ordre:
        return await refuser(dire, "refus_ordre_inconnu",
                             "Chasseur : ordre non compris (défends, attaque ma cible, tir à "
                             "volonté, tiens la position, suis-moi, cessez le feu, rappel)")
    touche, nom = ordre
    if not await touche_prete(dire, touche, f"Chasseur ({nom})"):
        return
    if logs.ETAT["vaisseau"].get("chasseur") in ("a_bord", "detruit"):
        return await refuser(dire, "refus_pas_de_chasseur", "Chasseur : aucun chasseur déployé")
    if not await preparer_jeu(dire):
        return
    await confirmer(dire, action, poli)
    await appuyer(touche)
    await logs.annoncer(f"Chasseur : {nom}")


# =====================================================================
#  DRONES (lancés depuis un groupe de tir)
# =====================================================================
async def _drone(action, texte, dire, poli):
    sorte = ("prospection" if _contient(texte, ("prospect",)) else
             "collecte" if _contient(texte, ("collect", "recup", "ramass")) else None)
    if not sorte:
        return await refuser(dire, "refus_ordre_inconnu",
                             "Drone : précise « prospection » ou « collecte »")
    reglage = macros.DRONES[sorte]
    if not reglage.get("groupe"):
        return await refuser(dire, "refus_drone_non_regle",
                             f"Drone de {sorte} : indique son groupe de tir dans DRONES (macros.py)")
    tir = "tir_secondaire" if reglage.get("tir") == "secondaire" else "tir_principal"
    for touche, nom in ((tir, "Tir"), ("groupe_suivant", "Groupe de tir suivant")):
        if not await touche_prete(dire, touche, f"Drone ({nom})"):
            return
    if etat_connu():
        if not drapeau("vaisseau"):
            return await refuser(dire, "refus_hors_vaisseau", "Drone : impossible hors du vaisseau")
        if await _interdits(dire, "Drone", [_SC, _AMARRE]):
            return
    if not await preparer_jeu(dire):
        return

    def groupe():
        return logs.ETAT["status"].get("groupe_tir")

    voulu, depart = reglage["groupe"] - 1, groupe()
    if depart is None:
        return await refuser(dire, "macro_echec", "Drone : groupe de tir actuel inconnu")
    await confirmer(dire, action, poli)

    avances = 0
    while groupe() != voulu and avances < 10:
        precedent = groupe()
        await appuyer("groupe_suivant")
        avances += 1
        await attendre(lambda: groupe() != precedent, 1)
    if groupe() != voulu:
        await logs.annoncer(f"Drone : groupe de tir {reglage['groupe']} introuvable", "alerte")
        return await dire("macro_echec", "refus")

    await asyncio.sleep(0.3)
    await appuyer(tir, duree=0.25)
    await asyncio.sleep(0.4)
    retours = 0
    while groupe() != depart and retours < 10:          # retour au groupe de départ
        precedent = groupe()
        await appuyer("groupe_suivant")
        retours += 1
        await attendre(lambda: groupe() != precedent, 1)
    await logs.annoncer(f"Drone de {sorte} lancé")


# =====================================================================
#  RÉACTIONS AUTOMATIQUES
# =====================================================================
_reactions = {"actives": macros.REACTIONS_AU_DEMARRAGE}


async def _basculer_reactions(action, texte, dire, poli):
    voulu = intention(texte)
    _reactions["actives"] = (voulu == "sortir") if voulu else not _reactions["actives"]
    etat = "activées" if _reactions["actives"] else "désactivées"
    await logs.annoncer(f"Réactions automatiques {etat}", "succes" if _reactions["actives"] else "info")
    await dire("reactions_actives" if _reactions["actives"] else "reactions_coupees",
               "affirmation", poli=poli)


async def _reagir(nom, texte, dire, cle, *etapes):
    """Joue une réaction si elle est permise et si le jeu a déjà le clavier."""
    if not (_reactions["actives"] and macros.REACTIONS.get(nom)):
        return
    if not drapeau("vaisseau") or not await asyncio.to_thread(macros.jeu_au_premier_plan):
        return
    await logs.annoncer(f"Réaction automatique : {texte}", "attention")
    await dire(cle)
    for etape in etapes:
        if etape in macros.MACROS:
            await asyncio.to_thread(macros.executer_touches, etape)
        else:
            await appuyer(etape)


async def surveiller_reactions(dire):
    """Tâche de fond lancée par main.py : réagit aux changements d'état du vaisseau."""
    interdictions = []
    logs.ecouter_evenements(
        lambda e: interdictions.append(e) if e.get("event") == "Interdicted" else None)
    precedents = None
    while True:
        await asyncio.sleep(0.25)
        try:
            actuels = _flags()
            if not actuels:
                precedents = None
                continue
            if precedents is not None:
                apparus, disparus = actuels & ~precedents, precedents & ~actuels
                if apparus & (1 << BIT["surchauffe"]) and macros.touche_connue("puce_thermique") \
                        and _module_present("heatsinklauncher") is not False:
                    await _reagir("surchauffe", "surchauffe, puce thermique larguée", dire,
                                  "reaction_surchauffe", "puce_thermique")
                if disparus & (1 << BIT["boucliers"]) and not drapeau("amarre"):
                    await _reagir("bouclier_tombe", "boucliers tombés, énergie aux systèmes", dire,
                                  "reaction_bouclier", "energie_sys")
            if interdictions:
                interdictions.clear()
                await _reagir("interdiction", "interdiction, énergie aux systèmes", dire,
                              "reaction_interdiction", "pips_defense")
            precedents = actuels
        except Exception as erreur:
            print(f"[Réactions] Erreur : {erreur!r}")


# =====================================================================
#  PROGRAMME : FUITE
# =====================================================================
async def _fuite(dire, poli=False):
    if etat_connu():
        if not drapeau("vaisseau"):
            return await refuser(dire, "refus_hors_vaisseau", "Fuite : impossible hors du vaisseau")
        if drapeau("amarre") or drapeau("pose"):
            return await refuser(dire, "refus_amarre", "Fuite : le vaisseau est posé")
        if drapeau("supercroisiere"):
            return await refuser(dire, "refus_supercroisiere", "Fuite : déjà en supercroisière")
    if not await preparer_jeu(dire):
        return
    await confirmer(dire, "fuite", poli)
    await logs.annoncer("Fuite : énergie aux systèmes et aux moteurs, saut dès que possible", "attention")

    if drapeau("armes") and macros.touche_connue("armement"):
        await appuyer("armement")            # le FSD ne charge pas armes sorties
        await attendre(lambda: not drapeau("armes"), 2)
    await asyncio.to_thread(macros.executer_touches, "pips_defense")
    if macros.touche_connue("leurres") and _module_present("chafflauncher"):
        await appuyer("leurres")

    def parti():
        return drapeau("supercroisiere") or drapeau("saut")

    fin, prochain_boost = time.monotonic() + 90, 0
    while time.monotonic() < fin and not parti():
        maintenant = time.monotonic()
        if maintenant >= prochain_boost:
            await appuyer("boost")
            prochain_boost = maintenant + 6
        # On n'appuie que si le FSD ne charge pas déjà : un 2e appui annulerait la charge
        if not drapeau("fsd_charge") and not drapeau("fsd_refroid"):
            await appuyer("saut")
            await attendre(lambda: drapeau("fsd_charge") or parti(), 2)
        await asyncio.sleep(0.3)

    if parti():
        await logs.annoncer("Fuite réussie", "succes")
        await dire("fuite_reussie")
    else:
        await logs.annoncer("Fuite : le FSD n'est pas parti (masse verrouillée ou FSD "
                            "endommagé ?). À toi les commandes", "alerte")
        await dire("macro_echec", "refus")


# =====================================================================
#  PROGRAMME : DÉCOLLAGE DE STATION
# =====================================================================
async def _decollage(dire, poli=False):
    if etat_connu():
        if not drapeau("vaisseau"):
            return await refuser(dire, "refus_hors_vaisseau", "Décollage : impossible hors du vaisseau")
        if not drapeau("amarre"):
            return await refuser(dire, "refus_pas_amarre", "Décollage : le vaisseau n'est pas amarré")
    if not await preparer_jeu(dire):
        return
    await confirmer(dire, "decollage", poli)
    await logs.annoncer("Décollage en cours…")

    if not await fermer_panneaux():
        return await refuser(dire, "macro_echec", "Décollage : un menu reste ouvert, ferme-le et réessaie")
    for touche in macros.SEQUENCE_DECOLLAGE:
        await appuyer(touche)
        await asyncio.sleep(0.15)
    # La plateforme peut devoir remonter du hangar : on laisse du temps au jeu
    if not await attendre(lambda: not drapeau("amarre"), 90):
        return await refuser(dire, "macro_echec",
                             "Décollage : le vaisseau est toujours amarré "
                             "(SEQUENCE_DECOLLAGE dans macros.py)")

    if _module_present("dockingcomputer_advanced"):
        await logs.annoncer("Pinces libérées : l'ordinateur d'appontage sort le vaisseau")
    else:
        await asyncio.sleep(2.5)                 # le temps de s'élever au-dessus de la plateforme
        if drapeau("train") and not drapeau("pose"):
            await appuyer("train")
        await logs.annoncer("Pinces libérées, train rentré : à toi les commandes pour la sortie")
        await dire("decollage_a_vous")

    if await attendre(lambda: not drapeau("masse"), 300):
        await logs.annoncer("Dégagé de la station", "succes")
        await dire("decollage_degage")


# =====================================================================
#  PROGRAMME : APONTAGE COMPLET (demande, train, ravitaillement)
# =====================================================================
async def _demander_apontage(dire):
    """Envoie la demande et attend la réponse de la station. Renvoie True si accordée."""
    reponses = []
    arreter_ecoute = logs.ecouter_evenements(
        lambda e: reponses.append(e) if e.get("event") in
        ("DockingRequested", "DockingGranted", "DockingDenied") else None)
    try:
        if not await fermer_panneaux():
            await refuser(dire, "macro_echec", "Apontage : un menu reste ouvert, ferme-le et réessaie")
            return False
        for touche in macros.SEQUENCE_DEMANDE_APONTAGE:
            await appuyer(touche)
            await asyncio.sleep(0.25)
        await attendre(lambda: any(e["event"] != "DockingRequested" for e in reponses), 10)
        await fermer_panneaux()
    finally:
        arreter_ecoute()

    accord = next((e for e in reponses if e["event"] == "DockingGranted"), None)
    refus = next((e for e in reponses if e["event"] == "DockingDenied"), None)
    if accord:
        await logs.annoncer(f"Apontage autorisé — plateforme {accord.get('LandingPad', '?')}", "succes")
        await dire("apontage_accorde")
        return True
    if refus:
        await logs.annoncer(f"Apontage refusé par la station ({refus.get('Reason', 'sans motif')})", "alerte")
        await dire("apontage_refuse", "refus")
    else:
        await logs.annoncer("Apontage : la station n'a pas répondu. Trop loin (plus de 7,5 km), ou "
                            "demande mal envoyée (SEQUENCE_DEMANDE_APONTAGE dans macros.py)", "alerte")
        await dire("macro_echec", "refus")
    return False


async def _apontage(dire, poli=False, annonce=True):
    if etat_connu():
        if not drapeau("vaisseau"):
            return await refuser(dire, "refus_hors_vaisseau", "Apontage : impossible hors du vaisseau")
        if drapeau("amarre"):
            return await refuser(dire, "refus_amarre", "Apontage : le vaisseau est déjà amarré")
        if drapeau("supercroisiere"):
            return await refuser(dire, "refus_supercroisiere",
                                 "Apontage : sors d'abord de supercroisière près de la station")
    if not await preparer_jeu(dire):
        return
    if annonce:
        await confirmer(dire, "apontage", poli)
    if not await _demander_apontage(dire):
        return

    if macros.TRAIN_AUTO_APONTAGE and not drapeau("train"):
        await appuyer("train")

    annulations = []
    arreter_ecoute = logs.ecouter_evenements(
        lambda e: annulations.append(e) if e.get("event") in
        ("DockingCancelled", "DockingTimeout") else None)
    try:
        amarre = await attendre(lambda: drapeau("amarre") or annulations, 600)
    finally:
        arreter_ecoute()
    if not drapeau("amarre"):
        await logs.annoncer("Apontage : autorisation perdue ou expirée", "attention")
        return await dire("apontage_expire", "refus")

    await asyncio.sleep(3)                       # le jeu affiche le menu d'amarrage
    await _ravitaillement(dire)


# =====================================================================
#  PROGRAMME : AUTOPILOTE VERS LA STATION CIBLÉE
#  Le COVAS enchaîne les étapes ; ce sont les modules du jeu qui pilotent
#  (assistance de supercroisière, ordinateur d'appontage).
# =====================================================================
async def _autopilote_station(dire, poli=False):
    if etat_connu():
        if not drapeau("vaisseau"):
            return await refuser(dire, "refus_hors_vaisseau", "Autopilote : impossible hors du vaisseau")
        if drapeau("amarre") or drapeau("pose"):
            return await refuser(dire, "refus_amarre", "Autopilote : décolle d'abord")
    destination = logs.ETAT["status"].get("destination")
    if not destination:
        return await refuser(dire, "refus_pas_de_destination",
                             "Autopilote : aucune destination. Cible la station dans le panneau "
                             "de navigation, puis redemande")
    if not await preparer_jeu(dire):
        return
    await confirmer(dire, "autopilote_station", poli)
    await logs.annoncer(f"Autopilote : cap sur {destination}")

    # 1. Supercroisière
    if not drapeau("supercroisiere"):
        if drapeau("armes") and macros.touche_connue("armement"):
            await appuyer("armement")
        if drapeau("train"):
            await appuyer("train")
        if drapeau("ecope"):
            await appuyer("soute")
        if drapeau("masse"):
            await logs.annoncer("Autopilote : masse verrouillée, éloigne-toi de la station", "attention")
            await dire("refus_masse")
            if not await attendre(lambda: not drapeau("masse"), 300):
                return await refuser(dire, "macro_echec", "Autopilote : toujours en masse verrouillée")
        await attendre(lambda: not drapeau("fsd_refroid"), 30)
        touche = "supercroisiere" if macros.touche_connue("supercroisiere") else "saut"
        await appuyer(touche)
        if not await attendre(lambda: drapeau("supercroisiere"), 40):
            return await refuser(dire, "macro_echec", "Autopilote : la supercroisière ne s'est pas enclenchée")
        await asyncio.sleep(3)

    # 2. Gaz dans la zone bleue + assistance de supercroisière
    if macros.touche_connue("vitesse_75"):
        await appuyer("vitesse_75")
    if macros.SEQUENCE_ASSISTANCE_SC:
        for touche in macros.SEQUENCE_ASSISTANCE_SC:
            await appuyer(touche)
            await asyncio.sleep(0.3)
        await fermer_panneaux()
        await logs.annoncer("Autopilote : assistance de supercroisière demandée")
    else:
        await logs.annoncer("Autopilote : active l'assistance de supercroisière sur ta destination "
                            "(panneau de navigation). Je m'occupe de la suite", "attention")
        await dire("autopilote_assistance")

    # 3. Attendre la sortie de supercroisière devant la station
    if not await attendre(lambda: not drapeau("supercroisiere"), 1800):
        return await refuser(dire, "macro_echec", "Autopilote : toujours en supercroisière après 30 minutes")
    await asyncio.sleep(2)
    if drapeau("danger") or drapeau("interdiction"):
        await logs.annoncer("Autopilote : sortie de supercroisière sous la menace. "
                            "Programme arrêté, à toi les commandes", "alerte")
        return await dire("autopilote_danger", "refus")
    await logs.annoncer("Autopilote : sortie de supercroisière, demande d'apontage")
    await asyncio.sleep(4)

    # 4. Apontage (l'ordinateur d'appontage pose le vaisseau) puis ravitaillement
    if _module_present("dockingcomputer") is False:
        await logs.annoncer("Autopilote : pas d'ordinateur d'appontage, tu poses le vaisseau", "attention")
    await _apontage(dire, annonce=False)


async def _services(dire, poli=False):
    if etat_connu() and not drapeau("amarre"):
        return await refuser(dire, "refus_pas_amarre", "Services : il faut être amarré à une station")
    if not await preparer_jeu(dire):
        return
    await confirmer(dire, "services", poli)
    if _focus() == 5:
        return await logs.annoncer("Services de la station déjà ouverts")
    if not await fermer_panneaux():
        return await refuser(dire, "macro_echec", "Services : un menu reste ouvert")
    for touche in macros.SEQUENCE_OUVRIR_SERVICES:
        await appuyer(touche)
        await asyncio.sleep(0.15)
    if await attendre(lambda: _focus() == 5, 5):
        await logs.annoncer("Services de la station ouverts")
    else:
        await logs.annoncer("Services : l'écran ne s'est pas ouvert "
                            "(SEQUENCE_OUVRIR_SERVICES dans macros.py)", "alerte")
        await dire("macro_echec", "refus")


# =====================================================================
#  RAVITAILLEMENT À QUAI : carburant, réparations, munitions
# =====================================================================
def _focus():
    return logs.ETAT["status"].get("focus") or 0


async def fermer_panneaux(essais=6):
    """Ferme les panneaux et menus ouverts (carte, panneaux latéraux, services...)
    jusqu'à revenir au cockpit. Le jeu indique le panneau ouvert dans Status.json."""
    for _ in range(essais):
        focus = _focus()
        if not focus:
            return True
        await appuyer("ui_retour")
        await attendre(lambda: _focus() != focus, 1.5)
    return not _focus()


async def _ravitaillement(dire, poli=False):
    if etat_connu() and not drapeau("amarre"):
        return await refuser(dire, "refus_pas_amarre",
                             "Ravitaillement : il faut être amarré à une station")

    station = logs.ETAT["position"].get("station") or {}
    services = set(station.get("services") or [])
    if services and not services & {"refuel", "repair", "rearm"}:
        return await refuser(dire, "refus_pas_de_services",
                             f"{station.get('nom') or 'Cette station'} ne propose ni carburant, "
                             "ni réparation, ni munitions")

    vaisseau = logs.ETAT["vaisseau"]
    carburant = logs.ETAT["status"].get("carburant")
    maxi = vaisseau.get("carburant_max")
    besoin_carburant = carburant is not None and maxi and carburant < maxi - 0.1
    besoin_reparation = (vaisseau.get("coque") or 1) < 0.999 or any(
        (m.get("sante") if m.get("sante") is not None else 1) < 0.999
        for m in logs.ETAT["modules"]["liste"])
    if not besoin_carburant and not besoin_reparation and services and "rearm" not in services:
        await logs.annoncer("Ravitaillement inutile : réservoir plein et vaisseau intact")
        return await dire("ravitaillement_inutile", "refus")

    if not await preparer_jeu(dire):
        return
    await dire("ravitaillement", poli=poli)
    await logs.annoncer("Ravitaillement en cours…")

    achats = []
    arreter_ecoute = logs.ecouter_evenements(
        lambda e: achats.append(e) if e.get("event") in ACHATS else None)
    try:
        if not await fermer_panneaux():
            return await refuser(dire, "macro_echec",
                                 "Ravitaillement : un menu reste ouvert, ferme-le et réessaie")

        for touche in macros.SEQUENCE_OUVRIR_SERVICES:
            await appuyer(touche)
            await asyncio.sleep(0.15)
        if not await attendre(lambda: _focus() == 5, 5):     # 5 = services de la station
            await fermer_panneaux()
            return await refuser(dire, "macro_echec",
                                 "Ravitaillement : les services de la station ne se sont pas ouverts "
                                 "(SEQUENCE_OUVRIR_SERVICES dans macros.py)")

        await asyncio.sleep(macros.ATTENTE_ECRAN)
        for touche in macros.SEQUENCE_RAVITAILLEMENT:
            await appuyer(touche)
            await asyncio.sleep(0.25)

        # Le jeu écrit chaque achat dans le journal : on attend de les voir passer
        def termine():
            noms = {e["event"] for e in achats}
            plein = not besoin_carburant or noms & {"RefuelAll", "RefuelPartial"}
            repare = not besoin_reparation or noms & {"RepairAll", "Repair"}
            return plein and repare
        await attendre(termine, 4)
        await asyncio.sleep(0.5)
        await fermer_panneaux()
    finally:
        arreter_ecoute()

    # Bilan
    noms = {e["event"] for e in achats}
    cout = sum(e.get("Cost", 0) or 0 for e in achats)
    carburant_achete = sum(e.get("Amount", 0) or 0 for e in achats if e["event"].startswith("Refuel"))
    faits = []
    if carburant_achete:
        faits.append(f"plein (+{carburant_achete:.1f} t)")
    if noms & {"RepairAll", "Repair"}:
        faits.append("réparations")
    if "BuyAmmo" in noms:
        faits.append("munitions")

    if faits:
        total = f"{int(cout):,}".replace(",", " ")
        await logs.annoncer(f"Ravitaillement terminé : {', '.join(faits)} — {total} cr", "succes")
        await dire("ravitaillement_termine")
    elif besoin_carburant or besoin_reparation:
        await logs.annoncer("Ravitaillement : rien n'a été acheté. Crédits insuffisants, ou boutons "
                            "à un autre endroit (SEQUENCE_RAVITAILLEMENT dans macros.py)", "alerte")
        await dire("macro_echec", "refus")
    else:
        await logs.annoncer("Rien à faire : réservoir plein, vaisseau intact, munitions au maximum")
        await dire("ravitaillement_inutile")


# =====================================================================
#  TABLES DES COMMANDES (remplies ici car les fonctions sont définies plus haut)
# =====================================================================
# clé de barks.json -> (nom affiché, fonction(dire, poli) qui fabrique le programme)
PROGRAMMES = {
    "ravitaillement": ("Ravitaillement", _ravitaillement),
    "decollage": ("Décollage", _decollage),
    "apontage": ("Apontage", _apontage),
    "fuite": ("Fuite", _fuite),
    "autopilote_station": ("Autopilote station", _autopilote_station),
    "services": ("Services de la station", _services),
}

# clé de barks.json -> fonction(action, texte, dire, poli)
SPECIALES = {
    "sous_systeme": _sous_systeme,
    "chasseur": _chasseur,
    "drone": _drone,
    "reactions": _basculer_reactions,
}
