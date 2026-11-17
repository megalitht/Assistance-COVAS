# module/cerveau.py
import json
import os
import random

DOSSIER_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHEMIN_BARKS = os.path.join(DOSSIER_BACKEND, "data", "barks.json")
CHEMIN_SVP = os.path.join(DOSSIER_BACKEND, "data", "son", "Easter-egg", "SVP.wav")


def _existants(chemins):
    """Garde seulement les fichiers audio déjà enregistrés : barks.json peut ainsi lister
    à l'avance des répliques qui ne sont pas encore prêtes (voir SCRIPT_VOIX.md)."""
    complets = [os.path.join(DOSSIER_BACKEND, c) for c in chemins or [] if c]
    return [c for c in complets if os.path.exists(c)]


async def obtenir_chemin_audio(action: str, polite: bool = False) -> str:
    """
    Cherche et retourne le chemin d'un fichier audio depuis barks.json.
    Gère la politesse (30%) et les easter eggs génériques (15%).
    La réplique ne remplace jamais la commande : elle est seulement jouée avec elle.
    """
    if polite and random.random() < 0.30 and os.path.exists(CHEMIN_SVP):
        return CHEMIN_SVP

    try:
        with open(CHEMIN_BARKS, "r", encoding="utf-8") as f:
            barks = json.load(f)

        if action in barks:
            oeufs = _existants(barks[action].get("easter_egg"))
            if oeufs and random.random() < 0.15:
                return random.choice(oeufs)

            reponses = _existants(barks[action].get("reponses"))
            if reponses:
                return random.choice(reponses)

    except Exception as e:
        print(f"[Routeur Audio] Erreur lors de la lecture du JSON : {e}")

    return None
