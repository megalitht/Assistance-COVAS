"""
spansh.py — Tracé de route avec Spansh (https://spansh.co.uk). Son API n'est PAS documentée
officiellement : tout ce qui en dépend est dans ce fichier, pour le réparer d'un seul endroit.

Vérifié en direct le 24/11/2026 :
  - route neutron    : POST /api/route?from=&to=&range=&efficiency=      -> 202 {"job": ...}
  - galaxy plotter   : POST /api/generic/route?source=&destination=&...   -> 202 {"job": ...}
                       (« ship details are invalid » sans les caractéristiques du FSD)
  - résultat         : GET /api/results/<job> -> 202 tant que le calcul tourne, puis 200
                       {"status": "ok", "result": {...}} ; 400 {"error": "..."} si refusé
  - neutron : result.system_jumps[] = {system, distance_jumped, distance_left, jumps, neutron_star}
  - galaxie : result.jumps[] = {name, distance, distance_to_destination, fuel_in_tank, fuel_used,
              has_neutron, is_scoopable, must_refuel}

Caractéristiques du FSD : module/jeu/fsd_table.py (coriolis-data), retouchées par l'ingénierie du
Loadout (FSDOptimalMass, MaxFuelPerJump). Fonctions bloquantes : asyncio.to_thread.
"""
import time

from module.externe.reseau import ErreurExterne, requete_json
from module.jeu.fsd_table import BOOSTERS, FSD

URL = "https://spansh.co.uk/api"
ATTENTE_MAX = 60          # s pour qu'un calcul aboutisse
PAS = 1.5                 # s entre deux demandes de résultat


def parametres_vaisseau(loadout):
    """Caractéristiques du vaisseau pour le galaxy plotter, d'après l'événement Loadout.
    None si le FSD est inconnu."""
    modules = (loadout or {}).get("Modules") or []
    fsd = next((m for m in modules if (m.get("Item") or "").lower() in FSD), None)
    if not fsd:
        return None
    masse_optimale, puissance, multiplicateur, carburant_max = FSD[fsd["Item"].lower()]
    for modif in (fsd.get("Engineering") or {}).get("Modifiers") or []:
        if modif.get("Label") == "FSDOptimalMass":
            masse_optimale = modif.get("Value") or masse_optimale
        elif modif.get("Label") == "MaxFuelPerJump":
            carburant_max = modif.get("Value") or carburant_max
    reservoir = loadout.get("FuelCapacity") or {}
    return {"fuel_power": puissance, "fuel_multiplier": multiplicateur, "optimal_mass": masse_optimale,
            "base_mass": loadout.get("UnladenMass") or 0, "tank_size": reservoir.get("Main") or 0,
            "internal_tank_size": reservoir.get("Reserve") or 0, "max_fuel_per_jump": carburant_max,
            "range_boost": sum(BOOSTERS.get((m.get("Item") or "").lower(), 0) for m in modules)}


def portee(parametres):
    """Portée de saut à vide (formule vérifiée sur les Loadout du commandant)."""
    p = parametres
    masse = p["base_mass"] + p["max_fuel_per_jump"]
    return p["optimal_mass"] / masse * (p["max_fuel_per_jump"] / p["fuel_multiplier"]) ** (1 / p["fuel_power"]) + p["range_boost"]


def _lancer(chemin, parametres, delai):
    _, reponse = requete_json(f"{URL}/{chemin}", parametres, methode="POST", delai=delai)
    job = (reponse or {}).get("job")
    if not job:
        raise ErreurExterne("Spansh n'a pas accepté la demande")
    return job


def _attendre(job, delai, attente_max=ATTENTE_MAX, pas=PAS, dormir=time.sleep):
    fin = time.monotonic() + attente_max
    while True:
        try:
            statut, reponse = requete_json(f"{URL}/results/{job}", delai=delai)
        except ErreurExterne as erreur:
            message = (erreur.corps or {}).get("error") if isinstance(erreur.corps, dict) else None
            raise ErreurExterne(message or str(erreur)) from None
        if statut != 202 and (reponse or {}).get("status") != "queued":
            return (reponse or {}).get("result") or {}
        if time.monotonic() >= fin:
            raise ErreurExterne("Spansh met trop longtemps à répondre")
        dormir(pas)


def route_neutron(depart, arrivee, portee_al, efficacite=60, delai=5, **attente):
    job = _lancer("route", {"from": depart, "to": arrivee, "range": round(portee_al, 2),
                            "efficiency": int(efficacite)}, delai)
    resultat = _attendre(job, delai, **attente)
    etapes = [{"systeme": e.get("system"), "distance": e.get("distance_jumped"),
               "reste": e.get("distance_left"), "sauts": e.get("jumps"),
               "neutron": bool(e.get("neutron_star")), "ravitaillable": None, "ravitailler": False,
               "carburant": None} for e in resultat.get("system_jumps") or []]
    return {"type": "neutron", "depart": depart, "arrivee": arrivee, "etapes": etapes,
            "sauts": resultat.get("total_jumps") or sum(e["sauts"] or 0 for e in etapes),
            "distance": resultat.get("distance")}


def route_galaxie(depart, arrivee, vaisseau, neutrons=True, delai=5, **attente):
    parametres = {"source": depart, "destination": arrivee, "is_supercharged": 0,
                  "use_supercharge": int(bool(neutrons)), "use_injections": 0, "exclude_secondary": 0,
                  "refuel_every_scoopable": 1, "cargo": 0, **vaisseau}
    job = _lancer("generic/route", parametres, delai)
    resultat = _attendre(job, delai, **attente)
    sauts = resultat.get("jumps") or []
    etapes = [{"systeme": e.get("name"), "distance": e.get("distance"),
               "reste": e.get("distance_to_destination"), "sauts": 1 if i else 0,
               "neutron": bool(e.get("has_neutron")), "ravitaillable": bool(e.get("is_scoopable")),
               "ravitailler": bool(e.get("must_refuel")), "carburant": e.get("fuel_in_tank")}
              for i, e in enumerate(sauts)]
    return {"type": "galaxie", "depart": depart, "arrivee": arrivee, "etapes": etapes,
            "sauts": max(0, len(etapes) - 1), "distance": etapes[0]["reste"] if etapes else None}
