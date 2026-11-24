"""
suivi_exploration.py — Valeur des données d'exploration pas encore vendues, gardée sur le disque
(Backend/data/suivi/exploration.json) : elle survit à un redémarrage du COVAS ou du jeu.

  - cartographie : chaque corps scanné (Scan), cartographié ou non (SAAScanComplete et son
    efficacité), première découverte (WasDiscovered) et première cartographie (WasMapped), plus les
    bonus de système complet. Formule : module/jeu/valeur_corps.py ;
  - biologie (Odyssey) : chaque espèce analysée (ScanOrganic « Analyse »), bonus du premier pas ;
  - vente (SellExplorationData, MultiSellExplorationData, SellOrganicData) : les systèmes vendus
    sont retirés (tout, si tout est vendu). Le montant payé est comparé à l'estimation ;
  - mort (Died) : tout est perdu, annoncé puis remis à zéro.

Annonces (lecteur_logs.py les dit) : paliers franchis (10, 50, 100 millions...), rappel à l'amarrage
dans une station qui achète les données, données perdues. Réglages : config.toml [exploration].

Module pur : ni touches, ni micro, ni réseau. Il se teste seul (tests/test_exploration_suivi.py).
"""
from module.jeu import valeur_corps
from module.jeu.suivi import Suivi

# Champs du Scan gardés pour recalculer la valeur (cartographie faite plus tard)
CHAMPS_SCAN = ("PlanetClass", "TerraformState", "MassEM", "WasDiscovered", "WasMapped", "StarType",
               "StellarMass", "WasFootfalled", "Landable", "ScanType")
TOP = 10                     # corps les plus rentables montrés dans l'interface
REGLAGES_DEFAUT = {"paliers_millions": [10, 50, 100], "rappel_min_millions": 1.0, "rappel_bio": True}


def _classe(scan):
    """Classe du corps en français (« Monde d'eau », « Étoile K »)."""
    from module.jeu import exploration
    if scan.get("StarType"):
        return f"Étoile {scan['StarType']}"
    return exploration.CLASSES.get(scan.get("PlanetClass"), scan.get("PlanetClass"))


def _especes():
    from module.jeu import exploration          # catalogue des espèces (prix exacts)
    return exploration._especes_par_id()


class SuiviExploration(Suivi):
    NOM = "exploration"
    EVENEMENTS = frozenset({"FSSDiscoveryScan", "Scan", "SAAScanComplete", "FSSAllBodiesFound",
                            "SellExplorationData", "MultiSellExplorationData", "ScanOrganic",
                            "SellOrganicData", "Died", "Docked"})

    def __init__(self, chemin=None, reglages=None):
        super().__init__(chemin)
        self.reglages = reglages or (lambda: dict(REGLAGES_DEFAUT))

    def vierge(self):
        return {"systemes": {}, "bio": [], "paliers_dits": [],
                "vendu": {"cartographie": 0, "bio": 0}, "derniere_vente": None}

    # ---------- Calculs ----------
    def _systeme(self, e, nom=None):
        adresse = str(e.get("SystemAddress"))
        systeme = self.donnees["systemes"].setdefault(
            adresse, {"nom": nom or e.get("StarSystem"), "corps": {}, "nb_corps": None, "complet": False})
        if nom or e.get("StarSystem"):
            systeme["nom"] = nom or e.get("StarSystem")
        return systeme

    @staticmethod
    def _valeurs_corps(fiche):
        valeur, carte = valeur_corps.valeur_scan(fiche["scan"], fiche["carto"], fiche["efficace"])
        fiche["valeur"], fiche["valeur_carto"] = valeur, carte

    @staticmethod
    def bonus(systeme):
        planetes = [f for f in systeme["corps"].values() if f["planete"]]
        return valeur_corps.bonus_systeme(systeme["nb_corps"], systeme["complet"], len(planetes),
                                          sum(1 for f in planetes if f["carto"]))

    def totaux(self):
        cartographie = bonus = corps = systemes = 0
        for systeme in self.donnees["systemes"].values():
            cartographie += sum(f["valeur"] for f in systeme["corps"].values())
            corps += len(systeme["corps"])
            systemes += bool(systeme["corps"])      # balayé sans aucun corps scanné : rien à vendre
            bonus += self.bonus(systeme)
        bio = sum(b["valeur"] for b in self.donnees["bio"])
        return {"cartographie": cartographie + bonus, "bonus": bonus, "bio": bio,
                "total": cartographie + bonus + bio, "corps": corps,
                "systemes": systemes, "especes": len(self.donnees["bio"])}

    # ---------- Événements ----------
    def _appliquer(self, e):
        nom = e.get("event")
        if nom == "Died":
            return self._perdre()
        if nom == "Docked":
            return self._rappel(e.get("StationServices") or [])
        if nom in ("SellExplorationData", "MultiSellExplorationData"):
            return self._vente_cartographie(e)
        if nom == "SellOrganicData":
            return self._vente_bio(e)
        if e.get("SystemAddress") is None:
            return []
        if nom == "Scan":
            self._scan(e)
        elif nom == "SAAScanComplete":
            self._cartographie(e)
        elif nom == "FSSDiscoveryScan":
            self._systeme(e, e.get("SystemName"))["nb_corps"] = e.get("BodyCount")
        elif nom == "FSSAllBodiesFound":
            systeme = self._systeme(e, e.get("SystemName"))
            systeme.update(complet=True, nb_corps=e.get("Count") or systeme["nb_corps"])
        elif nom == "ScanOrganic":
            self._bio(e)
        return self._paliers()

    def _scan(self, e):
        if e.get("BodyID") is None or not (e.get("PlanetClass") or e.get("StarType")):
            return                                   # ceinture d'astéroïdes, anneau...
        if e.get("ScanType") == "NavBeaconDetail":
            return                                   # données de balise : ne se vendent pas
        systeme = self._systeme(e)
        ancienne = systeme["corps"].get(str(e["BodyID"]))
        fiche = ancienne or {"carto": False, "efficace": True}
        fiche.update(nom=e.get("BodyName"), planete=bool(e.get("PlanetClass")),
                     scan={c: e[c] for c in CHAMPS_SCAN if c in e})
        self._valeurs_corps(fiche)
        systeme["corps"][str(e["BodyID"])] = fiche

    def _cartographie(self, e):
        fiche = self._systeme(e)["corps"].get(str(e.get("BodyID")))
        if not fiche:
            return                                   # cartographié sans scan connu : rien à estimer
        fiche["carto"] = True
        fiche["efficace"] = (e.get("ProbesUsed") or 0) <= (e.get("EfficiencyTarget") or 0)
        self._valeurs_corps(fiche)

    def _bio(self, e):
        if e.get("ScanType") != "Analyse":
            return
        adresse, corps, espece = str(e.get("SystemAddress")), e.get("Body"), e.get("Species")
        if any(b["adresse"] == adresse and b["corps"] == corps and b["espece"] == espece
               for b in self.donnees["bio"]):
            return
        prix = (_especes().get(espece) or {}).get("valeur") or 0
        systeme = self.donnees["systemes"].get(adresse) or {}
        scan = ((systeme.get("corps") or {}).get(str(corps)) or {}).get("scan") or {}
        bonus = scan.get("WasFootfalled") is False and not e.get("WasLogged")
        self.donnees["bio"].append({
            "adresse": adresse, "systeme": systeme.get("nom"), "corps": corps, "espece": espece,
            "nom": e.get("Species_Localised") or espece, "bonus": bonus,
            "valeur": prix * (5 if bonus else 1)})

    def _vente_cartographie(self, e):
        noms = {d.get("SystemName") if isinstance(d, dict) else d
                for d in (e.get("Discovered") or [])} | set(e.get("Systems") or [])
        noms = {(n or "").casefold() for n in noms if n}
        vendus = {a: s for a, s in self.donnees["systemes"].items() if (s["nom"] or "").casefold() in noms}
        estimation = sum(sum(f["valeur"] for f in s["corps"].values()) + self.bonus(s) for s in vendus.values())
        for adresse in vendus:
            del self.donnees["systemes"][adresse]
        paye = (e.get("TotalEarnings") or 0)
        self.donnees["vendu"]["cartographie"] += paye
        self.donnees["derniere_vente"] = {"h": e.get("timestamp"), "systemes": len(noms),
                                          "reconnus": len(vendus), "estimation": estimation, "paye": paye}
        self._oublier_paliers()
        return []

    def _vente_bio(self, e):
        for ligne in e.get("BioData") or []:
            for i, b in enumerate(self.donnees["bio"]):
                if b["espece"] == ligne.get("Species"):
                    del self.donnees["bio"][i]
                    break
            self.donnees["vendu"]["bio"] += (ligne.get("Value") or 0) + (ligne.get("Bonus") or 0)
        self._oublier_paliers()
        return []

    def _perdre(self):
        totaux = self.totaux()
        self.donnees["systemes"], self.donnees["bio"] = {}, []
        self._oublier_paliers()
        return [{"type": "perdu", "montant": totaux["total"]}] if totaux["total"] > 0 else []

    # ---------- Annonces ----------
    def _paliers_reglages(self):
        paliers = self.reglages().get("paliers_millions") or []
        return sorted({float(p) for p in paliers if isinstance(p, (int, float)) and not isinstance(p, bool) and p > 0})

    def _oublier_paliers(self):
        """Après une vente ou une perte : un palier repassé sera de nouveau annoncé."""
        total = self.totaux()["total"]
        self.donnees["paliers_dits"] = [p for p in self.donnees["paliers_dits"] if total >= p * 1e6]

    def _paliers(self):
        total = self.totaux()["total"]
        franchis = [p for p in self._paliers_reglages()
                    if total >= p * 1e6 and p not in self.donnees["paliers_dits"]]
        if not franchis:
            return []
        self.donnees["paliers_dits"].extend(franchis)
        return [{"type": "palier", "palier": max(franchis), "montant": total}]   # le plus haut seulement

    def _rappel(self, services):
        reglages, totaux, annonces = self.reglages(), self.totaux(), []
        minimum = (reglages.get("rappel_min_millions") or 0) * 1e6
        if "exploration" in services and totaux["cartographie"] > 0 and totaux["cartographie"] >= minimum:
            annonces.append({"type": "rappel", "service": "cartographie", "montant": totaux["cartographie"]})
        if reglages.get("rappel_bio", True) and "vistagenomics" in services and totaux["bio"] > 0:
            annonces.append({"type": "rappel", "service": "bio", "montant": totaux["bio"]})
        return annonces

    # ---------- Interface ----------
    def vue(self):
        totaux = self.totaux()
        corps = []
        for systeme in self.donnees["systemes"].values():
            for fiche in systeme["corps"].values():
                scan = fiche["scan"]
                corps.append({
                    "nom": fiche["nom"], "systeme": systeme["nom"], "valeur": fiche["valeur"],
                    "valeur_carto": fiche["valeur_carto"], "cartographie": fiche["carto"],
                    "etoile": not fiche["planete"],
                    "classe": _classe(scan),
                    "terraformable": valeur_corps.terraformable(scan),
                    "premiere_decouverte": scan.get("WasDiscovered") is False})
        corps.sort(key=lambda c: -c["valeur"])
        bio = sorted(self.donnees["bio"], key=lambda b: -b["valeur"])
        return {**totaux, "top": corps[:TOP], "bio_liste": bio[:TOP],
                "derniere_vente": self.donnees["derniere_vente"], "vendu": dict(self.donnees["vendu"]),
                "paliers": self._paliers_reglages()}
