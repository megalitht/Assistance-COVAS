"""
edsm.py — EDSM (Elite Dangerous Star Map), API publique : https://www.edsm.net/fr/api-v1

  systemes_dans_un_rayon(systeme, rayon)  systèmes à portée de saut (api-v1/sphere-systems)
  fiche_systeme(systeme)                  stations, corps et valeur estimée du système
                                          (api-system-v1/stations, /bodies, /estimated-value)

Formats vérifiés le 24/11/2026 (Sol) : un système inconnu d'EDSM renvoie {}.
Fonctions bloquantes (réseau) : à appeler via asyncio.to_thread. Seul le nom du système est envoyé.
"""
from module.externe.reseau import ErreurExterne, requete_json

URL = "https://www.edsm.net"
RAYON_MAX = 100          # limite imposée par EDSM (années-lumière)
CLASSES_RAVITAILLABLES = set("KGBFOAM")

TYPES_STATIONS = {
    "Coriolis Starport": "Coriolis", "Orbis Starport": "Orbis", "Ocellus Starport": "Ocellus",
    "Outpost": "Avant-poste", "Planetary Outpost": "Avant-poste planétaire", "Planetary Port": "Port planétaire",
    "Asteroid base": "Base astéroïde", "Mega ship": "Méga-vaisseau", "Fleet Carrier": "Porte-vaisseaux",
    "Odyssey Settlement": "Colonie",
}
# Plus grande plateforme : les avant-postes n'ont que des moyennes ; une colonie, ça dépend.
PLATEFORMES = {"Outpost": "M", "Odyssey Settlement": "?"}
SERVICES = {
    "Restock": "Munitions", "Refuel": "Carburant", "Repair": "Réparation",
    "Universal Cartographics": "Cartographie", "Vista Genomics": "Vista Genomics",
    "Material Trader": "Courtier en matériaux", "Technology Broker": "Courtier technologique",
    "Black Market": "Marché noir", "Interstellar Factors Contact": "Facteurs interstellaires",
    "Search and Rescue": "Recherche et sauvetage", "Missions": "Missions", "Crew Lounge": "Équipage",
    "Tuning": "Personnalisation", "Contacts": "Contacts",
}
SOUS_TYPES_NOTABLES = ("Earth-like world", "Water world", "Ammonia world")


def _classe_etoile(type_edsm):
    """'K (Yellow-Orange) Star' -> 'K' ; 'Neutron Star' -> 'N' ; etc."""
    if not type_edsm:
        return "?"
    texte = type_edsm.lower()
    for motif, classe in (("neutron", "N"), ("black hole", "H"), ("white dwarf", "D"),
                          ("wolf-rayet", "W"), ("t tauri", "TTS"), ("herbig", "AeBe")):
        if motif in texte:
            return classe
    return type_edsm.split(" ")[0][:3]


def systemes_dans_un_rayon(systeme, rayon_al, delai=10):
    """[{nom, distance, classe, ravitaillable}], du plus proche au plus lointain."""
    _, brut = requete_json(f"{URL}/api-v1/sphere-systems", {
        "systemName": systeme, "radius": round(min(rayon_al, RAYON_MAX), 2), "showPrimaryStar": 1}, delai=delai)
    if not isinstance(brut, list):      # système inconnu d'EDSM : l'API renvoie {}
        return []
    resultat = []
    for entree in brut:
        if not isinstance(entree, dict) or entree.get("name") == systeme:
            continue
        etoile = entree.get("primaryStar") or {}
        classe = _classe_etoile(etoile.get("type"))
        ravitaillable = etoile.get("isScoopable")
        if ravitaillable is None:
            ravitaillable = classe in CLASSES_RAVITAILLABLES
        resultat.append({"nom": entree.get("name"), "distance": entree.get("distance"),
                         "classe": classe, "ravitaillable": bool(ravitaillable)})
    resultat.sort(key=lambda s: s["distance"] if s["distance"] is not None else 1e9)
    return resultat


# =====================================================================
#  FICHE DU SYSTÈME
# =====================================================================
def stations(systeme, delai=5):
    """Stations du système : type, plus grande plateforme, distance, services."""
    _, brut = requete_json(f"{URL}/api-system-v1/stations", {"systemName": systeme}, delai=delai)
    liste = []
    entrees = (brut.get("stations") or []) if isinstance(brut, dict) else []
    for s in entrees:
        services = [nom for cle, nom in (("haveMarket", "Marché"), ("haveShipyard", "Chantier naval"),
                                         ("haveOutfitting", "Équipement")) if s.get(cle)]
        services += [SERVICES[x] for x in s.get("otherServices") or [] if x in SERVICES]
        liste.append({"nom": s.get("name"), "type": TYPES_STATIONS.get(s.get("type"), s.get("type")),
                      "plateforme": PLATEFORMES.get(s.get("type"), "L"),
                      "distance_ls": s.get("distanceToArrival"), "economie": s.get("economy"),
                      "services": services})
    ordre = {"L": 0, "M": 1, "?": 2}
    liste.sort(key=lambda s: (ordre.get(s["plateforme"], 3), s["distance_ls"] or 1e12))
    return liste


def corps(systeme, delai=5):
    """Résumé des corps connus d'EDSM : nombre, posables, terraformables, mondes notables."""
    _, brut = requete_json(f"{URL}/api-system-v1/bodies", {"systemName": systeme}, delai=delai)
    if not isinstance(brut, dict) or "bodies" not in brut:
        return None
    liste = brut.get("bodies") or []
    notables = [{"nom": b.get("name"), "type": b.get("subType"), "distance_ls": b.get("distanceToArrival")}
                for b in liste if b.get("subType") in SOUS_TYPES_NOTABLES]
    return {"total": brut.get("bodyCount") or len(liste), "connus": len(liste),
            "etoiles": sum(1 for b in liste if b.get("type") == "Star"),
            "planetes": sum(1 for b in liste if b.get("type") == "Planet"),
            "posables": sum(1 for b in liste if b.get("isLandable")),
            "terraformables": sum(1 for b in liste if (b.get("terraformingState") or "").startswith(("Candidate", "Terraform"))),
            "notables": notables}


def valeur(systeme, delai=5):
    """Valeur estimée par EDSM (sert à recouper l'estimation du COVAS)."""
    _, brut = requete_json(f"{URL}/api-system-v1/estimated-value", {"systemName": systeme}, delai=delai)
    if not isinstance(brut, dict) or "estimatedValue" not in brut:
        return None
    return {"estimation": brut.get("estimatedValue"), "estimation_carto": brut.get("estimatedValueMapped"),
            "precieux": [{"nom": b.get("bodyName"), "valeur": b.get("valueMax")}
                         for b in brut.get("valuableBodies") or []][:5]}


def fiche_systeme(systeme, delai=5, cache=None, duree_s=12 * 3600):
    """Les trois parties de la fiche ; une partie en panne vaut None (« Données indisponibles »)."""
    fiche, erreurs = {"systeme": systeme}, []
    for nom, fonction in (("stations", stations), ("corps", corps), ("valeur", valeur)):
        try:
            if cache:
                fiche[nom] = cache.ou_calculer(f"edsm:{nom}:{systeme}", duree_s, lambda f=fonction: f(systeme, delai))
            else:
                fiche[nom] = fonction(systeme, delai)
        except ErreurExterne as erreur:
            fiche[nom] = None
            erreurs.append(f"{nom} : {erreur}")
    fiche["erreurs"] = erreurs
    fiche["connu"] = bool(fiche.get("stations") or fiche.get("corps") or fiche.get("valeur"))
    return fiche
