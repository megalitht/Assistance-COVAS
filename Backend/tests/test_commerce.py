"""Commerce : profit par trajet, minage à coût zéro, pertes, soute pleine, session.
Sans touche, sans micro et sans réseau ; le journal est simulé."""
import glob
import importlib.util
import itertools
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from module.dialogue import morceaux  # noqa: E402
from module.jeu import suivi as suivis  # noqa: E402
from module.jeu.commerce import SuiviCommerce  # noqa: E402

DOSSIER_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_ED = os.path.join(os.path.expanduser("~"), "Saved Games", "Frontier Developments", "Elite Dangerous")
for _flux in (sys.stdout, sys.stderr):
    if hasattr(_flux, "reconfigure"):
        _flux.reconfigure(errors="replace")


class Base(unittest.TestCase):
    def setUp(self):
        self.s = SuiviCommerce()
        self.secondes = itertools.count()

    def ev(self, nom, **champs):
        s = next(self.secondes)
        return self.s.traiter({"timestamp": f"2026-11-24T10:{s // 60:02d}:{s % 60:02d}Z", "event": nom, **champs})

    def amarrer(self, station):
        self.ev("Docked", StationName=station, MarketID=hash(station) % 10000)


class Trajets(Base):
    def test_achat_puis_vente(self):
        self.amarrer("Abraham Lincoln")
        self.ev("MarketBuy", Type="gold", Type_Localised="Or", Count=10, BuyPrice=9000, TotalCost=90000)
        self.ev("Undocked", StationName="Abraham Lincoln")
        self.amarrer("Hutton Orbital")
        annonces = self.ev("MarketSell", Type="gold", Count=10, SellPrice=11000, TotalSale=110000, AvgPricePaid=9000)
        self.assertEqual(annonces, [{"type": "bilan", "profit": 20000, "recette": 110000}])
        dernier = self.s.vue()["dernier"]
        self.assertEqual((dernier["de"], dernier["vers"], dernier["profit"]), ("Abraham Lincoln", "Hutton Orbital", 20000))
        self.assertEqual(dernier["marchandises"], ["Or"])
        self.assertEqual(self.s.vue()["session"]["profit"], 20000)

    def test_le_trajet_dure_tant_qu_il_reste_de_la_marchandise(self):
        self.ev("MarketBuy", Type="gold", Count=10, TotalCost=90000)
        self.ev("MarketBuy", Type="silver", Count=5, TotalCost=25000)
        self.assertEqual(self.ev("MarketSell", Type="gold", Count=10, TotalSale=100000, AvgPricePaid=9000), [])
        self.assertEqual(self.s.vue()["en_cours"]["profit"], 10000)
        annonces = self.ev("MarketSell", Type="silver", Count=5, TotalSale=20000, AvgPricePaid=5000)
        self.assertEqual(annonces[0]["profit"], 10000 - 5000)

    def test_vente_en_perte(self):
        self.ev("MarketBuy", Type="gold", Count=1, TotalCost=10000)
        annonces = self.ev("MarketSell", Type="gold", Count=1, TotalSale=8000, AvgPricePaid=10000)
        self.assertEqual(annonces[0]["profit"], -2000)

    def test_minage_cout_zero_et_drones(self):
        self.ev("BuyDrones", Type="drones", Count=20, BuyPrice=101, TotalCost=2020)
        for _ in range(3):
            self.ev("MiningRefined", Type="$cobalt_name;", Type_Localised="Cobalt")
        self.ev("Cargo", Vessel="Ship", Count=23)                   # les drones comptent dans la soute
        annonces = self.ev("MarketSell", Type="cobalt", Count=3, TotalSale=60000, AvgPricePaid=0)
        self.assertEqual(annonces[0]["profit"], 60000 - 2020)         # les drones sont des frais
        self.assertEqual(self.s.vue()["dernier"]["de"], "Minage")

    def test_largage_et_mort(self):
        self.ev("MarketBuy", Type="gold", Count=10, TotalCost=100000)
        self.ev("EjectCargo", Type="gold", Count=4, Abandoned=True)
        self.assertEqual(self.s.vue()["en_cours"]["pertes"], 40000)
        annonces = self.ev("Died", KillerName="Pirate")
        self.assertEqual(annonces, [{"type": "cargaison_perdue", "pertes": 100000, "unites": 10}])
        dernier = self.s.vue()["dernier"]
        self.assertEqual((dernier["issue"], dernier["profit"]), ("mort", -100000))
        self.assertEqual(self.s.vue()["session"]["pertes"], 100000)

    def test_drones_larges_ne_sont_pas_une_perte(self):
        self.ev("MarketBuy", Type="gold", Count=1, TotalCost=1000)
        self.ev("EjectCargo", Type="drones", Count=25)
        self.assertEqual(self.s.vue()["en_cours"]["pertes"], 0)

    def test_mort_sans_cargaison_muette(self):
        self.assertEqual(self.ev("Died"), [])

    def test_recalage_sur_le_contenu_de_la_soute(self):
        self.ev("Cargo", Vessel="Ship", Count=12, Inventory=[
            {"Name": "drones", "Count": 4}, {"Name": "gold", "Name_Localised": "Or", "Count": 8}])
        self.assertEqual([(l["nom"], l["quantite"]) for l in self.s.vue()["stock"]], [("Or", 8)])
        self.assertIsNotNone(self.s.vue()["en_cours"])               # marchandise sans trajet : il commence
        # Soute vidée sans vente (livrée à un ingénieur) : le trajet se termine, sans bilan
        self.ev("MarketBuy", Type="metaalloys", Count=1, TotalCost=246598)
        self.assertEqual(self.ev("Cargo", Vessel="Ship", Count=4, Inventory=[{"Name": "drones", "Count": 4}]), [])
        self.assertIsNone(self.s.vue()["en_cours"])
        self.assertEqual(self.s.vue()["dernier"]["issue"], "sortie")

    def test_session_remise_a_zero_au_lancement_du_jeu(self):
        self.ev("MarketBuy", Type="gold", Count=1, TotalCost=1000)
        self.ev("MarketSell", Type="gold", Count=1, TotalSale=2000, AvgPricePaid=1000)
        self.ev("LoadGame", Commander="Test")
        self.assertEqual(self.s.vue()["session"]["profit"], 0)
        self.assertEqual(len(self.s.vue()["historique"]), 1)          # l'historique reste

    def test_mission(self):
        self.ev("MissionCompleted", CommodityReward=[{"Name": "gold", "Name_Localised": "Or", "Count": 2}])
        annonces = self.ev("MarketSell", Type="gold", Count=2, TotalSale=20000, AvgPricePaid=0)
        self.assertEqual(annonces[0]["profit"], 20000)


class Soute(Base):
    def test_pleine_une_seule_fois(self):
        self.ev("Loadout", CargoCapacity=32)
        self.assertEqual(self.ev("Cargo", Vessel="Ship", Count=31), [])
        self.assertEqual(self.ev("Cargo", Vessel="Ship", Count=32), [{"type": "soute_pleine", "capacite": 32}])
        self.assertEqual(self.ev("Cargo", Vessel="Ship", Count=32), [])
        self.ev("Cargo", Vessel="Ship", Count=20)
        self.assertEqual(len(self.ev("Cargo", Vessel="Ship", Count=32)), 1)

    def test_vrs_ignore(self):
        self.ev("Loadout", CargoCapacity=2)
        self.assertEqual(self.ev("Cargo", Vessel="SRV", Count=2), [])


class Voix(unittest.TestCase):
    def test_bilan(self):
        fin = lambda ids: [i.rsplit("/", 1)[-1] for i in ids]
        self.assertEqual(fin(morceaux.pour_bilan(950000))[0], "BeneficeTrajet.mp3")
        self.assertEqual(fin(morceaux.pour_bilan(-2000)), ["PerteTrajet.mp3", "002.mp3", "Mille.mp3", "Credits.mp3"])


def _lecteur_prive():
    avant = set(sys.modules)
    chemin = os.path.join(DOSSIER_BACKEND, "module", "jeu", "lecteur_logs.py")
    spec = importlib.util.spec_from_file_location("covas_lecteur_logs_commerce", chemin)
    copie = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copie)
    for nom in ("module.interface.serveur_ws", "module.jeu.edsm"):
        if nom in sys.modules and nom not in avant:
            del sys.modules[nom]
            paquet, _, enfant = nom.rpartition(".")
            delattr(sys.modules[paquet], enfant)
    return copie


logs = _lecteur_prive()


class Journal(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.dit, self.envoye = [], []
        self.origines = (logs.envoyer_donnees_web, logs._dire, logs._dire_morceaux, logs.SYSTEMES_PROCHES_ACTIF)

        async def envoyer(message):
            self.envoye.append(message)

        async def dire(cle, urgent=False, secours=None):
            self.dit.append(cle)

        async def dire_morceaux(ids, secours):
            self.dit.append(secours)

        logs.envoyer_donnees_web, logs._dire, logs._dire_morceaux = envoyer, dire, dire_morceaux
        logs.SYSTEMES_PROCHES_ACTIF = False
        logs._commerce.__init__()
        logs._reinitialiser_etat()

    def tearDown(self):
        logs.envoyer_donnees_web, logs._dire, logs._dire_morceaux, logs.SYSTEMES_PROCHES_ACTIF = self.origines
        logs._commerce.__init__()
        logs._reinitialiser_etat()

    async def ev(self, s, nom, **champs):
        await logs._traiter_ligne(json.dumps({"timestamp": f"2026-11-24T10:00:{s:02d}Z", "event": nom, **champs}),
                                  en_direct=True)

    async def test_vente_et_soute_pleine(self):
        await self.ev(0, "Loadout", Ship="python", CargoCapacity=4, Modules=[])
        await self.ev(1, "Docked", StationName="Rushworth Station", MarketID=1)
        await self.ev(2, "MarketBuy", Type="gold", Count=4, TotalCost=40000)
        await self.ev(3, "Cargo", Vessel="Ship", Count=4)
        await self.ev(4, "MarketSell", Type="gold", Count=4, TotalSale=52000, AvgPricePaid=10000)
        self.assertEqual(self.dit, ["soute_pleine", "commerce_benefice"])
        self.assertEqual(logs.ETAT["commerce"]["dernier"]["profit"], 12000)
        lignes = [m["evenement"]["texte"].replace(" ", " ") for m in self.envoye if m.get("type") == "evenement"]
        self.assertTrue(any(t.startswith("Bénéfice du trajet : 12 000 cr") for t in lignes), lignes)


class SurLesVraisJournaux(unittest.TestCase):
    def test_relecture_complete_idempotente(self):
        journaux = sorted(glob.glob(os.path.join(DOSSIER_ED, "Journal.*.log")), key=os.path.getctime)
        if not journaux:
            self.skipTest("journaux du jeu absents")
        s = SuiviCommerce()
        suivis.reconstruire([s], journaux)
        vue = s.vue()
        self.assertTrue(vue["historique"])
        suivis.reconstruire([s], journaux)
        self.assertEqual(s.vue(), vue)


if __name__ == "__main__":
    unittest.main()
