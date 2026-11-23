"""
avaries.py — Rapport d'avarie : état de la coque, des boucliers et des modules endommagés.

    rapport = construire_rapport(lecteur_logs.ETAT)
      rapport["texte"]  : ligne du journal de bord (catégorie « vaisseau »)
      rapport["resume"] : résumé d'une ligne pour l'en-tête du panneau Modules
      rapport["avaries"]: modules cités (emplacement, nom, santé), pour les surligner dans l'interface

Ce que le jeu permet de savoir (vérifié dans les journaux) :
  - la santé des modules n'est écrite que dans « Loadout » : au chargement, en station, et en vol
    seulement après le retour du chasseur ou du VRS. Pendant un combat, elle peut donc être
    dépassée : le rapport le signale (« relevé antérieur aux derniers dégâts ») ;
  - la coque n'est écrite (HullDamage) qu'au passage des paliers 80, 60, 40 et 20 % : après un
    palier, le rapport dit « sous 40 % » plutôt qu'un chiffre qui ne serait plus exact ;
  - les boucliers ne sont connus qu'en « levés / tombés » (aucun pourcentage nulle part).

Aucune dépendance : ce module ne touche ni au clavier ni au micro (testable seul).
"""
import math
from datetime import datetime, timezone

SEUIL_AVARIE = 0.8          # un module est cité sous ce niveau d'intégrité (seuil jaune de l'interface)
SEUIL_CRITIQUE = 0.5        # en dessous : critique (rouge)

# Début du nom interne du module -> nom en français (le plus long préfixe gagne).
# Même table que MODULES dans Frontend/interface.js : garder les deux identiques.
NOMS_MODULES = {
    "powerplant": "Générateur", "engine": "Propulseurs", "hyperdrive": "Réacteur FSD",
    "lifesupport": "Systèmes de survie", "powerdistributor": "Répartiteur de puissance",
    "sensors": "Capteurs", "fueltank": "Réservoir de carburant", "armour": "Blindage",
    "cockpit": "Verrière", "modularcargobaydoor": "Trappe de soute",
    "planetapproachsuite": "Suite d'approche planétaire",
    "shieldgenerator": "Générateur de bouclier", "shieldcellbank": "Cellules de bouclier",
    "shieldbooster": "Survolteur de bouclier", "cargorack": "Compartiment de soute",
    "fuelscoop": "Collecteur de carburant", "fsdinterdictor": "Interdicteur FSD",
    "repairer": "Unité de maintenance", "dockingcomputer": "Ordinateur d'appontage",
    "supercruiseassist": "Assistance supercroisière", "detailedsurfacescanner": "Scanner de surface",
    "buggybay": "Hangar de VRS", "fighterbay": "Hangar de chasseurs",
    "hullreinforcement": "Renfort de coque", "modulereinforcement": "Renfort de modules",
    "guardianfsdbooster": "Booster FSD gardien", "refinery": "Raffinerie",
    "passengercabin": "Cabine passagers", "dronecontrol": "Contrôleur de drones",
    "multidronecontrol": "Contrôleur de drones multiple", "chafflauncher": "Lance-paillettes",
    "heatsinklauncher": "Dissipateur thermique", "plasmapointdefence": "Défense ponctuelle",
    "electroniccountermeasure": "Contre-mesures électroniques", "cloudscanner": "Scanner de sillage",
    "crimescanner": "Scanner de primes", "cargoscanner": "Scanner de cargaison",
    "pulselaserburst": "Laser à rafales", "pulselaser": "Laser à impulsions",
    "beamlaser": "Laser à faisceau", "multicannon": "Multi-canon", "cannon": "Canon",
    "slugshot": "Canon à fragmentation", "railgun": "Canon électrique",
    "plasmaaccelerator": "Accélérateur plasma", "dumbfiremissilerack": "Lance-missiles",
    "basicmissilerack": "Missiles à tête chercheuse", "advancedtorppylon": "Lance-torpilles",
    "minelauncher": "Lance-mines", "mininglaser": "Laser minier",
}
MONTURES = {"fixed": "fixe", "gimbal": "cardan", "turret": "tourelle"}

BIT_BOUCLIERS = 3           # Status.json : boucliers levés


def nommer(objet):
    """Nom interne du module -> (nom affiché, nom court pour la voix).
    'hpt_multicannon_gimbal_large' -> ('Multi-canon cardan', 'Multi-canon')."""
    cle = (objet or "").lower().strip("$;").replace("_name", "")
    for prefixe in ("int_", "hpt_"):
        if cle.startswith(prefixe):
            cle = cle[len(prefixe):]
    trouves = [p for p in NOMS_MODULES if cle.startswith(p) or f"_{p}" in cle]
    if not trouves:
        nom = cle.replace("_", " ").strip() or "Module inconnu"
        return nom, nom
    court = NOMS_MODULES[max(trouves, key=len)]
    monture = next((MONTURES[m] for m in MONTURES if f"_{m}" in cle), None)
    return (f"{court} {monture}" if monture else court), court


def _heure_locale(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone().strftime("%H:%M")
    except (AttributeError, ValueError):
        return None


def _boucliers(etat):
    """True / False / None (inconnu). Status.json (temps réel) d'abord, sinon le dernier ShieldState."""
    drapeaux = (etat.get("status") or {}).get("flags") or 0
    if drapeaux:
        return bool(drapeaux & (1 << BIT_BOUCLIERS))
    return (etat.get("vaisseau") or {}).get("boucliers")


def _pour_cent(fraction):
    return round(fraction * 100)


def construire_rapport(etat, maintenant=None):
    """Rapport d'avarie à partir de l'état du COVAS (lecteur_logs.ETAT)."""
    vaisseau = etat.get("vaisseau") or {}
    modules = etat.get("modules") or {}
    liste = modules.get("liste") or []
    releve = modules.get("releve")
    coque = vaisseau.get("coque")
    palier = bool(vaisseau.get("coque_palier")) and coque is not None and coque < 0.995
    boucliers = _boucliers(etat)
    verriere = bool(vaisseau.get("verriere_brisee"))
    dernier_coup = vaisseau.get("dernier_coup")
    perime = bool(liste and dernier_coup and releve and dernier_coup > releve)

    avaries = []
    for module in liste:
        sante = module.get("sante")
        if sante is None or sante >= SEUIL_AVARIE:
            continue
        nom, court = nommer(module.get("objet"))
        avaries.append({"emplacement": module.get("emplacement"), "nom": nom, "court": court,
                        "sante": round(max(0.0, sante), 3), "hs": sante <= 0})
    avaries.sort(key=lambda a: a["sante"])            # HS d'abord, puis du plus touché au moins touché

    # --- Coque (palier : le jeu n'écrit la coque qu'à 80, 60, 40, 20 %) ---
    seuil = None
    if coque is None:
        coque_ecran = None
    elif coque >= 0.995:
        coque_ecran = "coque intacte"
    elif palier:
        seuil = min(100, max(20, math.ceil(coque * 5 - 1e-9) * 20))
        coque_ecran = f"coque < {seuil} %"
    else:
        coque_ecran = f"coque {_pour_cent(coque)} %"

    boucliers_ecran = {True: "boucliers en ligne", False: "boucliers hors ligne"}.get(boucliers)

    # --- Modules ---
    if not liste:
        modules_ecran, compte = "équipement inconnu", None
    elif not avaries:
        modules_ecran, compte = "aucune avarie", "aucune avarie"
    else:
        n = len(avaries)
        compte = f"{n} avarie{'s' if n > 1 else ''}"
        modules_ecran = compte + " : " + ", ".join(
            f"{a['nom']} {'HS' if a['hs'] else str(_pour_cent(a['sante'])) + ' %'}" for a in avaries)

    heure = _heure_locale(releve)
    precision = None
    if liste and heure:
        precision = f"relevé {heure}" + (", antérieur aux derniers dégâts" if perime else "")
    morceaux = [coque_ecran, "verrière brisée" if verriere else None, boucliers_ecran, modules_ecran]
    texte = "Rapport d'avarie — " + " · ".join(m for m in morceaux if m)
    if precision:
        texte += f" ({precision})"
    if coque is None and not liste:
        texte = "Rapport d'avarie : état du vaisseau inconnu (le jeu ne l'a pas encore écrit)"
    resume = " · ".join(m for m in (coque_ecran, "verrière brisée" if verriere else None,
                                    boucliers_ecran, compte) if m) or "état inconnu"

    if any(a["hs"] for a in avaries) or verriere or (coque is not None and coque < 0.3):
        gravite = "alerte"
    elif avaries or boucliers is False or (coque is not None and coque < SEUIL_AVARIE):
        gravite = "attention"
    elif coque is None and not liste:
        gravite = "info"
    else:
        gravite = "succes"

    return {
        "h": (maintenant or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "coque": coque, "coque_palier": palier, "coque_seuil": seuil, "modules_connus": bool(liste),
        "boucliers": boucliers, "verriere_brisee": verriere,
        "avaries": avaries, "releve": releve, "perime": perime, "gravite": gravite,
        "texte": texte, "resume": resume,
    }
