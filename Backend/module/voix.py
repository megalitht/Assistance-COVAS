import asyncio
import pygame

from module import sons

pygame.mixer.init(frequency=16000)

async def generer_et_jouer_voix(chemin_audio: str):
    try:
        chemin = sons.trouver(chemin_audio)          # .mp3 ou .wav, quelle que soit l'extension écrite
        if not chemin:
            print(f"[Moteur Vocal] Fichier introuvable : {chemin_audio}")
            return

        pygame.mixer.music.load(chemin)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.1)

        pygame.mixer.music.unload()

    except Exception as e:
        print(f"[Moteur Vocal] Erreur lors de la lecture audio : {e}")
