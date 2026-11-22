"""
morceaux.py — Phrases qui changent à chaque fois, dites avec des morceaux enregistrés.

Le rapport d'avarie, l'heure, la date et la position ne peuvent pas tenir dans une seule prise.
Le studio vocal (module/studio.py) propose donc ces morceaux à enregistrer : « Coque à »,
« quarante », « pour cent »... Le COVAS les met bout à bout au moment de parler.

    catalogue()             tous les morceaux à enregistrer
    pour_rapport(rapport)   morceaux d'un rapport d'avarie (module/avaries.py)
    recette(nom, instant)   morceaux d'une réplique « morceaux » de data/conversations.json
    assembler(ids)          fichier .wav prêt à jouer, ou None s'il manque un seul morceau :
                            jamais de phrase à trous, le texte reste à l'écran

Les noms de systèmes, de stations et de planètes sont trop nombreux pour être enregistrés :
la voix dit où en est le vaisseau, le nom exact est à l'écran.
"""
import os
import re
import tempfile
import unicodedata
from functools import lru_cache
from itertools import count

import numpy as np

from module import avaries, sons

DOSSIER_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER = "data/son/Morceaux"

TAUX = 48000
PAUSE = None                # dans une liste de morceaux : fin de phrase
ECART = 0.035               # secondes entre deux morceaux d'une même phrase
ECART_PHRASE = 0.17         # secondes entre deux phrases
TRAINE = 0.12               # résonance gardée après la parole (elle passe sous le morceau suivant)
SEUIL_PAROLE_DB = -32       # sous le maximum du morceau : ce n'est plus de la parole
GAIN_MAX = 2.0              # correction de volume entre deux prises, dans un sens ou dans l'autre
MODULES_CITES = 3           # le rapport doit rester court : il peut passer en plein combat

MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre",
        "octobre", "novembre", "décembre")
_UNITES = ("zéro", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix",
           "onze", "douze", "treize", "quatorze", "quinze", "seize")
_DIZAINES = {2: "vingt", 3: "trente", 4: "quarante", 5: "cinquante", 6: "soixante"}
_FEMININS = (1, 21, 31, 41, 51)     # « quatorze heures vingt et une »

_FIXES = {
    "Rapport": [
        ("CoqueIntacte", "Coque intacte."), ("CoqueA", "Coque à"), ("CoqueSous", "Coque sous"),
        ("PourCent", "pour cent"), ("VerriereBrisee", "Verrière brisée."),
        ("BoucliersEnLigne", "Boucliers en ligne."), ("BoucliersHorsLigne", "Boucliers hors ligne."),
        ("EquipementInconnu", "Équipement inconnu."), ("AucuneAvarie", "Aucune avarie."),
        ("UneAvarie", "Une avarie :"), ("Avaries", "avaries :"),
        ("PlusieursAvaries", "Plusieurs avaries :"), ("HorsService", "hors service"),
        ("EtDautres", "Et d'autres encore."), ("ModuleInconnu", "Module non identifié"),
        ("Perime", "Relevé antérieur aux derniers dégâts."),
        ("AucuneDonnee", "Aucune donnée sur le vaisseau pour l'instant."),
    ],
    "Heure": [
        ("IlEst", "Il est"), ("Midi", "midi"), ("Minuit", "minuit"), ("Commandant", "commandant."),
        ("Dormir", "Il serait peut-être temps de dormir."),
    ],
    "Date": [
        ("NousSommesLe", "Nous sommes le"), ("Premier", "premier"),
        ("Annee3300", "trois mille trois cent"), ("Calendrier", "Calendrier galactique."),
    ],
    "Position": [
        ("Ecran", "Votre position est à l'écran, commandant."),
        ("Supercroisiere", "Nous sommes en supercroisière, commandant."),
        ("Poses", "Nous sommes posés, commandant."),
        ("Amarres", "Nous sommes amarrés, commandant."),
    ],
}
_GROUPES = {"Rapport": "Rapport d'avarie", "Modules": "Noms des modules", "Nombres": "Nombres",
            "Heure": "Heure", "Date": "Date", "Position": "Position"}


def nombre(n, feminin=False):
    """0 à 100 en toutes lettres."""
    if n == 100:
        return "cent"
    if n <= 16:
        return "une" if feminin and n == 1 else _UNITES[n]
    if n < 20:
        return "dix-" + _UNITES[n - 10]
    dizaine, unite = divmod(n, 10)
    if dizaine == 7:
        return "soixante et onze" if n == 71 else "soixante-" + nombre(n - 60)
    if dizaine == 9:
        return "quatre-vingt-" + nombre(n - 80)
    if dizaine == 8:
        return "quatre-vingts" if not unite else "quatre-vingt-" + nombre(unite, feminin)
    if not unite:
        return _DIZAINES[dizaine]
    if unite == 1:
        return f"{_DIZAINES[dizaine]} et {'une' if feminin else 'un'}"
    return f"{_DIZAINES[dizaine]}-{_UNITES[unite]}"


def _ident(dossier, nom):
    return f"{DOSSIER}/{dossier}/{nom}.mp3"


def _nom_fichier(texte):
    sans_accent = unicodedata.normalize("NFKD", texte)
    sans_accent = "".join(c for c in sans_accent if not unicodedata.combining(c))
    return "".join(m.capitalize() for m in re.findall(r"[A-Za-z0-9]+", sans_accent))


def _id_nombre(n):
    return _ident("Nombres", f"{n:03d}")


def _id_feminin(n):
    return _ident("Nombres", f"F{n:02d}")


def _id_heure(h):
    return _ident("Heure", f"H{h:02d}")


def _id_module(nom):
    return _ident("Modules", _nom_fichier(nom))


def _texte_heure(h):
    return f"{nombre(h, feminin=True)} heure{'s' if h > 1 else ''}"


def catalogue():
    """[{id, groupe, contexte, texte}] : tout ce qu'il faut enregistrer, sans doublon."""
    lignes = []

    def ajouter(dossier, ident, texte, contexte):
        lignes.append({"id": ident, "groupe": _GROUPES[dossier], "contexte": contexte, "texte": texte})

    for dossier in ("Rapport",):
        for nom, texte in _FIXES[dossier]:
            ajouter(dossier, _ident(dossier, nom), texte, "morceau du rapport")
    for nom in sorted(set(avaries.NOMS_MODULES.values())):
        ajouter("Modules", _id_module(nom), nom, "nom cité dans le rapport")
    for n in range(101):
        ajouter("Nombres", _id_nombre(n), nombre(n), "pourcentages, minutes, jours, années")
    for n in _FEMININS:
        ajouter("Nombres", _id_feminin(n), nombre(n, feminin=True), "minutes (« quatorze heures vingt et une »)")
    for h in range(24):
        ajouter("Heure", _id_heure(h), _texte_heure(h), "heure")
    for nom, texte in _FIXES["Heure"]:
        ajouter("Heure", _ident("Heure", nom), texte, "morceau de l'heure et de la date")
    for nom, texte in _FIXES["Date"]:
        ajouter("Date", _ident("Date", nom), texte, "morceau de la date")
    for i, mois in enumerate(MOIS, 1):
        ajouter("Date", _ident("Date", f"Mois{i:02d}"), mois, "mois")
    for nom, texte in _FIXES["Position"]:
        ajouter("Position", _ident("Position", nom), texte, "le nom exact reste à l'écran")
    return lignes


# =====================================================================
#  COMPOSER LES PHRASES
# =====================================================================
def _heure(instant, nuit=False):
    fin = [_ident("Heure", "Commandant")]
    if nuit:
        fin += [PAUSE, _ident("Heure", "Dormir")]
    debut = [_ident("Heure", "IlEst")]
    if not instant.minute and instant.hour in (0, 12):
        return debut + [_ident("Heure", "Minuit" if instant.hour == 0 else "Midi")] + fin
    minutes = []
    if instant.minute:
        minutes = [_id_feminin(instant.minute) if instant.minute in _FEMININS else _id_nombre(instant.minute)]
    return debut + [_id_heure(instant.hour)] + minutes + fin


def _date(instant):
    annee = instant.year + 1286
    jour = _ident("Date", "Premier") if instant.day == 1 else _id_nombre(instant.day)
    morceaux = [_ident("Date", "NousSommesLe"), jour, _ident("Date", f"Mois{instant.month:02d}")]
    if 3300 <= annee < 3400:
        morceaux.append(_ident("Date", "Annee3300"))
        if annee > 3300:
            morceaux.append(_id_nombre(annee - 3300))
    return morceaux + [_ident("Heure", "Commandant"), PAUSE, _ident("Date", "Calendrier")]


RECETTES = {
    "heure": lambda instant: _heure(instant),
    "heure_nuit": lambda instant: _heure(instant, nuit=True),
    "date": _date,
    "position": lambda instant: [_ident("Position", "Ecran")],
    "position_supercroisiere": lambda instant: [_ident("Position", "Supercroisiere")],
    "position_pose": lambda instant: [_ident("Position", "Poses")],
    "position_amarre": lambda instant: [_ident("Position", "Amarres")],
}


def recette(nom, instant):
    return RECETTES[nom](instant)


def pour_rapport(rapport):
    """Morceaux d'un rapport d'avarie, dans l'ordre où ils sont dits."""
    r = lambda nom: _ident("Rapport", nom)
    coque = rapport.get("coque")
    if coque is None and not rapport.get("modules_connus"):
        return [r("AucuneDonnee")]

    morceaux = []
    if coque is not None:
        if coque >= 0.995:
            morceaux += [r("CoqueIntacte"), PAUSE]
        elif rapport.get("coque_seuil") is not None:
            morceaux += [r("CoqueSous"), _id_nombre(rapport["coque_seuil"]), r("PourCent"), PAUSE]
        else:
            morceaux += [r("CoqueA"), _id_nombre(round(coque * 100)), r("PourCent"), PAUSE]
    if rapport.get("verriere_brisee"):
        morceaux += [r("VerriereBrisee"), PAUSE]
    if rapport.get("boucliers") is not None:
        morceaux += [r("BoucliersEnLigne" if rapport["boucliers"] else "BoucliersHorsLigne"), PAUSE]

    liste = rapport.get("avaries") or []
    if not rapport.get("modules_connus"):
        morceaux += [r("EquipementInconnu"), PAUSE]
    elif not liste:
        morceaux += [r("AucuneAvarie"), PAUSE]
    else:
        if len(liste) == 1:
            morceaux.append(r("UneAvarie"))
        elif len(liste) <= 20:
            morceaux += [_id_nombre(len(liste)), r("Avaries")]
        else:
            morceaux.append(r("PlusieursAvaries"))
        connus = set(avaries.NOMS_MODULES.values())
        for a in liste[:MODULES_CITES]:
            morceaux.append(_id_module(a["court"]) if a["court"] in connus else r("ModuleInconnu"))
            morceaux += [r("HorsService")] if a["hs"] else [_id_nombre(round(a["sante"] * 100)), r("PourCent")]
            morceaux.append(PAUSE)
        if len(liste) > MODULES_CITES:
            morceaux += [r("EtDautres"), PAUSE]
    if rapport.get("perime"):
        morceaux += [r("Perime"), PAUSE]
    while morceaux and morceaux[-1] is PAUSE:
        morceaux.pop()
    return morceaux


# =====================================================================
#  ASSEMBLER LE SON
# =====================================================================
_numero = count()


@lru_cache(maxsize=256)
def _charger(chemin, _date_fichier):
    """(stéréo 48 kHz, début de la parole, fin de la parole, niveau de la parole)."""
    x, taux = sons.lire(chemin)
    if x.ndim == 1:
        x = x[:, None]
    if x.shape[1] == 1:
        x = np.repeat(x, 2, axis=1)
    x = x[:, :2]
    if taux != TAUX and len(x):
        n = int(round(len(x) * TAUX / taux))
        anciens, nouveaux = np.arange(len(x)), np.linspace(0, len(x) - 1, n)
        x = np.column_stack([np.interp(nouveaux, anciens, x[:, c]) for c in range(2)]).astype(np.float32)
    pas = int(0.01 * TAUX)
    n = len(x) // pas
    if not n:
        raise ValueError(f"morceau vide : {chemin}")
    trames = x[:n * pas].mean(axis=1).reshape(n, pas)
    niveaux = np.sqrt(np.mean(trames ** 2, axis=1))
    parle = np.flatnonzero(niveaux >= niveaux.max() * 10 ** (SEUIL_PAROLE_DB / 20))
    debut, fin = int(parle[0]) * pas, (int(parle[-1]) + 1) * pas
    return x, debut, fin, float(np.sqrt(np.mean(x[debut:fin] ** 2)))


def _chemin_morceau(ident):
    return sons.trouver(os.path.join(DOSSIER_BACKEND, *ident.split("/")))


def manquants(ids):
    return [i for i in ids if i is not PAUSE and not _chemin_morceau(i)]


def assembler(ids):
    """Met les morceaux bout à bout. Renvoie le chemin d'un .wav, ou None si la phrase est incomplète."""
    if not ids or manquants(ids):
        return None
    try:
        pieces, ecart = [], ECART
        for ident in ids:
            if ident is PAUSE:
                ecart = ECART_PHRASE
                continue
            chemin = _chemin_morceau(ident)
            pieces.append((*_charger(chemin, os.path.getmtime(chemin)), ecart))
            ecart = ECART
        cible = float(np.median([p[3] for p in pieces]))
        avant, traine, fondu = int(0.015 * TAUX), int(TRAINE * TAUX), int(0.005 * TAUX)
        taille = sum(p[2] - p[1] + avant + int(p[4] * TAUX) for p in pieces) + traine
        sortie = np.zeros((taille, 2), dtype=np.float32)
        position = 0
        for i, (x, debut, fin, niveau, avant_piece) in enumerate(pieces):
            if i:
                position += int(avant_piece * TAUX)
            a, z = max(0, debut - avant), min(len(x), fin + traine)
            morceau = x[a:z] * float(np.clip(cible / max(niveau, 1e-6), 1 / GAIN_MAX, GAIN_MAX))
            n = min(fondu, len(morceau))
            morceau[:n] *= np.linspace(0, 1, n)[:, None]
            n = min(int(0.04 * TAUX), len(morceau))
            morceau[-n:] *= np.linspace(1, 0, n)[:, None]
            sortie[position:position + len(morceau)] += morceau[:max(0, taille - position)]
            position += fin - a
        sortie = sortie[:min(taille, position + traine)]
        crete = float(np.abs(sortie).max())
        if crete > 0.98:
            sortie *= 0.98 / crete
        # plusieurs noms : le fichier précédent peut encore être en lecture
        chemin = os.path.join(tempfile.gettempdir(), f"covas_morceaux_{next(_numero) % 6}.wav")
        return sons.ecrire_wav(chemin, sortie, TAUX)
    except Exception as erreur:
        print(f"[Morceaux] Assemblage impossible : {erreur!r}")
        return None
