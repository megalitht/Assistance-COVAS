# module/dialogue/comprehension.py
"""
Rend la reconnaissance vocale plus tolérante.

Whisper ne transcrit pas toujours parfaitement : « mets les NVG » peut devenir
« mêlant VJ », « FSD » peut sortir en « F.S.D » ou « effe esse dé ». Ce module :

1. normalise la phrase (minuscules, sans accents ni ponctuation, sigles recollés :
   « n.v.g » / « n v g » -> « nvg ») ;
2. corrige les erreurs d'écoute connues (CORRECTIONS ci-dessous, à compléter) ;
3. cherche les mots-clés d'abord à l'identique, puis de façon approchée
   (« atterisage » ≈ « atterrissage », « croisierre » ≈ « croisière »).
"""
import re
import unicodedata
from difflib import SequenceMatcher
from typing import NamedTuple

# Similarité minimale (0 à 1) pour accepter un mot-clé approché.
SEUIL_APPROCHE = 0.82
# En dessous de cette longueur, un mot-clé doit être entendu exactement :
# « tir », « hud », « fsd »… se confondent trop facilement avec d'autres mots.
LONGUEUR_MIN_APPROCHE = 5

# Lettres épelées à la française, telles que Whisper les écrit parfois en toutes lettres.
_N = r"(?:n|en|enne|ene|aine|haine|hen)"
_V = r"(?:v|ve|vee|vay)"
_G = r"(?:g|j|ge|je|gee|jee|gai|jai)"
_F = r"(?:f|ef|eff|effe|ephe)"
_S = r"(?:s|es|ess|esse|aisse)"
_D = r"(?:d|de|dee|des|dai)"

# Erreurs d'écoute connues -> forme attendue. Les motifs s'appliquent au texte DÉJÀ
# normalisé (minuscules, sans accents, sigles recollés). Ajoutez-en au besoin en
# regardant ce que la console affiche après « [Écoute] ».
CORRECTIONS = [
    # NVG épelé lettre par lettre : « haine vé gé », « n v j », « en vg »…
    (rf"\b{_N}\s*{_V}\s*{_G}\b", "nvg"),
    # NVG dont le « N » a été avalé par le mot précédent : « mêlant VJ », « les VG »
    (r"\b[vb]\s*[gj]\b", "nvg"),
    (r"\b(?:nvj|nbg|mvg|envg|envj|anvg|anvj)\b", "nvg"),
    # FSD épelé ou déformé
    (rf"\b{_F}\s*{_S}\s*{_D}\b", "fsd"),
    (r"\b(?:fst|fsb|fsg|efsd|ffsd)\b", "fsd"),
    # Mot de réveil
    (r"\b(?:cova|covasse|kovasse|cobas|kobas|gova|govas|covaz|kovaz|kovass|covass"
     r"|covers|cover|kovers|kover|cauvas|cofas)\b", "covas"),
    # Divers
    (r"\bhe\s*u\s*d\b", "hud"),
    (r"\bboust\b", "boost"),
    # « soute » entendu « suite », seulement après un verbe (« tout de suite » reste intact)
    (r"\b(ouvre|ouvrir|ferme|fermer|deploie|deployer|rentre|rentrer|sors|sortir) (la|ta) suite\b",
     r"\1 la soute"),
]
_CORRECTIONS = [(re.compile(motif), remplacement) for motif, remplacement in CORRECTIONS]

# Suite de lettres isolées (« n v g »). On exclut « a » / « y » (« à », « y ») et les
# lettres suivies d'une apostrophe (« l'arme », « d'atterrissage »).
_LETTRES_ISOLEES = re.compile(r"(?<![\w'])(?:[b-xz] )+[b-xz](?![\w'])")


def sans_accents(texte: str) -> str:
    return unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()


def normaliser(texte: str) -> str:
    """Phrase brute de Whisper -> forme comparable (voir l'en-tête du module)."""
    texte = (texte or "").lower().replace("’", "'").replace("`", "'")
    texte = sans_accents(texte)
    # Sigles avec points : « n.v.g. » -> « nvg »
    texte = re.sub(r"\b((?:[a-z]\.){2,}[a-z]?)", lambda m: m.group(1).replace(".", ""), texte)
    # Toute autre ponctuation devient un espace (l'apostrophe est gardée : « l'arme »)
    texte = re.sub(r"[^a-z0-9' ]+", " ", texte)
    texte = " ".join(texte.split())
    # Lettres épelées séparées : « n v g » -> « nvg »
    texte = _LETTRES_ISOLEES.sub(lambda m: m.group(0).replace(" ", ""), texte)
    for motif, remplacement in _CORRECTIONS:
        texte = motif.sub(remplacement, texte)
    return " ".join(texte.split())


def _similarite(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


similarite = _similarite


def present(mot_cle_norm: str, texte_norm: str) -> bool:
    """Le mot-clé apparaît dans la phrase, au DÉBUT d'un mot : « ravitaill » trouve
    « ravitaillement », mais « tir » ne trouve plus « sortir » ni « partir »."""
    return re.search(rf"(?<![a-z0-9]){re.escape(mot_cle_norm)}", texte_norm) is not None


def meilleure_approche(texte_norm: str, mot_cle_norm: str) -> float:
    """Similarité du meilleur passage de la phrase ayant le même nombre de mots que le
    mot-clé (on essaie aussi un mot de plus ou de moins : « auto pilote » / « autopilote »)."""
    mots = texte_norm.split()
    n = len(mot_cle_norm.split())
    meilleur = 0.0
    for taille in {max(1, n - 1), n, n + 1}:
        for i in range(len(mots) - taille + 1):
            passage = " ".join(mots[i:i + taille])
            meilleur = max(meilleur, _similarite(passage, mot_cle_norm),
                           _similarite(passage.replace(" ", ""), mot_cle_norm.replace(" ", "")))
    return meilleur


# ---------- Sens de l'ordre : sortir / activer, ou rentrer / couper ----------
_RENTRER = ("rentr", "rang", "remball", "remont", "relev", "ferm", "referm", "etein", "eteig",
            "desactiv", "desengag", "debranch", "coup", "repli", "retract", "escamot", "planqu",
            "cach", "retir", "enlev", "rabat", "rengain", "desarm", "arret", "stopp", "quitt")
_RENTRER_EXACT = {"leve", "leves", "lever", "levez", "monte", "montes", "monter", "montez",
                  "ote", "oter", "otez", "vire", "virer", "virez", "off", "dedans"}
_SORTIR = ("deploi", "deploy", "redeplo", "depli", "descend", "baiss", "abaiss", "ouvr", "rouvr",
           "allum", "rallum", "activ", "reactiv", "enclench", "engag", "branch", "rebranch",
           "demarr", "lanc", "degain", "affich")
_SORTIR_EXACT = {"mets", "met", "mettre", "mettez", "remets", "remet", "remettre", "dehors",
                 "montre", "montrer", "montrez"}
# « sors », « sortir », « sortie »... mais pas « sorte » (« de sorte que »)
_FORME_SORTIR = re.compile(r"(?:res)?sor(?:s|t|ti|tis|tie|tir|tez)$")
_HORS_SERVICE = re.compile(r"\bhors (?:tension|service|ligne)\b|\bau repos\b")
# « ne sors pas », « n'ouvre plus »... mais « n'oublie pas de sortir le train » reste un ordre,
# et « je n'ai plus de munitions » un constat (être, avoir, savoir, voir ne sont pas des ordres)
_NEGATION = re.compile(r"\bne? (?:(?:me|te|le|la|les|l|lui|leur|nous|vous|y|en) )*"
                       r"(?!oubli|hesit|manqu|(?:a|ai|as|avons|avez|ont|est|es|suis|sommes|etes"
                       r"|sont|sais|sait|vois|voit|comprends)\b)\w+ (?:pas|plus|jamais)\b")


def _sens_du_mot(mot):
    if mot in _RENTRER_EXACT or mot.startswith(_RENTRER):
        return "rentrer"
    if mot in _SORTIR_EXACT or mot.startswith(_SORTIR) or _FORME_SORTIR.match(mot):
        return "sortir"
    return None


def _analyser_sens(texte):
    """(sens de l'ordre ou None, True si la phrase contient un ordre à la forme négative)."""
    phrase = normaliser(texte).replace("'", " ")
    sans_negation = _NEGATION.sub(" ", phrase)
    nie = sans_negation != phrase
    mots, gardes = sans_negation.split(), []
    for mot, suivant in zip(mots, mots[1:] + [""]):
        if suivant in ("pas", "jamais") and _sens_du_mot(mot):      # à l'oral : « sors pas le train »
            nie = True
        else:
            gardes.append(mot)
    if _HORS_SERVICE.search(" ".join(gardes)):
        return "rentrer", nie
    for i, mot in enumerate(gardes):
        sens = _sens_du_mot(mot)
        if sens:
            suivant = gardes[i + 1] if i + 1 < len(gardes) else ""
            if sens == "sortir" and _FORME_SORTIR.match(mot) and suivant in ("du", "de", "des"):
                return "rentrer", nie               # « sors du mode silencieux »
            if mot.startswith("rentr") and suivant in ("en", "dans"):
                return "sortir", nie                # « rentre en mode silencieux »
            return sens, nie
    return ("sortir" if len(gardes) > 1 and gardes[-1] == "on" else None), nie      # « phares on »


def intention(texte: str) -> str | None:
    """'sortir', 'rentrer' ou None (= basculer) d'après la phrase."""
    return _analyser_sens(texte)[0]


def ordre_nie(texte: str) -> bool:
    """True pour « ne sors pas le train » ; False si un autre ordre suit (« ne sors pas, rentre-le »)."""
    sens, nie = _analyser_sens(texte)
    return nie and sens is None


_ENERGIE_ARMES = re.compile(r"\b(?:energie|puissance|pips?|aliment\w*)\b|\baux? armes?\b")


def _deplace_les_armes(texte_norm):
    """« Remballe tes armes » parle des points d'emport ; « énergie aux armes » des pips."""
    return intention(texte_norm) is not None and not _ENERGIE_ARMES.search(texte_norm)


# « Coupe l'assistance » tout court, mais ni « appel à l'assistance » ni celle de supercroisière
_ASSISTANCE_SEULE = re.compile(r"(\w+)(?:[ -](?:moi|nous))? l'? ?assistance\b"
                               r"(?! (?:de |a la |au )?(?:supercroisiere|conduite))")


def _ordre_sur_l_assistance(texte_norm):
    trouve = _ASSISTANCE_SEULE.search(texte_norm)
    return bool(trouve) and intention(trouve.group(1)) is not None


class Correspondance(NamedTuple):
    cle: str | None          # clé de barks.json, ou None
    mot_cle: str | None      # mot-clé reconnu (normalisé)
    exacte: bool             # True : mot-clé entendu tel quel ; False : approché
    score: float             # 1.0 si exacte, sinon la similarité


AUCUNE = Correspondance(None, None, False, 0.0)


def trouver_action_detail(texte: str, actions: dict, ignorees=()) -> Correspondance:
    """
    actions : {clé: {"mots_cles": [...]}} (le contenu de barks.json).
    1) Correspondance exacte (en début de mot) : le mot-clé le plus long l'emporte
       (« réarme » -> ravitaillement plutôt que « arme » -> énergie aux armes).
    2) Sinon, correspondance approchée : la plus forte similarité l'emporte.
    """
    texte_norm = normaliser(texte).replace("-", " ")
    if not texte_norm:
        return AUCUNE

    exacte, mot_exact = None, ""
    approchee, mot_approche, score_max = None, None, 0.0
    for cle, donnees in actions.items():
        if cle in ignorees or not isinstance(donnees, dict):
            continue
        for mot_cle in donnees.get("mots_cles", []):
            mot_cle = normaliser(mot_cle).replace("-", " ")
            if not mot_cle:
                continue
            if present(mot_cle, texte_norm):
                if len(mot_cle) > len(mot_exact):
                    exacte, mot_exact = cle, mot_cle
            elif exacte is None and cle != "assistance_vol" \
                    and len(mot_cle.replace(" ", "")) >= LONGUEUR_MIN_APPROCHE:   # pas d'à-peu-près :
                # « assistance de supercroisière » ou « distance de vol » couperaient l'assistance
                score = meilleure_approche(texte_norm, mot_cle)
                if score > score_max:
                    approchee, mot_approche, score_max = cle, mot_cle, score

    if exacte == "energie_arm" and mot_exact.startswith("arme") and "armement" in actions \
            and "armement" not in ignorees and _deplace_les_armes(texte_norm):
        exacte = "armement"
    if not exacte and "assistance_vol" in actions and "assistance_vol" not in ignorees \
            and _ordre_sur_l_assistance(texte_norm):
        return Correspondance("assistance_vol", "assistance", True, 1.0)
    if exacte:
        return Correspondance(exacte, mot_exact, True, 1.0)
    if approchee and score_max >= SEUIL_APPROCHE:
        return Correspondance(approchee, mot_approche, False, score_max)
    return AUCUNE


def trouver_action(texte: str, actions: dict, ignorees=()) -> str | None:
    """Clé de l'action demandée, ou None (voir trouver_action_detail)."""
    resultat = trouver_action_detail(texte, actions, ignorees)
    if resultat.cle and not resultat.exacte:
        print(f"[Compréhension] Correspondance approchée : {resultat.cle} ({resultat.score:.0%})")
    return resultat.cle


def contient_reveil(texte: str, mots_reveil) -> bool:
    texte_norm = normaliser(texte)
    mots = {normaliser(m) for m in mots_reveil}
    if any(m and m in texte_norm for m in mots):
        return True
    # Tolérance : un mot de la phrase très proche de « covas »
    return any(_similarite(mot, "covas") >= 0.8 for mot in texte_norm.split())


def est_reveil_seul(texte: str, mots_reveil) -> bool:
    """Vrai si la phrase ne contient QUE le mot de réveil (« Covas ? », « Hé Covas »)."""
    texte_norm = normaliser(texte)
    restant = texte_norm
    for m in sorted({normaliser(m) for m in mots_reveil}, key=len, reverse=True):
        if m:
            restant = restant.replace(m, " ")
    restant = [mot for mot in restant.split() if mot not in {"he", "eh", "et", "hey", "ok", "oh"}
               and _similarite(mot, "covas") < 0.8]
    return contient_reveil(texte, mots_reveil) and not restant


def vocabulaire_pour_whisper(actions: dict) -> str:
    """Phrase d'amorce : Whisper écrit beaucoup mieux les mots qu'il « a déjà vus » ici."""
    return ("Commandes vocales du COVAS dans Elite Dangerous. Covas, mets les NVG. "
            "Covas, active le FSD. Sors le train d'atterrissage. Rentre le train d'atterrissage. "
            "Remballe les points d'emport. Ouvre la soute. Coupe l'assistance de vol. Boost. "
            "Pips aux moteurs, aux armes, aux boucliers. Mode croisière, mode combat. "
            "Puce thermique, leurres, appontage, décollage, autopilote, HUD, "
            "vision nocturne, phares, drone de prospection, chasseur, sous-système. "
            "Frein à main, tourelle, rappelle le vaisseau, lampe, trousse de soin, "
            "cellule d'énergie, échantillonneur. "
            "Rapport d'avarie, état des dégâts. Comment va le vaisseau ? "
            "Raconte-moi une histoire. Thargoïdes, Gardiens, Raxxla, Hutton Orbital, "
            "Fuel Rats, Colonia, Jameson.")
