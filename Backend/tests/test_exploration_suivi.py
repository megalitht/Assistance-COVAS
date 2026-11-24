"""Valeur des données d'exploration non vendues : formule, suivi enregistré, ventes, mort, annonces.
Sans touche, sans micro et sans réseau ; les fichiers vont dans un dossier temporaire."""
import glob
import importlib.util
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from module.jeu import suivi as suivis  # noqa: E402
from module.jeu import valeur_corps as vc  # noqa: E402
from module.jeu.suivi_exploration import SuiviExploration  # noqa: E402

DOSSIER_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_ED = os.path.join(os.path.expanduser("~"), "Saved Games", "Frontier Developments", "Elite Dangerous")
for _flux in (sys.stdout, sys.stderr):
    if hasattr(_flux, "reconfigure"):
        _flux.reconfigure(errors="replace")

REGLAGES = {"paliers_millions": [0.5, 5], "rappel_min_millions": 0.1, "rappel_bio": True}
ADRESSE = 1234


def scan(corps, classe="Water world", masse=0.5, decouvert=True, cartographie=True, h="2026-11-24T10:00:00Z",
         terra="", etoile=None, systeme="Test", adresse=ADRESSE, **autres):
    e = {"timestamp": h, "event": "Scan", "ScanType": "Detailed", "BodyName": f"{systeme} {corps}",
         "BodyID": corps, "StarSystem": systeme, "SystemAddress": adresse,
         "WasDiscovered": decouvert, "WasMapped": cartographie, **autres}
    if etoile:
        e.update(StarType=etoile, StellarMass=masse)
    else:
        e.update(PlanetClass=classe, MassEM=masse, TerraformState=terra)
    return e


class Formule(unittest.TestCase):
    """Valeurs calculées à la main avec les constantes d'EDDiscovery (EstimatedValues.cs)."""

    def test_planete_non_cartographiee(self):
        k = 64831 + 116295
        self.assertEqual(vc.valeur_planete("Water world", True, 1.0, False), round(k + k * vc.Q))
        self.assertEqual(vc.valeur_planete("Earthlike body", False, 1.0, True), round((k + k * vc.Q) * 2.6))

    def test_cartographie(self):
        base = 64831 + 64831 * vc.Q * 0.5 ** 0.2
        deja = base * (10 / 3)
        deja += max(deja * 0.3, 555)
        self.assertEqual(vc.valeur_planete("Water world", False, 0.5, False, True, False, True), round(deja * 1.25))
        premier = base * 3.699622554
        premier += max(premier * 0.3, 555)
        self.assertEqual(vc.valeur_planete("Water world", False, 0.5, True, True, True, False), round(premier * 2.6))
        seul = base * 8.0956
        seul += max(seul * 0.3, 555)
        self.assertEqual(vc.valeur_planete("Water world", False, 0.5, False, True, True, True), round(seul * 1.25))

    def test_minimum_sur_la_valeur_de_base(self):
        self.assertEqual(vc.valeur_planete("Icy body", False, 0.0001, False), 500)
        petite = 500 * (10 / 3)
        petite += max(petite * 0.3, 555)
        self.assertEqual(vc.valeur_planete("Icy body", False, 0.0001, False, True, False, False), round(petite))

    def test_riche_en_metaux_terraformable(self):
        self.assertEqual(vc.k_planete("Metal rich body", True), 21790 + 65631)

    def test_etoiles(self):
        self.assertEqual(vc.valeur_etoile("K", 1.0, False), round(1200 + 1200 / 66.25))
        self.assertEqual(vc.valeur_etoile("DA", 0.6, True), round((14057 + 0.6 * 14057 / 66.25) * 2.6))
        self.assertEqual(vc.valeur_etoile("N", 1.4, False), round(22628 + 1.4 * 22628 / 66.25))

    def test_scan(self):
        self.assertEqual(vc.valeur_scan({"ScanType": "NavBeaconDetail", "PlanetClass": "Icy body"}), (0, 0))
        self.assertEqual(vc.valeur_scan({"BodyName": "X A Belt Cluster 1"}), (0, 0))
        valeur, carte = vc.valeur_scan(scan(1))
        self.assertLess(valeur, carte)

    def test_bonus_systeme(self):
        self.assertEqual(vc.bonus_systeme(10, False, 4, 4), 0)
        self.assertEqual(vc.bonus_systeme(10, True, 4, 3), 10 * 1000)
        self.assertEqual(vc.bonus_systeme(10, True, 4, 4), 10 * 1000 + 4 * 10000)


class Garde(unittest.TestCase):
    def test_un_evenement_compte_une_fois(self):
        s = SuiviExploration(reglages=lambda: REGLAGES)
        e = scan(1)
        s.traiter(e)
        self.assertEqual(s.traiter(dict(e)), [])
        self.assertFalse(s.deja_compte(scan(2)))                       # même seconde, autre corps
        s.traiter(scan(2))
        self.assertEqual(s.totaux()["corps"], 2)
        self.assertTrue(s.deja_compte(scan(3, h="2026-11-24T09:00:00Z")))   # plus ancien

    def test_fichier_et_relecture(self):
        with tempfile.TemporaryDirectory() as dossier:
            chemin = os.path.join(dossier, "exploration.json")
            s = SuiviExploration(reglages=lambda: REGLAGES)
            self.assertFalse(s.ouvrir(chemin))
            for i in range(3):
                s.traiter(scan(i))
            s.enregistrer(forcer=True)
            autre = SuiviExploration(reglages=lambda: REGLAGES)
            self.assertTrue(autre.ouvrir(chemin))
            self.assertEqual(autre.totaux(), s.totaux())
            for i in range(3):                                         # le COVAS relit le journal
                autre.traiter(scan(i))
            self.assertEqual(autre.totaux(), s.totaux())

    def test_fichier_illisible(self):
        with tempfile.TemporaryDirectory() as dossier:
            chemin = os.path.join(dossier, "exploration.json")
            with open(chemin, "w", encoding="utf-8") as f:
                f.write("{pas du json")
            self.assertFalse(SuiviExploration().ouvrir(chemin))
            self.assertTrue(os.path.exists(chemin + ".illisible"))

    def test_reconstruction_depuis_des_journaux(self):
        with tempfile.TemporaryDirectory() as dossier:
            journal = os.path.join(dossier, "Journal.2026-11-24T100000.01.log")
            with open(journal, "w", encoding="utf-8") as f:
                for i in range(4):
                    f.write(json.dumps(scan(i, h=f"2026-11-24T10:00:0{i}Z"), separators=(",", ":")) + "\n")
                f.write('{"timestamp":"2026-11-24T10:00:09Z","event":"Music","MusicTrack":"x"}\n')
            s = SuiviExploration(chemin=os.path.join(dossier, "suivi", "exploration.json"))
            self.assertEqual(suivis.reconstruire([s], [journal]), 4)
            self.assertEqual(s.totaux()["corps"], 4)
            self.assertTrue(os.path.exists(s.chemin))


class Exploration(unittest.TestCase):
    def setUp(self):
        self.s = SuiviExploration(reglages=lambda: REGLAGES)

    def ev(self, nom, h="2026-11-24T11:00:00Z", **champs):
        return self.s.traiter({"timestamp": h, "event": nom, **champs})

    def test_cartographie_et_efficacite(self):
        self.s.traiter(scan(5, cartographie=False))
        avant = self.s.totaux()["cartographie"]
        self.ev("SAAScanComplete", SystemAddress=ADRESSE, BodyID=5, ProbesUsed=9, EfficiencyTarget=6)
        fiche = self.s.donnees["systemes"][str(ADRESSE)]["corps"]["5"]
        self.assertTrue(fiche["carto"] and not fiche["efficace"])
        self.assertGreater(self.s.totaux()["cartographie"], avant)
        self.assertEqual(fiche["valeur"], vc.valeur_planete("Water world", False, 0.5, False, True, True, False))

    def test_bonus_du_systeme_complet(self):
        self.ev("FSSDiscoveryScan", SystemAddress=ADRESSE, SystemName="Test", BodyCount=3)
        for i in range(3):
            self.s.traiter(scan(i, etoile="M" if i == 0 else None, classe="Icy body"))
        self.ev("FSSAllBodiesFound", h="2026-11-24T11:00:01Z", SystemAddress=ADRESSE, SystemName="Test", Count=3)
        self.assertEqual(self.s.totaux()["bonus"], 3 * 1000)

    def test_balise_et_ceinture_ne_comptent_pas(self):
        self.s.traiter(scan(1, ScanType="NavBeaconDetail"))
        self.s.traiter({"timestamp": "2026-11-24T10:00:01Z", "event": "Scan", "BodyName": "Test A Belt Cluster 1",
                        "BodyID": 9, "SystemAddress": ADRESSE, "StarSystem": "Test"})
        self.assertEqual(self.s.totaux()["corps"], 0)

    def test_vente_partielle_puis_complete(self):
        self.s.traiter(scan(1, systeme="Alpha", adresse=1))
        self.s.traiter(scan(1, systeme="Beta", adresse=2))
        valeur_alpha = self.s.donnees["systemes"]["1"]["corps"]["1"]["valeur"]
        self.ev("MultiSellExplorationData", Discovered=[{"SystemName": "Alpha", "NumBodies": 1}],
                BaseValue=valeur_alpha, Bonus=0, TotalEarnings=valeur_alpha)
        self.assertEqual(self.s.totaux()["systemes"], 1)
        vente = self.s.donnees["derniere_vente"]
        self.assertEqual((vente["estimation"], vente["paye"], vente["reconnus"]), (valeur_alpha, valeur_alpha, 1))
        self.ev("SellExplorationData", h="2026-11-24T11:00:05Z", Systems=["beta"], Discovered=[], TotalEarnings=100)
        self.assertEqual(self.s.totaux()["total"], 0)

    def test_paliers_une_fois_puis_apres_la_vente(self):
        annonces = self.s.traiter(scan(1, classe="Earthlike body", masse=1.0, decouvert=False, cartographie=False))
        self.assertEqual([a["type"] for a in annonces], ["palier"])     # monde terrestre découvert : ≈ 0,74 M
        self.assertEqual(annonces[0]["palier"], 0.5)
        self.assertEqual(self.s.traiter(scan(2, classe="Icy body", h="2026-11-24T10:00:01Z")), [])
        self.ev("SellExplorationData", Systems=["Test"], TotalEarnings=1)
        self.assertEqual(self.s.donnees["paliers_dits"], [])
        annonces = self.s.traiter(scan(1, classe="Earthlike body", masse=1.0, decouvert=False,
                                       cartographie=False, h="2026-11-24T12:00:00Z"))
        self.assertEqual([a["type"] for a in annonces], ["palier"])

    def test_plusieurs_paliers_d_un_coup_annonce_le_plus_haut(self):
        self.s.reglages = lambda: dict(REGLAGES, paliers_millions=[0.1, 0.2, 50])
        annonces = self.s.traiter(scan(1, classe="Earthlike body", masse=1.0, decouvert=False, cartographie=False))
        self.assertEqual((len(annonces), annonces[0]["palier"]), (1, 0.2))

    def test_mort(self):
        self.s.traiter(scan(1))
        annonces = self.ev("Died", KillerName="Pirate")
        self.assertEqual(annonces[0]["type"], "perdu")
        self.assertGreater(annonces[0]["montant"], 0)
        self.assertEqual(self.s.totaux()["total"], 0)
        self.assertEqual(self.ev("Died", h="2026-11-24T11:10:00Z"), [])     # rien à perdre : silence

    def test_rappel_a_l_amarrage(self):
        self.s.traiter(scan(1, classe="Earthlike body", masse=1.0))
        annonces = self.ev("Docked", StationName="X", StationServices=["dock", "exploration", "vistagenomics"])
        self.assertEqual([a["service"] for a in annonces], ["cartographie"])     # pas de bio à vendre
        self.assertEqual(self.ev("Docked", h="2026-11-24T11:00:09Z", StationServices=["dock", "refuel"]), [])

    def test_biologie(self):
        self.s.traiter(scan(3, classe="Rocky body", WasFootfalled=False, Landable=True))
        espece = "$Codex_Ent_Stratum_07_Name;"
        self.ev("ScanOrganic", ScanType="Log", SystemAddress=ADRESSE, Body=3, Species=espece, Genus="g")
        self.assertEqual(self.s.totaux()["especes"], 0)                   # pas encore analysée
        self.ev("ScanOrganic", h="2026-11-24T11:01:00Z", ScanType="Analyse", SystemAddress=ADRESSE, Body=3,
                Species=espece, Species_Localised="Stratum Tectonicas", Genus="g")
        bio = self.s.donnees["bio"][0]
        self.assertTrue(bio["bonus"])
        self.assertEqual(bio["valeur"] % 5, 0)
        annonces = self.ev("Docked", h="2026-11-24T11:02:00Z", StationServices=["vistagenomics"])
        self.assertIn("bio", [a["service"] for a in annonces])
        self.ev("SellOrganicData", h="2026-11-24T11:03:00Z",
                BioData=[{"Genus": "g", "Species": espece, "Value": 1, "Bonus": 4}])
        self.assertEqual((self.s.totaux()["bio"], self.s.donnees["vendu"]["bio"]), (0, 5))

    def test_vue(self):
        for i in range(12):
            self.s.traiter(scan(i, classe="Icy body", masse=0.01 * (i + 1), h=f"2026-11-24T10:00:{i:02d}Z"))
        vue = self.s.vue()
        self.assertEqual(len(vue["top"]), 10)
        self.assertEqual(vue["top"][0]["classe"], "Glacé")
        self.assertGreaterEqual(vue["top"][0]["valeur"], vue["top"][-1]["valeur"])


def _lecteur_prive():
    avant = set(sys.modules)
    chemin = os.path.join(DOSSIER_BACKEND, "module", "jeu", "lecteur_logs.py")
    spec = importlib.util.spec_from_file_location("covas_lecteur_logs_explo", chemin)
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
        logs._explo.__init__(reglages=lambda: REGLAGES)
        logs._reinitialiser_etat()

    def tearDown(self):
        logs.envoyer_donnees_web, logs._dire, logs._dire_morceaux, logs.SYSTEMES_PROCHES_ACTIF = self.origines
        logs._explo.__init__(reglages=lambda: REGLAGES)
        logs._reinitialiser_etat()

    async def ligne(self, e, en_direct=True):
        await logs._traiter_ligne(json.dumps(e), en_direct=en_direct)

    async def test_scan_palier_vente(self):
        await self.ligne(scan(1, classe="Earthlike body", masse=1.0, decouvert=False, cartographie=False))
        self.assertGreater(logs.ETAT["donnees_explo"]["total"], 0.5e6)
        self.assertIn("exploration_palier", self.dit)
        self.assertTrue(any(m.get("section") == "donnees_explo" for m in self.envoye))
        await self.ligne({"timestamp": "2026-11-24T12:00:00Z", "event": "MultiSellExplorationData",
                          "Discovered": [{"SystemName": "Test", "NumBodies": 1}], "BaseValue": 2_000_000,
                          "Bonus": 0, "TotalEarnings": 2_000_000})
        self.assertEqual(logs.ETAT["donnees_explo"]["total"], 0)
        lignes = [m["evenement"]["texte"] for m in self.envoye if m.get("type") == "evenement"]
        self.assertTrue(any("estimation ≈" in t for t in lignes), lignes)

    async def test_relecture_muette_et_sans_double_comptage(self):
        e = scan(1, classe="Earthlike body", masse=1.0)
        await self.ligne(e, en_direct=False)
        await self.ligne(e)
        self.assertEqual(logs.ETAT["donnees_explo"]["corps"], 1)
        self.assertEqual(self.dit, [])

    async def test_mort_annoncee(self):
        await self.ligne(scan(1))
        await self.ligne({"timestamp": "2026-11-24T12:00:00Z", "event": "Died", "KillerName": "X"})
        self.assertIn("exploration_perdue", self.dit)
        self.assertEqual(logs.ETAT["donnees_explo"]["total"], 0)


class SurLesVraisJournaux(unittest.TestCase):
    """Tous les journaux du commandant (lecture seule) : la relecture complète tient, et relire une
    deuxième fois n'ajoute rien."""

    def test_relecture_complete_idempotente(self):
        journaux = sorted(glob.glob(os.path.join(DOSSIER_ED, "Journal.*.log")), key=os.path.getctime)
        if not journaux:
            self.skipTest("journaux du jeu absents")
        s = SuiviExploration(reglages=lambda: REGLAGES)
        suivis.reconstruire([s], journaux)
        totaux = s.totaux()
        self.assertGreater(len(s.donnees["vendu"]), 0)
        suivis.reconstruire([s], journaux)
        self.assertEqual(s.totaux(), totaux)


if __name__ == "__main__":
    unittest.main()
