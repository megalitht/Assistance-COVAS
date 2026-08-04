import asyncio
import pygame
import os

pygame.mixer.init(frequency=16000)

async def generer_et_jouer_voix(chemin_audio: str):
    try:
        if not chemin_audio or not os.path.exists(chemin_audio):
            print(f"[Moteur Vocal] Fichier introuvable : {chemin_audio}")
            return

        pygame.mixer.music.load(chemin_audio)
        pygame.mixer.music.play()
        
        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.1)
            
        pygame.mixer.music.unload()
            
    except Exception as e:
        print(f"[Moteur Vocal] Erreur lors de la lecture audio : {e}")