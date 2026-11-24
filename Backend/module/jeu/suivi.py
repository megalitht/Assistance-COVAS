"""
suivi.py — Ce que les suivis (exploration, commerce, matériaux) ont en commun : un fichier JSON dans
Backend/data/suivi/, et la garantie qu'aucun événement du journal n'est compté deux fois.

Pourquoi c'est nécessaire : au démarrage, le COVAS relit les derniers journaux du jeu pour
reconstruire son état. Les suivis, eux, sont enregistrés sur le disque : sans précaution, une vente
ou un scan déjà compté le serait une seconde fois. Chaque fichier retient donc l'horodatage du
dernier événement compté (et une empreinte des événements de cette seconde-là, le journal n'étant
précis qu'à la seconde) : tout événement plus ancien est ignoré.

Au tout premier lancement (fichier absent), lecteur_logs.py fait relire TOUS les journaux au suivi :
il retrouve ainsi, par exemple, les données d'exploration non vendues depuis la dernière vente.

Classe de base : un suivi définit EVENEMENTS, vierge() et _appliquer(e) -> annonces.
"""
import hashlib
import json
import os
import time

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
        self.empreintes = set()   # événements comptés à cette seconde-là
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
            print(f"[Suivi] {os.path.basename(self.chemin)} illisible ({erreur}) : mis de côté, "
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
        self.empreintes = set(brut.get("empreintes") or [])
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
                           "empreintes": sorted(self.empreintes), "donnees": self.donnees},
                          f, ensure_ascii=False, separators=(",", ":"))
            os.replace(provisoire, self.chemin)
            self.modifie, self.ecrit = False, time.monotonic()
        except OSError as erreur:
            print(f"[Suivi] Écriture de {os.path.basename(self.chemin)} impossible : {erreur}")

    # ---------- Événements ----------
    def deja_compte(self, evenement):
        horodatage = evenement.get("timestamp") or ""
        if not horodatage or horodatage > self.dernier:
            return False
        return horodatage < self.dernier or empreinte(evenement) in self.empreintes

    def traiter(self, evenement):
        """Un événement du journal : appliqué une seule fois, même relu. Renvoie les annonces."""
        if evenement.get("event") not in self.EVENEMENTS or self.deja_compte(evenement):
            return []
        horodatage = evenement.get("timestamp") or ""
        if horodatage:
            if horodatage > self.dernier:
                self.dernier, self.empreintes = horodatage, set()
            self.empreintes.add(empreinte(evenement))
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
        suivi.modifie = True
        suivi.enregistrer(forcer=True)
    return compte
