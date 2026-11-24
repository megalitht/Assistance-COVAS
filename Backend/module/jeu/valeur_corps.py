"""
valeur_corps.py — Ce que rapporte un corps céleste à la Cartographie universelle.

Formule de la communauté (MattG, forum Frontier « Exploration value formulae »), alignée sur le code
d'EDDiscovery (EliteDangerousCore, FrontierData/Enumerations/EstimatedValues.cs, relu le 24/11/2026).
Tout le calcul est ici : s'il faut la corriger (mise à jour du jeu), c'est le seul fichier à modifier.
Les tests (tests/test_exploration_suivi.py) donnent des valeurs de référence.

Limite connue, mesurée sur les ventes du commandant : une planète déjà découverte mais marquée
« jamais cartographiée » (WasMapped = false) reçoit ici, comme dans EDDiscovery, le bonus de premier
cartographe (×8,1), alors que le jeu a souvent payé le tarif normal (×3,3) : l'estimation est alors
trop haute. Chaque vente compare l'estimation au montant payé (voir suivi_exploration.py).

  valeur_planete(...)  /  valeur_etoile(...)   : un corps
  valeur_scan(scan, carto, efficace)            : d'après un événement Scan du journal
  bonus_systeme(...)                            : bonus de système complet et de cartographie complète

Ces montants restent des ESTIMATIONS (≈) : le jeu ne les écrit qu'à la vente.
"""

Q = 0.56591828                    # coefficient de masse des planètes
PREMIERE_DECOUVERTE = 2.6         # bonus de première découverte (WasDiscovered = false)
CARTO_PREMIER_DECOUVREUR = 3.699622554   # cartographié, premier découvreur et premier cartographe
CARTO_PREMIER = 8.0956            # premier cartographe (déjà découvert par quelqu'un d'autre)
CARTO_DEJA = 10 / 3               # cartographié, déjà cartographié par quelqu'un
BONUS_ODYSSEY = 0.3               # + 30 % (au moins 555 cr) pour une planète cartographiée
BONUS_ODYSSEY_MIN = 555
BONUS_EFFICACITE = 1.25           # cartographie faite avec au plus le nombre de sondes visé
VALEUR_MIN = 500

# Bonus de fin de système (notes de version 3.3 « Beyond » : à vérifier sur une vente réelle)
BONUS_SYSTEME_COMPLET = 1000          # cr par corps, quand tous les corps sont trouvés (FSS)
BONUS_CARTOGRAPHIE_COMPLETE = 10000   # cr par planète, quand toutes les planètes sont cartographiées

TERRAFORMABLE = ("Terraformable", "Terraforming", "Terraformed")


def k_planete(classe, terraformable):
    """Valeur de base d'une planète selon sa classe (PlanetClass du journal)."""
    if classe == "Metal rich body":
        return 21790 + (65631 if terraformable else 0)
    if classe == "Ammonia world":
        return 96932
    if classe == "Sudarsky class I gas giant":
        return 1656
    if classe == "Sudarsky class II gas giant":
        return 9654
    if classe == "High metal content body":
        return 9654 + (100677 if terraformable else 0)
    if classe == "Water world":
        return 64831 + (116295 if terraformable else 0)
    if classe == "Earthlike body":
        return 64831 + 116295
    return 300 + (93328 if terraformable else 0)


def valeur_planete(classe, terraformable, masse, premier, carto=False, premier_carto=False,
                   efficace=True):
    """Crédits à la vente. premier : première découverte. carto : cartographiée (sondes).
    premier_carto : personne ne l'avait cartographiée (WasMapped = false)."""
    k = k_planete(classe, terraformable)
    valeur = max(VALEUR_MIN, k + k * Q * (masse or 0) ** 0.2)      # minimum sur la valeur de base
    if carto:
        if premier and premier_carto:
            valeur *= CARTO_PREMIER_DECOUVREUR
        elif premier_carto:
            valeur *= CARTO_PREMIER
        else:
            valeur *= CARTO_DEJA
        valeur += max(valeur * BONUS_ODYSSEY, BONUS_ODYSSEY_MIN)
        if efficace:
            valeur *= BONUS_EFFICACITE
    return round(valeur * (PREMIERE_DECOUVERTE if premier else 1))


def valeur_etoile(type_etoile, masse, premier):
    """Étoiles (et trous noirs) : selon le type (StarType) et la masse (en masses solaires)."""
    type_etoile = type_etoile or ""
    if type_etoile in ("N", "H", "SupermassiveBlackHole"):
        k = 22628
    elif type_etoile.startswith("D"):
        k = 14057
    else:
        k = 1200
    return round((k + (masse or 0) * k / 66.25) * (PREMIERE_DECOUVERTE if premier else 1))


def terraformable(scan):
    return (scan.get("TerraformState") or "") in TERRAFORMABLE


def valeur_scan(scan, carto=False, efficace=True):
    """(valeur actuelle, valeur une fois cartographiée) d'un événement Scan ; (0, 0) si le scan
    ne vaut rien (ceinture d'astéroïdes, balise de navigation)."""
    if not scan or scan.get("ScanType") == "NavBeaconDetail":
        return 0, 0
    premier = scan.get("WasDiscovered") is False
    if scan.get("StarType"):
        v = valeur_etoile(scan["StarType"], scan.get("StellarMass"), premier)
        return v, v
    if not scan.get("PlanetClass"):
        return 0, 0
    classe, terra, masse = scan["PlanetClass"], terraformable(scan), scan.get("MassEM")
    carte = valeur_planete(classe, terra, masse, premier, True, scan.get("WasMapped") is False, efficace)
    return (carte if carto else valeur_planete(classe, terra, masse, premier)), carte


def bonus_systeme(nombre_corps, complet, planetes, cartographiees):
    """Bonus de fin de système : tous les corps trouvés (FSSAllBodiesFound), et toutes les
    planètes cartographiées."""
    if not complet:                     # sans balayage complet, on ne connaît pas toutes les planètes
        return 0
    bonus = BONUS_SYSTEME_COMPLET * (nombre_corps or 0)
    if planetes and cartographiees >= planetes:
        bonus += BONUS_CARTOGRAPHIE_COMPLETE * cartographiees
    return bonus
