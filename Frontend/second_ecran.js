/* =====================================================================
   COVAS — Second écran
   - Téléphone ou tablette en portrait (largeur ≤ 760 px) : une colonne, des onglets en bas
     (Navigation, Combat, Vaisseau, Exploration, Commerce, Minage, Matériaux). Chaque panneau dit
     dans quel(s) onglet(s) il apparaît : data-mobile="navigation exploration". Quand le PC
     bascule en vue combat, le téléphone passe sur l'onglet Combat, puis revient.
   - Commandes depuis un autre appareil : le backend exige le code (PIN) de data/config.toml.
     La fenêtre du code s'ouvre avant d'envoyer une commande tant que l'appareil n'est pas autorisé.
   - PC : bouton « Second écran » (adresse, QR code, commande du pare-feu).
   Le son reste sur le PC : cette page ne joue rien.
   ===================================================================== */
window.COVAS_SECOND_ECRAN = (() => {
    'use strict';

    const LARGEUR_TELEPHONE = '(max-width: 760px)';
    const CLE_ONGLET = 'covas-onglet-telephone';
    const CLE_PIN = 'covas-pin';
    const $ = id => document.getElementById(id);
    const tous = selecteur => document.querySelectorAll(selecteur);
    const lire = (stockage, cle) => { try { return window[stockage].getItem(cle); } catch { return null; } };
    const garder = (stockage, cle, valeur) => {
        try { valeur == null ? window[stockage].removeItem(cle) : window[stockage].setItem(cle, valeur); } catch { /* stockage indisponible */ }
    };
    const ecrire = (cle, texte) => tous(`[data-v="${cle}"]`).forEach(el => { el.textContent = texte ?? ''; });

    const ecran = matchMedia(LARGEUR_TELEPHONE);
    let onglet = lire('localStorage', CLE_ONGLET) || 'navigation';
    let ongletAvantCombat = null;
    let modeActuel = 'nav';
    // Avant le message « acces » du backend (simulation, page locale) : tout est permis
    let acces = { local: true, autorise: true, pin_regle: true };
    let envoyer = () => false;          // fourni par interface.js : envoie un message au backend
    let pinEnvoye = null;               // code en cours de vérification (pour le retenir s'il est bon)

    // ----------------------------------------------------------------
    //  TÉLÉPHONE : ONGLETS
    // ----------------------------------------------------------------
    const surface = mode => ['vrs', 'pied', 'nomade'].includes(mode);

    /** Visibilité d'un élément marqué data-mobile, selon l'onglet et la vue demandée par le PC. */
    function visible(el) {
        const onglets = (el.dataset.mobile || '').split(/\s+/);
        if (!onglets.includes(onglet)) return false;
        if (el.classList.contains('vue-combat')) return modeActuel !== 'chasseur';
        if (el.classList.contains('vue-chasseur')) return modeActuel === 'chasseur';
        if (el.classList.contains('vue-surface')) return surface(modeActuel);
        // En surface, l'onglet Navigation montre la vue de surface à la place de celle du vaisseau
        if (onglet === 'navigation' && surface(modeActuel) && el.closest('.vue-nav')) return false;
        return true;
    }

    function appliquer() {
        const telephone = ecran.matches;
        document.body.toggleAttribute('data-telephone', telephone);
        if (!telephone) {
            tous('.hors-onglet').forEach(el => el.classList.remove('hors-onglet'));
            return;
        }
        document.body.dataset.onglet = onglet;
        tous('[data-mobile]').forEach(el => el.classList.toggle('hors-onglet', !visible(el)));
        // Une vue sans panneau marqué (combat, chasseur, surface) est marquée elle-même ; vue-nav
        // reste affichée, ses panneaux sont triés un par un.
        tous('.vue').forEach(vue => {
            if (vue.hasAttribute('data-mobile')) return;
            vue.classList.toggle('hors-onglet', !vue.querySelector('[data-mobile]:not(.hors-onglet)'));
        });
        tous('[data-onglet-tel]').forEach(bouton => {
            const cle = bouton.dataset.ongletTel;
            bouton.setAttribute('aria-selected', String(cle === onglet));
            // Un onglet sans aucun panneau (ajout à venir) reste caché
            bouton.hidden = !document.querySelector(`[data-mobile~="${cle}"]`);
        });
        // Le panneau Route a ses propres onglets : Exploration y montre l'exploration
        const sousOnglet = onglet === 'exploration' ? 'exploration' : onglet === 'navigation' ? 'tracee' : null;
        const actuel = document.querySelector('[data-onglet][aria-selected="true"]')?.dataset.onglet;
        if (sousOnglet && (onglet === 'exploration' || actuel === 'exploration') && actuel !== sousOnglet) {
            document.querySelector(`[data-onglet="${sousOnglet}"]`)?.click();
        }
    }

    function choisir(cle, automatique = false) {
        if (!automatique) ongletAvantCombat = null;      // le commandant a choisi : on n'y revient pas
        onglet = cle;
        garder('localStorage', CLE_ONGLET, cle);
        appliquer();
        if (!automatique) window.scrollTo({ top: 0 });
    }

    /** Appelé par interface.js à chaque changement de vue (nav, combat, chasseur, surface...). */
    function mode(nouveau) {
        const ancien = modeActuel;
        modeActuel = nouveau;
        const combat = m => m === 'combat' || m === 'chasseur';
        if (ecran.matches && combat(nouveau) && !combat(ancien) && onglet !== 'combat') {
            ongletAvantCombat = onglet;
            choisir('combat', true);
            return;
        }
        if (ecran.matches && !combat(nouveau) && combat(ancien) && ongletAvantCombat && onglet === 'combat') {
            const retour = ongletAvantCombat;
            ongletAvantCombat = null;
            choisir(retour, true);
            return;
        }
        appliquer();
    }

    // ----------------------------------------------------------------
    //  CODE (PIN) DES COMMANDES
    // ----------------------------------------------------------------
    function ouvrirPin(message = '') {
        const fenetre = $('fenetre-pin');
        if (!fenetre) return;
        const consigne = acces.pin_regle
            ? 'Les commandes envoyées depuis cet appareil demandent le code réglé sur le PC.'
            : 'Aucun code n\'est réglé sur le PC : depuis cet appareil, l\'interface se consulte sans commander. Règle « pin » dans Backend/data/config.toml.';
        ecrire('pin-consigne', consigne);
        $('champ-pin').disabled = $('pin-valider').disabled = !acces.pin_regle;
        afficherMessage(message);
        if (!fenetre.open) fenetre.showModal();
        if (acces.pin_regle) $('champ-pin').focus();
    }

    function afficherMessage(texte, etat = '') {
        ecrire('pin-message', texte);
        tous('[data-v="pin-message"]').forEach(el => { el.dataset.etat = etat; });
    }

    function envoyerPin(code) {
        pinEnvoye = code;
        if (!envoyer({ pin: code })) afficherMessage('Liaison avec le COVAS coupée.');
    }

    function resultatPin(message) {
        const fenetre = $('fenetre-pin');
        if (message.resultat === 'ok') {
            acces.autorise = true;
            if ($('pin-memoire')?.checked && pinEnvoye) garder('localStorage', CLE_PIN, pinEnvoye);
            pinEnvoye = null;
            afficherMessage('Code accepté. Appuie de nouveau sur la commande.', 'ok');
            if (fenetre?.open) setTimeout(() => fenetre.close(), 900);
            return;
        }
        acces.autorise = false;
        if (pinEnvoye && pinEnvoye === lire('localStorage', CLE_PIN)) garder('localStorage', CLE_PIN, null);
        pinEnvoye = null;
        const textes = {
            faux: 'Code incorrect.',
            bloque: `Trop d'erreurs : appareil bloqué${message.attente ? ` encore ${Math.ceil(message.attente / 60)} min` : ''}.`,
            absent: 'Aucun code n\'est réglé sur le PC (Backend/data/config.toml).',
        };
        if (fenetre?.open || message.resultat !== 'faux') ouvrirPin(textes[message.resultat] || 'Code refusé.');
    }

    /** Avant une commande : true si elle peut partir, sinon la fenêtre du code s'ouvre. */
    function autoriser() {
        if (acces.autorise) return true;
        ouvrirPin();
        return false;
    }

    // ----------------------------------------------------------------
    //  PC : ADRESSE, QR CODE ET PARE-FEU
    // ----------------------------------------------------------------
    function majSecondEcran(infos) {
        const bouton = $('bouton-second-ecran');
        if (bouton) bouton.hidden = !infos.actif;
        const liste = $('second-adresses');
        if (!liste) return;
        const adresses = infos.adresses || [];
        liste.replaceChildren(...(adresses.length ? adresses : ['Aucune adresse réseau trouvée : ce PC est-il connecté au Wi-Fi ou au réseau local ?'])
            .map((adresse, i) => {
                const li = document.createElement('li');
                li.textContent = adresse;
                if (!adresses.length) li.className = 'vide';
                else if (i) li.title = 'Autre carte réseau de ce PC (à essayer si la première adresse ne répond pas)';
                return li;
            }));
        const qr = $('second-qr');
        qr.replaceChildren();
        if (infos.qr) {
            // QR code fabriqué par le backend (bibliothèque segno) : un SVG sans espace de noms,
            // lu comme du HTML pour qu'il soit dessiné
            const svg = new DOMParser().parseFromString(infos.qr, 'text/html').querySelector('svg');
            if (svg) qr.append(document.importNode(svg, true));
        }
        ecrire('second-pin', infos.pin_regle
            ? 'Les boutons du téléphone demanderont le code (PIN) réglé dans Backend/data/config.toml.'
            : 'Aucun code (PIN) n\'est réglé : le téléphone pourra regarder, pas commander. Règle « pin » dans Backend/data/config.toml.');
        ecrire('second-commande', `New-NetFirewallRule -DisplayName "COVAS second écran" -Direction Inbound -Protocol TCP -LocalPort ${infos.port} -Action Allow -Profile Private`);
    }

    // ----------------------------------------------------------------
    //  MESSAGES DU BACKEND ET INSTALLATION
    // ----------------------------------------------------------------
    function recevoir(message) {
        if (message.type === 'acces') {
            acces = { local: !!message.local, autorise: !!message.autorise, pin_regle: !!message.pin_regle };
            const retenu = lire('localStorage', CLE_PIN);
            if (!acces.autorise && retenu && acces.pin_regle) envoyerPin(retenu);    // code retenu : on se reconnecte seul
        } else if (message.type === 'pin') {
            resultatPin(message);
        } else if (message.type === 'refus') {
            acces.autorise = false;
            acces.pin_regle = message.pin_regle ?? acces.pin_regle;
            ouvrirPin();
        } else if (message.type === 'second_ecran') {
            majSecondEcran(message);
        }
    }

    function installer(options = {}) {
        envoyer = options.envoyer || envoyer;
        tous('[data-onglet-tel]').forEach(bouton => { bouton.onclick = () => choisir(bouton.dataset.ongletTel); });
        ecran.addEventListener('change', appliquer);

        const fenetrePin = $('fenetre-pin');
        $('form-pin')?.addEventListener('submit', evenement => {
            evenement.preventDefault();
            const code = $('champ-pin').value.trim();
            if (!code) return;
            afficherMessage('Vérification…', 'ok');
            envoyerPin(code);
            $('champ-pin').value = '';
        });
        $('pin-annuler')?.addEventListener('click', () => fenetrePin.close());

        const fenetreSecond = $('fenetre-second-ecran');
        $('bouton-second-ecran')?.addEventListener('click', () => fenetreSecond.showModal());
        $('second-fermer')?.addEventListener('click', () => fenetreSecond.close());
        appliquer();
    }

    return { installer, recevoir, mode, autoriser, appliquer };
})();
