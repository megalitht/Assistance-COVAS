"""
effet_voix.py — La voix du COVAS : la voix du commandant enregistrée au micro, transformée
(studio vocal, module/studio/studio.py).

    voix_covas = robotiser(voix_mono, taux, reglages, egalisation)   -> tableau stéréo n × 2

Chaîne d'effet calquée sur les répliques enregistrées du COVAS (data/son), mesurées sur les 36 fichiers :
  1. hauteur    : la voix est redécoupée période par période (PSOLA) pour aller vers ~145 Hz comme
                  les enregistrements ; les formants (le « timbre » : taille de la gorge) peuvent
                  être déplacés à part
  2. boîte      : salle minuscule et dense (~70 ms), différente à gauche et à droite, puis une
                  traîne très faible
  3. peigne     : écho de 13,08 ms réinjecté sur lui-même -> résonance de tôle (les deux canaux)
  4. stéréo     : écho de 12,00 ms sur le canal droit seulement (empreinte des enregistrements)
  5. égalisation: courbe propre à chaque voix, calculée pour retrouver la courbe moyenne des
                  enregistrements (CIBLE_SPECTRE) ; voir etalonner()
  Pas de modulation en anneau ni de saturation : les enregistrements n'en ont pas.

Pour une prise du micro, nettoyer() passe avant : graves parasites coupés, bruit de fond retiré,
silences du début et de la fin rognés (et les clics du clavier qui démarre ou arrête la prise).

Aucun accès au micro, au clavier ni au jeu ici : seulement du calcul sur des tableaux numpy.
"""
import numpy as np

# Réglages communs, mesurés sur les enregistrements (cepstre, interspectre gauche/droite, queue)
EFFET_BASE = {
    "hauteur_hz": 137.0,        # hauteur visée ; donne ~145 Hz mesurés, comme les enregistrements
    "decalage_dt": None,        # ou bien : décalage fixe en demi-tons (remplace hauteur_hz), comme un
                                # changeur de voix ; ne dépend pas de la hauteur de référence
    "intonation": 1.0,          # 1 = mélodie gardée (comme les enregistrements), 0 = monocorde
    "reference_hz": None,       # hauteur habituelle de la voix d'origine (None = médiane de la phrase) :
                                # une voix étalonnée garde ainsi les mêmes écarts d'une prise à l'autre
    "formants": 1.0,            # timbre : > 1 = gorge plus petite (plus clair), < 1 = plus grande
    "peigne_ms": 13.08,         # retard de la résonance commune aux deux canaux
    "peigne_retour": 0.2,       # réinjection (0 à 0,85) : plus haut = plus métallique
    "peigne_dose": 0.1,         # part de voix résonnante dans le mélange (pic de cepstre mesuré ~0,05)
    "echo_droit_ms": 12.0,      # résonance propre au canal droit
    "echo_droit_gain": 0.0,     # ... en écho simple (ancien modèle)
    "echo_droit_retour": 0.26,  # ... en boucle (mesuré : pic de cepstre 0,25 à 12 ms, 2e reflet à 24 ms)
    "droit_aigus_db": -3.0,     # le canal droit est un peu plus sombre au-dessus de 2 kHz
    "salle_s": 0.3,             # pièce COMMUNE aux deux canaux : durée de la traîne (s, -60 dB)
    "salle_dose": 0.4,          # niveau de cette pièce (réponse d'énergie 1) par rapport à la voix
    "reverbe_s": 0.07,          # « boîte » très courte, propre à chaque canal : la petite différence
    "reverbe_dose": 0.5,        #   entre gauche et droite (cohérence mesurée ~0,7)
    "traine_s": 0.9,            # traîne lente et faible derrière la boîte
    "traine_db": -42.0,
    "vocodeur": 0.0,            # 0 = voix traitée ; 1 = robot à vocodeur (note continue sculptée par la voix)
}

# Les réglages ci-dessus sont mesurés (2026-11-22) sur deux paires voix brute du commandant /
# réplique d'origine (FSD3, EchangeRole) : cepstre de chaque canal, cohérence gauche/droite, traîne
# en fin de phrase. Le premier modèle (2026-11-19) avait une boîte forte et différente par canal,
# un écho simple de 12 ms à droite et un peigne plus fort : gardé comme référence de comparaison.
MODELE_2026_11_19 = {"echo_droit_gain": 0.8, "echo_droit_retour": 0.0, "droit_aigus_db": 0.0,
                     "salle_s": 0.0, "salle_dose": 0.0, "reverbe_dose": 1.5,
                     "peigne_retour": 0.45, "peigne_dose": 0.35}

# Profils : ce qu'ils changent par-dessus les réglages de base (et ceux propres à la voix)
PROFILS = {
    "fidele": {},
    "monocorde": {"intonation": 0.0},
    "metal": {"intonation": 0.0, "peigne_retour": 0.7, "peigne_dose": 0.6},
    "vocodeur": {"intonation": 0.0, "vocodeur": 1.0},
    "vocodeur_chantant": {"intonation": 1.0, "vocodeur": 1.0},
}

EGALISATION_NEUTRE = ((40, 0.0), (20000, 0.0))

# Bandes d'un tiers d'octave (Hz) où l'égalisation est réglée, de 100 Hz à 16 kHz
CENTRES = tuple(round(1000 * 2 ** (k / 3)) for k in range(-10, 13))

# Courbe moyenne des 36 répliques enregistrées d'origine (dB par bande de CENTRES, 0 dB = moyenne
# des bandes de 317 Hz à 3,2 kHz), mesurée par spectre_bandes() sur les .wav d'origine.
CIBLE_SPECTRE = None            # rempli plus bas (bloc « CIBLE »)

VOLUME_RMS = 0.05               # niveau moyen des .wav enregistrés du COVAS (~0,045)
PAS_HAUTEUR = 0.005             # une mesure de hauteur toutes les 5 ms


def reglages(profil="fidele", propres=None, choisis=None):
    """Réglages complets : base, puis réglages propres à la voix, puis profil, puis choix à la main."""
    return {**EFFET_BASE, **(propres or {}), **PROFILS[profil], **(choisis or {})}


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


def _coupe_bas(x, taux, fc, pente=4):
    """Passe-haut sans déphasage (pente 6 × pente dB/octave sous fc)."""
    nfft = _taille_fft(len(x))
    spectre = np.fft.rfft(x, nfft)
    f = np.fft.rfftfreq(nfft, 1 / taux)
    rapport = (f / fc) ** pente
    return np.fft.irfft(spectre * np.sqrt(rapport ** 2 / (1 + rapport ** 2)), nfft)[:len(x)].astype(np.float32)


def suivre_hauteur(x, taux, fmin=70.0, fmax=420.0):
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


_suivre_hauteur = suivre_hauteur            # ancien nom


def hauteur_mediane(x, taux):
    """Hauteur habituelle d'une voix (Hz), ou None si rien de voisé."""
    f0 = suivre_hauteur(np.asarray(x, dtype=np.float32), taux)
    return float(np.median(f0[f0 > 0])) if (f0 > 0).any() else None


_hann = {}


def _fenetre(demi):
    if demi not in _hann:
        _hann[demi] = np.hanning(2 * demi + 1).astype(np.float32)
    return _hann[demi]


def _psola(x, taux, hauteur_hz, intonation, formants=1.0, reference=None, decalage_dt=None):
    """Change la hauteur sans changer la durée ni le timbre : chaque période de la voix est
    découpée (fenêtre de deux périodes centrée sur une crête) puis recollée à l'écart voulu.
    formants != 1 : chaque morceau est aussi resserré (> 1) ou étiré (< 1) avant d'être recollé,
    ce qui déplace le timbre sans toucher à la hauteur."""
    f0 = suivre_hauteur(x, taux)
    if not (f0 > 0).any():
        return x
    pas = PAS_HAUTEUR * taux
    hauteur_a = lambda n: f0[min(len(f0) - 1, int(n / pas))]
    reference = float(reference or np.median(f0[f0 > 0]))
    if decalage_dt is not None:
        hauteur_hz = reference * 2 ** (decalage_dt / 12)
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
    formants = float(formants or 1.0)
    deforme = abs(formants - 1.0) > 1e-3
    # 20 ms : plus qu'une période de la voix la plus grave (davantage si les morceaux sont déformés)
    marge = int((taux // 50) * max(1.0, formants) / min(1.0, formants)) + 2
    xp = np.pad(x.astype(np.float32), (marge, marge))
    y = np.zeros(len(xp), dtype=np.float32)
    ts, k = float(marques[0]), 0
    while ts < n:
        while k + 1 < len(marques) and abs(marques[k + 1] - ts) <= abs(marques[k] - ts):
            k += 1
        Pa, c = periodes[k], int(marques[k])
        if hauteurs[k] > 0:
            Pt = taux / (hauteur_hz * (hauteurs[k] / reference) ** intonation)
        else:
            Pt = Pa
        if deforme:
            # morceau lu assez long pour qu'une fois resserré (ou étiré), il couvre encore deux
            # périodes de sortie : les morceaux se recouvrent, pas de grésillement entre eux
            demi_sortie = max(1, min(marge // 2, int(max(Pa / formants, Pt))))
            demi = int(demi_sortie * formants)                    # demi-morceau lu dans la voix
            source = xp[c + marge - demi - 1:c + marge + demi + 2]
            positions = demi + 1 + np.arange(-demi_sortie, demi_sortie + 1) * formants
            morceau = np.interp(positions, np.arange(len(source)), source).astype(np.float32)
            morceau *= _fenetre(demi_sortie) * np.float32(np.sqrt(Pt / demi_sortie))   # même énergie par seconde
            demi = demi_sortie
        else:
            demi = min(marge - 1, int(Pa))
            morceau = xp[c + marge - demi:c + marge + demi + 1] * _fenetre(demi)
            if hauteurs[k] > 0:
                morceau = morceau * np.sqrt(Pt / Pa)      # garde la même énergie par seconde
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


def _vocoder(x, taux, hauteur_hz, intonation, relache_db_s=160.0, formants=1.0, reference=None,
             decalage_dt=None):
    """La voix ne garde que ses formants ; la vibration vient d'une note en dents de scie
    (fixe ou qui suit la mélodie), du souffle pour les consonnes. Les formants s'éteignent
    lentement (relache_db_s) : la note comble les petits trous entre les mots."""
    N = 1024 if taux <= 24000 else 2048
    H = N // 4
    f0 = suivre_hauteur(x, taux)
    voisee = f0 > 0
    if not voisee.any():
        return x
    reference = float(reference or np.median(f0[voisee]))
    if decalage_dt is not None:
        hauteur_hz = reference * 2 ** (decalage_dt / 12)
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
    if abs(float(formants or 1.0) - 1.0) > 1e-3:            # formants déplacés : axe des fréquences étiré
        cases = np.arange(log_voix.shape[1])
        log_voix = np.stack([np.interp(cases / formants, cases, l) for l in log_voix])
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


def _etagere(x, taux, fc, gain_db):
    """Étagère douce : gain_db au-dessus de fc, 0 dB en dessous (sans déphasage)."""
    nfft = _taille_fft(len(x))
    f = np.fft.rfftfreq(nfft, 1 / taux)
    part = (f / fc) ** 2 / (1 + (f / fc) ** 2)
    gain = 1 + (10 ** (gain_db / 20) - 1) * part
    return np.fft.irfft(np.fft.rfft(x, nfft) * gain, nfft)[:len(x)].astype(np.float32)


def _convoluer(x, rep):
    n = len(x) + len(rep) - 1
    nfft = 1 << int(np.ceil(np.log2(n)))
    return np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(rep, nfft), nfft)[:n].astype(np.float32)


def _egaliser(x, taux, points):
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


def robotiser(x, taux, e=None, egalisation=EGALISATION_NEUTRE):
    """Voix mono -> voix du COVAS (stéréo, tableau n × 2). e : voir reglages() ;
    egalisation : points (Hz, dB) propres à la voix d'origine (voir etalonner())."""
    e = reglages() if e is None else {**EFFET_BASE, **e}
    x = np.asarray(x, dtype=np.float32)
    if not len(x):
        return np.zeros((0, 2), dtype=np.float32)
    # 1. Hauteur des enregistrements (et intonation, selon le profil), puis timbre
    if e["vocodeur"] < 1:
        grave = _psola(x, taux, e["hauteur_hz"], e["intonation"], e["formants"], e["reference_hz"],
                       e["decalage_dt"])
    else:
        grave = np.zeros_like(x)
    if e["vocodeur"] > 0:                         # robot à vocodeur, pur ou mélangé
        robot = _vocoder(x, taux, e["hauteur_hz"], e["intonation"], formants=e["formants"],
                         reference=e["reference_hz"], decalage_dt=e["decalage_dt"])
        robot *= np.sqrt(np.mean(x ** 2) / (np.mean(robot ** 2) + 1e-12))
        grave = (1 - e["vocodeur"]) * grave + e["vocodeur"] * robot
    if np.isfinite(grave).all():                  # sécurité : sinon on garde la voix telle quelle
        x = grave
    x = _niveler(x, taux)
    # 2. Salle : une pièce commune aux deux canaux (avec sa traîne), plus une petite boîte propre à
    #    chaque canal (gauche et droite ne sont pas tout à fait identiques). Même ordre que les
    #    enregistrements : les résonances s'appliquent ensuite au son de la salle aussi.
    queue = int(taux * max(e["reverbe_s"], e["traine_s"], e["salle_s"]) * 1.1)
    x = np.concatenate([x, np.zeros(queue, dtype=np.float32)])
    commune = x
    if e["salle_dose"] > 0 and e["salle_s"] > 0:
        piece = {"reverbe_s": e["salle_s"], "traine_s": e["salle_s"], "traine_db": -120.0}
        commune = x + e["salle_dose"] * _convoluer(x, _reponse_salle(taux, piece, graine=0))[:len(x)]
    canaux = []
    for cote in (1, 2):
        c = commune + e["reverbe_dose"] * _convoluer(x, _reponse_salle(taux, e, graine=cote))[:len(x)]
        # 3. Résonance métallique commune ; 4. résonance de 12 ms à droite seulement
        c = (1 - e["peigne_dose"]) * c + e["peigne_dose"] * _peigne(c, taux, e["peigne_ms"], e["peigne_retour"])
        if cote == 2:
            if e["echo_droit_gain"]:
                c = (c + e["echo_droit_gain"] * _retarder(c, taux, e["echo_droit_ms"])) / (1 + e["echo_droit_gain"])
            if e["echo_droit_retour"]:
                g = e["echo_droit_retour"]
                c = _peigne(c, taux, e["echo_droit_ms"], g) / (1 - g)
            if e["droit_aigus_db"]:
                c = _etagere(c, taux, 2000.0, e["droit_aigus_db"])
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
#  PRISE DU MICRO : NETTOYAGE (graves, bruit de fond, silences)
# =====================================================================
def _debruiter(x, taux, force):
    """Masque spectral : le bruit de fond est estimé sur les moments les plus calmes de la prise
    (avant de parler, entre les mots), puis retiré bande par bande. force 0 à 1."""
    N = 1 << int(round(np.log2(taux * 0.04)))     # ~40 ms
    H = N // 4
    X, fenetre = _stft(x, N, H)
    puissance = np.abs(X) ** 2
    energie = puissance.sum(axis=1)
    utiles = np.arange(4, max(5, len(X) - 4))    # pas les trames de bord (à moitié vides)
    calmes = utiles[np.argsort(energie[utiles])[:max(3, len(utiles) // 10)]]
    bruit = puissance[calmes].mean(axis=0) + 1e-14
    lisse = np.copy(puissance)                    # puissance lissée sur 3 trames : moins de « gazouillis »
    lisse[1:-1] = (puissance[:-2] + puissance[1:-1] + puissance[2:]) / 3
    sur = 1.0 + 2.0 * force                       # soustraction plus ou moins appuyée
    plancher = 10 ** (-(6 + 24 * force) / 20)     # ce qui reste du bruit : -6 à -30 dB
    gain = np.clip(1 - sur * bruit[None, :] / (lisse + 1e-14), plancher, 1.0)
    gain = np.apply_along_axis(lambda g: np.convolve(g, np.ones(5) / 5, mode="same"), 1, gain)
    gain[1:-1] = (gain[:-2] + 2 * gain[1:-1] + gain[2:]) / 4
    return _istft(X * gain, fenetre, H, len(x))


def _niveaux(x, taux):
    """Niveau (dB) de chaque tranche de 10 ms."""
    P = int(0.01 * taux)
    n = len(x) // P
    return 20 * np.log10(np.sqrt(np.mean(x[:n * P].reshape(n, P) ** 2, axis=1)) + 1e-9)


def zone_parole(x, taux, duree_min=0.08):
    """(début, fin) en échantillons de la parole dans une prise (avant débruitage : le seuil se
    règle sur le vrai bruit de fond). Les bruits plus courts que duree_min (clic du clavier,
    bouche) sont ignorés. None si rien n'a été dit."""
    P = int(0.01 * taux)
    niveau = _niveaux(x, taux)
    n = len(niveau)
    if n < 5:
        return None
    seuil = max(np.percentile(niveau, 10) + 10, np.percentile(niveau, 99) - 40, -70)
    actif = niveau > seuil
    # les petits trous (< 40 ms : occlusives, « t », « p ») ne coupent pas un mot
    trous = 0
    for i in range(n):
        if actif[i]:
            if 0 < trous <= 4 and i - trous - 1 >= 0 and actif[i - trous - 1]:
                actif[i - trous:i] = True
            trous = 0
        else:
            trous += 1
    morceaux, debut = [], None
    for i in range(n + 1):
        if i < n and actif[i]:
            debut = i if debut is None else debut
        elif debut is not None:
            if (i - debut) * P >= duree_min * taux:
                morceaux.append((debut, i))
            debut = None
    if not morceaux:
        return None
    return morceaux[0][0] * P, morceaux[-1][1] * P


def bande_utile(x, taux):
    """Fréquence (Hz) au-delà de laquelle une prise est vide : micro ou liaison limités (un casque
    sans fil en mode « mains libres » coupe vers 7 kHz). None si la prise monte au-delà de 11 kHz."""
    f, puissance = _spectre_moyen(x, taux)
    largeur = max(1, int(200 / f[1]))
    db = 10 * np.log10(np.convolve(puissance, np.ones(largeur) / largeur, mode="same") + 1e-30)
    reference = np.median(db[(f >= 1000) & (f <= 4000)])
    haut = min(taux / 2 * 0.95, 16000)
    for i in np.where((f >= 3000) & (f < haut - 1000))[0][::max(1, int(50 / f[1]))]:
        if db[i] < reference - 30 and np.median(db[(f > f[i]) & (f < min(f[i] + 3000, haut))]) < reference - 45:
            return None if f[i] > 11000 else float(f[i])
    return None


def etendre_aigus(x, taux, limite, gains_db=(-12.0, -20.0, -28.0)):
    """Recrée les aigus qu'un micro limité a coupés (comme le « SBR » des codecs) : tout ce qui
    traîne au-dessus de la limite est retiré (souffle, sifflements), puis la moitié haute de la
    bande utile est recopiée deux fois au-dessus, de plus en plus faible. L'égalisation étalonnée
    règle ensuite le niveau final de ces aigus."""
    nfft = _taille_fft(len(x))
    X = np.fft.rfft(x, nfft)
    f = np.fft.rfftfreq(nfft, 1 / taux)
    coupure = limite - 100.0
    X = X / np.sqrt(1 + (f / coupure) ** 48)                    # coupe nette au-dessus de la limite
    largeur = coupure / 2
    decalage = int(round(largeur / f[1]))
    fondu = 250.0
    source = np.clip((f - largeur) / fondu, 0, 1) * np.clip((coupure - f) / fondu + 0.5, 0, 1)
    source = np.sin(source * np.pi / 2) ** 2                   # bords en cosinus : pas de trou ni de bosse
    Y = X.copy()
    for rang, gain_db in enumerate(gains_db, 1):
        d = decalage * rang
        if d >= len(X):
            break
        copie = np.zeros_like(X)
        copie[d:] = (X * source)[:len(X) - d]
        Y += copie * 10 ** (gain_db / 20)
    Y /= np.sqrt(1 + (f / min(taux / 2 * 0.95, 16500)) ** 24)   # rien au-delà de ce qu'avaient les originaux
    return np.fft.irfft(Y, nfft)[:len(x)].astype(np.float32)


def nettoyer(x, taux, force=0.6, marge_avant=0.10, marge_apres=0.22, aigus=True):
    """Prise du micro -> voix propre (mono) prête pour robotiser(), et un bilan :
        {"parole": durée parlée (s), "crete_db", "niveau_db" (parole), "bruit_db" (fond),
         "ecretage": la prise a saturé, "debut"/"fin" : zone parlée dans la prise d'origine}"""
    x = np.asarray(x, dtype=np.float32)
    if x.ndim == 2:
        x = x.mean(axis=1)
    bilan = {"parole": 0.0, "crete_db": -120.0, "niveau_db": -120.0, "bruit_db": -120.0,
             "ecretage": False, "debut": 0, "fin": len(x), "bande_hz": None}
    if len(x) < int(0.2 * taux):
        return np.zeros(0, dtype=np.float32), bilan
    crete = float(np.abs(x).max())
    bilan["crete_db"] = 20 * np.log10(crete + 1e-9)
    bilan["ecretage"] = int(np.sum(np.abs(x) > 0.985)) > 3
    x = _coupe_bas(x - x.mean(), taux, 70.0)
    bilan["bruit_db"] = float(np.percentile(_niveaux(x, taux), 10))
    zone = zone_parole(x, taux)
    if zone is None:
        return np.zeros(0, dtype=np.float32), bilan
    debut, fin = zone
    parole = x[debut:fin]
    bilan.update(parole=(fin - debut) / taux, debut=debut, fin=fin,
                 niveau_db=20 * np.log10(float(np.sqrt(np.mean(parole ** 2))) + 1e-9))
    if force > 0:
        x = _debruiter(x, taux, force)
    limite = bande_utile(x[debut:fin], taux) if aigus else None
    bilan["bande_hz"] = limite
    if limite:
        x = etendre_aigus(x, taux, limite)
    a = max(0, debut - int(marge_avant * taux))
    b = min(len(x), fin + int(marge_apres * taux))
    y = x[a:b].copy()
    fondu = min(len(y) // 4, int(0.015 * taux))
    if fondu:
        rampe = np.linspace(0, 1, fondu, dtype=np.float32)
        y[:fondu] *= rampe
        y[-fondu:] *= rampe[::-1]
    return y, bilan


# =====================================================================
#  ÉTALONNAGE : l'égalisation qui donne à une voix la courbe des enregistrements d'origine
# =====================================================================
def _spectre_moyen(x, taux):
    """(fréquences, puissance moyenne) d'un son, seulement là où l'on parle (tous canaux)."""
    x = np.asarray(x, dtype=np.float64)
    canaux = x.T if x.ndim == 2 else x[None, :]
    N = 1 << int(round(np.log2(taux * 0.17)))     # ~6 Hz de résolution : la bande de 100 Hz a ses cases
    H = N // 2
    if canaux.shape[1] < N:
        canaux = np.pad(canaux, ((0, 0), (0, N - canaux.shape[1])))
    fenetre = np.hanning(N)
    nb = 1 + (canaux.shape[1] - N) // H
    puissance = 0
    for c in canaux:
        trames = c[np.arange(N)[None, :] + H * np.arange(nb)[:, None]] * fenetre
        puissance = puissance + np.abs(np.fft.rfft(trames, axis=1)) ** 2
    energie = puissance.sum(axis=1)
    parle = energie > energie.max() * 10 ** (-30 / 10)
    return np.fft.rfftfreq(N, 1 / taux), puissance[parle].mean(axis=0)


def _bandes(f, puissance, taux):
    """dB par bande de CENTRES, 0 dB = moyenne des bandes de 317 Hz à 3,2 kHz ; NaN au-delà de taux."""
    niveaux = []
    for fc in CENTRES:
        dans = (f >= fc * 2 ** (-1 / 6)) & (f < fc * 2 ** (1 / 6))
        if fc * 2 ** (1 / 6) > taux / 2 * 0.98 or not dans.any():
            niveaux.append(np.nan)
        else:
            niveaux.append(10 * np.log10(puissance[dans].mean() + 1e-30))
    niveaux = np.array(niveaux)
    milieu = [i for i, fc in enumerate(CENTRES) if 300 <= fc <= 3300]
    return niveaux - np.nanmean(niveaux[milieu])


def spectre_bandes(x, taux):
    """Courbe moyenne d'une voix (dB par bande de CENTRES, 0 dB = moyenne de 317 Hz à 3,2 kHz),
    mesurée seulement là où l'on parle. Les bandes au-dessus de ce que permet taux valent NaN."""
    f, puissance = _spectre_moyen(x, taux)
    return _bandes(f, puissance, taux)


def _gains(f, points):
    """Gain (dB) de l'égalisation `points` à chaque fréquence f (même calcul que _egaliser)."""
    return np.interp(np.log(np.maximum(f, 1.0)), np.log([p[0] for p in points]), [p[1] for p in points])


def _points(gains, gain_min):
    points = [(40, float(max(gain_min, gains[0] - 6.0)))]
    points += [(fc, float(g)) for fc, g in zip(CENTRES, gains)]
    points.append((20000, float(max(gain_min, gains[-1] - 20.0))))
    return points


def etalonner(voix, e=None, gain_max=14.0, gain_min=-36.0, tours=12):
    """Égalisation propre à une voix : voix = [(échantillons mono nettoyés, taux), ...] (plusieurs
    phrases, 15 s au moins pour une courbe stable). Les phrases passent une fois dans la chaîne
    sans égalisation ; on cherche ensuite (par petites retouches, sur le spectre mesuré) les gains
    qui amènent chaque bande sur CIBLE_SPECTRE. Renvoie les points (Hz, dB) à donner à robotiser()."""
    reference, cumul, poids_total = None, None, 0.0
    for x, taux in voix:
        if len(x) < int(0.3 * taux):
            continue
        f, puissance = _spectre_moyen(robotiser(x, taux, e, EGALISATION_NEUTRE), taux)
        if reference is None:
            reference = (f, taux)
        elif taux != reference[1]:                # autre micro, autre fréquence : même grille
            puissance = np.interp(reference[0], f, puissance, right=0.0)
        milieu = (reference[0] >= 300) & (reference[0] <= 3300)
        poids = len(x) / taux
        part = puissance / (puissance[milieu].mean() + 1e-30) * poids    # chaque phrase compte selon sa durée
        cumul = part if cumul is None else cumul + part
        poids_total += poids
    if reference is None:
        return None
    f, taux = reference
    puissance = cumul / poids_total
    cible = np.array(CIBLE_SPECTRE)
    mesurable = np.isfinite(_bandes(f, puissance, taux))
    # au-dessus de 6 kHz, une voix a peu d'énergie : remonter beaucoup ne ferait monter que le souffle
    plafond = np.array([gain_max if fc <= 6000 else min(gain_max, 6.0) for fc in CENTRES])
    milieu = [i for i, fc in enumerate(CENTRES) if 400 <= fc <= 4100]
    gains = np.zeros(len(CENTRES))
    for _ in range(tours):
        niveaux = _bandes(f, puissance * 10 ** (_gains(f, _points(gains, gain_min)) / 10), taux)
        gains = gains + np.where(mesurable, cible - niveaux, 0.0)
        gains -= np.median(gains[milieu])
        gains = np.clip(gains, gain_min, plafond)
    # bandes impossibles à mesurer (fréquence d'échantillonnage trop basse) : comme la dernière mesurée
    if not mesurable.all():
        derniere = gains[mesurable][-1]
        gains = np.where(mesurable, gains, derniere)
    return tuple((fc, round(g, 1)) for fc, g in _points(gains, gain_min))


# =====================================================================
#  CIBLE (mesurée sur les 36 répliques d'origine, voir etalonner())
# =====================================================================
CIBLE_SPECTRE = (
    -22.0, -15.8, -15.7, -14.3, -1.9, 7.9, 12.7, 11.9, 6.1, 1.1, -0.9,     # 100 Hz à 1 kHz
    -2.0, -3.4, -9.2, -13.3, -11.0, -8.6, -12.5, -19.8, -23.5, -29.8,      # 1,26 kHz à 10 kHz
    -36.8, -49.4,                                                          # 12,7 et 16 kHz
)
