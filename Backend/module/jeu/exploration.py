"""
exploration.py — Ce que vaut un corps céleste, et la vie qu'on peut y trouver.

  - valeur d'un corps : formule de la communauté (MattG, forum Frontier), selon qu'il a déjà
    été découvert ou cartographié ;
  - exobiologie : espèces possibles d'après la planète (data/exobiologie.json), prix exacts,
    bonus ×5 du premier pas ;
  - le Carnet : les corps du système actuel et ce qui reste à vendre depuis le début de la session.

Module pur : ni touches, ni micro. Il se teste sans importer macros.py.
"""
import json
import os

DOSSIER_BACKEND = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHEMIN_EXOBIO = os.path.join(DOSSIER_BACKEND, "data", "exobiologie.json")

GRAVITE = 9.797759              # m/s² pour 1 g, valeur utilisée par les règles d'apparition
ATMOSPHERE = 101231.65625       # Pa pour 1 atm, idem
BONUS_PREMIER_PAS = 5           # valeur totale d'une espèce avec le bonus de première découverte

CLASSES = {
    "Metal rich body": "Riche en métaux", "High metal content body": "Haute teneur en métaux",
    "Rocky body": "Rocheux", "Icy body": "Glacé", "Rocky ice body": "Roche et glace",
    "Earthlike body": "Monde terrestre", "Water world": "Monde d'eau",
    "Ammonia world": "Monde d'ammoniac", "Water giant": "Géante d'eau",
    "Gas giant with water based life": "Géante à vie aquatique",
    "Gas giant with ammonia based life": "Géante à vie ammoniacale",
    "Sudarsky class I gas giant": "Géante gazeuse I", "Sudarsky class II gas giant": "Géante gazeuse II",
    "Sudarsky class III gas giant": "Géante gazeuse III", "Sudarsky class IV gas giant": "Géante gazeuse IV",
    "Sudarsky class V gas giant": "Géante gazeuse V", "Helium rich gas giant": "Géante riche en hélium",
    "Helium gas giant": "Géante d'hélium",
}


# =====================================================================
#  VALEUR D'UN CORPS
# =====================================================================
def _k_planete(classe, terraformable):
    if classe == "Metal rich body":
        return 21790
    if classe == "Ammonia world":
        return 96932
    if classe == "Sudarsky class I gas giant":
        return 1656
    if classe == "Sudarsky class II gas giant":
        return 9654
    if classe == "High metal content body":
        return 9654 + (100677 if terraformable else 0)
    if classe == "Water world":
        return 64831 + (116295 if terraformable else 0)
    if classe == "Earthlike body":
        return 64831 + 116295
    return 300 + (93328 if terraformable else 0)


def valeur_planete(classe, terraformable, masse, premier, carto=False, premier_carto=False,
                   efficace=True):
    """Crédits à la vente. premier : première découverte. carto : cartographiée."""
    k = _k_planete(classe, terraformable)
    valeur = k + k * 0.56591828 * (masse or 0) ** 0.2
    if carto:
        if premier and premier_carto:
            valeur *= 3.699622554
        elif premier_carto:
            valeur *= 8.0956
        else:
            valeur *= 10 / 3
        valeur += max(valeur * 0.3, 555)
        if efficace:
            valeur *= 1.25
    valeur = max(500, valeur)
    return round(valeur * (2.6 if premier else 1))


def valeur_etoile(type_etoile, masse, premier):
    type_etoile = type_etoile or ""
    k = 22628 if type_etoile in ("N", "H", "SuperMassiveBlackHole") else (
        14057 if type_etoile.startswith("D") else 1200)
    return round((k + (masse or 0) * k / 66.25) * (2.6 if premier else 1))


# =====================================================================
#  EXOBIOLOGIE
# =====================================================================
_catalogue = {}


def catalogue():
    if not _catalogue:
        with open(CHEMIN_EXOBIO, encoding="utf-8") as f:
            _catalogue.update(json.load(f)["genres"])
    return _catalogue


def _especes_par_id():
    return {i: e for g in catalogue().values() for i, e in g["especes"].items()}


def _gaz(scan, nom):
    for gaz in scan.get("AtmosphereComposition") or []:
        if gaz.get("Name") == nom:
            return gaz.get("Percent") or 0
    return 0


def _volcanisme_ok(regle, volcanisme):
    if isinstance(regle, list):
        return any(volcanisme == v[1:] if v.startswith("=") else v in volcanisme for v in regle)
    if regle == "Any":
        return bool(volcanisme)
    if regle == "None":
        return not volcanisme
    if regle.startswith("!"):
        return bool(volcanisme) and regle[1:] not in volcanisme
    return True


def regle_ok(regle, scan):
    """La planète remplit-elle ces conditions ? Ce que le Scan ne dit pas n'élimine personne."""
    atmosphere = scan.get("AtmosphereType") or "None"
    gravite = (scan.get("SurfaceGravity") or 0) / GRAVITE
    temperature = scan.get("SurfaceTemperature") or 0
    pression = (scan.get("SurfacePressure") or 0) / ATMOSPHERE
    for cle, valeur in regle.items():
        if cle == "body_type" and scan.get("PlanetClass") not in valeur:
            return False
        if cle == "atmosphere":
            if valeur == "Any":
                if atmosphere in ("", "None"):
                    return False
            elif atmosphere not in valeur:
                return False
        if cle == "atmosphere_component" and any(_gaz(scan, g) < p for g, p in valeur.items()):
            return False
        if cle == "min_gravity" and gravite < valeur:
            return False
        if cle == "max_gravity" and gravite > valeur:
            return False
        if cle == "min_temperature" and temperature and temperature < valeur:
            return False
        if cle == "max_temperature" and temperature and temperature > valeur:
            return False
        if cle == "min_pressure" and pression and pression < valeur:
            return False
        if cle == "max_pressure" and pression and pression >= valeur:
            return False
        if cle == "max_orbital_period" and (scan.get("OrbitalPeriod") or 0) >= valeur:
            return False
        if cle == "volcanism" and not _volcanisme_ok(valeur, scan.get("Volcanism") or ""):
            return False
    return True


def especes_possibles(genre, scan):
    """[(id, nom, valeur)] des espèces de ce genre compatibles avec la planète."""
    bloc = catalogue().get(genre)
    if not bloc:
        return []
    return [(i, e["nom"], e["valeur"]) for i, e in bloc["especes"].items()
            if any(regle_ok(r, scan) for r in e["regles"])]


def _genres_possibles(scan):
    return {g: p for g in catalogue() if (p := especes_possibles(g, scan))}


def _estimer_bio(corps):
    """Fourchette de valeur de la vie sur ce corps (sans puis avec le bonus du premier pas)."""
    scan = corps.get("scan") or {}
    signaux, confirmees = corps["signaux"], corps["confirmees"]
    if not signaux and not corps["genres"] and not confirmees:
        return None

    bonus = bool(scan) and scan.get("WasFootfalled") is False
    lignes, mini, maxi = [], 0, 0
    deja = set()
    for ident, c in confirmees.items():
        deja.add(c["genre"])
        lignes.append({"genre": c["genre_nom"], "espece": c["nom"], "min": c["valeur"], "max": c["valeur"],
                       "etat": c["etat"], "possibles": 1})
        mini += c["valeur"]
        maxi += c["valeur"]

    for genre, nom in corps["genres"].items():
        if genre in deja:
            continue
        possibles = especes_possibles(genre, scan) if scan else []
        if not possibles:
            possibles = [(i, e["nom"], e["valeur"]) for i, e in
                         (catalogue().get(genre) or {"especes": {}})["especes"].items()]
        if not possibles:
            lignes.append({"genre": nom, "espece": None, "min": 0, "max": 0, "etat": "detecte", "possibles": 0})
            continue
        valeurs = [p[2] for p in possibles]
        lignes.append({"genre": nom, "espece": possibles[0][1] if len(possibles) == 1 else None,
                       "min": min(valeurs), "max": max(valeurs), "etat": "detecte",
                       "possibles": len(possibles)})
        mini += min(valeurs)
        maxi += max(valeurs)

    restants = max(0, signaux - len(deja) - len([g for g in corps["genres"] if g not in deja]))
    approx = restants > 0
    if restants and scan:           # genres pas encore connus (scan FSS sans cartographie)
        candidats = [p for g, p in _genres_possibles(scan).items()
                     if g not in deja and g not in corps["genres"]]
        hauts = sorted((max(v[2] for v in p) for p in candidats), reverse=True)
        bas = sorted(min(v[2] for v in p) for p in candidats)
        maxi += sum(hauts[:restants])
        mini += sum(bas[:restants])

    lignes.sort(key=lambda l: -l["max"])
    facteur = BONUS_PREMIER_PAS if bonus else 1
    return {"signaux": max(signaux, len(lignes)), "lignes": lignes, "min": mini, "max": maxi,
            "min_bonus": mini * facteur, "max_bonus": maxi * facteur, "bonus": bonus, "approx": approx,
            "analysees": sum(1 for c in confirmees.values() if c["etat"] == "analyse")}


# =====================================================================
#  CARNET D'EXPLORATION
# =====================================================================
def _nom_court(nom, systeme):
    if nom and systeme and nom.startswith(systeme + " "):
        return nom[len(systeme) + 1:]
    return nom


class Carnet:
    def __init__(self):
        self.nouvelle_session()

    def nouvelle_session(self):
        self.adresse, self.systeme = None, None
        self.corps = {}             # BodyID -> données du système actuel
        self.dernier = None
        self.a_vendre = {}          # nom du système -> {BodyID: valeur}
        self.exo = {}               # (système, corps, espèce) -> valeur
        self.vendu, self.exo_vendu = 0, 0

    def assurer_systeme(self, adresse, nom=None):
        if adresse is not None and adresse != self.adresse:
            self.adresse, self.systeme = adresse, nom
            self.corps, self.dernier = {}, None
        elif nom:
            self.systeme = nom

    def _corps(self, ident, nom=None):
        c = self.corps.setdefault(ident, {"id": ident, "nom": nom, "scan": None, "signaux": 0, "genres": {},
                                          "confirmees": {}, "carto": False, "efficace": True})
        if nom:
            c["nom"] = nom
        return c

    # ---------- Événements du journal ----------
    def scan(self, e):
        """Scan d'un corps. Renvoie sa fiche si c'est une planète ou une étoile, et True
        si le corps n'avait encore jamais été vu dans cette visite."""
        if not (e.get("PlanetClass") or e.get("StarType")) or e.get("BodyID") is None:
            return None, False
        self.assurer_systeme(e.get("SystemAddress"), e.get("StarSystem"))
        c = self._corps(e["BodyID"], e.get("BodyName"))
        neuf = c["scan"] is None
        balise = e.get("ScanType") == "NavBeaconDetail"
        if neuf or not balise:      # une balise n'écrase pas un vrai scan
            c["scan"] = e
        self.dernier = c["id"]
        self._retenir(c)
        return self.fiche(c), neuf

    def signaux_fss(self, e):
        self.assurer_systeme(e.get("SystemAddress"))
        c = self._corps(e.get("BodyID"), e.get("BodyName"))
        c["signaux"] = max(c["signaux"], self._nb_bio(e))
        self.dernier = c["id"]
        return self.fiche(c)

    def signaux_saa(self, e):
        """Cartographie : le jeu donne enfin les genres présents."""
        self.assurer_systeme(e.get("SystemAddress"))
        c = self._corps(e.get("BodyID"), e.get("BodyName"))
        c["signaux"] = max(c["signaux"], self._nb_bio(e))
        for g in e.get("Genuses") or []:
            c["genres"][g.get("Genus")] = g.get("Genus_Localised") or g.get("Genus")
        return self.fiche(c)

    @staticmethod
    def _nb_bio(e):
        return sum(s.get("Count") or 0 for s in e.get("Signals") or []
                   if "Biological" in (s.get("Type") or ""))

    def cartographie(self, e):
        self.assurer_systeme(e.get("SystemAddress"))
        c = self._corps(e.get("BodyID"), e.get("BodyName"))
        c["carto"] = True
        c["efficace"] = (e.get("ProbesUsed") or 0) <= (e.get("EfficiencyTarget") or 0)
        self.dernier = c["id"]
        self._retenir(c)
        return self.fiche(c)

    def organique(self, e):
        """ScanOrganic : l'espèce devient certaine. Renvoie (valeur, bonus) à l'analyse."""
        adresse, ident = e.get("SystemAddress"), e.get("Body")
        self.assurer_systeme(adresse)
        c = self._corps(ident)
        espece = e.get("Species")
        fiche = _especes_par_id().get(espece) or {}
        valeur = fiche.get("valeur") or 0
        ligne = c["confirmees"].setdefault(espece, {
            "nom": e.get("Species_Localised") or fiche.get("nom") or espece,
            "genre": e.get("Genus"), "genre_nom": e.get("Genus_Localised") or e.get("Genus"),
            "valeur": valeur, "etat": "prelevement"})
        c["genres"].setdefault(e.get("Genus"), e.get("Genus_Localised") or e.get("Genus"))
        self.dernier = c["id"]
        if e.get("ScanType") != "Analyse":
            return None
        ligne["etat"] = "analyse"
        scan = c.get("scan") or {}
        bonus = scan.get("WasFootfalled") is False and not e.get("WasLogged")
        total = valeur * (BONUS_PREMIER_PAS if bonus else 1)
        self.exo[(adresse, ident, espece)] = total
        return total, bonus

    def vente_exploration(self, e):
        noms = [d.get("SystemName") for d in e.get("Discovered") or []] + list(e.get("Systems") or [])
        for nom in noms:
            self.a_vendre.pop(nom, None)
        self.vendu += e.get("TotalEarnings") or 0

    def vente_exobio(self, e):
        for ligne in e.get("BioData") or []:
            self.exo_vendu += (ligne.get("Value") or 0) + (ligne.get("Bonus") or 0)
        self.exo.clear()

    def perdre_donnees(self):
        self.a_vendre.clear()
        self.exo.clear()

    # ---------- Affichage ----------
    def _valeurs(self, c):
        """(valeur actuelle, valeur une fois cartographié), None pour un corps sans Scan."""
        e = c.get("scan")
        if not e:
            return None, None
        premier = e.get("WasDiscovered") is False
        if e.get("StarType"):
            v = valeur_etoile(e.get("StarType"), e.get("StellarMass"), premier)
            return v, v
        terra = (e.get("TerraformState") or "") in ("Terraformable", "Terraforming", "Terraformed")
        classe, masse = e.get("PlanetClass"), e.get("MassEM")
        carte = valeur_planete(classe, terra, masse, premier, True, e.get("WasMapped") is False, c["efficace"])
        return (carte if c["carto"] else valeur_planete(classe, terra, masse, premier)), carte

    def _retenir(self, c):
        e = c.get("scan") or {}
        if e and e.get("ScanType") != "NavBeaconDetail" and self.systeme:
            self.a_vendre.setdefault(self.systeme, {})[c["id"]] = self._valeurs(c)[0]

    def fiche(self, c):
        e = c.get("scan") or {}
        valeur, carte = self._valeurs(c)
        bio = _estimer_bio(c)
        etoile = bool(e.get("StarType"))
        classe = (f"Étoile {e['StarType']}" if etoile else CLASSES.get(e.get("PlanetClass"), e.get("PlanetClass")))
        terra = (e.get("TerraformState") or "") in ("Terraformable", "Terraforming", "Terraformed")
        return {
            "id": c["id"], "nom": c["nom"], "court": _nom_court(c["nom"], self.systeme),
            "classe": classe, "etoile": etoile, "terraformable": terra,
            "atterrissable": bool(e.get("Landable")),
            "distance_ls": e.get("DistanceFromArrivalLS"),
            "connu": bool(e),
            "premiere_decouverte": e.get("WasDiscovered") is False,
            "premiere_carto": not etoile and e.get("WasMapped") is False,
            "premier_pas": bool(e.get("Landable")) and e.get("WasFootfalled") is False,
            "balise": e.get("ScanType") == "NavBeaconDetail",
            "cartographie": c["carto"], "valeur": valeur, "valeur_carto": carte, "bio": bio,
            "potentiel": (carte or 0) + (bio["max_bonus"] if bio else 0),
        }

    def fiche_id(self, ident):
        return self.fiche(self.corps[ident]) if ident in self.corps else None

    def vue(self):
        fiches = sorted((self.fiche(c) for c in self.corps.values()), key=lambda f: -f["potentiel"])
        connues = [f for f in fiches if f["connu"] and not f["balise"]]
        return {
            "systeme": self.systeme, "corps": fiches, "dernier": self.dernier,
            "total": sum(f["valeur"] or 0 for f in connues),
            "total_carto": sum(f["valeur_carto"] or 0 for f in connues),
            "bio_min": sum(f["bio"]["min_bonus"] for f in fiches if f["bio"]),
            "bio_max": sum(f["bio"]["max_bonus"] for f in fiches if f["bio"]),
            "premieres": sum(1 for f in connues if f["premiere_decouverte"]),
            "session": {
                "a_vendre": sum(sum(v.values()) for v in self.a_vendre.values()),
                "corps": sum(len(v) for v in self.a_vendre.values()),
                "exo": sum(self.exo.values()), "exo_especes": len(self.exo),
                "vendu": self.vendu, "exo_vendu": self.exo_vendu,
            },
        }
