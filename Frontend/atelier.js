/* =====================================================================
   COVAS — Atelier des plans
   Fabrique le plan d'hologramme d'un vaisseau (vaisseaux/<id>.js) à partir d'une
   capture d'écran du jeu prise DU DESSUS (caméra libre), vaisseau sur fond d'espace.

   1. détourage : seuil de luminosité (Otsu), fermeture, trous bouchés, plus grande pièce ;
   2. orientation : axe de symétrie cherché automatiquement (ou deux clics : nez puis poupe),
      nez du côté le plus étroit (inversable) ;
   3. mise au plan : nez en y = 0, poupe en y = 1000, axe en x = 0 ; symétrisation facultative ;
   4. tracés : silhouette (courbe de niveau 0,5 du masque lissé), lignes de détail (courbes de
      niveau de la luminosité de la coque), profil de largeur ;
   5. export : un fichier vaisseaux/<id>.js identique aux autres plans.

   Aucune dépendance : tout se fait dans le navigateur (canvas). Pour les essais automatiques :
       await ATELIER.traiter(urlImage, { id, nez: [x, y], poupe: [x, y], ... })  -> plan
   ===================================================================== */
window.ATELIER = (() => {
    'use strict';

    const H = window.COVAS_HOLOGRAMMES;
    const LONGUEUR = 1000;
    const TAILLE_MAX = 1400;        // côté le plus long de l'image analysée (px)
    const PAS = 2;                  // unités de plan par case de la grille de travail
    const STATIONS = 51;            // points du profil de largeur (comme les autres plans)

    const REGLAGES_DEFAUT = {
        fond: 'couleur',            // détourage : 'couleur' = écart à la couleur du fond (mesurée sur
                                    // les bords) ; 'teinte' = écart de teinte seulement (ignore les
                                    // ombres portées sur un sol)
        seuil: null,                // écart 0-255 ; null = automatique (Otsu)
        cadre: null,                // [x0, y0, x1, y1] en fractions de l'image : ne garder que ça
        rapport: null,              // largeur/longueur imposée (vue de biais) ; null = mesurée
        fermeture: 0.006,           // rayon de fermeture du masque (part du côté de l'image)
        symetrie: true,             // moyenne gauche/droite : silhouette parfaitement symétrique
        dessous: false,             // capture prise par-dessous : gauche et droite inversées
        inverser: false,            // nez et poupe inversés (si l'automatique se trompe)
        niveaux: 6,                 // nombre de courbes de niveau de luminosité (détails)
        tolerance: 1.2,             // simplification de la silhouette (unités de plan)
        nez: null, poupe: null,     // points cliqués (pixels de l'image analysée), facultatifs
        source: 'capture',          // clé de COVAS_HOLOGRAMMES.SOURCES (crédit affiché sur l'hologramme)
        origine: '',                // image d'origine, notée dans l'en-tête du fichier
    };

    // ----------------------------------------------------------------
    //  IMAGE
    // ----------------------------------------------------------------
    function chargerImage(source) {
        return new Promise((resoudre, rejeter) => {
            const img = new Image();
            img.onload = () => resoudre(img);
            img.onerror = () => rejeter(new Error('image illisible'));
            img.src = source;
        });
    }

    function lireImage(img, cadre) {
        const [c0, c1, c2, c3] = cadre || [0, 0, 1, 1];
        const sx = Math.min(c0, c2) * img.naturalWidth, sy = Math.min(c1, c3) * img.naturalHeight;
        const sw = Math.abs(c2 - c0) * img.naturalWidth, sh = Math.abs(c3 - c1) * img.naturalHeight;
        const echelle = Math.min(1, TAILLE_MAX / Math.max(sw, sh));
        const w = Math.max(1, Math.round(sw * echelle));
        const h = Math.max(1, Math.round(sh * echelle));
        const canvas = document.createElement('canvas');
        canvas.width = w; canvas.height = h;
        const ctx = canvas.getContext('2d', { willReadFrequently: true });
        ctx.drawImage(img, sx, sy, sw, sh, 0, 0, w, h);
        const rgba = ctx.getImageData(0, 0, w, h).data;
        const lum = new Float32Array(w * h);
        for (let i = 0, j = 0; i < lum.length; i++, j += 4) lum[i] = 0.299 * rgba[j] + 0.587 * rgba[j + 1] + 0.114 * rgba[j + 2];
        return { w, h, lum, rgba, canvas };
    }

    /** Couleur du fond : médiane des pixels du bord de l'image. */
    function couleurFond(image) {
        const { w, h, rgba } = image;
        const canaux = [[], [], []];
        const prendre = i => { for (let c = 0; c < 3; c++) canaux[c].push(rgba[i * 4 + c]); };
        for (let x = 0; x < w; x += 2) { prendre(x); prendre((h - 1) * w + x); }
        for (let y = 0; y < h; y += 2) { prendre(y * w); prendre(y * w + w - 1); }
        return canaux.map(c => c.sort((a, b) => a - b)[c.length >> 1]);
    }

    /** Écart de chaque pixel au fond (0-255) : ce qui s'en distingue est le vaisseau. */
    function ecartAuFond(image, mode) {
        const { rgba } = image;
        const [fr, fg, fb] = couleurFond(image);
        const ecart = new Float32Array(image.w * image.h);
        const sf = fr + fg + fb + 1;
        for (let i = 0, j = 0; i < ecart.length; i++, j += 4) {
            const r = rgba[j], g = rgba[j + 1], b = rgba[j + 2];
            if (mode === 'teinte') {                 // chromaticité : une ombre garde la teinte du sol
                const s = r + g + b + 1;
                const d = Math.hypot(r / s - fr / sf, g / s - fg / sf, b / s - fb / sf);
                ecart[i] = Math.min(255, d * 900 * Math.min(1, s / 90));
            } else {
                ecart[i] = Math.min(255, Math.hypot(r - fr, g - fg, b - fb));
            }
        }
        return ecart;
    }

    /** Seuil d'Otsu : sépare au mieux le fond sombre de la coque. */
    function otsu(lum) {
        const histo = new Float64Array(256);
        for (const v of lum) histo[Math.min(255, v | 0)]++;
        const total = lum.length;
        let somme = 0;
        for (let i = 0; i < 256; i++) somme += i * histo[i];
        let sommeFond = 0, poidsFond = 0, meilleur = 0, seuil = 40;
        for (let t = 0; t < 256; t++) {
            poidsFond += histo[t];
            if (!poidsFond) continue;
            const poidsAvant = total - poidsFond;
            if (!poidsAvant) break;
            sommeFond += t * histo[t];
            const ecart = poidsFond * poidsAvant * (sommeFond / poidsFond - (somme - sommeFond) / poidsAvant) ** 2;
            if (ecart > meilleur) { meilleur = ecart; seuil = t; }
        }
        return Math.max(8, seuil);
    }

    // ----------------------------------------------------------------
    //  MASQUE DU VAISSEAU
    // ----------------------------------------------------------------
    /** Max (dilatation) ou min (érosion) sur un carré de côté 2r+1, en deux passes. */
    function morpho(src, w, h, r, max) {
        const tmp = new Uint8Array(w * h), dst = new Uint8Array(w * h);
        const cible = max ? 1 : 0;
        for (let y = 0; y < h; y++) {
            const ligne = y * w;
            let compte = 0;                       // nombre de « cible » dans la fenêtre
            for (let x = -r; x < w + r; x++) {
                const entre = x + r, sort = x - r - 1;
                if (entre < w && src[ligne + entre] === cible) compte++;
                if (sort >= 0 && src[ligne + sort] === cible) compte--;
                if (x >= 0 && x < w) tmp[ligne + x] = compte > 0 ? cible : 1 - cible;
            }
        }
        for (let x = 0; x < w; x++) {
            let compte = 0;
            for (let y = -r; y < h + r; y++) {
                const entre = y + r, sort = y - r - 1;
                if (entre < h && tmp[entre * w + x] === cible) compte++;
                if (sort >= 0 && tmp[sort * w + x] === cible) compte--;
                if (y >= 0 && y < h) dst[y * w + x] = compte > 0 ? cible : 1 - cible;
            }
        }
        return dst;
    }

    /** Étiquette les pièces connexes (4-voisinage) d'un masque. */
    function pieces(masque, w, h) {
        const etiquettes = new Int32Array(w * h).fill(-1);
        const tailles = [];
        const pile = new Int32Array(w * h);
        for (let depart = 0; depart < masque.length; depart++) {
            if (!masque[depart] || etiquettes[depart] >= 0) continue;
            const n = tailles.length;
            let haut = 0, taille = 0;
            pile[haut++] = depart; etiquettes[depart] = n;
            while (haut) {
                const i = pile[--haut]; taille++;
                const x = i % w, y = (i - x) / w;
                for (const j of [x > 0 ? i - 1 : -1, x < w - 1 ? i + 1 : -1, y > 0 ? i - w : -1, y < h - 1 ? i + w : -1]) {
                    if (j >= 0 && masque[j] && etiquettes[j] < 0) { etiquettes[j] = n; pile[haut++] = j; }
                }
            }
            tailles.push(taille);
        }
        return { etiquettes, tailles };
    }

    function masqueVaisseau(image, reglages) {
        const { w, h } = image;
        const ecart = ecartAuFond(image, reglages.fond);
        const seuil = reglages.seuil ?? otsu(ecart);
        let m = new Uint8Array(w * h);
        for (let i = 0; i < m.length; i++) m[i] = ecart[i] > seuil ? 1 : 0;
        // Fermeture : recolle les panneaux sombres de la coque
        const r = Math.max(1, Math.round(Math.max(w, h) * reglages.fermeture));
        m = morpho(morpho(m, w, h, r, true), w, h, r, false);
        // Trous bouchés : tout ce que le fond n'atteint pas depuis les bords appartient au vaisseau
        const fond = pieces(m.map(v => 1 - v), w, h);
        const bord = new Set();
        for (let x = 0; x < w; x++) { bord.add(fond.etiquettes[x]); bord.add(fond.etiquettes[(h - 1) * w + x]); }
        for (let y = 0; y < h; y++) { bord.add(fond.etiquettes[y * w]); bord.add(fond.etiquettes[y * w + w - 1]); }
        for (let i = 0; i < m.length; i++) if (!m[i] && !bord.has(fond.etiquettes[i])) m[i] = 1;
        // Le vaisseau = la plus grande pièce (et les pièces assez grosses : nacelles détachées)
        const { etiquettes, tailles } = pieces(m, w, h);
        if (!tailles.length) throw new Error('aucun vaisseau trouvé : baisse le seuil');
        const plusGrande = Math.max(...tailles);
        for (let i = 0; i < m.length; i++) m[i] = m[i] && tailles[etiquettes[i]] >= plusGrande * 0.03 ? 1 : 0;
        return { masque: m, seuil };
    }

    // ----------------------------------------------------------------
    //  ORIENTATION
    // ----------------------------------------------------------------
    function pointsDuMasque(masque, w, h, maxPoints = 40000) {
        let n = 0;
        for (const v of masque) n += v;
        const pas = Math.max(1, Math.ceil(Math.sqrt(n / maxPoints)));
        const points = [];
        let cx = 0, cy = 0, total = 0;
        for (let y = 0; y < h; y += pas) for (let x = 0; x < w; x += pas) {
            if (masque[y * w + x]) { points.push(x, y); cx += x; cy += y; total++; }
        }
        return { points, centre: [cx / total, cy / total] };
    }

    /** Angle (radians) de l'axe de symétrie passant par le centre : le reflet du vaisseau
        à travers cet axe retombe au mieux sur le vaisseau. */
    function axeSymetrie(masque, w, h) {
        const { points, centre: [cx, cy] } = pointsDuMasque(masque, w, h, 12000);
        const dedans = (x, y) => { const xi = Math.round(x), yi = Math.round(y); return xi >= 0 && yi >= 0 && xi < w && yi < h && masque[yi * w + xi]; };
        const score = theta => {
            const ux = Math.cos(theta), uy = Math.sin(theta);
            let bons = 0;
            for (let k = 0; k < points.length; k += 2) {
                const px = points[k] - cx, py = points[k + 1] - cy;
                const d = 2 * (px * ux + py * uy);
                if (dedans(cx + d * ux - px, cy + d * uy - py)) bons++;
            }
            return bons / (points.length / 2);
        };
        let meilleur = 0, valeur = -1;
        for (let deg = 0; deg < 180; deg += 1) {
            const s = score(deg * Math.PI / 180);
            if (s > valeur) { valeur = s; meilleur = deg; }
        }
        for (let deg = meilleur - 1; deg <= meilleur + 1; deg += 0.1) {
            const s = score(deg * Math.PI / 180);
            if (s > valeur) { valeur = s; meilleur = deg; }
        }
        return { angle: meilleur * Math.PI / 180, centre: [cx, cy], qualite: valeur };
    }

    /** Repère du plan dans l'image : origine (sur l'axe), direction du nez f, droite r. */
    function repere(masque, image, reglages) {
        const { w, h } = image;
        let origine, f, qualite = null;
        if (reglages.nez && reglages.poupe) {
            const [nx, ny] = reglages.nez, [px, py] = reglages.poupe;
            const d = Math.hypot(nx - px, ny - py) || 1;
            f = [(nx - px) / d, (ny - py) / d];
            origine = [nx, ny];
        } else {
            const axe = axeSymetrie(masque, w, h);
            qualite = axe.qualite;
            origine = axe.centre;
            f = [Math.cos(axe.angle), Math.sin(axe.angle)];
            // Le nez est du côté le plus étroit (l'arrière porte les moteurs)
            const { points } = pointsDuMasque(masque, w, h);
            const r = [-f[1], f[0]];
            let amin = Infinity, amax = -Infinity;
            for (let k = 0; k < points.length; k += 2) {
                const a = (points[k] - origine[0]) * f[0] + (points[k + 1] - origine[1]) * f[1];
                amin = Math.min(amin, a); amax = Math.max(amax, a);
            }
            const tranche = (amax - amin) * 0.15;
            const etendue = (de, a) => {
                let lmin = Infinity, lmax = -Infinity;
                for (let k = 0; k < points.length; k += 2) {
                    const x = points[k] - origine[0], y = points[k + 1] - origine[1];
                    const al = x * f[0] + y * f[1];
                    if (al < de || al > a) continue;
                    const lat = x * r[0] + y * r[1];
                    lmin = Math.min(lmin, lat); lmax = Math.max(lmax, lat);
                }
                return lmax - lmin;
            };
            if (etendue(amax - tranche, amax) > etendue(amin, amin + tranche)) f = [-f[0], -f[1]];
        }
        if (reglages.inverser) f = [-f[0], -f[1]];
        const r = [-f[1], f[0]];                 // droite du vaisseau, vu du dessus, nez en haut
        return { origine, f, r, qualite };
    }

    // ----------------------------------------------------------------
    //  GRILLE DU PLAN (nez en haut, 1000 unités de long)
    // ----------------------------------------------------------------
    function flou(champ, l, h, passes = 2) {
        let a = Float32Array.from(champ), b = new Float32Array(champ.length);
        for (let p = 0; p < passes; p++) {
            for (let y = 0; y < h; y++) for (let x = 0; x < l; x++) {
                const i = y * l + x;
                b[i] = (a[i] * 2 + (x > 0 ? a[i - 1] : a[i]) + (x < l - 1 ? a[i + 1] : a[i])) / 4;
            }
            for (let y = 0; y < h; y++) for (let x = 0; x < l; x++) {
                const i = y * l + x;
                a[i] = (b[i] * 2 + (y > 0 ? b[i - l] : b[i]) + (y < h - 1 ? b[i + l] : b[i])) / 4;
            }
        }
        return a;
    }

    function miroir(champ, l, h) {
        const m = new Float32Array(champ.length);
        for (let y = 0; y < h; y++) for (let x = 0; x < l; x++) m[y * l + x] = champ[y * l + (l - 1 - x)];
        return m;
    }

    function grillePlan(image, masque, rep, reglages) {
        const { w, h, lum } = image;
        const { origine: [ox, oy], f, r } = rep;
        // Étendue du vaisseau le long de l'axe et de part et d'autre
        let amin = Infinity, amax = -Infinity, lmax = 0;
        for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
            if (!masque[y * w + x]) continue;
            const dx = x - ox, dy = y - oy;
            const a = dx * f[0] + dy * f[1], l = Math.abs(dx * r[0] + dy * r[1]);
            if (a < amin) amin = a;
            if (a > amax) amax = a;
            if (l > lmax) lmax = l;
        }
        const echelle = LONGUEUR / (amax - amin);          // unités de plan par pixel
        // Vue de biais : la largeur est ramenée aux proportions réelles du vaisseau
        const kx = reglages.rapport ? (reglages.rapport * LONGUEUR) / (2 * lmax * echelle) : 1;
        const demi = Math.ceil((lmax * echelle * kx) / PAS) + 3;
        const l = demi * 2, hg = Math.ceil(LONGUEUR / PAS) + 7;
        const x0 = -demi * PAS, y0 = -3 * PAS;              // coin de la grille (unités de plan)
        const champMasque = new Float32Array(l * hg), champLum = new Float32Array(l * hg);
        const signe = reglages.dessous ? -1 : 1;
        const lire = (tab, x, y) => {                        // bilinéaire
            if (x < 0 || y < 0 || x > w - 1 || y > h - 1) return 0;
            const xi = Math.min(w - 2, x | 0), yi = Math.min(h - 2, y | 0), fx = x - xi, fy = y - yi, i = yi * w + xi;
            return tab[i] * (1 - fx) * (1 - fy) + tab[i + 1] * fx * (1 - fy) + tab[i + w] * (1 - fx) * fy + tab[i + w + 1] * fx * fy;
        };
        for (let j = 0; j < hg; j++) for (let i = 0; i < l; i++) {
            const xp = x0 + (i + 0.5) * PAS, yp = y0 + (j + 0.5) * PAS;
            const a = amax - yp / echelle, lat = signe * xp / (echelle * kx);
            const sx = ox + a * f[0] + lat * r[0], sy = oy + a * f[1] + lat * r[1];
            champMasque[j * l + i] = lire(masque, sx, sy);
            champLum[j * l + i] = lire(lum, sx, sy);
        }
        let m = flou(champMasque, l, hg, 1), lu = flou(champLum, l, hg, 2);
        if (reglages.symetrie) {
            const mm = miroir(m, l, hg), ml = miroir(lu, l, hg);
            for (let k = 0; k < m.length; k++) { m[k] = (m[k] + mm[k]) / 2; lu[k] = (lu[k] + ml[k]) / 2; }
        }
        return { l, h: hg, x0, y0, masque: m, lum: lu, largeurPx: 2 * lmax, longueurPx: amax - amin };
    }

    // ----------------------------------------------------------------
    //  COURBES DE NIVEAU (marching squares) ET SIMPLIFICATION
    // ----------------------------------------------------------------
    /** Segments de la courbe de niveau `iso` ; une case dont un coin vaut NaN est ignorée.
        Renvoie des polylignes (fermées ou ouvertes) en unités de plan. */
    function courbes(champ, l, h, iso, x0, y0) {
        const H_ = (i, j) => j * l + i;                       // arête horizontale (i,j)-(i+1,j)
        const V_ = (i, j) => l * h + j * l + i;              // arête verticale   (i,j)-(i,j+1)
        const point = new Map();
        const pos = (id, a, b, va, vb) => {
            if (!point.has(id)) {
                const t = (iso - va) / (vb - va || 1e-9);
                point.set(id, [x0 + (a[0] + (b[0] - a[0]) * t + 0.5) * PAS, y0 + (a[1] + (b[1] - a[1]) * t + 0.5) * PAS]);
            }
            return id;
        };
        const voisins = new Map();
        const lier = (p, q) => {
            if (!voisins.has(p)) voisins.set(p, []);
            if (!voisins.has(q)) voisins.set(q, []);
            voisins.get(p).push(q); voisins.get(q).push(p);
        };
        for (let j = 0; j < h - 1; j++) for (let i = 0; i < l - 1; i++) {
            const v0 = champ[j * l + i], v1 = champ[j * l + i + 1], v2 = champ[(j + 1) * l + i + 1], v3 = champ[(j + 1) * l + i];
            if (Number.isNaN(v0 + v1 + v2 + v3)) continue;
            const cas = (v0 > iso) * 8 + (v1 > iso) * 4 + (v2 > iso) * 2 + (v3 > iso);
            if (cas === 0 || cas === 15) continue;
            const T = () => pos(H_(i, j), [i, j], [i + 1, j], v0, v1);
            const R = () => pos(V_(i + 1, j), [i + 1, j], [i + 1, j + 1], v1, v2);
            const B = () => pos(H_(i, j + 1), [i, j + 1], [i + 1, j + 1], v3, v2);
            const L = () => pos(V_(i, j), [i, j], [i, j + 1], v0, v3);
            const centre = (v0 + v1 + v2 + v3) / 4 > iso;
            switch (cas) {
                case 1: case 14: lier(L(), B()); break;
                case 2: case 13: lier(B(), R()); break;
                case 3: case 12: lier(L(), R()); break;
                case 4: case 11: lier(T(), R()); break;
                case 6: case 9: lier(T(), B()); break;
                case 7: case 8: lier(T(), L()); break;
                case 5: if (centre) { lier(T(), L()); lier(B(), R()); } else { lier(T(), R()); lier(L(), B()); } break;
                case 10: if (centre) { lier(T(), R()); lier(L(), B()); } else { lier(T(), L()); lier(B(), R()); } break;
            }
        }
        // Chaînage : d'abord depuis les extrémités (lignes ouvertes), puis les boucles
        const vus = new Set(), lignes = [];
        const suivre = depart => {
            const chemin = [depart];
            vus.add(depart);
            let courant = depart;
            for (;;) {
                const suivant = (voisins.get(courant) || []).find(v => !vus.has(v));
                if (suivant === undefined) break;
                vus.add(suivant); chemin.push(suivant); courant = suivant;
            }
            const ferme = chemin.length > 2 && (voisins.get(courant) || []).includes(depart);
            const pts = chemin.map(id => point.get(id));
            if (ferme) pts.push(pts[0]);
            return { pts, ferme };
        };
        for (const [id, v] of voisins) if (v.length === 1 && !vus.has(id)) lignes.push(suivre(id));
        for (const id of voisins.keys()) if (!vus.has(id)) lignes.push(suivre(id));
        return lignes;
    }

    function douglasPeucker(pts, tolerance) {
        if (pts.length < 3) return pts;
        const garder = new Uint8Array(pts.length);
        garder[0] = garder[pts.length - 1] = 1;
        const pile = [[0, pts.length - 1]];
        while (pile.length) {
            const [a, b] = pile.pop();
            const [ax, ay] = pts[a], [bx, by] = pts[b];
            const dx = bx - ax, dy = by - ay, d = Math.hypot(dx, dy);
            let max = 0, idx = -1;
            for (let k = a + 1; k < b; k++) {
                // Boucle fermée (a = b) : distance au point de départ
                const e = d < 1e-6 ? Math.hypot(pts[k][0] - ax, pts[k][1] - ay)
                    : Math.abs((pts[k][0] - ax) * dy - (pts[k][1] - ay) * dx) / d;
                if (e > max) { max = e; idx = k; }
            }
            if (max > tolerance && idx > 0) { garder[idx] = 1; pile.push([a, idx], [idx, b]); }
        }
        return pts.filter((_, k) => garder[k]);
    }

    const longueurLigne = pts => pts.reduce((s, p, k) => k ? s + Math.hypot(p[0] - pts[k - 1][0], p[1] - pts[k - 1][1]) : 0, 0);
    const aire = pts => pts.reduce((s, p, k) => { const q = pts[(k + 1) % pts.length]; return s + p[0] * q[1] - q[0] * p[1]; }, 0) / 2;
    const n1 = v => (Math.round(v * 10) / 10).toString();

    function chemin(lignes) {
        return lignes.map(({ pts, ferme }) => {
            const corps = pts.slice(0, ferme ? -1 : undefined);
            return 'M' + corps.map(p => n1(p[0]) + ' ' + n1(p[1])).join('L') + (ferme ? 'z' : '');
        }).join('');
    }

    // ----------------------------------------------------------------
    //  PLAN COMPLET
    // ----------------------------------------------------------------
    function construirePlan(grille, reglages, id) {
        const { l, h, x0, y0 } = grille;
        // Silhouette : courbe 0,5 du masque lissé ; les petites îles (bruit) sont écartées
        let boucles = courbes(grille.masque, l, h, 0.5, x0, y0).filter(b => b.ferme);
        if (!boucles.length) throw new Error('silhouette introuvable : ajuste le seuil');
        const plusGrande = Math.max(...boucles.map(b => Math.abs(aire(b.pts))));
        boucles = boucles.filter(b => Math.abs(aire(b.pts)) > plusGrande * 0.01)
            .map(b => ({ pts: douglasPeucker(b.pts, reglages.tolerance), ferme: true }));

        // Détails : courbes de niveau de la luminosité, seulement à l'intérieur de la coque
        const interieur = Float32Array.from(grille.lum);
        const valeurs = [];
        for (let k = 0; k < interieur.length; k++) {
            if (grille.masque[k] < 0.97) interieur[k] = NaN;
            else valeurs.push(interieur[k]);
        }
        valeurs.sort((a, b) => a - b);
        const quantile = q => valeurs[Math.min(valeurs.length - 1, Math.floor(q * valeurs.length))] ?? 0;
        const traits = [], details = [];
        const n = Math.max(0, reglages.niveaux | 0);
        for (let k = 0; k < n; k++) {
            const q = 0.18 + (0.7 * (k + 0.5)) / n;
            const lignes = courbes(interieur, l, h, quantile(q), x0, y0)
                .filter(c => longueurLigne(c.pts) > 18)
                .map(c => ({ pts: douglasPeucker(c.pts, 1.6), ferme: c.ferme }));
            (k === Math.floor(n / 2) || k === Math.floor(n / 2) - 1 ? traits : details).push(...lignes);
        }
        traits.push({ pts: [[0, 0], [0, LONGUEUR]], ferme: false });       // axe du vaisseau

        // Profil de largeur (51 stations) et largeur totale
        const min = [], max = [];
        let largeur = 0;
        for (let s = 0; s < STATIONS; s++) {
            const j = Math.min(h - 1, Math.max(0, Math.round(((s / (STATIONS - 1)) * LONGUEUR - y0) / PAS - 0.5)));
            let gauche = null, droite = null;
            for (let i = 0; i < l; i++) if (grille.masque[j * l + i] >= 0.5) { const x = x0 + (i + 0.5) * PAS; gauche ??= x; droite = x; }
            min.push(gauche); max.push(droite);
        }
        for (let s = 0; s < STATIONS; s++) {                 // stations vides : voisines
            if (min[s] == null) {
                const k = [...Array(STATIONS).keys()].sort((a, b) => Math.abs(a - s) - Math.abs(b - s)).find(k2 => min[k2] != null);
                min[s] = k == null ? 0 : min[k]; max[s] = k == null ? 0 : max[k];
            }
            largeur = Math.max(largeur, max[s] - min[s]);
        }
        const xs = boucles.flatMap(b => b.pts.map(p => p[0]));
        if (xs.length) largeur = Math.max(...xs) - Math.min(...xs);
        return {
            id, nom: H?.nom(id, id) || id, source: reglages.source || 'capture',
            largeur: Math.round(largeur * 10) / 10, longueur: LONGUEUR,
            coque: chemin(boucles), traits: chemin(traits), details: chemin(details),
            profil: { min: min.map(v => Math.round(v * 10) / 10), max: max.map(v => Math.round(v * 10) / 10) },
        };
    }

    /** Toute la chaîne. Renvoie { plan, image, masque, repere, seuil, grille }. */
    async function traiter(source, options = {}) {
        const reglages = { ...REGLAGES_DEFAUT, ...options };
        const img = typeof source === 'string' ? await chargerImage(source) : source;
        const image = lireImage(img, reglages.cadre);
        const { masque, seuil } = masqueVaisseau(image, reglages);
        const rep = repere(masque, image, reglages);
        const grille = grillePlan(image, masque, rep, reglages);
        const plan = construirePlan(grille, reglages, reglages.id || 'vaisseau');
        return { plan, image, masque, repere: rep, seuil, grille, origine: reglages.origine };
    }

    /** Texte du fichier vaisseaux/<id>.js. */
    function fichier(plan, origine = '') {
        const credit = (H?.SOURCES?.[plan.source] || '').replace(/^Plan : /, '');
        return `/* Hologramme COVAS : ${plan.nom} en vue de dessus, nez en haut, longueur normalisée à 1000.\n`
            + `   Plan détouré par l'atelier des plans (Frontend/atelier.html)${credit ? ' : ' + credit : ''}.\n`
            + (origine ? `   Image d'origine : ${origine}\n` : '')
            + `   Fichier généré : coque = silhouette, traits = lignes de structure, details = lignes fines. */\n`
            + `window.COVAS_HOLOGRAMMES && window.COVAS_HOLOGRAMMES.enregistrer(${JSON.stringify(plan)});\n`;
    }

    return { traiter, fichier, otsu, REGLAGES_DEFAUT };
})();

/* =====================================================================
   PAGE DE L'ATELIER (atelier.html)
   ===================================================================== */
(() => {
    'use strict';
    const $ = id => document.getElementById(id);
    if (!$('atelier')) return;                       // script chargé ailleurs (essais)
    const H = window.COVAS_HOLOGRAMMES, A = window.ATELIER;

    const etat = { source: null, nom: '', clics: [], cadre: null, coins: [], resultat: null, mode: null };
    const holo = H.creer($('apercu'), {});

    // Liste des vaisseaux, triés par nom
    const choix = $('choix-vaisseau');
    for (const id of H.identifiants().sort((a, b) => H.nom(a).localeCompare(H.nom(b)))) {
        const option = document.createElement('option');
        option.value = id; option.textContent = `${H.nom(id)} (${id})`;
        choix.append(option);
    }
    choix.value = new URLSearchParams(location.search).get('vaisseau') || 'python_nx';

    function lireReglages() {
        const seuilAuto = $('seuil-auto').checked;
        const fiche = H.CATALOGUE[choix.value];
        return {
            id: choix.value,
            fond: $('fond').value,
            cadre: etat.cadre,
            rapport: $('proportions').checked && fiche ? fiche[3] / fiche[2] : null,
            seuil: seuilAuto ? null : Number($('seuil').value),
            symetrie: $('symetrie').checked,
            dessous: $('dessous').checked,
            inverser: $('inverser').checked,
            niveaux: Number($('niveaux').value),
            nez: etat.clics.length === 2 ? etat.clics[0] : null,
            poupe: etat.clics.length === 2 ? etat.clics[1] : null,
        };
    }

    // Dans les réglages de l'application, le plan s'installe directement (la fenêtre ne télécharge pas)
    const bord = (() => {
        try { return window.parent !== window ? window.parent.COVAS_REGLAGES : null; } catch { return null; }
    })();
    const installable = !!bord?.peutInstallerPlan?.();
    $('installer').hidden = $('note-installer').hidden = !installable;
    $('telecharger').hidden = $('note-telecharger').hidden = installable;
    let confirmation = 0;

    function desarmerInstallation() {
        clearTimeout(confirmation);
        confirmation = 0;
        $('installer').textContent = 'Installer dans le COVAS';
    }

    function exportPossible(actif) {
        $('telecharger').disabled = $('installer').disabled = !actif;
        desarmerInstallation();
    }

    function dessinerSource() {
        const r = etat.resultat;
        const canvas = $('vue-source');
        if (!r) return;
        const { w, h } = r.image;
        canvas.width = w; canvas.height = h;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(r.image.canvas, 0, 0);
        // Masque détecté en orange translucide
        const calque = ctx.getImageData(0, 0, w, h);
        for (let i = 0, j = 0; i < r.masque.length; i++, j += 4) {
            if (r.masque[i]) { calque.data[j] = calque.data[j] * 0.5 + 127; calque.data[j + 1] = calque.data[j + 1] * 0.5 + 60; calque.data[j + 2] *= 0.5; }
        }
        ctx.putImageData(calque, 0, 0);
        // Axe trouvé
        const { origine: [ox, oy], f } = r.repere;
        const L = Math.max(w, h);
        ctx.strokeStyle = '#9fdcff'; ctx.lineWidth = Math.max(1, L / 600); ctx.setLineDash([L / 80, L / 120]);
        ctx.beginPath(); ctx.moveTo(ox - f[0] * L, oy - f[1] * L); ctx.lineTo(ox + f[0] * L, oy + f[1] * L); ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = '#ffd23f';
        ctx.beginPath(); ctx.arc(ox + f[0] * L * 0.03, oy + f[1] * L * 0.03, L / 150, 0, 7); ctx.fill();
        for (const [k, [x, y]] of etat.clics.entries()) {
            ctx.fillStyle = k ? '#ff3a1c' : '#ffd23f';
            ctx.beginPath(); ctx.arc(x, y, L / 120, 0, 7); ctx.fill();
        }
    }

    async function recalculer() {
        if (!etat.source) return;
        $('etat').textContent = 'Analyse…';
        try {
            etat.resultat = await A.traiter(etat.source, lireReglages());
            const { plan, seuil, repere: rep } = etat.resultat;
            if ($('seuil-auto').checked) $('seuil').value = seuil;
            $('valeur-seuil').textContent = seuil;
            holo.poserPlan(plan, plan.id);
            dessinerSource();
            const qualite = rep.qualite != null ? ` · symétrie ${(rep.qualite * 100).toFixed(0)} %` : ' · axe cliqué';
            $('etat').textContent = `${plan.nom} : ${plan.largeur.toFixed(0)} × 1000 (largeur/longueur ${(plan.largeur / 1000).toFixed(3)})${qualite}`;
            exportPossible(true);
        } catch (erreur) {
            $('etat').textContent = 'Échec : ' + erreur.message;
            exportPossible(false);
        }
    }

    function ouvrir(fichier) {
        if (!fichier || !fichier.type.startsWith('image/')) return;
        const lecteur = new FileReader();
        lecteur.onload = () => {
            Object.assign(etat, { source: lecteur.result, nom: fichier.name, clics: [], cadre: null, coins: [], mode: null });
            recalculer();
        };
        lecteur.readAsDataURL(fichier);
    }

    $('fichier').onchange = e => ouvrir(e.target.files[0]);
    const depot = $('depot');
    depot.ondragover = e => { e.preventDefault(); depot.classList.add('survol'); };
    depot.ondragleave = () => depot.classList.remove('survol');
    depot.ondrop = e => { e.preventDefault(); depot.classList.remove('survol'); ouvrir(e.dataTransfer.files[0]); };
    document.addEventListener('paste', e => ouvrir([...e.clipboardData.files][0]));

    for (const id of ['choix-vaisseau', 'fond', 'symetrie', 'dessous', 'inverser', 'proportions', 'niveaux', 'seuil-auto']) $(id).onchange = recalculer;
    $('seuil').onchange = () => { $('seuil-auto').checked = false; recalculer(); };
    $('seuil').oninput = () => { $('valeur-seuil').textContent = $('seuil').value; };

    // Deux clics sur l'image : le nez, puis la poupe (sinon l'axe est trouvé tout seul)
    $('placer-axe').onclick = () => { etat.mode = 'axe'; etat.clics = []; $('etat').textContent = 'Clique sur le NEZ du vaisseau, puis sur le MILIEU DE LA POUPE.'; };
    $('axe-auto').onclick = () => { etat.mode = null; etat.clics = []; recalculer(); };
    // Recadrage : deux coins opposés (image entière affichée le temps de les choisir)
    $('recadrer').onclick = async () => {
        if (!etat.source) return;
        Object.assign(etat, { cadre: null, coins: [], clics: [] });
        await recalculer();
        etat.mode = 'cadre';
        $('etat').textContent = 'Clique sur deux coins opposés autour du vaisseau.';
    };
    $('vue-source').onclick = e => {
        if (!etat.mode || !etat.resultat) return;
        // Position du clic dans l'image (le canvas garde ses proportions : object-fit contain)
        const boite = e.target.getBoundingClientRect();
        const ratio = Math.min(boite.width / e.target.width, boite.height / e.target.height);
        const marge = [(boite.width - e.target.width * ratio) / 2, (boite.height - e.target.height * ratio) / 2];
        const x = (e.clientX - boite.left - marge[0]) / ratio, y = (e.clientY - boite.top - marge[1]) / ratio;
        if (etat.mode === 'cadre') {
            etat.coins.push([x / e.target.width, y / e.target.height]);
            if (etat.coins.length === 2) {
                etat.cadre = [...etat.coins[0], ...etat.coins[1]];
                etat.mode = null; etat.coins = [];
                recalculer();
            }
            return;
        }
        etat.clics.push([x, y]);
        if (etat.clics.length === 2) { etat.mode = null; recalculer(); } else dessinerSource();
    };

    $('installer').onclick = async () => {
        const plan = etat.resultat?.plan;
        if (!plan) return;
        if (!confirmation) {                         // deux clics : l'ancien plan va être remplacé
            $('installer').textContent = `Remplacer le plan de ${plan.nom} ?`;
            confirmation = setTimeout(desarmerInstallation, 4000);
            return;
        }
        desarmerInstallation();
        $('installer').disabled = true;
        $('etat').textContent = 'Installation…';
        const r = await bord.installerPlan(plan.id, A.fichier(plan, etat.nom), plan).catch(e => ({ erreur: e.message || String(e) }));
        $('installer').disabled = false;
        $('etat').textContent = r?.ok
            ? `Plan de ${plan.nom} installé` + (r.sauvegarde ? ` (ancien plan : ${r.sauvegarde}).` : '.')
            : `Installation impossible : ${r?.erreur || 'erreur inconnue'}`;
    };

    $('telecharger').onclick = () => {
        const plan = etat.resultat?.plan;
        if (!plan) return;
        const lien = document.createElement('a');
        lien.href = URL.createObjectURL(new Blob([A.fichier(plan, etat.nom)], { type: 'text/javascript' }));
        lien.download = plan.id + '.js';
        lien.click();
        setTimeout(() => URL.revokeObjectURL(lien.href), 5000);
        $('etat').textContent = `Fichier ${plan.id}.js téléchargé : place-le dans Frontend/vaisseaux/ (il remplace l'ancien plan).`;
    };
})();
