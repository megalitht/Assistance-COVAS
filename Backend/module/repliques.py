"""
repliques.py — Fabrique les répliques fixes du COVAS (data/SCRIPT_VOIX.md) avec la voix de synthèse
(module/synthese.py : même voix et même profil que le rapport d'avarie), en .mp3.

Depuis Backend/ :
    python -m module.repliques             fabrique ce qui manque, et refait les répliques de
                                           synthèse dont la phrase, la voix ou le profil a changé
    python -m module.repliques --liste     montre ce qui serait fait, sans rien fabriquer
    python -m module.repliques --tout      refait toutes les répliques de synthèse
    python -m module.repliques NVG1 Lock2  refait seulement ces fichiers (nom sans extension)
    ... --verifier                          fait écouter chaque réplique par Whisper (le modèle du
                                           COVAS, sur le fichier : pas de micro) et refait jusqu'à
                                           PRISES_MAX prises si elle est mal comprise ; garde la meilleure

Les fichiers fabriqués sont notés dans data/son/repliques_synthese.json (phrase, voix, profil).
Un fichier qui n'y figure pas a été enregistré à la main : il n'est jamais touché. Pour remplacer
une réplique de synthèse par un enregistrement, dépose simplement le .wav au même chemin : il
passe devant le .mp3 (module/sons.py).

Les conversations (data/conversations.json) ne sont pas traitées ici.
"""
import difflib
import json
import os
import re
import shutil
import sys
import tempfile
import time
import unicodedata

import numpy as np

from module import sons, synthese

DOSSIER_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHEMIN_SCRIPT = os.path.join(DOSSIER_BACKEND, "data", "SCRIPT_VOIX.md")
CHEMIN_REGISTRE = os.path.join(DOSSIER_BACKEND, "data", "son", "repliques_synthese.json")
# | `cle` | `data/son/Dossier/Fichier.mp3` | Phrase à dire |
LIGNE = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|\s*(.+?)\s*\|\s*$")
PRISES_MAX = 8                  # --verifier : prises au plus pour une réplique mal comprise
BIEN_COMPRISE = 0.85            # ressemblance (sons prononcés) entre la phrase et ce que Whisper entend


# =====================================================================
#  VÉRIFICATION PAR WHISPER (option --verifier)
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


def a_faire(lignes, registre, tout=False, noms=None):
    """[(chemin relatif, phrase, raison)] : ce qu'il faut fabriquer, sans jamais toucher un
    enregistrement fait à la main."""
    signature = {"voix": synthese.VOIX, "profil": synthese.PROFIL}
    travail = []
    for _, relatif, phrase in lignes:
        nom = os.path.splitext(os.path.basename(relatif))[0]
        if noms and nom not in noms:
            continue
        mp3 = os.path.splitext(relatif)[0] + ".mp3"
        existant = sons.trouver(os.path.join(DOSSIER_BACKEND, relatif))
        note = registre.get(mp3)
        if existant and not note:
            continue                                        # enregistré à la main
        if existant and not existant.lower().endswith(".mp3"):
            continue                                        # .wav déposé par-dessus : il gagne
        if not existant:
            travail.append((mp3, phrase, "manquante"))
        elif tout or noms:
            travail.append((mp3, phrase, "demandée"))
        elif note != {"texte": phrase, **signature}:
            travail.append((mp3, phrase, "phrase ou voix changée"))
    return travail


def _une_prise(phrase, chemin):
    audio, taux = synthese.synthetiser_audio(phrase)
    if audio is None:
        return None
    sons.encoder_mp3(audio, taux, chemin)
    return len(audio) / taux


def fabriquer(travail, registre, verifier=False):
    signature = {"voix": synthese.VOIX, "profil": synthese.PROFIL}
    faits, mal_comprises = 0, []
    for i, (mp3, phrase, raison) in enumerate(travail, 1):
        debut = time.perf_counter()
        chemin = os.path.join(DOSSIER_BACKEND, *mp3.split("/"))
        duree = _une_prise(phrase, chemin)
        if duree is None:
            print("Synthèse indisponible : arrêt.")
            break
        avis = ""
        if verifier:
            # Piper varie un peu d'une prise à l'autre : on refait tant que Whisper comprend mal
            score, entendu = comprehension(chemin, phrase)
            prises = 1
            while score < BIEN_COMPRISE and prises < PRISES_MAX:
                essai = os.path.join(tempfile.gettempdir(), "covas_prise.mp3")
                duree_essai = _une_prise(phrase, essai)
                prises += 1
                score_essai, entendu_essai = comprehension(essai, phrase)
                if score_essai > score:
                    shutil.move(essai, chemin)
                    score, entendu, duree = score_essai, entendu_essai, duree_essai
            avis = f", compris à {score:.0%}" + (f" en {prises} prises" if prises > 1 else "")
            if score < BIEN_COMPRISE:
                mal_comprises.append((mp3, phrase, entendu, score))
        registre[mp3] = {"texte": phrase, **signature}
        ecrire_registre(registre)                            # à chaque fichier : rien de perdu si on coupe
        faits += 1
        print(f"[{i:3d}/{len(travail)}] {mp3:52s} {duree:4.1f} s "
              f"({(time.perf_counter() - debut) * 1000:4.0f} ms, {raison}{avis}) « {phrase} »", flush=True)
    if mal_comprises:
        print(f"\n{len(mal_comprises)} répliques restent mal comprises par Whisper (à écouter, ou phrase à reformuler) :")
        for mp3, phrase, entendu, score in mal_comprises:
            print(f"  {mp3:52s} {score:.0%}  « {phrase} » entendu « {entendu} »")
    return faits


def main(arguments):
    options = {a for a in arguments if a.startswith("--")}
    noms = {a for a in arguments if not a.startswith("--")}
    lignes = lire_script()
    registre = lire_registre()
    travail = a_faire(lignes, registre, tout="--tout" in options, noms=noms)
    manuels = sum(1 for _, r, _ in lignes
                  if sons.trouver(os.path.join(DOSSIER_BACKEND, r))
                  and os.path.splitext(r)[0] + ".mp3" not in registre)
    print(f"{len(lignes)} répliques dans le script : {len(travail)} à fabriquer, "
          f"{manuels} enregistrées à la main (jamais touchées). Voix {synthese.VOIX}, profil {synthese.PROFIL}.")
    if "--liste" in options:
        for mp3, phrase, raison in travail:
            print(f"  {mp3:52s} {raison:24s} « {phrase} »")
        return 0
    if not travail:
        return 0
    if synthese.charger() is None:
        return 1
    faits = fabriquer(travail, registre, verifier="--verifier" in options)
    print(f"{faits} répliques fabriquées.")
    return 0 if faits == len(travail) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
