import os
import sys

# Le terminal est habillé AVANT les autres imports : certains modules affichent
# déjà des messages au chargement.
from module.interface import terminal as t
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
import time
import traceback
import sounddevice as sd
import numpy as np
import winsound



# Importation de nos modules personnalisés situés dans le sous-dossier 'module'
from module.pilotage.actions import executer_commande, surveiller_reactions, programme_en_cours
from module.dialogue.cerveau import obtenir_chemin_audio
from module.son import audio
from module.pilotage import touches
from module.jeu import lecteur_logs as logs
from module.jeu.lecteur_logs import DOSSIER_ED, surveiller_logs, surveiller_status_json, surveiller_fichiers_auxiliaires
from module.son.voix import generer_et_jouer_voix
from module.son import sons
from module.dialogue import conversation
from module.son import ecoute as pause_ecoute
from module import config
from module.interface import reglages
from module.interface import serveur_ws
from module.interface.serveur_ws import demarrer_serveur_web
from module.dialogue.comprehension import trouver_action, contient_reveil, est_reveil_seul, vocabulaire_pour_whisper
t.ok("Modules de bord chargés.", t.CYAN)

# Dossier Backend/ : les chemins ne dépendent plus de la lettre du disque
DOSSIER_BACKEND = os.path.dirname(os.path.abspath(__file__))

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
    """Trouve l'action demandée (correspondance exacte, puis approchée) : voir module/dialogue/comprehension.py."""
    return trouver_action(texte_entendu, barks, CLES_IGNOREES)

TITRE = "COVAS — Assistance de bord"      # titre de la fenêtre (voir macros.TITRE_INTERFACE)

# Remplis par initialiser() : rien de lourd (modèle vocal, micro) n'est chargé à l'import,
# pour que l'application (app.py) s'ouvre tout de suite et n'active le COVAS qu'au clic.
barks = {}
MOTS_REVEIL = []
PROMPT_WHISPER = ""
modele_vocal = None
reconnaisseur = None
micro_calibre = None            # micro sur lequel le seuil d'écoute a été calibré


def _signaler(progression, texte, etat="etape"):
    """Transmet une étape du démarrage à l'écran d'accueil de l'application (s'il y en a un)."""
    if progression:
        try:
            progression(texte, etat)
        except Exception:
            pass


def initialiser(progression=None):
    """Charge les répliques, le modèle vocal (GPU) et calibre le micro.
    `progression(texte, etat)` : rappel facultatif pour l'écran d'accueil."""
    global barks, MOTS_REVEIL, PROMPT_WHISPER, modele_vocal, reconnaisseur, micro_calibre

    # --- CONFIGURATION (data/config.toml, modifiable à la main) ---
    ecrites = config.preparer()
    if ecrites:
        t.ok(f"Configuration : {', '.join(ecrites)} ajouté(s) à {config.CHEMIN}")

    # --- CHARGEMENT DES RÉPLIQUES ET PARAMÈTRES (BARKS) ---
    _signaler(progression, "Indexation des répliques")
    chemin_barks = os.path.join(DOSSIER_BACKEND, "data", "barks.json")
    with open(chemin_barks, "r", encoding="utf-8") as fichier:
        barks = json.load(fichier)
    reglages.lier_commandes(barks)      # modes d'énergie créés dans l'interface
    t.ok(f"Répliques indexées ({len(barks)} entrées).")

    # Conversations RP (data/conversations.json) : vérifiées au démarrage
    _signaler(progression, "Chargement des conversations")
    try:
        erreurs_conversation = conversation.charger(actions=barks)
        for erreur in erreurs_conversation:
            t.erreur("CONVERSATION", erreur)
        enregistrees = sum(1 for r in conversation._contenu["repliques"]
                           if conversation.chemin_enregistrement(r))
        t.ok(f"Conversations chargées ({len(conversation._contenu['sujets'])} sujets, "
             f"{enregistrees}/{len(conversation._contenu['repliques'])} répliques enregistrées).")
    except (OSError, ValueError) as erreur:
        t.erreur("CONVERSATION", f"conversations.json illisible : {erreur}")

    # Extraire les mots de réveil depuis le JSON
    MOTS_REVEIL = barks["mots_reveil"]["mots_cles"]

    # --- INITIALISATION IA (WHISPER) ---
    # large-v3-turbo comprend bien mieux le français que l'ancien modèle « small » ;
    # l'ancien reste utilisé en secours si le dossier du nouveau est absent.
    chemin_vers_fichiers = os.path.join(DOSSIER_BACKEND, "module", "modele_vocal_turbo")
    if not os.path.exists(os.path.join(chemin_vers_fichiers, "model.bin")):
        chemin_vers_fichiers = os.path.join(DOSSIER_BACKEND, "module", "modele_vocal_fr")
    t.vide()
    t.ligne("IA", f"Chargement du modèle vocal : {os.path.basename(chemin_vers_fichiers)}")
    t.ligne("IA", "Transfert vers le GPU (cuda / float16)...")
    _signaler(progression, "Transfert du modèle vocal vers le GPU")
    with t.Chargement():
        modele_vocal = WhisperModel(chemin_vers_fichiers, device="cuda", compute_type="float16")
    t.ok("Modèle de reconnaissance vocale opérationnel.")

    PROMPT_WHISPER = vocabulaire_pour_whisper(barks)

    # Le micro est calibré UNE fois au démarrage (puis le seuil s'adapte tout seul) :
    # recalibrer avant chaque phrase mangeait le début de la commande.
    _signaler(progression, "Calibrage du micro — silence, s'il vous plaît")
    reconnaisseur = sr.Recognizer()
    reconnaisseur.dynamic_energy_threshold = True
    reconnaisseur.pause_threshold = 0.7         # silence (s) qui marque la fin de la phrase
    reconnaisseur.non_speaking_duration = 0.4
    micro_calibre = audio.entree()
    with sr.Microphone(device_index=audio.index_micro()) as source:
        t.ligne("MICRO", "Calibrage du micro (silence, s'il vous plaît)...")
        reconnaisseur.adjust_for_ambient_noise(source, duration=1.0)
    t.ok(f"Micro calibré (seuil {reconnaisseur.energy_threshold:.0f}).")


def ecouter(silencieux=False):
    """Écoute le micro choisi dans Réglages > Son. S'il ne s'ouvre pas, celui de Windows prend
    le relais quelques secondes : un micro débranché ne doit pas arrêter le COVAS."""
    global micro_calibre
    choisi = audio.entree()
    try:
        with sr.Microphone(device_index=audio.index_micro()) as source:
            if choisi != micro_calibre:             # autre micro : autre niveau de bruit de fond
                reconnaisseur.adjust_for_ambient_noise(source, duration=0.6)
                micro_calibre = choisi
            return transcrire(source, silencieux)
    except (OSError, AssertionError, AttributeError) as erreur:
        t.erreur("MICRO", f"Micro inaccessible : {erreur}")
        audio.micro_en_echec()
        time.sleep(1)
        return ""


def transcrire(source, silencieux=False):
    """Capte une phrase et la transcrit localement avec Whisper"""
    if not silencieux:
        t.etat("ÉCOUTE", "ACTIVE — parlez maintenant", t.CYAN)
    try:
        prise = reconnaisseur.listen(source, timeout=3, phrase_time_limit=7)
        # Directement en mémoire, au format attendu par Whisper (16 kHz, mono, float32)
        brut = prise.get_raw_data(convert_rate=16000, convert_width=2)
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
    def __init__(self, progression=None):
        self.progression = progression    # écran d'accueil de l'application (app.py)
        self.tts_queue = asyncio.Queue()
        self.action_queue = asyncio.Queue()
        # Le COVAS parle-t-il ? (sa voix peut revenir dans le micro par les haut-parleurs)
        self.parole = {"en_cours": False, "fin": 0.0}
        self.phrases_en_cours = 0       # phrases du commandant en cours de traitement

    async def generer_audio_tts(self, action_ou_texte: str):
        await self.tts_queue.put(action_ou_texte)

    async def tache_lecture_audio(self):
        while True:
            texte_a_dire = await self.tts_queue.get()
            nom = texte_a_dire
            if os.path.isfile(nom):                       # chemin d'un son : on garde le nom
                nom = os.path.splitext(os.path.basename(nom))[0]
            t.ligne("COVAS", nom, t.CYAN)

            self.parole["en_cours"] = True
            try:
                await generer_et_jouer_voix(texte_a_dire)
            finally:
                self.parole.update(en_cours=False, fin=time.monotonic())
                self.tts_queue.task_done()

    def a_parle_depuis(self, instant):
        """True si le COVAS parlait à un moment depuis `instant` (time.monotonic)."""
        return self.parole["en_cours"] or self.parole["fin"] > instant or not self.tts_queue.empty()

    def occupe(self):
        """Le COVAS ne lance pas de conversation pendant qu'on lui parle ou qu'il parle."""
        return (pause_ecoute.PAUSE.is_set()      # studio vocal ouvert : on ne parle pas sur une prise
                or self.phrases_en_cours > 0 or self.parole["en_cours"] or not self.tts_queue.empty()
                or not self.action_queue.empty())

    # --- Conversations -------------------------------------------------------
    async def dire_et_attendre(self, chemin):
        await self.tts_queue.put(chemin)
        await self.tts_queue.join()

    async def afficher_covas(self, texte, detail=None):
        if texte:
            t.ligne("COVAS", f"« {texte} »", t.CYAN)
        await logs.dialogue("COVAS", texte, detail)

    async def commander(self, commande):
        """Commande lancée par une réplique (« oui » -> rapport d'avarie, ravitaillement...)."""
        action, _, texte = commande.partition("|")
        await self.action_queue.put((action, texte, False))
        await self.action_queue.join()

    async def jouer_replique(self, replique):
        await conversation.jouer(replique, logs.ETAT, dire=self.dire_et_attendre,
                                 afficher=self.afficher_covas, commander=self.commander)

    async def traiter_phrase(self, texte, reveil=True, debut_ecoute=None):
        """Phrase du commandant (micro ou interface) : commande, conversation, ou rien.
        reveil=False : phrase dite sans « Covas », acceptée seulement si le COVAS attend
        une réponse. debut_ecoute : instant où le micro a commencé à écouter."""
        self.phrases_en_cours += 1
        try:
            texte_min, poli = separer_politesse(texte.lower())
            echo = debut_ecoute is not None and self.a_parle_depuis(debut_ecoute)
            decision = conversation.decider(texte_min, barks, CLES_IGNOREES, logs.ETAT,
                                            reveil=reveil, echo_possible=echo)
            if decision.type == "ignore":
                if reveil:
                    t.ligne("ÉCOUTE", f"Ignoré : {decision.raison}", t.GRIS)
                return

            if decision.type == "conversation":
                t.ok(f"Conversation : {decision.sujet} ({decision.raison})")
                await logs.dialogue("CMDR", texte.strip())
                await self.jouer_replique(decision.replique)
                return

            if decision.type == "commande":
                t.ok(f"Commande reconnue : {decision.action}{' (poli)' if poli else ''}"
                     + ("" if decision.raison == "commande reconnue" else f" — {decision.raison}"))
                await self.action_queue.put((decision.action, texte_min, poli))
                # On attend la fin de la commande et de la réponse avant de réécouter le micro
                await self.action_queue.join()
                await self.tts_queue.join()
                return

            t.erreur("ÉCOUTE", f"Aucune commande reconnue dans « {texte_min} »")
            if poli:
                await self.dire("commande_incomprise")
        finally:
            self.phrases_en_cours -= 1

    async def question_ecrite(self, texte):
        """Phrase tapée dans l'interface : traitée comme si elle suivait « Covas »."""
        t.ligne("CLAVIER", f"« {texte} »", t.CYAN)
        await self.traiter_phrase(texte)

    async def dire(self, *cles, poli=False):
        """Joue la première réplique disponible parmi les clés de barks.json données.
        Accepte aussi le chemin d'un son (.wav fabriqué par la synthèse vocale, .mp3...)."""
        for cle in cles:
            if sons.est_son(cle) and sons.trouver(cle):
                await self.tts_queue.put(sons.trouver(cle))
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

        reseau = serveur_ws.infos_second_ecran()
        if reseau["actif"] and not serveur_web.done():
            for adresse in reseau["adresses"][:1]:
                t.ok(f"Second écran : {adresse}" + ("" if reseau["pin_regle"] else
                     " (sans PIN : consultation seulement)"))
                await logs.annoncer(f"Second écran : ouvre {adresse} sur le téléphone (même Wi-Fi)")

        if problemes:
            print("[Démarrage] Systèmes dégradés :")
            for probleme in problemes:
                print(f"   - {probleme}")
                _signaler(self.progression, probleme, "attention")
            _signaler(self.progression, "Systèmes dégradés — COVAS en ligne", "pret")
            return
        print("[Démarrage] Tous les systèmes sont opérationnels.")
        _signaler(self.progression, "Système COVAS opérationnel", "pret")
        await self.dire("système_vocal_opérationnel")
        await self.tts_queue.join()

    async def boucle_principale(self):
        self.taches = set()
        t.vide()
        t.ligne("SYSTEM", "Lancement des sous-systèmes...")
        _signaler(self.progression, "Lancement des sous-systèmes")
        # Le serveur de l'interface d'abord, pour que l'écran se connecte au plus vite
        serveur_web = self.lancer_tache(demarrer_serveur_web(self.action_queue), "serveur web")
        self.lancer_tache(self.tache_lecture_audio(), "lecture audio")
        self.lancer_tache(self.tache_execution_macros(), "macros")

        self.lancer_tache(surveiller_logs(self.tts_queue, obtenir_chemin_audio), "journal")
        self.lancer_tache(surveiller_status_json(), "Status.json")
        self.lancer_tache(surveiller_fichiers_auxiliaires(), "fichiers auxiliaires")
        self.lancer_tache(surveiller_reactions(self.dire), "réactions automatiques")
        # Conversations : phrases tapées dans l'interface, et le COVAS qui prend la parole
        serveur_ws.definir_questions(self.question_ecrite)
        conversation.configurer(programme_en_cours=programme_en_cours)
        logs.ecouter_evenements(conversation.observer_evenement)
        self.lancer_tache(conversation.surveiller_initiatives(logs.ETAT, self.jouer_replique,
                                                              self.occupe), "conversations")

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
            if pause_ecoute.PAUSE.is_set():      # studio vocal ouvert : ses répliques ne sont pas des ordres
                await asyncio.sleep(0.2)
                continue
            debut_ecoute = time.monotonic()
            text = await asyncio.to_thread(ecouter, silencieux=True)
            if pause_ecoute.PAUSE.is_set():
                continue

            if text:
                text_min = text.lower()

                if not contient_reveil(text_min, MOTS_REVEIL):
                    # Le COVAS vient de poser une question : on peut lui répondre sans « Covas »
                    if conversation.attend_reponse():
                        t.ligne("ÉCOUTE", f"Réponse ? « {text} »", t.CYAN)
                        await self.traiter_phrase(text, reveil=False, debut_ecoute=debut_ecoute)
                    continue

                t.vide()
                t.etat("RÉVEIL", f"Mot de réveil détecté : « {text} »", t.JAUNE_VIF)

                if est_reveil_seul(text_min, MOTS_REVEIL):
                    t.ligne("SIGNAL", "Activation vocale. En attente de la commande...")

                    chemin_reveil = await obtenir_chemin_audio("mots_reveil")
                    if chemin_reveil:
                        await self.tts_queue.put(chemin_reveil)
                        await self.tts_queue.join()

                    debut_ecoute = time.monotonic()
                    text = await asyncio.to_thread(ecouter, silencieux=False)
                    if pause_ecoute.PAUSE.is_set():
                        continue
                    if not text:
                        t.ligne("SIGNAL", "Délai d'attente dépassé.", t.ROUGE)
                        t.etat("ÉCOUTE", "VEILLE", t.CYAN)
                        continue

                # Commande ou conversation (voir module/dialogue/conversation.py). La politesse est
                # notée puis retirée : la commande est toujours exécutée.
                await self.traiter_phrase(text, debut_ecoute=debut_ecoute)
                t.etat("ÉCOUTE", "VEILLE", t.CYAN)


def demarrer(progression=None):
    """Active le COVAS : chargements, puis boucle d'écoute (ne rend la main qu'à l'arrêt)."""
    initialiser(progression)
    asyncio.run(CovasBackend(progression).boucle_principale())


if __name__ == "__main__":
    demarrer()