"""
touches.py — Lit les raccourcis clavier directement dans le fichier d'Elite Dangerous.

Le jeu range tes commandes dans un fichier « .binds » :
  %LOCALAPPDATA%/Frontier Developments/Elite Dangerous/Options/Bindings/

Au lancement, le COVAS y lit la touche clavier de chaque commande qu'il utilise :
plus besoin de recopier tes raccourcis dans macros.py. Si une commande n'a pas de
touche clavier dans le jeu (ex. la vision nocturne, qui n'en a pas par défaut),
le COVAS te le dit et te donne le nom du réglage à remplir dans Options > Commandes.

TOUCHES VIRTUELLES : si une commande n'a aucune touche clavier, le COVAS lui en donne
une tout seul, prise parmi F13 à F24. Ces touches existent pour Windows et pour le jeu,
mais pas sur un clavier normal : tu ne peux pas les déclencher par erreur. Elles sont
écrites dans le fichier .binds (une sauvegarde « .bak » est faite avant) et le jeu les
prend en compte à son prochain lancement. Une manette ou une souris déjà assignée
reste en place : la touche virtuelle va dans l'emplacement libre.

Diagnostic : lance   python module/touches.py   pour voir ce qui a été lu
             (ajoute  --assigner  pour écrire aussi les touches virtuelles).

Si le dossier est ailleurs, indique-le dans la variable d'environnement COVAS_DOSSIER_BINDS.
"""
import glob
import os
import shutil
import time
import xml.etree.ElementTree as ET

# Disposition du clavier : "auto" (détectée), "azerty" ou "qwerty".
# À changer seulement si les touches lues sont décalées (A/Q, Z/W, M inversés).
CLAVIER = "auto"

# Donner une touche virtuelle (F13 à F24) aux commandes qui n'ont pas de touche clavier
ASSIGNER_TOUCHES_VIRTUELLES = True

# Touches virtuelles : d'abord seules, puis combinées avec F23 ou F24 (30 combinaisons)
_VIRTUELLES = [f"f{n}" for n in range(13, 23)]
_MODIFICATEURS_VIRTUELS = ["f23", "f24"]

# nom utilisé par le COVAS -> (nom de la commande dans le fichier .binds, libellé pour toi)
COMMANDES_JEU = {
    # Vol
    "train": ("LandingGearToggle", "Train d'atterrissage"),
    "soute": ("ToggleCargoScoop", "Écope de soute"),
    "cible": ("SelectTarget", "Cibler ce qui est devant"),
    "boost": ("UseBoostJuice", "Boost moteurs"),
    "saut": ("HyperSuperCombination", "Activer le FSD (saut / supercroisière)"),
    "supercroisiere": ("Supercruise", "Supercroisière"),
    "vitesse_zero": ("SetSpeedZero", "Régler la vitesse à 0 %"),
    "vitesse_75": ("SetSpeed75", "Régler la vitesse à 75 %"),
    "vitesse_max": ("SetSpeed100", "Régler la vitesse à 100 %"),
    # Énergie
    "pips_sys": ("IncreaseSystemsPower", "Énergie vers les systèmes"),
    "pips_moteurs": ("IncreaseEnginesPower", "Énergie vers les moteurs"),
    "pips_armes": ("IncreaseWeaponsPower", "Énergie vers les armes"),
    "pips_equilibre": ("ResetPowerDistribution", "Équilibrer l'énergie"),
    # Menus
    "ui_haut": ("UI_Up", "Interface : haut"),
    "ui_bas": ("UI_Down", "Interface : bas"),
    "ui_gauche": ("UI_Left", "Interface : gauche"),
    "ui_droite": ("UI_Right", "Interface : droite"),
    "ui_onglet_gauche": ("CyclePreviousPanel", "Interface : onglet précédent"),
    "ui_onglet_droite": ("CycleNextPanel", "Interface : onglet suivant"),
    "ui_selection": ("UI_Select", "Interface : valider"),
    "ui_retour": ("UI_Back", "Interface : retour"),
    "ec_nav": ("FocusLeftPanel", "Panneau de navigation (gauche)"),
    "ec_com": ("FocusCommsPanel", "Panneau de communication"),
    "ec_deploy": ("FocusRadarPanel", "Panneau de rôle (bas)"),
    "ec_sys": ("FocusRightPanel", "Panneau des systèmes (droite)"),
    "carte_galaxie": ("GalaxyMapOpen", "Carte de la galaxie"),
    "carte_systeme": ("SystemMapOpen", "Carte du système"),
    # Cockpit
    "nvg": ("NightVisionToggle", "Vision nocturne"),
    "phares": ("ShipSpotLightToggle", "Phares du vaisseau"),
    "armement": ("DeployHardpointToggle", "Déployer les points d'emport"),
    "hud": ("PlayerHUDModeToggle", "Changer de mode du cockpit (combat / analyse)"),
    "silencieux": ("ToggleButtonUpInput", "Mode silencieux"),
    # Combat
    "puce_thermique": ("DeployHeatSink", "Larguer une puce thermique"),
    "leurres": ("FireChaffLauncher", "Lancer des leurres"),
    "cible_menace": ("SelectHighestThreat", "Cibler la plus grande menace"),
    "cible_hostile": ("CycleNextHostileTarget", "Vaisseau hostile suivant"),
    "sous_systeme_suivant": ("CycleNextSubsystem", "Sous-système suivant"),
    "sous_systeme_precedent": ("CyclePreviousSubsystem", "Sous-système précédent"),
    "tir_principal": ("PrimaryFire", "Tir principal"),
    "tir_secondaire": ("SecondaryFire", "Tir secondaire"),
    "groupe_suivant": ("CycleFireGroupNext", "Groupe de tir suivant"),
    "groupe_precedent": ("CycleFireGroupPrevious", "Groupe de tir précédent"),
    # Chasseur embarqué
    "chasseur_defense": ("OrderDefensiveBehaviour", "Chasseur : défendre"),
    "chasseur_attaque": ("OrderFocusTarget", "Chasseur : attaquer ma cible"),
    "chasseur_feu_libre": ("OrderAggressiveBehaviour", "Chasseur : tir à volonté"),
    "chasseur_position": ("OrderHoldPosition", "Chasseur : tenir la position"),
    "chasseur_suivre": ("OrderFollow", "Chasseur : me suivre"),
    "chasseur_cessez": ("OrderHoldFire", "Chasseur : cesser le feu"),
    "chasseur_rappel": ("OrderRequestDock", "Chasseur : rappel au vaisseau"),
}

# Noms de touches du jeu -> noms compris par pydirectinput
_SPECIALES = {
    "space": "space", "tab": "tab", "enter": "enter", "backspace": "backspace", "escape": "esc",
    "home": "home", "end": "end", "insert": "insert", "delete": "delete",
    "pageup": "pageup", "pagedown": "pagedown", "capslock": "capslock",
    "uparrow": "up", "downarrow": "down", "leftarrow": "left", "rightarrow": "right",
    "leftshift": "shiftleft", "rightshift": "shiftright",
    "leftcontrol": "ctrlleft", "rightcontrol": "ctrlright",
    "leftalt": "altleft", "rightalt": "altright",
    "minus": "-", "equals": "=", "leftbracket": "[", "rightbracket": "]", "backslash": "\\",
    "semicolon": ";", "apostrophe": "'", "comma": ",", "period": ".", "slash": "/", "grave": "`",
    "numpad_enter": "enter", "numpad_add": "add", "numpad_subtract": "subtract",
    "numpad_multiply": "multiply", "numpad_divide": "divide", "numpad_decimal": "decimal",
}

# Clavier AZERTY : le jeu nomme la touche d'après la lettre imprimée dessus, alors que
# pydirectinput vise un emplacement physique (celui d'un clavier américain).
_AZERTY = {"a": "q", "q": "a", "z": "w", "w": "z", "m": ";", ",": "m", ";": ",", ":": ".", "!": "/"}

ETAT = {"fichier": None, "disposition": None, "azerty": False, "lues": {}, "manquantes": {},
        "assignees": {}}


def dossier_binds():
    return os.environ.get("COVAS_DOSSIER_BINDS") or os.path.join(
        os.environ.get("LOCALAPPDATA", ""), "Frontier Developments", "Elite Dangerous",
        "Options", "Bindings")


def trouver_fichier():
    """Le fichier .binds du profil choisi dans le jeu (sinon le plus récent)."""
    dossier = dossier_binds()
    fichiers = glob.glob(os.path.join(dossier, "*.binds"))
    if not fichiers:
        return None
    profils = []
    for nom in ("StartPreset.4.start", "StartPreset.start"):
        try:
            with open(os.path.join(dossier, nom), "r", encoding="utf-8") as f:
                profils = [ligne.strip() for ligne in f if ligne.strip()]
            break
        except OSError:
            continue
    # Depuis Odyssey : 4 lignes (général, vaisseau, VRS, à pied) ; on veut le vaisseau.
    profil = profils[1] if len(profils) > 1 else (profils[0] if profils else None)
    if profil:
        du_profil = [f for f in fichiers
                     if os.path.basename(f).lower().startswith(profil.lower() + ".")]
        if du_profil:
            fichiers = du_profil
    return max(fichiers, key=os.path.getmtime)


def _convertir(nom_jeu, azerty):
    """'Key_LeftArrow' -> 'left'. Renvoie None si la touche est inconnue."""
    if not nom_jeu or not nom_jeu.startswith("Key_"):
        return None
    nom = nom_jeu[4:].lower()
    if nom.startswith("numpad_") and nom[7:].isdigit():
        return "numpad" + nom[7:]
    if nom in _SPECIALES:
        touche = _SPECIALES[nom]
    elif len(nom) == 1 and (nom.isalnum()):
        touche = nom
    elif nom.startswith("f") and nom[1:].isdigit():
        touche = nom
    else:
        return None
    return _AZERTY.get(touche, touche) if azerty else touche


def _touche_clavier(element, azerty):
    """(touche, [modificateurs]) de la 1re affectation clavier utilisable, sinon None."""
    for emplacement in ("Primary", "Secondary"):
        affectation = element.find(emplacement)
        if affectation is None or affectation.get("Device") != "Keyboard":
            continue
        touche = _convertir(affectation.get("Key"), azerty)
        if not touche:
            continue
        modificateurs = []
        for m in affectation.findall("Modifier"):
            converti = _convertir(m.get("Key"), azerty) if m.get("Device") == "Keyboard" else None
            if not converti:
                modificateurs = None
                break
            modificateurs.append(converti)
        if modificateurs is None:
            continue
        return (touche, modificateurs)
    return None


def _detecter_azerty(racine, disposition):
    if CLAVIER in ("azerty", "qwerty"):
        return CLAVIER == "azerty"
    # Les touches des menus trahissent la façon dont le jeu a nommé les lettres.
    for commande, lettre_azerty, lettre_qwerty in (("UI_Up", "Key_Z", "Key_W"),
                                                    ("UI_Left", "Key_Q", "Key_A"),
                                                    ("ForwardThrustButton", "Key_Z", "Key_W"),
                                                    ("YawLeftButton", "Key_Q", "Key_A")):
        element = racine.find(commande)
        if element is None:
            continue
        touches = {a.get("Key") for a in element if a.get("Device") == "Keyboard"}
        if lettre_azerty in touches:
            return True
        if lettre_qwerty in touches:
            return False
    return (disposition or "").lower().startswith(("fr", "be"))


def _combinaisons_prises(racine):
    """Ce que le fichier utilise déjà au clavier : ({(touche, (modificateurs))}, {modificateurs})."""
    prises, modificateurs = set(), set()
    for affectation in racine.iter():
        if affectation.tag not in ("Primary", "Secondary") or affectation.get("Device") != "Keyboard":
            continue
        mods = tuple(sorted(m.get("Key") for m in affectation.findall("Modifier")))
        prises.add((affectation.get("Key"), mods))
        modificateurs.update(mods)
    return prises, modificateurs


def _combinaisons_libres(racine):
    """Touches virtuelles libres, dans l'ordre : F13…F22 seules, puis F23+…, puis F24+…"""
    prises, modificateurs_pris = _combinaisons_prises(racine)
    touches_prises = {touche for touche, _ in prises}
    candidates = [(t, ()) for t in _VIRTUELLES]
    for m in _MODIFICATEURS_VIRTUELS:
        # un modificateur ne doit pas servir de touche seule ailleurs (et inversement)
        if "Key_" + m.upper() not in touches_prises:
            candidates += [(t, (m,)) for t in _VIRTUELLES]
    for touche, mods in candidates:
        cle_jeu = "Key_" + touche.upper()
        mods_jeu = tuple("Key_" + m.upper() for m in mods)
        if cle_jeu in modificateurs_pris or (cle_jeu, mods_jeu) in prises:
            continue
        yield touche, mods


def _emplacement_libre(racine, commande):
    """L'emplacement vide (Secondary de préférence) de la commande, créé au besoin."""
    element = racine.find(commande)
    if element is None:
        element = ET.SubElement(racine, commande)
        element.text, element.tail = "\n\t\t", "\n\t"
        for nom in ("Primary", "Secondary"):
            vide = ET.SubElement(element, nom, Device="{NoDevice}", Key="")
            vide.tail = "\n\t\t" if nom == "Primary" else "\n\t"
    for nom in ("Secondary", "Primary"):
        emplacement = element.find(nom)
        if emplacement is not None and emplacement.get("Device") == "{NoDevice}":
            return emplacement
    return None


def _ecrire(fichier, racine):
    """Sauvegarde l'ancien fichier, puis écrit le nouveau sans risque de le laisser à moitié."""
    shutil.copy2(fichier, f"{fichier}.avant-covas-{time.strftime('%Y%m%d-%H%M%S')}.bak")
    with open(fichier, "r", encoding="utf-8-sig") as f:
        entete = f.readline().strip()
    if not entete.startswith("<?xml"):
        entete = '<?xml version="1.0" encoding="UTF-8" ?>'
    temporaire = fichier + ".covas-tmp"
    with open(temporaire, "w", encoding="utf-8", newline="\n") as f:
        f.write(entete + "\n" + ET.tostring(racine, encoding="unicode") + "\n")
    os.replace(temporaire, fichier)


def _jeu_lance():
    if os.name != "nt":
        return False
    import ctypes
    return bool(ctypes.windll.user32.FindWindowW("FrontierDevelopmentsAppWinClass", None))


def _assigner_virtuelles(fichier, racine, sauf):
    """Donne une touche virtuelle aux commandes sans touche clavier, et l'écrit dans le jeu."""
    libres = _combinaisons_libres(racine)
    for nom in [n for n in ETAT["manquantes"] if n not in sauf]:
        commande = COMMANDES_JEU[nom][0]
        emplacement = _emplacement_libre(racine, commande)
        if emplacement is None:
            print(f"[Touches] {nom} : les deux emplacements sont pris (manette/souris), "
                  "pas de touche virtuelle possible.")
            continue
        combinaison = next(libres, None)
        if combinaison is None:
            print("[Touches] Plus de touche virtuelle libre.")
            break
        touche, mods = combinaison
        emplacement.attrib.clear()
        emplacement.set("Device", "Keyboard")
        emplacement.set("Key", "Key_" + touche.upper())
        for m in mods:
            emplacement.text = "\n\t\t\t"
            ET.SubElement(emplacement, "Modifier", Device="Keyboard",
                          Key="Key_" + m.upper()).tail = "\n\t\t"
        ETAT["assignees"][nom] = (touche, list(mods))

    if not ETAT["assignees"]:
        return
    try:
        _ecrire(fichier, racine)
    except OSError as erreur:
        print(f"[Touches] Impossible d'écrire {os.path.basename(fichier)} ({erreur}) : "
              "touches virtuelles non enregistrées.")
        ETAT["assignees"] = {}
        return
    for nom, (touche, mods) in ETAT["assignees"].items():
        ETAT["lues"][nom] = (touche, mods)
        ETAT["manquantes"].pop(nom, None)
        print(f"[Touches] {libelle(nom)} -> touche virtuelle {' + '.join(mods + [touche]).upper()}")
    if _jeu_lance():
        print("[Touches] Le jeu est lancé : redémarre-le pour qu'il charge les nouvelles touches "
              "(sinon il risque aussi de les effacer en enregistrant ses options).")


def charger(assigner=False, sauf=()):
    """Lit le fichier .binds. Renvoie {nom COVAS: (touche, [modificateurs])}.
    assigner=True : donne une touche virtuelle aux commandes qui n'en ont pas
    (sauf celles listées dans `sauf`)."""
    ETAT.update(fichier=None, disposition=None, azerty=False, lues={}, manquantes={},
                assignees={})
    fichier = trouver_fichier()
    if not fichier:
        print(f"[Touches] Aucun fichier .binds dans {dossier_binds()} : touches par défaut de "
              "macros.py. (Modifie une commande dans le jeu pour qu'il crée ce fichier.)")
        return {}
    try:
        racine = ET.parse(fichier).getroot()
    except (OSError, ET.ParseError) as erreur:
        print(f"[Touches] Fichier illisible ({erreur}) : touches par défaut de macros.py.")
        return {}

    disposition = racine.findtext("KeyboardLayout")
    azerty = _detecter_azerty(racine, disposition)
    ETAT.update(fichier=fichier, disposition=disposition, azerty=azerty)

    for nom, (commande, libelle) in COMMANDES_JEU.items():
        element = racine.find(commande)
        touche = _touche_clavier(element, azerty) if element is not None else None
        if touche:
            ETAT["lues"][nom] = touche
        else:
            ETAT["manquantes"][nom] = libelle
    print(f"[Touches] {len(ETAT['lues'])} touches lues dans {os.path.basename(fichier)} "
          f"(clavier {'AZERTY' if azerty else 'QWERTY'}).")
    if assigner and ASSIGNER_TOUCHES_VIRTUELLES and ETAT["manquantes"]:
        _assigner_virtuelles(fichier, racine, set(sauf))
    return dict(ETAT["lues"])


def libelle(nom):
    """Nom du réglage dans Options > Commandes, pour dire au commandant quoi régler."""
    return COMMANDES_JEU.get(nom, (None, nom))[1]


if __name__ == "__main__":
    import sys
    charger(assigner="--assigner" in sys.argv)
    print(f"\nFichier : {ETAT['fichier']}\nDisposition : {ETAT['disposition']}\n")
    for nom, (touche, modificateurs) in sorted(ETAT["lues"].items()):
        print(f"  {nom:24} {' + '.join(modificateurs + [touche])}")
    if ETAT["manquantes"]:
        print("\nSans touche clavier dans le jeu (Options > Commandes) :")
        for nom, texte in sorted(ETAT["manquantes"].items()):
            print(f"  {nom:24} {texte}")
