"""
pont_studio.py — Relie l'onglet Studio des réglages au studio vocal.

Le studio tourne dans son propre processus (studio_vocal.py --service) : ses calculs audio et son
Whisper ne ralentissent pas le COVAS en vol. Échange par tubes, jamais par le réseau :
  demande : {"id": 1, "nom": "niveau", "args": []}
  réponse : {"id": 1, "resultat": ...}  ou  {"id": 1, "erreur": "..."}
"""
import json
import os
import subprocess
import threading

DELAI_REPONSE = 180         # secondes (un étalonnage peut être long)
DELAI_ARRET = 4


class PontStudio:
    def __init__(self, commande):
        self.commande = commande
        self._processus = None
        self._attentes = {}
        self._numero = 0
        self._verrou = threading.Lock()

    @property
    def actif(self):
        return self._processus is not None and self._processus.poll() is None

    def demarrer(self):
        with self._verrou:
            if self.actif:
                return
            if self._processus is not None:          # studio arrêté tout seul
                try:
                    self._processus.stdin.close()
                except OSError:
                    pass
            options ={"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
            self._processus = subprocess.Popen(self.commande, stdin=subprocess.PIPE,
                                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                               **options)
            self._attentes = {}
            threading.Thread(target=self._lire, args=(self._processus, self._attentes),
                             name="Pont-studio", daemon=True).start()

    @staticmethod
    def _lire(processus, attentes):
        for ligne in processus.stdout:
            try:
                reponse = json.loads(ligne)
                attente = attentes.pop(reponse.get("id"), None)
            except (ValueError, AttributeError):
                continue
            if attente:
                attente["reponse"] = reponse
                attente["fin"].set()
        while attentes:                              # studio arrêté : personne n'attend pour rien
            try:
                _, attente = attentes.popitem()
            except KeyError:
                break
            attente["fin"].set()
        processus.stdout.close()

    def appeler(self, nom, args=()):
        attente = {"fin": threading.Event(), "reponse": None}
        with self._verrou:
            if not self.actif:
                return {"erreur": "le studio vocal est arrêté"}
            self._numero += 1
            numero, attentes = self._numero, self._attentes
            attentes[numero] = attente
            try:
                demande = json.dumps({"id": numero, "nom": nom, "args": list(args or [])})
                self._processus.stdin.write(demande.encode("ascii") + b"\n")
                self._processus.stdin.flush()
            except (OSError, ValueError):
                attentes.pop(numero, None)
                return {"erreur": "le studio vocal est arrêté"}
        if not attente["fin"].wait(DELAI_REPONSE):
            attentes.pop(numero, None)
            return {"erreur": "le studio vocal ne répond plus"}
        reponse = attente["reponse"]
        if reponse is None:
            return {"erreur": "le studio vocal s'est arrêté"}
        return {"erreur": reponse["erreur"]} if "erreur" in reponse else reponse.get("resultat")

    def arreter(self):
        """Fermer son entrée suffit : le studio coupe le micro et se termine."""
        with self._verrou:
            processus, self._processus = self._processus, None
        if processus is None:
            return
        try:
            processus.stdin.close()
        except OSError:
            pass
        try:
            processus.wait(DELAI_ARRET)
        except subprocess.TimeoutExpired:
            processus.kill()
