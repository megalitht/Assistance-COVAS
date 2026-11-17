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
from module.actions import executer_commande, surveiller_reactions
from module.cerveau import obtenir_chemin_audio
from module.lecteur_logs import surveiller_logs, surveiller_status_json, surveiller_fichiers_auxiliaires
from module.voix import generer_et_jouer_voix
from module.serveur_ws import demarrer_serveur_web
from module.comprehension import trouver_action, contient_reveil, est_reveil_seul, vocabulaire_pour_whisper

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


# Formules de politesse : on les repère, puis on les retire de la phrase pour qu'elles
# ne gênent jamais la reconnaissance de la commande (« active le FSD s'il te plaît »).
FORMULES_POLITESSE = ("s'il te plaît", "s'il te plait", "s'il te plaîs", "s'il vous plaît",
                      "s'il vous plait", "si il te plaît", "si te plaît", "steuplaît",
                      "stp", "svp")


def separer_politesse(texte):
    """Renvoie (phrase sans la formule de politesse, True si le commandant a été poli)."""
    texte = texte.replace("\u2019", "'").replace("`", "'")     # apostrophes de Whisper
    poli = False
    for formule in FORMULES_POLITESSE:
        if formule in texte:
            poli = True
            texte = texte.replace(formule, " ")
    return " ".join(texte.split()), poli


def detecter_action(texte_entendu):
    """Trouve l'action demandée (correspondance exacte, puis approchée) : voir module/comprehension.py."""
    return trouver_action(texte_entendu, barks, CLES_IGNOREES)

# --- CHARGEMENT DES RÉPLIQUES ET PARAMÈTRES (BARKS) ---
chemin_barks = "D:/Assistance-COVAS/Backend/data/barks.json" 
with open(chemin_barks, "r", encoding="utf-8") as fichier:
    barks = json.load(fichier)

# Extraire les mots de réveil depuis le JSON
MOTS_REVEIL = barks["mots_reveil"]["mots_cles"]

# --- INITIALISATION IA (WHISPER) ---
# large-v3-turbo comprend bien mieux le français que l'ancien modèle « small » ;
# l'ancien reste utilisé en secours si le dossier du nouveau est absent.
chemin_vers_fichiers = "D:/Assistance-COVAS/Backend/module/modele_vocal_turbo"
if not os.path.exists(os.path.join(chemin_vers_fichiers, "model.bin")):
    chemin_vers_fichiers = "D:/Assistance-COVAS/Backend/module/modele_vocal_fr"
print("Chargement du modèle d'IA vocal local...")
modele_vocal = WhisperModel(chemin_vers_fichiers, device="cuda", compute_type="float16")


PROMPT_WHISPER = vocabulaire_pour_whisper(barks)

# Le micro est calibré UNE fois au démarrage (puis le seuil s'adapte tout seul) :
# recalibrer avant chaque phrase mangeait le début de la commande.
reconnaisseur = sr.Recognizer()
reconnaisseur.dynamic_energy_threshold = True
reconnaisseur.pause_threshold = 0.7         # silence (s) qui marque la fin de la phrase
reconnaisseur.non_speaking_duration = 0.4
with sr.Microphone() as _source:
    print("Calibrage du micro (silence, s'il vous plaît)...")
    reconnaisseur.adjust_for_ambient_noise(_source, duration=1.0)


def ecouter(silencieux=False):
    """Capte le son du micro et le transcrit localement avec Whisper"""
    with sr.Microphone() as source:
        if not silencieux:
            print("Écoute...")
        try:
            audio = reconnaisseur.listen(source, timeout=3, phrase_time_limit=7)
            # Directement en mémoire, au format attendu par Whisper (16 kHz, mono, float32)
            brut = audio.get_raw_data(convert_rate=16000, convert_width=2)
            echantillons = np.frombuffer(brut, dtype=np.int16).astype(np.float32) / 32768.0

            segments, info = modele_vocal.transcribe(
                echantillons,
                language="fr",
                beam_size=5,
                temperature=0.0,
                initial_prompt=PROMPT_WHISPER,
                condition_on_previous_text=False,
                without_timestamps=True,
                no_speech_threshold=0.6,
                # Ne transcrit que les passages où quelqu'un parle vraiment : évite que
                # Whisper « invente » une phrase (voire une commande) sur un bruit.
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 500, "speech_pad_ms": 300},
            )
            texte = "".join(s.text for s in segments if s.no_speech_prob < 0.6).strip()
            if texte and not silencieux:
                print(f"[Whisper] {texte}")
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
            if "|" in action:          # bouton de l'interface : "chasseur|rappel"
                action, texte = action.split("|", 1)
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
        self.lancer_tache(surveiller_reactions(self.dire), "réactions automatiques")

        while True:
            text = await asyncio.to_thread(ecouter, silencieux=True)
            
            if text:
                text_min = text.lower()
                
                if not contient_reveil(text_min, MOTS_REVEIL):
                    continue

                print(f">>>> Mot de réveil détecté dans : {text}")

                polite = False

                if est_reveil_seul(text_min, MOTS_REVEIL):
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

                # La politesse est notée puis retirée : la commande est toujours exécutée
                text_min, polite = separer_politesse(text_min)

                action_detectee = detecter_action(text_min)
                print(f"[Écoute] « {text_min} » -> {action_detectee or 'aucune commande reconnue'}"
                      f"{' (poli)' if polite else ''}")

                if not action_detectee and polite:
                    await self.dire("commande_incomprise")

                if action_detectee:
                    await self.action_queue.put((action_detectee, text_min, polite))
                    # On attend la fin de la commande et de la réponse avant de réécouter le micro
                    await self.action_queue.join()
                    await self.tts_queue.join()
if __name__ == "__main__":
    backend = CovasBackend()
    asyncio.run(backend.boucle_principale())