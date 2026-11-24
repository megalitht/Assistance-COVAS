"""
inara.py — Profil du commandant sur Inara (https://inara.cz/inara-api/), et rien d'autre : jamais
les prix du marché.

Seulement si le commandant a mis sa clé dans data/config.toml ([externe] inara_cle). Jamais plus de
2 requêtes par minute (Limiteur), et le profil est gardé une heure dans le cache local.
Ce qui part chez Inara : la clé et le nom du commandant, rien d'autre.
Fonction bloquante : asyncio.to_thread.

Non testé contre le vrai service (pas de clé pendant le développement) : format d'après la
documentation de l'API Inara (événement getCommanderProfile).
"""
import time
from collections import deque
from datetime import datetime, timezone

from module.externe.reseau import ErreurExterne, requete_json

URL = "https://inara.cz/inapi/v1/"
APPLICATION = "COVAS-Assistance"
VERSION = "1.0"
MAX_PAR_MINUTE = 2


class Limiteur:
    """Au plus `nombre` requêtes sur une fenêtre glissante de `fenetre` secondes."""

    def __init__(self, nombre=MAX_PAR_MINUTE, fenetre=60.0, horloge=time.monotonic):
        self.nombre, self.fenetre, self.horloge = nombre, fenetre, horloge
        self.envois = deque()

    def attente(self):
        """Secondes avant de pouvoir envoyer (0 : maintenant)."""
        maintenant = self.horloge()
        while self.envois and maintenant - self.envois[0] >= self.fenetre:
            self.envois.popleft()
        if len(self.envois) < self.nombre:
            return 0.0
        return self.fenetre - (maintenant - self.envois[0])

    def prendre(self):
        """Réserve un envoi ; False s'il faut attendre."""
        if self.attente() > 0:
            return False
        self.envois.append(self.horloge())
        return True


LIMITEUR = Limiteur()


def profil(cle_api, commandant, delai=5, limiteur=LIMITEUR):
    """Profil du commandant : rangs, escadron, allégeance, puissance, lien Inara."""
    if not cle_api or not commandant:
        raise ErreurExterne("clé Inara ou nom du commandant absent")
    if not limiteur.prendre():
        raise ErreurExterne(f"Inara : patiente encore {round(limiteur.attente())} s (2 requêtes par minute au plus)")
    corps = {
        "header": {"appName": APPLICATION, "appVersion": VERSION, "isBeingDeveloped": True,
                   "APIkey": cle_api, "commanderName": commandant},
        "events": [{"eventName": "getCommanderProfile",
                    "eventTimestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "eventData": {"searchName": commandant}}],
    }
    _, reponse = requete_json(URL, methode="POST", corps=corps, delai=delai)
    entete = (reponse or {}).get("header") or {}
    if entete.get("eventStatus") not in (None, 200):
        raise ErreurExterne(f"Inara : {entete.get('eventStatusText') or entete.get('eventStatus')}")
    evenement = ((reponse or {}).get("events") or [{}])[0]
    if evenement.get("eventStatus") != 200:
        raise ErreurExterne(f"Inara : {evenement.get('eventStatusText') or 'profil introuvable'}")
    d = evenement.get("eventData") or {}
    escadron = d.get("commanderSquadron") or {}
    return {
        "commandant": d.get("commanderName") or d.get("userName"),
        "rangs": [{"nom": r.get("rankName"), "valeur": r.get("rankValue"), "progression": r.get("rankProgress")}
                  for r in d.get("commanderRanksPilot") or []],
        "allegeance": d.get("preferredAllegianceName"), "puissance": d.get("preferredPowerName"),
        "escadron": escadron.get("squadronName") or escadron.get("SquadronName"),
        "lien": d.get("inaraURL"),
    }
