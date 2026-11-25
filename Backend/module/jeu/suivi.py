"""
suivi.py — Ce que les suivis (exploration, commerce, matériaux) ont en commun : un fichier JSON dans
Backend/data/suivi/, et la garantie qu'aucun événement du journal n'est compté deux fois.

Pourquoi c'est nécessaire : au démarrage, le COVAS relit les derniers journaux du jeu pour
reconstruire son état. Les suivis, eux, sont enregistrés sur le disque : sans précaution, une vente
ou un scan déjà compté le serait une seconde fois. Chaque fichier retient donc l'horodatage du
dernier événement compté, et combien de fois chaque événement de cette seconde-là a été compté : le
journal n'est précis qu'à la seconde, et deux lignes identiques dans la même seconde sont deux vrais
événements (vérifié : deux ramassages du même matériau). Tout événement plus ancien est ignoré.

Au tout premier lancement (fichier absent), lecteur_logs.py fait relire TOUS les journaux au suivi :
il retrouve ainsi, par exemple, les données d'exploration non vendues depuis la dernière vente.

Classe de base : un suivi définit EVENEMENTS, vierge() et _appliquer(e) -> annonces.
"""
import hashlib
import json
import logging
import os
import time

_log = logging.getLogger(__name__)

DOSSIER_BACKEND = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOSSIER = os.path.join(DOSSIER_BACKEND, "data", "suivi")
DELAI_ECRITURE = 2.0          # s au moins entre deux écritures (un saut fait plusieurs événements)


def empreinte(evenement):
    texte = json.dumps(evenement, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(texte.encode("utf-8")).hexdigest()[:16]


class Suivi:
    NOM = "suivi"                 # nom du fichier : data/suivi/<NOM>.json
    EVENEMENTS = frozenset()      # événements du journal qui intéressent ce suivi
    VERSION = 1

    def __init__(self, chemin=None):
        self.chemin = chemin      # None : en mémoire seulement (tests)
        self.donnees = self.vierge()
        self.dernier = ""         # horodatage du dernier événement compté
        self.empreintes = {}      # empreinte -> nombre de fois comptée, à cette seconde-là
        self._lecture = ("", {})  # (seconde, {empreinte: occurrences}) de la lecture en cours
        self.modifie = False
        self.ecrit = 0.0

    # ---------- À définir par chaque suivi ----------
    def vierge(self):
        return {}

    def _appliquer(self, evenement):
        """Met à jour self.donnees ; renvoie la liste des annonces à faire (dicts)."""
        return []

    # ---------- Disque ----------
    def ouvrir(self, chemin=None):
        """Lit le fichier. Renvoie False s'il n'existait pas (premier lancement : tout relire)."""
        self.chemin = chemin or self.chemin or os.path.join(DOSSIER, f"{self.NOM}.json")
        try:
            with open(self.chemin, encoding="utf-8") as f:
                brut = json.load(f)
        except FileNotFoundError:
            return False
        except (OSError, ValueError) as erreur:
            _log.warning(f"{os.path.basename(self.chemin)} illisible ({erreur}) : mis de côté, "
                         "reconstruit depuis les journaux.")
            try:
                os.replace(self.chemin, self.chemin + ".illisible")
            except OSError:
                pass
            return False
        if not isinstance(brut, dict) or brut.get("version") != self.VERSION:
            return False
        self.donnees = {**self.vierge(), **(brut.get("donnees") or {})}
        self.dernier = brut.get("dernier") or ""
        empreintes = brut.get("empreintes") or {}
        self.empreintes = dict.fromkeys(empreintes, 1) if isinstance(empreintes, list) else dict(empreintes)
        return True

    def enregistrer(self, forcer=False):
        """Écrit le fichier s'il a changé (au plus toutes les DELAI_ECRITURE s, sauf forcer)."""
        if not self.chemin or not self.modifie:
            return
        if not forcer and time.monotonic() - self.ecrit < DELAI_ECRITURE:
            return
        try:
            os.makedirs(os.path.dirname(self.chemin), exist_ok=True)
            provisoire = self.chemin + ".tmp"
            with open(provisoire, "w", encoding="utf-8") as f:
                json.dump({"version": self.VERSION, "dernier": self.dernier,
                           "empreintes": self.empreintes, "donnees": self.donnees},
                          f, ensure_ascii=False, separators=(",", ":"))
            os.replace(provisoire, self.chemin)
            self.modifie, self.ecrit = False, time.monotonic()
        except OSError as erreur:
            _log.warning(f"Écriture de {os.path.basename(self.chemin)} impossible : {erreur}")

    # ---------- Événements ----------
    def nouvelle_lecture(self):
        """Début de la lecture d'un fichier du journal : les occurrences repartent de zéro."""
        self._lecture = ("", {})

    def _occurrence(self, horodatage, cle):
        """Rang de cet événement parmi les lignes identiques de la même seconde, dans la lecture en
        cours (1 pour la première)."""
        seconde, vues = self._lecture
        return (vues.get(cle, 0) if seconde == horodatage else 0) + 1

    def deja_compte(self, evenement):
        """True si cet événement (cette occurrence, dans la lecture en cours) a déjà été compté."""
        horodatage = evenement.get("timestamp") or ""
        if not horodatage or horodatage > self.dernier:
            return False
        if horodatage < self.dernier:
            return True
        cle = empreinte(evenement)
        return self._occurrence(horodatage, cle) <= self.empreintes.get(cle, 0)

    def traiter(self, evenement):
        """Un événement du journal : appliqué une seule fois, même relu. Renvoie les annonces."""
        if evenement.get("event") not in self.EVENEMENTS:
            return []
        horodatage = evenement.get("timestamp") or ""
        if horodatage:
            cle = empreinte(evenement)
            deja = self.deja_compte(evenement)
            rang = self._occurrence(horodatage, cle)
            seconde, vues = self._lecture
            vues = vues if seconde == horodatage else {}
            vues[cle] = rang
            self._lecture = (horodatage, vues)
            if deja:
                return []
            if horodatage > self.dernier:
                self.dernier, self.empreintes = horodatage, {}
            self.empreintes[cle] = rang
        annonces = self._appliquer(evenement) or []
        self.modifie = True
        return annonces


def reconstruire(suivis, journaux):
    """Premier lancement : fait relire tous les journaux (du plus ancien au plus récent) aux suivis
    qui n'avaient pas encore de fichier. Fonction bloquante (à lancer dans un thread)."""
    if not suivis:
        return 0
    noms = set().union(*(s.EVENEMENTS for s in suivis))
    marques = tuple(f'"event":"{nom}"' for nom in noms)
    compte = 0
    for chemin in journaux:
        for suivi in suivis:
            suivi.nouvelle_lecture()
        try:
            with open(chemin, encoding="utf-8", errors="replace") as f:
                for ligne in f:
                    if not any(m in ligne for m in marques):
                        continue
                    try:
                        evenement = json.loads(ligne)
                    except ValueError:
                        continue
                    for suivi in suivis:
                        suivi.traiter(evenement)
                    compte += 1
        except OSError:
            continue
    for suivi in suivis:
        suivi.nouvelle_lecture()
        suivi.modifie = True
        suivi.enregistrer(forcer=True)
    return compte
