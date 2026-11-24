"""
cache.py — Cache local des réponses externes (SQLite : data/suivi/cache_externe.sqlite), pour ne pas
redemander les mêmes données à chaque passage dans un système. Chaque entrée a sa durée de vie.
Utilisable depuis plusieurs threads. Sans fichier (tests) : en mémoire.
"""
import json
import os
import sqlite3
import threading
import time

DOSSIER_BACKEND = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHEMIN = os.path.join(DOSSIER_BACKEND, "data", "suivi", "cache_externe.sqlite")


class Cache:
    def __init__(self, chemin=None, horloge=time.time):
        self.chemin = chemin or ":memory:"
        self.horloge = horloge
        self._verrou = threading.Lock()
        if self.chemin != ":memory:":
            os.makedirs(os.path.dirname(self.chemin), exist_ok=True)
        self._base = sqlite3.connect(self.chemin, check_same_thread=False)
        with self._verrou:
            self._base.execute("CREATE TABLE IF NOT EXISTS cache (cle TEXT PRIMARY KEY, valeur TEXT, expire REAL)")
            self._base.commit()

    def lire(self, cle):
        """La valeur gardée, None si absente ou périmée."""
        with self._verrou:
            ligne = self._base.execute("SELECT valeur, expire FROM cache WHERE cle = ?", (cle,)).fetchone()
        if not ligne or ligne[1] < self.horloge():
            return None
        return json.loads(ligne[0])

    def ecrire(self, cle, valeur, duree_s):
        with self._verrou:
            self._base.execute("INSERT OR REPLACE INTO cache VALUES (?, ?, ?)",
                               (cle, json.dumps(valeur, ensure_ascii=False), self.horloge() + duree_s))
            self._base.commit()

    def purger(self):
        """Retire les entrées périmées (au démarrage)."""
        with self._verrou:
            self._base.execute("DELETE FROM cache WHERE expire < ?", (self.horloge(),))
            self._base.commit()

    def ou_calculer(self, cle, duree_s, fabrique):
        """Valeur en cache, sinon fabrique() (qui peut lever ErreurExterne : rien n'est gardé)."""
        valeur = self.lire(cle)
        if valeur is None:
            valeur = fabrique()
            self.ecrire(cle, valeur, duree_s)
        return valeur
