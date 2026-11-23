/* =====================================================================
   COVAS — Réglages (icône d'engrenage du bandeau)
   Onglets : énergie, commandes (reglages_commandes.js), son (reglages_son.js), studio vocal,
   hangar des hologrammes, atelier des plans.

   Énergie : répartition de chaque mode, par défaut ou par vaisseau. Les valeurs sont en
   demi-pips, comme dans le jeu : [SYS, MOT, ARM], total 12. Chaque changement est enregistré
   tout seul par le backend (module/reglages.py).

   Studio, hangar et atelier affichent les pages existantes (?integre) dans un cadre. Le studio
   tourne dans son propre processus (module/pont_studio.py) : son micro n'est ouvert que tant
   que son onglet est affiché, et l'écoute du COVAS est en pause pendant ce temps.
   ===================================================================== */
window.COVAS_REGLAGES = (() => {
    'use strict';

    const LIGNES = ['Systèmes', 'Moteurs', 'Armes'];
    const DELAI_ENVOI = 250;          // ms : un glissé ne déclenche qu'un enregistrement
    const DELAI_CONFIRMATION = 3000;
    const MODES_PERSO_MAX = 12;
    const LONGUEUR_NOM = 24;

    let doc = null;
    let profil = 'defaut';            // 'defaut' ou type de vaisseau en cours d'édition
    let vaisseau = '';                // type du vaisseau piloté (minuscules)
    let pipsJeu = null;
    let noms = {};
    let envoyer = () => false;
    let gresiller = () => {};                       // parasites de changement d'écran (interface.js)
    let lancerAction = () => {};
    let majPlan = () => {};
    let rev = 0, minuterie = 0, nonEnvoye = false;
    let aNettoyer = false;            // fenêtre ouverte depuis le dernier nettoyage

    const $ = id => document.getElementById(id);
    const egaux = (a, b) => !!a && !!b && a.length === b.length && a.every((v, i) => v === b[i]);
    const enPips = v => (v / 2).toLocaleString('fr-FR');
    const nomVaisseau = type => noms[type] || type;
    const ouvert = () => $('fenetre-reglages').open;

    function creer(balise, classe, texte) {
        const el = document.createElement(balise);
        if (classe) el.className = classe;
        if (texte != null) el.textContent = texte;
        return el;
    }

    function bouton(classe, texte, titre) {
        const b = creer('button', classe, texte);
        b.type = 'button';
        if (titre) b.title = titre;
        return b;
    }

    /** Deux clics pour ce qui efface quelque chose. */
    function aConfirmer(b, action) {
        const libelle = b.textContent;
        let armee = 0;
        const desarmer = () => { clearTimeout(armee); armee = 0; b.textContent = libelle; b.classList.remove('arme'); };
        b.onclick = () => {
            if (armee) { desarmer(); action(); return; }
            b.textContent = 'Confirmer ?';
            b.classList.add('arme');
            armee = setTimeout(desarmer, DELAI_CONFIRMATION);
        };
    }

    // ----------------------------------------------------------------
    //  DONNÉES
    // ----------------------------------------------------------------
    const profilEffectif = () => (vaisseau && doc.pips.vaisseaux[vaisseau] ? vaisseau : 'defaut');
    const valeursDe = (id, nomProfil) => doc.pips.vaisseaux[nomProfil]?.[id] || doc.pips.defaut[id];
    const valeurs = id => valeursDe(id, profil);
    const estPropre = id => profil !== 'defaut' && !!doc.pips.vaisseaux[profil]?.[id];

    /** Change une ligne ; les deux autres se partagent le reste en gardant leur proportion. */
    function repartir(origine, ligne, valeur) {
        const [a, b] = [0, 1, 2].filter(i => i !== ligne);
        const reste = 12 - valeur;
        const somme = origine[a] + origine[b];
        const voulu = somme ? Math.round(reste * origine[a] / somme) : Math.round(reste / 2);
        const pourA = Math.max(Math.max(0, reste - 8), Math.min(8, reste, voulu));
        const resultat = [];
        resultat[ligne] = valeur;
        resultat[a] = pourA;
        resultat[b] = reste - pourA;
        return resultat;
    }

    function fixer(id, pips) {
        if (profil === 'defaut') doc.pips.defaut[id] = pips;
        else if (egaux(pips, doc.pips.defaut[id])) delete doc.pips.vaisseaux[profil][id];   // revient à l'héritage
        else doc.pips.vaisseaux[profil][id] = pips;
        planifierEnvoi();
    }

    function nomLibre(nom, id) {
        const propre = nom.trim().replace(/\s+/g, ' ');
        const pris = doc.pips.modes.some(m => m.id !== id && m.nom.toLocaleLowerCase('fr') === propre.toLocaleLowerCase('fr'));
        return propre && !pris ? propre : null;
    }

    // ----------------------------------------------------------------
    //  ENREGISTREMENT
    // ----------------------------------------------------------------
    function etatEnvoi(texte, type = '') {
        const el = $('reglages-etat');
        el.textContent = texte;
        el.dataset.type = type;
    }

    function envoyerMaintenant() {
        clearTimeout(minuterie);
        minuterie = 0;
        nonEnvoye = !envoyer(JSON.parse(JSON.stringify(doc)), rev);
        if (nonEnvoye) etatEnvoi('Hors ligne : enregistré au retour de la liaison', 'attention');
    }

    function planifierEnvoi() {
        rev = Math.max(Date.now(), rev + 1);
        nonEnvoye = true;
        etatEnvoi('Enregistrement…');
        clearTimeout(minuterie);
        minuterie = setTimeout(envoyerMaintenant, DELAI_ENVOI);
    }

    function recevoir({ reglages, rev: recue, erreur }) {
        if (recue != null && recue < rev) return;              // écho d'un envoi déjà dépassé
        if (recue == null && nonEnvoye && doc) { envoyerMaintenant(); return; }   // liaison revenue
        const echo = recue != null && recue === rev;
        doc = reglages;
        if (recue != null) rev = recue;
        if (echo) nonEnvoye = false;
        if (erreur) etatEnvoi(erreur, 'alerte');
        else if (echo) etatEnvoi('Enregistré', 'ok');
        if (profil !== 'defaut' && !doc.pips.vaisseaux[profil]) profil = 'defaut';
        if (echo) { rendreRapides(); window.COVAS_COMMANDES?.synchroniser(); return; }   // l'écran est déjà à jour
        rendre();
    }

    // ----------------------------------------------------------------
    //  RENDU
    // ----------------------------------------------------------------
    function rendreProfils() {
        const lignes = ['defaut', ...Object.keys(doc.pips.vaisseaux).sort((a, b) => nomVaisseau(a).localeCompare(nomVaisseau(b), 'fr'))];
        $('reglages-profils').replaceChildren(...lignes.map(cle => {
            const li = creer('li');
            const b = bouton('profil', cle === 'defaut' ? 'Par défaut' : nomVaisseau(cle));
            b.setAttribute('aria-pressed', String(cle === profil));
            if (cle !== 'defaut') {
                const n = Object.keys(doc.pips.vaisseaux[cle]).length;
                if (n) b.append(creer('small', '', String(n)));
            }
            if (cle === profilEffectif()) { b.classList.add('en-vol'); b.title = 'Profil utilisé par le vaisseau actuel'; }
            b.onclick = () => { profil = cle; rendre(); };
            li.append(b);
            return li;
        }));

        const ajoutActuel = $('reglages-ajouter-actuel');
        ajoutActuel.hidden = !vaisseau || !noms[vaisseau] || !!doc.pips.vaisseaux[vaisseau];
        if (!ajoutActuel.hidden) ajoutActuel.textContent = `+ ${nomVaisseau(vaisseau)} (actuel)`;

        const libres = Object.keys(noms).filter(t => !doc.pips.vaisseaux[t]).sort((a, b) => noms[a].localeCompare(noms[b], 'fr'));
        const choix = $('reglages-choix');
        const garde = choix.value;
        choix.replaceChildren(...libres.map(t => { const o = creer('option', '', noms[t]); o.value = t; return o; }));
        if (libres.includes(garde)) choix.value = garde;
        $('reglages-ajout').hidden = !libres.length;
    }

    function rendreTete() {
        const defaut = profil === 'defaut';
        $('reglages-profil-nom').textContent = defaut ? 'Par défaut' : nomVaisseau(profil);
        const n = defaut ? 0 : Object.keys(doc.pips.vaisseaux[profil]).length;
        $('reglages-profil-note').textContent = defaut
            ? 'Utilisé par tous les vaisseaux sans réglage propre.'
            : n ? `${n} mode${n > 1 ? 's' : ''} personnalisé${n > 1 ? 's' : ''}, les autres suivent le profil par défaut.`
                : 'Suit le profil par défaut. Change une valeur pour la personnaliser.';
        $('reglages-retirer').hidden = defaut;
    }

    function majCarte(article) {
        const id = article.dataset.mode;
        const mode = doc.pips.modes.find(m => m.id === id);
        if (!mode) return;
        const v = valeurs(id);
        article.querySelectorAll('.pip-curseur').forEach((curseur, i) => {
            curseur.value = v[i];
            curseur.style.setProperty('--v', v[i] / 8);
            curseur.setAttribute('aria-valuetext', `${enPips(v[i])} pip${v[i] > 2 ? 's' : ''}`);
            curseur.closest('.carte-ligne').querySelector('b').textContent = enPips(v[i]);
        });
        const propre = estPropre(id);
        const origine = article.querySelector('.carte-origine');
        origine.textContent = profil === 'defaut' ? '' : propre ? 'Personnalisé' : 'Par défaut';
        origine.dataset.propre = String(propre);
        article.querySelector('.carte-retour').hidden = !propre;
        article.querySelector('.carte-declencheur').textContent = mode.declencheur;

        const enEffet = profil === profilEffectif();
        const appliquer = article.querySelector('.carte-appliquer');
        if (appliquer) {
            appliquer.disabled = !enEffet;
            appliquer.title = enEffet ? 'Envoie cette répartition au jeu' : 'Ce profil n\'est pas celui du vaisseau actuel';
        }
        article.classList.toggle('en-cours', enEffet && egaux(v, pipsJeu));
    }

    function carte(mode) {
        const article = creer('article', 'carte-mode');
        article.dataset.mode = mode.id;

        const tete = creer('header', 'carte-tete');
        if (mode.base) {
            tete.append(creer('h4', '', mode.nom));
        } else {
            const champ = creer('input', 'carte-nom');
            champ.type = 'text';
            champ.maxLength = LONGUEUR_NOM;
            champ.value = mode.nom;
            champ.setAttribute('aria-label', 'Nom du mode');
            champ.oninput = () => {
                const propre = nomLibre(champ.value, mode.id);
                champ.classList.toggle('invalide', !propre);
                if (!propre) return;
                const courant = doc.pips.modes.find(m => m.id === mode.id);
                courant.nom = propre;
                courant.declencheur = `« mode ${propre.toLowerCase()} »`;
                majCarte(article);
                rendreRapides();
                planifierEnvoi();
            };
            champ.onblur = () => {
                champ.value = doc.pips.modes.find(m => m.id === mode.id)?.nom ?? champ.value;
                champ.classList.remove('invalide');
            };
            tete.append(champ);
        }
        const retour = bouton('carte-retour', '↺', 'Revenir à la valeur par défaut');
        retour.setAttribute('aria-label', `${mode.nom} : revenir à la valeur par défaut`);
        retour.onclick = () => { delete doc.pips.vaisseaux[profil][mode.id]; planifierEnvoi(); majCarte(article); rendreProfils(); rendreTete(); majActifs(); };
        tete.append(creer('span', 'carte-origine'), retour);
        article.append(tete, creer('p', 'carte-declencheur'));

        let depart = null;                // répartition au début du glissé : les proportions ne s'usent pas
        LIGNES.forEach((libelle, i) => {
            const ligne = creer('label', 'carte-ligne');
            const curseur = creer('input', 'pip-curseur');
            curseur.type = 'range';
            curseur.min = 0;
            curseur.max = 8;
            curseur.step = 1;
            curseur.setAttribute('aria-label', `${mode.nom}, ${libelle}`);
            curseur.oninput = () => {
                depart ??= [...valeurs(mode.id)];
                fixer(mode.id, repartir(depart, i, Number(curseur.value)));
                majCarte(article);
                rendreProfils();
                rendreTete();
                majActifs();
            };
            curseur.onchange = () => { depart = null; };
            ligne.append(creer('span', '', libelle), curseur, creer('b'));
            article.append(ligne);
        });

        const pied = creer('footer', 'carte-pied');
        if (mode.applicable) {
            const appliquer = bouton('carte-appliquer', 'Appliquer');
            appliquer.onclick = () => { if (minuterie) envoyerMaintenant(); lancerAction(mode.id); };
            pied.append(appliquer);
        }
        if (!mode.base) {
            const supprimer = bouton('carte-supprimer', 'Supprimer');
            aConfirmer(supprimer, () => {
                doc.pips.modes = doc.pips.modes.filter(m => m.id !== mode.id);
                delete doc.pips.defaut[mode.id];
                Object.values(doc.pips.vaisseaux).forEach(v => delete v[mode.id]);
                planifierEnvoi();
                rendre();
            });
            pied.append(supprimer);
        }
        if (pied.children.length) article.append(pied);
        majCarte(article);
        return article;
    }

    function rendreGrille() {
        const cartes = doc.pips.modes.map(carte);
        if (doc.pips.modes.filter(m => !m.base).length < MODES_PERSO_MAX) {
            const nouveau = bouton('carte-nouvelle', '+ Nouveau mode');
            nouveau.onclick = ajouterMode;
            cartes.push(nouveau);
        }
        $('reglages-grille').replaceChildren(...cartes);
    }

    function rendreRapides() {
        const conteneur = $('modes-rapides');
        if (!conteneur || !doc) return;
        conteneur.replaceChildren(...doc.pips.modes.filter(m => m.applicable).map(mode => {
            const b = bouton('', mode.nom);
            b.dataset.mode = mode.id;
            b.onclick = () => lancerAction(mode.id);
            return b;
        }));
        majActifs();
    }

    /** Met en évidence les modes qui correspondent à la répartition actuelle du vaisseau. */
    function majActifs() {
        if (!doc) return;
        const effectif = profilEffectif();
        document.querySelectorAll('#modes-rapides button').forEach(b => {
            const v = valeursDe(b.dataset.mode, effectif);
            b.setAttribute('aria-pressed', String(egaux(v, pipsJeu)));
            b.title = `${enPips(v[0])} SYS · ${enPips(v[1])} MOT · ${enPips(v[2])} ARM`;
        });
        if (ouvert()) document.querySelectorAll('.carte-mode').forEach(a => a.classList.toggle('en-cours', profil === effectif && egaux(valeurs(a.dataset.mode), pipsJeu)));
    }

    function rendre() {
        if (!doc) return;
        $('reglages-attente').hidden = true;
        $('reglages-corps').hidden = false;
        rendreRapides();
        if (!ouvert()) return;
        rendreProfils();
        rendreTete();
        rendreGrille();
        window.COVAS_COMMANDES?.rendre();
        window.COVAS_SON?.rendre();
    }

    // ----------------------------------------------------------------
    //  ACTIONS
    // ----------------------------------------------------------------
    function ajouterVaisseau(type) {
        if (!type || !doc) return;
        doc.pips.vaisseaux[type] ??= {};
        profil = type;
        planifierEnvoi();
        rendre();
        rendreRapides();
    }

    function ajouterMode() {
        let n = doc.pips.modes.filter(m => !m.base).length + 1;
        while (!nomLibre(`Perso ${n}`, '')) n++;
        const id = 'mode_perso_' + Date.now().toString(36);
        doc.pips.modes.push({ id, nom: `Perso ${n}`, base: false, declencheur: `« mode perso ${n} »`, applicable: true });
        doc.pips.defaut[id] = [4, 4, 4];
        planifierEnvoi();
        rendre();
        const champ = document.querySelector(`.carte-mode[data-mode="${id}"] .carte-nom`);
        champ?.focus();
        champ?.select();
    }

    function ouvrir() {
        if (doc && vaisseau && doc.pips.vaisseaux[vaisseau]) profil = vaisseau;
        $('fenetre-reglages').showModal();
        gresiller();
        aNettoyer = true;
        $('reglages-attente').hidden = !!doc;
        $('reglages-corps').hidden = !doc;
        rendre();
        afficherOnglet(onglet);
    }

    /** Sans attendre l'évènement « close » : le navigateur le retarde tant que la fenêtre n'est
        pas affichée, et le micro du studio doit se couper quoi qu'il arrive. */
    function fermer() {
        $('fenetre-reglages').close();
        gresiller();
        apresFermeture();
    }

    function apresFermeture() {
        window.COVAS_COMMANDES?.annuler();
        window.COVAS_SON?.quitter();
        if (!aNettoyer) return;
        aNettoyer = false;
        if (minuterie) envoyerMaintenant();
        if (onglet === 'studio') quitterStudio();
        retirerCadre('hangar');                     // 49 hologrammes : inutile de les garder en vol
    }

    // ----------------------------------------------------------------
    //  ONGLETS
    // ----------------------------------------------------------------
    const ATTENTE_ARRET_STUDIO = 5 * 60 * 1000;     // onglet quitté : la prise non gardée reste 5 min
    const NIVEAU_VEILLE = { niveau: -120, crete: -120, enregistre: false, duree: 0, plein: false, ouvert: false };
    const TITRES = { studio: 'Studio vocal', hangar: 'Hangar des hologrammes', atelier: 'Atelier des plans' };
    const cadres = {};
    const studio = { actif: false, file: Promise.resolve(), minuterie: 0 };
    let onglet = 'energie';

    const apiApp = () => window.pywebview?.api;

    function urlCadre(nom) {
        const type = vaisseau && window.COVAS_HOLOGRAMMES?.connu(vaisseau) ? vaisseau : '';
        if (nom === 'hangar') return 'hangar.html?integre' + (type ? '#' + type : '');
        if (nom === 'atelier') return 'atelier.html?integre' + (type ? '&vaisseau=' + type : '');
        return 'studio.html?integre';
    }

    function chargerCadre(nom) {
        if (!cadres[nom]) {
            const cadre = creer('iframe', 'cadre-reglages');
            cadre.title = TITRES[nom];
            cadre.src = urlCadre(nom);
            document.querySelector(`[data-panneau="${nom}"]`).append(cadre);
            cadres[nom] = cadre;
        }
        cadres[nom].hidden = false;
        cadres[nom].focus();
    }

    function retirerCadre(nom) {
        cadres[nom]?.remove();
        delete cadres[nom];
    }

    function noteStudio(texte) {
        $('reglages-studio-note').textContent = texte || '';
        $('reglages-studio-note').hidden = !texte;
        if (texte && cadres.studio) cadres.studio.hidden = true;
    }

    /** Ouvrir et quitter l'onglet s'exécutent dans l'ordre, même sur des clics rapprochés. */
    function enchainerStudio(action) {
        studio.file = studio.file.then(action).catch(erreur => console.error('Studio vocal', erreur));
    }

    function entrerStudio() {
        clearTimeout(studio.minuterie);
        const api = apiApp();
        if (!api?.studio_ouvrir) {
            noteStudio('Le studio vocal s\'utilise dans l\'application COVAS, ou avec STUDIO VOCAL.bat.');
            return;
        }
        enchainerStudio(async () => {
            if (onglet !== 'studio' || !ouvert()) return;
            const r = await api.studio_ouvrir();
            if (r?.erreur) { noteStudio(r.erreur); return; }
            noteStudio('');
            const dejaCharge = !!cadres.studio;
            studio.actif = true;
            etatEnvoi('Écoute du COVAS en pause', 'attention');
            if (dejaCharge) await api.studio_appel('demarrer', []);
            chargerCadre('studio');
        });
    }

    function quitterStudio() {
        etatEnvoi('');
        enchainerStudio(async () => {
            if (!studio.actif || (onglet === 'studio' && ouvert())) return;
            studio.actif = false;
            cadres.studio?.contentWindow?.suspendreStudio?.();
            await apiApp().studio_veille();
            programmerArretStudio();
        });
    }

    /** Whisper et le studio ne restent pas en mémoire pendant le vol. Un lot en cours va à son terme. */
    function programmerArretStudio() {
        clearTimeout(studio.minuterie);
        studio.minuterie = setTimeout(() => enchainerStudio(async () => {
            if (studio.actif) return;
            const travail = await apiApp().studio_appel('travail', []);
            if (travail?.en_cours) { programmerArretStudio(); return; }
            await apiApp().studio_fermer();
            retirerCadre('studio');
        }), ATTENTE_ARRET_STUDIO);
    }

    /** Appels de la page du studio. Son vumètre interroge sans arrêt : rien à demander en veille. */
    function appelStudio(nom, args) {
        if (nom === 'niveau' && !studio.actif) return Promise.resolve(NIVEAU_VEILLE);
        return apiApp().studio_appel(nom, args);
    }

    function afficherOnglet(nom) {
        const avant = onglet;
        if (avant !== nom) gresiller();
        onglet = nom;
        document.querySelectorAll('[data-reglage]').forEach(b => {
            const choisi = b.dataset.reglage === nom;
            b.setAttribute('aria-selected', String(choisi));
            b.tabIndex = choisi ? 0 : -1;
        });
        document.querySelectorAll('[data-panneau]').forEach(p => { p.hidden = p.dataset.panneau !== nom; });
        if (avant === 'studio' && nom !== 'studio') quitterStudio();
        if (avant === 'commandes' && nom !== 'commandes') window.COVAS_COMMANDES?.annuler();
        if (avant === 'son' && nom !== 'son') window.COVAS_SON?.quitter();
        if (nom === 'studio') entrerStudio();
        else if (nom === 'commandes') window.COVAS_COMMANDES?.rendre();
        else if (nom === 'son') window.COVAS_SON?.entrer();
        else if (nom !== 'energie') chargerCadre(nom);
    }

    function installerOnglets() {
        const boutons = [...document.querySelectorAll('[data-reglage]')];
        boutons.forEach((b, i) => {
            b.onclick = () => afficherOnglet(b.dataset.reglage);
            b.onkeydown = e => {
                const pas = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
                if (!pas) return;
                e.preventDefault();
                const suivant = boutons[(i + pas + boutons.length) % boutons.length];
                afficherOnglet(suivant.dataset.reglage);
                suivant.focus();
            };
        });
    }

    // ----------------------------------------------------------------
    //  PLANS DE L'ATELIER
    // ----------------------------------------------------------------
    const peutInstallerPlan = () => !!apiApp()?.installer_plan;

    async function installerPlan(id, contenu, plan) {
        const r = await apiApp().installer_plan(id, contenu);
        if (!r?.ok) return r || { erreur: 'installation impossible' };
        // Le navigateur garde les plans en cache : on lui fait relire celui-ci
        await fetch(`vaisseaux/${encodeURIComponent(id)}.js`, { cache: 'reload' }).catch(() => {});
        majPlan(plan);
        retirerCadre('hangar');                     // il se recharge à sa prochaine ouverture
        return r;
    }

    // ----------------------------------------------------------------
    //  LIEN AVEC L'INTERFACE
    // ----------------------------------------------------------------
    function majVaisseau(type) {
        const nouveau = (type || '').toLowerCase();
        if (nouveau === vaisseau) return;
        vaisseau = nouveau;
        if (!doc) return;
        majActifs();
        if (ouvert()) { rendreProfils(); document.querySelectorAll('.carte-mode').forEach(majCarte); }
    }

    function majPips(pips) {
        if (egaux(pips, pipsJeu)) return;
        pipsJeu = pips ? [...pips] : null;
        majActifs();
    }

    /** Répartition d'un mode pour le vaisseau actuel (utilisé par la simulation). */
    function pipsPour(id) {
        if (!doc || !doc.pips.defaut[id]) return null;
        return [...valeursDe(id, profilEffectif())];
    }

    function installer(options) {
        ({ envoyer, action: lancerAction, noms, majPlan, gresiller } = options);
        window.COVAS_COMMANDES?.installer({ doc: () => doc, changer: planifierEnvoi, etat: etatEnvoi, bouton, aConfirmer });
        window.COVAS_SON?.installer({ doc: () => doc, changer: planifierEnvoi });
        $('bouton-reglages').onclick = ouvrir;
        $('accueil-reglages').onclick = ouvrir;
        installerOnglets();
        $('reglages-fermer').onclick = fermer;
        $('fenetre-reglages').addEventListener('click', e => { if (e.target === $('fenetre-reglages')) fermer(); });
        // Dans le studio, Échap annule la prise : il ne doit pas fermer la fenêtre en plus
        // Pareil pendant le choix d'une touche : Échap annule seulement ce choix
        $('fenetre-reglages').addEventListener('cancel', e => {
            if (onglet === 'studio' || window.COVAS_COMMANDES?.enCapture()) e.preventDefault();
            else gresiller();
        });
        $('fenetre-reglages').addEventListener('close', () => { if (!ouvert()) apresFermeture(); });   // Échap
        $('reglages-ajouter-actuel').onclick = () => ajouterVaisseau(vaisseau);
        $('reglages-ajout').onsubmit = e => { e.preventDefault(); ajouterVaisseau($('reglages-choix').value); };
        aConfirmer($('reglages-retirer'), () => {
            delete doc.pips.vaisseaux[profil];
            profil = 'defaut';
            planifierEnvoi();
            rendre();
        });
    }

    return { installer, recevoir, majVaisseau, majPips, pipsPour, appelStudio, peutInstallerPlan, installerPlan };
})();
