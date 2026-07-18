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

# Importation de nos modules personnalisés situés dans le sous-dossier 'module'
from module.macros import executer_touches 
from module.cerveau import generer_replique_ia
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
        for mot_cle in donnees["mots_cles"]:
            if mot_cle in texte_entendu:
                return cle_action 
    return None

# --- CHARGEMENT DES RÉPLIQUES ET PARAMÈTRES (BARKS) ---
chemin_barks = "D:/Assistance-COVAS/Backend/data/barks.json" 
with open(chemin_barks, "r", encoding="utf-8") as fichier:
    barks = json.load(fichier)

# Extraire dynamiquement les mots de réveil depuis le JSON
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
            
            prompt_contexte = "Eve, COVAS, Elite Dangerous, pips, moteurs, boucliers, soute, train d'atterrissage."
            
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


# --- ARCHITECTURE DU BACKEND ASYNCHRONE ---
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

            # Kokoro génère et joue le son de manière nativement asynchrone !
            await generer_et_jouer_voix(texte_a_dire)

            self.tts_queue.task_done()

    async def tache_execution_macros(self):
        """Dépile et exécute les macros clavier de manière asynchrone via le module externe."""
        loop = asyncio.get_running_loop()
        while True:
            action = await self.action_queue.get()
            print(f"[Action] Demande d'exécution pour : {action}")
            
            # Exécution de la fonction importée dans un thread séparé
            await loop.run_in_executor(None, executer_touches, action)
            
            self.action_queue.task_done()

    async def boucle_principale(self):
        print("COVAS Opérationnel et asynchrone.")
        asyncio.create_task(self.tache_lecture_audio())
        asyncio.create_task(self.tache_execution_macros())
        
        while True:
            # L'écoute Whisper est envoyée dans un thread pour ne pas bloquer le script
            text = await asyncio.to_thread(ecouter, silencieux=True)
            
            if text:
                text_min = text.lower()
                
                # 1. VÉRIFICATION DU MOT DE RÉVEIL
                reveil_detecte = any(mot in text_min for mot in MOTS_REVEIL)
                if not reveil_detecte:
                    continue

                print(f">>>> Mot de réveil détecté dans : {text}")

                # 2. CAS OÙ TU DIS JUSTE LE NOM (Interpellation)
                mots_nettoyes = "".join(caractere for caractere in text_min if caractere.isalpha())
                if mots_nettoyes in MOTS_REVEIL:
                    print("Activation vocale. En attente de la commande...")
                    
                    # On demande au LLM de générer une réplique d'interpellation
                    replique_reveil = await generer_replique_ia("mots_reveil")
                    await self.tts_queue.put(replique_reveil)
                    
                    print(">>>> [ÉCOUTE ACTIVE DÉCLENCHÉE - PARLEZ MAINTENANT]")
                    text = await asyncio.to_thread(ecouter, silencieux=False)
                    if not text:
                        print("Délai d'attente dépassé. Retour en veille.")
                        continue
                    text_min = text.lower()

                # 3. EXÉCUTION DES COMMANDES DYNAMIQUES VIA LES QUEUES
                action_detectee = detecter_action(text_min)
                
                if action_detectee:
                    # 1. Macro immédiate (Priorité absolue en jeu)
                    await self.action_queue.put(action_detectee)
                    # 2. Génération de la voix par le LLM en tâche de fond
                    replique = await generer_replique_ia(action_detectee)
                    await self.tts_queue.put(replique)
                    # ON ATTEND QUE LE COVAS AIT FINI DE PARLER AVANT DE RE-ÉCOUTER
                    await self.tts_queue.join()
                    
                # Gestion des cas spécifiques hors de la structure JSON
                elif "reset" in text_min or "réinitialise" in text_min or "équilibre" in text_min:
                    await self.action_queue.put("reset")
                    replique = await generer_replique_ia("reset")
                    await self.tts_queue.put(replique)
                    await self.tts_queue.join()
                    
                elif "lock" in text_min or "euq" in text_min:
                    await self.action_queue.put("lock")
                    replique = await generer_replique_ia("lock")
                    await self.tts_queue.put(replique)
                    await self.tts_queue.join()

                elif "boost" in text_min or "propulsion" in text_min:
                    await self.action_queue.put("boost")
                    replique = await generer_replique_ia("boost")
                    await self.tts_queue.put(replique)
                    await self.tts_queue.join()
                
                elif "fsd" in text_min or "hyperespace" in text_min:
                    await self.action_queue.put("fsd")
                    replique = await generer_replique_ia("fsd")
                    await self.tts_queue.put(replique)
                    await self.tts_queue.join()

                # --- AJOUT DES MODES DE VOL MANQUANTS ---
                elif "mode" in text_min and "combat" in text_min:
                    await self.action_queue.put("mode_combat")
                    replique = await generer_replique_ia("mode_combat")
                    await self.tts_queue.put(replique)

                elif "mode" in text_min and "croisière" in text_min:
                    await self.action_queue.put("mode_croisiere")
                    replique = await generer_replique_ia("mode_croisiere")
                    await self.tts_queue.put(replique)

                elif "mode" in text_min and "récupération" in text_min:
                    await self.action_queue.put("mode_récuperation")
                    replique = await generer_replique_ia("mode_récuperation")
                    await self.tts_queue.put(replique)
                
                else:
                    print(f"[Discussion] Envoi de la question libre à l'IA : '{text_min}'")
                    replique_libre = await generer_replique_ia("discussion", texte_utilisateur=text)
                    await self.tts_queue.put(replique_libre)
                    # CRITIQUE ICI AUSSI : On attend la fin de la réponse libre !
                    await self.tts_queue.join()

# Lancement propre de la boucle asynchrone principale
if __name__ == "__main__":
    backend = CovasBackend()
    asyncio.run(backend.boucle_principale())