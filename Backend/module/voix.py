import asyncio
import pygame
import os

pygame.mixer.init(frequency=16000)

async def generer_et_jouer_voix(chemin_audio: str): # On remplace 'texte' par 'chemin_audio'
    try:
        # 1. Vérification de sécurité
        if not chemin_audio or not os.path.exists(chemin_audio):
            print(f"[Moteur Vocal] Fichier introuvable : {chemin_audio}")
            return

        # 2. Chargement et lecture du fichier existant
        pygame.mixer.music.load(chemin_audio)
        pygame.mixer.music.play()
        
        # 3. On attend que le fichier ait fini de jouer
        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.1)
            
        # 4. Nettoyage de la mémoire (SANS SUPPRIMER LE FICHIER SUR LE DISQUE)
        pygame.mixer.music.unload()
            
    except Exception as e:
        print(f"[Moteur Vocal] Erreur lors de la lecture audio : {e}")