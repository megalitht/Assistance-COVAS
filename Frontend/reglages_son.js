/* =====================================================================
   COVAS — Réglages > Son : sortie (casque, haut-parleurs), volume, micro.
   Le choix est enregistré avec les autres réglages (module/interface/reglages.py) et s'applique
   dès la prochaine réplique ou la prochaine écoute. Les listes de périphériques et les
   essais passent par l'application (window.pywebview.api.audio_*).
   ===================================================================== */
window.COVAS_SON = (() => {
    'use strict';

    const INTERVALLE_NIVEAU = 100;    // ms entre deux lectures du vumètre
    const PLANCHER_DB = -60;
    const SEUIL_SATURE = -3;
    const SEUIL_FAIBLE = -40;

    let outils = null;
    let liste = null;
    let chargement = null;
    let minuterie = 0;
    let testMicro = false;
    let sonActif = false;             // onglet affiché

    const $ = id => document.getElementById(id);
    const api = () => window.pywebview?.api;
    const reglage = () => outils?.doc()?.audio;

    function note(id, texte, type = '') {
        const el = $(id);
        el.textContent = texte || '';
        el.dataset.type = type;
    }

    function remplir(select, appareils, choisi, defaut) {
        const options = [];
        const premier = document.createElement('option');
        premier.value = '';
        premier.textContent = defaut ? `Windows par défaut (${defaut})` : 'Windows par défaut';
        options.push(premier);
        for (const { nom, libelle } of appareils) {
            const o = document.createElement('option');
            o.value = nom;
            o.textContent = libelle;
            options.push(o);
        }
        if (choisi && !appareils.some(a => a.nom === choisi)) {     // casque débranché : on garde son choix
            const o = document.createElement('option');
            o.value = choisi;
            o.textContent = `${choisi} (absent, Windows prend le relais)`;
            options.push(o);
        }
        select.replaceChildren(...options);
        select.value = choisi || '';
    }

    function rendre() {
        const r = reglage();
        if (!r) return;
        const dispo = !!api()?.audio_lister;
        $('son-volume').value = r.volume;
        $('son-volume').style.setProperty('--v', r.volume / 100);
        $('son-volume-valeur').textContent = `${r.volume} %`;
        for (const id of ['son-sortie', 'son-entree', 'son-tester-sortie', 'son-tester-micro', 'son-actualiser']) $(id).disabled = !dispo;
        if (!dispo) {
            note('son-note-sortie', 'Le choix des périphériques se fait dans l\'application COVAS.', 'attention');
            return;
        }
        if (!liste) return;
        if (document.activeElement !== $('son-sortie')) remplir($('son-sortie'), liste.sorties, r.sortie, liste.defaut_sortie);
        if (document.activeElement !== $('son-entree')) remplir($('son-entree'), liste.entrees, r.entree, liste.defaut_entree);
    }

    async function charger() {
        if (!api()?.audio_lister) { rendre(); return; }
        if (chargement) return chargement;
        $('son-actualiser').disabled = true;
        note('son-note-liste', 'Recherche des périphériques…');
        chargement = (async () => {
            try {
                liste = await api().audio_lister();
                note('son-note-liste', liste.erreur || '', liste.erreur ? 'alerte' : '');
            } catch (erreur) {
                note('son-note-liste', 'Périphériques illisibles', 'alerte');
                console.error('Son', erreur);
            } finally {
                chargement = null;
                $('son-actualiser').disabled = false;
                rendre();
            }
        })();
        return chargement;
    }

    function changer(cle, valeur) {
        const r = reglage();
        if (!r || r[cle] === valeur) return;
        r[cle] = valeur;
        outils.changer();
    }

    // ----------------------------------------------------------------
    //  ESSAIS
    // ----------------------------------------------------------------
    async function testerSortie() {
        const r = reglage();
        const b = $('son-tester-sortie');
        if (!r || b.disabled) return;
        b.disabled = true;
        note('son-note-sortie', 'Lecture de l\'essai…');
        try {
            const res = await api().audio_tester_sortie($('son-sortie').value || null, r.volume);
            if (res?.erreur) note('son-note-sortie', res.erreur, 'alerte');
            else note('son-note-sortie', 'Essai terminé.', 'ok');
        } catch (erreur) {
            note('son-note-sortie', 'Lecture impossible', 'alerte');
            console.error('Son', erreur);
        } finally {
            b.disabled = false;
        }
    }

    function afficherNiveau(db) {
        const part = Math.max(0, Math.min(1, (db - PLANCHER_DB) / -PLANCHER_DB));
        const barre = $('son-vumetre');
        barre.style.setProperty('--niveau', part);
        barre.dataset.etat = db >= SEUIL_SATURE ? 'sature' : db > SEUIL_FAIBLE ? 'bon' : 'faible';
    }

    function finTestMicro(texte = '', type = '') {
        clearTimeout(minuterie);
        minuterie = 0;
        testMicro = false;
        $('son-tester-micro').textContent = 'Tester le micro';
        $('son-tester-micro').setAttribute('aria-pressed', 'false');
        afficherNiveau(PLANCHER_DB);
        note('son-note-micro', texte, type);
    }

    async function lireNiveau() {
        if (!testMicro) return;
        try {
            const n = await api().audio_micro_niveau();
            if (!testMicro) return;
            if (!n?.actif) { finTestMicro('Test terminé. Le COVAS écoute de nouveau.'); return; }
            afficherNiveau(n.db);
        } catch (erreur) {
            console.error('Son', erreur);
        }
        if (testMicro) minuterie = setTimeout(lireNiveau, INTERVALLE_NIVEAU);
    }

    async function demarrerMicro() {
        testMicro = true;
        $('son-tester-micro').textContent = 'Arrêter le test';
        $('son-tester-micro').setAttribute('aria-pressed', 'true');
        note('son-note-micro', 'Parle : la barre doit bouger. Le COVAS n\'écoute pas pendant le test.');
        let res;
        try {
            res = await api().audio_micro_demarrer($('son-entree').value || null);
        } catch (erreur) {
            console.error('Son', erreur);
            res = { erreur: 'Micro inaccessible' };
        }
        if (!testMicro) {                 // onglet quitté pendant l'ouverture du micro
            api().audio_micro_arreter();
            return;
        }
        if (res?.erreur) { finTestMicro(res.erreur, 'alerte'); return; }
        lireNiveau();
    }

    function arreterMicro(texte) {
        if (!testMicro) return;
        finTestMicro(texte);
        api()?.audio_micro_arreter();
    }

    // ----------------------------------------------------------------
    //  LIEN AVEC LES RÉGLAGES
    // ----------------------------------------------------------------
    function entrer() {
        sonActif = true;
        rendre();
        if (!liste) charger();
    }

    /** Onglet quitté ou fenêtre fermée : le micro ne reste jamais ouvert. */
    function quitter() {
        sonActif = false;
        arreterMicro('');
    }

    function installer(options) {
        outils = options;
        $('son-sortie').onchange = e => { changer('sortie', e.target.value || null); note('son-note-sortie', ''); };
        $('son-entree').onchange = async e => {
            changer('entree', e.target.value || null);
            if (testMicro) { arreterMicro(''); await demarrerMicro(); }
        };
        $('son-volume').oninput = e => {
            const v = Number(e.target.value);
            e.target.style.setProperty('--v', v / 100);
            $('son-volume-valeur').textContent = `${v} %`;
            changer('volume', v);
        };
        $('son-tester-sortie').onclick = testerSortie;
        $('son-tester-micro').onclick = () => (testMicro ? arreterMicro('Test arrêté. Le COVAS écoute de nouveau.') : demarrerMicro());
        $('son-actualiser').onclick = charger;
    }

    return { installer, rendre: () => { if (sonActif) rendre(); }, entrer, quitter };
})();
