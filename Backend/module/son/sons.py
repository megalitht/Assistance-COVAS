"""
sons.py — Fichiers audio du COVAS : les retrouver quelle que soit leur extension, les encoder en MP3.

Les répliques sont rangées en .mp3 (8 fois plus léger que le .wav, relu sans souci par pygame).
Un chemin écrit avec une extension retrouve aussi les autres : « data/son/X.wav » trouve
« data/son/X.mp3 » et inversement. On peut donc déposer un enregistrement en .wav ou en .mp3
sans toucher à barks.json ni à conversations.json.

Formats essayés : l'Opus (.ogg) n'est pas relu par pygame, et l'encodeur Vorbis de FFmpeg est
expérimental. Le MP3 (encodeur LAME, fourni avec PyAV, déjà installé pour Whisper) l'est.
"""
import os
import wave

import numpy as np

EXTENSIONS = (".wav", ".mp3", ".ogg")          # ordre de préférence quand plusieurs existent :
                                               # un .wav enregistré à la main passe devant le .mp3
                                               # déjà présent au même chemin
DEBIT_VOIX = 64000                             # bits/s : sons à bas débit (jusqu'à 24 kHz)
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


def lire(chemin):
    """N'importe quel son (.wav, .mp3...) -> (échantillons float n × canaux, taux)."""
    if chemin.lower().endswith(".wav"):
        try:
            return lire_wav(chemin)
        except (wave.Error, EOFError):
            pass                                # .wav non PCM (flottant...) : PyAV s'en charge
    import av
    with av.open(chemin) as entree:
        flux = entree.streams.audio[0]
        disposition = flux.codec_context.layout
        canaux = len(disposition.channels)
        reechantillonneur = av.AudioResampler(format="flt", layout=disposition.name, rate=flux.rate)
        morceaux = []
        for cadre in entree.decode(flux):
            for sortie in reechantillonneur.resample(cadre):
                morceaux.append(sortie.to_ndarray().reshape(-1, canaux))
        for sortie in reechantillonneur.resample(None):
            morceaux.append(sortie.to_ndarray().reshape(-1, canaux))
        taux = flux.rate
    if not morceaux:
        return np.zeros((0, canaux), dtype=np.float32), taux
    return np.concatenate(morceaux).astype(np.float32), taux


def ecrire_wav(chemin, x, taux):
    """Écrit un .wav 16 bits, mono (tableau n) ou stéréo (tableau n × 2)."""
    donnees = (np.clip(np.asarray(x, dtype=np.float32), -1, 1) * 32767).astype("<i2")
    with wave.open(chemin, "wb") as f:
        f.setnchannels(1 if donnees.ndim == 1 else donnees.shape[1])
        f.setsampwidth(2)
        f.setframerate(taux)
        f.writeframes(donnees.tobytes())
    return chemin
