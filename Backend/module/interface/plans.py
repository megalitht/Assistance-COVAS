"""
plans.py — Installe un plan d'hologramme sorti de l'atelier (Frontend/vaisseaux/<id>.js).

Ce fichier sera exécuté par l'interface : seul le format exact produit par l'atelier est accepté
(un commentaire, puis un unique appel avec des données JSON). L'ancien plan n'est jamais perdu :
il est copié dans vaisseaux/anciens/ sous un nom daté.
"""
import json
import os
import re
import shutil
import time

TAILLE_MAX = 1_000_000
_ID = re.compile(r"^[a-z0-9_]{1,40}$")
_FICHIER = re.compile(r"\A/\*(?:(?!\*/).)*\*/\n"
                      r"window\.COVAS_HOLOGRAMMES && window\.COVAS_HOLOGRAMMES\.enregistrer\("
                      r"(\{.*\})\);\n\Z", re.S)


def verifier(identifiant, contenu):
    """Lève ValueError si ce n'est pas un plan valide pour ce vaisseau."""
    if not isinstance(identifiant, str) or not _ID.match(identifiant):
        raise ValueError("identifiant de vaisseau invalide")
    if not isinstance(contenu, str) or len(contenu) > TAILLE_MAX:
        raise ValueError("fichier de plan invalide")
    forme = _FICHIER.match(contenu)
    if not forme:
        raise ValueError("ce fichier n'a pas le format d'un plan de l'atelier")
    try:
        plan = json.loads(forme.group(1))
    except ValueError:
        raise ValueError("données du plan illisibles") from None
    largeur = plan.get("largeur")
    if plan.get("id") != identifiant or plan.get("longueur") != 1000 \
            or not isinstance(largeur, (int, float)) or isinstance(largeur, bool) or largeur <= 0 \
            or not isinstance(plan.get("coque"), str) or not plan["coque"].startswith("M") \
            or not isinstance(plan.get("traits", ""), str) \
            or not isinstance(plan.get("details", ""), str):
        raise ValueError("données du plan incomplètes")


def _nom_sauvegarde(anciens, identifiant):
    base = f"{identifiant}-{time.strftime('%Y%m%d-%H%M%S')}"
    nom, n = f"{base}.js", 2
    while os.path.exists(os.path.join(anciens, nom)):
        nom, n = f"{base}-{n}.js", n + 1
    return nom


def installer(dossier, identifiant, contenu):
    """Écrit le plan. Renvoie {"ok": True, "sauvegarde": chemin de l'ancien plan ou None}."""
    verifier(identifiant, contenu)
    cible = os.path.join(dossier, f"{identifiant}.js")
    sauvegarde = None
    if os.path.exists(cible):
        anciens = os.path.join(dossier, "anciens")
        os.makedirs(anciens, exist_ok=True)
        nom = _nom_sauvegarde(anciens, identifiant)
        shutil.copy2(cible, os.path.join(anciens, nom))
        sauvegarde = f"vaisseaux/anciens/{nom}"
    temporaire = cible + ".tmp"
    with open(temporaire, "w", encoding="utf-8", newline="\n") as f:
        f.write(contenu)
    os.replace(temporaire, cible)
    return {"ok": True, "sauvegarde": sauvegarde}
