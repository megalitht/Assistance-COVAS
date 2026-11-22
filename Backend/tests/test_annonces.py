"""Annonces des actions manuelles : logique pure, sans touche, sans micro, sans macros.py."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from module.annonces import DetecteurManuel  # noqa: E402

AMARRE, POSE, TRAIN, SC, ARMES, ECOPE = 1 << 0, 1 << 1, 1 << 2, 1 << 4, 1 << 6, 1 << 9
CHARGE, VAISSEAU, ANALYSE, SAUT = 1 << 17, 1 << 24, 1 << 27, 1 << 30


class Annonces(unittest.TestCase):
    def setUp(self):
        self.d = DetecteurManuel()
        self.t = 100.0
        self.appuis = {}
        self.vu(VAISSEAU)

    def vu(self, flags, apres=10.0, **options):
        self.t += apres
        return self.d.observer(flags, self.t, self.appuis, **options)

    def test_premiere_lecture_muette(self):
        self.assertEqual(DetecteurManuel().observer(VAISSEAU | TRAIN, 0, {}), [])

    def test_fsd_manuel(self):
        self.assertEqual(self.vu(VAISSEAU | CHARGE), ["manuel_fsd"])

    def test_bascules_dans_les_deux_sens(self):
        self.assertEqual(self.vu(VAISSEAU | TRAIN), ["manuel_train_sorti"])
        self.assertEqual(self.vu(VAISSEAU), ["manuel_train_rentre"])
        self.assertEqual(self.vu(VAISSEAU | ANALYSE), ["manuel_analyse"])
        self.assertEqual(self.vu(VAISSEAU), ["manuel_combat"])

    def test_appui_du_covas_silencieux_une_seule_fois(self):
        self.appuis["train"] = self.t + 9.5
        self.assertEqual(self.vu(VAISSEAU | TRAIN), [])
        self.assertEqual(self.vu(VAISSEAU), ["manuel_train_rentre"])

    def test_fsd_lance_par_le_covas(self):
        self.appuis["saut"] = self.t + 9.5
        self.assertEqual(self.vu(VAISSEAU | CHARGE), [])

    def test_vieil_appui_ignore(self):
        self.appuis["train"] = self.t - 20
        self.assertEqual(self.vu(VAISSEAU | TRAIN), ["manuel_train_sorti"])

    def test_muet_pendant_un_programme(self):
        self.assertEqual(self.vu(VAISSEAU | CHARGE, muet=True), [])
        self.assertEqual(self.vu(VAISSEAU, muet=True), [])

    def test_amarrage_ne_parle_pas(self):
        self.assertEqual(self.vu(VAISSEAU | AMARRE | TRAIN), [])
        self.assertEqual(self.vu(VAISSEAU | AMARRE), [])

    def test_changement_du_jeu_a_la_supercroisiere(self):
        self.vu(VAISSEAU | ARMES)
        self.assertEqual(self.vu(VAISSEAU | SC), [])
        self.assertEqual(self.vu(VAISSEAU, apres=1), [])

    def test_rangement_pendant_la_charge(self):
        self.vu(VAISSEAU | ARMES)
        self.assertEqual(self.vu(VAISSEAU | ARMES | CHARGE), ["manuel_fsd"])
        self.assertEqual(self.vu(VAISSEAU | CHARGE, apres=1), [])

    def test_plusieurs_modules_d_un_coup(self):
        self.assertEqual(self.vu(VAISSEAU | TRAIN | ECOPE), [])

    def test_hors_du_vaisseau(self):
        self.assertEqual(self.vu(TRAIN), [])
        self.assertEqual(self.vu(VAISSEAU), [])

    def test_retour_du_menu(self):
        self.assertEqual(self.vu(0), [])
        self.assertEqual(self.vu(VAISSEAU | TRAIN), [])

    def test_pas_de_repetition(self):
        self.assertEqual(self.vu(VAISSEAU | CHARGE), ["manuel_fsd"])
        self.assertEqual(self.vu(VAISSEAU, apres=3.1), [])
        self.assertEqual(self.vu(VAISSEAU | CHARGE, apres=0.5), [])

    def test_reglage_par_module(self):
        self.assertEqual(self.vu(VAISSEAU | TRAIN, actives={"train": False}), [])
        self.assertEqual(self.vu(VAISSEAU | TRAIN | CHARGE, actives={"fsd": False}), [])


if __name__ == "__main__":
    unittest.main()
