import speech_recognition as sr
import pyaudio
import struct
import math
import pydirectinput
from faster_whisper import WhisperModel
import pyttsx3
import json
import random

# --- INITIALISATION VOCALE (TTS) ---
moteur_vocal = pyttsx3.init()

def detecter_action(texte_entendu):
    """Parcourt le JSON pour trouver à quelle action correspond la phrase"""
    for cle_action, donnees in barks.items():
        for mot_cle in donnees["mots_cles"]:
            if mot_cle in texte_entendu:
                return cle_action # Retourne "energie_mtr", "energie_arm", etc.
    return None

def parler_aleatoire(cle_action):
    """Sélectionne une réponse au hasard selon la nouvelle structure JSON"""
    if cle_action in barks:
        texte = random.choice(barks[cle_action]["reponses"]) # Ajout de ["reponses"]
        
        if texte.strip() == "":
            texte = "Commande confirmée."
    else:
        texte = "Erreur de base de données vocale."
        
    print(texte)
    moteur_vocal.say(texte)
    moteur_vocal.runAndWait()

# --- INITIALISATION IA (WHISPER) ---
# --- CHARGEMENT DES RÉPLIQUES (BARKS) ---
chemin_barks = "D:/Assistance-COVAS/Backend/data/barks.json" 
with open(chemin_barks, "r", encoding="utf-8") as fichier:
    barks = json.load(fichier)

# --- INITIALISATION IA (WHISPER) ---
chemin_vers_fichiers = "D:/Assistance-COVAS/Backend/module/modele_vocal_fr"
print("Chargement du modèle d'IA vocal local...")
modele_vocal = WhisperModel(chemin_vers_fichiers, device="cuda", compute_type="float16")

# Maintenant que 'barks' est chargé, cette fonction peut s'exécuter sans erreur :
parler_aleatoire("système_vocal_opérationnel")


def ecouter(silencieux=False):
    """Capte le son du micro et le transcrit localement avec Whisper"""
    r = sr.Recognizer()
    with sr.Microphone() as source:
        if not silencieux:
            print("Écoute...")
        # Ajustement automatique au bruit ambiant
        r.adjust_for_ambient_noise(source, duration=0.5)
        try:
            audio = r.listen(source, timeout=5, phrase_time_limit=10)
            
            # Écriture temporaire du fichier wav pour Whisper
            chemin_wav = "D:/Assistance-COVAS/Backend/data/temp.wav"
            with open(chemin_wav, "wb") as f:
                f.write(audio.get_wav_data())
            
            # Transcription locale
            segments, info = modele_vocal.transcribe(chemin_wav, beam_size=5, language="fr")
            texte = "".join([segment.text for segment in segments]).strip()
            
            if texte:
                print(f"Transcription : {texte}")
                return texte
        except sr.WaitTimeoutError:
            pass
        except Exception as e:
            print(f"Erreur lors de la capture : {e}")
    return ""

# --- CHARGEMENT DES RÉPLIQUES (BARKS) ---

# Lancement de la boucle infinie
while True:
    print("\nEn attente d'instruction...")
    
    # Écoute active
    text = ecouter(silencieux=False)
    
    if text:
        text_min = text.lower()

        # --- GESTION DU PILOTAGE ---
        if ("sort" in text_min or "rentre" in text_min) and "train" in text_min:
            parler_aleatoire("train_atterrissage")
            pydirectinput.press('l')

        # Ton bloc corrigé (exemple configuré pour la soute)
        elif ("ouvre" in text_min or "ferme" in text_min) and "soute" in text_min:
            parler_aleatoire("soute")
            pydirectinput.press('home')
            
       # --- GESTION ENERGIE (PIPS) ---
        elif "pleine puissance" in text_min:
            
            # 1. On demande à l'algorithme de trouver l'action visée
            action_detectee = detecter_action(text_min)
            
            # 2. On exécute la macro correspondante
            if action_detectee == "energie_mtr":
                parler_aleatoire(action_detectee)
                pydirectinput.press('down') 
                pydirectinput.press('up', presses=4) 
                
            elif action_detectee == "energie_sys":
                parler_aleatoire(action_detectee)
                pydirectinput.press('down') 
                pydirectinput.press('left', presses=4)

            elif action_detectee == "energie_arm":
                parler_aleatoire(action_detectee)
                pydirectinput.press('down') 
                pydirectinput.press('right', presses=4)
                
            elif "reset" in text_min or "réinitialise" in text_min:
                parler("Réinitialisation des systèmes en cours...")
                pydirectinput.press('down') 
                
            else:
                parler("Veuillez préciser le système : moteurs, boucliers ou armes.")