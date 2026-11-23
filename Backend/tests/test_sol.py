"""VRS et pied à terre : sans touche, sans micro, sans macros.py.
Les fichiers de commandes du jeu sont des copies temporaires."""
import hashlib
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from module.pilotage import commandes, touches  # noqa: E402
from module.dialogue import comprehension  # noqa: E402
from module.jeu import sol  # noqa: E402

VRS, VAISSEAU, A_PIED = 1 << 26, 1 << 24, 1


def binds(*lignes):
    corps = "".join(f'<{nom}><Primary Device="Keyboard" Key="{cle}" /><Secondary Device="{{NoDevice}}" Key="" /></{nom}>'
                    for nom, cle in lignes)
    return f'<?xml version="1.0" encoding="UTF-8" ?><Root><KeyboardLayout>fr-FR</KeyboardLayout><UI_Up><Primary Device="Keyboard" Key="Key_Z" /></UI_Up>{corps}</Root>'


class Situation(unittest.TestCase):
    def test_lieux(self):
        self.assertEqual(sol.situation(VAISSEAU), "vaisseau")
        self.assertEqual(sol.situation(VRS), "vrs")
        self.assertEqual(sol.situation(1 << 25), "chasseur")
        self.assertIsNone(sol.situation(0, 0))
        self.assertIsNone(sol.situation(None, None))

    def test_a_pied_en_station_avec_flags_nuls(self):
        self.assertEqual(sol.situation(0, A_PIED | 1 << 3), "pied")


class Traduction(unittest.TestCase):
    def test_memes_mots_autre_touche(self):
        self.assertEqual(sol.traduire("phares", [], "vrs"), "vrs_phares")
        self.assertEqual(sol.traduire("phares", [], "pied"), "pied_lampe")
        self.assertIsNone(sol.traduire("phares", [], "vaisseau"))

    def test_commande_hors_de_son_lieu(self):
        self.assertEqual(sol.traduire("vrs_frein", [], "vrs"), "vrs_frein")
        self.assertIsNone(sol.traduire("vrs_frein", [], "pied"))
        self.assertIsNone(sol.traduire("pied_soin", [], "vaisseau"))

    def test_mots_a_pied(self):
        self.assertEqual(sol.traduire("energie_sys", ["active", "le", "bouclier"], "pied"), "pied_bouclier")
        self.assertIsNone(sol.traduire("energie_sys", ["energie", "aux", "systemes"], "pied"))
        self.assertEqual(sol.traduire("energie_arm", ["range", "l", "arme"], "pied"), "pied_arme")

    def test_chaque_commande_a_sa_touche_de_jeu(self):
        self.assertEqual(set(sol.COMMANDES), set(touches.COMMANDES_SOL))
        for cible in [c for routes in sol._ROUTES.values() for c in routes.values()]:
            self.assertIn(cible, sol.COMMANDES)

    def test_ordres_vocaux(self):
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "data", "barks.json"), encoding="utf-8") as f:
            barks = json.load(f)
        for phrase, cle in (("serre le frein à main", "vrs_frein"), ("rappelle le vaisseau", "vrs_vaisseau"),
                            ("allume la lampe", "pied_lampe"), ("utilise une trousse de soin", "pied_soin"),
                            ("recharge l'arme", "pied_recharger"), ("sors le train", "train_atterrissage"),
                            ("active le fsd", "fsd"), ("éteins les phares", "phares")):
            self.assertEqual(comprehension.trouver_action(phrase, barks, {"mots_reveil", "politesse"}), cle, phrase)


class Boussole(unittest.TestCase):
    def test_distance_et_cap(self):
        rayon = 1_000_000
        distance, cap = sol.distance_cap(0, 0, 0, 1, rayon)
        self.assertAlmostEqual(distance, 17453.3, places=0)
        self.assertAlmostEqual(cap, 90, places=3)
        self.assertAlmostEqual(sol.distance_cap(0, 0, 1, 0, rayon)[1] % 360, 0, places=3)
        self.assertAlmostEqual(sol.distance_cap(1, 0, 0, 0, rayon)[1], 180, places=3)
        self.assertAlmostEqual(sol.distance_cap(0, 0, 0, -1, rayon)[1], 270, places=3)

    def test_retour_au_vaisseau(self):
        etat = sol.vierge()
        sol.vaisseau_pose(etat, 10, 20, "A 1")
        status = {"latitude": 10, "longitude": 20.01, "rayon": 1_000_000, "corps": "A 1"}
        self.assertTrue(sol.actualiser(etat, status))
        self.assertEqual(etat["vaisseau"]["cap"], 270)
        self.assertGreater(etat["vaisseau"]["distance"], 100)
        self.assertFalse(sol.actualiser(etat, status))

    def test_autre_corps_pas_de_direction(self):
        etat = sol.vierge()
        sol.vaisseau_pose(etat, 10, 20, "A 1")
        sol.actualiser(etat, {"latitude": 10, "longitude": 21, "rayon": 1e6, "corps": "B 2"})
        self.assertIsNone(etat["vaisseau"]["distance"])

    def test_vaisseau_renvoye(self):
        etat = sol.vierge()
        sol.vaisseau_pose(etat, 10, 20, "A 1")
        sol.vaisseau_oublie(etat, "parti")
        self.assertEqual(etat["vaisseau"]["etat"], "parti")
        self.assertIsNone(etat["vaisseau"]["latitude"])


class Exobiologie(unittest.TestCase):
    def scan(self, etat, genre, status, espece="$E1;"):
        sol.scan_organique(etat, {"ScanType": genre, "Genus": "$Codex_Ent_Tussocks_Genus_Name;",
                                  "Species": espece, "Species_Localised": "Touradon Ignis"}, status)

    def test_sequence_du_journal(self):
        etat, status = sol.vierge(), {"latitude": 0, "longitude": 0, "rayon": 1_000_000, "corps": "A"}
        self.scan(etat, "Log", status)
        self.assertEqual((etat["exobio"]["echantillons"], etat["exobio"]["portee"]), (1, 200))
        status = {**status, "longitude": 0.005}
        sol.actualiser(etat, status)
        self.assertFalse(etat["exobio"]["libre"])
        status = {**status, "longitude": 0.02}
        sol.actualiser(etat, status)
        self.assertTrue(etat["exobio"]["libre"])
        self.scan(etat, "Sample", status)
        self.scan(etat, "Sample", status)
        self.assertEqual(etat["exobio"]["echantillons"], 3)
        self.scan(etat, "Analyse", status)
        self.assertTrue(etat["exobio"]["termine"])
        self.assertIsNone(etat["exobio"]["distance"])

    def test_nouvelle_espece_repart_de_zero(self):
        etat, status = sol.vierge(), {"latitude": 0, "longitude": 0}
        self.scan(etat, "Log", status)
        self.scan(etat, "Sample", status)
        self.scan(etat, "Log", status, "$E2;")
        self.assertEqual((etat["exobio"]["id"], etat["exobio"]["echantillons"]), ("$E2;", 1))
        self.assertEqual(len(etat["exobio"]["points"]), 1)


class TouchesParProfil(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {"COVAS_DOSSIER_BINDS": self.dossier.name})
        self.env.start()
        commandes.oublier_jeu()

    def tearDown(self):
        commandes.oublier_jeu()
        self.env.stop()
        self.dossier.cleanup()

    def ecrire(self, nom, contenu):
        chemin = os.path.join(self.dossier.name, nom)
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(contenu)
        return chemin

    def test_chaque_categorie_dans_son_profil(self):
        self.ecrire("StartPreset.4.start", "Vol\nVol\nRoute\nMarche")
        self.ecrire("Vol.4.2.binds", binds(("LandingGearToggle", "Key_L"), ("AutoBreakBuggyButton", "Key_K")))
        self.ecrire("Route.4.2.binds", binds(("AutoBreakBuggyButton", "Key_X")))
        self.ecrire("Marche.4.2.binds", binds(("HumanoidToggleFlashlightButton", "Key_T")))
        lues = touches.lire_sans_ecrire()[2]
        self.assertEqual(lues["train"], ("l", []))
        self.assertEqual(lues["vrs_frein"], ("x", []))
        self.assertEqual(lues["pied_lampe"], ("t", []))

    def test_profil_integre_sans_touche(self):
        self.ecrire("StartPreset.4.start", "Vol\nVol\nKeyboardMouseOnly\nMarche")
        self.ecrire("Vol.4.2.binds", binds(("AutoBreakBuggyButton", "Key_K")))
        self.ecrire("Marche.4.2.binds", binds(("HumanoidToggleFlashlightButton", "Key_T")))
        lues = touches.lire_sans_ecrire()[2]
        self.assertNotIn("vrs_frein", lues)
        self.assertIn("pied_lampe", lues)

    def test_jamais_de_touche_virtuelle_ni_d_ecriture(self):
        chemin = self.ecrire("Custom.4.2.binds", binds(("LandingGearToggle", "Key_L")))
        with open(chemin, "rb") as f:
            avant = hashlib.sha256(f.read()).hexdigest()
        catalogue = commandes.catalogue()
        with mock.patch.object(touches, "_jeu_lance", return_value=False):
            touches.charger(assigner=False)
        self.assertFalse(set(touches.COMMANDES_SOL) & set(touches.ETAT["manquantes"]))
        with open(chemin, "rb") as f:
            self.assertEqual(hashlib.sha256(f.read()).hexdigest(), avant)
        groupes = {g["id"]: g for g in catalogue["groupes"]}
        self.assertFalse(groupes["vrs"]["sequences"])
        self.assertTrue(groupes["vol"]["sequences"])
        self.assertTrue(all(c["secours"] is None for c in groupes["pied"]["commandes"]))

    def test_touche_personnelle_acceptee(self):
        propre = commandes.nettoyer({"touches": {"pied_soin": ["h", []], "inconnue": ["h", []]}})
        self.assertEqual(propre["touches"], {"pied_soin": ["h", []]})


if __name__ == "__main__":
    unittest.main()
