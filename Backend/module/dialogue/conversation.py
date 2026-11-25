"""
conversation.py — Conversations RP entre le commandant et le COVAS.

Le commandant pose une question (« Covas, comment va le vaisseau ? ») et le COVAS répond
par une réplique ENREGISTRÉE (data/son/Conversations/...), choisie selon la situation :
coque, carburant, danger, heure, vaisseau piloté... Le contenu complet (questions,
répliques, contextes) est dans data/conversations.json.

Trois mécanismes :
  1. Questions -> réponses : trouvées comme les commandes (mots-clés, tolérance aux
     erreurs de Whisper), mais une commande reste prioritaire quand elle est explicite
     (« sors le train, merci » sort le train ; « comment vont les boucliers ? » ne touche
     pas aux pips).
  2. Suites : une réplique peut poser une question (« Voulez-vous le rapport d'avarie ? »).
     Pendant quelques secondes, le commandant répond SANS redire « Covas » (« oui »,
     « non », la réponse d'une devinette...).
  3. Initiatives : le COVAS engage lui-même la conversation (retour à quai, long trajet,
     fin de combat, découverte d'un monde terrestre...). « Covas, silence radio » les coupe,
     « Covas, tu peux parler » les rétablit.

Enregistrement des voix : data/SCRIPT_CONVERSATIONS.md liste chaque fichier et sa phrase.
Il est régénéré par (depuis Backend/) :
    python -m module.dialogue.conversation --script
Tant qu'un fichier n'existe pas, la réplique est seulement affichée. Les répliques
« voix: aucune » (heure, position...) sont affichées, et dites si leurs « morceaux » (module/dialogue/morceaux.py)
sont tous enregistrés : leur texte change
à chaque fois.

Essais sans micro ni jeu (depuis Backend/) :
    python -m module.dialogue.conversation --verifier
    python -m module.dialogue.conversation "comment va le vaisseau"

Ce module ne touche ni au clavier ni au micro : il décide QUOI dire, main.py le joue.
"""
import asyncio
import json
import logging
import os
import random
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime

from module import config
from module.dialogue import morceaux
from module.son import sons
from module.dialogue.comprehension import (SEUIL_APPROCHE, meilleure_approche, normaliser, present,
                                           similarite, trouver_action_detail)

_log = logging.getLogger(__name__)

DOSSIER_BACKEND = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHEMIN_CONVERSATIONS = os.path.join(DOSSIER_BACKEND, "data", "conversations.json")
CHEMIN_SCRIPT = os.path.join(DOSSIER_BACKEND, "data", "SCRIPT_CONVERSATIONS.md")
DOSSIER_SONS = "data/son/Conversations"          # relatif à Backend/

# --- RÉGLAGES ----------------------------------------------------------------
ATTENTE_REPONSE = 8           # secondes pour répondre au COVAS sans redire « Covas »
INITIATIVES_AU_DEMARRAGE = True   # le COVAS peut engager la conversation de lui-même
ECART_INITIATIVES = 240       # secondes minimum entre deux initiatives
COMBAT_RECENT = 180           # secondes pendant lesquelles un accrochage reste « récent »
ENGAGEMENT_RECENT = 75        # le drapeau « danger » du jeu ne vaut combat que si on a essuyé
                              # un tir depuis ce délai (le jeu écrit UnderAttack ~1 fois/min)
SEUIL_ECHO = 0.55             # phrase entendue trop proche de ce que le COVAS vient de dire :
                              # c'est sa propre voix captée par le micro (haut-parleurs)
PROFONDEUR_MAX = 3            # enchaînements de sujets (« oui » -> une histoire...) au plus
# ---------------------------------------------------------------------------

# Bits de Status.json utilisés par les contextes
_BITS = {"amarre": 0, "pose": 1, "boucliers": 3, "supercroisiere": 4, "surchauffe": 20,
         "danger": 22, "interdiction": 23, "vaisseau": 24, "chasseur": 25, "vrs": 26}

RANGS_PILOTES = {"Harmless": "inoffensif", "Mostly Harmless": "presque inoffensif",
                 "Novice": "novice", "Competent": "compétent", "Expert": "expert",
                 "Master": "maître", "Dangerous": "dangereux", "Deadly": "mortel",
                 "Elite": "élite"}
STATUTS_LEGAUX = {"Clean": "en règle", "Wanted": "recherché", "Lawless": "hors-la-loi",
                  "Enemy": "ennemi", "WantedEnemy": "ennemi recherché", "Hunter": "chasseur"}
MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre")

# Événements du journal qui comptent comme un accrochage (contexte « combat_recent »)
EVENEMENTS_COMBAT = {"UnderAttack", "HullDamage", "Interdicted", "CockpitBreached"}

# Effets internes qu'une réplique peut déclencher (« interne » dans le JSON)
INTERNES = {"initiatives_off", "initiatives_on"}

_maintenant = datetime.now          # remplaçable dans les tests


# =====================================================================
#  CONTEXTES (« si » dans conversations.json ; « !nom » = le contraire)
# =====================================================================
def _section(etat, nom):
    return (etat or {}).get(nom) or {}


def _flags(etat):
    return _section(etat, "status").get("flags") or 0


def _bit(etat, nom):
    return bool(_flags(etat) & (1 << _BITS[nom]))


def _nombre(valeur):
    return valeur if isinstance(valeur, (int, float)) and not isinstance(valeur, bool) else None


def _part_carburant(etat):
    carburant = _nombre(_section(etat, "status").get("carburant"))
    maxi = _nombre(_section(etat, "vaisseau").get("carburant_max"))
    return carburant / maxi if carburant is not None and maxi else None


def _coque(etat):
    return _nombre(_section(etat, "vaisseau").get("coque"))


def _sauts_restants(etat):
    route = _section(etat, "route")
    etapes = route.get("etapes") or []
    if not etapes or _section(etat, "position").get("systeme") == etapes[-1].get("systeme"):
        return 0
    if route.get("indice_actuel") is not None:
        return len(etapes) - 1 - route["indice_actuel"]
    return (route.get("prochain") or {}).get("sauts_restants") or len(etapes) - 1


def _credits(etat):
    credits = _nombre(_section(etat, "status").get("credits"))
    return credits if credits is not None else _nombre(_section(etat, "commandant").get("credits"))


def _nb_missions(etat):
    missions = _section(etat, "missions")
    return len(missions.get("liste") or []) + (missions.get("anterieures") or 0)


def _amarre(etat):
    return _bit(etat, "amarre") or bool(_section(etat, "position").get("amarre"))


def _en_vol(etat):
    return bool(_flags(etat)) and _bit(etat, "vaisseau") and not _amarre(etat) and not _bit(etat, "pose")


def _rang(etat, domaine):
    return (_section(etat, "commandant").get("rangs") or {}).get(domaine, 0)


def _securite(etat):
    return normaliser(_section(etat, "position").get("securite") or "")


def _besoin_ravitaillement(etat):
    part = _part_carburant(etat)
    coque = _coque(etat)
    modules = _section(etat, "modules").get("liste") or []
    return ((part is not None and part < 0.99) or (coque is not None and coque < 0.999)
            or any((_nombre(m.get("sante")) or 1) < 0.999 for m in modules))


def _services_ravitaillement(etat):
    station = _section(etat, "position").get("station") or {}
    return bool(set(station.get("services") or []) & {"refuel", "repair", "rearm"})


def _cible(etat):
    return _section(etat, "cible")


def _soute(etat):
    return _section(etat, "soute")


def _corps_evalue(etat):
    """Fiche du corps où l'on est, sinon du dernier corps scanné."""
    explo = _section(etat, "exploration")
    fiches = [f for f in explo.get("corps") or [] if f.get("connu")]
    ici = _section(etat, "status").get("corps") or _section(etat, "position").get("corps")
    return next((f for f in fiches if f["nom"] == ici), None) \
        or next((f for f in fiches if f["id"] == explo.get("dernier")), None)


def _montant(n):
    if n is None:
        return None
    for seuil, unite in ((1e9, "Md"), (1e6, "M")):
        if n >= seuil:
            return f"{_format_nombre(n / seuil, 1)} {unite} cr"
    return f"{_format_nombre(n)} cr"


def _detail_corps(f):
    if not f:
        return None
    morceaux_detail = [f["classe"], f"≈ {_montant(f['valeur'])}"]
    if f.get("valeur_carto") != f["valeur"]:
        morceaux_detail.append(f"cartographié ≈ {_montant(f['valeur_carto'])}")
    morceaux_detail.append("première découverte" if f["premiere_decouverte"] else "déjà découvert")
    if f.get("bio") and f["bio"]["max_bonus"]:
        morceaux_detail.append(f"vie : {_montant(f['bio']['min_bonus'])} à {_montant(f['bio']['max_bonus'])}")
    return " · ".join(morceaux_detail)


# nom -> (fonction(etat, paramètre) -> bool, description pour le script d'enregistrement)
CONDITIONS = {
    "matin": (lambda e, p: 5 <= _maintenant().hour < 12, "le matin"),
    "apres_midi": (lambda e, p: 12 <= _maintenant().hour < 18, "l'après-midi"),
    "soir": (lambda e, p: 18 <= _maintenant().hour < 23, "le soir"),
    "nuit": (lambda e, p: _maintenant().hour >= 23 or _maintenant().hour < 5, "la nuit"),
    "amarre": (lambda e, p: _amarre(e), "amarré à une station"),
    "pose": (lambda e, p: _bit(e, "pose") and not _amarre(e), "posé sur une planète"),
    "supercroisiere": (lambda e, p: _bit(e, "supercroisiere"), "en supercroisière"),
    "en_vol": (lambda e, p: _en_vol(e), "en vol"),
    # Flags2 d'abord : à pied en station, Flags peut valoir 0
    "a_pied": (lambda e, p: bool((_section(e, "status").get("flags2") or 0) & 1) or (
        bool(_flags(e)) and not (_bit(e, "vaisseau") or _bit(e, "vrs") or _bit(e, "chasseur"))),
               "à pied"),
    "vrs": (lambda e, p: _bit(e, "vrs"), "en VRS"),
    # Le drapeau du jeu s'allume dès qu'un hostile rôde (zone d'extraction...) : seul, il ne
    # veut pas dire qu'on nous tire dessus
    "danger": (lambda e, p: _bit(e, "interdiction") or (
        _bit(e, "danger") and time.monotonic() - _memoire["combat"] < ENGAGEMENT_RECENT),
               "en danger"),
    "menace_proche": (lambda e, p: _bit(e, "danger") or _bit(e, "interdiction"),
                      "hostiles à proximité"),
    "combat_recent": (lambda e, p: time.monotonic() - _memoire["combat"] < COMBAT_RECENT,
                      "juste après un accrochage"),
    "surchauffe": (lambda e, p: _bit(e, "surchauffe"), "en surchauffe"),
    "boucliers_tombes": (lambda e, p: _en_vol(e) and not _bit(e, "boucliers"),
                         "boucliers tombés"),
    "coque_intacte": (lambda e, p: (_coque(e) or 0) >= 0.99, "coque intacte"),
    "coque_abimee": (lambda e, p: _coque(e) is not None and 0.4 < _coque(e) < 0.99,
                     "coque abîmée"),
    "coque_critique": (lambda e, p: _coque(e) is not None and _coque(e) <= 0.4,
                       "coque sous 40 %"),
    "carburant_plein": (lambda e, p: (_part_carburant(e) or 0) >= 0.95, "réservoir plein"),
    # Mêmes seuils que les alertes (data/config.toml, section [carburant])
    "carburant_bas": (lambda e, p: _part_carburant(e) is not None
                      and _part_carburant(e) < config.valeur("carburant", "seuil_bas") / 100,
                      "carburant sous le seuil bas"),
    "carburant_critique": (lambda e, p: _part_carburant(e) is not None
                           and _part_carburant(e) < config.valeur("carburant", "seuil_critique") / 100,
                           "carburant sous le seuil critique"),
    "besoin_ravitaillement": (lambda e, p: _besoin_ravitaillement(e),
                              "carburant ou réparations à faire"),
    "services_ravitaillement": (lambda e, p: _services_ravitaillement(e),
                                "station avec carburant/réparations"),
    "route": (lambda e, p: _sauts_restants(e) > 0, "route tracée"),
    "dernier_saut": (lambda e, p: _sauts_restants(e) == 1, "un seul saut restant"),
    "route_longue": (lambda e, p: _sauts_restants(e) >= 10, "10 sauts ou plus restants"),
    "cible": (lambda e, p: bool(_cible(e).get("verrouillee")), "cible verrouillée"),
    "cible_recherchee": (lambda e, p: _cible(e).get("statut") == "Wanted", "cible recherchée"),
    "cible_dangereuse": (lambda e, p: _cible(e).get("rang") in ("Dangerous", "Deadly", "Elite"),
                         "pilote dangereux ou mieux"),
    "cible_en_regle": (lambda e, p: (_cible(e).get("verdict") or {}).get("tirer") is False, "cible à ne pas toucher"),
    "chasse_active": (lambda e, p: bool(_section(e, "chasse").get("actif")), "mode chasseur de primes actif"),
    "primes_a_encaisser": (lambda e, p: (_section(e, "chasse").get("a_encaisser_total") or 0) > 0,
                           "primes à encaisser"),
    "corps_evalue": (lambda e, p: bool(_corps_evalue(e)), "corps scanné"),
    "corps_premiere": (lambda e, p: bool((_corps_evalue(e) or {}).get("premiere_decouverte")),
                       "corps jamais découvert"),
    "corps_vivant": (lambda e, p: bool((_corps_evalue(e) or {}).get("bio")), "vie détectée sur le corps"),
    "systeme_evalue": (lambda e, p: bool(_section(e, "exploration").get("total")), "corps scannés ici"),
    "donnees_a_vendre": (lambda e, p: bool((_section(e, "exploration").get("session") or {}).get("a_vendre")
                                           or (_section(e, "exploration").get("session") or {}).get("exo")),
                         "données à vendre"),
    "soute_vide": (lambda e, p: not _soute(e).get("total"), "soute vide"),
    "soute_pleine": (lambda e, p: bool(_section(e, "vaisseau").get("soute_max"))
                     and (_soute(e).get("total") or 0) >= _section(e, "vaisseau")["soute_max"],
                     "soute pleine"),
    "marchandise_volee": (lambda e, p: any(o.get("vole") for o in _soute(e).get("inventaire") or []),
                          "marchandise volée à bord"),
    "recherche": (lambda e, p: _section(e, "status").get("statut_legal")
                  in ("Wanted", "Warrant", "Hostile", "PassengerWanted"), "commandant recherché"),
    "cargaison_illegale": (lambda e, p: _section(e, "status").get("statut_legal") == "IllegalCargo",
                           "cargaison illégale"),
    "fauche": (lambda e, p: _credits(e) is not None and _credits(e) < 1e6, "moins d'1 M cr"),
    "modeste": (lambda e, p: _credits(e) is not None and 1e6 <= _credits(e) < 1e8,
                "1 à 100 M cr"),
    "aise": (lambda e, p: _credits(e) is not None and 1e8 <= _credits(e) < 1e9,
             "100 M à 1 Md cr"),
    "riche": (lambda e, p: (_credits(e) or 0) >= 1e9, "plus d'1 Md cr"),
    "vaisseau": (lambda e, p: (_section(e, "vaisseau").get("type") or "").lower() == p,
                 "vaisseau"),
    "missions_aucune": (lambda e, p: _nb_missions(e) == 0, "aucune mission"),
    "missions": (lambda e, p: _nb_missions(e) >= 1, "missions en cours"),
    "missions_nombreuses": (lambda e, p: _nb_missions(e) >= 10, "10 missions ou plus"),
    "systeme_complet": (lambda e, p: bool(_section(e, "position").get("corps_total"))
                        and (_section(e, "position").get("corps_scannes") or 0)
                        >= _section(e, "position")["corps_total"], "système entièrement scanné"),
    "systeme_a_scanner": (lambda e, p: bool(_section(e, "position").get("corps_total"))
                          and (_section(e, "position").get("corps_scannes") or 0)
                          < _section(e, "position")["corps_total"], "corps restant à scanner"),
    "securite_haute": (lambda e, p: any(m in _securite(e) for m in ("elev", "high")),
                       "système à sécurité élevée"),
    "anarchie": (lambda e, p: any(m in _securite(e) for m in ("anarch", "lawless")),
                 "système anarchique"),
    "elite": (lambda e, p: any(_rang(e, d) >= 8 for d in ("Combat", "Trade", "Explore")),
              "rang Élite atteint"),
    "elite_combat": (lambda e, p: _rang(e, "Combat") >= 8, "Élite au combat"),
    "morts_session": (lambda e, p: (_section(e, "combat").get("morts") or 0) >= 1,
                      "vaisseau détruit aujourd'hui"),
    "chasseur_de_primes": (lambda e, p: (_section(e, "combat").get("eliminations") or 0) >= 10,
                           "10 éliminations ou plus aujourd'hui"),
    "position_connue": (lambda e, p: bool(_section(e, "position").get("systeme")),
                        "système connu"),
    "station_connue": (lambda e, p: bool((_section(e, "position").get("station") or {})
                                         .get("nom")), "station connue"),
    "corps_connu": (lambda e, p: bool(_section(e, "status").get("corps")
                                      or _section(e, "position").get("corps")), "astre connu"),
    "programme": (lambda e, p: bool(_crochets["programme_en_cours"]()),
                  "programme automatique en cours"),
}


def condition_vraie(nom, etat):
    """« coque_critique », « !danger », « vaisseau:python_nx »."""
    negation = nom.startswith("!")
    nom, _, parametre = nom.lstrip("!").partition(":")
    fonction = CONDITIONS[nom][0]
    try:
        resultat = bool(fonction(etat, parametre))
    except Exception:
        resultat = False
    return resultat != negation


def conditions_vraies(conditions, etat):
    return all(condition_vraie(c, etat) for c in conditions or [])


def decrire_condition(nom):
    negation = nom.startswith("!")
    base, _, parametre = nom.lstrip("!").partition(":")
    texte = CONDITIONS[base][1] + (f" {parametre}" if parametre else "")
    return ("pas " if negation else "") + texte


# =====================================================================
#  VALEURS AFFICHÉES OU LUES ({systeme}, {carburant}...)
# =====================================================================
def _format_nombre(n, decimales=0):
    texte = f"{n:,.{decimales}f}".replace(",", " ").replace(".", ",")
    return texte


def _heure_parlee(maintenant):
    if maintenant.hour == 0 and maintenant.minute == 0:
        return "minuit"
    if maintenant.hour == 12 and maintenant.minute == 0:
        return "midi"
    heures = f"{maintenant.hour} heure{'s' if maintenant.hour > 1 else ''}"
    return heures + (f" {maintenant.minute}" if maintenant.minute else "")


def valeurs(etat):
    """Valeurs des {champs} des répliques. Une valeur inconnue vaut None."""
    vaisseau, position, status = (_section(etat, n) for n in ("vaisseau", "position", "status"))
    cible, route = _cible(etat), _section(etat, "route")
    maintenant = _maintenant()
    part = _part_carburant(etat)
    carburant = _nombre(status.get("carburant"))
    credits = _credits(etat)
    sauts = _sauts_restants(etat)
    coque = _coque(etat)
    etapes = route.get("etapes") or []
    explo, tableau = _section(etat, "exploration"), _section(etat, "chasse")
    session, corps_vu = explo.get("session") or {}, _corps_evalue(etat)
    return {
        "corps_nom": corps_vu["nom"] if corps_vu else None,
        "corps_detail": _detail_corps(corps_vu),
        "systeme_valeur": _montant(explo.get("total_carto")) if explo.get("total") else None,
        "systeme_vie": _montant(explo.get("bio_max")) if explo.get("bio_max") else "aucune détectée",
        "a_vendre": _montant(session.get("a_vendre") or 0),
        "exo_a_vendre": _montant(session.get("exo") or 0),
        "primes_total": _montant(tableau.get("a_encaisser_total") or 0),
        "chasse_gains": _montant(tableau.get("gains") or 0),
        "chasse_eliminations": str(tableau.get("eliminations") or 0),
        "commandant": _section(etat, "commandant").get("nom"),
        "vaisseau": vaisseau.get("modele") or vaisseau.get("type"),
        "nom_vaisseau": vaisseau.get("nom"),
        "systeme": position.get("systeme"),
        "station": (position.get("station") or {}).get("nom"),
        "corps": status.get("corps") or position.get("corps"),
        "securite": position.get("securite"),
        "allegeance": position.get("allegeance"),
        "carburant": _format_nombre(carburant, 1) if carburant is not None else None,
        "carburant_max": _format_nombre(vaisseau["carburant_max"], 0)
        if _nombre(vaisseau.get("carburant_max")) else None,
        "carburant_pct": f"{part * 100:.0f} %" if part is not None else None,
        "coque_pct": f"{coque * 100:.0f} %" if coque is not None else None,
        "credits": _format_nombre(credits) + " cr" if credits is not None else None,
        "sauts": str(sauts) if sauts else None,
        "sauts_texte": f"{sauts} saut{'s' if sauts > 1 else ''}" if sauts else None,
        "destination": etapes[-1].get("systeme") if etapes else None,
        "cible_vaisseau": cible.get("vaisseau"),
        "cible_pilote": cible.get("pilote"),
        "cible_rang": RANGS_PILOTES.get(cible.get("rang"), cible.get("rang")),
        "cible_statut": STATUTS_LEGAUX.get(cible.get("statut"), cible.get("statut")),
        "soute": str(_soute(etat).get("total") or 0),
        "soute_max": str(vaisseau["soute_max"]) if vaisseau.get("soute_max") is not None else None,
        "missions": str(_nb_missions(etat)),
        "corps_scannes": str(position.get("corps_scannes") or 0),
        "corps_total": str(position["corps_total"]) if position.get("corps_total") else None,
        "heure": maintenant.strftime("%H:%M"),
        "heure_parlee": _heure_parlee(maintenant),
        "date_galactique": f"{maintenant.day} {MOIS[maintenant.month - 1]} {maintenant.year + 1286}",
    }


class _Inconnue(dict):
    def __missing__(self, cle):
        raise KeyError(cle)


def formater(modele, etat_ou_valeurs):
    """Remplit les {champs}. Renvoie None si l'un d'eux est inconnu."""
    if not modele:
        return modele
    vals = etat_ou_valeurs if "heure_parlee" in etat_ou_valeurs else valeurs(etat_ou_valeurs)
    try:
        return modele.format_map(_Inconnue({k: v for k, v in vals.items() if v is not None}))
    except (KeyError, ValueError, IndexError):
        return None


# =====================================================================
#  CHARGEMENT ET VÉRIFICATION DE conversations.json
# =====================================================================
_contenu = {"sujets": {}, "initiatives": {}, "suites": {}, "types": {}, "erreurs": [],
            "repliques": [], "charge": False}


def _normaliser_question(question):
    return normaliser(question).replace("-", " ")


class _Preparation:
    """Parcourt le JSON : chemins des fichiers, questions normalisées, références."""

    def __init__(self, brut, actions):
        self.brut, self.actions = brut, actions
        self.erreurs, self.repliques = [], []
        self.fichiers = {}             # fichier -> texte (un même fichier = une même phrase)
        self.types = {}
        for nom, liste in (brut.get("reponses_types") or {}).items():
            self.types[nom] = [_normaliser_question(q) for q in liste]
        self.suites = brut.get("suites") or {}
        self.suites_pretes = {}

    def declencheurs(self, bloc, ou):
        """Questions et groupes de mots d'un sujet ou d'une branche."""
        questions = [_normaliser_question(q) for q in bloc.get("questions") or []]
        types = bloc.get("type") or []
        for nom in [types] if isinstance(types, str) else types:
            if nom not in self.types:
                self.erreurs.append(f"{ou} : type de réponse inconnu « {nom} »")
            questions += self.types.get(nom, [])
        bloc["_questions"] = [q for q in questions if q]
        bloc["_mots"] = [[_normaliser_question(m) for m in groupe] for groupe in bloc.get("mots") or []]

    def repliques_de(self, bloc, dossier, ou, chemin):
        for numero, replique in enumerate(bloc.get("repliques") or [], 1):
            self.replique(replique, dossier, f"{ou}, réplique {numero}", chemin)
        if bloc.get("sujet") and bloc["sujet"] not in (self.brut.get("sujets") or {}):
            self.erreurs.append(f"{ou} : sujet inconnu « {bloc['sujet']} »")

    def replique(self, r, dossier, ou, chemin):
        r["_chemin"] = chemin
        for c in r.get("si") or []:
            if c.lstrip("!").partition(":")[0] not in CONDITIONS:
                self.erreurs.append(f"{ou} : contexte inconnu « {c} »")
        if r.get("interne") and r["interne"] not in INTERNES:
            self.erreurs.append(f"{ou} : effet interne inconnu « {r['interne']} »")
        if r.get("commande") and self.actions is not None \
                and r["commande"].partition("|")[0] not in self.actions:
            self.erreurs.append(f"{ou} : commande inconnue « {r['commande']} »")
        if r.get("sujet") and r["sujet"] not in (self.brut.get("sujets") or {}):
            self.erreurs.append(f"{ou} : sujet inconnu « {r['sujet']} »")
        if r.get("morceaux") and r["morceaux"] not in morceaux.RECETTES:
            self.erreurs.append(f"{ou} : morceaux inconnus « {r['morceaux']} »")
        parle = bool(r.get("texte"))
        if not parle and not (r.get("commande") or r.get("sujet")):
            self.erreurs.append(f"{ou} : réplique sans texte")
        if parle and r.get("voix") != "aucune":
            if not r.get("fichier") and not r.get("id"):
                self.erreurs.append(f"{ou} : il manque « id » (nom du fichier à enregistrer)")
            fichier = r.get("fichier") or f"{DOSSIER_SONS}/{dossier}/{r.get('id')}.wav"
            r["_fichier"] = fichier
            if fichier in self.fichiers and self.fichiers[fichier] != r["texte"]:
                self.erreurs.append(f"{ou} : le fichier {fichier} sert déjà à une autre phrase")
            self.fichiers[fichier] = r["texte"]
        if parle:
            self.repliques.append(r)
        if r.get("suite"):
            r["suite"] = self.suite(r["suite"], dossier, ou, chemin)

    def suite(self, suite, dossier, ou, chemin):
        if isinstance(suite, str):                   # suite partagée (section « suites »)
            if suite not in self.suites:
                self.erreurs.append(f"{ou} : suite inconnue « {suite} »")
                return None
            if suite not in self.suites_pretes:
                bloc = self.suites[suite]
                self.suites_pretes[suite] = bloc
                self.suite_bloc(bloc, bloc.get("dossier") or dossier, f"suite « {suite} »",
                                chemin + [f"suite « {suite} »"])
            return self.suites_pretes[suite]
        self.suite_bloc(suite, dossier, ou, chemin)
        return suite

    def suite_bloc(self, suite, dossier, ou, chemin):
        for numero, branche in enumerate(suite.get("branches") or [], 1):
            self.declencheurs(branche, f"{ou}, branche {numero}")
            if not branche["_questions"] and not branche["_mots"]:
                self.erreurs.append(f"{ou}, branche {numero} : aucune réponse attendue")
            etiquette = branche.get("type") or (branche.get("questions") or ["?"])[0]
            if isinstance(etiquette, list):
                etiquette = "/".join(etiquette)
            self.repliques_de(branche, dossier, f"{ou}, branche {numero}",
                              chemin + [f"si « {etiquette} »"])
        for nom, libelle in (("autre", "autre réponse"), ("silence", "sans réponse")):
            if suite.get(nom):
                self.repliques_de(suite[nom], dossier, f"{ou}, {nom}", chemin + [libelle])


def charger(chemin=CHEMIN_CONVERSATIONS, actions=None):
    """Charge conversations.json. `actions` (barks.json) sert à vérifier les « commande ».
    Renvoie la liste des erreurs trouvées (vide si tout va bien)."""
    with open(chemin, "r", encoding="utf-8") as f:
        brut = json.load(f)
    prep = _Preparation(brut, actions)
    sujets = brut.get("sujets") or {}
    for cle, sujet in sujets.items():
        sujet["_cle"] = cle
        prep.declencheurs(sujet, f"sujet « {cle} »")
        prep.repliques_de(sujet, sujet.get("dossier") or "Divers", f"sujet « {cle} »", [])
        if not any(not r.get("si") for r in sujet.get("repliques") or []):
            prep.erreurs.append(f"sujet « {cle} » : aucune réplique sans contexte (réponse par défaut)")
    initiatives = brut.get("initiatives") or {}
    for cle, initiative in initiatives.items():
        initiative["_cle"] = cle
        for c in initiative.get("si") or []:
            if c.lstrip("!").partition(":")[0] not in CONDITIONS:
                prep.erreurs.append(f"initiative « {cle} » : contexte inconnu « {c} »")
        declencheur = initiative.get("declencheur") or {}
        if not declencheur.get("evenement") and not declencheur.get("pendant"):
            prep.erreurs.append(f"initiative « {cle} » : déclencheur « evenement » ou « pendant » manquant")
        prep.repliques_de(initiative, initiative.get("dossier") or "Initiatives",
                          f"initiative « {cle} »", [])

    _contenu.update(sujets=sujets, initiatives=initiatives, suites=prep.suites_pretes,
                    types=prep.types, erreurs=prep.erreurs, repliques=prep.repliques, charge=True)
    return prep.erreurs


def _charge():
    if not _contenu["charge"]:
        charger()
    return _contenu


def sujet(cle):
    return _charge()["sujets"].get(cle)


# =====================================================================
#  RECONNAISSANCE DES QUESTIONS
# =====================================================================
_MOTS_REVEIL = ("covas", "corvus", "kovas")
_INTERJECTIONS = ("he", "hey", "eh", "et", "ok", "oh", "dis", "alors")

_DEBUTS_QUESTION = (
    "comment ", "pourquoi", "combien", "quand ", "ou ", "quel ", "quelle ", "quels ", "quelles ",
    "qui ", "que ", "qu'", "quoi", "est ce", "c'est quoi", "c est quoi", "tu es ", "t'es ",
    "tu as ", "t'as ", "as tu", "es tu", "tu aimes", "tu penses", "tu crois", "tu sais",
    "sais tu", "y a t il", "il y a", "on est ", "on a ", "raconte", "parle moi", "est il",
    "sommes nous", "avons nous", "peut on", "ca va", "dis moi")
# Verbes qui font d'une question une vraie demande (« est-ce que tu peux sortir le train ? »)
_VERBES_DEMANDE = {
    "mets", "met", "lance", "active", "desactive", "coupe", "sors", "rentre", "ouvre", "ferme",
    "allume", "eteins", "deploie", "passe", "donne", "envoie", "largue", "cible", "vise", "fais",
    "engage", "demande", "trace", "suis", "emmene", "amene", "conduis", "decolle", "quitte",
    "ravitaille", "repare", "rearme", "affiche", "annule", "arrete", "stop", "balance", "verrouille",
    "boost", "booste", "saute", "rappelle", "attaque", "defends", "protege"}
_DEBUTS_DEMANDE = ("peu", "pourr", "pouv", "voudr", "voul", "veu")


def sans_reveil(texte_norm):
    """Retire le « Covas » d'adresse en tête de phrase (« Hé Covas, ... »)."""
    mots = texte_norm.split()

    def reveil(mot):
        return mot in _MOTS_REVEIL or similarite(mot, "covas") >= 0.8

    while mots and (reveil(mots[0]) or (mots[0] in _INTERJECTIONS and len(mots) > 1
                                         and reveil(mots[1]))):
        mots.pop(0)
    return " ".join(mots)


def est_question(texte_norm):
    mots = texte_norm.split()
    candidats = [texte_norm, " ".join(mots[1:])] if len(mots) > 1 else [texte_norm]
    return any((c + " ").startswith(_DEBUTS_QUESTION) for c in candidats)


def est_demande(texte_norm):
    return any(mot in _VERBES_DEMANDE or mot.startswith(_DEBUTS_DEMANDE)
               for mot in texte_norm.replace("'", " ").split())


def score_exact(texte_norm, questions, groupes_mots):
    """Longueur du meilleur déclencheur présent dans la phrase (0 si aucun).
    Questions : en mots entiers. Groupes de mots : chaque mot présent en début de mot,
    dans n'importe quel ordre (« thargo » trouve « thargoïdes »)."""
    entoure = f" {texte_norm} "
    meilleur = 0
    for question in questions:
        if f" {question} " in entoure and len(question) > meilleur:
            meilleur = len(question)
    for groupe in groupes_mots:
        if groupe and all(present(m, texte_norm) for m in groupe):
            meilleur = max(meilleur, sum(len(m) for m in groupe) + len(groupe) - 1)
    return meilleur


LONGUEUR_MIN_APPROCHE = 12   # une question plus courte doit être entendue telle quelle
                             # (« c'est quoi » ressemble trop à « c'est qui »)


def score_approche(texte_norm, questions):
    return max((meilleure_approche(texte_norm, q) for q in questions
                if len(q) >= LONGUEUR_MIN_APPROCHE), default=0.0)


def trouver_sujet(texte_norm):
    """(clé du sujet, score exact, similarité approchée) du sujet le plus proche."""
    exact, score_max = None, 0
    approche, similarite_max = None, 0.0
    for cle, s in _charge()["sujets"].items():
        if not s["_questions"] and not s["_mots"]:
            continue                                  # sujet caché (atteint par référence)
        score = score_exact(texte_norm, s["_questions"], s["_mots"])
        if score > score_max:
            exact, score_max = cle, score
    if not exact:
        approche, similarite_max = trouver_sujet_approche(texte_norm)
    return exact, score_max, approche, similarite_max


def trouver_sujet_approche(texte_norm):
    """(clé, similarité) du sujet dont une question ressemble le plus à la phrase."""
    approche, similarite_max = None, 0.0
    for cle, s in _charge()["sujets"].items():
        proche = score_approche(texte_norm, s["_questions"])
        if proche > similarite_max:
            approche, similarite_max = cle, proche
    return approche, similarite_max


# =====================================================================
#  CHOIX DE LA RÉPLIQUE
# =====================================================================
_memoire = {"dernieres": {}, "combat": -1e9, "paroles": deque(maxlen=4)}


def choisir(repliques, etat, memoire=None):
    """Parmi les répliques dont le contexte est vrai : priorité la plus haute, puis contexte
    le plus précis ; au hasard entre égales, sans redire la dernière."""
    candidates = [r for r in repliques or [] if conditions_vraies(r.get("si"), etat)]
    if not candidates:
        return None
    priorite = max(r.get("priorite", 0) for r in candidates)
    candidates = [r for r in candidates if r.get("priorite", 0) == priorite]
    precision = max(len(r.get("si") or []) for r in candidates)
    candidates = [r for r in candidates if len(r.get("si") or []) == precision]
    cle = memoire or id(repliques)
    if len(candidates) > 1:
        candidates = [r for r in candidates if r is not _memoire["dernieres"].get(cle)] or candidates
    choisie = random.choice(candidates)
    _memoire["dernieres"][cle] = choisie
    return choisie


def choisir_dans(bloc, etat):
    """Bloc = sujet, branche, « autre », « silence » ou initiative."""
    if bloc.get("repliques"):
        replique = choisir(bloc["repliques"], etat, memoire=id(bloc))
        if replique:
            return replique
    if bloc.get("sujet") and sujet(bloc["sujet"]):
        return choisir(sujet(bloc["sujet"])["repliques"], etat, memoire=bloc["sujet"])
    return None


# =====================================================================
#  RÉPONSES ATTENDUES (suites)
# =====================================================================
_attente = {"suite": None, "jusqu_a": 0.0}


def attendre_reponse(suite):
    _attente.update(suite=suite, jusqu_a=time.monotonic() + suite.get("attente", ATTENTE_REPONSE))


def attend_reponse():
    return _attente["suite"] is not None and time.monotonic() < _attente["jusqu_a"]


def annuler_attente():
    _attente.update(suite=None, jusqu_a=0.0)


def attente_expiree():
    """La suite restée sans réponse (une seule fois), sinon None."""
    if _attente["suite"] is not None and time.monotonic() >= _attente["jusqu_a"]:
        suite = _attente["suite"]
        annuler_attente()
        return suite
    return None


def _branche(suite, texte_norm, accepter_autre):
    meilleure, score_max = None, 0
    for branche in suite.get("branches") or []:
        score = score_exact(texte_norm, branche["_questions"], branche["_mots"])
        if score > score_max:
            meilleure, score_max = branche, score
    if meilleure:
        return meilleure
    for branche in suite.get("branches") or []:
        if score_approche(texte_norm, branche["_questions"]) >= SEUIL_APPROCHE:
            return branche
    if accepter_autre and suite.get("autre") and texte_norm:
        return suite["autre"]
    return None


def _echo(texte_norm):
    """Vrai si la phrase ressemble à ce que le COVAS vient de dire (sa voix dans le micro)."""
    limite = time.monotonic() - 30
    return any(instant > limite and similarite(texte_norm, dit) >= SEUIL_ECHO
               for instant, dit in _memoire["paroles"])


# =====================================================================
#  DÉCISION : commande, conversation ou rien
# =====================================================================
@dataclass
class Decision:
    type: str                  # "commande" | "conversation" | "ignore" | "rien"
    action: str = None         # commande : clé de barks.json
    replique: dict = None      # conversation : réplique choisie
    sujet: str = None          # conversation : sujet (ou « suite »)
    raison: str = ""


def decider(texte, actions, ignorees=(), etat=None, reveil=True, echo_possible=False):
    """
    texte         : phrase entendue (politesse déjà retirée)
    actions       : barks.json (les commandes)
    reveil        : False si la phrase ne contient pas « Covas » : seule une réponse attendue
                    par le COVAS peut alors être prise en compte
    echo_possible : le COVAS parlait pendant l'écoute (sa voix a pu être captée)
    """
    texte_norm = sans_reveil(_normaliser_question(texte))
    if echo_possible and _echo(texte_norm):
        return Decision("ignore", raison="écho de la voix du COVAS")

    # 1. Le COVAS attend une réponse : « oui », « non », la solution d'une devinette...
    if attend_reponse():
        branche = _branche(_attente["suite"], texte_norm, accepter_autre=not echo_possible)
        if branche is _attente["suite"].get("autre") and reveil \
                and trouver_action_detail(texte, actions, ignorees).exacte:
            branche = None              # « Covas, sors le train » : un ordre, pas une réponse
        if branche:
            annuler_attente()
            replique = choisir_dans(branche, etat)
            if replique:
                return Decision("conversation", replique=replique, sujet="suite",
                                raison="réponse à la question du COVAS")
        if not reveil:
            return Decision("ignore", raison="sans rapport avec la question du COVAS")
        annuler_attente()                 # nouvelle demande : la question est abandonnée
    elif not reveil:
        return Decision("ignore", raison="mot de réveil absent")
    if not texte_norm:
        return Decision("rien")

    # 2. Commande ou conversation ?
    commande = trouver_action_detail(texte, actions, ignorees)
    cle_sujet, score_sujet, sujet_approche, similarite_sujet = trouver_sujet(texte_norm)
    question = est_question(texte_norm)

    def conversation(cle, raison):
        replique = choisir(sujet(cle)["repliques"], etat, memoire=cle)
        if not replique:
            return Decision("rien", raison=f"aucune réplique de « {cle} » pour ce contexte")
        return Decision("conversation", replique=replique, sujet=cle, raison=raison)

    def inconnue():
        if sujet("question_inconnue"):
            return conversation("question_inconnue", "question sans réponse prévue")
        return Decision("rien", raison="question non reconnue")

    if cle_sujet:
        faible = sujet(cle_sujet).get("faible")
        if not commande.exacte or (not faible and score_sujet > len(commande.mot_cle)) \
                or (not faible and score_sujet == len(commande.mot_cle) and question):
            return conversation(cle_sujet, "question reconnue")

    if commande.exacte:
        # « Comment vont les boucliers ? » : une question qui contient juste un mot de
        # commande n'est pas un ordre (pas de verbe de demande, mot-clé d'un seul mot)
        if question and not est_demande(texte_norm) and " " not in commande.mot_cle:
            if cle_sujet:
                return conversation(cle_sujet, "question reconnue")
            sujet_approche, similarite_sujet = trouver_sujet_approche(texte_norm)
            if sujet_approche and similarite_sujet >= SEUIL_APPROCHE:
                return conversation(sujet_approche, f"question approchée ({similarite_sujet:.0%})")
            return inconnue()
        return Decision("commande", action=commande.cle, raison="commande reconnue")

    # 3. Rien d'exact : la meilleure approximation
    if sujet_approche and similarite_sujet >= SEUIL_APPROCHE and (
            not commande.cle or similarite_sujet > commande.score
            or (similarite_sujet == commande.score and question)):
        return conversation(sujet_approche, f"question approchée ({similarite_sujet:.0%})")
    if commande.cle:
        return Decision("commande", action=commande.cle,
                        raison=f"commande approchée ({commande.score:.0%})")
    if question:
        return inconnue()
    return Decision("rien", raison="rien de reconnu")


# =====================================================================
#  JOUER UNE RÉPLIQUE
# =====================================================================
def texte_de(replique, etat):
    """(texte dit, détail affiché à l'écran) ; texte None si un {champ} est inconnu."""
    vals = valeurs(etat)
    texte = formater(replique.get("texte") or "", vals)
    detail = formater(replique.get("ecran"), vals) if replique.get("ecran") else None
    return texte, detail


def chemin_enregistrement(replique):
    """Chemin complet du son enregistré (.wav ou .mp3, quelle que soit l'extension écrite),
    ou None (réplique sans voix, ou fichier pas encore créé)."""
    if replique.get("voix") == "aucune" or not replique.get("_fichier"):
        return None
    return sons.trouver(os.path.join(DOSSIER_BACKEND, *replique["_fichier"].split("/")))


async def jouer(replique, etat, *, dire, afficher, commander=None, profondeur=0):
    """Joue une réplique puis ses effets.
    dire(chemin)              : joue le .wav ET attend la fin
    afficher(texte, detail)   : montre la réplique dans l'interface
    commander("action|texte") : lance une commande du COVAS (rapport d'avarie, ravitaillement...)
    """
    texte, detail = texte_de(replique, etat)
    if replique.get("texte") and texte is None:
        _log.warning(f"Valeur inconnue dans « {replique['texte']} » : réplique sautée")
    elif texte:
        _memoire["paroles"].append((time.monotonic(), _normaliser_question(texte)))
        await afficher(texte, detail)
        chemin = chemin_enregistrement(replique)
        if not chemin and replique.get("morceaux"):     # heure, date, position : morceaux du studio
            chemin = await asyncio.to_thread(
                morceaux.assembler, morceaux.recette(replique["morceaux"], _maintenant()))
        if chemin:
            await dire(chemin)
    elif detail:
        await afficher("", detail)

    if replique.get("interne"):
        appliquer_interne(replique["interne"])
    if replique.get("commande") and commander:
        await commander(replique["commande"])
    if replique.get("sujet") and profondeur < PROFONDEUR_MAX and sujet(replique["sujet"]):
        suivante = choisir(sujet(replique["sujet"])["repliques"], etat, memoire=replique["sujet"])
        if suivante:
            return await jouer(suivante, etat, dire=dire, afficher=afficher, commander=commander,
                               profondeur=profondeur + 1)
    if replique.get("suite"):
        attendre_reponse(replique["suite"])


# =====================================================================
#  INITIATIVES : le COVAS engage la conversation
# =====================================================================
_initiatives = {"actives": INITIATIVES_AU_DEMARRAGE, "derniere": -1e9, "repos": {},
                "programmees": [], "depuis": {}}
_crochets = {"programme_en_cours": lambda: False}


def configurer(programme_en_cours=None):
    if programme_en_cours:
        _crochets["programme_en_cours"] = programme_en_cours


def appliquer_interne(effet):
    if effet == "initiatives_off":
        _initiatives["actives"] = False
    elif effet == "initiatives_on":
        _initiatives["actives"] = True


def initiatives_actives():
    return _initiatives["actives"]


def _champs_ok(champs, evenement):
    for nom, attendu in (champs or {}).items():
        if evenement.get(nom) not in (attendu if isinstance(attendu, list) else [attendu]):
            return False
    return True


def observer_evenement(evenement):
    """À brancher sur lecteur_logs.ecouter_evenements (événements en direct du journal)."""
    nom = evenement.get("event")
    if nom in EVENEMENTS_COMBAT and not evenement.get("Fighter") \
            and evenement.get("Target") != "Fighter":
        _memoire["combat"] = time.monotonic()
    if nom == "ShieldState" and not evenement.get("ShieldsUp"):
        _memoire["combat"] = time.monotonic()
    for cle, initiative in _charge()["initiatives"].items():
        declencheur = initiative.get("declencheur") or {}
        if declencheur.get("evenement") == nom and _champs_ok(declencheur.get("champs"), evenement):
            echeance = time.monotonic() + initiative.get("delai", 2)
            _initiatives["programmees"].append({"cle": cle, "a": echeance, "fin": echeance + 45})


def _peut_lancer(cle, initiative, etat, occupe):
    maintenant = time.monotonic()
    if not _initiatives["actives"] or occupe() or attend_reponse():
        return False
    if _crochets["programme_en_cours"]():
        return False
    if maintenant - _initiatives["derniere"] < ECART_INITIATIVES:
        return False
    if maintenant - _initiatives["repos"].get(cle, -1e9) < initiative.get("repos", 600):
        return False
    return conditions_vraies(initiative.get("si"), etat)


async def _lancer(cle, initiative, etat, jouer_initiative):
    _initiatives["repos"][cle] = time.monotonic()        # même si le hasard dit non
    if random.random() >= initiative.get("chance", 1.0):
        return False
    replique = choisir_dans(initiative, etat)
    if not replique:
        return False
    _initiatives["derniere"] = time.monotonic()
    await jouer_initiative(replique)
    return True


async def tour_initiatives(etat, jouer_initiative, occupe):
    """Un passage de la surveillance (appelé chaque seconde)."""
    maintenant = time.monotonic()

    # 1. Question du COVAS restée sans réponse
    suite = attente_expiree()
    if suite and suite.get("silence"):
        replique = choisir_dans(suite["silence"], etat)
        if replique:
            await jouer_initiative(replique)
        return

    # 2. Déclencheurs « pendant » : contexte vrai depuis N secondes
    for cle, initiative in _charge()["initiatives"].items():
        duree = (initiative.get("declencheur") or {}).get("pendant")
        if not duree:
            continue
        if not conditions_vraies(initiative.get("si"), etat):
            _initiatives["depuis"].pop(cle, None)
            continue
        depuis = _initiatives["depuis"].setdefault(cle, maintenant)
        if maintenant - depuis >= duree and _peut_lancer(cle, initiative, etat, occupe):
            _initiatives["depuis"][cle] = maintenant
            if await _lancer(cle, initiative, etat, jouer_initiative):
                return

    # 3. Déclencheurs « evenement » arrivés à échéance
    restantes = []
    for prevue in _initiatives["programmees"]:
        initiative = _charge()["initiatives"].get(prevue["cle"])
        if not initiative or maintenant > prevue["fin"]:
            continue
        if maintenant < prevue["a"] or not _peut_lancer(prevue["cle"], initiative, etat, occupe):
            if maintenant < prevue["a"] or conditions_vraies(initiative.get("si"), etat):
                restantes.append(prevue)          # trop tôt, ou occupé : on réessaie
            continue
        await _lancer(prevue["cle"], initiative, etat, jouer_initiative)
    _initiatives["programmees"] = restantes


async def surveiller_initiatives(etat, jouer_initiative, occupe):
    """Tâche de fond (main.py). jouer_initiative(replique) : async ; occupe() -> bool."""
    while True:
        await asyncio.sleep(1)
        try:
            await tour_initiatives(etat, jouer_initiative, occupe)
        except Exception:
            _log.exception("Erreur dans la surveillance des initiatives")


# =====================================================================
#  SCRIPT D'ENREGISTREMENT (data/SCRIPT_CONVERSATIONS.md)
# =====================================================================
TITRES_DOSSIERS = {"Social": "Échanges courants", "Personnalite": "Personnalité du COVAS",
                   "Bord": "Questions de bord", "Univers": "La galaxie et son histoire",
                   "Jeux": "Jeux", "Meta": "Aide et réglages", "Initiatives": "Le COVAS prend la parole"}


def _questions_lisibles(bloc, maxi=10):
    exemples = [f"« {q} »" for q in (bloc.get("questions") or [])[:maxi]]
    for groupe in bloc.get("mots") or []:
        exemples.append("toute phrase avec « " + " » + « ".join(groupe) + " »")
    return ", ".join(exemples) or "—"


def _lignes_repliques(bloc, contexte_parent, lignes, sans_voix):
    for r in bloc.get("repliques") or []:
        contexte = list(contexte_parent) + [decrire_condition(c) for c in r.get("si") or []]
        etiquette = " · ".join(contexte) or "toujours"
        if r.get("texte"):
            if r.get("voix") == "aucune":
                sans_voix.append((etiquette, r["texte"]))
            else:
                fait = "✅" if chemin_enregistrement(r) else "⬜"
                lignes.append(f"| {fait} | {etiquette} | `{r['_fichier']}` | {r['texte']} |")
        effets = []
        if r.get("commande"):
            effets.append(f"lance la commande `{r['commande'].partition('|')[0]}`")
        if r.get("sujet"):
            effets.append(f"enchaîne sur le sujet `{r['sujet']}`")
        if effets and not r.get("texte"):
            lignes.append(f"|  | {etiquette} | — | *({', '.join(effets)}, sans rien dire)* |")
        suite = r.get("suite")
        if suite and not suite.get("_ecrite"):
            suite["_ecrite"] = True
            amorce = f"↳ après « {(r.get('texte') or '')[:38]}… »"
            for branche in suite.get("branches") or []:
                reponses = ", ".join(f"« {q} »" for q in (branche.get("questions") or [])[:4])
                types = branche.get("type") or []
                types = [types] if isinstance(types, str) else types
                nom = " / ".join([f"*{t}*" for t in types] + ([reponses] if reponses else []))
                sous = [amorce, f"réponse {nom}"]
                if branche.get("sujet") and not branche.get("repliques"):
                    lignes.append(f"|  | {' · '.join(sous)} | — | *(enchaîne sur le sujet "
                                  f"`{branche['sujet']}`)* |")
                _lignes_repliques(branche, sous, lignes, sans_voix)
            for nom, libelle in (("autre", "toute autre réponse"), ("silence", "pas de réponse")):
                if suite.get(nom):
                    _lignes_repliques(suite[nom], [amorce, libelle], lignes, sans_voix)


def ecrire_script(chemin=CHEMIN_SCRIPT):
    contenu = _charge()
    for r in contenu["repliques"]:
        if isinstance(r.get("suite"), dict):
            r["suite"].pop("_ecrite", None)
    enregistrables = [r for r in contenu["repliques"] if r.get("voix") != "aucune"]
    faits = sum(1 for r in enregistrables if chemin_enregistrement(r))
    fichiers = {r["_fichier"] for r in enregistrables}
    corps, sans_voix = [], []

    def section(titre, blocs, est_initiative=False):
        corps.extend(["", f"## {titre}", ""])
        for cle, bloc in blocs:
            corps.append(f"### {bloc.get('titre') or cle} (`{cle}`)")
            corps.append("")
            if est_initiative:
                declencheur = bloc.get("declencheur") or {}
                quand = (f"événement du journal `{declencheur['evenement']}`"
                         if declencheur.get("evenement")
                         else f"contexte vrai depuis {declencheur.get('pendant')} s")
                contexte = ", ".join(decrire_condition(c) for c in bloc.get("si") or [])
                corps.append(f"*Le COVAS parle de lui-même :* {quand}"
                             + (f" — si {contexte}" if contexte else "")
                             + f" (chance {int(bloc.get('chance', 1) * 100)} %, "
                               f"pas plus d'une fois toutes les {bloc.get('repos', 600) // 60} min).")
            elif bloc.get("_questions") or bloc.get("_mots"):
                corps.append(f"*Questions :* {_questions_lisibles(bloc)}")
            else:
                corps.append("*Sujet caché : atteint seulement par une autre réplique.*")
            corps.extend(["", "| | Contexte | Fichier | Phrase à dire |", "|---|---|---|---|"])
            _lignes_repliques(bloc, [], corps, sans_voix)
            corps.append("")

    groupes = {}
    for cle, s in contenu["sujets"].items():
        groupes.setdefault(s.get("dossier") or "Divers", []).append((cle, s))
    for dossier, blocs in groupes.items():
        section(f"{TITRES_DOSSIERS.get(dossier, dossier)} — `{DOSSIER_SONS}/{dossier}/`", blocs)
    section(f"Le COVAS prend la parole — `{DOSSIER_SONS}/Initiatives/`",
            list(contenu["initiatives"].items()), est_initiative=True)

    entete = [
        "# Script des conversations à enregistrer",
        "",
        "*Fichier généré par `python -m module.dialogue.conversation --script` (depuis `Backend/`) à partir "
        "de `data/conversations.json` : modifie le JSON, pas ce fichier.*",
        "",
        f"**{len(fichiers)} fichiers à enregistrer** — {faits} déjà faits ✅, "
        f"{len(fichiers) - faits} à faire ⬜.",
        "",
        "Le plus simple : `STUDIO VOCAL.bat` (à la racine) liste ces phrases, transforme ta voix en voix "
        "du COVAS et range chaque fichier au bon endroit. Sinon, enregistre chaque phrase et range le "
        "fichier `.wav` au chemin indiqué (dans `Backend/`). "
        "Tant qu'un fichier manque, la phrase est seulement affichée à l'écran.",
        "",
        "- **Contexte** : la réplique n'est choisie que dans cette situation. Une réplique "
        "« toujours » est la réponse par défaut.",
        "- **↳ après « … »** : le COVAS vient de poser une question ; le commandant répond "
        "sans redire « Covas » (8 s par défaut, 15 s pour les devinettes).",
        "- Tu peux changer une phrase : modifie `texte` dans le JSON (le fichier garde son nom).",
    ]
    if sans_voix:
        corps.extend(["", "## Répliques à texte variable (à enregistrer en morceaux dans le studio vocal)", "",
                      "Leur texte change à chaque fois (heure, système...).", "",
                      "| Contexte | Phrase |", "|---|---|"])
        corps.extend(f"| {contexte} | {texte} |" for contexte, texte in sans_voix)
    with open(chemin, "w", encoding="utf-8") as f:
        f.write("\n".join(entete + corps) + "\n")
    return len(fichiers), faits
