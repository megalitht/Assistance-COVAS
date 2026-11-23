"""
chasse.py — Le mode chasseur de primes.

  - le vaisseau est-il armé pour chasser ? (d'après les modules du Loadout) ;
  - sommes-nous dans une zone de chasse ? (SupercruiseDestinationDrop : sites d'extraction) ;
  - que vaut la cible scannée : recherchée, en règle, autorités, sans juridiction... ;
  - le tableau de chasse : éliminations, gains, primes à encaisser par faction.

Module pur : ni touches, ni fichiers, ni micro. Il se teste sans importer macros.py.
"""

SEUIL_GROS_GIBIER = 500_000     # cr : au-delà, le COVAS signale une belle prime
ARMES_MINIMUM = 2               # armes de combat pour considérer le vaisseau comme un chasseur
REPOS_ANNONCE = 120             # s avant de réannoncer le même pilote

RANGS_DANGEREUX = {"Dangerous", "Deadly", "Elite"}
_MINAGE = ("mining", "seismchrgwarhd", "subsurfdispmisle", "abrasion")

# Identifiant du jeu -> (code, nom affiché)
ZONES = {
    "$MULTIPLAYER_SCENARIO79_TITLE;": ("res_danger", "Site d'extraction [Danger]"),
    "$MULTIPLAYER_SCENARIO78_TITLE;": ("res_haut", "Site d'extraction [Élevé]"),
    "$MULTIPLAYER_SCENARIO14_TITLE;": ("res", "Site d'extraction"),
    "$MULTIPLAYER_SCENARIO77_TITLE;": ("res_bas", "Site d'extraction [Pauvre]"),
}

_VERDICTS = {
    "recherche": ("Recherché", True, "Feu autorisé"),
    "mandat": ("Sous mandat", True, "Prime dans une autre juridiction"),
    "ennemi": ("Ennemi", True, "Cible de guerre"),
    "sans_loi": ("Sans juridiction", True, "Aucune prime, aucun délit"),
    "clean": ("En règle", False, "Ne tirez pas"),
    "autorite": ("Autorités", False, "Ne tirez surtout pas"),
    "allie": ("Équipage", False, "Vaisseau ami"),
    "inconnu": ("Scan en cours", None, "Attendez la fin du scan"),
}


def vierge():
    return {"actif": False, "manuel": False, "zone": None, "zone_nom": None, "depuis": None,
            "profil": {"armes": 0, "scanner": False, "pret": False},
            "eliminations": 0, "gains": 0, "meilleure": 0, "scannes": 0, "recherches": 0,
            "a_encaisser": {}, "a_encaisser_total": 0}


def type_zone(type_brut):
    """(code, nom affiché) d'une destination de supercroisière, ou (None, None)."""
    return ZONES.get(type_brut or "", (None, None))


def profil(modules):
    """Armes de combat montées (hors minage et utilitaires) et présence d'un scanner de primes."""
    armes, scanner = 0, False
    for module in modules or []:
        emplacement, objet = (module.get("emplacement") or "").lower(), module.get("objet") or ""
        if "crimescanner" in objet:
            scanner = True
        if "hardpoint" in emplacement and not emplacement.startswith("tiny") \
                and not any(mot in objet for mot in _MINAGE):
            armes += 1
    return {"armes": armes, "scanner": scanner, "pret": armes >= ARMES_MINIMUM}


# ---------- Verdict sur une cible ----------
def verdict(e):
    """Ce qu'il faut savoir d'un événement ShipTargeted."""
    pilote = str(e.get("PilotName") or "")
    prime = e.get("Bounty") or 0
    statut = e.get("LegalStatus")

    if e.get("ScanStage", 0) < 3:
        code = "inconnu"
    elif pilote.startswith("$RolePanel2_"):        # son propre équipage, ou celui d'un autre joueur
        code = "allie"
    elif pilote.startswith(("$ShipName_Police", "$ShipName_PowersSecurity")):
        code = "autorite"
    elif statut in ("Wanted", "WantedEnemy") or (statut == "None" and prime):
        code = "recherche"            # « None » avec une prime : payée à la destruction
    elif statut == "Warrant":
        code = "mandat"
    elif statut == "Enemy":
        code = "ennemi"
    elif statut == "Clean":
        code = "clean"
    elif statut in ("Lawless", "None"):
        code = "sans_loi"
    else:
        code = "inconnu"

    libelle, tirer, conseil = _VERDICTS[code]
    return {"code": code, "libelle": libelle, "tirer": tirer, "conseil": conseil,
            "joueur": pilote.startswith("$cmdr_decorate"),
            "prime": prime if code in ("recherche", "mandat") else 0,
            "dangereux": e.get("PilotRank") in RANGS_DANGEREUX,
            "gros": code in ("recherche", "mandat") and prime >= SEUIL_GROS_GIBIER}


def repliques_cible(fiche):
    """Clés de répliques d'un verdict : d'abord l'essentiel, puis une précision utile."""
    cles = {"recherche": ["chasse_recherchee"], "mandat": ["chasse_recherchee"],
            "clean": ["chasse_clean"], "autorite": ["chasse_autorite"],
            "sans_loi": ["chasse_sans_loi"]}.get(fiche["code"], [])
    if not cles:
        return []
    if fiche["joueur"]:
        cles = cles + ["chasse_joueur"]
    elif fiche["gros"]:
        cles = cles + ["chasse_gros_gibier"]
    elif fiche["tirer"] and fiche["dangereux"]:
        cles = cles + ["chasse_dangereux"]
    return cles


class Veille:
    """Retient les pilotes déjà annoncés : une cible n'est dite qu'une fois."""

    def __init__(self):
        self.vus = {}

    def nouvelle(self, e, maintenant):
        cle = (e.get("PilotName"), e.get("Ship"))
        if maintenant - self.vus.get(cle, -1e9) < REPOS_ANNONCE:
            return False
        self.vus = {c: t for c, t in self.vus.items() if maintenant - t < REPOS_ANNONCE}
        self.vus[cle] = maintenant
        return True

    def oublier(self):
        self.vus.clear()


# ---------- Mode et tableau de chasse ----------
def activer(chasse, horodatage, zone=None, zone_nom=None, manuel=False):
    """Démarre une chasse. True si le mode vient de s'allumer."""
    deja = chasse["actif"]
    if zone:
        chasse.update(zone=zone, zone_nom=zone_nom)
    if deja:
        chasse["manuel"] = chasse["manuel"] or manuel
        return False
    if not zone:
        chasse.update(zone=None, zone_nom=None)
    chasse.update(actif=True, manuel=manuel, depuis=horodatage, eliminations=0, gains=0,
                  meilleure=0, scannes=0, recherches=0)
    return True


def arreter(chasse):
    """Fin de la chasse. Renvoie le bilan si le mode était allumé, sinon None.
    Les primes à encaisser restent : elles sont valables jusqu'à la station."""
    if not chasse["actif"]:
        return None
    bilan = {"eliminations": chasse["eliminations"], "gains": chasse["gains"]}
    chasse.update(actif=False, manuel=False, zone=None, zone_nom=None, depuis=None)
    return bilan


def compter_scan(chasse, fiche):
    if chasse["actif"] and fiche["code"] != "inconnu":
        chasse["scannes"] += 1
        if fiche["code"] in ("recherche", "mandat"):
            chasse["recherches"] += 1


def _total(chasse):
    chasse["a_encaisser_total"] = sum(chasse["a_encaisser"].values())


def prime(chasse, e):
    """Événement Bounty : tableau de chasse et primes à encaisser par faction."""
    montant = e.get("TotalReward", e.get("Reward", 0)) or 0
    recompenses = e.get("Rewards") or [{"Faction": e.get("Faction") or "?", "Reward": montant}]
    for ligne in recompenses:
        faction = ligne.get("Faction") or "?"
        chasse["a_encaisser"][faction] = chasse["a_encaisser"].get(faction, 0) + (ligne.get("Reward") or 0)
    _total(chasse)
    if chasse["actif"]:
        chasse["eliminations"] += 1
        chasse["gains"] += montant
        chasse["meilleure"] = max(chasse["meilleure"], montant)
    return montant


def encaisser(chasse, e):
    """RedeemVoucher de primes : les factions payées sortent de la liste."""
    if e.get("Type") != "bounty":
        return False
    factions = [f.get("Faction") for f in e.get("Factions") or []]
    if factions:
        for faction in factions:
            chasse["a_encaisser"].pop(faction, None)
    else:
        chasse["a_encaisser"].clear()
    _total(chasse)
    return True


def perdre_primes(chasse):
    """Vaisseau détruit : les primes non encaissées sont perdues."""
    chasse["a_encaisser"].clear()
    _total(chasse)
