"""Matériaux d'ingénieur : table des grades, stock, limites, alertes, garde contre le double comptage.
Sans touche, sans micro et sans réseau ; le journal est simulé, puis comparé aux vrais inventaires."""
import glob
import importlib.util
import itertools
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from module.dialogue import morceaux  # noqa: E402
from module.jeu.materiaux import SuiviMateriaux, categorie, cle, limite  # noqa: E402
from module.jeu.materiaux_table import LIMITES, MATERIAUX  # noqa: E402

DOSSIER_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_ED = os.path.join(os.path.expanduser("~"), "Saved Games", "Frontier Developments", "Elite Dangerous")
for _flux in (sys.stdout, sys.stderr):
    if hasattr(_flux, "reconfigure"):
        _flux.reconfigure(errors="replace")


class Table(unittest.TestCase):
    def test_grades_et_limites(self):
        self.assertEqual(len(MATERIAUX), 147)
        self.assertEqual(LIMITES, {1: 300, 2: 250, 3: 200, 4: 150, 5: 100})
        self.assertEqual(limite("carbon"), 300)
        self.assertEqual(limite("AdaptiveEncryptors"), 100)
        self.assertEqual(limite("FSDTelemetry"), 250)
        self.assertIsNone(limite("metaalloys"))                   # une marchandise, pas un matériau

    def test_categories(self):
        self.assertEqual(categorie("iron"), "brut")
        self.assertEqual(categorie("focuscrystals"), "fabrique")
        self.assertEqual(categorie("inconnu", "$MICRORESOURCE_CATEGORY_Encoded;"), "encode")
        self.assertIsNone(categorie("metaalloys"))
        self.assertTrue(all(c in ("brut", "fabrique", "encode") and 1 <= g <= 5 for c, g, _ in MATERIAUX.values()))
        self.assertTrue(all(g <= 4 for c, g, _ in MATERIAUX.values() if c == "brut"))


class Base(unittest.TestCase):
    def setUp(self):
        self.s = SuiviMateriaux(reglages=lambda: {"seuil_presque_plein": 90})
        self.secondes = itertools.count()

    def ev(self, nom, meme_seconde=False, **champs):
        s = self.derniere if meme_seconde else next(self.secondes)
        self.derniere = s
        return self.s.traiter({"timestamp": f"2026-11-24T10:{s // 60:02d}:{s % 60:02d}Z", "event": nom, **champs})

    def releve(self, **stock):
        return self.ev("Materials", Raw=[{"Name": k, "Count": v} for k, v in stock.items() if categorie(k) == "brut"],
                       Manufactured=[{"Name": k, "Count": v} for k, v in stock.items() if categorie(k) == "fabrique"],
                       Encoded=[{"Name": k, "Count": v} for k, v in stock.items() if categorie(k) == "encode"])

    def stock(self, nom):
        return self.s.donnees["stock"].get(nom, 0)


class Stock(Base):
    def test_releve_muet(self):
        self.assertEqual(self.releve(carbon=299, adaptiveencryptors=100), [])
        self.assertEqual((self.stock("carbon"), self.stock("adaptiveencryptors")), (299, 100))
        # Déjà plein au lancement : pas d'annonce quand on en ramasse encore
        self.assertEqual(self.ev("MaterialCollected", Category="Encoded", Name="adaptiveencryptors", Count=3), [])

    def test_presque_plein_puis_plein_une_fois(self):
        self.releve(adaptiveencryptors=85)
        annonces = self.ev("MaterialCollected", Category="Encoded", Name="adaptiveencryptors",
                           Name_Localised="Capture de cryptage évolutif", Count=6)
        self.assertEqual(annonces, [{"type": "presque", "materiau": "adaptiveencryptors",
                                     "nom": "Capture de cryptage évolutif", "quantite": 91, "limite": 100}])
        self.assertEqual(self.ev("MaterialCollected", Category="Encoded", Name="adaptiveencryptors", Count=3), [])
        annonces = self.ev("MaterialCollected", Category="Encoded", Name="adaptiveencryptors", Count=9)
        self.assertEqual((annonces[0]["type"], self.stock("adaptiveencryptors")), ("plein", 100))   # plafonné
        self.assertEqual(self.ev("MaterialCollected", Category="Encoded", Name="adaptiveencryptors", Count=1), [])

    def test_rearme_quand_il_redescend(self):
        self.releve(adaptiveencryptors=99)
        self.assertEqual(self.ev("MaterialCollected", Category="Encoded", Name="adaptiveencryptors", Count=1)[0]["type"], "plein")
        self.ev("MaterialDiscarded", Category="Encoded", Name="adaptiveencryptors", Count=5)    # 95 : presque
        self.assertEqual(self.ev("MaterialCollected", Category="Encoded", Name="adaptiveencryptors", Count=5)[0]["type"], "plein")
        self.ev("EngineerCraft", Ingredients=[{"Name": "adaptiveencryptors", "Count": 50}])     # 50 : réarmé
        self.assertEqual(self.ev("MaterialCollected", Category="Encoded", Name="adaptiveencryptors", Count=41)[0]["type"], "presque")

    def test_tous_les_mouvements(self):
        self.releve(iron=100, nickel=50, compoundshielding=30, focuscrystals=10)
        self.ev("MaterialTrade", TraderType="manufactured",
                Paid={"Material": "compoundshielding", "Category": "Manufactured", "Quantity": 26},
                Received={"Material": "electrochemicalarrays", "Category": "Manufactured", "Quantity": 13})
        self.ev("EngineerCraft", Ingredients=[{"Name": "iron", "Count": 2}, {"Name": "metaalloys", "Count": 1}])
        self.ev("Synthesis", Name="Ammo Basic", Materials=[{"Name": "nickel", "Count": 1}])
        self.ev("TechnologyBroker", Materials=[{"Name": "focuscrystals", "Count": 5, "Category": "Manufactured"}],
                Commodities=[{"Name": "gold", "Count": 1}])
        self.ev("MissionCompleted", MaterialsReward=[{"Name": "FSDTelemetry", "Category": "$MICRORESOURCE_CATEGORY_Encoded;", "Count": 8}])
        self.ev("EngineerContribution", Type="Materials", Material="iron", Quantity=10)
        self.ev("ScientificResearch", Category="Raw", Name="nickel", Count=4)
        self.assertEqual({k: self.stock(k) for k in ("iron", "nickel", "compoundshielding", "electrochemicalarrays",
                                                     "focuscrystals", "fsdtelemetry")},
                         {"iron": 88, "nickel": 45, "compoundshielding": 4, "electrochemicalarrays": 13,
                          "focuscrystals": 5, "fsdtelemetry": 8})
        self.assertNotIn("metaalloys", self.s.donnees["stock"])

    def test_seuil_reglable(self):
        self.s.reglages = lambda: {"seuil_presque_plein": 50}
        self.releve(carbon=100)
        self.assertEqual(self.ev("MaterialCollected", Category="Raw", Name="carbon", Count=50)[0]["type"], "presque")

    def test_vue(self):
        self.releve(carbon=280, adaptiveencryptors=10, focuscrystals=200)
        vue = self.s.vue()
        self.assertEqual([c["titre"] for c in vue["categories"]], ["Bruts", "Fabriqués", "Chiffrés"])
        self.assertEqual(vue["presque_pleins"], 2)
        carbone = vue["categories"][0]["materiaux"][0]
        self.assertEqual((carbone["nom"], carbone["limite"], carbone["etat"]), ("Carbone", 300, "presque"))


class Garde(Base):
    def test_deux_lignes_identiques_dans_la_meme_seconde(self):
        """Vu dans les journaux : deux ramassages identiques dans la même seconde."""
        self.releve(heatdispersionplate=0)
        ligne = dict(Category="Manufactured", Name="heatdispersionplate", Count=3)
        self.ev("MaterialCollected", **ligne)
        self.ev("MaterialCollected", meme_seconde=True, **ligne)
        self.assertEqual(self.stock("heatdispersionplate"), 6)
        # Relecture du même journal (redémarrage du COVAS) : rien n'est recompté
        self.s.nouvelle_lecture()
        for e in ({"timestamp": "2026-11-24T10:00:01Z", "event": "MaterialCollected", **ligne},) * 2:
            self.s.traiter(dict(e))
        self.assertEqual(self.stock("heatdispersionplate"), 6)


class Voix(unittest.TestCase):
    def test_nom_enregistre(self):
        ids = morceaux.pour_materiau("plein", "adaptiveencryptors")
        self.assertEqual([i.rsplit("/", 1)[-1] for i in ids], ["StockPlein.mp3", "CaptureDeCryptageEvolutif.mp3"])
        self.assertIsNone(morceaux.pour_materiau("presque", "polonium"))


def _lecteur_prive():
    avant = set(sys.modules)
    chemin = os.path.join(DOSSIER_BACKEND, "module", "jeu", "lecteur_logs.py")
    spec = importlib.util.spec_from_file_location("covas_lecteur_logs_materiaux", chemin)
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
        self.origines = (logs.envoyer_donnees_web, logs._dire, logs._dire_morceaux)

        async def envoyer(message):
            self.envoye.append(message)

        async def dire(cle_, urgent=False, secours=None):
            self.dit.append(cle_)

        async def dire_morceaux(ids, secours):
            self.dit.append("+".join(i.rsplit("/", 1)[-1][:-4] for i in ids if i))

        logs.envoyer_donnees_web, logs._dire, logs._dire_morceaux = envoyer, dire, dire_morceaux
        logs._materiaux.__init__(reglages=lambda: {"seuil_presque_plein": 90})
        logs._reinitialiser_etat()

    def tearDown(self):
        logs.envoyer_donnees_web, logs._dire, logs._dire_morceaux = self.origines
        logs._materiaux.__init__(reglages=lambda: {"seuil_presque_plein": 90})
        logs._reinitialiser_etat()

    async def ligne(self, s, nom, **champs):
        await logs._traiter_ligne(json.dumps({"timestamp": f"2026-11-24T10:00:{s:02d}Z", "event": nom, **champs}),
                                  en_direct=True)

    async def test_materiels_et_alertes(self):
        await self.ligne(0, "Materials", Raw=[{"Name": "polonium", "Count": 130}], Manufactured=[],
                         Encoded=[{"Name": "adaptiveencryptors", "Name_Localised": "Capture de cryptage évolutif", "Count": 89}])
        self.assertEqual(self.dit, [])
        await self.ligne(1, "MaterialCollected", Category="Encoded", Name="adaptiveencryptors", Count=1)
        await self.ligne(2, "MaterialCollected", Category="Raw", Name="polonium", Count=6)
        self.assertEqual(self.dit, ["StockPresquePlein+CaptureDeCryptageEvolutif", "materiau_presque_plein"])
        self.assertEqual(logs.ETAT["materiaux"]["presque_pleins"], 2)
        lignes = [m["evenement"]["texte"] for m in self.envoye if m.get("type") == "evenement"]
        self.assertIn("Stock presque plein : Capture de cryptage évolutif (90/100)", lignes)


class SurLesVraisJournaux(unittest.TestCase):
    """Avant chaque inventaire complet (Materials) des journaux du commandant, le stock suivi doit
    être exactement celui du jeu."""

    def test_inventaires_du_jeu(self):
        journaux = sorted(glob.glob(os.path.join(DOSSIER_ED, "Journal.*.log")), key=os.path.getctime)
        if not journaux:
            self.skipTest("journaux du jeu absents")
        s, compares, ecarts, premier = SuiviMateriaux(), 0, [], True
        for chemin in journaux:
            s.nouvelle_lecture()
            with open(chemin, encoding="utf-8", errors="replace") as f:
                for ligne in f:
                    if '"event":"' not in ligne:
                        continue
                    try:
                        e = json.loads(ligne)
                    except ValueError:
                        continue
                    if e.get("event") == "Materials":
                        if not premier:
                            vrai = {cle(m["Name"]): m["Count"] for c in ("Raw", "Manufactured", "Encoded")
                                    for m in e.get(c) or []}
                            calcule = {k: v for k, v in s.donnees["stock"].items() if v}
                            compares += 1
                            if calcule != {k: v for k, v in vrai.items() if v}:
                                ecarts.append(e["timestamp"])
                        premier = False
                    s.traiter(e)
        self.assertGreater(compares, 0)
        self.assertEqual(ecarts, [], f"{len(ecarts)} inventaires sur {compares}")


if __name__ == "__main__":
    unittest.main()
