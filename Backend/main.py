import os
import sys

# Le terminal est habillé AVANT les autres imports : certains modules affichent
# déjà des messages au chargement.
from module import terminal as t
t.activer()
t.banniere("COVAS // ASSISTANCE DE BORD")
t.ligne("SYSTEM", "Initialisation du noyau COVAS...")

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
from module import touches
from module.lecteur_logs import DOSSIER_ED, surveiller_logs, surveiller_status_json, surveiller_fichiers_auxiliaires
from module.voix import generer_et_jouer_voix
from module import synthese
from module.serveur_ws import demarrer_serveur_web
from module.comprehension import trouver_action, contient_reveil, est_reveil_seul, vocabulaire_pour_whisper
t.ok("Modules de bord chargés.", t.CYAN)

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
t.ok(f"Répliques indexées ({len(barks)} entrées).")

# Extraire les mots de réveil depuis le JSON
MOTS_REVEIL = barks["mots_reveil"]["mots_cles"]

# --- INITIALISATION IA (WHISPER) ---
# large-v3-turbo comprend bien mieux le français que l'ancien modèle « small » ;
# l'ancien reste utilisé en secours si le dossier du nouveau est absent.
chemin_vers_fichiers = "D:/Assistance-COVAS/Backend/module/modele_vocal_turbo"
if not os.path.exists(os.path.join(chemin_vers_fichiers, "model.bin")):
    chemin_vers_fichiers = "D:/Assistance-COVAS/Backend/module/modele_vocal_fr"
t.vide()
t.ligne("IA", f"Chargement du modèle vocal : {os.path.basename(chemin_vers_fichiers)}")
t.ligne("IA", "Transfert vers le GPU (cuda / float16)...")
with t.Chargement():
    modele_vocal = WhisperModel(chemin_vers_fichiers, device="cuda", compute_type="float16")
t.ok("Modèle de reconnaissance vocale opérationnel.")


PROMPT_WHISPER = vocabulaire_pour_whisper(barks)

# Le micro est calibré UNE fois au démarrage (puis le seuil s'adapte tout seul) :
# recalibrer avant chaque phrase mangeait le début de la commande.
reconnaisseur = sr.Recognizer()
reconnaisseur.dynamic_energy_threshold = True
reconnaisseur.pause_threshold = 0.7         # silence (s) qui marque la fin de la phrase
reconnaisseur.non_speaking_duration = 0.4
with sr.Microphone() as _source:
    t.ligne("MICRO", "Calibrage du micro (silence, s'il vous plaît)...")
    reconnaisseur.adjust_for_ambient_noise(_source, duration=1.0)
t.ok(f"Micro calibré (seuil {reconnaisseur.energy_threshold:.0f}).")


def ecouter(silencieux=False):
    """Capte le son du micro et le transcrit localement avec Whisper"""
    with sr.Microphone() as source:
        if not silencieux:
            t.etat("ÉCOUTE", "ACTIVE — parlez maintenant", t.CYAN)
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
                t.ligne("WHISPER", f"« {texte} »", t.CYAN)
            return texte
        except sr.WaitTimeoutError:
            pass
        except Exception as e:
            t.erreur("MICRO", f"Erreur lors de la capture : {e}")
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
            nom = texte_a_dire
            if os.path.isfile(nom):                       # chemin d'un .wav : on garde le nom
                nom = os.path.splitext(os.path.basename(nom))[0]
            t.ligne("COVAS", nom, t.CYAN)

            await generer_et_jouer_voix(texte_a_dire)

            self.tts_queue.task_done()

    async def dire(self, *cles, poli=False):
        """Joue la première réplique disponible parmi les clés de barks.json données.
        Accepte aussi le chemin d'un .wav (réplique fabriquée par la synthèse vocale)."""
        for cle in cles:
            if cle and cle.lower().endswith(".wav") and os.path.isfile(cle):
                await self.tts_queue.put(cle)
                return True
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
            t.ligne("ACTION", f"Exécution : {action}")
            try:
                await executer_commande(action, texte, self.dire, poli)
            except Exception:
                t.erreur("ACTION", f"Erreur pendant « {action} » :")
                traceback.print_exc()
            finally:
                self.action_queue.task_done()

    def lancer_tache(self, coroutine, nom):
        """Lance une tâche de fond en gardant une référence dessus (sinon Python peut
        la supprimer en pleine exécution) et affiche son erreur si elle plante."""
        tache = asyncio.create_task(coroutine, name=nom)
        self.taches.add(tache)

        def fin_de_tache(finie):
            self.taches.discard(finie)
            if not finie.cancelled() and finie.exception():
                t.erreur("ERREUR", f"La tâche « {nom} » s'est arrêtée :")
                traceback.print_exception(finie.exception())

        tache.add_done_callback(fin_de_tache)
        return tache

    async def verifier_systemes(self, serveur_web):
        """Contrôle de démarrage. Si tout est bon, le COVAS annonce « systèmes opérationnels » ;
        sinon il affiche ce qui ne va pas, sans rien dire."""
        await asyncio.sleep(1.5)          # laisse le serveur web ouvrir son port
        problemes = []
        if serveur_web.done():
            problemes.append("serveur de l'interface arrêté (port déjà utilisé ?)")
        if not os.path.isdir(DOSSIER_ED):
            problemes.append(f"dossier des journaux du jeu introuvable ({DOSSIER_ED})")
        if not touches.ETAT["fichier"]:
            problemes.append("fichier de touches du jeu (.binds) introuvable")
        try:
            if not sr.Microphone.list_microphone_names():
                problemes.append("aucun micro détecté")
        except Exception as erreur:
            problemes.append(f"micro inaccessible ({erreur})")

        if problemes:
            print("[Démarrage] Systèmes dégradés :")
            for probleme in problemes:
                print(f"   - {probleme}")
            return
        print("[Démarrage] Tous les systèmes sont opérationnels.")
        await self.dire("système_vocal_opérationnel")
        await self.tts_queue.join()

    async def boucle_principale(self):
        self.taches = set()
        t.vide()
        t.ligne("SYSTEM", "Lancement des sous-systèmes...")
        # Le serveur de l'interface d'abord, pour que l'écran se connecte au plus vite
        serveur_web = self.lancer_tache(demarrer_serveur_web(self.action_queue), "serveur web")
        self.lancer_tache(self.tache_lecture_audio(), "lecture audio")
        self.lancer_tache(self.tache_execution_macros(), "macros")

        self.lancer_tache(surveiller_logs(self.tts_queue, obtenir_chemin_audio), "journal")
        self.lancer_tache(surveiller_status_json(), "Status.json")
        self.lancer_tache(surveiller_fichiers_auxiliaires(), "fichiers auxiliaires")
        self.lancer_tache(surveiller_reactions(self.dire), "réactions automatiques")
        # Voix de synthèse (rapport d'avarie) chargée d'avance : le premier rapport part sans attendre
        self.lancer_tache(asyncio.to_thread(synthese.charger), "synthèse vocale")

        await self.verifier_systemes(serveur_web)
        await asyncio.sleep(0.3)        # laisse les modules annoncer leur démarrage

        t.separateur()
        t.titre_central("Système COVAS opérationnel", "EN ATTENTE DU MOT DE RÉVEIL")
        t.note(f"Dites « {MOTS_REVEIL[0].capitalize()} » suivi d'une commande,",
               "ou seulement le mot de réveil pour l'écoute active.")
        t.vide()
        t.etat("STATUS", "ONLINE")
        t.etat("ÉCOUTE", "VEILLE", t.CYAN)
        t.vide()

        while True:
            text = await asyncio.to_thread(ecouter, silencieux=True)
            
            if text:
                text_min = text.lower()
                
                if not contient_reveil(text_min, MOTS_REVEIL):
                    continue

                t.vide()
                t.etat("RÉVEIL", f"Mot de réveil détecté : « {text} »", t.JAUNE_VIF)

                polite = False

                if est_reveil_seul(text_min, MOTS_REVEIL):
                    t.ligne("SIGNAL", "Activation vocale. En attente de la commande...")
                    
                    chemin_reveil = await obtenir_chemin_audio("mots_reveil")
                    if chemin_reveil:
                        await self.tts_queue.put(chemin_reveil)
                        await self.tts_queue.join()
                    
                    text = await asyncio.to_thread(ecouter, silencieux=False)
                    if not text:
                        t.ligne("SIGNAL", "Délai d'attente dépassé.", t.ROUGE)
                        t.etat("ÉCOUTE", "VEILLE", t.CYAN)
                        continue
                    text_min = text.lower()

                # La politesse est notée puis retirée : la commande est toujours exécutée
                text_min, polite = separer_politesse(text_min)

                action_detectee = detecter_action(text_min)
                if action_detectee:
                    t.ok(f"Commande reconnue : {action_detectee}{' (poli)' if polite else ''}")
                else:
                    t.erreur("ÉCOUTE", f"Aucune commande reconnue dans « {text_min} »")

                if not action_detectee and polite:
                    await self.dire("commande_incomprise")

                if action_detectee:
                    await self.action_queue.put((action_detectee, text_min, polite))
                    # On attend la fin de la commande et de la réponse avant de réécouter le micro
                    await self.action_queue.join()
                    await self.tts_queue.join()
                t.etat("ÉCOUTE", "VEILLE", t.CYAN)


if __name__ == "__main__":
    backend = CovasBackend()
    asyncio.run(backend.boucle_principale())