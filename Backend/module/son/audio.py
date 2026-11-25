"""
audio.py — Micro et sortie audio choisis dans Réglages > Son.

Le choix est enregistré par reglages.py sous forme de noms de périphériques, car leurs numéros
changent quand on branche ou débranche un casque. Un périphérique absent : celui de Windows.

Rien n'est ouvert à l'import. Le micro n'est ouvert ici que pendant « Tester le micro ».
"""
import json
import logging
import math
import os
import subprocess
import threading
import time

from module import programme
from module.interface import reglages

_log = logging.getLogger(__name__)

DOSSIER_BACKEND = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SONS_ESSAI = ("data/son/Demarrage/Système COVAS opérationnel.mp3",
              "data/son/Demarrage/SysCOVASOp.mp3")
VALIDITE_INDEX = 10         # secondes : retrouver le micro par son nom à chaque phrase serait lent
DUREE_TEST_MICRO = 20       # secondes : le test du micro s'arrête tout seul
DELAI_LISTE = 10            # secondes au plus pour lister les sorties
DELAI_ESSAI = 15            # secondes au plus pour jouer le son d'essai
_MAPPEURS = ("mappeur", "mapper", "pilote de capture", "périphérique audio principal")

_index = {"nom": None, "valeur": None, "quand": -math.inf}


def reparer_nom(nom):
    """PortAudio rend parfois l'UTF-8 de Windows mal décodé (« tÃ©lÃ©phone »)."""
    for codage in ("cp1252", "latin-1"):
        try:
            return nom.encode(codage).decode("utf-8")
        except UnicodeError:
            continue
    return nom


def _est_mappeur(nom):
    nom = nom.casefold()
    return any(m in nom for m in _MAPPEURS)


def _micros(p):
    """[(index, nom brut, nom complet)] des micros de l'interface par défaut (celle du COVAS).
    Sous Windows, cette interface coupe les noms à 31 caractères : le nom complet vient des autres."""
    interface = p.get_default_host_api_info()["index"]
    appareils = [p.get_device_info_by_index(i) for i in range(p.get_device_count())]
    entrees = [d for d in appareils if d["maxInputChannels"] > 0]
    micros, vus = [], set()
    for d in entrees:
        brut = d["name"]
        if d["hostApi"] != interface or brut in vus or _est_mappeur(reparer_nom(brut)):
            continue
        vus.add(brut)
        complet = reparer_nom(brut)
        candidats = [reparer_nom(a["name"]) for a in entrees if a["hostApi"] != interface]
        complet = next((c for c in candidats if c.startswith(complet) and "\n" not in c), complet)
        micros.append((d["index"], brut, complet))
    return micros


def _sorties():
    resultat = subprocess.run(programme.commande("audio-sortie", "--lister"), capture_output=True,
                              text=True, timeout=DELAI_LISTE, cwd=DOSSIER_BACKEND,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if resultat.returncode:
        raise OSError(resultat.stderr.strip() or "sorties audio illisibles")
    return json.loads(resultat.stdout)


def peripheriques():
    """Ce que l'onglet Son affiche. Une liste illisible n'empêche pas d'afficher l'autre."""
    infos = {"entrees": [], "sorties": [], "defaut_entree": "", "defaut_sortie": "", "erreur": None}
    try:
        import pyaudio
        p = pyaudio.PyAudio()
        try:
            micros = _micros(p)
            infos["entrees"] = [{"nom": brut, "libelle": complet} for _, brut, complet in micros]
            try:
                brut = p.get_default_input_device_info()["name"]
                infos["defaut_entree"] = next((c for _, b, c in micros if b == brut), reparer_nom(brut))
            except OSError:
                pass
            try:
                infos["defaut_sortie"] = reparer_nom(p.get_default_output_device_info()["name"])
            except OSError:
                pass
        finally:
            p.terminate()
    except Exception as erreur:
        infos["erreur"] = f"Micros illisibles ({erreur})"
    try:
        noms = _sorties()
        infos["sorties"] = [{"nom": n, "libelle": n} for n in noms]
        # Le nom par défaut peut être coupé à 31 caractères : on prend sa version complète
        infos["defaut_sortie"] = next((n for n in noms if n.startswith(infos["defaut_sortie"])),
                                      infos["defaut_sortie"]) if infos["defaut_sortie"] else ""
    except (OSError, ValueError, subprocess.SubprocessError) as erreur:
        infos["erreur"] = infos["erreur"] or f"Sorties illisibles ({erreur})"
    return infos


# ---------- Utilisé par le COVAS ----------
def sortie():
    """Nom de la sortie choisie (None : celle de Windows)."""
    return reglages.audio()["sortie"]


def volume():
    """Volume de la voix du COVAS, de 0 à 1."""
    return reglages.audio()["volume"] / 100


def entree():
    """Nom du micro choisi (None : celui de Windows)."""
    return reglages.audio()["entree"]


def index_micro():
    """Numéro du micro choisi pour speech_recognition. None : celui de Windows."""
    nom = entree()
    if not nom:
        return None
    maintenant = time.monotonic()
    if _index["nom"] == nom and maintenant - _index["quand"] < VALIDITE_INDEX:
        return _index["valeur"]
    valeur = None
    try:
        import pyaudio
        p = pyaudio.PyAudio()
        try:
            valeur = next((i for i, brut, _ in _micros(p) if brut == nom), None)
        finally:
            p.terminate()
    except Exception as erreur:
        _log.warning(f"Micros illisibles : {erreur}")
    if valeur is None:
        _log.warning(f"Micro « {nom} » absent : micro de Windows utilisé.")
    _index.update(nom=nom, valeur=valeur, quand=maintenant)
    return valeur


def micro_en_echec():
    """Le micro choisi ne s'ouvre pas : celui de Windows prend le relais quelques secondes."""
    _index.update(nom=entree(), valeur=None, quand=time.monotonic())


# ---------- Boutons d'essai ----------
def tester_sortie(nom=None, niveau=100):
    """Joue une réplique sur ce périphérique, sans toucher à la voix du COVAS."""
    from module.son import sons
    son = next((c for c in (sons.trouver(os.path.join(DOSSIER_BACKEND, s)) for s in SONS_ESSAI) if c), None)
    if not son:
        return {"erreur": "Son d'essai introuvable"}
    try:
        niveau = max(0, min(100, float(niveau)))
    except (TypeError, ValueError):
        niveau = 100
    try:
        resultat = subprocess.run(programme.commande("audio-sortie", "--jouer", son, nom or "", str(niveau)),
                                  capture_output=True, text=True, timeout=DELAI_ESSAI, cwd=DOSSIER_BACKEND,
                                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError) as erreur:
        return {"erreur": f"Lecture impossible ({erreur})"}
    if resultat.returncode:
        return {"erreur": "Ce périphérique ne répond pas. Vérifie qu'il est branché."}
    return {"ok": True}


class TestMicro:
    """Vumètre de l'onglet Son : micro ouvert seulement pendant le test, jamais enregistré."""

    def __init__(self):
        self._verrou = threading.RLock()
        self._p = None
        self._flux = None
        self._minuterie = None
        self._apres = None
        self._crete = -120.0

    @property
    def actif(self):
        return self._flux is not None

    def _recu(self, donnees, _n, _temps, _statut):
        import numpy as np
        import pyaudio
        bloc = np.frombuffer(donnees, dtype=np.int16).astype(np.float32) / 32768
        if bloc.size:
            niveau = 20 * float(np.log10(np.sqrt(np.mean(bloc ** 2)) + 1e-9))
            self._crete = max(self._crete, niveau)
        return None, pyaudio.paContinue

    def demarrer(self, nom=None, apres=None):
        """Ouvre le micro `nom` (None : celui de Windows). `apres` est appelé à l'arrêt."""
        import pyaudio
        with self._verrou:
            self._fermer()
            p = pyaudio.PyAudio()
            try:
                index = next((i for i, brut, _ in _micros(p) if brut == nom), None) if nom else None
                if nom and index is None:
                    raise OSError("micro absent")
                infos = p.get_device_info_by_index(index) if index is not None else p.get_default_input_device_info()
                taux = int(infos["defaultSampleRate"])
                self._crete = -120.0
                self._flux = p.open(format=pyaudio.paInt16, channels=1, rate=taux, input=True,
                                    input_device_index=infos["index"], frames_per_buffer=int(taux * 0.05),
                                    stream_callback=self._recu)
            except Exception as erreur:
                p.terminate()
                self._flux = None
                return {"erreur": f"Micro inaccessible ({erreur})"}
            self._p = p
            self._apres = apres
            self._minuterie = threading.Timer(DUREE_TEST_MICRO, self.arreter)
            self._minuterie.daemon = True
            self._minuterie.start()
            return {"ok": True, "duree": DUREE_TEST_MICRO}

    def niveau(self):
        with self._verrou:
            crete, self._crete = self._crete, -120.0
            return {"actif": self.actif, "db": round(crete, 1)}

    def _fermer(self):
        if self._minuterie:
            self._minuterie.cancel()
        self._minuterie = None
        if self._flux is not None:
            try:
                self._flux.stop_stream()
                self._flux.close()
            except Exception:
                pass
        if self._p is not None:
            try:
                self._p.terminate()
            except Exception:
                pass
        self._flux = self._p = None

    def arreter(self):
        with self._verrou:
            self._fermer()
            apres, self._apres = self._apres, None
        if apres:
            apres()
        return {"ok": True}


TEST_MICRO = TestMicro()
