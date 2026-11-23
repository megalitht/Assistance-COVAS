/* =====================================================================
   COVAS — Hologramme du vaisseau
   Vue de dessus du vaisseau du commandant, nez en haut, dessinée en SVG.
   Chaque modèle a son plan dans vaisseaux/<symbole du journal>.js (chargé à la
   demande) : silhouette de la coque, lignes de structure, détails fins, profil
   de largeur. Tous les plans ont la même longueur normalisée (1000 unités).

   Utilisation :
       const holo = COVAS_HOLOGRAMMES.creer(conteneur, { zones, etiquettes });
       holo.afficher('anaconda');          // symbole "Ship" du journal
       holo.signalerZones(['armes']);      // modules touchés : voyants rouge/noir sur la coque
       holo.signalerImpact('coque');       // coup reçu : 'bouclier' | 'effondrement' | 'coque'

   Le bouclier est un bandeau de LED qui suit le contour du vaisseau et éclaire sa coque.
   Un coup fait passer au rouge la partie du bandeau la plus proche de l'impact.
   ===================================================================== */
window.COVAS_HOLOGRAMMES = (() => {
    'use strict';

    const SVG = 'http://www.w3.org/2000/svg';
    const LONGUEUR = 1000;              // nez en y = 0, poupe en y = 1000
    const DOSSIER = 'vaisseaux/';
    const DUREE_APPARITION = 1300;      // ms, balayage qui fait apparaître un nouveau vaisseau
    // Avaries (ms) : chaque nouveau coup relance l'effet depuis le début
    const DUREE_VOYANT_ZONE = 4000;     // repère d'un module touché : voyant rouge/noir
    const DUREE_VOYANT_COQUE = 1600;    // coup sur la coque sans savoir quel module : toute la silhouette
    const DUREE_EFFONDREMENT = 1300;    // boucliers qui tombent
    // Bouclier : il épouse la coque à cette distance, fixe à l'écran quel que soit le vaisseau
    const ECART_BOUCLIER_PX = 19;       // environ 5 mm (1 cm = 38 px sur un écran standard)
    const ECART_BOUCLIER_MAX = 0.03;    // ... sans dépasser cette part du petit côté de l'hologramme
    const FINESSE_BOUCLIER = 480;       // cases sur le grand côté pour calculer le contour
    // Bandeau de LED du bouclier
    const PAS_LED_PX = 8;               // distance entre deux LED
    const IMAGES_REPOS = 24;            // images par seconde au repos (le jeu tourne à côté)
    const IMAGES_EFFET = 60;            // ... pendant un impact ou un allumage
    const DUREE_ROUGE = 1900;           // ms : une zone touchée reste rouge, puis repasse au bleu
    const MAINTIEN_ROUGE = 450;         // ms à pleine intensité avant le retour au bleu
    const LARGEUR_IMPACT_PX = 120;      // étendue de la zone rouge de part et d'autre de l'impact
    const DUREE_BASCULE = 1000;         // ms : les LED s'allument ou s'éteignent en vague
    const IMPACTS_MAX = 10;
    const RAFALE = 1800;                // ms : des coups rapprochés restent du même côté du vaisseau
    const REDUCTION_LUMIERE = 0.4;      // la lumière projetée est douce : calculée en plus petit
    const LED_BLEU = [159, 220, 255];
    const LED_ROUGE = [255, 44, 22];

    // Symbole du journal -> [nom, constructeur, longueur, largeur, hauteur (m), plateforme]
    const CATALOGUE = {
        sidewinder: ['Sidewinder', 'Faulcon DeLacy', 14.9, 21.3, 5.4, 'S'],
        eagle: ['Eagle', 'Core Dynamics', 31.2, 29.7, 7.1, 'S'],
        hauler: ['Hauler', 'Zorgon Peterson', 28.6, 26.2, 10.4, 'S'],
        adder: ['Adder', 'Zorgon Peterson', 31.5, 28.8, 9.6, 'S'],
        empire_eagle: ['Imperial Eagle', 'Gutamaya', 31.2, 34.7, 7.1, 'S'],
        viper: ['Viper Mk III', 'Faulcon DeLacy', 29.8, 24.0, 8.6, 'S'],
        cobramkiii: ['Cobra Mk III', 'Faulcon DeLacy', 27.1, 44.0, 7.9, 'S'],
        viper_mkiv: ['Viper Mk IV', 'Faulcon DeLacy', 29.9, 24.7, 8.7, 'S'],
        diamondback: ['Diamondback Scout', 'Lakon Spaceways', 39.0, 24.3, 12.3, 'S'],
        cobramkiv: ['Cobra Mk IV', 'Faulcon DeLacy', 33.1, 48.1, 8.6, 'S'],
        cobramkv: ['Cobra Mk V', 'Faulcon DeLacy', 41.2, 55.1, 9.5, 'S'],
        type6: ['Type-6 Transporter', 'Lakon Spaceways', 48.4, 27.2, 15.0, 'M'],
        dolphin: ['Dolphin', 'Saud Kruger', 51.8, 20.8, 8.8, 'S'],
        diamondbackxl: ['Diamondback Explorer', 'Lakon Spaceways', 45.0, 27.3, 13.6, 'S'],
        empire_courier: ['Imperial Courier', 'Gutamaya', 42.1, 27.4, 7.1, 'S'],
        independant_trader: ['Keelback', 'Lakon Spaceways', 49.7, 40.3, 14.9, 'M'],
        asp_scout: ['Asp Scout', 'Lakon Spaceways', 54.8, 59.4, 17.0, 'M'],
        vulture: ['Vulture', 'Core Dynamics', 43.1, 34.7, 12.3, 'S'],
        asp: ['Asp Explorer', 'Lakon Spaceways', 56.5, 51.3, 19.7, 'M'],
        federation_dropship: ['Federal Dropship', 'Core Dynamics', 73.9, 52.3, 21.7, 'M'],
        type7: ['Type-7 Transporter', 'Lakon Spaceways', 81.6, 56.1, 25.4, 'L'],
        type8: ['Type-8 Transporter', 'Lakon Spaceways', 99.3, 60.0, 25.6, 'M'],
        typex: ['Alliance Chieftain', 'Lakon Spaceways', 68.1, 58.5, 19.9, 'M'],
        federation_dropship_mkii: ['Federal Assault Ship', 'Core Dynamics', 73.8, 49.5, 22.8, 'M'],
        empire_trader: ['Imperial Clipper', 'Gutamaya', 106.7, 103.7, 24.8, 'L'],
        typex_2: ['Alliance Crusader', 'Lakon Spaceways', 68.1, 58.5, 19.8, 'M'],
        typex_3: ['Alliance Challenger', 'Lakon Spaceways', 68.4, 48.4, 19.7, 'M'],
        federation_gunship: ['Federal Gunship', 'Core Dynamics', 75.5, 53.3, 22.5, 'M'],
        krait_light: ['Krait Phantom', 'Faulcon DeLacy', 73.3, 72.0, 14.6, 'M'],
        krait_mkii: ['Krait Mk II', 'Faulcon DeLacy', 73.3, 72.0, 13.5, 'M'],
        mandalay: ['Mandalay', 'Zorgon Peterson', 49.6, 74.4, 14.9, 'M'],
        ferdelance: ['Fer-de-Lance', 'Zorgon Peterson', 73.6, 51.6, 15.4, 'M'],
        mamba: ['Mamba', 'Zorgon Peterson', 72.2, 50.1, 11.4, 'M'],
        python: ['Python', 'Faulcon DeLacy', 87.9, 58.1, 18.0, 'M'],
        python_nx: ['Python Mk II', 'Faulcon DeLacy', 88.4, 67.5, 17.3, 'M'],
        corsair: ['Corsair', 'Gutamaya', 86.8, 69.4, 16.0, 'M'],
        lakonminer: ['Type-11 Prospector', 'Lakon Spaceways', 78.6, 78.3, 28.7, 'M'],
        mediumtransport01: ['Lynx Highliner', 'Zorgon Peterson', 89.3, 45.2, 18.8, 'M'],
        smallcombat01_nx: ['Kestrel Mk II', 'Core Dynamics', 49.4, 40.0, 9.1, 'S'],
        type9: ['Type-9 Heavy', 'Lakon Spaceways', 117.4, 115.3, 33.2, 'L'],
        belugaliner: ['Beluga Liner', 'Saud Kruger', 209.1, 131.6, 38.6, 'L'],
        orca: ['Orca', 'Saud Kruger', 130.4, 50.8, 22.7, 'L'],
        type9_military: ['Type-10 Defender', 'Lakon Spaceways', 118.4, 135.1, 39.3, 'L'],
        anaconda: ['Anaconda', 'Faulcon DeLacy', 155.0, 62.0, 32.0, 'L'],
        anacondamkii: ['Anaconda Mk II', 'Faulcon DeLacy', 167.9, 74.2, 27.3, 'L'],
        federation_corvette: ['Federal Corvette', 'Core Dynamics', 167.8, 87.2, 28.3, 'L'],
        cutter: ['Imperial Cutter', 'Gutamaya', 192.6, 111.1, 33.4, 'L'],
        panthermkii: ['Panther Clipper Mk II', 'Zorgon Peterson', 146.9, 117.1, 33.8, 'L'],
        explorer_nx: ['Caspian Explorer', 'Zorgon Peterson', 126.7, 104.5, 27.6, 'L'],
    };

    // Auteurs des plans (champ "source" des fichiers vaisseaux/*.js)
    const SOURCES = {
        arithon: 'Plan : schéma de CMDR Arithon (EDAssets)',
        frontier: 'Plan : vue orthographique officielle Frontier',
        covas: 'Plan : reconstitution COVAS d\'après les visuels officiels',
        capture: 'Plan : tiré d\'une capture du jeu, vue de dessus (atelier.html)',
        rendu: 'Plan : détouré d\'un rendu officiel de Frontier vu de dessus',
        blueprint: 'Plan : détouré des « Ship Blueprints » d\'elite-dangerous-blog.co.uk',
    };

    // Où poser les repères de modules, en fraction de la longueur (y)
    // et de la demi-largeur locale de la coque (x). Un plan peut les ajuster (plan.zones).
    const GEOMETRIE_ZONES = {
        capteurs: { y: 0.05, x: 0 },
        verriere: { y: 0.16, x: 0 },
        armes: { y: 0.3, x: 0.55, miroir: true },
        noyau: { y: 0.46, x: 0 },
        utilitaires: { y: 0.52, x: 0.78, miroir: true },
        internes: { y: 0.6, x: 0 },
        soute: { y: 0.72, x: 0 },
        fsd: { y: 0.84, x: 0 },
        moteurs: { y: 0.95, x: 0.42, miroir: true },
    };

    // Silhouette de secours : vaisseau inconnu ou plan absent
    const GENERIQUE = {
        id: 'generique', nom: 'Vaisseau', source: 'covas', largeur: 600.8,
        coque: 'M0 0l51.4 122.5 39.5 158.1 31.6 229.3 162.1 209.5 15.8 106.7-146.2 35.6-27.7 102.7-253 0-27.7-102.7-146.2-35.6 15.8-106.7 162.1-209.5 31.6-229.3 39.5-158.1z',
        traits: 'M0 138.3l33.6 110.7-33.6 59.3-33.6-59.3 33.6-110.7M0 0l0 138.3M0 308.3l0 656.1M-90.9 280.6l181.8 0M-122.5 509.9l245 0M-154.2 861.7l308.4 0M-122.5 509.9l-31.7 351.8M122.5 509.9l31.7 351.8M-284.6 719.4l130.4 43.4M284.6 719.4l-130.4 43.4M-51.4 122.5l102.8 0M-106.7 964.4l0 35.6 79 0 0-35.6M27.7 964.4l0 35.6 79 0 0-35.6',
        details: '',
    };

    const plans = Object.create(null);
    const attentes = Object.create(null);
    plans.generique = GENERIQUE;

    // ----------------------------------------------------------------
    //  PLANS
    // ----------------------------------------------------------------
    function normaliser(type) {
        return String(type || '').trim().toLowerCase();
    }

    /** Vrai pour une combinaison, un VRS ou un chasseur : le vaisseau affiché ne change pas. */
    function horsVaisseau(type) {
        return /suit|testbuggy|srv|buggy|fighter|_nx_fighter|empire_fighter|federation_fighter|independent_fighter/.test(normaliser(type));
    }

    function connu(type) {
        return normaliser(type) in CATALOGUE;
    }

    function nom(type, repli) {
        const fiche = CATALOGUE[normaliser(type)];
        return fiche ? fiche[0] : (repli || type || '');
    }

    function enregistrer(plan) {
        if (!plan || !plan.id) return;
        plans[plan.id] = plan;
        const attente = attentes[plan.id];
        if (attente) attente.resoudre(plan);
    }

    /** Charge vaisseaux/<id>.js (une balise script : fonctionne aussi en file://). */
    function charger(id) {
        if (plans[id]) return Promise.resolve(plans[id]);
        if (attentes[id]) return attentes[id].promesse;
        const attente = {};
        attente.promesse = new Promise((resoudre, rejeter) => { attente.resoudre = resoudre; attente.rejeter = rejeter; });
        attentes[id] = attente;
        const script = document.createElement('script');
        script.src = DOSSIER + encodeURIComponent(id) + '.js';
        script.async = true;
        const echec = raison => {
            delete attentes[id];
            attente.rejeter(new Error(raison));
        };
        script.onload = () => { script.remove(); if (!plans[id]) echec('plan invalide : ' + id); else delete attentes[id]; };
        script.onerror = () => { script.remove(); echec('plan absent : ' + id); };
        document.head.append(script);
        return attente.promesse;
    }

    // ----------------------------------------------------------------
    //  OUTILS SVG
    // ----------------------------------------------------------------
    function creerSvg(balise, attributs = {}, parent = null) {
        const el = document.createElementNS(SVG, balise);
        for (const [cle, valeur] of Object.entries(attributs)) el.setAttribute(cle, valeur);
        if (parent) parent.append(el);
        return el;
    }

    function poser(el, attributs) {
        for (const [cle, valeur] of Object.entries(attributs)) el.setAttribute(cle, valeur);
    }

    const arrondi = v => Math.round(v * 10) / 10;
    const metres = v => (v >= 100 ? Math.round(v) : Math.round(v * 10) / 10).toLocaleString('fr-FR') + ' m';

    /** [min, max] de la coque à la hauteur y, d'après le profil du plan. */
    function largeurA(plan, y) {
        const profil = plan.profil;
        if (!profil || !profil.min || profil.min.length < 2) return [-plan.largeur / 2, plan.largeur / 2];
        const n = profil.min.length - 1;
        const t = Math.max(0, Math.min(n, (y / LONGUEUR) * n));
        const i = Math.min(n - 1, Math.floor(t));
        const f = t - i;
        return [profil.min[i] + (profil.min[i + 1] - profil.min[i]) * f, profil.max[i] + (profil.max[i + 1] - profil.max[i]) * f];
    }

    /** Pas de la grille métrique : environ 8 à 16 cases sur la longueur du vaisseau. */
    function pasGrille(longueurMetres) {
        for (const pas of [2, 5, 10, 20, 25, 50]) if (longueurMetres / pas <= 16) return pas;
        return 100;
    }

    // ----------------------------------------------------------------
    //  CONTOUR DU BOUCLIER
    //  La coque, épaissie de `ecart` dans toutes les directions, est dessinée sur une petite
    //  toile ; on en relève le bord extérieur. Les creux plus étroits que le bouclier
    //  (entre deux nacelles, par exemple) se referment, comme sur une vraie bulle d'énergie.
    // ----------------------------------------------------------------
    // Bords d'une case : 0 haut, 1 droite, 2 bas, 3 gauche. Pour chaque combinaison de coins
    // pleins (1 haut-gauche, 2 haut-droite, 4 bas-droite, 8 bas-gauche) : [bord d'entrée, de sortie]
    const SEGMENTS = [[], [[3, 0]], [[0, 1]], [[3, 1]], [[1, 2]], [[3, 0], [1, 2]], [[0, 2]], [[3, 2]],
        [[2, 3]], [[2, 0]], [[0, 1], [2, 3]], [[2, 1]], [[1, 3]], [[1, 0]], [[0, 3]], []];
    const SEUIL_CONTOUR = 128;

    /** Plus grande boucle du bord de la forme, en coordonnées de la toile. */
    function bordExterieur(alpha, w, h) {
        const valeur = (x, y) => alpha[(y * w + x) * 4 + 3];
        const bord = (x, y, cote) => (cote === 0 ? 2 * (y * w + x) : cote === 2 ? 2 * ((y + 1) * w + x)
            : cote === 3 ? 2 * (y * w + x) + 1 : 2 * (y * w + x + 1) + 1);
        const suivants = new Map();
        for (let y = 0; y < h - 1; y++) {
            for (let x = 0; x < w - 1; x++) {
                const cas = (valeur(x, y) >= SEUIL_CONTOUR ? 1 : 0) | (valeur(x + 1, y) >= SEUIL_CONTOUR ? 2 : 0)
                    | (valeur(x + 1, y + 1) >= SEUIL_CONTOUR ? 4 : 0) | (valeur(x, y + 1) >= SEUIL_CONTOUR ? 8 : 0);
                for (const [entree, sortie] of SEGMENTS[cas]) suivants.set(bord(x, y, entree), bord(x, y, sortie));
            }
        }
        // Position du bord entre ses deux pixels, d'après leur opacité : un tracé sans escalier
        const point = id => {
            const vertical = id % 2 === 1, indice = Math.floor(id / 2);
            const x = indice % w, y = Math.floor(indice / w);
            const a = valeur(x, y), b = vertical ? valeur(x, y + 1) : valeur(x + 1, y);
            const t = a === b ? 0.5 : (SEUIL_CONTOUR - a) / (b - a);
            return vertical ? [x + 0.5, y + 0.5 + t] : [x + 0.5 + t, y + 0.5];
        };
        const vus = new Set();
        let meilleure = null, aireMax = 0;
        for (const depart of suivants.keys()) {
            if (vus.has(depart)) continue;
            const boucle = [];
            let id = depart;
            while (id !== undefined && !vus.has(id)) {
                vus.add(id);
                boucle.push(point(id));
                id = suivants.get(id);
            }
            let aire = 0;
            boucle.forEach(([x, y], i) => {
                const [xs, ys] = boucle[(i + 1) % boucle.length];
                aire += x * ys - xs * y;
            });
            if (Math.abs(aire) > aireMax) { aireMax = Math.abs(aire); meilleure = boucle; }
        }
        return meilleure || [];
    }

    /** Retire les points inutiles d'une ligne (Douglas-Peucker). */
    function simplifier(points, tolerance) {
        const garder = new Uint8Array(points.length);
        garder[0] = garder[points.length - 1] = 1;
        const pile = [[0, points.length - 1]];
        while (pile.length) {
            const [debut, fin] = pile.pop();
            const [ax, ay] = points[debut], [bx, by] = points[fin];
            const dx = bx - ax, dy = by - ay, carre = dx * dx + dy * dy;
            let pire = -1, ecartMax = tolerance * tolerance;
            for (let i = debut + 1; i < fin; i++) {
                const [px, py] = points[i];
                const t = carre ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / carre)) : 0;
                const ex = px - ax - t * dx, ey = py - ay - t * dy, d = ex * ex + ey * ey;
                if (d > ecartMax) { ecartMax = d; pire = i; }
            }
            if (pire >= 0) {
                garder[pire] = 1;
                pile.push([debut, pire], [pire, fin]);
            }
        }
        return points.filter((_, i) => garder[i]);
    }

    const contours = new WeakMap();     // plan -> (écart -> forme) : un plan remplacé repart de zéro
    const FORME_VIDE = { trace: '', points: [] };

    /** Forme du bouclier : la coque du plan, décalée de `ecart` unités vers l'extérieur.
        trace : chemin SVG ; points : le même contour en unités du plan. */
    function formeBouclier(plan, ecart) {
        const cle = Math.round(ecart / 2) * 2;      // un redimensionnement fin ne relance pas le calcul
        let parEcart = contours.get(plan);
        if (!parEcart) contours.set(plan, parEcart = new Map());
        if (parEcart.has(cle)) return parEcart.get(cle);

        const reserve = cle + 0.04 * Math.max(plan.largeur, LONGUEUR);
        const x0 = -plan.largeur / 2 - reserve, y0 = -reserve;
        const largeur = plan.largeur + 2 * reserve, hauteur = LONGUEUR + 2 * reserve;
        const k = FINESSE_BOUCLIER / Math.max(largeur, hauteur);
        const toile = document.createElement('canvas');
        toile.width = Math.ceil(largeur * k);
        toile.height = Math.ceil(hauteur * k);
        const c = toile.getContext('2d', { willReadFrequently: true });
        if (!c) return FORME_VIDE;
        c.setTransform(k, 0, 0, k, -x0 * k, -y0 * k);
        const coque = new Path2D(plan.coque);
        c.lineJoin = c.lineCap = 'round';
        c.lineWidth = cle * 2;
        c.fill(coque);
        c.stroke(coque);
        const boucle = bordExterieur(c.getImageData(0, 0, toile.width, toile.height).data, toile.width, toile.height);
        if (boucle.length < 3) return FORME_VIDE;

        // La boucle est coupée en son point le plus éloigné du départ pour la simplifier en deux moitiés
        let loin = 0, distanceMax = -1;
        boucle.forEach(([x, y], i) => {
            const d = (x - boucle[0][0]) ** 2 + (y - boucle[0][1]) ** 2;
            if (d > distanceMax) { distanceMax = d; loin = i; }
        });
        const points = [...simplifier(boucle.slice(0, loin + 1), 0.3).slice(0, -1), ...simplifier([...boucle.slice(loin), boucle[0]], 0.3).slice(0, -1)]
            .map(([x, y]) => [arrondi(x0 + x / k), arrondi(y0 + y / k)]);
        const forme = { trace: 'M' + points.map(([x, y]) => `${x} ${y}`).join('L') + 'Z', points };
        if (parEcart.size >= 6) parEcart.delete(parEcart.keys().next().value);
        parEcart.set(cle, forme);
        return forme;
    }

    const contourBouclier = (plan, ecart) => formeBouclier(plan, ecart).trace;

    // ----------------------------------------------------------------
    //  BANDEAU DE LED DU BOUCLIER
    //  Une toile entre le plan et les effets : le plan détaillé n'est jamais repeint.
    //  La lumière bleue projetée sur la coque est calculée une fois par vaisseau et par taille ;
    //  seules les LED et la zone rouge d'un impact sont redessinées.
    // ----------------------------------------------------------------
    function toileVide(l, h) {
        const toile = document.createElement('canvas');
        toile.width = Math.max(1, Math.ceil(l));
        toile.height = Math.max(1, Math.ceil(h));
        return toile;
    }

    /** Point lumineux prêt à copier : cœur blanc, teinte de la LED, halo qui s'estompe. */
    function spriteLed([r, v, b], rayon) {
        const toile = toileVide(rayon * 2, rayon * 2);
        const c = toile.getContext('2d');
        const degrade = c.createRadialGradient(rayon, rayon, 0, rayon, rayon, rayon);
        degrade.addColorStop(0, 'rgba(255, 255, 255, 1)');
        degrade.addColorStop(0.14, `rgba(${r}, ${v}, ${b}, 1)`);
        degrade.addColorStop(0.32, `rgba(${r}, ${v}, ${b}, 0.34)`);
        degrade.addColorStop(1, `rgba(${r}, ${v}, ${b}, 0)`);
        c.fillStyle = degrade;
        c.fillRect(0, 0, rayon * 2, rayon * 2);
        return toile;
    }

    /** Tache de lumière projetée par une LED sur la coque. */
    function spriteLumiere([r, v, b], rayon) {
        const toile = toileVide(rayon * 2, rayon * 2);
        const c = toile.getContext('2d');
        const degrade = c.createRadialGradient(rayon, rayon, 0, rayon, rayon, rayon);
        degrade.addColorStop(0, `rgba(${r}, ${v}, ${b}, 1)`);
        degrade.addColorStop(0.5, `rgba(${r}, ${v}, ${b}, 0.3)`);
        degrade.addColorStop(1, `rgba(${r}, ${v}, ${b}, 0)`);
        c.fillStyle = degrade;
        c.fillRect(0, 0, rayon * 2, rayon * 2);
        return toile;
    }

    const SPRITES_LED = {};
    const spritesLed = rayon => (SPRITES_LED[rayon] ??= {
        bleu: spriteLed(LED_BLEU, rayon), rouge: spriteLed(LED_ROUGE, rayon),
    });

    class BandeauLed {
        constructor(hote) {
            this.hote = hote;
            this.toile = document.createElement('canvas');
            this.toile.className = 'holo-led';
            this.toile.setAttribute('aria-hidden', 'true');
            hote.calques[2].before(this.toile);
            this.c = this.toile.getContext('2d');
            this.n = 0;
            this.geo = null;
            this.aConstruire = false;
            this.impacts = [];
            this.transition = null;
            this.enLigne = hote.conteneur.dataset.boucliers !== 'non';
            this.dernierImpact = -Infinity;
            this.positionRafale = 0;
            this.origineChute = null;
            this.image = 0;
            this.attente = 0;
            this.demande = 0;
            this.tourner = this.tourner.bind(this);
            new MutationObserver(() => this.suivreEtat()).observe(hote.conteneur, { attributes: true, attributeFilter: ['data-boucliers'] });
        }

        placer(plan, points, vue, u, ecartPx) {
            const g = this.geo;
            if (g && g.plan === plan && g.points === points && g.u === u && g.vue.x === vue.x && g.vue.y === vue.y
                && g.vue.l === vue.l && g.vue.h === vue.h) return;
            this.geo = { plan, points, vue: { ...vue }, u, ecartPx };
            this.aConstruire = true;
            this.toile.hidden = false;
            this.reveiller();
        }

        masquer() {
            this.geo = null;
            this.n = 0;
            this.toile.hidden = true;
        }

        /** Répartit les LED à distance égale sur le contour et prépare la lumière projetée. */
        construire() {
            const { plan, points, vue, u, ecartPx } = this.geo;
            const lp = this.toile.clientWidth, hp = this.toile.clientHeight;
            if (lp < 10 || hp < 10) return false;
            const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
            const L = this.toile.width = Math.round(lp * dpr);
            const H = this.toile.height = Math.round(hp * dpr);
            const k = this.k = dpr / u;
            this.vue = vue;

            const longueurs = [];
            let perimetre = 0;
            points.forEach(([x, y], i) => {
                const [xs, ys] = points[(i + 1) % points.length];
                const d = Math.hypot(xs - x, ys - y);
                longueurs.push(d);
                perimetre += d;
            });
            const n = this.n = Math.max(24, Math.round(perimetre / (PAS_LED_PX * u)));
            this.perimetrePx = perimetre / u;
            const X = this.X = new Float32Array(n), Y = this.Y = new Float32Array(n);
            this.allumees = new Float32Array(n);
            this.rouges = new Float32Array(n);
            let segment = 0, debut = 0;
            for (let i = 0; i < n; i++) {
                const s = (i / n) * perimetre;
                while (segment < points.length - 1 && s > debut + longueurs[segment]) debut += longueurs[segment++];
                const [ax, ay] = points[segment], [bx, by] = points[(segment + 1) % points.length];
                const t = longueurs[segment] ? (s - debut) / longueurs[segment] : 0;
                X[i] = (ax + (bx - ax) * t - vue.x) * k;
                Y[i] = (ay + (by - ay) * t - vue.y) * k;
            }
            let nez = 0;
            for (let i = 1; i < n; i++) if (Y[i] < Y[nez]) nez = i;
            this.positionNez = nez / n;

            // Ce que la lumière peut éclairer : la coque, et surtout ses lignes
            const R = REDUCTION_LUMIERE, lr = L * R, hr = H * R;
            const masque = this.masque = toileVide(lr, hr);
            const m = masque.getContext('2d');
            m.setTransform(k * R, 0, 0, k * R, -vue.x * k * R, -vue.y * k * R);
            const coque = new Path2D(plan.coque);
            m.fillStyle = 'rgba(255, 255, 255, 0.2)';
            m.fill(coque);
            m.lineJoin = m.lineCap = 'round';
            m.strokeStyle = 'rgba(255, 255, 255, 0.62)';
            m.lineWidth = 1.1 / (k * R);
            if (plan.traits) m.stroke(new Path2D(plan.traits));
            m.strokeStyle = '#fff';
            m.lineWidth = 2.2 / (k * R);
            m.stroke(coque);

            this.rayonLumiere = Math.max(10, Math.ceil(Math.max(ecartPx, 34) * 2.15 * dpr * R));
            this.tacheRouge = spriteLumiere(LED_ROUGE, this.rayonLumiere);
            const bleue = this.lumiereBleue = toileVide(lr, hr);
            this.projeter(bleue.getContext('2d'), spriteLumiere(LED_BLEU, this.rayonLumiere), () => 0.05);
            this.lumiereRouge = toileVide(lr, hr);
            this.cRouge = this.lumiereRouge.getContext('2d');
            this.rayonSprite = Math.max(6, Math.round(10 * dpr));
            this.sprites = spritesLed(this.rayonSprite);
            return true;
        }

        /** Dessine la lumière de chaque LED, puis ne garde que ce qui tombe sur le vaisseau. */
        projeter(c, tache, intensite) {
            const R = REDUCTION_LUMIERE, rayon = this.rayonLumiere;
            c.globalCompositeOperation = 'source-over';
            c.globalAlpha = 1;
            c.clearRect(0, 0, c.canvas.width, c.canvas.height);
            c.globalCompositeOperation = 'lighter';
            for (let i = 0; i < this.n; i++) {
                const a = intensite(i);
                if (a < 0.002) continue;
                c.globalAlpha = a;
                c.drawImage(tache, this.X[i] * R - rayon, this.Y[i] * R - rayon);
            }
            c.globalCompositeOperation = 'destination-in';
            c.globalAlpha = 1;
            c.drawImage(this.masque, 0, 0);
        }

        // --- Évènements ---------------------------------------------------
        suivreEtat() {
            const voulu = this.hote.conteneur.dataset.boucliers !== 'non';
            if (voulu === this.enLigne) return;
            this.enLigne = voulu;
            this.transition = {
                debut: performance.now(), allumage: voulu,
                origine: voulu ? null : this.origineChute,       // null : depuis le nez du vaisseau
            };
            this.origineChute = null;
            this.reveiller();
        }

        /** Nouveau vaisseau à l'écran : les LED s'allument depuis le nez. */
        allumer() {
            if (!this.enLigne) return;
            this.transition = { debut: performance.now(), allumage: true, origine: null };
            this.reveiller();
        }

        /** Point du bandeau pour un coup sur le bouclier : une rafale reste du même côté. */
        pointImpact() {
            if (this.aConstruire && this.geo) this.aConstruire = !this.construire();
            if (!this.n) return null;
            const t = performance.now();
            const position = t - this.dernierImpact < RAFALE
                ? (this.positionRafale + (Math.random() - 0.5) * 0.05 + 1) % 1 : Math.random();
            this.dernierImpact = t;
            this.positionRafale = position;
            const i = Math.min(this.n - 1, Math.floor(position * this.n));
            return { x: this.X[i] / this.k + this.vue.x, y: this.Y[i] / this.k + this.vue.y };
        }

        /** Fait passer au rouge la partie du bandeau la plus proche de `point` (unités du plan). */
        toucher(type, point) {
            if (this.aConstruire && this.geo) this.aConstruire = !this.construire();
            if (!this.n || !point) return;
            const px = (point.x - this.vue.x) * this.k, py = (point.y - this.vue.y) * this.k;
            let proche = 0, mini = Infinity;
            for (let i = 0; i < this.n; i++) {
                const d = (this.X[i] - px) ** 2 + (this.Y[i] - py) ** 2;
                if (d < mini) { mini = d; proche = i; }
            }
            const position = proche / this.n;
            const largeur = (type === 'effondrement' ? 2.4 : 1) * LARGEUR_IMPACT_PX / this.perimetrePx;
            this.impacts.push({ position, largeur, debut: performance.now() });
            if (this.impacts.length > IMPACTS_MAX) this.impacts.shift();
            if (type === 'effondrement') {
                this.origineChute = position;
                const tr = this.transition;
                if (tr && !tr.allumage && performance.now() - tr.debut < 300) tr.origine = position;
            }
            this.reveiller();
        }

        // --- Animation ----------------------------------------------------
        reveiller() {
            clearTimeout(this.attente);
            this.attente = 0;
            if (!this.demande) this.demande = requestAnimationFrame(this.tourner);
        }

        visible() {
            if (document.hidden) return false;
            return this.toile.checkVisibility ? this.toile.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })
                : !!this.toile.offsetParent;
        }

        tourner(t) {
            this.demande = 0;
            if (!this.geo) return;
            if (!this.visible()) {                       // vue cachée : rien à dessiner
                this.attente = setTimeout(() => this.reveiller(), 400);
                return;
            }
            if (this.aConstruire) {
                this.aConstruire = !this.construire();
                this.image = 0;
                if (this.aConstruire) { this.attente = setTimeout(() => this.reveiller(), 200); return; }
            }
            if (!this.n) return;
            const effet = this.impacts.length > 0 || !!this.transition;
            const intervalle = 1000 / (effet ? IMAGES_EFFET : IMAGES_REPOS);
            let dessine = false;
            if (t - this.image >= intervalle - 2) {
                this.image = t;
                const maintenant = performance.now();
                this.calculer(maintenant);
                this.dessiner(maintenant);
                dessine = true;
            }
            // Hors ligne et sans effet : l'image ne change plus, on attend le prochain évènement
            if (!dessine || this.enLigne || this.impacts.length || this.transition) this.demande = requestAnimationFrame(this.tourner);
        }

        calculer(t) {
            const { n, allumees, rouges } = this;
            this.impacts = this.impacts.filter(impact => t - impact.debut < DUREE_ROUGE);
            const tr = this.transition;
            let front = 0;
            if (tr) {
                const p = (t - tr.debut) / DUREE_BASCULE;
                if (p >= 1) this.transition = null;
                else front = p * 0.58;
            }
            const enCours = this.transition;
            const origine = enCours ? (enCours.origine ?? this.positionNez) : 0;
            const forces = this.impacts.map(({ debut }) => {
                const age = t - debut;
                if (age < 60) return age / 60;
                if (age < MAINTIEN_ROUGE) return 1;
                return (1 - (age - MAINTIEN_ROUGE) / (DUREE_ROUGE - MAINTIEN_ROUGE)) ** 2;
            });
            const largeurs = this.impacts.map(({ debut, largeur }) => largeur * (0.3 + 0.7 * (1 - Math.exp(-(t - debut) / 90))));
            let somme = 0;
            for (let i = 0; i < n; i++) {
                const pos = i / n;
                let rouge = 0, allume = this.enLigne ? 1 : 0;
                if (enCours) {
                    let d = Math.abs(pos - origine);
                    d = Math.min(d, 1 - d);
                    const passe = Math.max(0, Math.min(1, (front - d) / 0.05));
                    allume = enCours.allumage ? passe : 1 - passe;
                    if (!enCours.allumage) rouge = Math.exp(-(((front - d) / 0.035) ** 2));
                }
                for (let j = 0; j < this.impacts.length; j++) {
                    let d = Math.abs(pos - this.impacts[j].position);
                    d = Math.min(d, 1 - d) / largeurs[j];
                    if (d < 3) rouge = Math.max(rouge, forces[j] * Math.exp(-d * d));
                }
                allumees[i] = allume;
                rouges[i] = rouge;
                somme += allume;
            }
            this.moyenneAllumees = n ? somme / n : 0;
        }

        dessiner(t) {
            const { c, n, X, Y, allumees, rouges, sprites, rayonSprite: rs } = this;
            const L = this.toile.width, H = this.toile.height;
            c.setTransform(1, 0, 0, 1, 0, 0);
            c.globalCompositeOperation = 'source-over';
            c.globalAlpha = 1;
            c.clearRect(0, 0, L, H);
            c.globalCompositeOperation = 'lighter';

            // Lumière projetée sur la coque
            if (this.moyenneAllumees > 0.01) {
                c.globalAlpha = this.moyenneAllumees * (0.86 + 0.14 * Math.sin(t / 1900));
                c.drawImage(this.lumiereBleue, 0, 0, L, H);
            }
            let rougeActif = false;
            for (let i = 0; i < n && !rougeActif; i++) rougeActif = rouges[i] > 0.03;
            if (rougeActif) {
                this.projeter(this.cRouge, this.tacheRouge, i => (rouges[i] > 0.03 ? rouges[i] * 0.3 : 0));
                c.globalAlpha = 1;
                c.drawImage(this.lumiereRouge, 0, 0, L, H);
            }

            // Les LED : une vague lumineuse lente parcourt le bandeau
            const phase = t / 5200;
            for (let i = 0; i < n; i++) {
                const rouge = rouges[i], allume = allumees[i] * (1 - rouge);
                if (allume > 0.02) {
                    const vague = 0.5 + 0.5 * Math.cos(2 * Math.PI * (3 * i / n - phase));
                    c.globalAlpha = allume * (0.5 + 0.5 * vague * vague);
                    c.drawImage(sprites.bleu, X[i] - rs, Y[i] - rs);
                }
                const veille = (1 - allumees[i]) * (1 - rouge) * 0.2;      // bouclier hors ligne : LED rouges très faibles
                const a = Math.max(rouge, veille);
                if (a > 0.02) {
                    c.globalAlpha = a;
                    c.drawImage(sprites.rouge, X[i] - rs, Y[i] - rs);
                }
            }
        }
    }

    // ----------------------------------------------------------------
    //  HOLOGRAMME
    // ----------------------------------------------------------------
    let compteur = 0;

    class Hologramme {
        /**
         * @param {HTMLElement} conteneur
         * @param {{zones?: {cle: string, nom: string}[], etiquettes?: boolean, legende?: boolean,
         *          cotes?: boolean, grille?: boolean, animation?: boolean}} options
         */
        constructor(conteneur, options = {}) {
            this.conteneur = conteneur;
            this.n = ++compteur;
            this.zones = options.zones || [];
            this.etiquettes = !!options.etiquettes;
            this.avecLegende = options.legende !== false;
            this.avecCotes = options.cotes !== false;
            this.avecGrille = options.grille !== false;
            this.animation = options.animation !== false;
            this.plan = null;
            this.id = null;
            this.demande = null;
            this.uParPx = 1;
            this.minuteries = new Map();      // élément -> (classe -> minuterie) des effets en cours
            this.led = null;                  // bandeau de LED, créé si cet hologramme montre le bouclier
            this.construire();
            this.observateur = new ResizeObserver(() => this.mettreEnPage());
            this.observateur.observe(conteneur);
        }

        /*  Trois calques SVG superposés, au même viewBox :
              fond   : grille métrique, lumière du projecteur, bouclier (animé)
              plan   : la coque et ses milliers de traits, statique (peint une seule fois)
              (toile : le bandeau de LED du bouclier et la lumière qu'il projette)
              effets : balayage, avaries (coque en alerte, lueurs des zones touchées), front
                       d'apparition, cotes, repères de modules, impacts
            Les animations ne repeignent ainsi jamais le plan détaillé. */
        construire() {
            const n = this.n;
            const pile = document.createElement('div');
            pile.className = 'holo';
            const calque = (classe, contenu) => {
                const svg = creerSvg('svg', { class: 'holo-calque ' + classe, 'aria-hidden': 'true', preserveAspectRatio: 'xMidYMid meet', viewBox: '-600 -100 1200 1200' });
                svg.innerHTML = contenu;
                pile.append(svg);
                return svg;
            };
            this.calques = [
                calque('holo-fond', `
                    <defs>
                        <radialGradient id="holo-lumiere-${n}" cx="50%" cy="50%" r="50%">
                            <stop offset="0" class="holo-stop-lumiere"/><stop offset="1" class="holo-stop-vide"/>
                        </radialGradient>
                    </defs>
                    <g class="holo-grille"></g>
                    <ellipse class="holo-lumiere" fill="url(#holo-lumiere-${n})"/>
                    <path class="bouclier-voile"/>
                    <path class="bouclier-anneau"/>`),
                calque('holo-plan', `
                    <defs>
                        <clipPath id="holo-revele-${n}" clipPathUnits="userSpaceOnUse"><rect class="holo-revele" x="-5000" y="-5000" width="10000" height="10000"/></clipPath>
                        <clipPath id="holo-clip-${n}"><path class="holo-forme"/></clipPath>
                        <radialGradient id="holo-fond-${n}" cx="50%" cy="42%" r="62%">
                            <stop offset="0" class="holo-stop-centre"/><stop offset="0.7" class="holo-stop-milieu"/><stop offset="1" class="holo-stop-bord"/>
                        </radialGradient>
                        <pattern id="holo-trame-${n}" class="holo-motif" patternUnits="userSpaceOnUse" x="0" y="0" width="5000" height="3">
                            <rect class="holo-trame-ligne" x="-2500" y="0" width="5000" height="1"/>
                        </pattern>
                    </defs>
                    <g class="holo-vaisseau" clip-path="url(#holo-revele-${n})">
                        <path class="holo-coque" fill="url(#holo-fond-${n})"/>
                        <rect class="holo-trame" clip-path="url(#holo-clip-${n})" fill="url(#holo-trame-${n})"/>
                        <path class="holo-details"/>
                        <path class="holo-traits"/>
                        <path class="holo-halo"/>
                        <path class="holo-contour"/>
                    </g>`),
                calque('holo-effets', `
                    <defs>
                        <clipPath id="holo-clip-effets-${n}"><path class="holo-forme"/></clipPath>
                        <linearGradient id="holo-bande-${n}" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0" class="holo-stop-vide"/><stop offset="0.8" class="holo-stop-bande"/><stop offset="0.9" class="holo-stop-front"/><stop offset="1" class="holo-stop-vide"/>
                        </linearGradient>
                        <radialGradient id="holo-lueur-${n}">
                            <stop offset="0" class="holo-stop-lueur-coeur"/><stop offset="0.45" class="holo-stop-lueur-milieu"/><stop offset="1" class="holo-stop-lueur-bord"/>
                        </radialGradient>
                    </defs>
                    <g clip-path="url(#holo-clip-effets-${n})"><rect class="holo-balayage" fill="url(#holo-bande-${n})"/></g>
                    <g class="avaries" clip-path="url(#holo-clip-effets-${n})">
                        <path class="alerte-coque"/>
                        <g class="zones-lueurs"></g>
                    </g>
                    <line class="holo-front"/>
                    <g class="holo-cotes">
                        <path class="holo-cote-trait"/>
                        <text class="holo-cote-texte" data-cote="longueur"/>
                        <text class="holo-cote-texte" data-cote="largeur"/>
                        <text class="holo-cote-texte holo-cote-grille" data-cote="grille"/>
                    </g>
                    <g class="zones"></g>
                    <g class="impact"><circle r="40"/><circle r="40"/></g>`),
            ];
            this.pile = pile;
            const q = selecteur => pile.querySelector(selecteur);
            this.el = {
                formes: pile.querySelectorAll('.holo-forme'), revele: q('.holo-revele'), grille: q('.holo-grille'), lumiere: q('.holo-lumiere'),
                bouclier: q('.bouclier-anneau'), voile: q('.bouclier-voile'), vaisseau: q('.holo-vaisseau'),
                coque: q('.holo-coque'), trame: q('.holo-trame'), motif: q('.holo-motif'), ligneTrame: q('.holo-trame-ligne'),
                details: q('.holo-details'), traits: q('.holo-traits'), halo: q('.holo-halo'), contour: q('.holo-contour'),
                balayage: q('.holo-balayage'), front: q('.holo-front'), cotes: q('.holo-cotes'), coteTrait: q('.holo-cote-trait'),
                coteLongueur: q('[data-cote="longueur"]'), coteLargeur: q('[data-cote="largeur"]'), coteGrille: q('[data-cote="grille"]'),
                zones: q('.zones'), impact: q('.impact'), alerteCoque: q('.alerte-coque'), lueurs: q('.zones-lueurs'),
            };

            // Repères de modules : un ou deux losanges par zone, une étiquette (vue combat),
            // et sous la coque une lueur rouge (visible quand la zone est touchée, critique ou HS)
            this.reperes = [];
            for (const zone of this.zones) {
                const geo = GEOMETRIE_ZONES[zone.cle] || { y: 0.5, x: 0 };
                const instances = geo.miroir ? [-1, 1] : [1];
                for (const cote of instances) {
                    const g = creerSvg('g', { class: 'zone', 'data-zone': zone.cle, 'data-etat': 'vide' }, this.el.zones);
                    const lueur = creerSvg('circle', { class: 'zone-lueur', 'data-zone': zone.cle, 'data-etat': 'vide', fill: `url(#holo-lueur-${n})` }, this.el.lueurs);
                    const repere = { cle: zone.cle, cote, g, lueur, losange: creerSvg('rect', {}, g) };
                    if (this.etiquettes && cote === 1) {
                        repere.renvoi = creerSvg('polyline', { class: 'zone-renvoi' }, g);
                        repere.texte = creerSvg('text', {}, g);
                        repere.texte.textContent = zone.nom;
                    }
                    this.reperes.push(repere);
                }
            }

            this.conteneur.append(pile);
            if (this.avecLegende) {
                this.legende = document.createElement('div');
                this.legende.className = 'holo-legende';
                this.legende.innerHTML = '<b></b><span></span>';
                this.conteneur.append(this.legende);
            }
            this.conteneur.classList.add('holo-hote');
        }

        /** Affiche le vaisseau `type` (symbole du journal). Inconnu : silhouette générique. */
        async afficher(type) {
            let id = normaliser(type);
            if (!id || horsVaisseau(id)) {                          // à pied, en VRS, en chasseur : on garde le vaisseau
                if (this.plan || this.demande) return this.plan;
                id = 'generique';                                   // ... ou la silhouette générique s'il n'y en a pas encore
            }
            const cible = connu(id) ? id : 'generique';
            if (cible === this.id || cible === this.demande) return this.plan;
            this.demande = cible;
            let plan;
            try {
                plan = await charger(cible);
            } catch (erreur) {
                console.warn('[COVAS] ' + erreur.message + ' : silhouette générique');
                plan = GENERIQUE;
            }
            if (this.demande !== cible) return this.plan;           // un autre vaisseau a été demandé entre-temps
            this.demande = null;
            this.poserPlan(plan, cible);
            return plan;
        }

        poserPlan(plan, id) {
            this.plan = plan;
            this.id = id;
            const fiche = CATALOGUE[id];
            this.metres = fiche ? { longueur: fiche[2], largeur: fiche[3], hauteur: fiche[4] } : null;
            const e = this.el;
            for (const el of [...e.formes, e.coque, e.halo, e.contour, e.alerteCoque]) el.setAttribute('d', plan.coque);
            e.traits.setAttribute('d', plan.traits || '');
            e.details.setAttribute('d', plan.details || '');
            this.conteneur.dataset.vaisseau = id;

            if (this.legende) {
                this.legende.querySelector('b').textContent = fiche ? fiche[0] : 'Vaisseau inconnu';
                this.legende.querySelector('span').textContent = fiche
                    ? `${fiche[1]} · ${metres(fiche[2])} × ${metres(fiche[3])} · plateforme ${{ S: 'petite', M: 'moyenne', L: 'grande' }[fiche[5]]}`
                    : 'Plan non disponible';
                this.legende.title = SOURCES[plan.source] || '';
            }
            this.mettreEnPage();
            this.placerZones();
            this.apparaitre();
            this.led?.allumer();
        }

        /** Cadre le vaisseau dans le conteneur : viewBox, grille, bouclier, cotes, étiquettes. */
        mettreEnPage() {
            const plan = this.plan;
            if (!plan) return;
            const { width: lp, height: hp } = this.conteneur.getBoundingClientRect();
            if (lp < 10 || hp < 10) return;
            const W = plan.largeur;
            const cote = this.avecCotes ? 0.075 * Math.max(W, LONGUEUR) : 0;
            const reserve = this.etiquettes ? Math.min(124, lp * 0.24) : 0;    // colonne des étiquettes, en px
            const haut = this.legende ? this.legende.offsetHeight + 6 : 0;     // légende en haut à gauche, en px

            // Le bouclier garde le même écart à l'écran : on le retire de la place avant de calculer
            // l'échelle. Les miniatures du hangar n'en ont pas et gardent une simple marge.
            const avecBouclier = getComputedStyle(this.el.bouclier).display !== 'none';
            const ecartPx = avecBouclier ? Math.min(ECART_BOUCLIER_PX, ECART_BOUCLIER_MAX * Math.min(lp, hp)) : 0;
            const margeFixe = avecBouclier ? 0 : 0.07 * Math.max(W, LONGUEUR);
            const s = Math.max(0.01, Math.min((lp - reserve - 16 - 2 * ecartPx) / (W + 2 * margeFixe + cote),
                (hp - haut - 16 - 2 * ecartPx) / (LONGUEUR + 2 * margeFixe + cote * 0.9)));
            const u = 1 / s;                                                    // unités par pixel
            const marge = margeFixe + ecartPx * u;
            const rx = W / 2 + marge, ry = LONGUEUR / 2 + marge;
            this.bouclier = { rx, ry };

            // Boîte utile (unités du plan)
            const x0 = -rx - cote, x1 = rx, y0 = LONGUEUR / 2 - ry, y1 = LONGUEUR / 2 + ry + cote * 0.9;
            this.uParPx = u;
            const largeurVue = lp * u, hauteurVue = hp * u;
            const vx = x0 - ((lp - reserve) * u - (x1 - x0)) / 2;
            const vy = y0 - haut * u - ((hp - haut) * u - (y1 - y0)) / 2;
            this.vue = { x: vx, y: vy, l: largeurVue, h: hauteurVue };
            const viewBox = `${arrondi(vx)} ${arrondi(vy)} ${arrondi(largeurVue)} ${arrondi(hauteurVue)}`;
            for (const svg of this.calques) svg.setAttribute('viewBox', viewBox);
            const e = this.el;

            // Bouclier, halo de projection
            const forme = avecBouclier ? formeBouclier(plan, ecartPx * u) : FORME_VIDE;
            if (e.bouclier.getAttribute('d') !== forme.trace) {
                e.bouclier.setAttribute('d', forme.trace);
                e.voile.setAttribute('d', forme.trace);
            }
            if (forme.points.length) (this.led ??= new BandeauLed(this)).placer(plan, forme.points, this.vue, u, ecartPx);
            else this.led?.masquer();
            poser(e.lumiere, { cx: 0, cy: LONGUEUR / 2, rx: arrondi(rx * 1.25), ry: arrondi(ry * 1.15) });

            // Trame horizontale (une ligne sur trois pixels) et bande de balayage
            poser(e.motif, { height: arrondi(3 * u * 10) / 10 });
            poser(e.ligneTrame, { height: arrondi(u * 10) / 10 });
            poser(e.trame, { x: arrondi(-W / 2 - 10), y: -10, width: arrondi(W + 20), height: LONGUEUR + 20 });
            poser(e.balayage, { x: arrondi(-W / 2 - 10), y: -260, width: arrondi(W + 20), height: 240 });

            // Grille métrique centrée sur le vaisseau
            const parMetre = this.metres ? LONGUEUR / this.metres.longueur : null;
            const pasM = this.metres ? pasGrille(this.metres.longueur) : null;
            const pas = parMetre ? pasM * parMetre : LONGUEUR / 10;
            const traits = [];
            const premierX = Math.ceil(vx / pas), dernierX = Math.floor((vx + largeurVue) / pas);
            const premierY = Math.ceil((vy - LONGUEUR / 2) / pas), dernierY = Math.floor((vy + hauteurVue - LONGUEUR / 2) / pas);
            const majeurs = [], mineurs = [];
            for (let i = premierX; i <= dernierX; i++) (i % 5 ? mineurs : majeurs).push(`M${arrondi(i * pas)} ${arrondi(vy)}V${arrondi(vy + hauteurVue)}`);
            for (let j = premierY; j <= dernierY; j++) (j % 5 ? mineurs : majeurs).push(`M${arrondi(vx)} ${arrondi(LONGUEUR / 2 + j * pas)}H${arrondi(vx + largeurVue)}`);
            traits.push(`<path class="mineur" d="${mineurs.join('')}"/>`, `<path class="majeur" d="${majeurs.join('')}"/>`);
            e.grille.innerHTML = this.avecGrille ? traits.join('') : '';
            e.cotes.style.display = this.avecCotes ? '' : 'none';

            // Cotes : longueur à gauche, largeur en dessous
            const xc = -rx - cote * 0.45, yc = LONGUEUR / 2 + ry + cote * 0.35, t = 5 * u;
            e.coteTrait.setAttribute('d',
                `M${arrondi(xc)} 0V${LONGUEUR}M${arrondi(xc - t)} 0H${arrondi(xc + t)}M${arrondi(xc - t)} ${LONGUEUR}H${arrondi(xc + t)}` +
                `M${arrondi(-W / 2)} ${arrondi(yc)}H${arrondi(W / 2)}M${arrondi(-W / 2)} ${arrondi(yc - t)}V${arrondi(yc + t)}M${arrondi(W / 2)} ${arrondi(yc - t)}V${arrondi(yc + t)}` +
                `M${arrondi(-W / 2)} ${arrondi(LONGUEUR * 0.985)}V${arrondi(yc - t)}M${arrondi(W / 2)} ${arrondi(LONGUEUR * 0.985)}V${arrondi(yc - t)}` +
                `M${arrondi(xc + t)} 0H${arrondi(-W * 0.04)}M${arrondi(xc + t)} ${LONGUEUR}H${arrondi(-W * 0.2)}`);
            const corps = 11 * u;
            e.cotes.style.fontSize = arrondi(corps * 10) / 10 + 'px';
            const mesures = this.metres;
            poser(e.coteLongueur, { x: arrondi(xc - 7 * u), y: LONGUEUR / 2, transform: `rotate(-90 ${arrondi(xc - 7 * u)} ${LONGUEUR / 2})` });
            e.coteLongueur.textContent = mesures ? metres(mesures.longueur) : '';
            poser(e.coteLargeur, { x: 0, y: arrondi(yc + corps * 1.35) });
            e.coteLargeur.textContent = mesures ? metres(mesures.largeur) : '';
            poser(e.coteGrille, { x: arrondi(vx + largeurVue - reserve * u - 8 * u), y: arrondi(vy + hauteurVue - 8 * u) });
            e.coteGrille.textContent = pasM ? `grille ${pasM} m` : '';
            e.coteGrille.style.display = this.etiquettes || lp > 360 ? '' : 'none';

            // Repères de zones et étiquettes
            for (const r of this.reperes) {
                const taille = (this.etiquettes ? 11 : 8) * u;
                poser(r.losange, { width: arrondi(taille * 10) / 10, height: arrondi(taille * 10) / 10 });
            }
            this.el.zones.style.fontSize = arrondi(12 * u * 10) / 10 + 'px';
            this.placerEtiquettes();
        }

        /** Positionne les repères de modules sur la coque du vaisseau affiché. */
        placerZones() {
            const plan = this.plan;
            if (!plan) return;
            const reglages = plan.zones || {};
            // Lueur des zones touchées : proportionnée au vaisseau, plus petite en vue navigation
            const rayon = arrondi((this.etiquettes ? 0.09 : 0.075) * Math.sqrt(plan.largeur * LONGUEUR));
            for (const r of this.reperes) {
                const geo = { ...GEOMETRIE_ZONES[r.cle], ...(reglages[r.cle] || {}) };
                const y = geo.y * LONGUEUR;
                const [min, max] = largeurA(plan, y);
                const centre = (min + max) / 2, demi = (max - min) / 2;
                const voulu = { x: centre + r.cote * geo.x * demi, y };
                r.position = this.dansLaCoque(voulu);
                r.lueur.setAttribute('r', rayon);
            }
            this.placerEtiquettes();
        }

        /** Point de la coque le plus proche de `point` (la silhouette peut être creuse, fourchue...). */
        dansLaCoque(point) {
            const forme = this.el.coque;
            if (typeof forme.isPointInFill !== 'function') return point;
            const essai = (x, y) => {
                try { return forme.isPointInFill(new DOMPoint(x, y)); } catch { return true; }
            };
            if (essai(point.x, point.y)) return point;
            const pas = LONGUEUR / 100;
            for (let rayon = pas; rayon <= LONGUEUR / 3; rayon += pas) {
                for (let k = 0; k < 16; k++) {
                    const a = (k / 16) * Math.PI * 2;
                    const x = point.x + Math.cos(a) * rayon, y = point.y + Math.sin(a) * rayon;
                    if (essai(x, y)) return { x, y };
                }
            }
            return point;
        }

        placerEtiquettes() {
            const u = this.uParPx, b = this.bouclier;
            if (!b) return;
            const taille = (this.etiquettes ? 11 : 8) * u;
            for (const r of this.reperes) {
                if (!r.position) continue;
                poser(r.losange, { x: arrondi(r.position.x - taille / 2), y: arrondi(r.position.y - taille / 2) });
                poser(r.lueur, { cx: arrondi(r.position.x), cy: arrondi(r.position.y) });
            }
            if (!this.etiquettes) return;
            const avecTexte = this.reperes.filter(r => r.texte && r.position).sort((a, c) => a.position.y - c.position.y);
            if (!avecTexte.length) return;
            const ecart = 17 * u;
            const xTexte = b.rx + 16 * u;
            const ys = avecTexte.map(r => r.position.y);
            for (let i = 1; i < ys.length; i++) ys[i] = Math.max(ys[i], ys[i - 1] + ecart);
            const bas = this.vue.y + this.vue.h - 10 * u;
            const debordement = ys[ys.length - 1] - bas;
            if (debordement > 0) for (let i = 0; i < ys.length; i++) ys[i] -= debordement;
            for (let i = ys.length - 2; i >= 0; i--) ys[i] = Math.min(ys[i], ys[i + 1] - ecart);
            avecTexte.forEach((r, i) => {
                const y = ys[i];
                poser(r.texte, { x: arrondi(xTexte), y: arrondi(y + 4 * u) });
                const coude = Math.max(r.position.x + 8 * u, b.rx - 6 * u);
                r.renvoi.setAttribute('points', `${arrondi(r.position.x + 7 * u)},${arrondi(r.position.y)} ${arrondi(coude)},${arrondi(y)} ${arrondi(xTexte - 4 * u)},${arrondi(y)}`);
            });
        }

        /** Balayage de haut en bas qui matérialise le vaisseau (une fois, au changement de vaisseau).
            Joué même si Windows demande moins d'animations : c'est l'effet d'apparition de l'hologramme. */
        apparaitre() {
            const { revele, front } = this.el;
            cancelAnimationFrame(this.animationApparition);
            const plan = this.plan;
            if (!this.animation) {
                poser(revele, { y: -5000, height: 10000 });
                front.style.opacity = 0;
                return;
            }
            const W = plan.largeur;
            const debut = performance.now();
            this.conteneur.classList.add('holo-apparition');
            const etape = maintenant => {
                const k = Math.min(1, (maintenant - debut) / DUREE_APPARITION);
                const lisse = 1 - Math.pow(1 - k, 2.2);
                const y = -40 + lisse * (LONGUEUR + 80);
                poser(revele, { y: -5000, height: arrondi(5000 + y) });
                poser(front, { x1: arrondi(-W / 2 - 30), x2: arrondi(W / 2 + 30), y1: arrondi(y), y2: arrondi(y) });
                front.style.opacity = k < 0.85 ? 1 : (1 - k) / 0.15;
                if (k < 1) this.animationApparition = requestAnimationFrame(etape);
                else {
                    poser(revele, { y: -5000, height: 10000 });
                    this.conteneur.classList.remove('holo-apparition');
                }
            };
            this.animationApparition = requestAnimationFrame(etape);
        }

        /** Place les ondes d'impact (avant d'ajouter la classe « touche ») et renvoie leur point :
            sur le bandeau du bouclier s'il encaisse le coup, sinon au hasard sur la coque.
            Le jeu ne dit pas d'où vient le tir : le côté touché est choisi au hasard. */
        preparerImpact(surBouclier = false) {
            const plan = this.plan;
            if (!plan) return null;
            let point = surBouclier ? this.led?.pointImpact() ?? null : null;
            this.el.impact.dataset.sur = surBouclier ? 'bouclier' : 'coque';
            for (let essai = 0; essai < 12 && !point; essai++) {
                const y = (0.1 + Math.random() * 0.8) * LONGUEUR;
                const [min, max] = largeurA(plan, y);
                const candidat = { x: min + Math.random() * (max - min), y };
                try { if (this.el.coque.isPointInFill(new DOMPoint(candidat.x, candidat.y))) point = candidat; } catch { point = candidat; }
            }
            point = point || { x: 0, y: LONGUEUR / 2 };
            const r = 0.035 * Math.max(plan.largeur, LONGUEUR);
            for (const cercle of this.el.impact.children) poser(cercle, { cx: arrondi(point.x), cy: arrondi(point.y), r: arrondi(r) });
            return point;
        }

        // ----------------------------------------------------------------
        //  AVARIES (calque effets uniquement : le plan détaillé n'est jamais repeint)
        // ----------------------------------------------------------------
        /** Relance l'effet porté par `classe` sur ces éléments (un nouveau coup le fait repartir
            de zéro), puis retire la classe au bout de `duree` ms. */
        relancer(elements, classe, duree) {
            const liste = elements.filter(Boolean);
            if (!liste.length) return;
            for (const el of liste) el.classList.remove(classe);
            void this.pile.getBoundingClientRect();       // le navigateur constate le retrait : l'animation repart à zéro
            for (const el of liste) {
                el.classList.add(classe);
                const parClasse = this.minuteries.get(el) || new Map();
                clearTimeout(parClasse.get(classe));
                parClasse.set(classe, setTimeout(() => el.classList.remove(classe), duree));
                this.minuteries.set(el, parClasse);
            }
        }

        /** Modules touchés : leurs repères clignotent rouge/noir comme un voyant d'impact, avec une
            lueur rouge sur la coque autour d'eux. Ensuite, l'état du module (data-etat) reprend la main :
            rouge fixe s'il est critique ou HS. */
        signalerZones(cles, duree = DUREE_VOYANT_ZONE) {
            const voulues = new Set(cles);
            this.relancer(this.reperes.filter(r => voulues.has(r.cle)).flatMap(r => [r.g, r.lueur]), 'voyant', duree);
        }

        /** Coup reçu sans savoir quel module (le jeu ne le dit pas) :
              'bouclier'     : coup absorbé, une partie des LED passe au rouge
              'effondrement' : les boucliers tombent, les LED s'éteignent depuis l'impact
              'coque'        : coup sur la coque, toute la silhouette clignote rouge/noir */
        signalerImpact(type) {
            if (!this.plan) return;
            const point = this.preparerImpact(type !== 'coque');
            this.led?.toucher(type, point);
            if (type === 'coque') this.relancer([this.el.alerteCoque], 'voyant', DUREE_VOYANT_COQUE);
            else if (type === 'effondrement') this.relancer([this.el.voile, this.el.bouclier], 'effondrement', DUREE_EFFONDREMENT);
        }
    }

    return {
        LONGUEUR, CATALOGUE, SOURCES,
        enregistrer, charger, connu, nom, normaliser, horsVaisseau, contourBouclier,
        creer: (conteneur, options) => new Hologramme(conteneur, options),
        identifiants: () => Object.keys(CATALOGUE),
    };
})();
