"""
Tests des phrases assemblées (module/dialogue/morceaux.py) : rapport d'avarie, heure, date, position.

Lancer depuis Backend/ :
    ..\\.venv\\Scripts\\python.exe -m unittest tests.test_morceaux -v

Aucun micro, aucun haut-parleur : les morceaux sont des sons fabriqués dans un dossier temporaire.
"""
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest import mock

import numpy as np

DOSSIER_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, DOSSIER_BACKEND)

from module.jeu import avaries  # noqa: E402
from module.dialogue import conversation, morceaux  # noqa: E402
from module.son import sons  # noqa: E402
from module.studio import studio  # noqa: E402


def module(objet, sante):
    return {"emplacement": objet, "objet": objet, "sante": sante}


class Textes(unittest.TestCase):
    def test_nombres(self):
        for n, attendu in {0: "zéro", 17: "dix-sept", 21: "vingt et un", 71: "soixante et onze",
                           72: "soixante-douze", 80: "quatre-vingts", 81: "quatre-vingt-un",
                           91: "quatre-vingt-onze", 99: "quatre-vingt-dix-neuf", 100: "cent"}.items():
            self.assertEqual(morceaux.nombre(n), attendu)
        self.assertEqual(morceaux.nombre(21, feminin=True), "vingt et une")

    def test_catalogue_sans_doublon_ni_vide(self):
        lignes = morceaux.catalogue()
        ids = [l["id"] for l in lignes]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(l["texte"].strip() for l in lignes))

    def test_studio_propose_tous_les_morceaux(self):
        visibles = {l["id"] for l in studio.inventaire() if l["source"] == "morceaux"}
        self.assertEqual(visibles, {l["id"] for l in morceaux.catalogue()})

    def test_toutes_les_heures_et_dates_existent(self):
        connus = {l["id"] for l in morceaux.catalogue()}
        instant = datetime(2026, 1, 1)
        for _ in range(24 * 60):
            for nom in ("heure", "heure_nuit"):
                self.assertLessEqual(set(morceaux.recette(nom, instant)) - {None}, connus)
            instant += timedelta(minutes=1)
        jour = datetime(2028, 1, 1)
        for _ in range(366):
            self.assertLessEqual(set(morceaux.recette("date", jour)) - {None}, connus)
            jour += timedelta(days=1)

    def test_tous_les_rapports_existent(self):
        connus = {l["id"] for l in morceaux.catalogue()}
        noms = list(avaries.NOMS_MODULES) + ["int_truc_inconnu"]
        for coque in (None, 1.0, 0.73, 0.0):
            for palier in (False, True):
                for n in (0, 1, 2, 4, 25):
                    etat = {"vaisseau": {"coque": coque, "coque_palier": palier, "boucliers": False},
                            "modules": {"liste": [module(noms[i % len(noms)], 0.0 if i % 2 else 0.42)
                                                  for i in range(n)]}}
                    ids = morceaux.pour_rapport(avaries.construire_rapport(etat))
                    self.assertTrue(ids)
                    self.assertLessEqual(set(ids) - {None}, connus)

    def test_tous_les_noms_de_modules_cites(self):
        connus = {l["id"] for l in morceaux.catalogue()}
        for objet in avaries.NOMS_MODULES:
            rapport = avaries.construire_rapport({"vaisseau": {"coque": 1.0},
                                                  "modules": {"liste": [module(objet, 0.3)]}})
            self.assertLessEqual(set(morceaux.pour_rapport(rapport)) - {None}, connus)
            self.assertNotIn(morceaux._ident("Rapport", "ModuleInconnu"), morceaux.pour_rapport(rapport))

    def test_les_repliques_variables_ont_une_recette(self):
        conversation.charger()
        self.assertEqual(conversation._contenu["erreurs"], [])
        sans_voix = [r for r in conversation._contenu["repliques"] if r.get("voix") == "aucune"]
        self.assertEqual(len(sans_voix), 7)
        self.assertTrue(all(r.get("morceaux") in morceaux.RECETTES for r in sans_voix))


class Assemblage(unittest.TestCase):
    def setUp(self):
        self.racine = tempfile.mkdtemp(prefix="covas_test_morceaux_")
        self.addCleanup(shutil.rmtree, self.racine, ignore_errors=True)
        patch = mock.patch.object(morceaux, "DOSSIER_BACKEND", self.racine)
        patch.start()
        self.addCleanup(patch.stop)
        morceaux._charger.cache_clear()
        self.ids = [morceaux._ident("Heure", "IlEst"), morceaux._id_heure(14), None,
                    morceaux._ident("Heure", "Commandant")]

    def fabriquer(self, ident, taux=48000, volume=0.2):
        t = np.arange(int(0.6 * taux)) / taux
        voix = np.sin(2 * np.pi * 180 * t) * np.sin(np.pi * t / 0.6) ** 0.5 * volume
        silence = np.zeros(int(0.2 * taux))
        x = np.concatenate([silence, voix, silence]).astype(np.float32)
        chemin = os.path.join(self.racine, *ident.split("/"))
        os.makedirs(os.path.dirname(chemin), exist_ok=True)
        sons.encoder_mp3(np.column_stack([x, x]), taux, chemin, sons.DEBIT_ENREGISTREMENT)

    def test_il_manque_un_morceau(self):
        self.fabriquer(self.ids[0])
        self.assertIsNone(morceaux.assembler(self.ids))
        self.assertEqual(len(morceaux.manquants(self.ids)), 2)

    def test_phrase_complete(self):
        self.fabriquer(self.ids[0])
        self.fabriquer(self.ids[1], taux=44100, volume=0.1)      # autre micro, autre volume
        self.fabriquer(self.ids[3], volume=0.3)
        chemin = morceaux.assembler(self.ids)
        self.addCleanup(lambda: os.path.exists(chemin) and os.remove(chemin))
        x, taux = sons.lire(chemin)
        self.assertEqual(taux, 48000)
        self.assertEqual(x.shape[1], 2)
        # trois morceaux d'environ 0,6 s, silences d'origine retirés
        self.assertGreater(len(x) / taux, 1.5)
        self.assertLess(len(x) / taux, 2.4)
        self.assertLessEqual(float(np.abs(x).max()), 1.0)


if __name__ == "__main__":
    unittest.main()
