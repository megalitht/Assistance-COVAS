"""
repliques.py — Outils du studio vocal pour les répliques fixes du COVAS (data/SCRIPT_VOIX.md) :
lecture du script, écoute d'un fichier par Whisper (pas de micro), et registre
data/son/repliques_synthese.json : les anciens fichiers de synthèse qui restent à réenregistrer.
Le studio retire une réplique de ce registre dès qu'elle est gardée avec ta voix.
"""
import difflib
import json
import os
import re
import sys
import unicodedata

import numpy as np

from module.son import sons

DOSSIER_BACKEND = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHEMIN_SCRIPT = os.path.join(DOSSIER_BACKEND, "data", "SCRIPT_VOIX.md")
CHEMIN_REGISTRE = os.path.join(DOSSIER_BACKEND, "data", "son", "repliques_synthese.json")
# | `cle` | `data/son/Dossier/Fichier.mp3` | Phrase à dire |
LIGNE = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|\s*(.+?)\s*\|\s*$")


# =====================================================================
#  VÉRIFICATION PAR WHISPER
# =====================================================================
_oreille = {}


def _whisper():
    """Le modèle Whisper du COVAS (carte graphique, comme main.py ; processeur sinon)."""
    if "modele" not in _oreille:
        nvidia = os.path.join(sys.prefix, "Lib", "site-packages", "nvidia")
        for sous in ("cublas", "cudnn"):
            dossier = os.path.join(nvidia, sous, "bin")
            if os.path.isdir(dossier):
                os.environ["PATH"] = dossier + ";" + os.environ.get("PATH", "")
                os.add_dll_directory(dossier)
        from faster_whisper import WhisperModel
        chemin = os.path.join(DOSSIER_BACKEND, "module", "modele_vocal_turbo")
        if not os.path.exists(os.path.join(chemin, "model.bin")):
            chemin = os.path.join(DOSSIER_BACKEND, "module", "modele_vocal_fr")
        try:
            _oreille["modele"] = WhisperModel(chemin, device="cuda", compute_type="float16")
            segments, _ = _oreille["modele"].transcribe(np.zeros(16000, np.float32), language="fr")
            list(segments)                          # la transcription est paresseuse : on la force
        except Exception:
            _oreille["modele"] = WhisperModel(chemin, device="cpu", compute_type="int8")
    return _oreille["modele"]


def _sons_prononces(texte):
    """Lettres seulement, sans accents ni finales muettes : « Boucliers rétablis » ~ « Bouclier rétabli »."""
    texte = unicodedata.normalize("NFKD", texte.lower().replace("œ", "oe"))
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    mots = [CHIFFRES.get(m, m) for m in re.findall(r"[a-z0-9]+", texte)]      # « 0 » se dit « zéro »
    return "".join(re.sub(r"(es|s|x|t|e)$", "", m) if len(m) > 3 else m for m in mots)


CHIFFRES = dict(zip("0123456789", ["zero", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf"]))


def comprehension(chemin, phrase):
    """(ressemblance 0 à 1, ce que Whisper a entendu)."""
    segments, _ = _whisper().transcribe(chemin, language="fr", beam_size=5)
    entendu = " ".join(s.text for s in segments).strip()
    return difflib.SequenceMatcher(None, _sons_prononces(phrase), _sons_prononces(entendu)).ratio(), entendu


def lire_script(chemin=CHEMIN_SCRIPT):
    """[(clé, chemin relatif à Backend/, phrase)] dans l'ordre du script."""
    lignes = []
    with open(chemin, encoding="utf-8") as f:
        for ligne in f:
            m = LIGNE.match(ligne.strip())
            if m and sons.est_son(m.group(2)):
                lignes.append((m.group(1), m.group(2), m.group(3)))
    return lignes


def lire_registre():
    try:
        with open(CHEMIN_REGISTRE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def ecrire_registre(registre):
    os.makedirs(os.path.dirname(CHEMIN_REGISTRE), exist_ok=True)
    provisoire = CHEMIN_REGISTRE + ".partiel"
    with open(provisoire, "w", encoding="utf-8", newline="\r\n") as f:
        json.dump(dict(sorted(registre.items())), f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(provisoire, CHEMIN_REGISTRE)
