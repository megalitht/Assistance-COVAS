"""
actions.py — Commandes « intelligentes ».

Avant d'appuyer sur une touche, le COVAS regarde l'état du vaisseau (Status.json) :
  - il refuse ce qui n'a pas de sens (« sors le train » alors qu'il est déjà sorti) ;
  - il refuse ce que le jeu interdit (train en supercroisière, FSD à quai...) ;
  - après l'appui, il vérifie que le jeu a bien réagi, sinon il le signale.
Chaque refus est dit à voix haute (barks.json) et affiché dans l'interface.

Deux sortes de commandes :
  - les commandes courtes (une ou quelques touches) s'exécutent tout de suite ;
  - les PROGRAMMES (décollage, apontage, fuite, autopilote, voyage, ravitaillement) durent
    longtemps : ils tournent en tâche de fond, un seul à la fois, et « stop » les annule.

Point d'entrée : executer_commande(action, texte, dire, poli)
  action : clé de barks.json détectée dans la phrase (ex. "train_atterrissage")
  texte  : la phrase entendue (pour savoir si on veut sortir ou rentrer)
  dire   : fonction async dire(*cles, poli=False) qui joue la première réplique trouvée
"""
import asyncio
import os
import time
import traceback

from module import annonces
from module import avaries
from module import ecran
from module import lecteur_logs as logs
from module import macros
from module import serveur_ws
from module import touches

# Page de l'interface (le « panel »), ouverte par la commande vocale « ouvre le panel »
CHEMIN_INTERFACE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "Frontend", "interface.html")
# True quand le COVAS tourne dans l'application (Backend/app.py) : l'interface est alors
# sa propre fenêtre, on ne lance jamais de navigateur.
MODE_APPLICATION = False
from module.macros import normaliser

# Bits de Status.json utilisés ici
BIT = {"amarre": 0, "pose": 1, "train": 2, "boucliers": 3, "supercroisiere": 4, "armes": 6,
       "feux": 8, "ecope": 9, "silencieux": 10, "ecopage_carburant": 11, "masse": 16, "fsd_charge": 17,
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


def sans_reaction(nom, touche):
    """Texte affiché quand le jeu n'a pas réagi à la touche."""
    raison = touches.pourquoi_sans_effet(touche)
    if raison:
        return f"{nom} : le jeu n'a pas réagi à {macros.nom_touche(touche).upper()} ({raison})"
    return f"{nom} : le jeu n'a pas réagi (touche « {macros.nom_touche(touche)} » ?)"


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
#  PROGRAMME : FSD DIFFÉRÉ (demandé en masse verrouillée)
#  Le commandant s'éloigne aux commandes ; le FSD part tout seul à la sortie du champ.
# =====================================================================
NOM_FSD_DIFFERE = "FSD en attente"
FSD_ATTENTE_MAX = 300           # secondes avant d'abandonner la demande
FSD_DELAI_LIBRE = 1             # secondes sans masse verrouillée avant d'appuyer


def _fsd_differe_en_cours():
    return programme_en_cours() and _programme["nom"] == NOM_FSD_DIFFERE


async def _fsd_apres_masse(dire, poli=False):
    await logs.annoncer("FSD en attente : éloigne-toi, il partira dès la sortie de la masse "
                        "verrouillée (« stop » pour annuler)", "attention")
    await dire("refus_masse", "refus")

    fin = time.monotonic() + FSD_ATTENTE_MAX
    libre_depuis = None
    while True:
        maintenant = time.monotonic()
        if maintenant > fin:
            return await refuser(dire, "macro_echec",
                                 "FSD annulé : toujours en masse verrouillée après 5 minutes")
        if not etat_connu():            # Status.json en cours d'écriture, ou menu du jeu
            libre_depuis = None
        elif not drapeau("vaisseau") or drapeau("amarre") or drapeau("pose"):
            return await logs.annoncer("FSD en attente annulé : le vaisseau n'est plus en vol",
                                       "attention")
        elif drapeau("supercroisiere") or drapeau("saut") or drapeau("fsd_charge"):
            # Le commandant a lancé le FSD lui-même : un 2e appui l'annulerait
            return await logs.annoncer("FSD déjà lancé manuellement")
        elif drapeau("masse") or drapeau("fsd_refroid") or _focus():
            libre_depuis = None         # on n'appuie pas non plus dans un menu ouvert
        else:
            libre_depuis = libre_depuis or maintenant
            if maintenant - libre_depuis >= FSD_DELAI_LIBRE:
                break
        await asyncio.sleep(0.15)

    if not await preparer_jeu(dire):
        return
    await confirmer(dire, "fsd", poli)
    # Le FSD ne charge pas avec les points d'emport, le train ou l'écope sortis
    a_rentrer = [(bit, touche) for bit, touche in
                 (("armes", "armement"), ("train", "train"), ("ecope", "soute"))
                 if drapeau(bit) and macros.touche_connue(touche)]
    for _, touche in a_rentrer:
        await appuyer(touche)
    if a_rentrer:
        await attendre(lambda: not any(drapeau(bit) for bit, _ in a_rentrer), 3)

    await asyncio.to_thread(macros.executer_touches, "fsd")
    if await attendre(lambda: drapeau("fsd_charge") or drapeau("saut")
                      or drapeau("supercroisiere"), 3):
        await logs.annoncer("Sortie de la masse verrouillée : FSD enclenché", "succes")
    else:
        await logs.annoncer(sans_reaction("FSD", "saut"), "alerte")
        await dire("macro_echec", "refus")


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

    if cle == "fsd" and _fsd_differe_en_cours():
        # Surtout pas de 2e appui : il annulerait la charge lancée par le programme
        return await logs.annoncer("FSD déjà en attente de la sortie de masse verrouillée")

    if cle == "fsd" and etat_connu():
        if not drapeau("vaisseau"):
            return await refuser(dire, "refus_hors_vaisseau", "FSD : impossible hors du vaisseau")
        if drapeau("amarre"):
            return await refuser(dire, "refus_amarre", "FSD : impossible quand le vaisseau est amarré")
        if drapeau("pose"):
            return await refuser(dire, "refus_pose", "FSD : décolle d'abord")
        if drapeau("masse"):
            if not await touche_prete(dire, "saut", "FSD"):
                return
            return await _lancer_programme(NOM_FSD_DIFFERE, _fsd_apres_masse(dire, poli), dire)

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
        await logs.annoncer(sans_reaction(cfg["nom"], cfg["touche"]), "alerte")
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
        await logs.annoncer(sans_reaction(nom, touche), "alerte")
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
#  INTERFACE WEB (« ouvre le panel »)
# =====================================================================
def _navigateur_app():
    """Chemin de Chrome ou d'Edge (ils savent ouvrir une page dans sa propre fenêtre)."""
    import winreg
    for exe in ("chrome.exe", "msedge.exe"):
        for racine in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(racine, r"Software\Microsoft\Windows\CurrentVersion"
                                            rf"\App Paths\{exe}") as cle:
                    chemin = winreg.QueryValue(cle, None)
            except OSError:
                continue
            if chemin and os.path.exists(chemin.strip('"')):
                return chemin.strip('"')
    return None


def _lancer_fenetre_interface():
    """Ouvre l'interface dans sa propre fenêtre (mode application de Chrome/Edge), et non
    dans un onglet : le COVAS peut ainsi toujours la retrouver par son titre.
    À défaut, navigateur par défaut."""
    import pathlib
    import subprocess
    navigateur = _navigateur_app() if os.name == "nt" else None
    if navigateur:
        subprocess.Popen([navigateur, f"--app={pathlib.Path(CHEMIN_INTERFACE).as_uri()}"])
    else:
        os.startfile(CHEMIN_INTERFACE)


async def _ouvrir_interface(action, texte, dire, poli):
    # Déjà ouverte : on ramène sa fenêtre devant les autres
    if await asyncio.to_thread(macros.focaliser_interface):
        await logs.annoncer("Interface ramenée au premier plan")
        return await confirmer(dire, action, poli)
    if MODE_APPLICATION:
        return await refuser(dire, "macro_echec",
                             "Interface : la fenêtre de l'application est introuvable")
    if serveur_ws.interfaces_ouvertes():
        # Connectée mais introuvable : c'est un onglet caché d'un navigateur -> on ouvre
        # une vraie fenêtre (tu peux fermer l'ancien onglet)
        await logs.annoncer("Interface cachée dans un onglet : ouverture dans sa propre "
                            "fenêtre (tu peux fermer l'ancien onglet)", "attention")
    if not os.path.exists(CHEMIN_INTERFACE):
        return await refuser(dire, "macro_echec", f"Interface introuvable : {CHEMIN_INTERFACE}")
    try:
        await asyncio.to_thread(_lancer_fenetre_interface)
    except OSError as erreur:
        return await refuser(dire, "macro_echec", f"Interface : impossible de l'ouvrir ({erreur})")
    await confirmer(dire, action, poli)


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
    gestes = annonces.DetecteurManuel()
    while True:
        await asyncio.sleep(0.25)
        try:
            actuels = _flags()
            for cle in gestes.observer(actuels, time.monotonic(), macros.DERNIERS_APPUIS,
                                       muet=programme_en_cours(),
                                       actives=macros.ANNONCES_MANUELLES):
                await dire(cle)
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
#  PROGRAMME : DÉCOLLAGE (station ou surface d'une planète)
#  Amarré (station, avant-poste, port planétaire) -> menu d'amarrage.
#  Posé sur une planète sans être amarré -> poussée verticale.
# =====================================================================
async def _decollage(dire, poli=False):
    if etat_connu():
        if not drapeau("vaisseau"):
            return await refuser(dire, "refus_hors_vaisseau", "Décollage : impossible hors du vaisseau")
        if drapeau("pose") and not drapeau("amarre"):
            return await _decollage_planete(dire, poli)
        if not drapeau("amarre"):
            return await refuser(dire, "refus_pas_amarre",
                                 "Décollage : le vaisseau n'est ni amarré ni posé")
    return await _decollage_station(dire, poli)


async def _decollage_planete(dire, poli=False):
    if not await touche_prete(dire, "poussee_haut", "Décollage de la planète"):
        return
    if not await preparer_jeu(dire):
        return
    await confirmer(dire, "decollage", poli)
    corps = logs.ETAT["status"].get("corps") or "la surface"
    await logs.annoncer(f"Décollage de {corps}…")
    if not await fermer_panneaux():
        return await refuser(dire, "macro_echec", "Décollage : un menu reste ouvert, ferme-le et réessaie")

    # Poussée verticale par impulsions, jusqu'à ce que le jeu ne dise plus « posé »
    fin = time.monotonic() + macros.DECOLLAGE_PLANETE_MAX
    while drapeau("pose") and time.monotonic() < fin:
        if not await appuyer("poussee_haut", duree=0.5):
            return
    if drapeau("pose"):
        return await refuser(dire, "macro_echec",
                             "Décollage : le vaisseau ne quitte pas le sol (touche « "
                             f"{macros.nom_touche('poussee_haut')} » ?)")

    # Un peu de hauteur avant de rentrer le train, pour ne pas retoucher le sol
    await appuyer("poussee_haut", duree=macros.DECOLLAGE_PLANETE_MONTEE)
    if drapeau("train"):
        await appuyer("train")
        await attendre(lambda: not drapeau("train"), 2)
    altitude = logs.ETAT["status"].get("altitude")
    hauteur = f" ({int(altitude)} m)" if isinstance(altitude, (int, float)) else ""
    await logs.annoncer(f"Décollé de {corps}{hauteur}, train rentré : à toi les commandes", "succes")
    await dire("decollage_a_vous")


async def _decollage_station(dire, poli=False):
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


# =====================================================================
#  PROGRAMME : VOYAGE AUTOMATIQUE LE LONG DE LA ROUTE (sauts FSD)
#  À chaque arrivée : piquer de ~90° pour ne plus viser l'étoile, avancer,
#  relancer le FSD, puis cabrer d'autant pour revenir dans l'axe d'arrivée.
# =====================================================================
def _route_active():
    """True si une route est tracée et qu'on n'en est pas encore au bout."""
    etapes = logs.ETAT["route"]["etapes"]
    return bool(etapes) and logs.ETAT["position"]["systeme"] != etapes[-1]["systeme"]


def _sauts_restants():
    route = logs.ETAT["route"]
    if route["etapes"] and route.get("indice_actuel") is not None:
        return len(route["etapes"]) - 1 - route["indice_actuel"]
    return (route.get("prochain") or {}).get("sauts_restants")


def _part_carburant():
    carburant = logs.ETAT["status"].get("carburant")
    maxi = logs.ETAT["vaisseau"].get("carburant_max")
    return carburant / maxi if carburant is not None and maxi else None


async def _autopilote(dire, poli=False):
    """« Autopilote » : suit la route si elle mène à un autre système, sinon va à la station."""
    if _route_active():
        return await _voyage(dire, poli)
    return await _autopilote_station(dire, poli)


async def _gaz_croisiere():
    """Gaz dans la zone bleue : c'est là que le vaisseau tourne le mieux en supercroisière."""
    for touche in ("vitesse_75", "vitesse_max"):
        if macros.touche_connue(touche):
            return await appuyer(touche)


async def _voyage_interrompu(dire):
    await logs.annoncer("Voyage : interdiction ! Programme arrêté, à toi les commandes", "alerte")
    await dire("autopilote_danger", "refus")


async def _voyage(dire, poli=False):
    if etat_connu():
        if not drapeau("vaisseau"):
            return await refuser(dire, "refus_hors_vaisseau", "Voyage : impossible hors du vaisseau")
        if drapeau("amarre") or drapeau("pose"):
            return await refuser(dire, "refus_amarre", "Voyage : décolle d'abord")
    if not _route_active():
        return await refuser(dire, "refus_pas_de_destination",
                             "Voyage : aucune route. Trace-la dans la carte de la galaxie, "
                             "puis redemande")
    for touche, nom in (("saut", "FSD"), ("tangage_bas", "piquer"), ("tangage_haut", "cabrer")):
        if not await touche_prete(dire, touche, f"Voyage ({nom})"):
            return
    if not await preparer_jeu(dire):
        return
    await confirmer(dire, "autopilote_route", poli)
    if not await fermer_panneaux():
        return await refuser(dire, "macro_echec", "Voyage : un menu reste ouvert, ferme-le et réessaie")
    destination = logs.ETAT["route"]["etapes"][-1]["systeme"]
    restants = _sauts_restants()
    await logs.annoncer(f"Voyage : cap sur {destination}"
                        + (f" ({restants} saut{'s' if restants > 1 else ''})" if restants else ""))

    if drapeau("armes") and macros.touche_connue("armement"):
        await appuyer("armement")            # le FSD ne charge pas armes sorties
    if drapeau("train"):
        await appuyer("train")
    if drapeau("ecope"):
        await appuyer("soute")

    if await asyncio.to_thread(ecran.ecran_lisible) is False:
        await logs.annoncer("Voyage : l'écran du jeu est illisible (plein écran exclusif ?). "
                            "Je ne verrai pas l'étoile, seule la chaleur sera surveillée. "
                            "Passe le jeu en plein écran fenêtré", "attention")

    evenements = []

    def ecouter(e):
        if e.get("event") in ("StartJump", "FSDJump"):
            evenements.append(e)
        elif e.get("event") == "HeatWarning":
            _CHALEUR["alerte"] = time.monotonic()

    arreter_ecoute = logs.ecouter_evenements(ecouter)
    try:
        # En supercroisière, le vaisseau vient sans doute d'arriver face à l'étoile
        face_etoile = drapeau("supercroisiere")
        while _route_active():
            part = _part_carburant()
            if part is not None and part < macros.VOYAGE_CARBURANT_MIN:
                await logs.annoncer(f"Voyage arrêté : carburant à {part:.0%}. Ravitaille-toi "
                                    "(écope sur une étoile KGBFOAM), puis relance", "alerte")
                return await dire("refus_carburant_voyage", "alerte_carburant")
            evenements.clear()
            if not await _un_saut(dire, face_etoile, evenements):
                return
            face_etoile = True
    finally:
        arreter_ecoute()

    # Arrivée : on ne laisse pas le vaisseau filer droit sur l'étoile
    await _gaz_croisiere()
    await appuyer("tangage_bas", duree=macros.VOYAGE_DUREE_TANGAGE)
    await logs.annoncer(f"Voyage terminé : bienvenue dans {destination}. À toi les commandes",
                        "succes")
    await dire("voyage_arrivee", "affirmation")


# Heure (time.monotonic) du dernier HeatWarning du journal pendant un voyage
_CHALEUR = {"alerte": 0.0}


def _trop_chaud():
    """True si le vaisseau est trop près de l'étoile. Le jeu ne donne pas la température :
    on se fie à la surchauffe (> 100 %), à l'écopage de carburant (on frôle l'étoile)
    et aux alertes de chaleur des 10 dernières secondes."""
    return (drapeau("surchauffe") or drapeau("ecopage_carburant")
            or time.monotonic() - _CHALEUR["alerte"] < 10)


async def _voler(dire, duree_min, duree_max=None):
    """Avance tout droit au moins `duree_min` s, et tant que le vaisseau chauffe (jusqu'à
    `duree_max`). False si une interdiction interrompt le vol."""
    debut = time.monotonic()
    duree_max = duree_max or duree_min
    while True:
        if drapeau("interdiction"):
            await _voyage_interrompu(dire)
            return False
        ecoule = time.monotonic() - debut
        if ecoule >= duree_max or (ecoule >= duree_min and not _trop_chaud()):
            return True
        await asyncio.sleep(0.5)


async def _ecart(dire, duree_min, duree_max=None):
    """Pique d'~90°, avance, puis cabre d'autant : le vaisseau se décale de côté
    et garde le cap d'origine."""
    await _gaz_croisiere()
    if not await appuyer("tangage_bas", duree=macros.VOYAGE_DUREE_TANGAGE):
        return False
    if not await _voler(dire, duree_min, duree_max):
        return False
    return await appuyer("tangage_haut", duree=macros.VOYAGE_DUREE_TANGAGE)


async def _attendre_voie_libre(dire):
    """N'autorise le FSD que quand ni l'étoile (au centre de l'écran) ni la chaleur ne
    gênent, et ce depuis VOYAGE_DELAI_VOIE_LIBRE secondes. Si l'étoile reste dans l'axe,
    refait un écart ; au-delà de VOYAGE_CONTOURNEMENTS_MAX, laisse le commandant
    contourner et saute dès que la voie se libère."""
    fin = time.monotonic() + macros.VOYAGE_ATTENTE_VOIE_LIBRE
    libre_depuis, ecarts, deja_dit = None, 0, set()

    async def dire_une_fois(cle, texte):
        if cle not in deja_dit:
            deja_dit.add(cle)
            await logs.annoncer(texte, "attention")

    while True:
        if drapeau("interdiction"):
            await _voyage_interrompu(dire)
            return False
        devant = await asyncio.to_thread(ecran.etoile_devant)     # None : écran illisible
        chaud = _trop_chaud()
        maintenant = time.monotonic()

        if not devant and not chaud:
            libre_depuis = libre_depuis or maintenant
            if maintenant - libre_depuis >= macros.VOYAGE_DELAI_VOIE_LIBRE:
                return True
        else:
            libre_depuis = None
            if devant and ecarts < macros.VOYAGE_CONTOURNEMENTS_MAX:
                ecarts += 1
                await logs.annoncer(f"Voyage : étoile dans l'axe, contournement ({ecarts}/"
                                    f"{macros.VOYAGE_CONTOURNEMENTS_MAX})", "attention")
                if not await _ecart(dire, macros.VOYAGE_DUREE_CONTOURNEMENT,
                                    macros.VOYAGE_DUREE_AVANCE_MAX):
                    return False
                continue
            if devant:
                if "manuel" not in deja_dit:
                    await dire("voyage_alignement")
                await dire_une_fois("manuel", "Voyage : l'étoile masque toujours la cible. "
                                              "Contourne-la, je saute dès que la voie est libre")
            else:
                await dire_une_fois("chaud", "Voyage : trop près de l'étoile, FSD en attente "
                                             "le temps de refroidir")

        if maintenant > fin:
            await refuser(dire, "macro_echec", "Voyage : la voie ne s'est pas libérée, "
                                               "programme arrêté. À toi les commandes")
            return False
        await asyncio.sleep(0.5)


async def _un_saut(dire, face_etoile, evenements):
    """Un saut de la route. Renvoie True une fois arrivé dans le système suivant."""
    def parti():
        return drapeau("saut") or any(
            e["event"] == "FSDJump" or e.get("JumpType") == "Hyperspace" for e in evenements)

    # 1. S'écarter de l'étoile : piquer, avancer (plus longtemps s'il fait chaud), cabrer
    #    d'autant pour revenir dans l'axe d'arrivée, vers le système suivant
    if face_etoile:
        await logs.annoncer("Voyage : dégagement de l'étoile")
        if not await _ecart(dire, macros.VOYAGE_DUREE_AVANCE, macros.VOYAGE_DUREE_AVANCE_MAX):
            return False

    # 2. Pas de FSD tant que l'étoile est dans l'axe ou que le vaisseau chauffe
    if drapeau("masse"):
        await logs.annoncer("Voyage : masse verrouillée, éloigne-toi de l'objet massif", "attention")
        if not await attendre(lambda: not drapeau("masse"), 120):
            await refuser(dire, "refus_masse", "Voyage : toujours en masse verrouillée")
            return False
    if not await _attendre_voie_libre(dire):
        return False

    # 3. Voie libre : lancer le FSD
    await attendre(lambda: not drapeau("fsd_refroid"), 60)
    await appuyer("saut")
    if not await attendre(lambda: drapeau("fsd_charge") or parti(), 3):
        await logs.annoncer(sans_reaction("Voyage : FSD", "saut"), "alerte")
        await dire("macro_echec", "refus")
        return False
    debut_charge = time.monotonic()

    # 4. Le saut part tout seul une fois chargé et aligné
    reste = macros.VOYAGE_ATTENTE_ALIGNEMENT - (time.monotonic() - debut_charge)
    if not await attendre(parti, max(reste, 1)):
        await logs.annoncer("Voyage : aligne-toi sur la cible (point plein au centre de la "
                            "boussole), le saut partira tout seul", "attention")
        await dire("voyage_alignement")
        fin, sans_charge = time.monotonic() + 300, None
        while not parti() and time.monotonic() < fin:
            if drapeau("interdiction"):
                await _voyage_interrompu(dire)
                return False
            # Charge annulée (cible masquée, trop long...) : on relance, sans jamais
            # appuyer pendant une charge (un 2e appui l'annulerait).
            if drapeau("fsd_charge") or drapeau("fsd_refroid"):
                sans_charge = None
            elif sans_charge is None:
                sans_charge = time.monotonic()
            elif time.monotonic() - sans_charge > 5 and not _trop_chaud() \
                    and not await asyncio.to_thread(ecran.etoile_devant):
                await appuyer("saut")
                sans_charge = None
            await asyncio.sleep(0.25)
        if not parti():
            await refuser(dire, "macro_echec", "Voyage : pas de saut après 5 minutes, programme arrêté")
            return False

    # 5. Arrivée dans le système suivant
    if not await attendre(lambda: any(e["event"] == "FSDJump" for e in evenements), 120):
        await refuser(dire, "macro_echec", "Voyage : arrivée dans le système suivant non détectée")
        return False
    await attendre(lambda: drapeau("supercroisiere") and not drapeau("saut"), 15)
    await asyncio.sleep(2)                  # le jeu rend les commandes peu après l'arrivée
    restants = _sauts_restants()
    if restants:
        await logs.annoncer(f"Voyage : {logs.ETAT['position']['systeme']} — encore {restants} "
                            f"saut{'s' if restants > 1 else ''}")
    return True


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
#  RAPPORT D'AVARIE (aucune touche : on lit l'état du vaisseau, voir module/avaries.py)
# =====================================================================
async def _rapport_avarie(action, texte, dire, poli):
    """Coque, boucliers, modules endommagés : affiché dans l'interface, annoncé par une réplique enregistrée."""
    rapport = avaries.construire_rapport(logs.ETAT)
    await logs.annoncer(rapport["texte"], rapport["gravite"], categorie="vaisseau")
    await serveur_ws.envoyer_donnees_web({"type": "rapport_avarie", "rapport": rapport})
    await dire("rapport_avarie", poli=poli)


# =====================================================================
#  TABLES DES COMMANDES (remplies ici car les fonctions sont définies plus haut)
# =====================================================================
# clé de barks.json -> (nom affiché, fonction(dire, poli) qui fabrique le programme)
PROGRAMMES = {
    "ravitaillement": ("Ravitaillement", _ravitaillement),
    "decollage": ("Décollage", _decollage),
    "apontage": ("Apontage", _apontage),
    "fuite": ("Fuite", _fuite),
    "autopilote_station": ("Autopilote", _autopilote),
    "autopilote_route": ("Voyage automatique", _voyage),
    "services": ("Services de la station", _services),
}

# clé de barks.json -> fonction(action, texte, dire, poli)
SPECIALES = {
    "sous_systeme": _sous_systeme,
    "chasseur": _chasseur,
    "drone": _drone,
    "reactions": _basculer_reactions,
    "interface": _ouvrir_interface,
    "rapport_avarie": _rapport_avarie,
}
