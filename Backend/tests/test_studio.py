"""
Tests du studio vocal (module/studio/effet_voix.py, module/studio/studio.py).

Lancer depuis Backend/ :
    ..\\.venv\\Scripts\\python.exe -m unittest tests.test_studio -v

Aucun micro, aucun haut-parleur, aucune touche : les « prises » sont des voix fabriquées
(train d'impulsions + formants), et tout ce qui s'écrit va dans un dossier temporaire.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

DOSSIER_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, DOSSIER_BACKEND)

from module.studio import effet_voix, repliques, studio  # noqa: E402
from module.son import sons  # noqa: E402

TAUX = 48000


def voix(duree=1.6, f0=115.0, graine=0, taux=TAUX):
    """Une « voix » : impulsions glottiques, quatre formants, quatre syllabes, et une mélodie de
    phrase (monte, puis redescend sous la hauteur habituelle) comme une vraie voix."""
    t = np.arange(int(duree * taux)) / taux
    melodie = 1.2 - 0.4 * (t / duree) ** 1.5 + 0.06 * np.sin(2 * np.pi * 2.1 * t + graine)
    hauteur = f0 * melodie
    phase = np.cumsum(hauteur / taux)
    impulsions = (np.diff(np.floor(phase), prepend=0) > 0).astype(float)
    spectre = np.fft.rfft(impulsions)
    f = np.fft.rfftfreq(len(impulsions), 1 / taux)
    # pente moyenne de la parole (-6 dB/octave au-dessus de 500 Hz), formants, creux limités à -10 dB
    pics = sum(1 / (1 + ((f - F) / B) ** 2) for F, B in ((600, 90), (1150, 110), (2500, 160), (3500, 250)))
    filtre = (0.3 + pics) / np.sqrt(1 + (f / 500) ** 2)
    x = np.fft.irfft(spectre * filtre, len(impulsions))
    syllabes = np.abs(np.sin(np.pi * t * 4 / duree)) ** 0.4
    x *= syllabes
    return (x / np.sqrt(np.mean(x ** 2)) * 10 ** (-22 / 20)).astype(np.float32)


def prise(duree=1.6, f0=115.0, graine=0, avant=0.6, apres=0.5, bruit_db=-55.0, clics=True):
    """Une prise de micro : silence, voix, silence, souffle, et les clics du clavier."""
    rng = np.random.default_rng(graine)
    v = voix(duree, f0, graine)
    x = np.concatenate([np.zeros(int(avant * TAUX)), v, np.zeros(int(apres * TAUX))]).astype(np.float32)
    x += (rng.standard_normal(len(x)) * 10 ** (bruit_db / 20)).astype(np.float32)
    if clics:
        for position in (int(0.05 * TAUX), len(x) - int(0.05 * TAUX)):
            n = int(0.012 * TAUX)
            x[position:position + n] += (rng.standard_normal(n) * np.exp(-np.arange(n) / 96) * 0.3).astype(np.float32)
    return x, (int(avant * TAUX), int(avant * TAUX) + len(v))


class EffetVoix(unittest.TestCase):
    def test_zone_parole_ignore_les_clics(self):
        x, (debut, fin) = prise()
        _, bilan = effet_voix.nettoyer(x, TAUX)
        self.assertAlmostEqual(bilan["debut"] / TAUX, debut / TAUX, delta=0.12)
        self.assertAlmostEqual(bilan["fin"] / TAUX, fin / TAUX, delta=0.12)
        self.assertFalse(bilan["ecretage"])

    def test_debruitage_baisse_le_fond(self):
        x, (debut, _) = prise(bruit_db=-50.0, clics=False)
        propre, _ = effet_voix.nettoyer(x, TAUX, force=0.6, marge_avant=0.5)
        avant = 20 * np.log10(np.sqrt(np.mean(x[int(0.15 * TAUX):debut - int(0.15 * TAUX)] ** 2)))
        apres = 20 * np.log10(np.sqrt(np.mean(propre[int(0.05 * TAUX):int(0.3 * TAUX)] ** 2)) + 1e-12)
        self.assertLess(apres, avant - 15)

    def test_silence_rien_entendu(self):
        rng = np.random.default_rng(1)
        propre, bilan = effet_voix.nettoyer((rng.standard_normal(TAUX) * 1e-3).astype(np.float32), TAUX)
        self.assertEqual(bilan["parole"], 0)
        self.assertEqual(len(propre), 0)

    def test_ecretage_detecte(self):
        x, _ = prise(clics=False)
        _, bilan = effet_voix.nettoyer(np.clip(x * 300, -1, 1), TAUX)
        self.assertTrue(bilan["ecretage"])

    def test_hauteur_et_formants(self):
        v = voix(f0=110.0)
        self.assertAlmostEqual(effet_voix.hauteur_mediane(v, TAUX), 110.0, delta=8)
        for formants in (0.85, 1.0, 1.2):
            with self.subTest(formants=formants):
                y = effet_voix.robotiser(v, TAUX, effet_voix.reglages(choisis={"formants": formants}))
                self.assertEqual(y.shape[1], 2)
                self.assertTrue(np.isfinite(y).all())
                self.assertLessEqual(float(np.abs(y).max()), 0.97 + 1e-6)

    def test_etalonnage_rejoint_la_cible(self):
        prises = [(voix(1.5, 105 + 6 * g, g), TAUX) for g in range(6)]
        e = effet_voix.reglages()
        points = effet_voix.etalonner(prises, e)
        mesure = np.mean([effet_voix.spectre_bandes(effet_voix.robotiser(x, t, e, points), t)
                          for x, t in prises], axis=0)
        ecart = mesure - np.array(effet_voix.CIBLE_SPECTRE)
        utiles = [i for i, fc in enumerate(effet_voix.CENTRES) if 250 <= fc <= 5000]
        self.assertLess(float(np.max(np.abs(ecart[utiles]))), 4.0, np.round(ecart, 1))

    def test_decalage_en_demi_tons(self):
        v = voix(f0=110.0)
        for decalage in (-2.0, 1.9, 4.0):
            with self.subTest(decalage=decalage):
                y = effet_voix._psola(v, TAUX, 999.0, 1.0, decalage_dt=decalage)   # hauteur_hz ignorée
                attendu = effet_voix.hauteur_mediane(v, TAUX) * 2 ** (decalage / 12)
                self.assertAlmostEqual(effet_voix.hauteur_mediane(y, TAUX), attendu, delta=attendu * 0.04)

    def test_micro_limite_aigus_recrees(self):
        """Un micro qui coupe à ~6,8 kHz (casque sans fil) : la coupure est trouvée, les aigus recréés."""
        x, _ = prise(clics=False)
        spectre = np.fft.rfft(x)
        f = np.fft.rfftfreq(len(x), 1 / TAUX)
        coupe = np.fft.irfft(spectre / np.sqrt(1 + (f / 6800) ** 60), len(x)).astype(np.float32)
        coupe += (np.random.default_rng(3).standard_normal(len(x)) * 1e-5).astype(np.float32)
        propre, bilan = effet_voix.nettoyer(coupe, TAUX)
        self.assertAlmostEqual(bilan["bande_hz"], 6800, delta=400)
        f2, p2 = effet_voix._spectre_moyen(propre, TAUX)
        milieu = p2[(f2 > 2000) & (f2 < 4000)].mean()
        self.assertGreater(p2[(f2 > 8000) & (f2 < 12000)].mean(), milieu * 1e-4)   # moins de 40 dB sous le médium
        _, bilan_plein = effet_voix.nettoyer(x, TAUX)                                # pleine bande : rien à recréer
        self.assertIsNone(bilan_plein["bande_hz"])

    @staticmethod
    def _coherence(y, N=2048):
        H = N // 2
        idx = np.arange(N)[None, :] + H * np.arange(1 + (len(y) - N) // H)[:, None]
        G, D = np.fft.rfft(y[idx, 0] * np.hanning(N), axis=1), np.fft.rfft(y[idx, 1] * np.hanning(N), axis=1)
        coh = np.abs((G * np.conj(D)).mean(0)) ** 2 / ((np.abs(G) ** 2).mean(0) * (np.abs(D) ** 2).mean(0) + 1e-20)
        f = np.fft.rfftfreq(N, 1 / TAUX)
        return float(coh[(f > 300) & (f < 6000)].mean())

    def test_stereo_comme_les_originaux(self):
        """Originaux : gauche et droite cohérents à ~0,7. Le premier modèle les décorrélait (~0,4)."""
        v = voix(2.0)
        nouveau = self._coherence(effet_voix.robotiser(v, TAUX, effet_voix.reglages()))
        ancien = self._coherence(effet_voix.robotiser(v, TAUX, effet_voix.reglages("fidele", effet_voix.MODELE_2026_11_19)))
        self.assertGreater(nouveau, 0.55)
        self.assertLess(ancien, nouveau - 0.1)


class Rangement(unittest.TestCase):
    """garder(), appliquer_a_toutes(), étalonnage : dans une copie temporaire de data/."""

    def setUp(self):
        self.racine = tempfile.mkdtemp(prefix="covas_studio_")
        self.addCleanup(shutil.rmtree, self.racine, ignore_errors=True)
        son = os.path.join(self.racine, "data", "son", "Test")
        os.makedirs(son)
        stereo = np.stack([voix(), voix()], axis=1) * 0.5
        sons.encoder_mp3(stereo, TAUX, os.path.join(son, "Origine.mp3"))          # fait à la main
        sons.encoder_mp3(stereo, TAUX, os.path.join(son, "Synthese.mp3"))         # ancien fichier de synthèse
        sons.ecrire_wav(os.path.join(son, "Depose.wav"), stereo, TAUX)            # .wav déposé
        registre = os.path.join(self.racine, "data", "son", "repliques_synthese.json")
        with open(registre, "w", encoding="utf-8") as f:
            json.dump({"data/son/Test/Synthese.mp3": {"texte": "Essai.", "voix": "x", "profil": "fidele"}}, f)
        dossier_studio = os.path.join(self.racine, "data", "studio")
        for cible, valeur in {
            "DOSSIER_BACKEND": self.racine, "DOSSIER_STUDIO": dossier_studio,
            "CHEMIN_REGLAGES": os.path.join(dossier_studio, "reglages.json"),
            "CHEMIN_PRISES": os.path.join(dossier_studio, "prises.json"),
            "CHEMIN_ORIGINAUX": os.path.join(dossier_studio, "originaux.json"),
            "DOSSIER_PRISES": os.path.join(dossier_studio, "prises"),
            "DOSSIER_REMPLACES": os.path.join(dossier_studio, "remplaces"),
        }.items():
            patch = mock.patch.object(studio, cible, valeur)
            patch.start()
            self.addCleanup(patch.stop)
        for patch in (mock.patch.object(repliques, "CHEMIN_REGISTRE", registre),
                      mock.patch.object(studio.Studio, "_script_conversations", staticmethod(lambda: None))):
            patch.start()
            self.addCleanup(patch.stop)
        self.studio = studio.Studio()
        self.studio._lignes = {"data/son/Test/Origine.mp3": {"id": "data/son/Test/Origine.mp3", "texte": "Origine."}}

    def chemin(self, *parties):
        return os.path.join(self.racine, *parties)

    def test_garder_remplace_la_synthese(self):
        resume = self.studio.traiter(prise()[0], TAUX, "data/son/Test/Synthese.mp3")
        self.assertGreater(resume["parole"], 1.0)
        self.assertEqual(len(resume["forme_brut"]), 500)
        ligne = self.studio.garder()
        self.assertEqual(ligne["etat"], "studio")
        self.assertIsNone(ligne["remplace"])
        self.assertNotIn("data/son/Test/Synthese.mp3", repliques.lire_registre())
        self.assertIn("data/son/Test/Synthese.mp3", studio.lire_prises())
        self.assertTrue(os.path.isfile(self.chemin("data", "studio", "prises", "Test", "Synthese.mp3")))
        sortie, taux = sons.lire(self.chemin("data", "son", "Test", "Synthese.mp3"))
        self.assertEqual((taux, sortie.shape[1]), (TAUX, 2))
        self.assertEqual(studio.etat_replique("data/son/Test/Synthese.mp3"), "studio")

    def test_garder_met_l_original_de_cote(self):
        self.studio.traiter(prise()[0], TAUX, "data/son/Test/Origine.mp3")
        self.assertEqual(studio.etat_replique("data/son/Test/Origine.mp3"), "origine")
        ligne = self.studio.garder()
        self.assertEqual(ligne["remplace"], "data/studio/remplaces/Test/Origine.mp3")
        self.assertTrue(os.path.isfile(self.chemin("data", "studio", "remplaces", "Test", "Origine.mp3")))
        self.assertEqual(studio.lire_prises()["data/son/Test/Origine.mp3"]["texte"], "Origine.")
        # une deuxième prise remplace la première sans rien mettre de côté
        self.studio.traiter(prise(graine=2)[0], TAUX, "data/son/Test/Origine.mp3")
        self.assertIsNone(self.studio.garder()["remplace"])

    def test_un_wav_depose_ne_passe_plus_devant(self):
        self.studio.traiter(prise()[0], TAUX, "data/son/Test/Depose.wav")
        self.studio.garder()
        trouve = sons.trouver(self.chemin("data", "son", "Test", "Depose.wav"))
        self.assertTrue(trouve.endswith(".mp3"))
        self.assertTrue(os.path.isfile(self.chemin("data", "studio", "remplaces", "Test", "Depose.wav")))

    def test_rien_a_garder(self):
        resume = self.studio.traiter(np.zeros(TAUX, np.float32), TAUX, "data/son/Test/Synthese.mp3")
        self.assertEqual(resume["parole"], 0)
        self.assertIn("rien entendu", resume["conseils"][0])
        with self.assertRaises(ValueError):
            self.studio.garder()
        self.studio.traiter(prise()[0], TAUX, None)                       # essai libre
        with self.assertRaises(ValueError):
            self.studio.garder()
        with self.assertRaises(ValueError):
            self.studio.garder("../../ailleurs.mp3")

    def test_reglages_bornes_et_profil(self):
        self.studio.regler({"decalage_dt": 99, "debruitage": -3, "inconnu": 1})
        self.assertEqual(self.studio.reglages["valeurs"]["decalage_dt"], 8)
        self.assertEqual(self.studio.reglages["debruitage"], 0)
        self.studio.regler({"profil": "metal"})
        self.assertEqual(self.studio.reglages["valeurs"]["peigne_dose"], effet_voix.PROFILS["metal"]["peigne_dose"])
        self.assertEqual(studio.lire_reglages()["profil"], "metal")       # enregistré

    def test_appliquer_a_toutes(self):
        self.studio.traiter(prise()[0], TAUX, "data/son/Test/Synthese.mp3")
        self.studio.garder()
        self.studio.regler({"decalage_dt": 4.0})
        self.assertEqual(self.studio.compteurs(), {"gardees": 1, "anciennes": 1})
        travail = self.studio.appliquer_a_toutes()
        self.assertEqual((travail["fait"], travail["total"]), (1, 1), travail["message"])
        self.assertEqual(self.studio.compteurs()["anciennes"], 0)

    def test_etalonnage(self):
        with self.assertRaises(ValueError):
            self.studio.etalonner()
        for g in range(5):
            self.studio.traiter(prise(1.6, 108.0, g)[0], TAUX, None)
        self.assertGreaterEqual(self.studio.voix_disponible(), 6)
        etalonnage = self.studio.etalonner()
        self.assertAlmostEqual(etalonnage["hauteur_hz"], 108.0, delta=10)
        self.assertEqual(len(self.studio.reglages["egalisation"]), len(effet_voix.CENTRES) + 2)
        self.assertIsNotNone(studio.lire_reglages()["egalisation"])

    def test_anciens_reglages_migres(self):
        """Réglages de la première chaîne : curseurs remis aux valeurs mesurées, égalisation à refaire,
        hauteur habituelle et préférences gardées."""
        ancien = {"profil": "fidele", "valeurs": {"hauteur_hz": 137.0, "formants": 1.0, "reverbe_dose": 1.5},
                  "debruitage": 0.4, "egalisation": [[40, -30.0], [20000, -10.0]], "reference_hz": 115.4,
                  "etalonnage": {"date": "2026-11-22T18:46:44", "secondes": 21.3, "prises": 4},
                  "micro": "Casque", "verifier": False, "ecoute_auto": True}
        studio._ecrire_json(studio.CHEMIN_REGLAGES, ancien)
        r = studio.lire_reglages()
        self.assertEqual(r["version"], studio.VERSION_REGLAGES)
        self.assertEqual(r["valeurs"], studio.REGLAGES_DEFAUT["valeurs"])
        self.assertIsNone(r["egalisation"])
        self.assertIsNone(r["etalonnage"])
        self.assertEqual((r["reference_hz"], r["micro"], r["verifier"], r["debruitage"]), (115.4, "Casque", False, 0.4))


class Inventaire(unittest.TestCase):
    def test_toutes_les_repliques(self):
        lignes = studio.inventaire()
        ids = [l["id"] for l in lignes]
        self.assertEqual(len(ids), len(set(ids)))
        sources = {s: [l for l in lignes if l["source"] == s] for s in studio.SOURCES}
        self.assertEqual(len(sources["repliques"]), len(repliques.lire_script()))
        self.assertGreater(len(sources["origine"]), 30)
        self.assertGreater(len(sources["conversations"]), 100)
        for ligne in lignes:
            self.assertTrue(ligne["id"].startswith("data/son/") and ligne["id"].endswith(".mp3"), ligne)
            self.assertTrue(ligne["texte"].strip(), ligne)
            self.assertIn(ligne["etat"], studio.ETATS)
            self.assertNotIn("{", ligne["texte"], ligne)


if __name__ == "__main__":
    unittest.main()
