"""
synthese.py — Synthèse vocale locale (Piper) avec un timbre d'ordinateur de bord.

Sert aux répliques dont le texte change à chaque fois (le rapport d'avarie : noms de
modules, pourcentages), qu'on ne peut donc pas enregistrer à l'avance comme les .wav
de barks.json.

    chemin = await synthetiser("Rapport d'avarie. Coque à 47 pour cent.")
    -> un .wav prêt pour la file audio du COVAS, ou None si la synthèse est indisponible
       (Piper absent, voix absente) : le COVAS reste alors muet et l'écran suffit.

Voix (hors ligne, sur le processeur : la carte graphique reste à Whisper), dans modele_synthese/ :
    fr_FR-siwis-medium : féminine, parle vers 223 Hz
    fr_FR-tom-medium   : masculine, parle vers 139 Hz (presque la hauteur des enregistrements)
Changer VOIX ci-dessous ; chaque voix a ses réglages (REGLAGES_VOIX). Pour retélécharger :
    python -m piper.download_voices fr_FR-tom-medium --download-dir module/modele_synthese

Effet calqué sur les répliques enregistrées du COVAS (data/son), mesurées sur les 36 fichiers :
  1. hauteur    : la voix est redécoupée période par période (PSOLA) pour aller vers
                  ~145 Hz comme les enregistrements
  2. boîte      : salle minuscule et dense (~70 ms), différente à gauche et à droite, puis
                  une traîne très faible
  3. peigne     : écho de 13,08 ms réinjecté sur lui-même -> résonance de tôle (les deux canaux)
  4. stéréo     : écho de 12,00 ms sur le canal droit seulement (empreinte des enregistrements)
  5. égalisation: courbe moyenne des enregistrements (graves coupés, éclat métallique vers 4 kHz)
  Pas de modulation en anneau ni de saturation : les enregistrements n'en ont pas.
PROFIL « fidele » (calqué sur les enregistrements, par défaut), « monocorde » (même timbre,
intonation aplatie) ou « metal » (monocorde et plus résonnant).

Essai à l'oreille (depuis Backend/) :
    python -m module.synthese "Rapport d'avarie, commandant."
    -> écrit essai_synthese.wav (et essai_synthese_brut.wav, sans effet) ; --jouer pour l'écouter.

Dépendance : pip install piper-tts
"""
import asyncio
import itertools
import os
import sys
import tempfile
import threading
import wave

import numpy as np

DOSSIER_MODELES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modele_synthese")
VOIX = "fr_FR-siwis-medium"

# Diction : intonation libre (noise_scale, valeur de Piper : pas de voix blasée) mais durées
# régulières (noise_w_scale bas : pas de syllabe traînée ni hachée) ; length_scale < 1 = plus rapide
DICTION = {"length_scale": 1.0, "noise_scale": 0.667, "noise_w_scale": 0.35}
PAUSE_ENTRE_PHRASES = 0.08      # secondes de silence entre deux phrases (silences de Piper retirés)
LOCUTEUR = None                 # voix à plusieurs locuteurs (upmc : 0 = Jessica, 1 = Pierre)
RESSERRER_MS = 25               # trous de silence dans une phrase ramenés à cette durée : pas de
                                # saccade entre les mots (0 = laisser la diction de Piper intacte)

# Réglages communs, mesurés sur les enregistrements (cepstre, interspectre gauche/droite, queue)
EFFET_BASE = {
    "hauteur_hz": 137.0,        # hauteur visée ; donne ~145 Hz mesurés, comme les enregistrements
    "intonation": 1.0,          # 1 = mélodie gardée (comme les enregistrements), 0 = monocorde
    "peigne_ms": 13.08,         # retard de la résonance commune aux deux canaux
    "peigne_retour": 0.45,      # réinjection (0 à 0,85) : plus haut = plus métallique
    "peigne_dose": 0.35,        # part de voix résonnante dans le mélange
    "echo_droit_ms": 12.0,      # écho propre au canal droit
    "echo_droit_gain": 0.8,
    "reverbe_s": 0.07,          # « boîte » très courte et dense : élargit sans faire traîner
    "reverbe_dose": 1.5,        # niveau de la boîte (réponse d'énergie 1) par rapport à la voix
    "traine_s": 0.9,            # traîne lente et faible derrière la boîte
    "traine_db": -42.0,
    "vocodeur": 0.0,            # 0 = voix traitée ; 1 = robot à vocodeur (note continue sculptée par la voix)
}

# Réglages propres à chaque voix : dose des résonances et égalisation (Hz, dB), mesurées pour que
# la voix traitée retrouve la courbe moyenne et l'empreinte des enregistrements
# (12 phrases du COVAS dites par Piper ; égalisation interpolée entre les points).
REGLAGES_VOIX = {
    "fr_FR-siwis-medium": {
        "egalisation": (
            (40, -21.5), (100, -15.5), (126, -30.0), (159, -30.0), (200, -20.0), (252, -15.5),
            (317, -7.0), (400, 4.0), (504, 1.5), (635, -2.5), (800, -11.0), (1008, -3.0),
            (1270, -1.0), (1600, -3.5), (2016, -3.0), (2540, -3.0), (3200, 2.0), (4032, 10.5),
            (5080, 5.5), (6400, -5.5), (8063, -12.0), (10159, -19.0), (11000, -31.0),
        ),
    },
    "fr_FR-tom-medium": {       # voix plus riche en harmoniques : résonances moins dosées
        "peigne_dose": 0.22,
        "echo_droit_gain": 0.4,
        "egalisation": (
            (40, -31.5), (100, -25.5), (126, -20.5), (159, -27.5), (200, -16.5), (252, -10.5),
            (317, -3.0), (400, 3.5), (504, -1.0), (635, -2.0), (800, -1.5), (1008, -0.5),
            (1270, 4.5), (1600, 0.0), (2016, -1.5), (2540, -14.5), (3200, -12.5), (4032, -5.0),
            (5080, -9.5), (6400, -14.5), (8063, -20.5), (10159, -13.0), (11000, -25.0),
        ),
    },
}

# Profils : ce qu'ils changent par-dessus les réglages de base et ceux de la voix
PROFILS = {
    "fidele": {},
    "monocorde": {"intonation": 0.0},
    "metal": {"intonation": 0.0, "peigne_retour": 0.7, "peigne_dose": 0.6},
    "vocodeur": {"intonation": 0.0, "vocodeur": 1.0},
    "vocodeur_chantant": {"intonation": 1.0, "vocodeur": 1.0},
}
PROFIL = "fidele"


def reglages(profil=None, voix=None):
    """Réglages complets de l'effet : base, puis voix, puis profil."""
    propres = {k: v for k, v in REGLAGES_VOIX.get(voix or VOIX, {}).items() if k != "egalisation"}
    return {**EFFET_BASE, **propres, **PROFILS[profil or PROFIL]}


def egalisation(voix=None):
    return REGLAGES_VOIX.get(voix or VOIX, {}).get("egalisation", ((40, 0.0), (20000, 0.0)))
VOLUME_RMS = 0.05               # niveau moyen des .wav enregistrés du COVAS (~0,045)
PAS_HAUTEUR = 0.005             # une mesure de hauteur toutes les 5 ms

DOSSIER_SORTIE = os.path.join(tempfile.gettempdir(), "covas_synthese")
FICHIERS_TOURNANTS = 4          # fichiers réutilisés à tour de rôle (aucun n'est en lecture quand on le réécrit)

_voix = {"modele": None, "erreur": None}
_verrou = threading.Lock()
_compteur = itertools.count()


# =====================================================================
#  VOIX
# =====================================================================
def charger():
    """Charge la voix une fois pour toutes (environ une seconde). Renvoie None si impossible."""
    with _verrou:
        if _voix["modele"] is not None or _voix["erreur"]:
            return _voix["modele"]
        chemin = os.path.join(DOSSIER_MODELES, VOIX + ".onnx")
        try:
            from piper import PiperVoice
        except ImportError:
            _voix["erreur"] = "Piper n'est pas installé (pip install piper-tts)"
        else:
            if not os.path.exists(chemin):
                _voix["erreur"] = f"voix introuvable : {chemin}"
            else:
                try:
                    _voix["modele"] = PiperVoice.load(chemin)
                except Exception as erreur:
                    _voix["erreur"] = f"voix illisible ({erreur!r})"
        if _voix["erreur"]:
            print(f"[Synthèse] Indisponible : {_voix['erreur']}. Le rapport sera seulement affiché.")
        return _voix["modele"]


def disponible() -> bool:
    return charger() is not None


def _voix_brute(texte):
    """Texte -> (échantillons float32 dans [-1, 1], fréquence d'échantillonnage)."""
    from piper import SynthesisConfig
    modele = charger()
    if modele is None:
        return None, None
    config = SynthesisConfig(speaker_id=LOCUTEUR, **DICTION) if LOCUTEUR is not None else SynthesisConfig(**DICTION)
    morceaux = list(modele.synthesize(texte, syn_config=config))
    if not morceaux:
        return None, None
    taux = morceaux[0].sample_rate
    pause = np.zeros(int(taux * PAUSE_ENTRE_PHRASES), dtype=np.float32)
    parties = []
    for morceau in morceaux:                      # Piper rend un morceau par phrase
        if parties:
            parties.append(pause)
        phrase = _rogner(np.asarray(morceau.audio_float_array, dtype=np.float32).reshape(-1), taux)
        parties.append(_resserrer(phrase, taux, RESSERRER_MS))
    return np.concatenate(parties), taux


def _resserrer(x, taux, garde_ms):
    """Raccourcit les trous de silence à l'intérieur d'une phrase (fondus de 4 ms aux raccords)."""
    P = int(0.005 * taux)
    n = len(x) // P
    if garde_ms <= 0 or n < 3:
        return x
    energie = np.sqrt(np.mean(x[:n * P].reshape(n, P) ** 2, axis=1))
    calme = energie < energie.max() * 10 ** (-35 / 20)
    garde = max(1, int(garde_ms / 5))
    gardes, debut, i = [], 0, 0
    while i < n:
        if calme[i]:
            j = i
            while j < n and calme[j]:
                j += 1
            if i > 0 and j < n and j - i > garde:      # trou intérieur trop long
                gardes.append((debut, (i + garde // 2) * P))
                debut = (j - (garde - garde // 2)) * P
            i = j
        else:
            i += 1
    gardes.append((debut, len(x)))
    if len(gardes) == 1:
        return x
    fondu = int(0.004 * taux)
    sortie = x[gardes[0][0]:gardes[0][1]].copy()
    for a, b in gardes[1:]:
        morceau = x[a:b]
        k = min(fondu, len(sortie), len(morceau))
        if k:
            rampe = np.linspace(0, 1, k, dtype=np.float32)
            sortie[-k:] = sortie[-k:] * rampe[::-1] + morceau[:k] * rampe
        sortie = np.concatenate([sortie, morceau[k:]])
    return sortie


def _rogner(x, taux, seuil_db=-40.0, marge_s=0.02):
    """Retire le silence que Piper laisse avant et après chaque phrase (les phrases s'enchaînent)."""
    if not len(x):
        return x
    fort = np.where(np.abs(x) > np.abs(x).max() * 10 ** (seuil_db / 20))[0]
    if not len(fort):
        return x
    marge = int(marge_s * taux)
    return x[max(0, fort[0] - marge):fort[-1] + marge]


# =====================================================================
#  HAUTEUR : SUIVI PUIS PSOLA (la voix est redécoupée période par période)
# =====================================================================
def _taille_fft(n):
    """Puissance de deux >= n : une FFT sur une longueur quelconque peut être très lente."""
    return 1 << int(np.ceil(np.log2(max(n, 2))))


def _passe_bas(x, taux, fc):
    nfft = _taille_fft(len(x))
    spectre = np.fft.rfft(x, nfft)
    f = np.fft.rfftfreq(nfft, 1 / taux)
    return np.fft.irfft(spectre / np.sqrt(1 + (f / fc) ** 4), nfft)[:len(x)]


def _suivre_hauteur(x, taux, fmin=70.0, fmax=420.0):
    """Hauteur toutes les PAS_HAUTEUR secondes (autocorrélation normalisée) ; 0 = son non voisé."""
    pas, L = int(PAS_HAUTEUR * taux), int(0.03 * taux)
    lmin, lmax = int(taux / fmax), int(taux / fmin) + 2
    nb = max(1, (len(x) - 1) // pas + 1)
    xp = np.pad(x, (L // 2, L + pas))
    fenetre = np.hanning(L)
    trames = xp[np.arange(L)[None, :] + pas * np.arange(nb)[:, None]] * fenetre
    nfft = 1 << int(np.ceil(np.log2(L + lmax + 1)))
    r = np.fft.irfft(np.abs(np.fft.rfft(trames, nfft)) ** 2, nfft)[:, :lmax + 2]
    rf = np.correlate(fenetre, fenetre, "full")[L - 1:L + lmax + 1]
    rn = r / (r[:, :1] + 1e-12) / np.maximum(rf / rf[0], 1e-3)[None, :]
    energie = np.sqrt(r[:, 0] / np.sum(fenetre ** 2))
    seuil_energie = energie.max() * 10 ** (-35 / 20)
    f0 = np.zeros(nb)
    for i in range(nb):
        zone = rn[i, lmin:lmax + 1]
        meilleur = zone.max()
        if meilleur < 0.5 or energie[i] < seuil_energie:
            continue
        # le plus petit retard presque aussi fort que le meilleur (évite les erreurs d'octave)
        l = lmin + int(np.argmax(zone >= 0.88 * meilleur))
        fin = min(lmax, l + max(2, l // 5))
        l += int(np.argmax(rn[i, l:fin + 1]))
        a, b, c = rn[i, l - 1], rn[i, l], rn[i, min(l + 1, lmax + 1)]
        decalage = 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) < 0 else 0.0
        f0[i] = taux / (l + decalage)
    # nettoyage : médiane glissante sur 5 mesures, îlots voisés de moins de 20 ms retirés
    voise = f0 > 0
    propre = f0.copy()
    for i in np.where(voise)[0]:
        voisins = f0[max(0, i - 2):i + 3]
        propre[i] = np.median(voisins[voisins > 0])
    debut = None
    for i in range(nb + 1):
        if i < nb and voise[i]:
            debut = i if debut is None else debut
        elif debut is not None:
            if i - debut < 4:
                propre[debut:i] = 0
            debut = None
    return propre


_hann = {}


def _fenetre(demi):
    if demi not in _hann:
        _hann[demi] = np.hanning(2 * demi + 1).astype(np.float32)
    return _hann[demi]


def _psola(x, taux, hauteur_hz, intonation):
    """Change la hauteur sans changer la durée ni le timbre : chaque période de la voix est
    découpée (fenêtre de deux périodes centrée sur une crête) puis recollée à l'écart voulu."""
    f0 = _suivre_hauteur(x, taux)
    if not (f0 > 0).any():
        return x
    pas = PAS_HAUTEUR * taux
    hauteur_a = lambda n: f0[min(len(f0) - 1, int(n / pas))]
    reference = float(np.median(f0[f0 > 0]))
    lisse = _passe_bas(x, taux, 900.0)
    n, periode_muette = len(x), int(0.005 * taux)
    # 1. marques d'analyse : une par période (sur la crête) quand c'est voisé, toutes les 5 ms sinon
    marques, periodes, hauteurs = [], [], []      # hauteur 0 = marque non voisée
    t, derniere = 0.0, -periode_muette
    while t < n:
        f = hauteur_a(int(t))
        if f > 0:
            P = taux / f
            a = max(0, derniere + int(0.6 * P), int(t - 0.3 * P))
            b = min(n, int(t + 0.3 * P))
            c = a + int(np.argmax(lisse[a:b])) if b > a else int(t)
        else:
            P, c = periode_muette, int(t)
        marques.append(c); periodes.append(P); hauteurs.append(f)
        derniere, t = c, c + P
    marques = np.array(marques)
    # 2. synthèse : chaque instant de sortie reprend la période d'analyse la plus proche
    marge = taux // 50 + 2                        # 20 ms : plus qu'une période de la voix la plus grave
    xp = np.pad(x.astype(np.float32), (marge, marge))
    y = np.zeros(len(xp), dtype=np.float32)
    ts, k = float(marques[0]), 0
    while ts < n:
        while k + 1 < len(marques) and abs(marques[k + 1] - ts) <= abs(marques[k] - ts):
            k += 1
        Pa, c = periodes[k], int(marques[k])
        demi = min(marge - 1, int(Pa))
        morceau = xp[c + marge - demi:c + marge + demi + 1] * _fenetre(demi)
        if hauteurs[k] > 0:
            cible = hauteur_hz * (hauteurs[k] / reference) ** intonation
            Pt = taux / cible
            morceau = morceau * np.sqrt(Pt / Pa)          # garde la même énergie par seconde
        else:
            Pt = Pa
        s = int(round(ts))
        y[s + marge - demi:s + marge + demi + 1] += morceau
        ts += Pt
    return y[marge:marge + n]


# =====================================================================
#  VOCODEUR : le robot classique (une note continue à qui la voix donne ses voyelles)
# =====================================================================
def _stft(x, N, H):
    fenetre = np.hanning(N).astype(np.float32)
    xp = np.pad(x, (N, N + H))
    nb = (len(xp) - N) // H
    trames = xp[np.arange(N)[None, :] + H * np.arange(nb)[:, None]] * fenetre
    return np.fft.rfft(trames, axis=1), fenetre


def _istft(Y, fenetre, H, n):
    N = len(fenetre)
    trames = np.fft.irfft(Y, N, axis=1) * fenetre
    y = np.zeros(H * len(trames) + N)
    somme = np.zeros_like(y)
    for i, t in enumerate(trames):
        y[i * H:i * H + N] += t
        somme[i * H:i * H + N] += fenetre ** 2
    return (y / np.maximum(somme, 1e-3))[N:N + n].astype(np.float32)


def _enveloppe(S, taux, N):
    """Enveloppe spectrale lissée (cepstre coupé à 1,5 ms : formants gardés, harmoniques effacées)."""
    c = np.fft.irfft(np.log(np.abs(S) + 1e-7), N, axis=1)
    L = int(0.0015 * taux)
    c[:, L:N - L] = 0
    return np.fft.rfft(c, axis=1).real


def _vocoder(x, taux, hauteur_hz, intonation, relache_db_s=160.0):
    """La voix ne garde que ses formants ; la vibration vient d'une note en dents de scie
    (fixe ou qui suit la mélodie), du souffle pour les consonnes. Les formants s'éteignent
    lentement (relache_db_s) : la note comble les petits trous entre les mots."""
    N = 1024 if taux <= 24000 else 2048
    H = N // 4
    f0 = _suivre_hauteur(x, taux)
    voisee = f0 > 0
    if not voisee.any():
        return x
    reference = float(np.median(f0[voisee]))
    # note porteuse : hauteur tenue pendant les consonnes (pas de rupture)
    tenue = f0.copy()
    dernier = reference
    for i in range(len(tenue)):
        dernier = tenue[i] if tenue[i] > 0 else dernier
        tenue[i] = dernier
    # mélodie lissée (médiane sur 45 ms) et bornée : une erreur d'octave du suivi ne fait pas sauter la note
    lisse = np.array([np.median(tenue[max(0, i - 4):i + 5]) for i in range(len(tenue))])
    rapport = np.clip(lisse / reference, 0.75, 1.4)
    rapport = np.convolve(np.pad(rapport, 3, mode="edge"), np.ones(7) / 7, mode="valid")
    instants = np.arange(len(x)) / (PAS_HAUTEUR * taux)
    note = hauteur_hz * np.interp(instants, np.arange(len(rapport)), rapport) ** intonation
    phase = np.cumsum(note / taux)
    scie = (2 * (phase % 1.0) - 1).astype(np.float32)
    souffle = np.random.default_rng(7).standard_normal(len(x)).astype(np.float32) * 0.3
    X, fenetre = _stft(x, N, H)
    C, _ = _stft(scie, N, H)
    B, _ = _stft(souffle, N, H)
    log_voix = _enveloppe(X, taux, N)
    # relâchement : chaque bande ne descend pas plus vite que relache_db_s
    chute = relache_db_s * (H / taux) / 20 * np.log(10)
    for i in range(1, len(log_voix)):
        log_voix[i] = np.maximum(log_voix[i], log_voix[i - 1] - chute)
    # part voisée par trame (lissée sur ~30 ms)
    v = np.interp((np.arange(len(X)) * H - N) / (PAS_HAUTEUR * taux), np.arange(len(f0)), voisee.astype(float))
    v = np.convolve(v, np.ones(3) / 3, mode="same")[:, None]
    porteuse = v * C / np.exp(_enveloppe(C, taux, N)) + (1 - v) * B / np.exp(_enveloppe(B, taux, N))
    return _istft(porteuse * np.exp(log_voix), fenetre, H, len(x))


# =====================================================================
#  CHAÎNE D'EFFET (peigne, écho droit, réverbération, égalisation)
# =====================================================================
def _peigne(x, taux, ms, retour):
    """Filtre en peigne réinjecté : y[n] = x[n] + retour·y[n - retard] (calculé par blocs)."""
    retard = max(1, int(round(taux * ms / 1000)))
    y = x.copy()
    for debut in range(retard, len(y), retard):
        fin = min(debut + retard, len(y))
        y[debut:fin] += retour * y[debut - retard:fin - retard]
    return y * (1 - retour)                       # compense le gain des résonances


def _retarder(x, taux, ms):
    """Retard exact, même entre deux échantillons (interpolation linéaire)."""
    position = np.arange(len(x)) - taux * ms / 1000
    return np.interp(position, np.arange(len(x)), x, left=0.0).astype(x.dtype)


def _reponse_salle(taux, e, graine):
    """Réponse impulsionnelle d'une petite salle : bruit qui s'éteint vite (les aigus plus vite
    encore), suivi d'une traîne lente et faible."""
    n = int(taux * max(e["reverbe_s"], e["traine_s"]) * 1.1)
    bruit = np.random.default_rng(graine).standard_normal(n)
    t = np.arange(n) / taux
    spectre = np.fft.rfft(bruit)
    f = np.fft.rfftfreq(n, 1 / taux)
    traine = 10 ** (e["traine_db"] / 20)
    rep = np.zeros(n)
    for bas, haut, facteur in ((0, 1000, 1.0), (1000, 4000, 0.7), (4000, taux, 0.4)):
        bande = np.fft.irfft(np.where((f >= bas) & (f < haut), spectre, 0), n=n)
        rep += bande * (np.exp(-6.91 * t / (e["reverbe_s"] * facteur))
                        + traine * np.exp(-6.91 * t / (e["traine_s"] * facteur)))
    pre = int(0.008 * taux)                       # 8 ms avant les premières réflexions
    rep = np.concatenate([np.zeros(pre), rep[:n - pre]])
    rep[pre:pre + int(0.004 * taux)] *= np.linspace(0, 1, int(0.004 * taux))
    return (rep / np.sqrt(np.sum(rep ** 2))).astype(np.float32)


def _convoluer(x, rep):
    n = len(x) + len(rep) - 1
    nfft = 1 << int(np.ceil(np.log2(n)))
    return np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(rep, nfft), nfft)[:n].astype(np.float32)


def _egaliser(x, taux, points=None):
    points = egalisation() if points is None else points
    nfft = _taille_fft(len(x))
    spectre = np.fft.rfft(x, nfft)
    f = np.maximum(np.fft.rfftfreq(nfft, 1 / taux), 1.0)
    frequences = np.log([p[0] for p in points])
    gains_db = np.interp(np.log(f), frequences, [p[1] for p in points])
    return np.fft.irfft(spectre * 10 ** (gains_db / 20), nfft)[:len(x)].astype(np.float32)


def _niveler(x, taux, rapport=4.0):
    """Compresseur doux : au-dessus du niveau habituel des syllabes fortes, le volume ne monte plus
    qu'au quart. Écrase les sursauts (pas d'à-coup) sans toucher aux syllabes normales."""
    P = int(0.01 * taux)
    n = len(x) // P
    if n < 3:
        return x
    niveau = np.sqrt(np.mean(x[:n * P].reshape(n, P) ** 2, axis=1)) + 1e-9
    parle = niveau > niveau.max() * 0.03
    if parle.sum() < 3:
        return x
    seuil = np.percentile(niveau[parle], 80)
    gain = np.minimum(1.0, (seuil / niveau) ** (1 - 1 / rapport))
    gain = np.convolve(np.pad(gain, 2, mode="edge"), np.ones(5) / 5, mode="valid")   # pas de pompage
    gain_ech = np.interp(np.arange(len(x)), np.arange(n) * P + P / 2, gain)
    return (x * gain_ech).astype(np.float32)


def robotiser(x, taux, e=None, egalisation=None):
    """Voix de Piper (mono) -> voix du COVAS (stéréo, tableau n × 2). Voir reglages()."""
    e = reglages() if e is None else e
    x = np.asarray(x, dtype=np.float32)
    if not len(x):
        return np.zeros((0, 2), dtype=np.float32)
    # 1. Hauteur des enregistrements (et intonation, selon le profil)
    if e["vocodeur"] < 1:
        grave = _psola(x, taux, e["hauteur_hz"], e["intonation"])
    else:
        grave = np.zeros_like(x)
    if e["vocodeur"] > 0:                         # robot à vocodeur, pur ou mélangé
        robot = _vocoder(x, taux, e["hauteur_hz"], e["intonation"])
        robot *= np.sqrt(np.mean(x ** 2) / (np.mean(robot ** 2) + 1e-12))
        grave = (1 - e["vocodeur"]) * grave + e["vocodeur"] * robot
    if np.isfinite(grave).all():                  # sécurité : sinon on garde la voix telle quelle
        x = grave
    x = _niveler(x, taux)
    # 2. Salle, différente à gauche et à droite (même ordre que les enregistrements :
    #    les résonances s'appliquent ensuite au son de la salle aussi)
    queue = int(taux * max(e["reverbe_s"], e["traine_s"]) * 1.1)
    x = np.concatenate([x, np.zeros(queue, dtype=np.float32)])
    canaux = []
    for cote, echo in ((1, 0.0), (2, e["echo_droit_gain"])):
        c = x + e["reverbe_dose"] * _convoluer(x, _reponse_salle(taux, e, graine=cote))[:len(x)]
        # 3. Résonance métallique commune ; 4. écho de 12 ms à droite seulement
        c = (1 - e["peigne_dose"]) * c + e["peigne_dose"] * _peigne(c, taux, e["peigne_ms"], e["peigne_retour"])
        if echo:
            c = (c + echo * _retarder(c, taux, e["echo_droit_ms"])) / (1 + echo)
        canaux.append(c)
    y = np.stack(canaux, axis=1)
    # 5. Égalisation, volume et fondus
    y = np.stack([_egaliser(y[:, i], taux, egalisation) for i in range(2)], axis=1)
    audible = np.where(np.abs(y).max(axis=1) > np.abs(y).max() * 1e-3)[0]   # -60 dB : fin de la traîne
    y = y[:audible[-1] + 1] if len(audible) else y
    rms = float(np.sqrt(np.mean(y ** 2))) or 1.0
    y *= VOLUME_RMS / rms
    crete = float(np.abs(y).max())
    if crete > 0.97:
        y *= 0.97 / crete
    fondu = min(len(y) // 2, int(taux * 0.01))
    if fondu:
        rampe = np.linspace(0, 1, fondu, dtype=np.float32)[:, None]
        y[:fondu] *= rampe
        y[-fondu:] *= rampe[::-1]
    return y.astype(np.float32)


# =====================================================================
#  FICHIERS
# =====================================================================
def _ecrire_wav(chemin, x, taux):
    """Écrit un .wav 16 bits, mono (tableau n) ou stéréo (tableau n × 2)."""
    donnees = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(chemin, "wb") as f:
        f.setnchannels(1 if donnees.ndim == 1 else donnees.shape[1])
        f.setsampwidth(2)
        f.setframerate(taux)
        f.writeframes(donnees.tobytes())


def synthetiser_fichier(texte, chemin=None, effet=True):
    """Version bloquante : texte -> .wav. Renvoie le chemin, ou None si la synthèse est indisponible."""
    audio, taux = _voix_brute(texte)
    if audio is None:
        return None
    if effet:
        audio = robotiser(audio, taux)
    if chemin is None:
        os.makedirs(DOSSIER_SORTIE, exist_ok=True)
        chemin = os.path.join(DOSSIER_SORTIE, f"replique-{next(_compteur) % FICHIERS_TOURNANTS}.wav")
    _ecrire_wav(chemin, audio, taux)
    return chemin


async def synthetiser(texte):
    """Texte -> chemin d'un .wav robotisé (dossier temporaire), ou None. Ne bloque pas le COVAS."""
    if not texte or not texte.strip():
        return None
    try:
        return await asyncio.to_thread(synthetiser_fichier, texte)
    except Exception as erreur:
        print(f"[Synthèse] Échec : {erreur!r}")
        return None


if __name__ == "__main__":
    arguments = [a for a in sys.argv[1:] if not a.startswith("--")]
    phrase = " ".join(arguments) or ("Coque sous 40 pour cent. Boucliers hors ligne. Trois avaries : "
                                     "multi-canon hors service, capteurs 33 pour cent, propulseurs 44.")
    sortie = os.path.join(os.getcwd(), "essai_synthese.wav")
    if not synthetiser_fichier(phrase, sortie):
        sys.exit(1)
    synthetiser_fichier(phrase, os.path.join(os.getcwd(), "essai_synthese_brut.wav"), effet=False)
    print(f"Écrit : {sortie} (et essai_synthese_brut.wav, sans effet)")
    if "--jouer" in sys.argv:
        import pygame
        pygame.mixer.init()
        pygame.mixer.music.load(sortie)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.wait(100)
