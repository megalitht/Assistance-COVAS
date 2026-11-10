"""
actions.py — Commandes « intelligentes ».

Avant d'appuyer sur une touche, le COVAS regarde l'état du vaisseau (Status.json) :
  - il refuse ce qui n'a pas de sens (« sors le train » alors qu'il est déjà sorti) ;
  - il refuse ce que le jeu interdit (train en supercroisière, FSD à quai...) ;
  - après l'appui, il vérifie que le jeu a bien réagi, sinon il le signale.
Chaque refus est dit à voix haute (barks.json) et affiché dans l'interface.

Point d'entrée : executer_commande(action, texte, dire, poli)
  action : clé de barks.json détectée dans la phrase (ex. "train_atterrissage")
  texte  : la phrase entendue (pour savoir si on veut sortir ou rentrer)
  dire   : fonction async dire(*cles, poli=False) qui joue la première réplique trouvée
"""
import asyncio
import time

from module import lecteur_logs as logs
from module import macros
from module.macros import normaliser

# Bits de Status.json utilisés ici
BIT = {"amarre": 0, "pose": 1, "train": 2, "supercroisiere": 4, "ecope": 9,
       "masse": 16, "vaisseau": 24}

# Débuts de mots qui indiquent ce que veut le commandant
MOTS_RENTRER = ("rentr", "rang", "remont", "ferm", "etein", "desactiv", "coup", "repli", "retract")
MOTS_SORTIR = ("sor", "deploi", "deploy", "descend", "baiss", "ouvr", "allum", "activ")

# Ce qui se bascule avec une seule touche, et dont le jeu donne l'état
BASCULES = {
    "train_atterrissage": {
        "touche": "train", "bit": "train", "nom": "Train d'atterrissage",
        "etats": ("sorti", "rentré"), "deja": ("train_deja_sorti", "train_deja_rentre"),
        # (drapeau qui interdit, intention concernée ou None = toujours, réplique, raison)
        "interdit": [("supercroisiere", None, "refus_supercroisiere", "en supercroisière"),
                     ("amarre", None, "refus_amarre", "quand le vaisseau est amarré"),
                     ("pose", "rentrer", "refus_pose", "quand le vaisseau est posé")],
    },
    "soute": {
        "touche": "soute", "bit": "ecope", "nom": "Écope de soute",
        "etats": ("ouverte", "fermée"), "deja": ("soute_deja_ouverte", "soute_deja_fermee"),
        "interdit": [("supercroisiere", "sortir", "refus_supercroisiere", "en supercroisière"),
                     ("amarre", None, "refus_amarre", "quand le vaisseau est amarré")],
    },
}

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


async def attendre(condition, delai):
    """Attend jusqu'à `delai` secondes que condition() devienne vraie."""
    fin = time.monotonic() + delai
    while time.monotonic() < fin:
        if condition():
            return True
        await asyncio.sleep(0.15)
    return condition()


async def appuyer(nom, fois=1):
    await asyncio.to_thread(macros.appuyer, nom, fois)


async def refuser(dire, cle, texte):
    await logs.annoncer(texte, "attention")
    await dire(cle, "refus")


async def preparer_jeu(dire):
    """Le jeu doit être au premier plan, sinon les touches partent ailleurs."""
    if await asyncio.to_thread(macros.focaliser_jeu):
        return True
    await refuser(dire, "refus_jeu_absent",
                  "Fenêtre d'Elite Dangerous introuvable : commande annulée")
    return False


# =====================================================================
#  POINT D'ENTRÉE
# =====================================================================
async def executer_commande(action, texte, dire, poli=False):
    cle = normaliser(action)

    if cle in BASCULES:
        return await _bascule(action, BASCULES[cle], texte, dire, poli)
    if cle == "ravitaillement":
        return await _ravitaillement(dire, poli)

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
    await dire(action, poli=poli)
    await asyncio.to_thread(macros.executer_touches, cle)


# =====================================================================
#  TRAIN, SOUTE...
# =====================================================================
async def _bascule(action, cfg, texte, dire, poli):
    voulu = intention(texte)

    if etat_connu():
        if not drapeau("vaisseau"):
            return await refuser(dire, "refus_hors_vaisseau",
                                 f"{cfg['nom']} : impossible hors du vaisseau")
        actuel = drapeau(cfg["bit"])
        if voulu and actuel == (voulu == "sortir"):
            etat = cfg["etats"][0 if actuel else 1]
            return await refuser(dire, cfg["deja"][0 if actuel else 1], f"{cfg['nom']} déjà {etat}")
        direction = voulu or ("rentrer" if actuel else "sortir")
        for nom_drapeau, seulement, cle, raison in cfg["interdit"]:
            if drapeau(nom_drapeau) and seulement in (None, direction):
                return await refuser(dire, cle, f"{cfg['nom']} : impossible {raison}")
    else:
        actuel = None      # état inconnu : on bascule à l'aveugle, comme avant

    if not await preparer_jeu(dire):
        return
    await dire(action, poli=poli)
    await appuyer(cfg["touche"])

    if actuel is None:
        return
    if await attendre(lambda: drapeau(cfg["bit"]) != actuel, 3):
        await logs.annoncer(f"{cfg['nom']} {cfg['etats'][0 if not actuel else 1]}")
    else:
        await logs.annoncer(f"{cfg['nom']} : le jeu n'a pas réagi (touche « "
                            f"{macros.TOUCHES[cfg['touche']]} » dans macros.py ?)", "alerte")
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


async def _ravitaillement(dire, poli):
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
