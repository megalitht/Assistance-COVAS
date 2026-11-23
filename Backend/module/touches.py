"""
touches.py — Lit les raccourcis clavier directement dans le fichier d'Elite Dangerous.

Le jeu range tes commandes dans un fichier « .binds » :
  %LOCALAPPDATA%/Frontier Developments/Elite Dangerous/Options/Bindings/

Au lancement, le COVAS y lit la touche clavier de chaque commande qu'il utilise :
plus besoin de recopier tes raccourcis dans macros.py. Si une commande n'a pas de
touche clavier dans le jeu (ex. la vision nocturne, qui n'en a pas par défaut),
le COVAS te le dit et te donne le nom du réglage à remplir dans Options > Commandes.

TOUCHES VIRTUELLES : si une commande n'a aucune touche clavier, le COVAS lui en donne
une tout seul, prise parmi F13 à F20 (seules ou avec Maj droite / Ctrl gauche). Ces
touches existent pour Windows et pour le jeu, mais pas sur un clavier normal : tu ne
peux pas les déclencher par erreur. Elles sont
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

# Donner une touche virtuelle (F13 à F20) aux commandes qui n'ont pas de touche clavier
ASSIGNER_TOUCHES_VIRTUELLES = True

# Touches virtuelles (noms du jeu). Elite ne connaît que F13 à F20 : il efface F21 à F24
# en réécrivant ses réglages. Ordre : F13…F20 seules, puis Maj droite + F13…F20, puis
# Ctrl gauche + F13…F20 (24 combinaisons). Ctrl droit est évité : pydirectinput l'envoie mal.
_VIRTUELLES = [f"Key_F{n}" for n in range(13, 21)]
_MODIFICATEURS_VIRTUELS = ["Key_RightShift", "Key_LeftControl"]
_INCONNUES_DU_JEU = {f"Key_F{n}" for n in range(21, 25)}

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
    "poussee_haut": ("UpThrustButton", "Poussée verticale vers le haut"),
    "tangage_haut": ("PitchUpButton", "Tangage : cabrer (nez vers le haut)"),
    "tangage_bas": ("PitchDownButton", "Tangage : piquer (nez vers le bas)"),
    "assistance_vol": ("ToggleFlightAssist", "Assistance de vol"),
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

# VRS et pied à terre : lus dans le profil de leur catégorie, jamais écrits. Contrairement à
# COMMANDES_JEU, le COVAS ne leur donne aucune touche virtuelle : sans touche dans le jeu, il
# le dit et n'envoie rien.
COMMANDES_SOL = {
    "vrs_frein": ("AutoBreakBuggyButton", "VRS : frein à main"),
    "vrs_assistance": ("ToggleDriveAssist", "VRS : assistance de conduite"),
    "vrs_phares": ("HeadlightsBuggyButton", "VRS : phares"),
    "vrs_tourelle": ("ToggleBuggyTurretButton", "VRS : vue tourelle"),
    "vrs_soute": ("ToggleCargoScoop_Buggy", "VRS : écope de soute"),
    "vrs_groupe": ("BuggyCycleFireGroupNext", "VRS : groupe de tir suivant"),
    "vrs_pips_sys": ("IncreaseSystemsPower_Buggy", "VRS : énergie vers les systèmes"),
    "vrs_pips_moteurs": ("IncreaseEnginesPower_Buggy", "VRS : énergie vers les moteurs"),
    "vrs_pips_armes": ("IncreaseWeaponsPower_Buggy", "VRS : énergie vers les armes"),
    "vrs_pips_equilibre": ("ResetPowerDistribution_Buggy", "VRS : équilibrer l'énergie"),
    "vrs_carte_galaxie": ("GalaxyMapOpen_Buggy", "VRS : carte de la galaxie"),
    "vrs_carte_systeme": ("SystemMapOpen_Buggy", "VRS : carte du système"),
    "vrs_vaisseau": ("RecallDismissShip", "VRS : rappeler ou renvoyer le vaisseau"),
    "pied_lampe": ("HumanoidToggleFlashlightButton", "À pied : lampe"),
    "pied_vision": ("HumanoidToggleNightVisionButton", "À pied : vision nocturne"),
    "pied_bouclier": ("HumanoidToggleShieldsButton", "À pied : bouclier"),
    "pied_arme": ("HumanoidHideWeaponButton", "À pied : ranger ou sortir l'arme"),
    "pied_recharger": ("HumanoidReloadButton", "À pied : recharger l'arme"),
    "pied_grenade": ("HumanoidSelectNextGrenadeTypeButton", "À pied : grenade suivante"),
    "pied_soin": ("HumanoidHealthPack", "À pied : trousse de soin"),
    "pied_cellule": ("HumanoidBattery", "À pied : cellule d'énergie"),
    "pied_echantillonneur": ("HumanoidSwitchToSuitTool", "À pied : outil de la combinaison"),
    "pied_analyseur": ("HumanoidSwitchToCompAnalyser", "À pied : analyseur de profil"),
    "pied_carte_galaxie": ("GalaxyMapOpen_Humanoid", "À pied : carte de la galaxie"),
    "pied_carte_systeme": ("SystemMapOpen_Humanoid", "À pied : carte du système"),
}
# Ligne du fichier StartPreset de chaque catégorie (général, vaisseau, VRS, à pied)
_LIGNES_SOL = {"vrs_": 2, "pied_": 3}

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

# Clavier AZERTY : le jeu nomme parfois une touche par son caractère, avec ou sans Maj
# (« 1 » ou « & », « ? » ou « , »…). On renvoie la touche du même emplacement physique.
_AZERTY_CARACTERES = {}
for _touche_us, _caracteres in {
        "`": "² squared", "1": "& 1 ampersand", "2": "é 2 e_acute eacute",
        "3": "\" 3 quotedbl doublequote", "4": "' 4", "5": "( 5 leftparenthesis",
        "6": "6", "7": "è 7 e_grave egrave", "8": "_ 8 underline underscore",
        "9": "ç 9 c_cedilla ccedilla", "0": "à 0 a_grave agrave",
        "-": ") ° ring degree rightparenthesis", "=": "= + plus",
        "[": "^ ¨ umlaut circumflex", "]": "$ £ dollar pound",
        "'": "ù % u_grave ugrave percent", "\\": "* µ asterisk mu",
        "m": ", ?", ",": "; .", ".": ": /", "/": "! § section exclamation"}.items():
    for _c in _caracteres.split():
        _AZERTY_CARACTERES[_c] = _touche_us

ETAT = {"fichier": None, "disposition": None, "azerty": False, "lues": {}, "manquantes": {},
        "assignees": {}, "ecrit_jeu_lance": False}


def dossier_binds():
    return os.environ.get("COVAS_DOSSIER_BINDS") or os.path.join(
        os.environ.get("LOCALAPPDATA", ""), "Frontier Developments", "Elite Dangerous",
        "Options", "Bindings")


_FICHIERS_START = ("StartPreset.4.start", "StartPreset.start")


def lire_profils():
    """(fichier StartPreset, [profils]) : depuis Odyssey, 4 lignes (général, vaisseau,
    VRS, à pied). Un profil sans fichier .binds ici est un profil intégré au jeu."""
    for nom in _FICHIERS_START:
        chemin = os.path.join(dossier_binds(), nom)
        try:
            with open(chemin, "r", encoding="utf-8-sig") as f:
                return chemin, [ligne.strip() for ligne in f if ligne.strip()]
        except OSError:
            continue
    return None, []


def _profil_vaisseau(profils):
    return profils[1] if len(profils) > 1 else (profils[0] if profils else None)


def _fichier_du_profil(profil, fichiers):
    return [f for f in fichiers if os.path.basename(f).lower().startswith(profil.lower() + ".")]


def trouver_fichier():
    """Le fichier .binds du profil choisi dans le jeu (sinon le plus récent)."""
    fichiers = glob.glob(os.path.join(dossier_binds(), "*.binds"))
    if not fichiers:
        return None
    profil = _profil_vaisseau(lire_profils()[1])
    if profil and _fichier_du_profil(profil, fichiers):
        fichiers = _fichier_du_profil(profil, fichiers)
    return max(fichiers, key=os.path.getmtime)


def fichier_categorie(ligne):
    """Le fichier .binds d'une ligne de StartPreset, ou None pour un profil intégré au jeu.
    Ancien fichier à une seule ligne : le même fichier sert pour tout."""
    profils = lire_profils()[1]
    if len(profils) <= ligne:
        return trouver_fichier()
    fichiers = _fichier_du_profil(profils[ligne], glob.glob(os.path.join(dossier_binds(), "*.binds")))
    return max(fichiers, key=os.path.getmtime) if fichiers else None


def fichiers_utilises():
    """Tous les fichiers .binds lus par le COVAS (vaisseau, VRS, à pied), sans doublon."""
    fichiers = [trouver_fichier()] + [fichier_categorie(n) for n in _LIGNES_SOL.values()]
    return tuple(sorted({f for f in fichiers if f}))


def profil_integre():
    """Nom du profil intégré au jeu utilisé pour le vaisseau, ou None si c'est un fichier
    personnalisé. Dans ce cas, le jeu ne lit pas les touches écrites par le COVAS."""
    profil = _profil_vaisseau(lire_profils()[1])
    fichiers = glob.glob(os.path.join(dossier_binds(), "*.binds"))
    if profil and not _fichier_du_profil(profil, fichiers):
        return profil
    return None


def utiliser_profil_perso():
    """Fait utiliser au jeu le fichier personnalisé (celui où le COVAS écrit) pour toutes
    les catégories. À faire jeu fermé : le jeu réécrit ce fichier en quittant.
    Renvoie un message d'explication."""
    if _jeu_lance():
        return "Ferme d'abord Elite Dangerous (il réécrit ses réglages en quittant)."
    chemin, profils = lire_profils()
    fichier = trouver_fichier()
    if not chemin or not fichier:
        return "Fichier StartPreset ou .binds introuvable."
    perso = os.path.basename(fichier).split(".")[0]
    if profils and all(p == perso for p in profils):
        return f"Le jeu utilise déjà « {perso} » partout."
    shutil.copy2(chemin, f"{chemin}.avant-covas-{time.strftime('%Y%m%d-%H%M%S')}.bak")
    with open(chemin, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join([perso] * max(len(profils), 1)) + "\n")
    return (f"Profils {' / '.join(profils)} remplacés par « {perso} » partout "
            f"(sauvegarde faite). Lance le jeu et vérifie tes commandes.")


def pourquoi_sans_effet(nom):
    """Explication probable quand le jeu ne réagit pas à une touche virtuelle, sinon None."""
    if not est_virtuelle(nom):
        return None
    integre = profil_integre()
    if integre:
        return (f"le vaisseau utilise le profil intégré « {integre} », qui ne contient pas les "
                "touches virtuelles : jeu fermé, lance « python module/touches.py --profil-perso »")
    if ETAT["ecrit_jeu_lance"]:
        return "touche virtuelle ajoutée pendant que le jeu tournait : redémarre le jeu"
    return None


def est_virtuelle(nom):
    """True si la touche de cette commande est une touche virtuelle (F13 à F24)."""
    touche = ETAT["lues"].get(nom)
    return bool(touche) and touche[0] in {f"f{n}" for n in range(13, 25)}


def _convertir(nom_jeu, azerty):
    """'Key_LeftArrow' -> 'left'. Renvoie None si la touche est inconnue."""
    if not nom_jeu or not nom_jeu.startswith("Key_"):
        return None
    nom = nom_jeu[4:].lower()
    if azerty and nom in _AZERTY_CARACTERES:
        return _AZERTY_CARACTERES[nom]
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


def _emplacements_clavier(racine):
    for affectation in racine.iter():
        if affectation.tag in ("Primary", "Secondary") and affectation.get("Device") == "Keyboard":
            yield affectation


def _modificateurs(affectation):
    return tuple(sorted(m.get("Key") for m in affectation.findall("Modifier")))


def _vider(emplacement):
    for enfant in list(emplacement):
        emplacement.remove(enfant)
    emplacement.text = None
    emplacement.attrib.clear()
    emplacement.set("Device", "{NoDevice}")
    emplacement.set("Key", "")


def _reparer(racine):
    """Retire les touches virtuelles que le jeu ne connaît pas (F21-F24) et les doublons
    de touches virtuelles (le jeu a pu retirer un modificateur et créer un conflit).
    Renvoie le nombre d'emplacements vidés : le COVAS les réassigne ensuite."""
    vus, vides = set(), 0
    for affectation in list(_emplacements_clavier(racine)):
        mods = _modificateurs(affectation)
        cle = affectation.get("Key")
        if cle in _INCONNUES_DU_JEU or _INCONNUES_DU_JEU & set(mods):
            _vider(affectation)
            vides += 1
        elif cle in _VIRTUELLES:
            if (cle, mods) in vus:
                _vider(affectation)
                vides += 1
            vus.add((cle, mods))
    return vides


def _combinaisons_libres(racine):
    """Combinaisons virtuelles pas encore utilisées dans le fichier, dans l'ordre."""
    prises, modificateurs_pris = set(), set()
    for affectation in _emplacements_clavier(racine):
        mods = _modificateurs(affectation)
        prises.add((affectation.get("Key"), mods))
        modificateurs_pris.update(mods)
    candidates = [(t, ()) for t in _VIRTUELLES]
    candidates += [(t, (m,)) for m in _MODIFICATEURS_VIRTUELS for t in _VIRTUELLES]
    for touche, mods in candidates:
        if touche not in modificateurs_pris and (touche, mods) not in prises:
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


def _assigner_virtuelles(racine, sauf):
    """Donne une touche virtuelle aux commandes sans touche clavier (dans `racine`)."""
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
        emplacement.set("Key", touche)
        for m in mods:
            emplacement.text = "\n\t\t\t"
            ET.SubElement(emplacement, "Modifier", Device="Keyboard", Key=m).tail = "\n\t\t"
        ETAT["assignees"][nom] = racine.find(commande)


def _enregistrer(fichier, racine, vides):
    """Écrit les réparations et les nouvelles touches virtuelles dans le fichier du jeu."""
    try:
        _ecrire(fichier, racine)
    except OSError as erreur:
        print(f"[Touches] Impossible d'écrire {os.path.basename(fichier)} ({erreur}) : "
              "touches virtuelles non enregistrées.")
        return False
    if vides:
        print(f"[Touches] {vides} touche(s) virtuelle(s) abîmée(s) par le jeu retirée(s) "
              "(F21-F24 ou doublon).")
    for nom, element in ETAT["assignees"].items():
        ETAT["lues"][nom] = _touche_clavier(element, ETAT["azerty"])
        ETAT["manquantes"].pop(nom, None)
        touche, mods = ETAT["lues"][nom]
        print(f"[Touches] {libelle(nom)} -> touche virtuelle {' + '.join(mods + [touche]).upper()}")
    if _jeu_lance():
        ETAT["ecrit_jeu_lance"] = True
        print("[Touches] Le jeu est lancé : redémarre-le pour qu'il charge les nouvelles touches "
              "(sinon il risque aussi de les effacer en enregistrant ses options).")
    return True


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
    vides = _reparer(racine) if assigner and ASSIGNER_TOUCHES_VIRTUELLES else 0

    for nom, (commande, libelle) in COMMANDES_JEU.items():
        element = racine.find(commande)
        touche = _touche_clavier(element, azerty) if element is not None else None
        if touche:
            ETAT["lues"][nom] = touche
        else:
            ETAT["manquantes"][nom] = libelle
    print(f"[Touches] {len(ETAT['lues'])} touches lues dans {os.path.basename(fichier)} "
          f"(clavier {'AZERTY' if azerty else 'QWERTY'}).")
    if assigner and ASSIGNER_TOUCHES_VIRTUELLES:
        if ETAT["manquantes"]:
            _assigner_virtuelles(racine, set(sauf))
        if (vides or ETAT["assignees"]) and not _enregistrer(fichier, racine, vides):
            ETAT["assignees"] = {}
    integre = profil_integre()
    if integre and any(est_virtuelle(n) for n in ETAT["lues"]):
        print(f"[Touches] ATTENTION : pour le vaisseau, le jeu utilise son profil intégré "
              f"« {integre} », pas {os.path.basename(fichier)} : il ne voit pas les touches "
              "virtuelles (F13-F20). Jeu fermé, lance   python module/touches.py --profil-perso"
              "   ou choisis le profil « Custom » dans Options > Commandes.")
    return dict(ETAT["lues"])


def lire_sans_ecrire():
    """(fichier, azerty, {nom COVAS: (touche, [modificateurs])}) : lecture seule, ETAT intact."""
    fichier = trouver_fichier()
    if not fichier:
        return None, False, {}
    racine = ET.parse(fichier).getroot()
    azerty = _detecter_azerty(racine, racine.findtext("KeyboardLayout"))
    lues = {}
    for nom, (commande, _) in COMMANDES_JEU.items():
        element = racine.find(commande)
        touche = _touche_clavier(element, azerty) if element is not None else None
        if touche:
            lues[nom] = touche
    lues.update(_lire_sol(fichier, racine, azerty))
    return fichier, azerty, lues


def _lire_sol(fichier, racine, azerty):
    """Touches du VRS et du pied à terre, chacune dans le profil de sa catégorie."""
    lues = {}
    for prefixe, ligne in _LIGNES_SOL.items():
        source = fichier_categorie(ligne)
        if not source:
            continue                    # profil intégré au jeu : ses touches ne sont pas lisibles
        arbre, clavier = racine, azerty
        if source != fichier:
            arbre = ET.parse(source).getroot()
            clavier = _detecter_azerty(arbre, arbre.findtext("KeyboardLayout"))
        for nom, (commande, _) in COMMANDES_SOL.items():
            element = arbre.find(commande) if nom.startswith(prefixe) else None
            touche = _touche_clavier(element, clavier) if element is not None else None
            if touche:
                lues[nom] = touche
    return lues


def libelle(nom):
    """Nom du réglage dans Options > Commandes, pour dire au commandant quoi régler."""
    return (COMMANDES_JEU.get(nom) or COMMANDES_SOL.get(nom) or (None, nom))[1]


if __name__ == "__main__":
    import sys
    if "--profil-perso" in sys.argv:
        print(utiliser_profil_perso())
        sys.exit()
    charger(assigner="--assigner" in sys.argv)
    print(f"\nProfils du jeu (général, vaisseau, VRS, à pied) : {' / '.join(lire_profils()[1])}")
    print(f"\nFichier : {ETAT['fichier']}\nDisposition : {ETAT['disposition']}\n")
    for nom, (touche, modificateurs) in sorted(ETAT["lues"].items()):
        print(f"  {nom:24} {' + '.join(modificateurs + [touche])}")
    if ETAT["manquantes"]:
        print("\nSans touche clavier dans le jeu (Options > Commandes) :")
        for nom, texte in sorted(ETAT["manquantes"].items()):
            print(f"  {nom:24} {texte}")
