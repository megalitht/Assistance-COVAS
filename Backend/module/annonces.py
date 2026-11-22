"""
annonces.py — Le COVAS annonce ce que le commandant fait lui-même (touche, HOTAS...).

Aucune écoute du clavier : on regarde les drapeaux de Status.json, que le jeu met à jour quelle
que soit la manette utilisée. Un changement n'est annoncé que s'il vient vraiment du commandant :
  - pas si le COVAS vient d'appuyer sur cette touche (il a déjà répondu à l'ordre) ;
  - pas pendant un programme (décollage, voyage...) ;
  - pas autour d'un amarrage, d'un atterrissage, d'une supercroisière ou d'un saut, car le jeu
    range alors lui-même le train, les armes ou l'écope.

Module sans dépendance : il se teste sans importer macros.py.
"""

FENETRE_COVAS = 6.0         # s : un changement aussi proche d'un appui du COVAS vient de lui
CALME_TRANSITION = 3.0      # s de silence après un changement d'état du vol
DELAI_REPETITION = 5.0      # s avant de pouvoir redire la même phrase

_AMARRE, _POSE, _SUPERCROISIERE, _CHARGE = 1 << 0, 1 << 1, 1 << 4, 1 << 17
_VAISSEAU, _SAUT = 1 << 24, 1 << 30
_TRANSITIONS = _AMARRE | _POSE | _SUPERCROISIERE | _VAISSEAU | _SAUT

# nom : (bit de Status.json, touches du COVAS, réplique à l'allumage, réplique à l'extinction)
SUIVIS = {
    "train": (2, ("train",), "manuel_train_sorti", "manuel_train_rentre"),
    "armes": (6, ("armement",), "manuel_armes_sorties", "manuel_armes_rentrees"),
    "phares": (8, ("phares",), "manuel_phares_on", "manuel_phares_off"),
    "soute": (9, ("soute",), "manuel_soute_ouverte", "manuel_soute_fermee"),
    "silencieux": (10, ("silencieux",), "manuel_silencieux_on", "manuel_silencieux_off"),
    "analyse": (27, ("hud",), "manuel_analyse", "manuel_combat"),
    "nvg": (28, ("nvg",), "manuel_nvg_on", "manuel_nvg_off"),
}
_FSD = ("saut", "supercroisiere")


class DetecteurManuel:
    def __init__(self):
        self.precedents = None
        self.calme_jusque = -1e9
        self.dites = {}

    def _vient_du_covas(self, touches, maintenant, appuis):
        """True si le COVAS vient d'appuyer ; l'appui est consommé (un seul changement par appui)."""
        for touche in touches:
            quand = appuis.get(touche)
            if quand is not None and maintenant - quand < FENETRE_COVAS:
                appuis.pop(touche, None)
                return True
        return False

    def _pas_redit(self, cle, maintenant):
        if maintenant - self.dites.get(cle, -1e9) < DELAI_REPETITION:
            return False
        self.dites[cle] = maintenant
        return True

    def observer(self, flags, maintenant, appuis, muet=False, actives=None):
        """Renvoie les clés de répliques à dire pour ce nouvel état des drapeaux."""
        actives = actives or {}
        if not flags:                       # menu du jeu, chargement
            self.precedents = None
            return []
        precedents, self.precedents = self.precedents, flags
        if precedents is None:
            return []

        change = flags ^ precedents
        if change & _TRANSITIONS:
            self.calme_jusque = maintenant + CALME_TRANSITION
        en_calme = maintenant < self.calme_jusque
        a_bord = flags & precedents & _VAISSEAU

        cles = []
        if change & flags & _CHARGE and a_bord and not en_calme and not muet \
                and not self._vient_du_covas(_FSD, maintenant, appuis) \
                and actives.get("fsd", True) and self._pas_redit("manuel_fsd", maintenant):
            cles.append("manuel_fsd")
        if change & _CHARGE:                # le jeu peut ranger des modules pendant la charge
            self.calme_jusque = max(self.calme_jusque, maintenant + CALME_TRANSITION)
            en_calme = True

        bascules = [(nom, s) for nom, s in SUIVIS.items() if change & (1 << s[0])]
        # Vrai pour les appuis du COVAS même en calme : sinon l'appui resterait « en attente »
        bascules = [(nom, s) for nom, s in bascules
                    if not self._vient_du_covas(s[1], maintenant, appuis)]
        # Plusieurs modules d'un coup : c'est le jeu, pas une main sur une touche
        if len(bascules) == 1 and a_bord and not en_calme and not muet \
                and not flags & (_AMARRE | _POSE):
            nom, (bit, _, allume, eteint) = bascules[0]
            cle = allume if flags & (1 << bit) else eteint
            if actives.get(nom, True) and self._pas_redit(cle, maintenant):
                cles.append(cle)
        return cles
