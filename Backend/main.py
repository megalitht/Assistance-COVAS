<<<<<<< HEAD
import os
import sys
=======
>>>>>>> 961b94d2d4b6c146b79770101cd0d79df548f907
import speech_recognition as sr
import pyaudio
import struct
import math
import pydirectinput
from faster_whisper import WhisperModel
import pyttsx3
import json
import random

<<<<<<< HEAD
# --- CONFIGURATION AUTOMATIQUE DES PATHS NVIDIA POUR LE VENV ---
venv_site_packages = next((p for p in sys.path if 'site-packages' in p), None)

if venv_site_packages:
    cublas_path = os.path.join(venv_site_packages, "nvidia", "cublas", "bin")
    cudnn_path = os.path.join(venv_site_packages, "nvidia", "cudnn", "bin")
    
    os.environ["PATH"] = f"{cublas_path};{cudnn_path};" + os.environ.get("PATH", "")
    if hasattr(os, 'add_dll_directory'):
        if os.path.exists(cublas_path): os.add_dll_directory(cublas_path)
        if os.path.exists(cudnn_path): os.add_dll_directory(cudnn_path)
            
=======
>>>>>>> 961b94d2d4b6c146b79770101cd0d79df548f907
# --- INITIALISATION VOCALE (TTS) ---
moteur_vocal = pyttsx3.init()

def detecter_action(texte_entendu):
    """Parcourt le JSON pour trouver à quelle action correspond la phrase"""
    for cle_action, donnees in barks.items():
<<<<<<< HEAD
        # On ignore la clé des mots de réveil pour ne pas la confondre avec une commande
        if cle_action == "mots_reveil":
            continue
        for mot_cle in donnees["mots_cles"]:
            if mot_cle in texte_entendu:
                return cle_action # Retourne "energie_mtr", "train_atterrissage", etc.
    return None

def parler_aleatoire(cle_action):
    """Sélectionne une réponse au hasard selon la structure JSON"""
    if cle_action in barks:
        texte = random.choice(barks[cle_action]["reponses"])
=======
        for mot_cle in donnees["mots_cles"]:
            if mot_cle in texte_entendu:
                return cle_action # Retourne "energie_mtr", "energie_arm", etc.
    return None

def parler_aleatoire(cle_action):
    """Sélectionne une réponse au hasard selon la nouvelle structure JSON"""
    if cle_action in barks:
        texte = random.choice(barks[cle_action]["reponses"]) # Ajout de ["reponses"]
        
>>>>>>> 961b94d2d4b6c146b79770101cd0d79df548f907
        if texte.strip() == "":
            texte = "Commande confirmée."
    else:
        texte = "Erreur de base de données vocale."
        
    print(texte)
    moteur_vocal.say(texte)
    moteur_vocal.runAndWait()

<<<<<<< HEAD
# --- CHARGEMENT DES RÉPLIQUES ET PARAMÈTRES (BARKS) ---
chemin_barks = "D:/Assistance-COVAS/Backend/data/barks.json" 
with open(chemin_barks, "r", encoding="utf-8") as fichier:
    barks = json.load(fichier)

# Extraire dynamiquement les mots de réveil depuis le JSON
MOTS_REVEIL = barks["mots_reveil"]["mots_cles"]

# Extraire dynamiquement TOUS les mots-clés de commandes pour la détection rapide globale
TOUS_LES_MOTS_CLES = []
for cle, data in barks.items():
    if cle != "mots_reveil":
        TOUS_LES_MOTS_CLES.extend(data["mots_cles"])

# --- INITIALISATION IA (WHISPER) ---
chemin_vers_fichiers = "D:/Assistance-COVAS/Backend/module/modele_vocal_fr"
print("Chargement du modèle d'IA vocal local...")
modele_vocal = WhisperModel(chemin_vers_fichiers, device="cuda", compute_type="float16")

parler_aleatoire("système_vocal_opérationnel")


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
            if texte:
t
                return texte
        except sr.WaitTimeoutError:
            pass
        except Exception as e:
            print(f"Erreur lors de la capture : {e}")
    return ""


# Lancement de la boucle infinie
while True:
    print("\nEn attente d'instruction (en sourdine)...")
    text = ecouter(silencieux=True)
    
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
            parler_aleatoire("mots_reveil")
            
            print(">>>> [ÉCOUTE ACTIVE DÉCLENCHÉE - PARLEZ MAINTENANT]")
            text = ecouter(silencieux=False)
            if not text:
                print("Délai d'attente dépassé. Retour en veille.")
                continue
            text_min = text.lower()

        # 3. EXÉCUTION DES COMMANDES DYNAMIQUES
        if "amara.org" in text_min:
            continue

        # Utilisation de notre super moteur de détection basé à 100% sur le JSON
        action_detectee = detecter_action(text_min)
        
        if action_detectee:
            # --- ACTION : TRAIN D'ATTERRISSAGE ---
            if action_detectee == "train_atterrissage":
                parler_aleatoire(action_detectee)
                pydirectinput.press('l')

            # --- ACTION : SOUTE ---
            elif action_detectee == "soute":
                parler_aleatoire(action_detectee)
                pydirectinput.press('home')

            # --- ACTION : PIPS MOTEURS ---
            elif action_detectee == "energie_mtr":
=======
# --- INITIALISATION IA (WHISPER) ---
chemin_vers_fichiers = "./module/modele_vocal_fr"
print("Chargement du modèle d'IA vocal local...")
modele_vocal = WhisperModel(chemin_vers_fichiers, device="cuda", compute_type="float16")
parler_aleatoire("système_vocal_opérationnel")

# --- CHARGEMENT DES RÉPLIQUES (BARKS) ---
chemin_barks = "./module/barks.json" # À adapter selon l'emplacement exact de ton fichier
with open(chemin_barks, "r", encoding="utf-8") as fichier:
    barks = json.load(fichier)

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
>>>>>>> 961b94d2d4b6c146b79770101cd0d79df548f907
                parler_aleatoire(action_detectee)
                pydirectinput.press('down') 
                pydirectinput.press('up', presses=4) 
                
<<<<<<< HEAD
            # --- ACTION : PIPS BOUCLIERS ---
=======
>>>>>>> 961b94d2d4b6c146b79770101cd0d79df548f907
            elif action_detectee == "energie_sys":
                parler_aleatoire(action_detectee)
                pydirectinput.press('down') 
                pydirectinput.press('left', presses=4)

<<<<<<< HEAD
            # --- ACTION : PIPS ARMES ---
=======
>>>>>>> 961b94d2d4b6c146b79770101cd0d79df548f907
            elif action_detectee == "energie_arm":
                parler_aleatoire(action_detectee)
                pydirectinput.press('down') 
                pydirectinput.press('right', presses=4)
                
<<<<<<< HEAD
        # --- CAS PARTICULIER : RESET DES PIPS ---
        elif "reset" in text_min or "réinitialise" in text_min or "équilibre" in text_min:
            moteur_vocal.say("Réinitialisation des systèmes en cours.")
            moteur_vocal.runAndWait()
            pydirectinput.press('down')
        


        if "lock" in text_min or "euq":
            pydirectinput.press('t') 

        #mode 
        if "mode" in text_min and "combat" in text_min:
            pydirectinput.press('left', presses=4)
            pydirectinput.press('right', presses=4)

        if "mode" in text_min and "croisière" in text_min:
            pydirectinput.press('left', presses=4)
            pydirectinput.press('up', presses=4)


        if "fsd" in text_min:
            pydirectinput.press('j') 
=======
            elif "reset" in text_min or "réinitialise" in text_min:
                parler("Réinitialisation des systèmes en cours...")
                pydirectinput.press('down') 
                
            else:
                parler("Veuillez préciser le système : moteurs, boucliers ou armes.")
>>>>>>> 961b94d2d4b6c146b79770101cd0d79df548f907
