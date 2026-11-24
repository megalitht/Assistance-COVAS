"""
prospection.py — Résultat des drones de prospection (événement ProspectedAsteroid) : faut-il miner
cet astéroïde ?

ProspectedAsteroid (vérifié sur les journaux du commandant) :
  Materials          [{Name, Name_Localised, Proportion}]   (« Proportion », en %)
  Content            "$AsteroidMaterialContent_High;" / Medium / Low
  MotherlodeMaterial le minerai du noyau, s'il y en a un (minage en profondeur)
  Remaining          % de matière encore là (100 : jamais miné)

Réglages : config.toml [minage] (minerais intéressants et pourcentage minimum pour chacun).
Annonces : « Astéroïde riche en » + minerai principal + pourcentage, et une annonce spéciale pour un
noyau. Un astéroïde sans intérêt n'est pas annoncé, sauf option.

Module pur : ni touches, ni micro, ni réseau. Il se teste seul (tests/test_prospection.py).
"""
from collections import deque

DERNIERS = 5
CONTENUS = {"high": "Élevé", "medium": "Moyen", "low": "Faible"}

# Noms des minerais : clé du journal (en minuscules) -> nom affiché. Les minerais qui ont un morceau
# de voix (data/son/Morceaux/Minerais/) sont dans VOIX.
NOMS = {
    "platinum": "Platine", "painite": "Painite", "osmium": "Osmium", "palladium": "Palladium",
    "gold": "Or", "silver": "Argent", "lowtemperaturediamond": "Diamants basse température",
    "tritium": "Tritium", "bromellite": "Bromellite", "opal": "Opales du vide",
    "alexandrite": "Alexandrite", "benitoite": "Bénitoïte", "grandidierite": "Grandidiérite",
    "monazite": "Monazite", "musgravite": "Musgravite", "rhodplumsite": "Rhodplumsite",
    "serendibite": "Sérendibite", "samarium": "Samarium", "praseodymium": "Praséodyme",
    "methaneclathrate": "Hydrate de méthane", "liquidoxygen": "Oxygène liquide",
    "methanolmonohydratecrystals": "Cristaux de méthanol monohydraté", "lithiumhydroxide": "Hydroxyde de lithium",
    "hydrogenperoxide": "Peroxyde d'hydrogène", "water": "Eau", "haematite": "Hématite",
    "bauxite": "Bauxite", "indite": "Indite", "gallite": "Gallite", "uraninite": "Uraninite",
    "rutile": "Rutile", "coltan": "Coltan", "cobalt": "Cobalt", "lepidolite": "Lépidolite",
    "bertrandite": "Bertrandite", "jadeite": "Jadéite", "moissanite": "Moissanite", "pyrophyllite": "Pyrophyllite",
    "taaffeite": "Taaffeite", "cryolite": "Cryolite", "goslarite": "Goslarite", "lanthanum": "Lanthane",
    "thorium": "Thorium", "beryllium": "Béryllium", "tellurium": "Tellure", "bismuth": "Bismuth",
    "hafnium178": "Hafnium 178", "rhodium": "Rhodium",
}
# Minerais dont le nom est enregistré (liste courte : les plus utiles en minage)
VOIX = ("platinum", "painite", "osmium", "palladium", "gold", "silver", "lowtemperaturediamond",
        "tritium", "bromellite", "opal", "alexandrite", "benitoite", "grandidierite", "monazite",
        "musgravite", "rhodplumsite", "serendibite")


def cle(nom):
    return (nom or "").strip("$;").replace("_name", "").replace(" ", "").lower()


def nom_minerai(nom_journal, localise=None):
    """Nom affiché : la table, sinon le nom traduit du jeu, sinon le nom brut."""
    return NOMS.get(cle(nom_journal)) or localise or nom_journal or "?"


def contenu(e):
    brut = (e.get("Content") or "").lower()
    for mot, texte in CONTENUS.items():
        if mot in brut:
            return mot, texte
    return None, e.get("Content_Localised") or "?"


class Prospection:
    def __init__(self):
        self.derniers = deque(maxlen=DERNIERS)
        self.prospectes = 0
        self.interessants = 0

    def analyser(self, e, reglages):
        """Un astéroïde prospecté. Renvoie (fiche, annonce ou None).
        annonce : {"noyau": cle ou None, "minerai": cle ou None, "pourcentage": %, "sans_interet": bool}"""
        seuils = {cle(k): v for k, v in (reglages.get("minerais") or {}).items()
                  if isinstance(v, (int, float)) and not isinstance(v, bool)}
        materiaux = []
        for m in e.get("Materials") or []:
            k = cle(m.get("Name"))
            pourcentage = float(m.get("Proportion") or 0)
            materiaux.append({"cle": k, "nom": nom_minerai(m.get("Name"), m.get("Name_Localised")),
                              "pourcentage": round(pourcentage, 1),
                              "interessant": k in seuils and pourcentage >= seuils[k]})
        materiaux.sort(key=lambda m: -m["pourcentage"])
        niveau, texte = contenu(e)
        noyau = e.get("MotherlodeMaterial")
        restant = e.get("Remaining")
        interessant = any(m["interessant"] for m in materiaux) or bool(noyau)
        fiche = {"h": e.get("timestamp"), "contenu": texte, "niveau": niveau,
                 "noyau": nom_minerai(noyau, e.get("MotherlodeMaterial_Localised")) if noyau else None,
                 "restant": restant, "materiaux": materiaux, "interessant": interessant}
        self.derniers.appendleft(fiche)
        self.prospectes += 1
        self.interessants += interessant
        return fiche, self._annonce(fiche, materiaux, noyau, restant, reglages)

    @staticmethod
    def _annonce(fiche, materiaux, noyau, restant, reglages):
        deja_mine = isinstance(restant, (int, float)) and restant < 100
        if deja_mine and reglages.get("ignorer_deja_mines", True):
            return None
        premier = next((m for m in materiaux if m["interessant"]), None)
        noyau_dit = cle(noyau) if noyau and reglages.get("annoncer_noyau", True) else None
        if premier or noyau_dit:
            return {"noyau": noyau_dit, "minerai": premier["cle"] if premier else None,
                    "pourcentage": premier["pourcentage"] if premier else None, "sans_interet": False}
        if reglages.get("annoncer_sans_interet"):
            return {"noyau": None, "minerai": None, "pourcentage": None, "sans_interet": True}
        return None

    def vue(self):
        return {"derniers": list(self.derniers), "prospectes": self.prospectes,
                "interessants": self.interessants}
