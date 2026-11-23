"""
audio_sortie.py — Petit programme à part pour les sorties audio (lancé par module/son/audio.py).

Il passe par la même bibliothèque que la voix du COVAS (pygame), donc voit les mêmes noms de
périphériques. Dans son propre processus, il ne dérange jamais une réplique en cours.

    python audio_sortie.py --lister                    -> liste JSON des sorties
    python audio_sortie.py --jouer son.mp3 "nom" 80    -> joue le son sur ce périphérique
"""
import json
import os
import sys
import time

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame  # noqa: E402

FREQUENCE = 16000           # comme module/son/voix.py


def lister():
    from pygame._sdl2 import audio as sdl
    pygame.mixer.init(frequency=FREQUENCE)
    try:
        return list(sdl.get_audio_device_names(False))
    finally:
        pygame.mixer.quit()


def jouer(chemin, nom, volume):
    pygame.mixer.init(frequency=FREQUENCE, devicename=nom or None)
    try:
        pygame.mixer.music.load(chemin)
        pygame.mixer.music.play()
        pygame.mixer.music.set_volume(volume / 100)
        while pygame.mixer.music.get_busy():
            time.sleep(0.05)
    finally:
        pygame.mixer.quit()


if __name__ == "__main__":
    try:
        if sys.argv[1] == "--lister":
            print(json.dumps(lister()))
        elif sys.argv[1] == "--jouer":
            jouer(sys.argv[2], sys.argv[3], float(sys.argv[4]))
        else:
            sys.exit(2)
    except Exception as erreur:
        print(erreur, file=sys.stderr)
        sys.exit(1)
