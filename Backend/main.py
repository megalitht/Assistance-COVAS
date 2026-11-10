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
import traceback
import sounddevice as sd
import numpy as np
import winsound



# Importation de nos modules personnalisés situés dans le sous-dossier 'module'
from module.actions import executer_commande
from module.cerveau import obtenir_chemin_audio
from module.lecteur_logs import surveiller_logs, surveiller_status_json, surveiller_fichiers_auxiliaires
from module.voix import generer_et_jouer_voix
from module.serveur_ws import demarrer_serveur_web

# --- CONFIGURATION AUTOMATIQUE DES PATHS NVIDIA POUR LE VENV ---
venv_site_packages = next((p for p in sys.path if 'site-packages' in p), None)

if venv_site_packages:
    cublas_path = os.path.join(venv_site_packages, "nvidia", "cublas", "bin")
    cudnn_path = os.path.join(venv_site_packages, "nvidia", "cudnn", "bin")
    
    os.environ["PATH"] = f"{cublas_path};{cudnn_path};" + os.environ.get("PATH", "")
    if hasattr(os, 'add_dll_directory'):
        if os.path.exists(cublas_path): 
            os.add_dll_directory(cublas_path)
        if os.path.exists(cudnn_path): 
            os.add_dll_directory(cudnn_path)
            

# Clés de barks.json qui ne sont pas des commandes
CLES_IGNOREES = {"mots_reveil", "politesse"}


def detecter_action(texte_entendu):
    """Trouve l'action dont le mot-clé reconnu est le plus précis (le plus long).
    Ex. « réarme » (ravitaillement) l'emporte sur « arme » (énergie aux armes)."""
    meilleure, longueur = None, 0
    for cle_action, donnees in barks.items():
        if cle_action in CLES_IGNOREES or not isinstance(donnees, dict):
            continue
        for mot_cle in donnees.get("mots_cles", []):
            mot_cle = mot_cle.lower()
            if mot_cle and mot_cle in texte_entendu and len(mot_cle) > longueur:
                meilleure, longueur = cle_action, len(mot_cle)
    return meilleure

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

    async def dire(self, *cles, poli=False):
        """Joue la première réplique disponible parmi les clés de barks.json données."""
        for cle in cles:
            chemin = await obtenir_chemin_audio(cle, polite=poli)
            if chemin:
                await self.tts_queue.put(chemin)
                return True
        return False

    async def tache_execution_macros(self):
        """Exécute les commandes (voix ou boutons de l'interface), une à la fois."""
        while True:
            commande = await self.action_queue.get()
            action, texte, poli = commande if isinstance(commande, tuple) else (commande, "", False)
            print(f"[Action] Demande d'exécution pour : {action}")
            try:
                await executer_commande(action, texte, self.dire, poli)
            except Exception:
                print(f"[Action] Erreur pendant « {action} » :")
                traceback.print_exc()
            finally:
                self.action_queue.task_done()

    def lancer_tache(self, coroutine, nom):
        """Lance une tâche de fond en gardant une référence dessus (sinon Python peut
        la supprimer en pleine exécution) et affiche son erreur si elle plante."""
        tache = asyncio.create_task(coroutine, name=nom)
        self.taches.add(tache)

        def fin_de_tache(t):
            self.taches.discard(t)
            if not t.cancelled() and t.exception():
                print(f"[Erreur] La tâche « {nom} » s'est arrêtée :")
                traceback.print_exception(t.exception())

        tache.add_done_callback(fin_de_tache)

    async def boucle_principale(self):
        print("COVAS Opérationnel.")
        self.taches = set()
        # Le serveur de l'interface d'abord, pour que l'écran se connecte au plus vite
        self.lancer_tache(demarrer_serveur_web(self.action_queue), "serveur web")
        self.lancer_tache(self.tache_lecture_audio(), "lecture audio")
        self.lancer_tache(self.tache_execution_macros(), "macros")

        self.lancer_tache(surveiller_logs(self.tts_queue, obtenir_chemin_audio), "journal")
        self.lancer_tache(surveiller_status_json(), "Status.json")
        self.lancer_tache(surveiller_fichiers_auxiliaires(), "fichiers auxiliaires")

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
                    await self.action_queue.put((action_detectee, text_min, polite))
                    # On attend la fin de la commande et de la réponse avant de réécouter le micro
                    await self.action_queue.join()
                    await self.tts_queue.join()
if __name__ == "__main__":
    backend = CovasBackend()
    asyncio.run(backend.boucle_principale())