"""
carburant.py — Combien de sauts reste-t-il dans le réservoir, et faut-il prévenir le commandant ?

Ce que lecteur_logs.py lui donne :
  - Loadout      : capacité du réservoir, FSD (consommation maximale d'un saut), collecteur ;
  - FSDJump      : carburant réellement consommé par chaque saut (FuelUsed) ;
  - Status.json  : carburant du réservoir principal (Fuel.FuelMain) ;
  - la route     : les étapes encore à faire, avec leurs étoiles récupérables.

Alertes (réglages dans data/config.toml, section [carburant]) :
  - « bas » puis « critique » quand le réservoir passe sous un seuil. Une seule fois par seuil : le
    seuil ne peut resonner qu'après être remonté de quelques points au-dessus (ravitaillement, écope) ;
  - « route » (prioritaire) : la route tracée ne peut pas être finie avec ce carburant ;
  - « etoile » (prioritaire) : avec un collecteur, on n'atteindrait pas la prochaine étoile
    récupérable de la route.

Module pur : ni touches, ni micro, ni réseau. Il se teste seul (tests/test_carburant.py).
"""
import re
from collections import deque

# Consommation maximale d'un saut (t), par taille de FSD et par classe (1 = E ... 5 = A).
# Source : EDCD/coriolis-data, modules/standard/frame_shift_drive.json (relevé le 24/11/2026).
FSD_CLASSIQUES = {
    2: (0.6, 0.6, 0.6, 0.8, 0.9), 3: (1.2, 1.2, 1.2, 1.5, 1.8), 4: (2.0, 2.0, 2.0, 2.5, 3.0),
    5: (3.3, 3.3, 3.3, 4.1, 5.0), 6: (5.3, 5.3, 5.3, 6.6, 8.0), 7: (8.5, 8.5, 8.5, 10.6, 12.8),
}
FSD_SCO = {      # « overcharge » : FSD à supercroisière surchargée
    2: (0.6, 0.9, 0.9, 0.9, 1.0), 3: (1.2, 1.8, 1.8, 1.8, 1.9), 4: (2.0, 3.0, 3.0, 3.0, 3.2),
    5: (3.3, 5.0, 5.0, 5.0, 5.2), 6: (5.3, 8.0, 8.0, 8.0, 8.3), 7: (8.5, 12.8, 12.8, 12.8, 13.1),
    8: (13.6, 20.4, 20.4, 20.4, 20.7),
}
FSD_PARTICULIERS = {
    "int_hyperdrive_overcharge_size8_class5_overchargebooster_mkii": 6.8,   # FSD Mk II (Caspian)
}
_FSD = re.compile(r"^int_hyperdrive(_overcharge)?_size(\d)_class(\d)")


def conso_max_fsd(objet, ingenierie=None):
    """Consommation maximale d'un saut pour ce FSD (t), None s'il est inconnu.
    Une modification d'ingénieur qui change cette valeur (MaxFuelPerJump) passe devant la table."""
    for modif in (ingenierie or {}).get("Modifiers") or []:
        if modif.get("Label") == "MaxFuelPerJump" and isinstance(modif.get("Value"), (int, float)):
            return float(modif["Value"])
    objet = (objet or "").lower()
    if objet in FSD_PARTICULIERS:
        return FSD_PARTICULIERS[objet]
    m = _FSD.match(objet)
    if not m:
        return None
    table = FSD_SCO if m.group(1) else FSD_CLASSIQUES
    taille, classe = int(m.group(2)), int(m.group(3))
    valeurs = table.get(taille)
    return valeurs[classe - 1] if valeurs and 1 <= classe <= 5 else None


class Reservoir:
    """Réservoir du vaisseau actuel : consommation, sauts possibles, alertes déjà données."""

    def __init__(self, nombre_sauts=10):
        self.vaisseau = None          # ShipID du Loadout
        self.capacite = None          # t (FuelCapacity.Main)
        self.fsd_max = None           # t par saut au maximum (table ou ingénierie)
        self.collecteur = False
        self.niveau = None            # t dans le réservoir principal
        self.historiques = {}         # ShipID -> deque des FuelUsed
        self.nombre_sauts = nombre_sauts
        self._reinitialiser_alertes()

    def _reinitialiser_alertes(self):
        # True = déjà annoncée (n'est redite qu'après être repassée au-dessus du seuil)
        self.dites = {"bas": False, "critique": False, "route": False}
        self.route_cle = None         # route sur laquelle porte l'alerte « route »
        self.calibre = False          # premier relevé fait (il ne fait jamais parler)

    # ---------- Événements ----------
    def equipement(self, loadout):
        """Loadout : capacité, FSD, collecteur. Un autre vaisseau repart d'un relevé muet."""
        vaisseau = loadout.get("ShipID")
        if vaisseau != self.vaisseau:
            self.vaisseau = vaisseau
            self.niveau = None
            self._reinitialiser_alertes()
        self.capacite = (loadout.get("FuelCapacity") or {}).get("Main")
        self.fsd_max, self.collecteur = None, False
        for module in loadout.get("Modules") or []:
            objet = (module.get("Item") or "").lower()
            if objet.startswith("int_hyperdrive"):
                self.fsd_max = conso_max_fsd(objet, module.get("Engineering"))
            elif objet.startswith("int_fuelscoop") and module.get("On", True):
                self.collecteur = True

    def saut(self, evenement):
        """FSDJump : retient le carburant consommé par ce vaisseau."""
        consomme = evenement.get("FuelUsed")
        if isinstance(consomme, (int, float)) and consomme > 0:
            historique = self.historiques.setdefault(self.vaisseau, deque(maxlen=50))
            historique.append(float(consomme))
        if isinstance(evenement.get("FuelLevel"), (int, float)):
            self.niveau = float(evenement["FuelLevel"])

    def mesurer(self, carburant):
        """Status.json : carburant du réservoir principal (t)."""
        if isinstance(carburant, (int, float)):
            self.niveau = float(carburant)

    # ---------- Calculs ----------
    def conso(self, nombre=None, secours=None):
        """(t par saut, source) : moyenne des derniers sauts, sinon maximum du FSD, sinon secours."""
        historique = list(self.historiques.get(self.vaisseau) or [])
        nombre = max(1, int(nombre or self.nombre_sauts))
        if historique:
            derniers = historique[-nombre:]
            return sum(derniers) / len(derniers), "historique"
        if self.fsd_max:
            return self.fsd_max, "fsd"
        if secours:
            return float(secours), "config"
        return None, None

    def part(self):
        if self.niveau is None or not self.capacite:
            return None
        return max(0.0, min(1.0, self.niveau / self.capacite))

    def besoin_route(self, a_venir, conso):
        """Carburant à garder pour la route : jusqu'à la destination, ou jusqu'à la prochaine
        étoile récupérable si le vaisseau a un collecteur. a_venir : étapes encore à atteindre
        (la première est le prochain saut), chacune avec « ravitaillable ». None sans route."""
        if not a_venir or not conso:
            return None
        sauts, cible = len(a_venir), "destination"
        if self.collecteur:
            for rang, etape in enumerate(a_venir, 1):
                if etape.get("ravitaillable"):
                    if rang < len(a_venir):
                        sauts, cible = rang, "etoile"
                    break
        return {"cible": cible, "sauts": sauts, "besoin": sauts * conso}

    # ---------- Alertes ----------
    def controler(self, a_venir, reglages, parler=True):
        """Annonces à faire maintenant : liste de "route", "etoile", "critique", "bas" (la plus
        importante d'abord). parler=False : met seulement à jour ce qui a déjà été dit
        (premier relevé, relecture du journal au démarrage)."""
        part = self.part()
        if part is None:
            return []
        parler = parler and self.calibre
        self.calibre = True
        annonces = self._controler_route(a_venir, reglages)       # prioritaire sur les seuils
        franchi = self._controler_seuils(part, reglages)
        if franchi and not annonces:                              # une seule annonce à la fois
            annonces.append(franchi)
        return annonces if parler else []

    def _controler_route(self, a_venir, reglages):
        conso, _ = self.conso(reglages.get("sauts_moyenne"), reglages.get("secours_par_saut"))
        besoin = self.besoin_route(a_venir, conso)
        if besoin is None:
            self.dites["route"], self.route_cle = False, None
            return []
        destination = a_venir[-1].get("systeme")
        if self.route_cle is not None and destination != self.route_cle:
            self.dites["route"] = False                 # autre destination : nouvelle route
        self.route_cle = destination
        if self.niveau >= besoin["besoin"] * reglages.get("marge_route", 1.0):
            self.dites["route"] = False                 # assez de carburant (écopé, ravitaillé)
            return []
        if self.dites["route"]:
            return []
        self.dites["route"] = True
        return ["etoile" if besoin["cible"] == "etoile" else "route"]

    def _controler_seuils(self, part, reglages):
        """Seuil franchi vers le bas à l'instant ("critique" ou "bas"), None sinon."""
        rearmement = reglages.get("rearmement", 0) / 100
        franchi = None
        for nom, seuil in (("critique", reglages.get("seuil_critique", 10) / 100),
                           ("bas", reglages.get("seuil_bas", 25) / 100)):
            if self.dites[nom]:
                if part >= seuil + rearmement:
                    self.dites[nom] = False
            elif part < seuil:
                self.dites[nom] = True
                franchi = franchi or nom                # le plus grave d'abord
        return franchi

    def vue(self, a_venir, reglages):
        """Ce que l'interface affiche (ETAT["carburant"])."""
        part = self.part()
        conso, source = self.conso(reglages.get("sauts_moyenne"), reglages.get("secours_par_saut"))
        bas, critique = reglages.get("seuil_bas", 25) / 100, reglages.get("seuil_critique", 10) / 100
        etat = None if part is None else ("critique" if part < critique else
                                          "bas" if part < bas else "ok")
        besoin = self.besoin_route(a_venir, conso)
        route = None
        if besoin and self.niveau is not None:
            route = {"cible": besoin["cible"], "sauts": besoin["sauts"],
                     "besoin": round(besoin["besoin"], 1),
                     "suffisant": self.niveau >= besoin["besoin"] * reglages.get("marge_route", 1.0)}
        return {
            "niveau": None if self.niveau is None else round(self.niveau, 2),
            "capacite": self.capacite, "part": None if part is None else round(part, 4),
            "etat": etat, "seuil_bas": bas, "seuil_critique": critique,
            "conso": None if conso is None else round(conso, 2), "source": source,
            "historique": len(self.historiques.get(self.vaisseau) or ()),
            "sauts": int(self.niveau // conso) if conso and self.niveau is not None else None,
            "fsd_max": self.fsd_max, "collecteur": self.collecteur, "route": route,
        }
