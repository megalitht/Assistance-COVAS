import asyncio
import pygame

from module.son import audio, sons

FREQUENCE = 16000
_sortie_ouverte = False      # False : rien d'ouvert ; None : la sortie de Windows ; sinon son nom


def ouvrir_sortie():
    """Ouvre la sortie choisie dans Réglages > Son, si elle a changé depuis la dernière réplique."""
    global _sortie_ouverte
    voulue = audio.sortie()
    if voulue == _sortie_ouverte and pygame.mixer.get_init():
        return
    pygame.mixer.quit()
    try:
        pygame.mixer.init(frequency=FREQUENCE, devicename=voulue)
    except pygame.error as erreur:
        print(f"[Moteur Vocal] Sortie « {voulue} » indisponible ({erreur}) : sortie de Windows utilisée.")
        pygame.mixer.init(frequency=FREQUENCE)
    _sortie_ouverte = voulue


ouvrir_sortie()


async def generer_et_jouer_voix(chemin_audio: str):
    try:
        chemin = sons.trouver(chemin_audio)          # .mp3 ou .wav, quelle que soit l'extension écrite
        if not chemin:
            print(f"[Moteur Vocal] Fichier introuvable : {chemin_audio}")
            return

        ouvrir_sortie()
        pygame.mixer.music.load(chemin)
        pygame.mixer.music.play()
        pygame.mixer.music.set_volume(audio.volume())    # à refaire après chaque chargement

        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.1)

        pygame.mixer.music.unload()

    except Exception as e:
        print(f"[Moteur Vocal] Erreur lors de la lecture audio : {e}")
