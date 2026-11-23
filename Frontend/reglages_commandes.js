/* =====================================================================
   COVAS — Réglages, onglet Commandes
   Touches envoyées au jeu et séquences de menus (apontage, décollage, ravitaillement...).

   Une touche choisie ici ne change que ce que le COVAS envoie : le fichier de commandes du jeu
   n'est jamais écrit. Les noms de touches sont ceux de pydirectinput, c'est-à-dire un emplacement
   physique : event.code donne le bon résultat sur un clavier AZERTY comme QWERTY.
   Tout est revérifié par le backend (module/pilotage/commandes.py).
   ===================================================================== */
window.COVAS_COMMANDES = (() => {
    'use strict';

    const MODIFICATEURS = { ControlLeft: 'ctrlleft', ShiftLeft: 'shiftleft', ShiftRight: 'shiftright', AltLeft: 'altleft' };
    const ORDRE_MODIFICATEURS = ['ctrlleft', 'shiftleft', 'shiftright', 'altleft'];
    const NON_ENVOYABLES = new Set(['ControlRight', 'AltRight']);
    const PAUSE_DEPART = 0.5;

    const CODES = {
        Space: 'space', Tab: 'tab', Enter: 'enter', NumpadEnter: 'enter', Backspace: 'backspace', CapsLock: 'capslock',
        Insert: 'insert', Delete: 'delete', Home: 'home', End: 'end', PageUp: 'pageup', PageDown: 'pagedown',
        ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right',
        Minus: '-', Equal: '=', BracketLeft: '[', BracketRight: ']', Backslash: '\\', Semicolon: ';', Quote: "'",
        Comma: ',', Period: '.', Slash: '/', Backquote: '`',
        NumpadAdd: 'add', NumpadSubtract: 'subtract', NumpadMultiply: 'multiply', NumpadDivide: 'divide', NumpadDecimal: 'decimal',
    };
    for (const lettre of 'ABCDEFGHIJKLMNOPQRSTUVWXYZ') CODES['Key' + lettre] = lettre.toLowerCase();
    for (let n = 0; n < 10; n++) { CODES['Digit' + n] = String(n); CODES['Numpad' + n] = 'numpad' + n; }
    for (let n = 1; n <= 20; n++) CODES['F' + n] = 'f' + n;

    const LIBELLES = {
        space: 'Espace', tab: 'Tab', enter: 'Entrée', backspace: 'Retour arrière', capslock: 'Verr. Maj',
        insert: 'Inser', delete: 'Suppr', home: 'Origine', end: 'Fin', pageup: 'Page préc.', pagedown: 'Page suiv.',
        up: '↑', down: '↓', left: '←', right: '→', esc: 'Échap',
        ctrlleft: 'Ctrl', ctrlright: 'Ctrl droit', shiftleft: 'Maj', shiftright: 'Maj droite', altleft: 'Alt', altright: 'Alt Gr',
        add: 'Pavé +', subtract: 'Pavé −', multiply: 'Pavé ×', divide: 'Pavé ÷', decimal: 'Pavé .',
    };
    // Ce qui est imprimé sur un clavier AZERTY à cet emplacement physique
    const AZERTY = { q: 'A', a: 'Q', w: 'Z', z: 'W', ';': 'M', m: ',', ',': ';', '.': ':', '/': '!', '[': '^', ']': '$', "'": 'ù', '\\': '*', '`': '²', '-': ')' };

    let lien = null;                  // { doc, changer, etat, bouton, aConfirmer }
    let vue = 'touches:vol';          // 'touches:<groupe>' ou 'sequence:<id>'
    let capture = null;
    let dernierRendu = '';

    const $ = id => document.getElementById(id);
    const doc = () => lien?.doc();
    const cat = () => doc()?.catalogue;
    const perso = () => doc().commandes;

    function creer(balise, classe, texte) {
        const el = document.createElement(balise);
        if (classe) el.className = classe;
        if (texte != null) el.textContent = texte;
        return el;
    }

    const visible = () => $('fenetre-reglages').open && !document.querySelector('[data-panneau="commandes"]').hidden;

    // ----------------------------------------------------------------
    //  TOUCHES
    // ----------------------------------------------------------------
    function nomTouche(id) {
        if (LIBELLES[id]) return LIBELLES[id];
        if (/^numpad\d$/.test(id)) return 'Pavé ' + id.slice(6);
        if (cat()?.azerty && AZERTY[id]) return AZERTY[id];
        return id.toUpperCase();
    }

    const nomCombinaison = v => (v ? [...v[1], v[0]].map(nomTouche).join(' + ') : 'Aucune');
    const cleCombinaison = v => (v ? [...v[1]].sort().concat(v[0]).join('+') : '');
    const memes = (a, b) => !!a && !!b && cleCombinaison(a) === cleCombinaison(b);
    const commandes = () => cat().groupes.flatMap(g => g.commandes);
    const commande = id => commandes().find(c => c.id === id);
    const effective = c => perso().touches[c.id] || c.jeu || c.secours;

    function fixerTouche(id, valeur) {
        const c = commande(id);
        if (!valeur || memes(valeur, c.jeu || c.secours)) delete perso().touches[id];
        else perso().touches[id] = valeur;
        lien.changer();
    }

    function etatLigne(c) {
        const propre = perso().touches[c.id];
        if (propre && c.jeu) return { texte: `Le jeu attend ${nomCombinaison(c.jeu)}`, type: 'attention' };
        if (propre) return { texte: 'À assigner aussi dans le jeu', type: 'attention' };
        if (c.jeu) return { texte: 'Lue dans le jeu', type: '' };
        if (c.secours) return { texte: 'Absente du fichier du jeu', type: 'attention' };
        return { texte: 'Aucune touche', type: 'alerte' };
    }

    function ligneTouche(c, groupe) {
        const li = creer('li', 'ligne-touche');
        li.append(creer('span', 'touche-nom', c.libelle));

        const valeur = lien.bouton('touche-valeur', nomCombinaison(effective(c)), 'Cliquer, puis appuyer sur la nouvelle touche');
        valeur.dataset.f = 'touche:' + c.id;
        valeur.setAttribute('aria-label', `${c.libelle} : ${nomCombinaison(effective(c))}. Changer la touche`);
        valeur.onclick = () => (capture?.id === c.id ? annuler() : demarrerCapture(c.id, valeur));
        li.append(valeur);

        const { texte, type } = etatLigne(c);
        const etat = creer('span', 'touche-etat', texte);
        etat.dataset.type = type;
        const autres = groupe.commandes.filter(x => x.id !== c.id && memes(effective(x), effective(c)));
        if (autres.length) etat.append(creer('small', '', `Aussi sur : ${autres.map(x => x.libelle).join(', ')}`));
        li.append(etat);

        const retour = lien.bouton('carte-retour', '↺', 'Revenir à la touche du jeu');
        retour.dataset.f = 'retour:' + c.id;
        retour.setAttribute('aria-label', `${c.libelle} : revenir à la touche du jeu`);
        retour.hidden = !perso().touches[c.id];
        retour.onclick = () => { fixerTouche(c.id, null); rendre(); };
        li.append(retour);
        return li;
    }

    function rendreTouches(groupe) {
        const propres = groupe.commandes.filter(c => perso().touches[c.id]);
        const tete = entete(groupe.nom, `Touches que le COVAS envoie au jeu${cat().fichier ? ` (lues dans ${cat().fichier})` : ''}. Le fichier du jeu n'est pas modifié : si tu changes une touche ici, donne-lui la même dans Options > Commandes.`);
        if (propres.length) {
            const tout = lien.bouton('', `Remettre les ${propres.length > 1 ? propres.length + ' touches' : 'touche'} du jeu`);
            lien.aConfirmer(tout, () => { propres.forEach(c => delete perso().touches[c.id]); lien.changer(); rendre(); });
            tete.append(tout);
        }
        const liste = creer('ul', 'liste-touches');
        liste.append(...groupe.commandes.map(c => ligneTouche(c, groupe)));
        $('commandes-contenu').replaceChildren(tete, liste);
    }

    // ----------------------------------------------------------------
    //  CAPTURE D'UNE TOUCHE
    // ----------------------------------------------------------------
    function demarrerCapture(id, bouton) {
        annuler();
        capture = { id, bouton, tenus: new Set() };
        bouton.textContent = 'Appuie sur une touche…';
        bouton.classList.add('ecoute');
        lien.etat('Échap pour annuler');
        window.addEventListener('keydown', surEnfoncee, true);
        window.addEventListener('keyup', surRelachee, true);
        window.addEventListener('pointerdown', surClic, true);
    }

    function finirCapture() {
        window.removeEventListener('keydown', surEnfoncee, true);
        window.removeEventListener('keyup', surRelachee, true);
        window.removeEventListener('pointerdown', surClic, true);
        capture = null;
    }

    /** Annule la capture en cours (Échap, clic ailleurs, onglet quitté, fenêtre fermée). */
    function annuler(message = '') {
        if (!capture) return;
        const { id, bouton } = capture;
        finirCapture();
        // Sans refaire la page : le clic qui annule doit encore atteindre le bouton visé
        bouton.classList.remove('ecoute');
        bouton.textContent = nomCombinaison(effective(commande(id)));
        lien.etat(message, message ? 'attention' : '');
        synchroniser();
    }

    function valider(touche, modificateurs) {
        const { id } = capture;
        finirCapture();
        fixerTouche(id, [touche, ORDRE_MODIFICATEURS.filter(m => modificateurs.includes(m))]);
        rendre();
    }

    function surEnfoncee(event) {
        event.preventDefault();
        event.stopImmediatePropagation();
        if (event.repeat) return;
        if (event.code === 'Escape') { annuler(); return; }
        if (NON_ENVOYABLES.has(event.code)) { annuler('Alt Gr et Ctrl droit ne peuvent pas être envoyés au jeu'); return; }
        if (MODIFICATEURS[event.code]) { capture.tenus.add(MODIFICATEURS[event.code]); return; }
        const touche = CODES[event.code];
        if (!touche) { annuler('Cette touche ne peut pas être envoyée au jeu'); return; }
        if (capture.tenus.size > 2) { annuler('Deux modificateurs au plus'); return; }
        valider(touche, [...capture.tenus]);
    }

    /** Maj, Ctrl ou Alt relâché sans autre touche : c'est lui, la touche voulue. */
    function surRelachee(event) {
        event.preventDefault();
        event.stopImmediatePropagation();
        const modificateur = MODIFICATEURS[event.code];
        if (!modificateur || !capture.tenus.has(modificateur)) return;
        capture.tenus.delete(modificateur);
        valider(modificateur, [...capture.tenus]);
    }

    function surClic(event) {
        if (!capture.bouton.contains(event.target)) annuler();
    }

    // ----------------------------------------------------------------
    //  SÉQUENCES
    // ----------------------------------------------------------------
    const etapesDe = s => perso().sequences[s.id] ?? s.etapes;
    const estPause = etape => etape.startsWith('pause:');
    const egales = (a, b) => a.length === b.length && a.every((e, i) => e === b[i]);

    /** Appuis identiques qui se suivent : une seule ligne avec un compteur. Jamais pour les pauses. */
    function grouper(etapes) {
        const blocs = [];
        for (const etape of etapes) {
            const dernier = blocs[blocs.length - 1];
            if (dernier?.etape === etape && !estPause(etape)) dernier.n++;
            else blocs.push({ etape, n: 1 });
        }
        return blocs;
    }

    const aplatir = blocs => blocs.flatMap(b => Array(b.n).fill(b.etape));

    function fixerSequence(s, etapes) {
        if (etapes.length > cat().etapes_max) return;
        if (egales(etapes, s.etapes)) delete perso().sequences[s.id];
        else perso().sequences[s.id] = etapes;
        lien.changer();
        rendre();
    }

    function petitBouton(texte, titre, focus, desactive, action) {
        const b = lien.bouton('etape-bouton', texte, titre);
        b.setAttribute('aria-label', titre);
        b.dataset.f = focus;
        b.disabled = desactive;
        b.onclick = action;
        return b;
    }

    function ligneEtape(s, blocs, i, total) {
        const bloc = blocs[i];
        const pause = estPause(bloc.etape);
        const c = pause ? null : commande(bloc.etape);
        const li = creer('li', 'ligne-etape');
        li.append(creer('span', 'etape-rang', String(i + 1)));
        li.append(creer('span', 'touche-nom', pause ? 'Pause' : c.libelle));

        const milieu = creer('span', 'etape-milieu');
        const modifier = changement => { changement(); fixerSequence(s, aplatir(blocs)); };
        if (pause) {
            const champ = creer('input', 'etape-duree');
            champ.type = 'number';
            champ.min = cat().pause_min;
            champ.max = cat().pause_max;
            champ.step = 0.1;
            champ.value = bloc.etape.slice(6);
            champ.dataset.f = `duree:${i}`;
            champ.setAttribute('aria-label', `Étape ${i + 1} : durée de la pause en secondes`);
            champ.onchange = () => {
                const lue = Number(champ.value);
                const v = Number.isFinite(lue) ? Math.min(cat().pause_max, Math.max(cat().pause_min, lue)) : PAUSE_DEPART;
                modifier(() => { bloc.etape = `pause:${v.toFixed(1)}`; });
            };
            milieu.append(champ, creer('span', 'etape-unite', 's'));
        } else {
            const touche = effective(c);
            const nom = creer('kbd', touche ? 'etape-touche' : 'etape-touche manquante', touche ? nomCombinaison(touche) : 'Aucune touche');
            const moins = petitBouton('−', `Étape ${i + 1} : un appui de moins`, `moins:${i}`, bloc.n < 2, () => modifier(() => { bloc.n--; }));
            const plus = petitBouton('+', `Étape ${i + 1} : un appui de plus`, `plus:${i}`, total >= cat().etapes_max, () => modifier(() => { bloc.n++; }));
            milieu.append(nom, moins, creer('b', 'etape-nombre', '×' + bloc.n), plus);
        }
        li.append(milieu);

        const echanger = decalage => modifier(() => { [blocs[i], blocs[i + decalage]] = [blocs[i + decalage], blocs[i]]; });
        li.append(
            petitBouton('↑', `Étape ${i + 1} : monter`, `monter:${i}`, i === 0, () => echanger(-1)),
            petitBouton('↓', `Étape ${i + 1} : descendre`, `descendre:${i}`, i === blocs.length - 1, () => echanger(1)),
            petitBouton('×', `Étape ${i + 1} : retirer`, `retirer:${i}`, false, () => modifier(() => { blocs.splice(i, 1); })),
        );
        return li;
    }

    function formulaireAjout(s, etapes) {
        const form = creer('form', 'ajout-etape');
        const choix = creer('select');
        choix.id = 'commandes-etape-choix';
        choix.setAttribute('aria-label', 'Commande à ajouter à la séquence');
        for (const groupe of cat().groupes.filter(g => g.sequences)) {     // ni VRS ni pied à terre
            const lot = creer('optgroup');
            lot.label = groupe.nom;
            lot.append(...groupe.commandes.map(c => {
                const o = creer('option', '', `${c.libelle} (${nomCombinaison(effective(c))})`);
                o.value = c.id;
                return o;
            }));
            choix.append(lot);
        }
        choix.value = sessionChoix || 'ui_selection';
        choix.onchange = () => { sessionChoix = choix.value; };
        const plein = etapes.length >= cat().etapes_max;
        const ajouter = creer('button', '', 'Ajouter');
        ajouter.type = 'submit';
        ajouter.disabled = plein;
        ajouter.dataset.f = 'ajouter';
        const pause = lien.bouton('', '+ Pause', 'Attendre avant la suite (menu lent à s\'ouvrir)');
        pause.disabled = plein;
        pause.dataset.f = 'ajouter-pause';
        pause.onclick = () => fixerSequence(s, [...etapes, `pause:${PAUSE_DEPART.toFixed(1)}`]);
        form.onsubmit = e => { e.preventDefault(); sessionChoix = choix.value; fixerSequence(s, [...etapes, choix.value]); };
        form.append(choix, ajouter, pause);
        return form;
    }

    let sessionChoix = '';

    function rendreSequence(s) {
        const etapes = etapesDe(s);
        const delai = s.pause ? ` ${s.pause.toLocaleString('fr-FR')} s entre chaque appui.` : '';
        const tete = entete(s.nom, s.note + delai);
        if (perso().sequences[s.id]) {
            const retour = lien.bouton('', 'Revenir à l\'origine');
            lien.aConfirmer(retour, () => { delete perso().sequences[s.id]; lien.changer(); rendre(); });
            tete.append(retour);
        }
        const blocs = grouper(etapes);
        const liste = creer('ol', 'liste-etapes');
        liste.append(...blocs.map((_, i) => ligneEtape(s, blocs, i, etapes.length)));
        if (!blocs.length) liste.append(creer('li', 'vide', 'Séquence vide : ajoute une première étape.'));
        $('commandes-contenu').replaceChildren(tete, liste, formulaireAjout(s, etapes));
    }

    // ----------------------------------------------------------------
    //  RENDU
    // ----------------------------------------------------------------
    function entete(titre, note) {
        const tete = creer('div', 'reglages-profil');
        const texte = creer('div');
        texte.append(creer('h3', '', titre), creer('p', '', note));
        tete.append(texte);
        return tete;
    }

    function entreeMenu(cle, nom, compte) {
        const li = creer('li');
        const b = lien.bouton('profil', nom);
        b.dataset.f = 'menu:' + cle;
        b.setAttribute('aria-pressed', String(cle === vue));
        if (compte) b.append(creer('small', '', String(compte)));
        b.onclick = () => { annuler(); vue = cle; rendre(); };
        li.append(b);
        return li;
    }

    function rendreMenu() {
        const titreTouches = creer('h3', '', 'Touches');
        const touches = creer('ul');
        touches.append(...cat().groupes.map(g => entreeMenu('touches:' + g.id, g.nom, g.commandes.filter(c => perso().touches[c.id]).length)));
        const titreSequences = creer('h3', '', 'Séquences');
        const sequences = creer('ul');
        sequences.append(...cat().sequences.map(s => entreeMenu('sequence:' + s.id, s.nom, perso().sequences[s.id] ? 1 : 0)));
        $('commandes-menu').replaceChildren(titreTouches, touches, titreSequences, sequences);
    }

    /** Refaire la page ne doit pas faire perdre sa place au clavier. */
    function garderFocus(action) {
        const repere = document.activeElement?.dataset?.f;
        action();
        if (repere) document.querySelector(`#commandes-corps [data-f="${CSS.escape(repere)}"]:not(:disabled)`)?.focus();
    }

    function rendre() {
        if (!lien || capture || !visible()) return;
        const d = doc();
        const pret = !!d?.catalogue && !!d?.commandes;
        const attente = $('commandes-attente');
        attente.hidden = pret;
        attente.textContent = d ? 'Relance le COVAS pour utiliser cet onglet (il n\'est pas disponible en simulation).' : 'En attente de la liaison avec le COVAS…';
        $('commandes-corps').hidden = !pret;
        if (!pret) return;
        dernierRendu = JSON.stringify(d.commandes);
        garderFocus(() => {
            rendreMenu();
            const [type, id] = vue.split(':');
            const sequence = type === 'sequence' && cat().sequences.find(s => s.id === id);
            if (sequence) rendreSequence(sequence);
            else rendreTouches(cat().groupes.find(g => g.id === id) || cat().groupes[0]);
        });
    }

    /** Écho du backend : on ne redessine que s'il a corrigé quelque chose. */
    function synchroniser() {
        if (doc()?.commandes && JSON.stringify(doc().commandes) !== dernierRendu) rendre();
    }

    const installer = options => { lien = options; };
    const enCapture = () => !!capture;

    return { installer, rendre, synchroniser, annuler, enCapture };
})();
