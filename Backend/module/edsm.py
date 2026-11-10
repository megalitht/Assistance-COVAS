"""
edsm.py — Systèmes à portée de saut, via l'API publique d'EDSM (Elite Dangerous Star Map).

Le jeu n'écrit nulle part la liste des systèmes atteignables : on la demande à EDSM
en lui envoyant le nom du système actuel et la portée de saut du vaisseau.
"""
import json
import urllib.parse
import urllib.request

URL_SPHERE = "https://www.edsm.net/api-v1/sphere-systems"
RAYON_MAX = 100          # limite imposée par EDSM (années-lumière)
CLASSES_RAVITAILLABLES = set("KGBFOAM")


def _classe_etoile(type_edsm):
    """'K (Yellow-Orange) Star' -> 'K' ; 'Neutron Star' -> 'N' ; etc."""
    if not type_edsm:
        return "?"
    texte = type_edsm.lower()
    for motif, classe in (("neutron", "N"), ("black hole", "H"), ("white dwarf", "D"),
                          ("wolf-rayet", "W"), ("t tauri", "TTS"), ("herbig", "AeBe")):
        if motif in texte:
            return classe
    return type_edsm.split(" ")[0][:3]


def systemes_dans_un_rayon(systeme, rayon_al, delai=10):
    """Renvoie [{nom, distance, classe, ravitaillable}], du plus proche au plus lointain.

    Fonction bloquante (réseau) : à appeler via asyncio.to_thread.
    """
    parametres = urllib.parse.urlencode({
        "systemName": systeme,
        "radius": round(min(rayon_al, RAYON_MAX), 2),
        "showPrimaryStar": 1,
    })
    requete = urllib.request.Request(f"{URL_SPHERE}?{parametres}",
                                     headers={"User-Agent": "Assistance-COVAS"})
    with urllib.request.urlopen(requete, timeout=delai) as reponse:
        brut = json.load(reponse)

    if not isinstance(brut, list):      # système inconnu d'EDSM : l'API renvoie {}
        return []

    resultat = []
    for entree in brut:
        if not isinstance(entree, dict) or entree.get("name") == systeme:
            continue
        etoile = entree.get("primaryStar") or {}
        classe = _classe_etoile(etoile.get("type"))
        ravitaillable = etoile.get("isScoopable")
        if ravitaillable is None:
            ravitaillable = classe in CLASSES_RAVITAILLABLES
        resultat.append({
            "nom": entree.get("name"),
            "distance": entree.get("distance"),
            "classe": classe,
            "ravitaillable": bool(ravitaillable),
        })
    resultat.sort(key=lambda s: s["distance"] if s["distance"] is not None else 1e9)
    return resultat
