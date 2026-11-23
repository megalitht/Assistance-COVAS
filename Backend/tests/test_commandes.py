"""Touches et séquences de Réglages > Commandes : sans touche, sans micro, sans macros.py.
Les fichiers du jeu et des réglages sont des copies temporaires."""
import hashlib
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from module.pilotage import commandes, touches  # noqa: E402
from module.interface import reglages  # noqa: E402

BINDS = """<?xml version="1.0" encoding="UTF-8" ?>
<Root PresetName="Custom">
\t<KeyboardLayout>fr-FR</KeyboardLayout>
\t<UI_Up><Primary Device="Keyboard" Key="Key_Z" /><Secondary Device="{NoDevice}" Key="" /></UI_Up>
\t<LandingGearToggle><Primary Device="Keyboard" Key="Key_L" /><Secondary Device="{NoDevice}" Key="" /></LandingGearToggle>
\t<UI_Left><Primary Device="Keyboard" Key="Key_Q" /><Secondary Device="{NoDevice}" Key="" /></UI_Left>
\t<NightVisionToggle><Primary Device="Keyboard" Key="Key_F13"><Modifier Device="Keyboard" Key="Key_RightShift" /></Primary><Secondary Device="{NoDevice}" Key="" /></NightVisionToggle>
</Root>
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.binds = os.path.join(self.dossier.name, "Custom.4.2.binds")
        with open(self.binds, "w", encoding="utf-8") as f:
            f.write(BINDS)
        self.env = mock.patch.dict(os.environ, {"COVAS_DOSSIER_BINDS": self.dossier.name})
        self.env.start()
        commandes.oublier_jeu()
        self.ancien = reglages.CHEMIN
        self.chemin = os.path.join(self.dossier.name, "reglages.json")
        reglages._barks, reglages._cles_vocales = None, set()
        reglages.charger(self.chemin)

    def tearDown(self):
        reglages.CHEMIN = self.ancien
        reglages._doc = None
        commandes.oublier_jeu()
        self.env.stop()
        self.dossier.cleanup()

    def ecrire(self, **parties):
        doc = reglages.document()
        doc["commandes"].update(parties)
        return reglages.enregistrer(doc)[0]


class Catalogue(Base):
    def test_chaque_commande_du_jeu_est_rangee_une_fois(self):
        rangees = [c for _, _, noms in commandes.GROUPES for c in noms]
        self.assertEqual(sorted(rangees), sorted(touches.COMMANDES_JEU))
        self.assertEqual(set(commandes.TOUCHES_SECOURS), set(touches.COMMANDES_JEU))

    def test_sequences_d_origine_valides(self):
        for cle, s in commandes.SEQUENCES.items():
            self.assertEqual(commandes.sequence_valide(s["etapes"]), s["etapes"], cle)

    def test_touches_valides_envoyables(self):
        import pydirectinput
        connues = set(pydirectinput.KEYBOARD_MAPPING)
        ajoutees = {f"f{n}" for n in range(13, 25)} | {f"numpad{n}" for n in range(10)}
        self.assertEqual(commandes.TOUCHES_VALIDES - connues - ajoutees, set())

    def test_lit_le_jeu_en_azerty(self):
        cat = reglages.document()["catalogue"]
        self.assertTrue(cat["azerty"])
        lignes = {c["id"]: c for g in cat["groupes"] for c in g["commandes"]}
        self.assertEqual(lignes["ui_haut"]["jeu"], ["w", []])       # emplacement physique du Z
        self.assertEqual(lignes["ui_gauche"]["jeu"], ["a", []])
        self.assertEqual(lignes["nvg"]["jeu"], ["f13", ["shiftright"]])
        self.assertIsNone(lignes["leurres"]["jeu"])

    def test_lecture_ne_modifie_rien(self):
        with open(self.binds, "rb") as f:
            avant = hashlib.sha256(f.read()).hexdigest()
        etat_avant = dict(touches.ETAT)
        reglages.document()
        commandes.oublier_jeu()
        reglages.enregistrer({"commandes": {"touches": {"train": ["k", []]}}})
        reglages.document()
        with open(self.binds, "rb") as f:
            self.assertEqual(hashlib.sha256(f.read()).hexdigest(), avant)
        self.assertEqual(touches.ETAT, etat_avant)
        self.assertEqual(os.listdir(self.dossier.name).count("Custom.4.2.binds"), 1)
        self.assertFalse([n for n in os.listdir(self.dossier.name) if n.endswith(".bak")])

    def test_suit_un_changement_du_fichier(self):
        self.assertEqual(commandes.touches_jeu()["train"], ("l", []))
        with open(self.binds, "w", encoding="utf-8") as f:
            f.write(BINDS.replace("Key_L", "Key_K"))
        os.utime(self.binds, (2_000_000_000, 2_000_000_000))
        commandes._jeu["verifie"] = -1e9
        self.assertEqual(commandes.touches_jeu()["train"], ("k", []))

    def test_fichier_en_cours_d_ecriture_garde_la_lecture(self):
        commandes.touches_jeu()
        with open(self.binds, "w", encoding="utf-8") as f:
            f.write("<Root><abim")
        os.utime(self.binds, (2_000_000_000, 2_000_000_000))
        commandes._jeu["verifie"] = -1e9
        self.assertEqual(commandes.touches_jeu()["train"], ("l", []))

    def test_sans_fichier_du_jeu(self):
        os.remove(self.binds)
        commandes.oublier_jeu()
        cat = commandes.catalogue()
        self.assertIsNone(cat["fichier"])
        lignes = {c["id"]: c for g in cat["groupes"] for c in g["commandes"]}
        self.assertEqual(lignes["train"]["secours"], ["l", []])


class Personnalisation(Base):
    def test_touche_et_sequence_relues_apres_redemarrage(self):
        etapes = ["ui_bas", "pause:0.7", "ui_selection"]
        self.ecrire(touches={"train": ["k", ["shiftleft", "ctrlleft"]]}, sequences={"decollage": etapes})
        reglages.charger(self.chemin)
        self.assertEqual(reglages.touche_perso("train"), ("k", ["ctrlleft", "shiftleft"]))
        self.assertEqual(reglages.sequence("decollage"), etapes)
        with open(self.chemin, encoding="utf-8") as f:
            disque = json.load(f)
        self.assertNotIn("catalogue", disque)
        self.assertEqual(disque["commandes"]["sequences"]["decollage"], etapes)

    def test_les_pips_sont_conserves(self):
        doc = reglages.document()
        doc["pips"]["vaisseaux"]["python_nx"] = {"mode_combat": [8, 4, 0]}
        doc["commandes"]["touches"]["train"] = ["k", []]
        reglages.enregistrer(doc)
        self.assertEqual(reglages.pips_pour("mode_combat", "python_nx"), (8, 4, 0))
        self.assertEqual(reglages.touche_perso("train"), ("k", []))

    def test_ancien_fichier_sans_commandes(self):
        with open(self.chemin, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "pips": {"modes": [], "defaut": {}, "vaisseaux": {"viper": {}}}}, f)
        doc = reglages.charger(self.chemin)
        self.assertEqual(doc["commandes"], {"touches": {}, "sequences": {}})
        self.assertIn("viper", doc["pips"]["vaisseaux"])

    def test_sequence_vide_gardee_mais_pas_l_origine(self):
        self.ecrire(sequences={"decollage": [], "services": list(commandes.SEQUENCES["services"]["etapes"])})
        self.assertEqual(reglages.sequence("decollage"), [])
        self.assertNotIn("services", reglages.document()["commandes"]["sequences"])

    def test_touches_refusees(self):
        for mauvaise in (["esc", []], ["win", []], ["ctrlright", []], ["k", ["ctrlright"]], ["k", ["k"]],
                         ["shiftleft", ["shiftleft"]], ["k", ["ctrlleft", "altleft", "shiftleft"]],
                         ["k"], "k", None, [1, []], ["k", "ctrlleft"]):
            self.assertIsNone(commandes.touche_valide(mauvaise), mauvaise)
        self.ecrire(touches={"inconnue": ["k", []], "train": ["win", []]})
        self.assertEqual(reglages.document()["commandes"]["touches"], {})

    def test_sequence_abimee_jamais_jouee_a_moitie(self):
        for mauvaise in (["ui_bas", "inconnue"], ["ui_bas", "pause:9"], ["pause:0"], ["pause:0.55"],
                         ["ui_bas", 3], "ui_bas", ["ui_bas"] * 61):
            self.ecrire(sequences={"decollage": mauvaise})
            self.assertEqual(reglages.sequence("decollage"), commandes.SEQUENCES["decollage"]["etapes"], mauvaise)

    def test_pauses(self):
        self.assertEqual(commandes.duree_pause("pause:0.1"), 0.1)
        self.assertEqual(commandes.duree_pause("pause:5.0"), 5.0)
        for mauvaise in ("pause:5.1", "pause:0.0", "pause:", "pause:a", "ui_bas", None):
            self.assertIsNone(commandes.duree_pause(mauvaise), mauvaise)

    def test_n_importe_quoi_ne_casse_rien(self):
        for brut in (None, 3, "x", [], {"touches": 2}, {"touches": {"train": 1}, "sequences": []}):
            self.assertEqual(commandes.nettoyer(brut), {"touches": {}, "sequences": {}})


if __name__ == "__main__":
    unittest.main()
