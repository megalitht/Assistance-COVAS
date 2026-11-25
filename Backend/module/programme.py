"""
programme.py — Commande pour lancer une partie du COVAS dans un processus à part.

Depuis les sources :  python Backend/studio_vocal.py --service
Dans l'application :  COVAS.exe --studio --service   (app.py redirige vers le bon module)
"""
import os
import sys

DOSSIER_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = {
    "studio": os.path.join(DOSSIER_BACKEND, "studio_vocal.py"),
    "audio-sortie": os.path.join(DOSSIER_BACKEND, "module", "son", "audio_sortie.py"),
}


def commande(nom, *arguments):
    """Liste d'arguments pour subprocess : `nom` est une clé de SCRIPTS."""
    if getattr(sys, "frozen", False):
        return [sys.executable, f"--{nom}", *arguments]
    return [sys.executable, SCRIPTS[nom], *arguments]
