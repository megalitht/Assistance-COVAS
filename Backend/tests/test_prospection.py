"""Prospecteurs : minerais intéressants, noyau, annonces, réglages, affichage des 5 derniers.
Sans touche, sans micro et sans réseau ; le journal est simulé."""
import glob
import importlib.util
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from module import config  # noqa: E402
from module.dialogue import morceaux  # noqa: E402
from module.jeu.prospection import Prospection, nom_minerai  # noqa: E402

DOSSIER_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_ED = os.path.join(os.path.expanduser("~"), "Saved Games", "Frontier Developments", "Elite Dangerous")
REGLAGES = {"annoncer_noyau": True, "annoncer_sans_interet": False, "ignorer_deja_mines": True,
            "minerais": {"platinum": 15, "tritium": 15, "bromellite": 15}}
for _flux in (sys.stdout, sys.stderr):
    if hasattr(_flux, "reconfigure"):
        _flux.reconfigure(errors="replace")

# Copie d'un événement du journal du commandant (23/11/2026)
REEL = {"timestamp": "2026-11-23T21:43:15Z", "event": "ProspectedAsteroid", "Materials": [
    {"Name": "Haematite", "Name_Localised": "Hématite", "Proportion": 24.252232},
    {"Name": "Indite", "Proportion": 9.913629}, {"Name": "cobalt", "Proportion": 7.634123}],
    "Content": "$AsteroidMaterialContent_Low;", "Content_Localised": "Présence de matériaux : faible",
    "Remaining": 100.0}


def asteroide(*materiaux, contenu="High", noyau=None, reste=100.0):
    e = {"timestamp": "2026-11-24T10:00:00Z", "event": "ProspectedAsteroid", "Remaining": reste,
         "Content": f"$AsteroidMaterialContent_{contenu};",
         "Materials": [{"Name": n, "Proportion": p} for n, p in materiaux]}
    if noyau:
        e["MotherlodeMaterial"] = noyau
    return e


class Analyse(unittest.TestCase):
    def setUp(self):
        self.p = Prospection()

    def test_evenement_reel_sans_interet(self):
        fiche, annonce = self.p.analyser(REEL, REGLAGES)
        self.assertIsNone(annonce)
        self.assertEqual((fiche["contenu"], fiche["niveau"]), ("Faible", "low"))
        self.assertEqual([(m["nom"], m["pourcentage"]) for m in fiche["materiaux"]],
                         [("Hématite", 24.3), ("Indite", 9.9), ("Cobalt", 7.6)])
        self.assertFalse(fiche["interessant"])

    def test_minerai_interessant(self):
        fiche, annonce = self.p.analyser(asteroide(("Bromellite", 18.0), ("tritium", 26.2), ("water", 9)), REGLAGES)
        self.assertEqual(annonce, {"noyau": None, "minerai": "tritium", "pourcentage": 26.2, "sans_interet": False})
        self.assertEqual([m["interessant"] for m in fiche["materiaux"]], [True, True, False])

    def test_sous_le_seuil(self):
        self.assertIsNone(self.p.analyser(asteroide(("platinum", 14.9)), REGLAGES)[1])

    def test_noyau(self):
        fiche, annonce = self.p.analyser(asteroide(("water", 9), noyau="Alexandrite"), REGLAGES)
        self.assertEqual(annonce["noyau"], "alexandrite")
        self.assertEqual(fiche["noyau"], "Alexandrite")
        self.assertTrue(fiche["interessant"])
        self.assertIsNone(self.p.analyser(asteroide(("water", 9), noyau="Alexandrite"),
                                          dict(REGLAGES, annoncer_noyau=False))[1])

    def test_deja_mine(self):
        e = asteroide(("platinum", 40), reste=60.0)
        self.assertIsNone(self.p.analyser(e, REGLAGES)[1])
        self.assertIsNotNone(self.p.analyser(e, dict(REGLAGES, ignorer_deja_mines=False))[1])

    def test_option_sans_interet(self):
        annonce = self.p.analyser(REEL, dict(REGLAGES, annoncer_sans_interet=True))[1]
        self.assertTrue(annonce["sans_interet"])

    def test_cinq_derniers(self):
        for i in range(7):
            self.p.analyser(asteroide(("platinum", 10 + i)), REGLAGES)
        vue = self.p.vue()
        self.assertEqual((len(vue["derniers"]), vue["prospectes"], vue["interessants"]), (5, 7, 2))
        self.assertEqual(vue["derniers"][0]["materiaux"][0]["pourcentage"], 16.0)     # le plus récent d'abord

    def test_noms(self):
        self.assertEqual(nom_minerai("LowTemperatureDiamond"), "Diamants basse température")
        self.assertEqual(nom_minerai("$opal_name;"), "Opales du vide")
        self.assertEqual(nom_minerai("unobtainium", "Inconnu"), "Inconnu")


class Voix(unittest.TestCase):
    def fin(self, ids):
        return [i.rsplit("/", 1)[-1] if i else None for i in ids]

    def test_riche_en(self):
        ids = morceaux.pour_prospection({"minerai": "platinum", "pourcentage": 31.8})
        self.assertEqual(self.fin(ids), ["AsteroideRicheEn.mp3", "Platine.mp3", "032.mp3", "PourCent.mp3"])

    def test_noyau_puis_minerai(self):
        ids = morceaux.pour_prospection({"noyau": "alexandrite", "minerai": "tritium", "pourcentage": 20})
        self.assertEqual(self.fin(ids)[:3], ["NoyauDetecte.mp3", "Alexandrite.mp3", None])

    def test_minerai_sans_voix(self):
        self.assertIsNone(morceaux.pour_prospection({"minerai": "haematite", "pourcentage": 30}))

    def test_morceaux_au_catalogue(self):
        ids = {l["id"] for l in morceaux.catalogue()}
        self.assertIn("data/son/Morceaux/Minerais/DiamantsBasseTemperature.mp3", ids)
        self.assertIn("data/son/Morceaux/Minage/AsteroideRicheEn.mp3", ids)


class Reglages(unittest.TestCase):
    def test_table_des_minerais_libre(self):
        with tempfile.TemporaryDirectory() as dossier:
            ancien = config.CHEMIN
            try:
                config.CHEMIN = os.path.join(dossier, "config.toml")
                with open(config.CHEMIN, "w", encoding="utf-8") as f:
                    f.write('[minage.minerais]\nsilver = 30\nplatinum = 12.5\nosmium = "beaucoup"\n')
                config.recharger()
                self.assertEqual(config.valeur("minage", "minerais"), {"silver": 30, "platinum": 12.5})
                self.assertTrue(config.valeur("minage", "annoncer_noyau"))
            finally:
                config.CHEMIN = ancien
                config.recharger()


def _lecteur_prive():
    avant = set(sys.modules)
    chemin = os.path.join(DOSSIER_BACKEND, "module", "jeu", "lecteur_logs.py")
    spec = importlib.util.spec_from_file_location("covas_lecteur_logs_minage", chemin)
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

        async def dire(cle, urgent=False, secours=None):
            self.dit.append(cle)

        async def dire_morceaux(ids, secours):
            self.dit.append("+".join(i.rsplit("/", 1)[-1][:-4] for i in ids if i))

        logs.envoyer_donnees_web, logs._dire, logs._dire_morceaux = envoyer, dire, dire_morceaux
        logs._prospection.__init__()
        logs._reinitialiser_etat()

    def tearDown(self):
        logs.envoyer_donnees_web, logs._dire, logs._dire_morceaux = self.origines
        logs._reinitialiser_etat()

    async def test_annonce_et_affichage(self):
        await logs._traiter_ligne(json.dumps(asteroide(("tritium", 26.2), ("water", 9))), en_direct=True)
        await logs._traiter_ligne(json.dumps(asteroide(("haematite", 40), contenu="Low")), en_direct=True)
        self.assertEqual(self.dit, ["AsteroideRicheEn+Tritium+026+PourCent"])
        derniers = logs.ETAT["minage"]["derniers"]
        self.assertEqual([d["interessant"] for d in derniers], [False, True])
        lignes = [m["evenement"]["texte"] for m in self.envoye if m.get("type") == "evenement"]
        self.assertIn("Astéroïde (élevé) : Tritium 26 %, Eau 9 %", lignes)


class SurLesVraisJournaux(unittest.TestCase):
    def test_tous_les_asteroides_du_commandant(self):
        p, annonces, total = Prospection(), 0, 0
        for chemin in glob.glob(os.path.join(DOSSIER_ED, "Journal.*.log")):
            with open(chemin, encoding="utf-8", errors="replace") as f:
                for ligne in f:
                    if '"ProspectedAsteroid"' in ligne:
                        total += 1
                        annonces += p.analyser(json.loads(ligne), config.DEFAUTS["minage"])[1] is not None
        if not total:
            self.skipTest("journaux du jeu absents")
        self.assertGreater(annonces, 0)
        self.assertLess(annonces, total)


if __name__ == "__main__":
    unittest.main()
