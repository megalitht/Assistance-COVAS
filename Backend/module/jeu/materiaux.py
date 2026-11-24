"""
materiaux.py — Stock des matériaux d'ingénieur (bruts, fabriqués, chiffrés), gardé sur le disque
(Backend/data/suivi/materiaux.json), et alertes de stock presque plein ou plein.

  - Materials (au lancement du jeu)  : le stock complet, qui remplace tout ;
  - MaterialCollected                : +   ;  MaterialDiscarded : −
  - MaterialTrade                    : − ce qui est payé, + ce qui est reçu (courtier en matériaux)
  - EngineerCraft (Ingredients), Synthesis (Materials), TechnologyBroker (Materials),
    EngineerContribution, ScientificResearch : −
  - MissionCompleted (MaterialsReward) : +
Le stock ne dépasse jamais la limite de son grade (table : materiaux_table.py).

Alertes (réglage config.toml [materiaux]) : « presque plein » au seuil (90 %) et « plein » à la
limite, une seule fois par matériau tant qu'il ne redescend pas sous le seuil. Le stock complet du
lancement du jeu ne fait jamais parler : il sert de point de départ.

Module pur : ni touches, ni micro, ni réseau. Il se teste seul (tests/test_materiaux.py).
"""
from module.jeu.materiaux_table import LIMITES, MATERIAUX
from module.jeu.suivi import Suivi

CATEGORIES = {"raw": "brut", "manufactured": "fabrique", "encoded": "encode"}
TITRES = {"brut": "Bruts", "fabrique": "Fabriqués", "encode": "Chiffrés"}
REGLAGES_DEFAUT = {"seuil_presque_plein": 90}


def cle(nom):
    return (nom or "").strip("$;").replace("_name", "").lower()


def categorie(nom, categorie_journal=None):
    """Catégorie d'un matériau : la table, sinon celle du journal (« Raw »,
    « $MICRORESOURCE_CATEGORY_Encoded; »). None : ce n'est pas un matériau (marchandise...)."""
    connu = MATERIAUX.get(cle(nom))
    if connu:
        return connu[0]
    brut = (categorie_journal or "").lower()
    return next((c for mot, c in CATEGORIES.items() if mot in brut), None)


def limite(nom):
    connu = MATERIAUX.get(cle(nom))
    return LIMITES[connu[1]] if connu else None


class SuiviMateriaux(Suivi):
    NOM = "materiaux"
    EVENEMENTS = frozenset({"Materials", "MaterialCollected", "MaterialDiscarded", "MaterialTrade",
                            "EngineerCraft", "Synthesis", "TechnologyBroker", "MissionCompleted",
                            "EngineerContribution", "ScientificResearch"})

    def __init__(self, chemin=None, reglages=None):
        super().__init__(chemin)
        self.reglages = reglages or (lambda: dict(REGLAGES_DEFAUT))

    def vierge(self):
        # stock : {clé: quantité} ; noms : {clé: nom écrit par le jeu} ; dits : {clé: "presque" | "plein"}
        return {"stock": {}, "noms": {}, "dits": {}, "releve": None}

    # ---------- Calculs ----------
    def _seuil(self):
        valeur = self.reglages().get("seuil_presque_plein", 90)
        return min(100, max(1, valeur)) / 100 if isinstance(valeur, (int, float)) else 0.9

    def _niveau(self, k, quantite):
        """None, "presque" ou "plein" pour cette quantité."""
        plafond = limite(k)
        if not plafond:
            return None
        if quantite >= plafond:
            return "plein"
        return "presque" if quantite >= plafond * self._seuil() else None

    def _changer(self, nom, delta, localise=None, categorie_journal=None, parler=True):
        """Ajoute (delta > 0) ou retire un matériau. Renvoie l'annonce éventuelle."""
        k = cle(nom)
        if not k or not categorie(k, categorie_journal):
            return None                               # pas un matériau (marchandise d'ingénieur...)
        if localise:
            self.donnees["noms"][k] = localise
        plafond = limite(k)
        quantite = max(0, self.donnees["stock"].get(k, 0) + (delta or 0))
        if plafond:
            quantite = min(quantite, plafond)
        self.donnees["stock"][k] = quantite
        return self._alerte(k, quantite, parler and delta > 0)

    def _alerte(self, k, quantite, parler=True):
        niveau, dit = self._niveau(k, quantite), self.donnees["dits"].get(k)
        if niveau is None:
            self.donnees["dits"].pop(k, None)        # redescendu sous le seuil : réarmé
            return None
        if niveau == "presque" and dit == "plein":
            self.donnees["dits"][k] = "presque"      # n'est plus plein : « plein » pourra resonner
            return None
        if dit == niveau or (niveau == "presque" and dit):
            return None
        self.donnees["dits"][k] = niveau
        if not parler:
            return None
        return {"type": niveau, "materiau": k, "nom": self.nom(k), "quantite": quantite, "limite": limite(k)}

    def nom(self, k):
        return self.donnees["noms"].get(k) or (MATERIAUX.get(k) or (None, None, k))[2]

    # ---------- Événements ----------
    def _appliquer(self, e):
        nom = e.get("event")
        if nom == "Materials":
            self._releve(e)
            return []
        changements = []                               # (nom, delta, nom traduit, catégorie)
        if nom == "MaterialCollected":
            changements.append((e.get("Name"), e.get("Count") or 1, e.get("Name_Localised"), e.get("Category")))
        elif nom == "MaterialDiscarded":
            changements.append((e.get("Name"), -(e.get("Count") or 1), e.get("Name_Localised"), e.get("Category")))
        elif nom == "MaterialTrade":
            paye, recu = e.get("Paid") or {}, e.get("Received") or {}
            changements.append((paye.get("Material"), -(paye.get("Quantity") or 0),
                                paye.get("Material_Localised"), paye.get("Category")))
            changements.append((recu.get("Material"), recu.get("Quantity") or 0,
                                recu.get("Material_Localised"), recu.get("Category")))
        elif nom in ("EngineerCraft", "Synthesis", "TechnologyBroker"):
            for m in e.get("Ingredients" if nom == "EngineerCraft" else "Materials") or []:
                changements.append((m.get("Name"), -(m.get("Count") or 0), m.get("Name_Localised"), m.get("Category")))
        elif nom == "EngineerContribution" and e.get("Type") == "Materials":
            changements.append((e.get("Material"), -(e.get("Quantity") or 0), e.get("Material_Localised"), None))
        elif nom == "ScientificResearch":
            changements.append((e.get("Name"), -(e.get("Count") or 0), e.get("Name_Localised"), e.get("Category")))
        elif nom == "MissionCompleted":
            for m in e.get("MaterialsReward") or []:
                changements.append((m.get("Name"), m.get("Count") or 0, m.get("Name_Localised"), m.get("Category")))
        annonces = [self._changer(*c) for c in changements]
        return [a for a in annonces if a]

    def _releve(self, e):
        """Stock complet du lancement : il remplace tout, sans annonce (point de départ)."""
        self.donnees["stock"] = {}
        for categorie_journal in ("Raw", "Manufactured", "Encoded"):
            for m in e.get(categorie_journal) or []:
                self._changer(m.get("Name"), m.get("Count") or 0, m.get("Name_Localised"),
                              categorie_journal, parler=False)
        self.donnees["releve"] = e.get("timestamp")

    # ---------- Interface ----------
    def vue(self):
        seuil = self._seuil()
        categories = {c: [] for c in TITRES}
        for k, quantite in self.donnees["stock"].items():
            cat = categorie(k)
            if not cat:
                continue
            plafond = limite(k) or 1
            categories[cat].append({"cle": k, "nom": self.nom(k), "grade": (MATERIAUX.get(k) or (None, 0))[1],
                                    "quantite": quantite, "limite": plafond,
                                    "part": round(quantite / plafond, 4),
                                    "etat": self._niveau(k, quantite) or "ok"})
        for liste in categories.values():
            liste.sort(key=lambda m: (-m["grade"], m["nom"]))
        presque = sum(1 for liste in categories.values() for m in liste if m["etat"] != "ok")
        return {"categories": [{"cle": c, "titre": TITRES[c], "materiaux": categories[c]} for c in TITRES],
                "presque_pleins": presque, "seuil": seuil, "releve": self.donnees["releve"]}
