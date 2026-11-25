"""
main.py — Cœur du COVAS : modèle vocal, écoute du micro, commandes et répliques.

Lancé par l'application (app.py) au clic sur le bouton central : rien de lourd n'est chargé
à l'import. Les problèmes sont écrits dans data/covas.log (voir app.py).
"""
import asyncio
import json
import logging
import os
import time

import numpy as np
import speech_recognition as sr

from module.pilotage.actions import executer_commande, surveiller_reactions, programme_en_cours
from module.dialogue.cerveau import obtenir_chemin_audio
from module.son import audio
from module.pilotage import touches
from module.jeu import lecteur_logs as logs
from module.jeu.lecteur_logs import DOSSIER_ED, surveiller_logs, surveiller_status_json, surveiller_fichiers_auxiliaires
from module.son.voix import generer_et_jouer_voix
from module.son import sons
from module.son import whisper
from module.dialogue import conversation
from module.son import ecoute as pause_ecoute
from module import config
from module.interface import reglages
from module.interface import serveur_ws
from module.interface.serveur_ws import demarrer_serveur_web
from module.dialogue.comprehension import contient_reveil, est_reveil_seul, vocabulaire_pour_whisper

_log = logging.getLogger(__name__)

DOSSIER_BACKEND = os.path.dirname(os.path.abspath(__file__))

# Clés de barks.json qui ne sont pas des commandes
CLES_IGNOREES = {"mots_reveil", "politesse"}


# Formules de politesse : on les repère, puis on les retire de la phrase pour qu'elles
# ne gênent jamais la reconnaissance de la commande (« active le FSD s'il te plaît »).
FORMULES_POLITESSE = ("s'il te plaît", "s'il te plait", "s'il te plaîs", "s'il vous plaît",
                      "s'il vous plait", "si il te plaît", "si te plaît", "steuplaît",
                      "stp", "svp")


def separer_politesse(texte):
    """Renvoie (phrase sans la formule de politesse, True si le commandant a été poli)."""
    texte = texte.replace("’", "'").replace("`", "'")     # apostrophes de Whisper
    poli = False
    for formule in FORMULES_POLITESSE:
        if formule in texte:
            poli = True
            texte = texte.replace(formule, " ")
    return " ".join(texte.split()), poli


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
    """Charge les répliques, le modèle vocal et calibre le micro.
    `progression(texte, etat)` : rappel facultatif pour l'écran d'accueil."""
    global barks, MOTS_REVEIL, PROMPT_WHISPER, modele_vocal, reconnaisseur, micro_calibre

    # --- CONFIGURATION (data/config.toml, modifiable à la main) ---
    config.preparer()

    # --- CHARGEMENT DES RÉPLIQUES ET PARAMÈTRES (BARKS) ---
    _signaler(progression, "Indexation des répliques")
    chemin_barks = os.path.join(DOSSIER_BACKEND, "data", "barks.json")
    with open(chemin_barks, "r", encoding="utf-8") as fichier:
        barks = json.load(fichier)
    reglages.lier_commandes(barks)      # modes d'énergie créés dans l'interface

    # Conversations RP (data/conversations.json) : vérifiées au démarrage
    _signaler(progression, "Chargement des conversations")
    try:
        for erreur in conversation.charger(actions=barks):
            _log.warning(f"conversations.json : {erreur}")
    except (OSError, ValueError) as erreur:
        _log.warning(f"conversations.json illisible : {erreur}")

    MOTS_REVEIL = barks["mots_reveil"]["mots_cles"]

    # --- RECONNAISSANCE VOCALE (WHISPER) ---
    modele_vocal = whisper.charger(lambda texte: _signaler(progression, texte))
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
        reconnaisseur.adjust_for_ambient_noise(source, duration=1.0)


def ecouter():
    """Écoute le micro choisi dans Réglages > Son. S'il ne s'ouvre pas, celui de Windows prend
    le relais quelques secondes : un micro débranché ne doit pas arrêter le COVAS."""
    global micro_calibre
    choisi = audio.entree()
    try:
        with sr.Microphone(device_index=audio.index_micro()) as source:
            if choisi != micro_calibre:             # autre micro : autre niveau de bruit de fond
                reconnaisseur.adjust_for_ambient_noise(source, duration=0.6)
                micro_calibre = choisi
            return transcrire(source)
    except (OSError, AssertionError, AttributeError) as erreur:
        _log.warning(f"Micro inaccessible : {erreur}")
        audio.micro_en_echec()
        time.sleep(1)
        return ""


def transcrire(source):
    """Capte une phrase et la transcrit localement avec Whisper"""
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
        return "".join(s.text for s in segments if s.no_speech_prob < 0.6).strip()
    except sr.WaitTimeoutError:
        pass
    except Exception as e:
        _log.warning(f"Erreur lors de la capture : {e}")
    return ""


class CovasBackend:
    def __init__(self, progression=None):
        self.progression = progression    # écran d'accueil de l'application (app.py)
        self.tts_queue = asyncio.Queue()
        self.action_queue = asyncio.Queue()
        # Le COVAS parle-t-il ? (sa voix peut revenir dans le micro par les haut-parleurs)
        self.parole = {"en_cours": False, "fin": 0.0}
        self.phrases_en_cours = 0       # phrases du commandant en cours de traitement

    async def tache_lecture_audio(self):
        while True:
            texte_a_dire = await self.tts_queue.get()
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
                return

            if decision.type == "conversation":
                await logs.dialogue("CMDR", texte.strip())
                await self.jouer_replique(decision.replique)
                return

            if decision.type == "commande":
                await self.action_queue.put((decision.action, texte_min, poli))
                # On attend la fin de la commande et de la réponse avant de réécouter le micro
                await self.action_queue.join()
                await self.tts_queue.join()
                return

            if poli:
                await self.dire("commande_incomprise")
        finally:
            self.phrases_en_cours -= 1

    async def question_ecrite(self, texte):
        """Phrase tapée dans l'interface : traitée comme si elle suivait « Covas »."""
        await self.traiter_phrase(texte)

    async def dire(self, *cles, poli=False):
        """Joue la première réplique disponible parmi les clés de barks.json données.
        Accepte aussi le chemin d'un son (.mp3, .wav)."""
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
            try:
                await executer_commande(action, texte, self.dire, poli)
            except Exception:
                _log.exception(f"Erreur pendant « {action} »")
            finally:
                self.action_queue.task_done()

    def lancer_tache(self, coroutine, nom):
        """Lance une tâche de fond en gardant une référence dessus (sinon Python peut
        la supprimer en pleine exécution) et note son erreur si elle plante."""
        tache = asyncio.create_task(coroutine, name=nom)
        self.taches.add(tache)

        def fin_de_tache(finie):
            self.taches.discard(finie)
            if not finie.cancelled() and finie.exception():
                _log.error(f"La tâche « {nom} » s'est arrêtée", exc_info=finie.exception())

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
                await logs.annoncer(f"Second écran : ouvre {adresse} sur le téléphone (même Wi-Fi)")

        if problemes:
            for probleme in problemes:
                _log.warning(f"Démarrage : {probleme}")
                _signaler(self.progression, probleme, "attention")
            _signaler(self.progression, "Systèmes dégradés — COVAS en ligne", "pret")
            return
        _signaler(self.progression, "Système COVAS opérationnel", "pret")
        await self.dire("système_vocal_opérationnel")
        await self.tts_queue.join()

    async def boucle_principale(self):
        self.taches = set()
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

        while True:
            if pause_ecoute.PAUSE.is_set():      # studio vocal ouvert : ses répliques ne sont pas des ordres
                await asyncio.sleep(0.2)
                continue
            debut_ecoute = time.monotonic()
            text = await asyncio.to_thread(ecouter)
            if pause_ecoute.PAUSE.is_set():
                continue

            if text:
                text_min = text.lower()

                if not contient_reveil(text_min, MOTS_REVEIL):
                    # Le COVAS vient de poser une question : on peut lui répondre sans « Covas »
                    if conversation.attend_reponse():
                        await self.traiter_phrase(text, reveil=False, debut_ecoute=debut_ecoute)
                    continue

                if est_reveil_seul(text_min, MOTS_REVEIL):
                    # « Covas » seul : le COVAS répond, puis écoute la commande
                    chemin_reveil = await obtenir_chemin_audio("mots_reveil")
                    if chemin_reveil:
                        await self.tts_queue.put(chemin_reveil)
                        await self.tts_queue.join()

                    debut_ecoute = time.monotonic()
                    text = await asyncio.to_thread(ecouter)
                    if pause_ecoute.PAUSE.is_set() or not text:
                        continue

                # Commande ou conversation (voir module/dialogue/conversation.py). La politesse est
                # notée puis retirée : la commande est toujours exécutée.
                await self.traiter_phrase(text, debut_ecoute=debut_ecoute)


def demarrer(progression=None):
    """Active le COVAS : chargements, puis boucle d'écoute (ne rend la main qu'à l'arrêt)."""
    initialiser(progression)
    asyncio.run(CovasBackend(progression).boucle_principale())
