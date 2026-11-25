"""
studio.py — Studio vocal : les répliques du COVAS dites avec TA voix, transformée en voix du COVAS.

La fenêtre est Backend/studio_vocal.py (lancée par « STUDIO VOCAL.bat »). Elle est indépendante
du COVAS : ni Whisper au démarrage, ni touches, ni jeu ; le COVAS peut tourner en même temps.
Ce module fait le travail sans micro ni fenêtre (il reçoit des échantillons, écrit des fichiers) :

  inventaire()          toutes les répliques à dire : data/SCRIPT_VOIX.md (alertes, commandes...),
                        les enregistrements d'origine (data/studio/originaux.json) et les
                        conversations (data/conversations.json) et morceaux des phrases qui
                        changent : rapport d'avarie, heure, date, position (module/dialogue/morceaux.py)
  Studio.traiter()      prise du micro -> voix nettoyée -> voix du COVAS (module/studio/effet_voix.py)
  Studio.garder()       range la réplique là où le COVAS la cherche (data/son/..., en .mp3)
  Studio.etalonner()    égalisation calculée sur TA voix pour retrouver le timbre des
                        enregistrements d'origine (et ta hauteur habituelle)
  Studio.appliquer_a_toutes()  refait toutes les répliques gardées avec les réglages actuels

Rangement (dans Backend/data/) :
  son/<...>.mp3             la réplique transformée : le COVAS la joue telle quelle
  studio/prises/<...>.mp3   ta prise d'origine, non transformée : permet de tout refaire si tu
                            changes la voix, sans rien réenregistrer
  studio/prises.json        registre des prises gardées (phrase, date, réglages utilisés)
  studio/reglages.json      réglages de la voix (profil, hauteur, timbre, égalisation étalonnée...)
  studio/remplaces/<...>    enregistrements faits à la main remplacés par une prise du studio
Une réplique gardée sort de data/son/repliques_synthese.json (anciens fichiers à réenregistrer).
"""
import copy
import hashlib
import itertools
import json
import logging
import os
import shutil
import tempfile
import threading
from datetime import datetime

import numpy as np

from module.studio import effet_voix
from module.son import sons

_log = logging.getLogger(__name__)

DOSSIER_BACKEND = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOSSIER_STUDIO = os.path.join(DOSSIER_BACKEND, "data", "studio")
CHEMIN_REGLAGES = os.path.join(DOSSIER_STUDIO, "reglages.json")
CHEMIN_PRISES = os.path.join(DOSSIER_STUDIO, "prises.json")
CHEMIN_ORIGINAUX = os.path.join(DOSSIER_STUDIO, "originaux.json")
DOSSIER_PRISES = os.path.join(DOSSIER_STUDIO, "prises")
DOSSIER_REMPLACES = os.path.join(DOSSIER_STUDIO, "remplaces")

DEBIT_COVAS = sons.DEBIT_ENREGISTREMENT   # réplique transformée : stéréo 48 kHz, comme celles d'origine
DEBIT_PRISE = 96000                       # prise d'origine : mono
MARGE_PRISE = 0.3                         # secondes gardées autour de la parole dans la prise d'origine
PAROLE_ETALONNAGE = 15.0                  # secondes de voix conseillées pour étalonner
PAROLE_ETALONNAGE_MIN = 6.0               # en dessous, la courbe ne serait pas fiable
ETALONNAGE_MAX = 150.0                    # secondes de voix au plus (les plus récentes)
PRISES_SEANCE = 40                        # prises de la séance gardées en mémoire pour l'étalonnage

# Ta voix -> voix du COVAS : mesuré le 2026-11-22 sur deux paires « ta voix brute / réplique d'origine »
# (testVoice/ : FSD3 et EchangeRole), alignées syllabe par syllabe : les originaux sont ~1,9 demi-ton
# plus haut que ta voix et leurs formants ~22 % plus hauts (timbre plus « petit » et plus clair).
# Salle, peigne et stéréo : voir effet_voix.EFFET_BASE.
VOIX_STUDIO = {"decalage_dt": 1.9, "formants": 1.22}
VERSION_REGLAGES = 2            # 2 : nouvelle salle, formants, aigus recréés (2026-11-22)

# Réglages proposés dans la fenêtre (curseurs). Les autres restent ceux du profil.
REGLABLES = [
    {"cle": "decalage_dt", "nom": "Hauteur", "min": -6, "max": 8, "pas": 0.1, "unite": "demi-tons",
     "aide": "Décalage de ta voix, en demi-tons (mesuré sur les originaux : +1,9)."},
    {"cle": "intonation", "nom": "Intonation", "min": 0, "max": 1.5, "pas": 0.05, "unite": "",
     "aide": "0 = monocorde, 1 = ta mélodie telle quelle, au-delà = plus chantante."},
    {"cle": "formants", "nom": "Timbre", "min": 0.8, "max": 1.5, "pas": 0.01, "unite": "",
     "aide": "Taille de la gorge : au-dessus de 1, voix plus claire (plus féminine) ; en dessous, plus "
             "sombre. Mesuré sur les originaux : 1,22."},
    {"cle": "peigne_dose", "nom": "Métal", "min": 0, "max": 0.8, "pas": 0.01, "unite": "",
     "aide": "Part de résonance de tôle (peigne de 13 ms) dans la voix."},
    {"cle": "peigne_retour", "nom": "Résonance", "min": 0, "max": 0.85, "pas": 0.01, "unite": "",
     "aide": "Force de cette résonance : plus haut, plus métallique."},
    {"cle": "salle_dose", "nom": "Salle", "min": 0, "max": 1.5, "pas": 0.05, "unite": "",
     "aide": "Pièce autour de la voix, la même à gauche et à droite (traîne de 0,3 s)."},
    {"cle": "reverbe_dose", "nom": "Largeur", "min": 0, "max": 2, "pas": 0.05, "unite": "",
     "aide": "Petite boîte différente à gauche et à droite : plus haut, voix plus large et diffuse."},
    {"cle": "vocodeur", "nom": "Vocodeur", "min": 0, "max": 1, "pas": 0.05, "unite": "",
     "aide": "0 = ta voix traitée ; 1 = robot à vocodeur (note continue sculptée par ta voix)."},
]
CLES_REGLABLES = [r["cle"] for r in REGLABLES]
DEBRUITAGE = {"cle": "debruitage", "nom": "Débruitage", "min": 0, "max": 1, "pas": 0.05, "unite": "",
              "aide": "Retire le bruit de fond (ventilateur, souffle). Trop fort, la voix devient « aquatique »."}

SOURCES = {"repliques": "Alertes et commandes", "origine": "Enregistrements d'origine",
           "conversations": "Conversations", "morceaux": "Rapport, heure, date, position"}
ETATS = {"studio": "ta voix", "synthese": "synthèse", "origine": "enregistrement d'origine",
         "manquante": "à enregistrer"}


def _valeurs_profil(profil):
    base = effet_voix.reglages(profil, VOIX_STUDIO)
    return {cle: base[cle] for cle in CLES_REGLABLES}


REGLAGES_DEFAUT = {
    "version": VERSION_REGLAGES,
    "profil": "fidele",
    "valeurs": _valeurs_profil("fidele"),
    "debruitage": 0.6,
    "egalisation": None,        # points (Hz, dB) étalonnés sur ta voix ; None = courbe provisoire
    "reference_hz": None,       # ta hauteur habituelle (étalonnage)
    "etalonnage": None,         # {"date", "secondes", "prises", "hauteur_hz"}
    "micro": None,              # nom du micro choisi (None = celui de Windows)
    "verifier": True,           # Whisper écoute chaque prise
    "ecoute_auto": True,        # la voix du COVAS est jouée dès la fin de la prise
}


# Égalisation (Hz, dB) utilisée tant que ta voix n'est pas étalonnée
EGALISATION_PROVISOIRE = (
    (40, -21.5), (100, -15.5), (126, -30.0), (159, -30.0), (200, -20.0), (252, -15.5),
    (317, -7.0), (400, 4.0), (504, 1.5), (635, -2.5), (800, -11.0), (1008, -3.0),
    (1270, -1.0), (1600, -3.5), (2016, -3.0), (2540, -3.0), (3200, 2.0), (4032, 10.5),
    (5080, 5.5), (6400, -5.5), (8063, -12.0), (10159, -19.0), (11000, -31.0),
)


def _egalisation_provisoire():
    return EGALISATION_PROVISOIRE


# =====================================================================
#  FICHIERS JSON
# =====================================================================
def _lire_json(chemin, defaut):
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return copy.deepcopy(defaut)


def _ecrire_json(chemin, donnees):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    provisoire = chemin + ".partiel"
    with open(provisoire, "w", encoding="utf-8", newline="\r\n") as f:
        json.dump(donnees, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(provisoire, chemin)


def lire_reglages():
    lus = _lire_json(CHEMIN_REGLAGES, {})
    if lus and lus.get("version", 1) < VERSION_REGLAGES:
        # la chaîne a changé : les curseurs repartent des valeurs mesurées et l'égalisation, calculée
        # pour l'ancienne chaîne, est à refaire. Ta hauteur habituelle reste valable.
        lus = {k: v for k, v in lus.items() if k not in ("valeurs", "egalisation", "etalonnage", "version")}
    reglages = copy.deepcopy(REGLAGES_DEFAUT)
    reglages.update({k: v for k, v in lus.items() if k in REGLAGES_DEFAUT})
    reglages["valeurs"] = {**REGLAGES_DEFAUT["valeurs"], **(lus.get("valeurs") or {})}
    if reglages["profil"] not in effet_voix.PROFILS:
        reglages["profil"] = "fidele"
    return reglages


def lire_prises():
    return _lire_json(CHEMIN_PRISES, {})


def _lire_registre_synthese():
    from module.studio import repliques
    return repliques.lire_registre()


def _ecrire_registre_synthese(registre):
    from module.studio import repliques
    repliques.ecrire_registre(registre)


def relatif_mp3(chemin):
    """« data/son/X/Y.wav » -> « data/son/X/Y.mp3 » : l'identifiant d'une réplique."""
    return os.path.splitext(chemin.replace("\\", "/"))[0] + ".mp3"


def absolu(relatif):
    return os.path.join(DOSSIER_BACKEND, *relatif.split("/"))


def chemin_prise(ident):
    """Où est rangée la prise d'origine d'une réplique."""
    sous = ident[len("data/son/"):] if ident.startswith("data/son/") else ident
    return os.path.join(DOSSIER_PRISES, *sous.split("/"))


# =====================================================================
#  INVENTAIRE DES RÉPLIQUES
# =====================================================================
def _lignes_script():
    from module.studio import repliques
    lignes, section = [], "Répliques"
    with open(repliques.CHEMIN_SCRIPT, encoding="utf-8") as f:
        for ligne in f:
            if ligne.startswith("## "):
                section = ligne[3:].strip()
            m = repliques.LIGNE.match(ligne.strip())
            if m and sons.est_son(m.group(2)):
                lignes.append({"id": relatif_mp3(m.group(2)), "source": "repliques", "groupe": section,
                               "contexte": m.group(1), "texte": m.group(3)})
    return lignes


def _lignes_originaux():
    lignes = []
    for chemin, info in _lire_json(CHEMIN_ORIGINAUX, {}).items():
        if chemin.startswith("_") or not isinstance(info, dict):
            continue
        note = None if info.get("retrouvee") else (
            "Phrase reconstituée d'après le nom du fichier" + (" (incertaine)" if info.get("incertain") else "")
            + " : écoute l'original (touche A) avant de la dire.")
        lignes.append({"id": relatif_mp3(chemin), "source": "origine", "groupe": SOURCES["origine"],
                       "contexte": info.get("cle", ""), "texte": info.get("texte", ""), "note": note})
    return lignes


def _court(texte, n=38):
    texte = texte or ""
    return texte if len(texte) <= n else texte[:n].rstrip() + "…"


def _reponse_attendue(branche):
    types = branche.get("type") or []
    types = [types] if isinstance(types, str) else list(types)
    questions = [f"« {q} »" for q in (branche.get("questions") or [])[:3]]
    return " / ".join(types + questions) or "?"


def _lignes_conversations():
    from module.dialogue import conversation
    conversation.charger()
    contenu = conversation._contenu
    lignes, vues, suites_vues = [], set(), set()

    def parcourir(bloc, groupe, sujet, contexte):
        for r in bloc.get("repliques") or []:
            ctx = contexte + [conversation.decrire_condition(c) for c in r.get("si") or []]
            fichier = r.get("_fichier")
            if fichier and r.get("texte") and r.get("voix") != "aucune":
                ident = relatif_mp3(fichier)
                if ident not in vues:
                    vues.add(ident)
                    lignes.append({"id": ident, "source": "conversations", "groupe": groupe,
                                   "contexte": " · ".join([sujet] + ctx), "texte": r["texte"]})
            suite = r.get("suite")
            if isinstance(suite, dict) and id(suite) not in suites_vues:
                suites_vues.add(id(suite))
                amorce = f"après « {_court(r.get('texte'))} »"
                for branche in suite.get("branches") or []:
                    parcourir(branche, groupe, sujet, [amorce, "réponse " + _reponse_attendue(branche)])
                for nom, libelle in (("autre", "toute autre réponse"), ("silence", "pas de réponse")):
                    if suite.get(nom):
                        parcourir(suite[nom], groupe, sujet, [amorce, libelle])

    for cle, s in contenu["sujets"].items():
        dossier = s.get("dossier") or "Divers"
        parcourir(s, conversation.TITRES_DOSSIERS.get(dossier, dossier), s.get("titre") or cle, [])
    for cle, i in contenu["initiatives"].items():
        parcourir(i, conversation.TITRES_DOSSIERS["Initiatives"], i.get("titre") or cle, [])
    return lignes


def _lignes_morceaux():
    from module.dialogue import morceaux
    return [{**m, "source": "morceaux"} for m in morceaux.catalogue()]


def etat_replique(ident, prises=None, synthetiques=None):
    """« studio » (ta voix), « synthese », « origine » (fait à la main avant le studio) ou « manquante »."""
    prises = lire_prises() if prises is None else prises
    synthetiques = _lire_registre_synthese() if synthetiques is None else synthetiques
    reel = sons.trouver(absolu(ident))
    if not reel:
        return "manquante"
    mp3 = reel.lower().endswith(".mp3")
    if mp3 and ident in prises:
        return "studio"
    if mp3 and ident in synthetiques:
        return "synthese"
    return "origine"


def inventaire():
    """Toutes les répliques à dire, dans l'ordre : alertes et commandes, enregistrements d'origine,
    conversations, morceaux des phrases variables. [{id, source, groupe, contexte, texte, etat, (note)}]"""
    prises, synthetiques = lire_prises(), _lire_registre_synthese()
    lignes, vues = [], set()
    for ligne in _lignes_script() + _lignes_originaux() + _lignes_conversations() + _lignes_morceaux():
        if ligne["id"] in vues:
            continue
        vues.add(ligne["id"])
        ligne["etat"] = etat_replique(ligne["id"], prises, synthetiques)
        if ligne["id"] in prises:
            ligne["date"] = prises[ligne["id"]].get("date")
        lignes.append(ligne)
    return lignes


# =====================================================================
#  OUTILS D'AFFICHAGE
# =====================================================================
def formes(x, n=500):
    """Silhouette d'un son pour l'écran : n paires [min, max]."""
    x = np.asarray(x, dtype=np.float32)
    if x.ndim == 2:
        x = x[:, 0] if x.shape[1] == 1 else x.mean(axis=1)
    if not len(x):
        return []
    bords = np.linspace(0, len(x), n + 1).astype(int)
    paires = []
    for a, b in zip(bords[:-1], bords[1:]):
        morceau = x[a:max(b, a + 1)]
        paires.append([round(float(morceau.min()), 3), round(float(morceau.max()), 3)])
    return paires


def conseils(bilan, taux):
    if bilan["parole"] <= 0:
        return ["Je n'ai rien entendu : vérifie le micro choisi en haut à droite, et son volume."]
    avis = []
    if bilan["ecretage"]:
        avis.append("Ça sature : recule un peu du micro ou baisse son volume dans Windows.")
    elif bilan["niveau_db"] < -40:
        avis.append("Voix faible : rapproche-toi du micro ou monte son volume dans Windows.")
    if bilan["bruit_db"] > -119 and bilan["niveau_db"] - bilan["bruit_db"] < 25:
        avis.append("Bruit de fond élevé : le débruitage force, la voix peut sonner un peu « aquatique ».")
    if bilan["debut"] < 0.03 * taux:
        avis.append("Tu as parlé dès le début : la première syllabe est peut-être coupée.")
    return avis


def _signature(reglages):
    cle = json.dumps([reglages["profil"], reglages["valeurs"], reglages["debruitage"],
                      reglages["egalisation"], reglages["reference_hz"]], sort_keys=True)
    return hashlib.sha1(cle.encode("utf-8")).hexdigest()[:10]


# =====================================================================
#  LE STUDIO
# =====================================================================
class Studio:
    def __init__(self):
        self._verrou = threading.RLock()
        self.reglages = lire_reglages()
        self.prise = None            # dernière prise : {ligne, brut, propre, covas, taux, bilan, hauteur}
        self.seance = []             # [(voix nettoyée, taux)] : prises de la séance, pour l'étalonnage
        self.travail = {"en_cours": False, "fait": 0, "total": 0, "message": ""}
        self._lignes = {}
        self._compteur = itertools.count()

    # --- réglages ------------------------------------------------------
    def effet(self):
        r = self.reglages
        return effet_voix.reglages(r["profil"], choisis={**r["valeurs"], "reference_hz": r["reference_hz"]})

    def egalisation(self):
        points = self.reglages["egalisation"]
        return tuple(tuple(p) for p in points) if points else _egalisation_provisoire()

    def signature(self):
        return _signature(self.reglages)

    def _enregistrer_reglages(self):
        _ecrire_json(CHEMIN_REGLAGES, self.reglages)

    def regler(self, changements):
        """Change des réglages ({cle: valeur}) ; les valeurs hors bornes sont ramenées dedans.
        Renvoie True si le son change (la dernière prise est alors refaite)."""
        bornes = {r["cle"]: r for r in REGLABLES + [DEBRUITAGE]}
        son_change = False
        with self._verrou:
            for cle, valeur in (changements or {}).items():
                if cle == "profil" and valeur in effet_voix.PROFILS:
                    self.reglages["profil"] = valeur
                    self.reglages["valeurs"] = _valeurs_profil(valeur)
                    son_change = True
                elif cle in bornes:
                    b = bornes[cle]
                    valeur = float(min(b["max"], max(b["min"], float(valeur))))
                    if cle == "debruitage":
                        self.reglages["debruitage"] = valeur
                    else:
                        self.reglages["valeurs"][cle] = valeur
                    son_change = True
                elif cle in ("verifier", "ecoute_auto"):
                    self.reglages[cle] = bool(valeur)
                elif cle == "micro":
                    self.reglages["micro"] = valeur or None
            self._enregistrer_reglages()
            if son_change and self.prise:
                self.retraiter()
        return son_change

    def reinitialiser(self, garder_etalonnage=True):
        with self._verrou:
            garde = {k: self.reglages[k] for k in ("micro", "verifier", "ecoute_auto")}
            if garder_etalonnage:
                garde.update({k: self.reglages[k] for k in ("egalisation", "reference_hz", "etalonnage")})
            self.reglages = {**copy.deepcopy(REGLAGES_DEFAUT), **garde}
            self._enregistrer_reglages()
            if self.prise:
                self.retraiter()

    # --- prises --------------------------------------------------------
    def _transformer(self, brut, taux):
        propre, bilan = effet_voix.nettoyer(brut, taux, self.reglages["debruitage"])
        if bilan["parole"] > 0:
            covas = effet_voix.robotiser(propre, taux, self.effet(), self.egalisation())
        else:
            covas = np.zeros((0, 2), dtype=np.float32)
        return propre, covas, bilan

    def traiter(self, brut, taux, ligne=None):
        """Prise du micro (mono) -> voix du COVAS. Renvoie le résumé pour l'écran."""
        brut = np.asarray(brut, dtype=np.float32)
        brut = brut.mean(axis=1) if brut.ndim == 2 else brut
        with self._verrou:
            propre, covas, bilan = self._transformer(brut, taux)
            hauteur = effet_voix.hauteur_mediane(propre, taux) if bilan["parole"] > 0 else None
            self.prise = {"ligne": ligne, "brut": brut, "propre": propre, "covas": covas, "taux": taux,
                          "bilan": bilan, "hauteur": hauteur, "numero": next(self._compteur)}
            if bilan["parole"] >= 0.3:
                self.seance.append((propre, taux))
                del self.seance[:-PRISES_SEANCE]
            return self.resume()

    def retraiter(self):
        """Refait la dernière prise avec les réglages actuels (après un changement de curseur)."""
        with self._verrou:
            p = self.prise
            if not p:
                return None
            p["propre"], p["covas"], p["bilan"] = self._transformer(p["brut"], p["taux"])
            p["numero"] = next(self._compteur)
            return self.resume()

    def resume(self):
        p = self.prise
        if not p:
            return None
        b, taux, n = p["bilan"], p["taux"], max(1, len(p["brut"]))
        return {
            "numero": p["numero"],
            "ligne": p["ligne"],
            "duree_brut": round(len(p["brut"]) / taux, 2),
            "duree_covas": round(len(p["covas"]) / taux, 2),
            "parole": round(float(b["parole"]), 2),
            "zone": [round(b["debut"] / n, 4), round(b["fin"] / n, 4)],
            "crete_db": round(float(b["crete_db"]), 1),
            "niveau_db": round(float(b["niveau_db"]), 1),
            "bruit_db": round(float(b["bruit_db"]), 1),
            "ecretage": bool(b["ecretage"]),
            "hauteur": round(p["hauteur"]) if p["hauteur"] else None,
            "hauteur_visee": self._hauteur_visee(p["hauteur"]),
            "conseils": conseils(b, taux),
            "forme_brut": formes(p["brut"]),
            "forme_covas": formes(p["covas"]),
        }

    def _hauteur_visee(self, hauteur):
        """Hauteur habituelle de la voix du COVAS pour cette prise (Hz), ou None."""
        v = self.reglages["valeurs"]
        if v.get("decalage_dt") is None:
            return round(v.get("hauteur_hz") or 0) or None
        depart = self.reglages["reference_hz"] or hauteur
        return round(depart * 2 ** (v["decalage_dt"] / 12)) if depart else None

    def ligne(self, ident):
        if not self._lignes:
            self._lignes = {l["id"]: l for l in inventaire()}
        return self._lignes.get(ident)

    def inventaire(self):
        with self._verrou:
            lignes = inventaire()
            self._lignes = {l["id"]: l for l in lignes}
            return lignes

    def _mettre_de_cote(self, chemin):
        """Un enregistrement fait à la main quitte data/son pour data/studio/remplaces (jamais effacé)."""
        racine = os.path.join(DOSSIER_BACKEND, "data", "son")
        destination = os.path.join(DOSSIER_REMPLACES, os.path.relpath(chemin, racine))
        base, extension = os.path.splitext(destination)
        n = 1
        while os.path.exists(destination):
            destination = f"{base}-{n}{extension}"
            n += 1
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.move(chemin, destination)
        return destination

    def garder(self, ident=None):
        """Range la dernière prise comme réplique `ident` (par défaut celle de la prise).
        Renvoie la ligne mise à jour."""
        with self._verrou:
            p = self.prise
            ident = relatif_mp3(ident or (p or {}).get("ligne") or "")
            if not p or not len(p["covas"]):
                raise ValueError("aucune prise à garder")
            if not ident.startswith("data/son/") or ".." in ident.split("/"):
                raise ValueError(f"réplique inconnue : {ident}")
            ligne = self.ligne(ident) or {"id": ident, "texte": ""}
            prises, synthetiques = lire_prises(), _lire_registre_synthese()
            cible = absolu(ident)
            # 1. ce qui occupe déjà la place : la synthèse et nos prises sont remplacées, un
            #    enregistrement fait à la main (ou un .wav qui passerait devant) est mis de côté
            remplace = None
            for extension in sons.EXTENSIONS:
                ancien = os.path.splitext(cible)[0] + extension
                if not os.path.isfile(ancien):
                    continue
                notre = extension == ".mp3" and (ident in prises or ident in synthetiques)
                if not notre:
                    remplace = self._mettre_de_cote(ancien)
            # 2. la réplique transformée, puis ta prise d'origine (autour de la parole)
            taux, b = p["taux"], p["bilan"]
            sons.encoder_mp3(p["covas"], taux, cible, DEBIT_COVAS)
            a = max(0, b["debut"] - int(MARGE_PRISE * taux))
            z = min(len(p["brut"]), b["fin"] + int(MARGE_PRISE * taux))
            sons.encoder_mp3(p["brut"][a:z], taux, chemin_prise(ident), DEBIT_PRISE)
            # 3. registres
            if ident in synthetiques:
                del synthetiques[ident]
                _ecrire_registre_synthese(synthetiques)
            prises[ident] = {"texte": ligne.get("texte", ""), "date": datetime.now().isoformat(timespec="seconds"),
                             "parole": round(float(b["parole"]), 2), "reglages": self.signature()}
            _ecrire_json(CHEMIN_PRISES, dict(sorted(prises.items())))
            if ligne.get("source") == "conversations":
                self._script_conversations()
            ligne = {**ligne, "etat": "studio", "date": prises[ident]["date"]}
            self._lignes[ident] = ligne
            return {**ligne, "remplace": os.path.relpath(remplace, DOSSIER_BACKEND).replace("\\", "/") if remplace else None}

    @staticmethod
    def _script_conversations():
        """SCRIPT_CONVERSATIONS.md coche ce qui est enregistré : on le tient à jour."""
        try:
            from module.dialogue import conversation
            conversation.ecrire_script()
        except Exception as erreur:            # le script n'est qu'un aide-mémoire
            _log.warning(f"Script des conversations non mis à jour : {erreur!r}")

    def compteurs(self):
        prises = lire_prises()
        signature = self.signature()
        return {"gardees": len(prises),
                "anciennes": sum(1 for p in prises.values() if p.get("reglages") != signature)}

    # --- étalonnage ----------------------------------------------------
    def _voix_gardees(self, maxi):
        """Prises gardées (les plus récentes d'abord), nettoyées : [(voix, taux)]."""
        voix, total = [], 0.0
        for ident, info in sorted(lire_prises().items(), key=lambda e: e[1].get("date", ""), reverse=True):
            if total >= maxi:
                break
            chemin = chemin_prise(ident)
            if not os.path.isfile(chemin):
                continue
            brut, taux = sons.lire(chemin)
            propre, bilan = effet_voix.nettoyer(brut.mean(axis=1), taux, self.reglages["debruitage"])
            if bilan["parole"] >= 0.3:
                voix.append((propre, taux))
                total += len(propre) / taux
        return voix

    def voix_disponible(self):
        """Secondes de ta voix utilisables pour l'étalonnage (séance + prises gardées)."""
        seance = sum(len(x) / t for x, t in self.seance)
        gardees = sum(float(p.get("parole", 0)) for p in lire_prises().values())
        return round(seance + gardees, 1)

    def etalonner(self):
        """Calcule ta hauteur habituelle et l'égalisation de ta voix. Renvoie l'étalonnage, ou
        lève ValueError s'il n'y a pas assez de voix."""
        with self._verrou:
            voix = list(reversed(self.seance))
            total = sum(len(x) / t for x, t in voix)
            if total < ETALONNAGE_MAX:
                voix += self._voix_gardees(ETALONNAGE_MAX - total)
            total = sum(len(x) / t for x, t in voix)
            if total < PAROLE_ETALONNAGE_MIN:
                raise ValueError(f"il faut au moins {PAROLE_ETALONNAGE_MIN:.0f} s de voix "
                                 f"(il y en a {total:.1f} s) : fais quelques prises d'abord")
            hauteurs = []
            for x, t in voix:
                f0 = effet_voix.suivre_hauteur(x, t)
                hauteurs.append(f0[f0 > 0])
            hauteurs = np.concatenate(hauteurs)
            reference = float(np.median(hauteurs)) if len(hauteurs) else None
            self.reglages["reference_hz"] = round(reference, 1) if reference else None
            points = effet_voix.etalonner(voix, self.effet())
            self.reglages["egalisation"] = [list(p) for p in points]
            self.reglages["etalonnage"] = {"date": datetime.now().isoformat(timespec="seconds"),
                                           "secondes": round(total, 1), "prises": len(voix),
                                           "hauteur_hz": self.reglages["reference_hz"]}
            self._enregistrer_reglages()
            if self.prise:
                self.retraiter()
            return self.reglages["etalonnage"]

    def oublier_etalonnage(self):
        with self._verrou:
            self.reglages.update(egalisation=None, reference_hz=None, etalonnage=None)
            self._enregistrer_reglages()
            if self.prise:
                self.retraiter()

    # --- tout refaire avec les réglages actuels -----------------------
    def appliquer_a_toutes(self, seulement_anciennes=False):
        """Refait chaque réplique gardée à partir de ta prise d'origine (bloquant ; à lancer
        dans un fil). L'avancement est dans self.travail."""
        with self._verrou:
            if self.travail["en_cours"]:
                return self.travail
            prises = lire_prises()
            signature = self.signature()
            a_faire = [i for i, p in prises.items()
                       if not seulement_anciennes or p.get("reglages") != signature]
            self.travail = {"en_cours": True, "fait": 0, "total": len(a_faire), "message": ""}
            effet, points, force = self.effet(), self.egalisation(), self.reglages["debruitage"]
        erreurs = []
        for ident in a_faire:
            try:
                brut, taux = sons.lire(chemin_prise(ident))
                propre, bilan = effet_voix.nettoyer(brut.mean(axis=1), taux, force)
                if bilan["parole"] <= 0:
                    raise ValueError("plus de voix dans la prise")
                covas = effet_voix.robotiser(propre, taux, effet, points)
                with self._verrou:
                    sons.encoder_mp3(covas, taux, absolu(ident), DEBIT_COVAS)
                    registre = lire_prises()
                    if ident in registre:
                        registre[ident]["reglages"] = signature
                        _ecrire_json(CHEMIN_PRISES, registre)
            except Exception as erreur:
                erreurs.append(f"{ident} : {erreur}")
            self.travail["fait"] += 1
        self.travail.update(en_cours=False, message=(f"{len(erreurs)} erreur(s) : " + " ; ".join(erreurs[:3]))
                            if erreurs else f"{len(a_faire)} répliques refaites.")
        return self.travail

    # --- vérification par Whisper -------------------------------------
    def verifier(self, texte, covas, taux):
        """(ressemblance 0 à 1 ou None, ce que Whisper entend). Bloquant : charge Whisper la
        première fois (carte graphique si possible)."""
        from module.studio import repliques
        chemin = os.path.join(tempfile.gettempdir(), f"covas_studio_{next(self._compteur) % 4}.wav")
        sons.ecrire_wav(chemin, covas, taux)
        if texte:
            return repliques.comprehension(chemin, texte)
        segments, _ = repliques._whisper().transcribe(chemin, language="fr", beam_size=5)
        return None, " ".join(s.text for s in segments).strip()
