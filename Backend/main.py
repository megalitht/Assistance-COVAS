import os
import sys
import speech_recognition as sr
import pyaudio
import struct
import math
import pydirectinput
from faster_whisper import WhisperModel
import json
import random
import asyncio
import sounddevice as sd
import numpy as np
import winsound

# Importation de nos modules personnalisés situés dans le sous-dossier 'module'
from module.macros import executer_touches 
from module.cerveau import obtenir_chemin_audio
from module.lecteur_logs import surveiller_logs, surveiller_status_json
from module.voix import generer_et_jouer_voix

# --- CONFIGURATION AUTOMATIQUE DES PATHS NVIDIA POUR LE VENV ---
venv_site_packages = next((p for p in sys.path if 'site-packages' in p), None)

if venv_site_packages:
    cublas_path = os.path.join(venv_site_packages, "nvidia", "cublas", "bin")
    cudnn_path = os.path.join(venv_site_packages, "nvidia", "cudnn", "bin")
    
    os.environ["PATH"] = f"{cublas_path};{cudnn_path};" + os.environ.get("PATH", "")
    if hasattr(os, 'add_dll_directory'):
        if os.path.exists(cublas_path): os.add_dll_directory(cublas_path)
        if os.path.exists(cudnn_path): os.add_dll_directory(cudnn_path)
            

def detecter_action(texte_entendu):
    """Parcourt le JSON pour trouver à quelle action correspond la phrase"""
    for cle_action, donnees in barks.items():
        if cle_action == "mots_reveil":
            continue
        
        # Vérification de sécurité : on s'assure que donnees est un dictionnaire avec la clé voulue
        if isinstance(donnees, dict) and "mots_cles" in donnees:
            for mot_cle in donnees["mots_cles"]:
                if mot_cle in texte_entendu:
                    return cle_action 
    return None

# --- CHARGEMENT DES RÉPLIQUES ET PARAMÈTRES (BARKS) ---
chemin_barks = "D:/Assistance-COVAS/Backend/data/barks.json" 
with open(chemin_barks, "r", encoding="utf-8") as fichier:
    barks = json.load(fichier)

# Extraire les mots de réveil depuis le JSON
MOTS_REVEIL = barks["mots_reveil"]["mots_cles"]

# --- INITIALISATION IA (WHISPER) ---
chemin_vers_fichiers = "D:/Assistance-COVAS/Backend/module/modele_vocal_fr"
print("Chargement du modèle d'IA vocal local...")
modele_vocal = WhisperModel(chemin_vers_fichiers, device="cuda", compute_type="float16")


def ecouter(silencieux=False):
    """Capte le son du micro et le transcrit localement avec Whisper"""
    r = sr.Recognizer()
    with sr.Microphone() as source:
        if not silencieux:
            print("Écoute...")
        r.adjust_for_ambient_noise(source, duration=0.3)
        try:
            audio = r.listen(source, timeout=3, phrase_time_limit=7)
            chemin_wav = "D:/Assistance-COVAS/Backend/data/temp.wav"
            with open(chemin_wav, "wb") as f:
                f.write(audio.get_wav_data())
            
            prompt_contexte = "COVAS, Elite Dangerous, pips, moteurs, boucliers, soute, train d'atterrissage."
            
            segments, info = modele_vocal.transcribe(
                chemin_wav, 
                beam_size=3, 
                language="fr", 
                initial_prompt=prompt_contexte
            )
            texte = "".join([segment.text for segment in segments]).strip()
            return texte
        except sr.WaitTimeoutError:
            pass
        except Exception as e:
            print(f"Erreur lors de la capture : {e}")
    return ""


class CovasBackend:
    def __init__(self):
        self.tts_queue = asyncio.Queue()
        self.action_queue = asyncio.Queue()
        
    async def generer_audio_tts(self, action_ou_texte: str):
        await self.tts_queue.put(action_ou_texte)

    async def tache_lecture_audio(self):
        while True:
            texte_a_dire = await self.tts_queue.get()
            print(f"[COVAS] {texte_a_dire}")

            await generer_et_jouer_voix(texte_a_dire)

            self.tts_queue.task_done()

    async def tache_execution_macros(self):
        """Dépile et exécute les macros clavier de manière asynchrone via le module externe."""
        loop = asyncio.get_running_loop()
        while True:
            action = await self.action_queue.get()
            print(f"[Action] Demande d'exécution pour : {action}")
            
            await loop.run_in_executor(None, executer_touches, action)
            
            self.action_queue.task_done()

    async def boucle_principale(self):
        print("COVAS Opérationnel.")
        asyncio.create_task(self.tache_lecture_audio())
        asyncio.create_task(self.tache_execution_macros())

        asyncio.create_task(surveiller_logs(self.tts_queue, obtenir_chemin_audio))
        asyncio.create_task(surveiller_status_json())
        
        while True:
            text = await asyncio.to_thread(ecouter, silencieux=True)
            
            if text:
                text_min = text.lower()
                
                reveil_detecte = any(mot in text_min for mot in MOTS_REVEIL)
                if not reveil_detecte:
                    continue

                print(f">>>> Mot de réveil détecté dans : {text}")

                polite = False

                texte_epure = text_min.replace(",", "").replace(".", "").replace("!", "").replace("?", "").strip()
                
                if texte_epure in MOTS_REVEIL:
                    print("Activation vocale. En attente de la commande...")
                    
                    chemin_reveil = await obtenir_chemin_audio("mots_reveil")
                    if chemin_reveil:
                        await self.tts_queue.put(chemin_reveil)
                        await self.tts_queue.join()
                    
                    print(">>>> [ÉCOUTE ACTIVE DÉCLENCHÉE - PARLEZ MAINTENANT]")
                    text = await asyncio.to_thread(ecouter, silencieux=False)
                    if not text:
                        print("Délai d'attente dépassé. Retour en veille.")
                        continue
                    text_min = text.lower()

                # On détecte la politesse dans la commande finale
                if "s'il te pla" in text_min or "stp" in text_min or "s'il te plaîs" in text_min:
                    polite = True

                action_detectee = detecter_action(text_min)
                
                if action_detectee:
                    await self.action_queue.put(action_detectee)
                    
                    chemin_audio = await obtenir_chemin_audio(action_detectee, polite=polite)
                    
                    if chemin_audio:
                        await self.tts_queue.put(chemin_audio)
                        await self.tts_queue.join()
                    else:
                        print(f"[COVAS] Avertissement : Aucun fichier audio associé à l'action '{action_detectee}'")
if __name__ == "__main__":
    backend = CovasBackend()
    asyncio.run(backend.boucle_principale())
