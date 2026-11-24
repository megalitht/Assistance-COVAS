"""
commerce.py — Profit de chaque trajet commercial et suivi de la soute, gardés sur le disque
(Backend/data/suivi/commerce.json).

Trajet : du premier achat (ou du premier minerai raffiné, de la première cargaison ramassée) jusqu'à
ce que toute la marchandise ait quitté la soute (vendue, larguée, perdue).
  - achat (MarketBuy)            : coût total, prix moyen de chaque marchandise ;
  - minage (MiningRefined), cargaison ramassée (CollectCargo), récompense de mission : coût zéro ;
  - vente (MarketSell)           : profit = TotalSale − AvgPricePaid × quantité (AvgPricePaid est le
                                   prix moyen payé que le jeu a retenu ; 0 pour du minerai) ;
  - largage (EjectCargo), mort (Died) : la marchandise perdue compte comme une perte, à son prix
                                   d'achat (zéro pour du minerai : seule la quantité est perdue) ;
  - drones (BuyDrones)           : frais du trajet. Ils ne sont pas de la marchandise (ils restent
                                   dans la soute) et ne comptent pas pour la fin du trajet.
La soute : Loadout (CargoCapacity) et Cargo (quantité totale, et détail quand le jeu le donne).

Annonces : soute pleine (une fois, jusqu'à ce qu'elle se vide un peu), bilan du trajet à la fin
de la vente (bénéfice ou perte). Session : depuis le lancement du jeu (LoadGame).

Module pur : ni touches, ni micro, ni réseau. Il se teste seul (tests/test_commerce.py).
"""
from module.jeu.suivi import Suivi

HISTORIQUE_MAX = 50
DRONES = "drones"


def _cle(nom):
    """« $cobalt_name; » et « cobalt » désignent la même marchandise."""
    return (nom or "").strip("$;").lower().replace("_name", "")


def _nom(e, cle="Type"):
    nom = e.get(cle + "_Localised") or e.get(cle) or "?"
    return nom.strip("$;").replace("_name", "") if nom.startswith("$") else nom


class SuiviCommerce(Suivi):
    NOM = "commerce"
    EVENEMENTS = frozenset({"LoadGame", "Loadout", "Cargo", "Docked", "Undocked", "Location",
                            "MarketBuy", "MarketSell", "MiningRefined", "CollectCargo", "EjectCargo",
                            "BuyDrones", "MissionCompleted", "Died"})

    def vierge(self):
        return {"trajet": None, "stock": {}, "historique": [],
                "session": {"debut": None, "profit": 0, "trajets": 0, "pertes": 0},
                "station": None, "soute": {"quantite": 0, "capacite": None}, "pleine_dite": False}

    # ---------- Stock (marchandise, sans les drones) ----------
    def _stock(self, cle, nom=None):
        ligne = self.donnees["stock"].setdefault(cle, {"nom": nom or cle, "quantite": 0, "cout": 0})
        if nom:
            ligne["nom"] = nom
        return ligne

    def quantite_marchandise(self):
        return sum(l["quantite"] for l in self.donnees["stock"].values())

    def _retirer(self, cle, quantite):
        """Retire des unités du stock ; renvoie leur coût (prix moyen)."""
        ligne = self.donnees["stock"].get(cle)
        if not ligne or ligne["quantite"] <= 0:
            return 0
        retire = min(quantite, ligne["quantite"])
        cout = round(ligne["cout"] * retire / ligne["quantite"])
        ligne["quantite"] -= retire
        ligne["cout"] -= cout
        if ligne["quantite"] <= 0:
            del self.donnees["stock"][cle]
        return cout

    # ---------- Trajet ----------
    def _trajet(self, e):
        """Trajet en cours (créé au premier mouvement de marchandise)."""
        if self.donnees["trajet"] is None:
            self.donnees["trajet"] = {"debut": e.get("timestamp"), "achats": {}, "ventes": {},
                                      "stations_achat": [], "stations_vente": [], "cout": 0,
                                      "recette": 0, "profit_ventes": 0, "frais": 0,
                                      "pertes": 0, "unites_perdues": 0, "mine": 0}
        return self.donnees["trajet"]

    def _station(self):
        return (self.donnees["station"] or {}).get("nom") or "Station inconnue"

    @staticmethod
    def _noter_station(liste, station):
        if station and (not liste or liste[-1] != station):
            liste.append(station)

    def _fermer(self, e, fin="vente"):
        """Fin du trajet : bilan, historique, session. Renvoie l'annonce du bilan."""
        trajet = self.donnees["trajet"]
        self.donnees["trajet"] = None
        if not trajet:
            return []
        profit = trajet["profit_ventes"] - trajet["frais"] - trajet["pertes"]
        bilan = {**trajet, "fin": e.get("timestamp"), "issue": fin, "profit": profit}
        self.donnees["historique"].insert(0, bilan)
        del self.donnees["historique"][HISTORIQUE_MAX:]
        session = self.donnees["session"]
        session["profit"] += profit
        session["trajets"] += 1
        session["pertes"] += trajet["pertes"]
        if fin != "vente" or not trajet["ventes"]:
            return []
        return [{"type": "bilan", "profit": profit, "recette": trajet["recette"]}]

    # ---------- Événements ----------
    def _appliquer(self, e):
        nom = e.get("event")
        methode = getattr(self, "_" + nom[0].lower() + nom[1:], None)
        return methode(e) or [] if methode else []

    def _loadGame(self, e):
        self.donnees["session"] = {"debut": e.get("timestamp"), "profit": 0, "trajets": 0, "pertes": 0}

    def _loadout(self, e):
        self.donnees["soute"]["capacite"] = e.get("CargoCapacity")
        return self._controler_pleine()

    def _docked(self, e):
        self.donnees["station"] = {"nom": e.get("StationName"), "marche": e.get("MarketID")}

    def _location(self, e):
        self.donnees["station"] = ({"nom": e.get("StationName"), "marche": e.get("MarketID")}
                                   if e.get("Docked") else None)

    def _undocked(self, _e):
        self.donnees["station"] = None

    def _cargo(self, e):
        if e.get("Vessel", "Ship") != "Ship":
            return []
        self.donnees["soute"]["quantite"] = e.get("Count") or 0
        if "Inventory" in e:
            self._recaler(e, e.get("Inventory") or [])
        return self._controler_pleine()

    def _recaler(self, e, inventaire):
        """Le jeu donne le contenu exact : le stock suivi s'y aligne (coûts gardés au prorata)."""
        presents = {}
        for objet in inventaire:
            cle = _cle(objet.get("Name"))
            if cle != DRONES:
                presents[cle] = (presents.get(cle, (0, None))[0] + (objet.get("Count") or 0),
                                 objet.get("Name_Localised") or objet.get("Name"))
        for cle in list(self.donnees["stock"]):
            if cle not in presents:
                del self.donnees["stock"][cle]
        for cle, (quantite, nom) in presents.items():
            ligne = self._stock(cle, self.donnees["stock"].get(cle, {}).get("nom") or nom)
            if ligne["quantite"] and quantite != ligne["quantite"]:
                ligne["cout"] = round(ligne["cout"] * quantite / ligne["quantite"])
            ligne["quantite"] = quantite
        trajet = self.donnees["trajet"]
        if presents and trajet is None:
            self._trajet(e)                    # de la marchandise sans trajet : il commence ici
        elif not presents and trajet and trajet["ventes"]:
            return self._fermer(e)
        elif not presents and trajet and (trajet["achats"] or trajet["mine"]):
            # Soute vidée sans vente (marchandise livrée à un ingénieur, à une mission...) : le
            # trajet se termine sans bilan
            self._fermer(e, "sortie")
        return []

    def _controler_pleine(self):
        soute = self.donnees["soute"]
        pleine = bool(soute["capacite"]) and soute["quantite"] >= soute["capacite"]
        if not pleine:
            self.donnees["pleine_dite"] = False
            return []
        if self.donnees["pleine_dite"]:
            return []
        self.donnees["pleine_dite"] = True
        return [{"type": "soute_pleine", "capacite": soute["capacite"]}]

    def _marketBuy(self, e):
        cle, quantite, cout = _cle(e.get("Type")), e.get("Count") or 0, e.get("TotalCost") or 0
        trajet = self._trajet(e)
        ligne = self._stock(cle, _nom(e))
        ligne["quantite"] += quantite
        ligne["cout"] += cout
        achat = trajet["achats"].setdefault(cle, {"nom": _nom(e), "quantite": 0, "cout": 0})
        achat["quantite"] += quantite
        achat["cout"] += cout
        trajet["cout"] += cout
        self._noter_station(trajet["stations_achat"], self._station())

    def _gratuit(self, e, cle, nom, quantite=1, source="mine"):
        """Minage, cargaison ramassée, récompense : coût zéro."""
        trajet = self._trajet(e)
        self._stock(cle, nom)["quantite"] += quantite
        if source == "mine":
            trajet["mine"] += quantite

    def _miningRefined(self, e):
        self._gratuit(e, _cle(e.get("Type")), _nom(e))

    def _collectCargo(self, e):
        if _cle(e.get("Type")) != DRONES:
            self._gratuit(e, _cle(e.get("Type")), _nom(e), source="ramasse")

    def _missionCompleted(self, e):
        for objet in e.get("CommodityReward") or []:
            self._gratuit(e, _cle(objet.get("Name")), objet.get("Name_Localised") or objet.get("Name"),
                          objet.get("Count") or 0, source="mission")
        if e.get("Commodity") and e.get("Count"):              # livraison : la marchandise part
            self._retirer(_cle(e["Commodity"]), e["Count"])

    def _buyDrones(self, e):
        self._trajet(e)["frais"] += e.get("TotalCost") or 0

    def _marketSell(self, e):
        cle, quantite = _cle(e.get("Type")), e.get("Count") or 0
        recette = e.get("TotalSale") or 0
        profit = recette - (e.get("AvgPricePaid") or 0) * quantite
        trajet = self._trajet(e)
        vente = trajet["ventes"].setdefault(cle, {"nom": _nom(e), "quantite": 0, "recette": 0, "profit": 0})
        vente["quantite"] += quantite
        vente["recette"] += recette
        vente["profit"] += profit
        trajet["recette"] += recette
        trajet["profit_ventes"] += profit
        self._noter_station(trajet["stations_vente"], self._station())
        self._retirer(cle, quantite)
        if self.quantite_marchandise() <= 0:
            return self._fermer(e)
        return []

    def _ejectCargo(self, e):
        cle = _cle(e.get("Type"))
        if cle == DRONES:
            return []
        trajet = self._trajet(e)
        trajet["pertes"] += self._retirer(cle, e.get("Count") or 0)
        trajet["unites_perdues"] += e.get("Count") or 0
        if self.quantite_marchandise() <= 0:
            return self._fermer(e, "largage")
        return []

    def _died(self, e):
        if not self.donnees["stock"] and not self.donnees["trajet"]:
            return []
        trajet = self._trajet(e)
        trajet["pertes"] += sum(l["cout"] for l in self.donnees["stock"].values())
        trajet["unites_perdues"] += self.quantite_marchandise()
        self.donnees["stock"] = {}
        self.donnees["soute"]["quantite"] = 0
        self._fermer(e, "mort")
        if not trajet["unites_perdues"]:
            return []
        return [{"type": "cargaison_perdue", "pertes": trajet["pertes"], "unites": trajet["unites_perdues"]}]

    # ---------- Interface ----------
    @staticmethod
    def _resume(trajet):
        if not trajet:
            return None
        # Le nom traduit de l'achat (« Or ») passe devant le nom brut d'une vente (« gold »)
        noms = {**{c: v["nom"] for c, v in trajet["ventes"].items()},
                **{c: a["nom"] for c, a in trajet["achats"].items()}}
        return {"debut": trajet["debut"], "fin": trajet.get("fin"), "issue": trajet.get("issue"),
                "de": " / ".join(trajet["stations_achat"]) or ("Minage" if trajet["mine"] else "—"),
                "vers": " / ".join(trajet["stations_vente"]) or "—",
                "marchandises": sorted(noms.values()), "cout": trajet["cout"], "recette": trajet["recette"],
                "frais": trajet["frais"], "pertes": trajet["pertes"], "unites_perdues": trajet["unites_perdues"],
                "profit": trajet.get("profit", trajet["profit_ventes"] - trajet["frais"] - trajet["pertes"])}

    def vue(self):
        stock = sorted(({"nom": l["nom"], "quantite": l["quantite"],
                         "prix_moyen": round(l["cout"] / l["quantite"]) if l["quantite"] else 0}
                        for l in self.donnees["stock"].values()), key=lambda l: -l["quantite"])
        historique = [self._resume(t) for t in self.donnees["historique"]]
        return {"soute": dict(self.donnees["soute"]), "stock": stock,
                "en_cours": self._resume(self.donnees["trajet"]),
                "dernier": historique[0] if historique else None,
                "historique": historique[:20], "session": dict(self.donnees["session"])}
