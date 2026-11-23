"""
sol.py — Hors du vaisseau : le VRS et le pied à terre.

  - où est le commandant (vaisseau, VRS, à pied), d'après les drapeaux de Status.json ;
  - les commandes propres au VRS et au pied à terre, et la traduction des ordres vocaux
    (« phares » allume les phares du VRS en VRS, la lampe de la combinaison à pied) ;
  - où est resté le vaisseau : distance et cap pour y revenir ;
  - l'exobiologie : les trois prélèvements et la distance minimale entre eux.

Module pur : ni touches, ni fichiers, ni micro. Il se teste sans importer macros.py.
"""
import math

# Status.json, champ Flags
_VAISSEAU, _CHASSEUR, _VRS = 1 << 24, 1 << 25, 1 << 26
# Status.json, champ Flags2 (à pied, le champ Flags peut valoir 0, en station notamment)
_A_PIED = 1 << 0


def situation(flags, flags2=0):
    """'pied', 'vrs', 'chasseur', 'vaisseau', ou None (menu du jeu, chargement)."""
    flags, flags2 = flags or 0, flags2 or 0
    if flags2 & _A_PIED:
        return "pied"
    if flags & _VRS:
        return "vrs"
    if flags & _CHASSEUR:
        return "chasseur"
    if flags & _VAISSEAU:
        return "vaisseau"
    return None


# ---------- Commandes ----------
def _c(lieu, nom, **options):
    return {"lieu": lieu, "nom": nom, **options}


# bit : drapeau de Status.json qui confirme la commande (absent = le jeu ne dit rien).
# mots : débuts de mots pour (activer, couper), quand les verbes habituels ne suffisent pas.
COMMANDES = {
    "vrs_frein": _c("vrs", "Frein à main", bit=12, etats=("serré", "desserré"),
                    mots=(("serr", "mets", "tire", "activ"),
                          ("desserr", "relach", "enleve", "coup", "desactiv"))),
    "vrs_assistance": _c("vrs", "Assistance de conduite", bit=15, etats=("activée", "coupée")),
    "vrs_tourelle": _c("vrs", "Vue tourelle", bit=13, etats=("active", "quittée"),
                       bloque_par=14, raison="tourelle rentrée sous le vaisseau"),
    # Le jeu fait défiler éteints, feux de croisement, pleins phares
    "vrs_phares": _c("vrs", "Phares du VRS", bit=8, etats=("allumés", "éteints"), cycle=True),
    "vrs_soute": _c("vrs", "Écope du VRS", bit=9, etats=("ouverte", "fermée")),
    "vrs_groupe": _c("vrs", "Groupe de tir suivant"),
    "vrs_pips_sys": _c("vrs", "Énergie aux systèmes", energie=True),
    "vrs_pips_moteurs": _c("vrs", "Énergie aux moteurs", energie=True),
    "vrs_pips_armes": _c("vrs", "Énergie aux armes", energie=True),
    "vrs_pips_equilibre": _c("vrs", "Énergie équilibrée"),
    "vrs_carte_galaxie": _c("vrs", "Carte de la galaxie", carte=6),
    "vrs_carte_systeme": _c("vrs", "Carte du système", carte=7),
    "vrs_vaisseau": _c("vrs", "Rappel du vaisseau"),

    "pied_lampe": _c("pied", "Lampe de la combinaison"),
    "pied_vision": _c("pied", "Vision nocturne"),
    "pied_bouclier": _c("pied", "Bouclier de la combinaison"),
    "pied_arme": _c("pied", "Arme rangée ou sortie"),
    "pied_recharger": _c("pied", "Rechargement de l'arme"),
    "pied_grenade": _c("pied", "Grenade suivante"),
    "pied_soin": _c("pied", "Trousse de soin"),
    "pied_cellule": _c("pied", "Cellule d'énergie"),
    "pied_echantillonneur": _c("pied", "Outil de la combinaison"),
    "pied_analyseur": _c("pied", "Analyseur de profil"),
    "pied_carte_galaxie": _c("pied", "Carte de la galaxie", carte=6),
    "pied_carte_systeme": _c("pied", "Carte du système", carte=7),
}

# Ordre vocal du vaisseau -> même idée hors du vaisseau
_ROUTES = {
    "vrs": {"phares": "vrs_phares", "soute": "vrs_soute", "energie_sys": "vrs_pips_sys",
            "energie_mtr": "vrs_pips_moteurs", "energie_arm": "vrs_pips_armes",
            "reset": "vrs_pips_equilibre", "carte_galaxie": "vrs_carte_galaxie",
            "carte_systeme": "vrs_carte_systeme"},
    "pied": {"phares": "pied_lampe", "nvg": "pied_vision", "armement": "pied_arme",
             "carte_galaxie": "pied_carte_galaxie", "carte_systeme": "pied_carte_systeme"},
}
# ... seulement si la phrase contient l'un de ces débuts de mots
_ROUTES_SELON_MOTS = {
    "pied": {"energie_sys": (("bouclier",), "pied_bouclier"),
             "energie_arm": (("rang", "sor", "rentr", "cach"), "pied_arme")},
}


def traduire(cle, mots, lieu):
    """Commande à exécuter ici pour cet ordre, ou None s'il n'a pas d'équivalent."""
    if cle in COMMANDES:
        return cle if COMMANDES[cle]["lieu"] == lieu else None
    route = _ROUTES.get(lieu, {}).get(cle)
    if route:
        return route
    debuts, cible = _ROUTES_SELON_MOTS.get(lieu, {}).get(cle, ((), None))
    return cible if any(mot.startswith(debuts) for mot in mots) else None


# ---------- Géographie ----------
def distance_cap(lat1, lon1, lat2, lon2, rayon):
    """(distance en mètres, cap en degrés) du point 1 vers le point 2, sur une sphère."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    distance = 2 * rayon * math.asin(min(1.0, math.sqrt(a)))
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return distance, math.degrees(math.atan2(y, x)) % 360


# ---------- État ----------
def vierge():
    return {"vaisseau": {"etat": None, "latitude": None, "longitude": None, "corps": None,
                         "distance": None, "cap": None},
            "vrs": None, "combinaison": None, "exobio": None}


def vaisseau_pose(sol, latitude, longitude, corps):
    if latitude is None or longitude is None:
        return
    sol["vaisseau"].update(etat="pose", latitude=latitude, longitude=longitude, corps=corps,
                           distance=None, cap=None)


def vaisseau_oublie(sol, etat=None):
    """Plus de position : 'parti' = renvoyé en orbite, None = on ne sait pas où il est."""
    sol["vaisseau"].update(etat=etat, latitude=None, longitude=None, corps=None,
                           distance=None, cap=None)


def reperer_vaisseau(sol, status, corps=None):
    """Le commandant quitte le vaisseau : il est là où le jeu nous situe à cet instant."""
    vaisseau_pose(sol, status.get("latitude"), status.get("longitude"),
                  corps or status.get("corps"))


def combinaison(sol, e):
    sol["combinaison"] = {
        "nom": e.get("SuitName_Localised") or e.get("SuitName"),
        "chargement": e.get("LoadoutName"),
        "armes": [m.get("ModuleName_Localised") or m.get("ModuleName")
                  for m in e.get("Modules") or []],
    }


# ---------- Exobiologie ----------
# Distance minimale (m) entre deux prélèvements d'une même espèce, par genre.
# Source : données du module communautaire EDMC-ExploData.
PORTEES = {
    "$Codex_Ent_Aleoids_Genus_Name;": 150, "$Codex_Ent_Bacterial_Genus_Name;": 500,
    "$Codex_Ent_Cactoid_Genus_Name;": 300, "$Codex_Ent_Clypeus_Genus_Name;": 150,
    "$Codex_Ent_Conchas_Genus_Name;": 150, "$Codex_Ent_Cone_Name;": 100,
    "$Codex_Ent_Electricae_Genus_Name;": 1000, "$Codex_Ent_Fonticulus_Genus_Name;": 500,
    "$Codex_Ent_Fumerolas_Genus_Name;": 100, "$Codex_Ent_Fungoids_Genus_Name;": 300,
    "$Codex_Ent_Ground_Struct_Ice_Name;": 100, "$Codex_Ent_Osseus_Genus_Name;": 800,
    "$Codex_Ent_Recepta_Genus_Name;": 150, "$Codex_Ent_Brancae_Name;": 100,
    "$Codex_Ent_Shrubs_Genus_Name;": 150, "$Codex_Ent_Sphere_Name;": 100,
    "$Codex_Ent_Stratum_Genus_Name;": 500, "$Codex_Ent_Stratum_04_Name;": 500,
    "$Codex_Ent_Tube_Name;": 100, "$Codex_Ent_Tubus_Genus_Name;": 800,
    "$Codex_Ent_Tussocks_Genus_Name;": 200, "$Codex_Ent_Vents_Name;": 100,
    "$Codex_Ent_Ingensradices_Genus_Name;": 15,
}
ECHANTILLONS = 3


def scan_organique(sol, e, status):
    """Le journal écrit Log, Sample, Sample, puis Analyse juste après le 3e prélèvement."""
    genre_scan, espece = e.get("ScanType"), e.get("Species")
    exo = sol.get("exobio")
    if genre_scan == "Log" or not exo or exo["id"] != espece:
        exo = sol["exobio"] = {
            "id": espece, "espece": e.get("Species_Localised") or espece,
            "genre": e.get("Genus_Localised") or e.get("Genus"),
            "variante": e.get("Variant_Localised"), "portee": PORTEES.get(e.get("Genus")),
            "echantillons": 0, "termine": False, "points": [], "corps": status.get("corps"),
            "distance": None, "libre": None,
        }
    if genre_scan == "Analyse":
        exo.update(echantillons=ECHANTILLONS, termine=True, points=[], distance=None, libre=None)
        return
    exo["echantillons"] = min(ECHANTILLONS, exo["echantillons"] + 1)
    if status.get("latitude") is not None and status.get("longitude") is not None:
        exo["points"].append([status["latitude"], status["longitude"]])


def actualiser(sol, status):
    """Recalcule distances et caps avec la position actuelle. True si l'affichage change."""
    latitude, longitude = status.get("latitude"), status.get("longitude")
    rayon, corps = status.get("rayon"), status.get("corps")
    connu = latitude is not None and longitude is not None and bool(rayon)
    meme_corps = lambda autre: not corps or not autre or corps == autre

    v, exo = sol["vaisseau"], sol.get("exobio")
    avant = (v["distance"], v["cap"], exo and exo["distance"], exo and exo["libre"])

    v["distance"], v["cap"] = None, None
    if connu and v["latitude"] is not None and meme_corps(v["corps"]):
        distance, cap = distance_cap(latitude, longitude, v["latitude"], v["longitude"], rayon)
        v["distance"], v["cap"] = round(distance), round(cap) % 360

    if exo:
        exo["distance"], exo["libre"] = None, None
        if connu and exo["points"] and not exo["termine"] and meme_corps(exo["corps"]):
            exo["distance"] = round(min(distance_cap(latitude, longitude, a, b, rayon)[0]
                                        for a, b in exo["points"]))
            if exo["portee"]:
                exo["libre"] = exo["distance"] >= exo["portee"]

    return avant != (v["distance"], v["cap"], exo and exo["distance"], exo and exo["libre"])
