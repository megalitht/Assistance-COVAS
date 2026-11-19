# module/comprehension.py
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
            elif exacte is None and len(mot_cle.replace(" ", "")) >= LONGUEUR_MIN_APPROCHE:
                score = meilleure_approche(texte_norm, mot_cle)
                if score > score_max:
                    approchee, mot_approche, score_max = cle, mot_cle, score

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
            "Covas, active le FSD. Sors le train d'atterrissage. Ouvre la soute. Boost. "
            "Pips aux moteurs, aux armes, aux boucliers. Mode croisière, mode combat. "
            "Puce thermique, leurres, appontage, décollage, autopilote, HUD, "
            "vision nocturne, phares, drone de prospection, chasseur, sous-système. "
            "Rapport d'avarie, état des dégâts. Comment va le vaisseau ? "
            "Raconte-moi une histoire. Thargoïdes, Gardiens, Raxxla, Hutton Orbital, "
            "Fuel Rats, Colonia, Jameson.")
