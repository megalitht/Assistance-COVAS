"""
whisper.py — Modèle de reconnaissance vocale (Whisper), pour le COVAS et le studio vocal.

Carte graphique NVIDIA : grand modèle (modele_vocal_turbo, large-v3-turbo, bien meilleur en
français). Sans elle, ou si elle refuse : petit modèle (modele_vocal_fr) sur le processeur,
où le grand serait trop lent. Si un seul des deux dossiers existe, il sert dans tous les cas.
"""
import glob
import logging
import os
import sys

import numpy as np

_log = logging.getLogger(__name__)

DOSSIER_BACKEND = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELE_GRAND = os.path.join(DOSSIER_BACKEND, "module", "modele_vocal_turbo")
MODELE_PETIT = os.path.join(DOSSIER_BACKEND, "module", "modele_vocal_fr")
_cuda = {"prepare": False}


def _preparer_cuda():
    """Bibliothèques NVIDIA (cuBLAS, cuDNN) : installées par pip, ou copiées dans l'application."""
    if _cuda["prepare"]:
        return
    _cuda["prepare"] = True
    bases = [p for p in sys.path if p.endswith("site-packages")]
    if getattr(sys, "frozen", False):
        bases.insert(0, sys._MEIPASS)
    for base in bases:
        for dossier in glob.glob(os.path.join(base, "nvidia", "*", "bin")):
            os.environ["PATH"] = dossier + os.pathsep + os.environ.get("PATH", "")
            os.add_dll_directory(dossier)


def _existe(modele):
    return os.path.exists(os.path.join(modele, "model.bin"))


def charger(signaler=None):
    """Charge le modèle. `signaler(texte)` : étape affichée à l'écran d'accueil (facultatif)."""
    _preparer_cuda()
    import ctranslate2
    from faster_whisper import WhisperModel

    signaler = signaler or (lambda texte: None)
    if ctranslate2.get_cuda_device_count() > 0:
        signaler("Transfert du modèle vocal vers la carte graphique")
        types = ctranslate2.get_supported_compute_types("cuda")
        try:
            modele = WhisperModel(MODELE_GRAND if _existe(MODELE_GRAND) else MODELE_PETIT, device="cuda",
                                  compute_type="float16" if "float16" in types else "int8")
            # La transcription est paresseuse : une bibliothèque NVIDIA manquante ne se voit qu'ici
            segments, _ = modele.transcribe(np.zeros(16000, np.float32), language="fr")
            list(segments)
            return modele
        except Exception:
            _log.exception("Carte graphique inutilisable : reconnaissance vocale sur le processeur")
    signaler("Chargement du modèle vocal (processeur)")
    return WhisperModel(MODELE_PETIT if _existe(MODELE_PETIT) else MODELE_GRAND, device="cpu",
                        compute_type="int8")
