"""Réglages > Son : sans micro, sans haut-parleur, sans macros.py (PyAudio et pygame sont simulés)."""
import asyncio
import importlib
import json
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy  # noqa: E402,F401  (chargé une seule fois : les faux modules ci-dessous ne doivent pas le retirer)

from module import audio, ecoute, reglages, sons  # noqa: E402,F401


def appareil(index, nom, api=0, entrees=1, sorties=0, taux=44100.0):
    return {"index": index, "name": nom, "hostApi": api, "maxInputChannels": entrees,
            "maxOutputChannels": sorties, "defaultSampleRate": taux}


APPAREILS = [
    appareil(0, "Mappeur de sons Microsoft - Input", entrees=2),
    appareil(1, "Microphone (JBL Quantum910 Wire"),
    appareil(2, "Microphone (USB Audio)"),
    appareil(3, "Casque pour tÃ©lÃ©phone (JBL Quan"),
    appareil(4, "Haut-parleurs (JBL Quantum910 W", entrees=0, sorties=2),
    appareil(5, "Microphone (JBL Quantum910 Wireless Chat)", api=1),
    appareil(6, "Casque pour tÃ©lÃ©phone (JBL Quantum910 Wireless Chat)", api=1),
]


class FauxFlux:
    def __init__(self):
        self.ferme = False

    def stop_stream(self):
        pass

    def close(self):
        self.ferme = True


class FauxPyAudio:
    ouverts = []

    def get_default_host_api_info(self):
        return {"index": 0}

    def get_device_count(self):
        return len(APPAREILS)

    def get_device_info_by_index(self, i):
        return APPAREILS[i]

    def get_default_input_device_info(self):
        return APPAREILS[1]

    def get_default_output_device_info(self):
        return APPAREILS[4]

    def open(self, **options):
        flux = FauxFlux()
        FauxPyAudio.ouverts.append((options, flux))
        return flux

    def terminate(self):
        pass


FAUX_PYAUDIO = types.SimpleNamespace(PyAudio=FauxPyAudio, paInt16=8, paContinue=0)


class BaseAudio(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.addCleanup(self.dossier.cleanup)
        ancien = reglages.CHEMIN
        self.addCleanup(lambda: reglages.charger(ancien))
        reglages.charger(os.path.join(self.dossier.name, "reglages.json"))
        audio._index.update(nom=None, valeur=None, quand=-1e9)
        FauxPyAudio.ouverts = []
        patcheur = mock.patch.dict(sys.modules, {"pyaudio": FAUX_PYAUDIO})
        patcheur.start()
        self.addCleanup(patcheur.stop)

    def choisir(self, **valeurs):
        doc = reglages.document()
        doc["audio"].update(valeurs)
        reglages.enregistrer(doc)


class TestReglagesAudio(BaseAudio):
    def test_depart(self):
        self.assertEqual(reglages.audio(), {"entree": None, "sortie": None, "volume": 100})

    def test_enregistre_et_relit(self):
        self.choisir(entree="Microphone (USB Audio)", sortie="Casque", volume=35)
        reglages.charger()
        self.assertEqual(reglages.audio(), {"entree": "Microphone (USB Audio)", "sortie": "Casque", "volume": 35})
        with open(reglages.CHEMIN, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["audio"]["volume"], 35)

    def test_valeurs_invalides(self):
        for volume, attendu in ((140, 100), (-3, 0), (True, 100), ("fort", 100), (float("nan"), 100), (float("inf"), 100)):
            propre = reglages.nettoyer({"audio": {"volume": volume, "entree": 12, "sortie": "x" * 500}})["audio"]
            self.assertEqual(propre, {"entree": None, "sortie": None, "volume": attendu})
        self.assertEqual(reglages.nettoyer({"audio": "rien"})["audio"]["volume"], 100)


class TestPeripheriques(BaseAudio):
    def test_noms_repares(self):
        self.assertEqual(audio.reparer_nom("Casque pour tÃ©lÃ©phone"), "Casque pour téléphone")
        self.assertEqual(audio.reparer_nom("Microphone (USB)"), "Microphone (USB)")

    def test_liste(self):
        with mock.patch.object(audio, "_sorties", return_value=["Haut-parleurs (JBL Quantum910 Wireless Game)"]):
            infos = audio.peripheriques()
        self.assertEqual([e["nom"] for e in infos["entrees"]],
                         ["Microphone (JBL Quantum910 Wire", "Microphone (USB Audio)", "Casque pour tÃ©lÃ©phone (JBL Quan"])
        self.assertEqual(infos["entrees"][0]["libelle"], "Microphone (JBL Quantum910 Wireless Chat)")
        self.assertEqual(infos["entrees"][2]["libelle"], "Casque pour téléphone (JBL Quantum910 Wireless Chat)")
        self.assertEqual(infos["defaut_entree"], "Microphone (JBL Quantum910 Wireless Chat)")
        self.assertEqual(infos["defaut_sortie"], "Haut-parleurs (JBL Quantum910 Wireless Game)")
        self.assertIsNone(infos["erreur"])

    def test_sorties_illisibles(self):
        with mock.patch.object(audio, "_sorties", side_effect=OSError("panne")):
            infos = audio.peripheriques()
        self.assertTrue(infos["entrees"])
        self.assertIn("panne", infos["erreur"])

    def test_index_du_micro(self):
        self.assertIsNone(audio.index_micro())
        self.choisir(entree="Microphone (USB Audio)")
        self.assertEqual(audio.index_micro(), 2)

    def test_micro_debranche(self):
        self.choisir(entree="Micro disparu")
        self.assertIsNone(audio.index_micro())

    def test_micro_en_echec_passe_sur_windows(self):
        self.choisir(entree="Microphone (USB Audio)")
        self.assertEqual(audio.index_micro(), 2)
        audio.micro_en_echec()
        self.assertIsNone(audio.index_micro())


class TestMicro(BaseAudio):
    def test_ouvre_et_ferme(self):
        fin = []
        test = audio.TestMicro()
        self.assertTrue(test.demarrer("Microphone (USB Audio)", apres=lambda: fin.append(1))["ok"])
        options, flux = FauxPyAudio.ouverts[0]
        self.assertEqual(options["input_device_index"], 2)
        self.assertTrue(test.actif)
        test.arreter()
        self.assertTrue(flux.ferme)
        self.assertFalse(test.actif)
        self.assertEqual(fin, [1])

    def test_niveau(self):
        import numpy as np
        test = audio.TestMicro()
        test.demarrer()
        self.addCleanup(test.arreter)
        test._recu((np.full(100, 3276, dtype=np.int16)).tobytes(), 100, None, 0)
        self.assertAlmostEqual(test.niveau()["db"], -20, delta=0.2)
        self.assertEqual(test.niveau()["db"], -120)

    def test_micro_absent(self):
        test = audio.TestMicro()
        self.assertIn("erreur", test.demarrer("Micro disparu"))
        self.assertFalse(test.actif)
        self.assertFalse(FauxPyAudio.ouverts)


class TestVoix(BaseAudio):
    """module.voix avec un faux pygame : aucun son n'est joué."""

    def charger_voix(self):
        mixer = mock.MagicMock()
        mixer.get_init.return_value = (16000, -16, 2)
        mixer.music.get_busy.return_value = False
        faux = types.SimpleNamespace(mixer=mixer, error=RuntimeError)
        patcheur = mock.patch.dict(sys.modules, {"pygame": faux})
        patcheur.start()
        self.addCleanup(patcheur.stop)
        sys.modules.pop("module.voix", None)
        self.addCleanup(sys.modules.pop, "module.voix", None)
        return importlib.import_module("module.voix"), mixer

    def test_sortie_et_volume(self):
        self.choisir(sortie="Casque", volume=40)
        voix, mixer = self.charger_voix()
        mixer.init.assert_called_once_with(frequency=16000, devicename="Casque")
        with mock.patch.object(voix.sons, "trouver", return_value="essai.mp3"):
            asyncio.run(voix.generer_et_jouer_voix("essai.mp3"))
        mixer.music.set_volume.assert_called_with(0.4)
        self.assertEqual(mixer.init.call_count, 1)      # même sortie : le mixeur reste ouvert

    def test_change_de_sortie(self):
        voix, mixer = self.charger_voix()
        self.choisir(sortie="Haut-parleurs")
        voix.ouvrir_sortie()
        mixer.quit.assert_called()
        mixer.init.assert_called_with(frequency=16000, devicename="Haut-parleurs")

    def test_sortie_absente(self):
        self.choisir(sortie="Casque disparu")
        mixer = mock.MagicMock()
        mixer.get_init.return_value = None
        mixer.init.side_effect = [RuntimeError("absent"), None]
        faux = types.SimpleNamespace(mixer=mixer, error=RuntimeError)
        with mock.patch.dict(sys.modules, {"pygame": faux}):
            sys.modules.pop("module.voix", None)
            importlib.import_module("module.voix")
            sys.modules.pop("module.voix", None)
        self.assertEqual(mixer.init.call_args_list[-1], mock.call(frequency=16000))


class TestPauseEcoute(BaseAudio):
    """Le test du micro et le studio suspendent l'écoute : elle ne reprend qu'une fois les deux finis."""

    def setUp(self):
        super().setUp()
        import app
        self.api = app.Api()
        ecoute.PAUSE.clear()
        self.addCleanup(ecoute.PAUSE.clear)
        self.addCleanup(audio.TEST_MICRO.arreter)

    def test_pendant_le_test(self):
        self.assertTrue(self.api.audio_micro_demarrer()["ok"])
        self.assertTrue(ecoute.PAUSE.is_set())
        self.api.audio_micro_arreter()
        self.assertFalse(ecoute.PAUSE.is_set())

    def test_micro_inaccessible(self):
        self.assertIn("erreur", self.api.audio_micro_demarrer("Micro disparu"))
        self.assertFalse(ecoute.PAUSE.is_set())

    def test_studio_garde_la_pause(self):
        self.api._suspendre_ecoute("studio")
        self.api.audio_micro_demarrer()
        self.api.audio_micro_arreter()
        self.assertTrue(ecoute.PAUSE.is_set())
        self.api._reprendre_ecoute("studio")
        self.assertFalse(ecoute.PAUSE.is_set())

    def test_cache_vide_sans_toucher_au_reste(self):
        import app
        with tempfile.TemporaryDirectory() as profil:
            defaut = os.path.join(profil, "EBWebView", "Default")
            for dossier in ("Cache", "Code Cache", "Local Storage"):
                os.makedirs(os.path.join(defaut, dossier))
            with mock.patch.object(app, "DOSSIER_PROFIL", profil):
                app._vider_cache_page()
            self.assertEqual(os.listdir(defaut), ["Local Storage"])


if __name__ == "__main__":
    unittest.main()
