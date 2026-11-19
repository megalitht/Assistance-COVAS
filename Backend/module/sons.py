"""
sons.py — Fichiers audio du COVAS : les retrouver quelle que soit leur extension, les encoder en MP3.

Les répliques sont rangées en .mp3 (8 fois plus léger que le .wav, relu sans souci par pygame).
Un chemin écrit avec une extension retrouve aussi les autres : « data/son/X.wav » trouve
« data/son/X.mp3 » et inversement. On peut donc déposer un enregistrement en .wav ou en .mp3
sans toucher à barks.json ni à conversations.json.

Formats essayés : l'Opus (.ogg) n'est pas relu par pygame, et l'encodeur Vorbis de FFmpeg est
expérimental. Le MP3 (encodeur LAME, fourni avec PyAV, déjà installé pour Whisper) l'est.

Conversion des .wav existants (les originaux sont déplacés dans un dossier de sauvegarde) :
    python -m module.sons --convertir "D:\\Sauvegarde-wav"
"""
import os
import shutil
import sys
import wave

import numpy as np

EXTENSIONS = (".wav", ".mp3", ".ogg")          # ordre de préférence quand plusieurs existent :
                                               # un .wav enregistré à la main passe devant le .mp3
                                               # fabriqué par la synthèse au même chemin
DEBIT_VOIX = 64000                             # bits/s : répliques de synthèse (16 kHz, stéréo)
DEBIT_ENREGISTREMENT = 112000                  # bits/s : enregistrements 48 kHz


def est_son(chemin):
    return bool(chemin) and os.path.splitext(chemin)[1].lower() in EXTENSIONS


def trouver(chemin):
    """Chemin réel d'un son, quelle que soit l'extension écrite ; None s'il n'existe sous aucune."""
    if not chemin:
        return None
    base, extension = os.path.splitext(chemin)
    if extension.lower() not in EXTENSIONS:
        return chemin if os.path.isfile(chemin) else None
    for autre in EXTENSIONS:                   # toujours dans l'ordre de préférence, même si le
        if os.path.isfile(base + autre):       # chemin écrit existe : un .wav déposé gagne
            return base + autre
    return None


def encoder_mp3(x, taux, chemin, debit=DEBIT_VOIX):
    """Échantillons float (n ou n × 2, dans [-1, 1]) -> fichier .mp3."""
    import av                                   # PyAV : chargé seulement pour encoder
    x = np.asarray(x, dtype=np.float32)
    if x.ndim == 1:
        x = x[:, None]
    canaux = "stereo" if x.shape[1] == 2 else "mono"
    entiers = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    os.makedirs(os.path.dirname(os.path.abspath(chemin)), exist_ok=True)
    provisoire = chemin + ".partiel"
    with av.open(provisoire, "w", format="mp3") as sortie:
        flux = sortie.add_stream("libmp3lame", rate=taux)
        flux.layout = canaux
        flux.bit_rate = debit
        cadre = av.AudioFrame.from_ndarray(np.ascontiguousarray(entiers.reshape(1, -1)), format="s16", layout=canaux)
        cadre.sample_rate = taux
        reechantillonneur = av.AudioResampler(format=flux.format.name, layout=canaux, rate=taux)
        for morceau in [*reechantillonneur.resample(cadre), *reechantillonneur.resample(None), None]:
            for paquet in flux.encode(morceau):
                sortie.mux(paquet)
    os.replace(provisoire, chemin)             # jamais de fichier à moitié écrit au bon nom
    return chemin


def lire_wav(chemin):
    """Fichier .wav (8, 16, 24 ou 32 bits) -> (échantillons float n × canaux, taux)."""
    with wave.open(chemin, "rb") as w:
        largeur, canaux, taux = w.getsampwidth(), w.getnchannels(), w.getframerate()
        brut = w.readframes(w.getnframes())
    if largeur == 1:
        x = (np.frombuffer(brut, np.uint8).astype(np.float32) - 128) / 128
    elif largeur == 2:
        x = np.frombuffer(brut, "<i2").astype(np.float32) / 32768
    elif largeur == 3:
        octets = np.frombuffer(brut, np.uint8).reshape(-1, 3).astype(np.int32)
        v = octets[:, 0] | (octets[:, 1] << 8) | (octets[:, 2] << 16)
        x = np.where(v >= 1 << 23, v - (1 << 24), v).astype(np.float32) / (1 << 23)
    else:
        x = np.frombuffer(brut, "<i4").astype(np.float32) / 2 ** 31
    return x.reshape(-1, canaux), taux


def convertir_dossier(dossier, sauvegarde):
    """Chaque .wav de dossier (récursif) -> .mp3 au même endroit ; l'original part dans sauvegarde
    (même arborescence). Renvoie [(wav, mp3, octets avant, octets après)]."""
    faits = []
    for racine, _, fichiers in os.walk(dossier):
        for nom in sorted(fichiers):
            if not nom.lower().endswith(".wav"):
                continue
            wav = os.path.join(racine, nom)
            mp3 = os.path.splitext(wav)[0] + ".mp3"
            x, taux = lire_wav(wav)
            encoder_mp3(x, taux, mp3, DEBIT_ENREGISTREMENT if taux > 24000 else DEBIT_VOIX)
            copie = os.path.join(sauvegarde, os.path.relpath(wav, dossier))
            os.makedirs(os.path.dirname(copie), exist_ok=True)
            avant = os.path.getsize(wav)
            shutil.move(wav, copie)
            faits.append((wav, mp3, avant, os.path.getsize(mp3)))
    return faits


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "--convertir":
        print('Usage : python -m module.sons --convertir "dossier de sauvegarde des .wav"')
        sys.exit(1)
    dossier_sons = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "son")
    resultats = convertir_dossier(dossier_sons, sys.argv[2])
    for wav, mp3, avant, apres in resultats:
        print(f"{os.path.relpath(mp3, dossier_sons):60s} {avant / 1024:7.0f} Ko -> {apres / 1024:5.0f} Ko")
    total_avant = sum(r[2] for r in resultats)
    total_apres = sum(r[3] for r in resultats)
    print(f"{len(resultats)} fichiers : {total_avant / 1e6:.1f} Mo -> {total_apres / 1e6:.1f} Mo "
          f"(originaux dans {sys.argv[2]})")
