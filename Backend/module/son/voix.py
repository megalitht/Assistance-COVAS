import asyncio
import logging
import pygame

from module.son import audio, sons

_log = logging.getLogger(__name__)

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
        _log.warning(f"Sortie « {voulue} » indisponible ({erreur}) : sortie de Windows utilisée.")
        pygame.mixer.init(frequency=FREQUENCE)
    _sortie_ouverte = voulue


ouvrir_sortie()


async def generer_et_jouer_voix(chemin_audio: str):
    try:
        chemin = sons.trouver(chemin_audio)          # .mp3 ou .wav, quelle que soit l'extension écrite
        if not chemin:
            _log.warning(f"Fichier introuvable : {chemin_audio}")
            return

        ouvrir_sortie()
        pygame.mixer.music.load(chemin)
        pygame.mixer.music.play()
        pygame.mixer.music.set_volume(audio.volume())    # à refaire après chaque chargement

        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.1)

        pygame.mixer.music.unload()

    except Exception as e:
        _log.warning(f"Erreur lors de la lecture audio : {e}")
