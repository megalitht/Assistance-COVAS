"""Pips et réglages : logique pure, sans touche, sans micro, sans macros.py."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from module.pilotage import pips  # noqa: E402
from module.interface import reglages  # noqa: E402
from module.dialogue.comprehension import trouver_action  # noqa: E402

TOUTES = [(s, m, a) for s in range(9) for m in range(9) for a in range(9) if s + m + a == 12]


class JeuSimule:
    """Répartiteur du jeu ; `regle` permet de simuler un jeu différent du modèle."""

    def __init__(self, depart=(4, 4, 4), regle=pips.apres_appui, reagit=True):
        self.etat, self.regle, self.reagit, self.appuis = tuple(depart), regle, reagit, []

    def lire(self):
        return list(self.etat)

    def appuyer(self, touche):
        self.appuis.append(touche)
        if self.reagit:
            self.etat = (pips.EQUILIBRE if touche == pips.TOUCHE_EQUILIBRE
                         else self.regle(self.etat, pips.TOUCHES.index(touche)))
        return True


def regle_differente(etat, ligne):
    """Variante : à 3,5 pips, le dernier demi-pip est pris sur la PLUS GRANDE ligne."""
    nouveau = list(etat)
    if nouveau[ligne] != 7:
        return pips.apres_appui(etat, ligne)
    autres = [i for i in range(3) if i != ligne]
    nouveau[ligne] = 8
    nouveau[max(autres, key=lambda i: nouveau[i])] -= 1
    return tuple(nouveau)


class Moteur(unittest.TestCase):
    def test_61_repartitions_toutes_atteignables(self):
        self.assertEqual(len(TOUTES), 61)
        for depart in TOUTES:
            for cible in TOUTES:
                self.assertIsNotNone(pips.chemin(depart, cible), (depart, cible))

    def test_appui_garde_le_total(self):
        for etat in TOUTES:
            for ligne in range(3):
                self.assertIsNotNone(pips.valide(pips.apres_appui(etat, ligne)), (etat, ligne))

    def test_anciennes_macros_retrouvees(self):
        jeu = JeuSimule()
        for touche, fois in (("pips_sys", 4), ("pips_armes", 4)):
            for _ in range(fois):
                jeu.appuyer(touche)
        self.assertEqual(jeu.etat, reglages._BASE["mode_combat"]["pips"])

    def test_atteint_toute_cible(self):
        for depart in TOUTES:
            for cible in TOUTES:
                jeu = JeuSimule(depart)
                self.assertEqual(pips.appliquer(cible, jeu.lire, jeu.appuyer, pause=lambda _: 0), "ok")
                self.assertEqual(jeu.etat, cible)

    def test_corrige_si_le_jeu_differe_du_modele(self):
        atteignables = {(4, 4, 4)}
        a_voir = [(4, 4, 4)]
        while a_voir:
            etat = a_voir.pop()
            for ligne in range(3):
                suivant = regle_differente(etat, ligne)
                if suivant not in atteignables:
                    atteignables.add(suivant)
                    a_voir.append(suivant)
        for depart in TOUTES:
            for cible in TOUTES:
                jeu = JeuSimule(depart, regle=regle_differente)
                resultat = pips.appliquer(cible, jeu.lire, jeu.appuyer, pause=lambda _: 0)
                if cible in atteignables or cible == tuple(depart):
                    self.assertEqual((resultat, jeu.etat), ("ok", cible), (depart, cible))
                else:                       # impossible dans ce jeu : il le dit, sans boucler
                    self.assertEqual(resultat, "ecart", (depart, cible))
                    self.assertLess(len(jeu.appuis), 40)

    def test_deja_en_place_aucune_touche(self):
        jeu = JeuSimule((6, 0, 6))
        self.assertEqual(pips.appliquer((6, 0, 6), jeu.lire, jeu.appuyer), "ok")
        self.assertEqual(jeu.appuis, [])

    def test_jeu_sans_reaction_on_n_insiste_pas(self):
        jeu = JeuSimule(reagit=False)
        attendu = len(pips.chemin((4, 4, 4), (8, 4, 0))) + 1      # trajet + un seul appui de contrôle
        resultat = pips.appliquer((8, 4, 0), jeu.lire, jeu.appuyer, pause=lambda _: 0)
        self.assertEqual(resultat, "sans_reaction")
        self.assertEqual(len(jeu.appuis), attendu)

    def test_etat_inconnu_part_de_l_equilibre(self):
        appuis = []
        resultat = pips.appliquer((6, 0, 6), lambda: None, lambda t: appuis.append(t) or True)
        self.assertEqual(resultat, "sans_verification")
        self.assertEqual(appuis[0], pips.TOUCHE_EQUILIBRE)

    def test_stop_interrompt(self):
        appuis = []
        def appuyer(touche):
            appuis.append(touche)
            return False
        self.assertEqual(pips.appliquer((8, 4, 0), lambda: [4, 4, 4], appuyer), "interrompu")
        self.assertEqual(len(appuis), 1)

    def test_valeurs_impossibles(self):
        for mauvais in ([4, 4], [9, 3, 0], [4, 4, 5], [True, 3, 8], [4.0, 4, 4], "444", None):
            self.assertIsNone(pips.valide(mauvais), mauvais)


class Reglages(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.ancien = reglages.CHEMIN
        self.chemin = os.path.join(self.dossier.name, "reglages.json")
        reglages._barks, reglages._cles_vocales = None, set()
        reglages.charger(self.chemin)

    def tearDown(self):
        reglages._barks, reglages._cles_vocales = None, set()
        reglages.CHEMIN = self.ancien
        reglages._doc = None
        self.dossier.cleanup()

    def doc(self):
        return reglages.document()

    def test_valeurs_de_depart(self):
        self.assertEqual(reglages.pips_pour("mode_combat"), (4, 0, 8))
        self.assertEqual(reglages.pips_pour("mode_croisiere", "python_nx"), (4, 8, 0))
        self.assertFalse(os.path.exists(self.chemin))

    def test_vaisseau_herite_puis_personnalise(self):
        doc = self.doc()
        doc["pips"]["vaisseaux"]["Python_NX"] = {"mode_combat": [6, 0, 6]}
        reglages.enregistrer(doc)
        self.assertEqual(reglages.pips_pour("mode_combat", "python_nx"), (6, 0, 6))
        self.assertEqual(reglages.pips_pour("mode_combat", "PYTHON_NX"), (6, 0, 6))
        self.assertEqual(reglages.pips_pour("mode_esquive", "python_nx"), (6, 6, 0))
        self.assertEqual(reglages.pips_pour("mode_combat", "anaconda"), (4, 0, 8))

    def test_relu_apres_redemarrage(self):
        doc = self.doc()
        doc["pips"]["modes"].append({"id": "mode_perso_a1", "nom": "Chasse"})
        doc["pips"]["defaut"]["mode_perso_a1"] = [2, 2, 8]
        doc["pips"]["vaisseaux"]["krait_mkii"] = {"mode_perso_a1": [8, 0, 4]}
        reglages.enregistrer(doc)
        reglages.charger(self.chemin)
        self.assertTrue(reglages.est_mode("mode_perso_a1"))
        self.assertEqual(reglages.pips_pour("mode_perso_a1"), (2, 2, 8))
        self.assertEqual(reglages.pips_pour("mode_perso_a1", "krait_mkii"), (8, 0, 4))
        with open(self.chemin, encoding="utf-8") as f:
            self.assertEqual([m["id"] for m in json.load(f)["pips"]["modes"]], ["mode_perso_a1"])

    def test_donnees_invalides_ecartees(self):
        reglages.enregistrer({"pips": {
            "modes": [{"id": "../../x", "nom": "A"}, {"id": "mode_perso_b", "nom": "combat"},
                      {"id": "mode_perso_c", "nom": "   "}, "rien"],
            "defaut": {"mode_combat": [9, 9, 9], "inconnu": [4, 4, 4]},
            "vaisseaux": {"../evil": {"mode_combat": [6, 0, 6]},
                          "viper": {"mode_combat": [1, 1, 1], "inconnu": [4, 4, 4]}},
        }})
        doc = self.doc()["pips"]
        self.assertEqual(len(doc["modes"]), len(reglages.MODES_BASE))
        self.assertEqual(doc["defaut"]["mode_combat"], [4, 0, 8])
        self.assertNotIn("inconnu", doc["defaut"])
        self.assertEqual(doc["vaisseaux"], {"viper": {}})

    def test_n_importe_quoi_ne_casse_rien(self):
        for brut in (None, 3, "x", [], {"pips": 2}, {"pips": {"modes": 1, "defaut": [], "vaisseaux": 0}}):
            self.assertEqual(len(reglages.nettoyer(brut)["pips"]["defaut"]), len(reglages.MODES_BASE))

    def test_fichier_illisible_mis_de_cote(self):
        with open(self.chemin, "w", encoding="utf-8") as f:
            f.write("{ abîmé")
        doc = reglages.charger(self.chemin)
        self.assertEqual(doc["pips"]["defaut"]["mode_combat"], [4, 0, 8])
        self.assertTrue(os.path.exists(self.chemin + ".illisible"))

    def test_commandes_vocales_suivent_les_modes(self):
        barks = {"mode_Combat": {"mots_cles": ["combat"], "reponses": []}}
        reglages.lier_commandes(barks)
        self.assertEqual(trouver_action("passe en mode esquive", barks), "mode_esquive")

        doc = self.doc()
        doc["pips"]["modes"].append({"id": "mode_perso_z", "nom": "Chasse"})
        reglages.enregistrer(doc)
        self.assertEqual(trouver_action("mode chasse", barks), "mode_perso_z")

        doc = self.doc()
        doc["pips"]["modes"] = [m for m in doc["pips"]["modes"] if m["id"] != "mode_perso_z"]
        reglages.enregistrer(doc)
        self.assertNotIn("mode_perso_z", barks)
        self.assertEqual(trouver_action("mode combat", barks), "mode_Combat")


if __name__ == "__main__":
    unittest.main()
