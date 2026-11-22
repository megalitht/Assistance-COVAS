/* =====================================================================
   COVAS — Interface de bord
   Reçoit l'état du vaisseau par WebSocket (Backend/module/serveur_ws.py)
   et l'affiche. Aucune logique de jeu ici, sauf le choix de la vue :
   navigation par défaut, combat dès qu'un événement hostile arrive.
   ===================================================================== */
(() => {
    'use strict';

    // ----------------------------------------------------------------
    //  RÉGLAGES
    // ----------------------------------------------------------------
    const PORT_WS = 8765;
    const DELAI_RETOUR_NAV = 25;      // secondes sans menace avant de quitter la vue combat
    const DELAI_ENGAGEMENT = 75;      // le drapeau « danger » ne prolonge le combat que si on a essuyé un tir depuis ce délai
    const LIGNES_JOURNAL_MAX = 150;
    const DUREE_LIGNE_TOUCHEE = 4;    // secondes : ligne d'un module qui vient de perdre de l'intégrité
    const DUREE_RAPPORT = 25;         // secondes : modules cités par le rapport d'avarie mis en évidence
    // Coups qui secouent l'écran (les autres, comme les salves sur le bouclier, sont trop fréquents)
    const IMPACTS_FORTS = new Set(['HullDamage', 'ShieldState', 'CockpitBreached']);

    // ----------------------------------------------------------------
    //  TABLES D'AFFICHAGE
    // ----------------------------------------------------------------
    // Drapeaux de Status.json (numéro de bit)
    const BIT = {
        amarre: 0, pose: 1, train: 2, boucliers: 3, supercroisiere: 4, assistanceOff: 5,
        armes: 6, escadrille: 7, feux: 8, ecope: 9, silencieux: 10, collecte: 11,
        masse: 16, fsdCharge: 17, fsdRefroid: 18, carburantBas: 19, surchauffe: 20,
        latLong: 21, danger: 22, interdiction: 23, vaisseau: 24, chasseur: 25, vrs: 26,
        analyse: 27, visionNuit: 28, saut: 30,
    };

    const VOYANTS = {
        vol: [
            ['train', 'Train sorti'], ['ecope', 'Écope de soute'], ['feux', 'Feux'],
            ['visionNuit', 'Vision nocturne'], ['assistanceOff', 'Assistance coupée', 'attention'],
            ['silencieux', 'Mode silencieux', 'attention'], ['armes', 'Points d\'emport'],
            ['analyse', 'Mode analyse'], ['supercroisiere', 'Supercroisière'],
            ['fsdCharge', 'FSD en charge'], ['fsdRefroid', 'FSD en refroid.'],
            ['masse', 'Masse verrouillée', 'attention'], ['collecte', 'Collecte carburant'],
            ['escadrille', 'En escadrille'], ['carburantBas', 'Carburant bas', 'alerte'],
            ['surchauffe', 'Surchauffe', 'alerte'], ['danger', 'Hostiles proches', 'attention'],
            ['interdiction', 'Interdiction', 'alerte'],
        ],
        combat: [
            ['armes', 'Armes sorties'], ['masse', 'Masse verrouillée', 'attention'],
            ['fsdCharge', 'FSD en charge'], ['fsdRefroid', 'FSD en refroid.', 'attention'],
            ['silencieux', 'Mode silencieux', 'attention'], ['surchauffe', 'Surchauffe', 'alerte'],
            ['carburantBas', 'Carburant bas', 'alerte'], ['interdiction', 'Interdiction', 'alerte'],
            ['danger', 'Hostiles proches', 'attention'],
        ],
    };

    const VAISSEAUX = {
        adder: 'Adder', anaconda: 'Anaconda', asp: 'Asp Explorer', asp_scout: 'Asp Scout',
        belugaliner: 'Beluga Liner', cobramkiii: 'Cobra Mk III', cobramkiv: 'Cobra Mk IV',
        cobramkv: 'Cobra Mk V', corsair: 'Corsair', cutter: 'Imperial Cutter',
        diamondback: 'Diamondback Scout', diamondbackxl: 'Diamondback Explorer', dolphin: 'Dolphin',
        eagle: 'Eagle', empire_courier: 'Imperial Courier', empire_eagle: 'Imperial Eagle',
        empire_trader: 'Imperial Clipper', federation_corvette: 'Federal Corvette',
        federation_dropship: 'Federal Dropship', federation_dropship_mkii: 'Federal Assault Ship',
        federation_gunship: 'Federal Gunship', ferdelance: 'Fer-de-Lance', hauler: 'Hauler',
        independant_trader: 'Keelback', krait_light: 'Krait Phantom', krait_mkii: 'Krait Mk II',
        mamba: 'Mamba', mandalay: 'Mandalay', orca: 'Orca', python: 'Python', python_nx: 'Python Mk II',
        sidewinder: 'Sidewinder', type6: 'Type-6', type7: 'Type-7', type8: 'Type-8', type9: 'Type-9',
        type9_military: 'Type-10', typex: 'Alliance Chieftain', typex_2: 'Alliance Crusader',
        typex_3: 'Alliance Challenger', viper: 'Viper Mk III', viper_mkiv: 'Viper Mk IV', vulture: 'Vulture',
        panthermkii: 'Panther Clipper Mk II', lakonminer: 'Type-11 Prospector', explorer_nx: 'Caspian Explorer',
        smallcombat01_nx: 'Kestrel Mk II', mediumtransport01: 'Lynx Highliner', anacondamkii: 'Anaconda Mk II',
    };

    // Début du nom interne du module -> nom affiché (le plus long préfixe gagne)
    const MODULES = {
        powerplant: 'Générateur', engine: 'Propulseurs', hyperdrive: 'Réacteur FSD',
        lifesupport: 'Systèmes de survie', powerdistributor: 'Répartiteur de puissance',
        sensors: 'Capteurs', fueltank: 'Réservoir de carburant', armour: 'Blindage',
        cockpit: 'Verrière', modularcargobaydoor: 'Trappe de soute',
        planetapproachsuite: 'Suite d\'approche planétaire',
        shieldgenerator: 'Générateur de bouclier', shieldcellbank: 'Cellules de bouclier',
        shieldbooster: 'Survolteur de bouclier', cargorack: 'Compartiment de soute',
        fuelscoop: 'Collecteur de carburant', fsdinterdictor: 'Interdicteur FSD',
        repairer: 'Unité de maintenance', dockingcomputer: 'Ordinateur d\'appontage',
        supercruiseassist: 'Assistance supercroisière', detailedsurfacescanner: 'Scanner de surface',
        buggybay: 'Hangar de VRS', fighterbay: 'Hangar de chasseurs',
        hullreinforcement: 'Renfort de coque', modulereinforcement: 'Renfort de modules',
        guardianfsdbooster: 'Booster FSD gardien', refinery: 'Raffinerie',
        passengercabin: 'Cabine passagers', dronecontrol: 'Contrôleur de drones',
        multidronecontrol: 'Contrôleur de drones multiple', chafflauncher: 'Lance-paillettes',
        heatsinklauncher: 'Dissipateur thermique', plasmapointdefence: 'Défense ponctuelle',
        electroniccountermeasure: 'Contre-mesures électroniques', cloudscanner: 'Scanner de sillage',
        crimescanner: 'Scanner de primes', cargoscanner: 'Scanner de cargaison',
        pulselaserburst: 'Laser à rafales', pulselaser: 'Laser à impulsions',
        beamlaser: 'Laser à faisceau', multicannon: 'Multi-canon', cannon: 'Canon',
        slugshot: 'Canon à fragmentation', railgun: 'Canon électrique',
        plasmaaccelerator: 'Accélérateur plasma', dumbfiremissilerack: 'Lance-missiles',
        basicmissilerack: 'Missiles à tête chercheuse', advancedtorppylon: 'Lance-torpilles',
        minelauncher: 'Lance-mines', mininglaser: 'Laser minier',
    };
    const MONTURES = { fixed: 'fixe', gimbal: 'cardan', turret: 'tourelle' };

    // Zones de l'hologramme : quelle famille de modules chaque repère résume.
    // Leur position sur la coque dépend du vaisseau (voir GEOMETRIE_ZONES dans hologramme.js).
    const ZONES = [
        { cle: 'capteurs', nom: 'Capteurs', test: e => e === 'radar' },
        { cle: 'verriere', nom: 'Verrière', test: e => e === 'shipcockpit' },
        { cle: 'armes', nom: 'Armement', test: e => /hardpoint/.test(e) && !/^tiny/.test(e) },
        { cle: 'noyau', nom: 'Générateur', test: e => ['powerplant', 'powerdistributor', 'lifesupport'].includes(e) },
        { cle: 'internes', nom: 'Compartiments', test: e => /^(slot|military)/.test(e) || e === 'armour' || e === 'planetaryapproachsuite' },
        { cle: 'utilitaires', nom: 'Utilitaires', test: e => /^tiny/.test(e) },
        { cle: 'soute', nom: 'Soute', test: e => e === 'cargohatch' || e === 'fueltank' },
        { cle: 'fsd', nom: 'FSD', test: e => e === 'frameshiftdrive' },
        { cle: 'moteurs', nom: 'Propulseurs', test: e => e === 'mainengines' },
    ];

    const GROUPES_MODULES = [
        ['Armement', e => /hardpoint/.test(e) && !/^tiny/.test(e)],
        ['Utilitaires', e => /^tiny/.test(e)],
        ['Modules principaux', e => ['powerplant', 'mainengines', 'frameshiftdrive', 'lifesupport', 'powerdistributor', 'radar', 'fueltank', 'armour', 'shipcockpit', 'cargohatch'].includes(e)],
        ['Modules optionnels', () => true],
    ];

    const ALLEGEANCES = { Federation: 'Fédération', Empire: 'Empire', Alliance: 'Alliance', Independent: 'Indépendant', PilotsFederation: 'Fédération des pilotes', Thargoid: 'Thargoïde', Guardian: 'Gardien' };
    const STATUTS = { Clean: 'En règle', IllegalCargo: 'Cargaison illégale', Speeding: 'Excès de vitesse', Wanted: 'Recherché', Hostile: 'Hostile', PassengerWanted: 'Passager recherché', Warrant: 'Sous mandat', Lawless: 'Sans loi', Enemy: 'Ennemi', WantedEnemy: 'Ennemi recherché', Hunter: 'Chasseur', Unknown: 'Inconnu' };
    const STATIONS = { Coriolis: 'Coriolis', Orbis: 'Orbis', Ocellus: 'Ocellus', Outpost: 'Avant-poste', Bernal: 'Ocellus', AsteroidBase: 'Base astéroïde', MegaShip: 'Méga-vaisseau', FleetCarrier: 'Porte-vaisseaux', CraterOutpost: 'Avant-poste de surface', CraterPort: 'Port de surface', OnFootSettlement: 'Colonie', SurfaceStation: 'Station de surface' };
    const SERVICES = { commodities: 'Marché', outfitting: 'Équipement', shipyard: 'Chantier naval', repair: 'Réparation', refuel: 'Carburant', rearm: 'Munitions', missions: 'Missions', contacts: 'Contacts', blackmarket: 'Marché noir', exploration: 'Cartographie', materialtrader: 'Courtier en matériaux', techBroker: 'Courtier technologique', engineer: 'Ingénieur' };
    const DOMAINES = { Combat: 'Combat', Trade: 'Commerce', Explore: 'Exploration', Exobiologist: 'Exobiologie', Soldier: 'Mercenaire', Federation: 'Fédération', Empire: 'Empire' };
    const CATEGORIES = { tous: 'Tout', covas: 'COVAS', navigation: 'Navigation', combat: 'Combat', station: 'Station', exploration: 'Exploration', soute: 'Soute', vaisseau: 'Vaisseau', systeme: 'Système' };
    const CHASSEUR = { deploye: 'Déployé', a_bord: 'À bord', detruit: 'Détruit' };

    // ----------------------------------------------------------------
    //  ÉTAT
    // ----------------------------------------------------------------
    const etat = {
        session: {}, commandant: { rangs: {}, progression: {} }, vaisseau: {}, position: {},
        status: {}, route: { etapes: [] }, modules: { liste: [] }, soute: { inventaire: [] },
        cible: {}, combat: {}, missions: { liste: [] }, proches: { liste: [] },
    };
    let journal = [];                 // lignes du journal de bord, la plus récente en premier
    let filtreJournal = 'tous';
    let modeChoisi = lirePreference('covas-mode') || 'auto';   // auto | combat | nav
    let derniereMenace = 0;           // Date.now() du dernier événement hostile
    let causeMenace = '';
    let simulation = false;
    let hologrammes = [];             // un hologramme par vue (navigation, combat)
    let santesConnues = new Map();    // emplacement -> { objet, sante } : pour repérer les modules qui viennent d'être touchés
    const lignesTouchees = new Map(); // emplacement -> fin de la mise en évidence (Date.now())
    let rapport = null;               // dernier rapport d'avarie (+ emplacements cités, fin de la mise en évidence)
    let minuterieTouche = 0, minuterieRapport = 0;
    // interface.html?vaisseau=anaconda : force le vaisseau de l'hologramme (aperçu des plans)
    const vaisseauForce = new URLSearchParams(location.search).get('vaisseau');

    // ----------------------------------------------------------------
    //  OUTILS
    // ----------------------------------------------------------------
    const $ = id => document.getElementById(id);
    const tous = selecteur => document.querySelectorAll(selecteur);
    const drapeau = nom => Math.floor((etat.status.flags || 0) / 2 ** BIT[nom]) % 2 === 1;
    const nombre = n => (n == null ? '—' : Math.round(n).toLocaleString('fr-FR'));
    const credits = n => (n == null ? '—' : nombre(n) + ' cr');
    const pourcent = x => (x == null ? '—' : Math.round(x * 100) + ' %');
    const palier = x => (x == null ? '' : x < 0.3 ? 'critique' : x < 0.6 ? 'attention' : 'ok');

    function ecrire(cle, texte) {
        tous(`[data-v="${cle}"]`).forEach(el => { el.textContent = texte ?? '—'; });
    }

    function jauge(cle, fraction, etatJauge) {
        tous(`[data-j="${cle}"]`).forEach(el => {
            el.firstElementChild.style.width = Math.max(0, Math.min(1, fraction || 0)) * 100 + '%';
            el.dataset.etat = etatJauge ?? palier(fraction);
        });
    }

    function creer(balise, classe, texte) {
        const el = document.createElement(balise);
        if (classe) el.className = classe;
        if (texte != null) el.textContent = texte;
        return el;
    }

    function remplir(conteneur, elements, texteVide) {
        conteneur.replaceChildren(...elements);
        if (!elements.length && texteVide) conteneur.append(creer('li', 'vide', texteVide));
    }

    function lirePreference(cle) { try { return localStorage.getItem(cle); } catch { return null; } }
    function garderPreference(cle, valeur) { try { localStorage.setItem(cle, valeur); } catch { /* stockage indisponible */ } }

    function nomVaisseau(type, modele) {
        if (!type) return modele || '—';
        return VAISSEAUX[type.toLowerCase()] || modele || type;
    }

    function decrireModule(module) {
        const objet = module.objet || '';
        const cle = objet.replace(/^(int|hpt)_/, '');
        const prefixe = Object.keys(MODULES).filter(p => cle.startsWith(p) || cle.includes('_' + p)).sort((a, b) => b.length - a.length)[0];
        let nom = prefixe ? MODULES[prefixe] : cle.replace(/_/g, ' ');
        const monture = (cle.match(/_(fixed|gimbal|turret)/) || [])[1];
        if (monture) nom += ' ' + MONTURES[monture];
        const taille = (objet.match(/_size(\d)/) || [])[1];
        const classe = (objet.match(/_class(\d)/) || [])[1];
        const calibre = { small: 1, medium: 2, large: 3, huge: 4 }[(cle.match(/_(small|medium|large|huge)$/) || [])[1]];
        const etiquette = taille && classe ? taille + 'EDCBA'[classe - 1] : calibre ? 'C' + calibre : '';
        return { nom, etiquette };
    }

    /** Zone de l'hologramme d'un emplacement de module ('' si aucune). */
    function zoneDe(emplacement) {
        return (ZONES.find(z => z.test((emplacement || '').toLowerCase())) || {}).cle || '';
    }

    function etatModule(module) {
        if (module.sante != null && module.sante <= 0) return 'hs';
        if (module.actif === false) return 'coupe';
        if (module.sante == null) return 'ok';
        return module.sante < 0.5 ? 'critique' : module.sante < 0.8 ? 'attention' : 'ok';
    }

    function heure(iso) {
        const d = new Date(iso);
        return isNaN(d) ? '' : d.toLocaleTimeString('fr-FR');
    }

    // ----------------------------------------------------------------
    //  RENDU
    // ----------------------------------------------------------------
    function rendreEntete() {
        const { commandant: c, vaisseau: v, position: p, status: s } = etat;
        ecrire('cmdr', c.nom || '—');
        ecrire('vaisseau-nom', v.nom || nomVaisseau(v.type, v.modele));
        // En-tête : le modèle en petit seulement si le vaisseau a un nom ; panneau Vaisseau : toujours le modèle
        ecrire('vaisseau-modele-entete', v.nom ? nomVaisseau(v.type, v.modele) : '');
        ecrire('vaisseau-modele', nomVaisseau(v.type, v.modele));
        ecrire('systeme', p.systeme || '—');
        ecrire('credits', credits(s.credits ?? c.credits));
        ecrire('statut-legal', STATUTS[s.statut_legal] || s.statut_legal || '—');
    }

    function etatDeVol() {
        if (!etat.status.flags) return etat.session.jeu_actif === false ? 'Jeu fermé' : 'En attente du jeu';
        if (drapeau('amarre')) return 'Amarré';
        if (drapeau('pose')) return 'Posé en surface';
        if (drapeau('saut')) return 'Saut hyperespace';
        if (drapeau('vrs')) return 'En VRS';
        if (drapeau('chasseur')) return 'En chasseur';
        if (drapeau('supercroisiere')) return 'Supercroisière';
        if (drapeau('vaisseau')) return 'Espace normal';
        return 'À pied';
    }

    function rendrePosition() {
        const p = etat.position, s = etat.status, station = p.station;
        ecrire('lieu', station?.nom && p.amarre ? `Amarré à ${station.nom}` : (p.corps || s.corps || ''));
        ecrire('etat-vol', etatDeVol());
        ecrire('destination', s.destination || '—');
        ecrire('population', p.population ? nombre(p.population) : '—');
        ecrire('corps', p.corps_total ? `${p.corps_scannes || 0} / ${p.corps_total}` : (p.corps_scannes ? String(p.corps_scannes) : '—'));

        const pastilles = [ALLEGEANCES[p.allegeance] || p.allegeance, p.gouvernement, p.economie, p.securite, p.faction];
        remplir($('pastilles-systeme'), pastilles.filter(Boolean).map(t => creer('li', '', t)));

        const enSurface = s.latitude != null && s.longitude != null;
        $('ligne-surface').hidden = !enSurface;
        if (enSurface) ecrire('surface', `${s.latitude.toFixed(2)}° / ${s.longitude.toFixed(2)}° · alt. ${nombre(s.altitude)} m · cap ${s.cap ?? '—'}°`);

        $('bloc-station').hidden = !station;
        if (station) {
            ecrire('station-nom', station.nom || '');
            const details = [STATIONS[station.type] || station.type, station.plateforme != null ? `plateforme ${station.plateforme}` : null,
                station.distance_ls ? `${nombre(station.distance_ls)} sl de l'étoile` : null, station.economie];
            ecrire('station-detail', details.filter(Boolean).join(' · '));
            const services = (station.services || []).map(x => SERVICES[x]).filter(Boolean);
            remplir($('pastilles-services'), [...new Set(services)].map(t => creer('li', '', t)));
        }
    }

    function ligneEtoile(nom, classe, distance, ravitaillable) {
        const li = creer('li');
        const pastille = creer('span', 'etoile', (classe || '?').split('_')[0].slice(0, 3));
        pastille.dataset.classe = (classe || '?')[0];
        li.append(pastille, creer('span', 'nom', nom));
        if (ravitaillable) li.append(creer('span', 'plein', 'carburant'));
        li.append(creer('span', 'valeur', distance != null ? distance.toFixed(1) + ' al' : ''));
        return li;
    }

    function rendreRoute() {
        const { etapes = [], indice_actuel: indice, prochain } = etat.route;
        const depuis = indice ?? 0;
        const restantes = etapes.slice(depuis + 1);
        const suivant = restantes[0] || (prochain && { systeme: prochain.systeme, classe: prochain.classe });
        ecrire('prochain-saut', suivant ? suivant.systeme : '—');
        ecrire('sauts-restants', etapes.length ? String(restantes.length) : (prochain?.sauts_restants != null ? String(prochain.sauts_restants) : '—'));
        ecrire('distance-restante', etapes.length ? restantes.reduce((t, e) => t + (e.distance || 0), 0).toFixed(1) + ' al' : '—');

        remplir($('liste-route'), etapes.map((e, i) => {
            const li = ligneEtoile(e.systeme, e.classe, i ? e.distance : null, e.ravitaillable);
            if (indice != null && i < indice) li.classList.add('passe');
            if (i === indice) li.classList.add('actuel');
            return li;
        }), 'Aucune route tracée. Trace-la dans la carte de la galaxie.');
        $('liste-route').querySelector('.actuel')?.scrollIntoView({ block: 'nearest' });
    }

    function rendreProches() {
        const p = etat.proches;
        const resume = {
            ok: `${nombre(p.total)} systèmes dans un rayon de ${p.rayon?.toFixed(1)} al` + (p.total > p.liste.length ? ` (${p.liste.length} plus proches affichés)` : ''),
            recherche: 'Recherche en cours auprès d\'EDSM…',
            erreur: 'EDSM ne répond pas. Nouvelle tentative au prochain saut.',
            desactive: 'Recherche désactivée dans lecteur_logs.py.',
        }[p.etat] || 'En attente de la position et de la portée de saut.';
        ecrire('proches-resume', resume);
        remplir($('liste-proches'), (p.liste || []).map(s => ligneEtoile(s.nom, s.classe, s.distance, s.ravitaillable)));
    }

    function rendreVaisseau() {
        const v = etat.vaisseau, s = etat.status;
        const boucliers = s.flags ? drapeau('boucliers') : v.boucliers;
        ecrire('coque', pourcent(v.coque));
        jauge('coque', v.coque ?? 0);
        ecrire('boucliers', boucliers == null ? '—' : boucliers ? 'En ligne' : 'Hors ligne');
        jauge('boucliers', boucliers ? 1 : 0, 'ok');
        tous('[data-hologramme]').forEach(h => { h.dataset.boucliers = boucliers === false ? 'non' : 'oui'; });
        // Silhouette du vaisseau : change avec le type (à pied, en VRS ou en chasseur, on garde le vaisseau)
        hologrammes.forEach(h => h.afficher(vaisseauForce || v.type || 'generique'));
        tous('.vital').forEach(el => { el.dataset.etat = el.classList.contains('bouclier') ? (boucliers === false ? 'critique' : '') : palier(v.coque); });

        ecrire('carburant', s.carburant != null ? `${s.carburant.toFixed(1)}${v.carburant_max ? ' / ' + v.carburant_max : ''} t` : '—');
        jauge('carburant', v.carburant_max ? s.carburant / v.carburant_max : 0, s.carburant != null && v.carburant_max && s.carburant / v.carburant_max < 0.25 ? 'critique' : 'ok');
        const charge = s.soute ?? etat.soute.total;
        ecrire('soute-charge', v.soute_max != null ? `${nombre(charge || 0)} / ${v.soute_max} t` : '—');
        jauge('soute', v.soute_max ? (charge || 0) / v.soute_max : 0, 'ok');

        ecrire('vaisseau-immat', v.immat || '—');
        ecrire('portee', v.portee_saut ? v.portee_saut.toFixed(2) + ' al' : '—');
        ecrire('rachat', credits(v.rachat));
        ecrire('reserve', s.reserve != null ? s.reserve.toFixed(2) + ' t' : '—');
        ecrire('groupe-tir', s.groupe_tir != null ? String.fromCharCode(65 + s.groupe_tir) : '—');
        ecrire('verriere', v.verriere_brisee ? 'Brisée' : 'Intacte');
        ecrire('chasseur', CHASSEUR[v.chasseur] || 'Aucun');
    }

    function rendreStatus() {
        const pips = etat.status.pips || [0, 0, 0];
        tous('[data-pips]').forEach(conteneur => {
            const rangees = ['SYS', 'MOT', 'ARM'].map((nom, i) => {
                const rangee = creer('div', 'rangee');
                rangee.append(creer('span', '', conteneur.classList.contains('grands') ? ['Systèmes', 'Moteurs', 'Armes'][i] : nom));
                for (let p = 0; p < 4; p++) {
                    const reste = pips[i] - p * 2;
                    rangee.append(creer('i', 'pip' + (reste >= 2 ? ' plein' : reste === 1 ? ' demi' : '')));
                }
                return rangee;
            });
            conteneur.replaceChildren(...rangees);
        });
        tous('[data-voyants]').forEach(liste => {
            liste.replaceChildren(...VOYANTS[liste.dataset.voyants].map(([cle, libelle, type]) => {
                const li = creer('li', drapeau(cle) ? 'allume' : '', libelle);
                li.dataset.type = type || 'info';
                return li;
            }));
        });
    }

    function ligneModule(module) {
        const { nom, etiquette } = decrireModule(module);
        const situation = etatModule(module);
        const ligne = creer('div', 'ligne-module');
        ligne.dataset.etat = situation;
        ligne.dataset.zone = zoneDe(module.emplacement);
        ligne.dataset.emplacement = module.emplacement;
        const maintenant = Date.now();
        if ((lignesTouchees.get(module.emplacement) || 0) > maintenant) ligne.classList.add('touchee');
        if (rapport && rapport.fin > maintenant && rapport.emplacements.has(module.emplacement)) ligne.classList.add('signalee');
        const titre = creer('span', 'nom', nom);
        titre.title = [module.emplacement, module.ingenierie && `${module.ingenierie.plan} G${module.ingenierie.niveau}`,
            module.ingenierie?.effet, module.puissance != null && `${module.puissance.toFixed(2)} MW`,
            module.priorite != null && `priorité ${module.priorite + 1}`].filter(Boolean).join(' · ');
        const mini = creer('span', 'mini-jauge');
        mini.append(creer('i'));
        mini.firstChild.style.width = (module.sante ?? 1) * 100 + '%';
        const valeur = situation === 'hs' ? 'HS' : situation === 'coupe' ? 'Coupé' : pourcent(module.sante ?? 1);
        ligne.append(creer('span', 'classe', etiquette), titre);
        if (module.ingenierie?.niveau) ligne.append(creer('span', 'discret', 'G' + module.ingenierie.niveau));
        ligne.append(mini, creer('span', 'valeur', valeur));
        return ligne;
    }

    function rendreModules() {
        const liste = etat.modules.liste || [];
        ecrire('modules-releve', etat.modules.releve ? `relevé de ${heure(etat.modules.releve)}` : '');

        // Vue navigation : par famille
        const restants = [...liste], blocs = [];
        for (const [titre, test] of GROUPES_MODULES) {
            const groupe = restants.filter(m => test(m.emplacement.toLowerCase()));
            groupe.forEach(m => restants.splice(restants.indexOf(m), 1));
            if (groupe.length) blocs.push(creer('div', 'groupe-modules', titre), ...groupe.map(ligneModule));
        }
        $('liste-modules').replaceChildren(...(blocs.length ? blocs : [creer('div', 'vide', 'Équipement inconnu : il est lu au chargement de la partie.')]));

        // Vue combat : les plus touchés d'abord
        const ordre = { hs: 0, critique: 1, attention: 2, coupe: 3, ok: 4 };
        const tries = [...liste].sort((a, b) => ordre[etatModule(a)] - ordre[etatModule(b)] || (a.sante ?? 1) - (b.sante ?? 1));
        $('liste-modules-combat').replaceChildren(...tries.map(ligneModule));

        // Zones de la silhouette (repères et lueurs) : état du module le plus touché de chaque zone
        for (const zone of ZONES) {
            const modules = liste.filter(m => zone.test(m.emplacement.toLowerCase()));
            const etats = modules.map(etatModule);
            const pire = !modules.length ? 'vide' : ['hs', 'critique', 'attention'].find(e => etats.includes(e)) || (etats.every(e => e === 'coupe') ? 'coupe' : 'ok');
            const sante = modules.length ? Math.min(...modules.map(m => m.sante ?? 1)) : null;
            tous(`.zone[data-zone="${zone.cle}"], .zone-lueur[data-zone="${zone.cle}"]`).forEach(g => {
                g.dataset.etat = pire;
                const texte = g.querySelector('text');
                if (texte) texte.textContent = `${zone.nom} ${pire === 'hs' ? 'HS' : sante != null ? Math.round(sante * 100) + ' %' : ''}`;
            });
        }
    }

    // ----------------------------------------------------------------
    //  AVARIES
    // ----------------------------------------------------------------
    function memoriserSantes(liste) {
        santesConnues = new Map((liste || []).map(m => [m.emplacement, { objet: m.objet, sante: m.sante }]));
    }

    /** Modules qui ont perdu de l'intégrité depuis le relevé précédent (même emplacement, même module).
        Le jeu n'écrit la santé des modules qu'à certains moments (retour du chasseur, station,
        chargement) : c'est à ce moment-là qu'on apprend qu'ils ont été touchés. */
    function modulesTouches(liste) {
        const touches = (liste || []).filter(m => {
            const avant = santesConnues.get(m.emplacement);
            return avant && avant.objet === m.objet && avant.sante != null && m.sante != null && m.sante < avant.sante - 0.004;
        });
        memoriserSantes(liste);
        return touches;
    }

    /** Lignes des modules touchés marquées quelques secondes, repères de leurs zones en voyant d'impact. */
    function signalerModulesTouches(modules) {
        if (!modules.length) return;
        const fin = Date.now() + DUREE_LIGNE_TOUCHEE * 1000;
        modules.forEach(m => lignesTouchees.set(m.emplacement, fin));
        const zones = [...new Set(modules.map(m => zoneDe(m.emplacement)).filter(Boolean))];
        hologrammes.forEach(h => h.signalerZones(zones));
        setTimeout(rendreModules, DUREE_LIGNE_TOUCHEE * 1000 + 50);
    }

    /** Coup reçu (le jeu ne dit pas quel module) : bulle du bouclier ou silhouette entière, ondes d'impact. */
    function signalerImpact(type, fort) {
        hologrammes.forEach(h => h.signalerImpact(type));
        tous('[data-hologramme]').forEach(h => {
            h.classList.remove('touche', 'touche-forte');
            void h.offsetWidth;            // relance l'animation
            h.classList.add('touche');
            if (fort) h.classList.add('touche-forte');
        });
        clearTimeout(minuterieTouche);
        minuterieTouche = setTimeout(() => tous('[data-hologramme]').forEach(h => h.classList.remove('touche', 'touche-forte')), 1100);
        if (fort) {
            document.body.classList.add('secoue');
            setTimeout(() => document.body.classList.remove('secoue'), 400);
        }
    }

    /** Rapport d'avarie (commande vocale ou bouton) : lignes citées en évidence, zones en voyant, résumé. */
    function afficherRapport(r) {
        const emplacements = new Set((r.avaries || []).map(a => a.emplacement));
        rapport = { ...r, emplacements, fin: Date.now() + DUREE_RAPPORT * 1000 };
        rendreModules();
        rendreRapport();
        const zones = [...new Set([...emplacements].map(zoneDe).filter(Boolean))];
        if (zones.length) hologrammes.forEach(h => h.signalerZones(zones, 2400));
        tous('#liste-modules, #liste-modules-combat').forEach(l => l.querySelector('.signalee')?.scrollIntoView({ block: 'nearest' }));
        clearTimeout(minuterieRapport);
        minuterieRapport = setTimeout(() => { rendreModules(); rendreRapport(); }, DUREE_RAPPORT * 1000 + 50);
    }

    function rendreRapport() {
        const actif = !!rapport && rapport.fin > Date.now();
        tous('[data-rapport]').forEach(el => {
            el.hidden = !actif;
            if (!actif) return;
            el.textContent = `Rapport de ${heure(rapport.h).slice(0, 5)} — ${rapport.resume}` + (rapport.perime ? ' · relevé des modules antérieur aux derniers dégâts' : '');
            el.dataset.gravite = rapport.gravite;
        });
    }

    function rendreSoute() {
        remplir($('liste-soute'), (etat.soute.inventaire || []).map(o => {
            const li = creer('li');
            li.append(creer('span', 'nom', o.nom));
            if (o.vole) li.append(creer('span', 'discret', 'volé'));
            li.append(creer('span', 'valeur', o.quantite + ' t'));
            return li;
        }), 'Soute vide');
    }

    function rendreCommandant() {
        const { rangs = {}, progression = {} } = etat.commandant;
        const lignes = Object.keys(DOMAINES).filter(d => rangs[d] != null).map(d => {
            const div = creer('div');
            div.append(creer('dt', '', DOMAINES[d]), creer('dd', '', `rang ${rangs[d]}` + (progression[d] != null ? ` · ${progression[d]} %` : '')));
            return div;
        });
        $('fiche-rangs').replaceChildren(...lignes);
    }

    function rendreMissions() {
        const { liste = [], anterieures = 0 } = etat.missions;
        ecrire('missions-nombre', String(liste.length + anterieures));
        const lignes = liste.map(m => {
            const li = creer('li');
            li.append(creer('span', 'nom', m.nom), creer('span', 'discret', [m.station, m.systeme].filter(Boolean).join(', ')));
            return li;
        });
        if (anterieures) lignes.push(creer('li', 'vide', `${anterieures} mission(s) acceptée(s) avant cette session`));
        remplir($('liste-missions'), lignes, 'Aucune mission en cours');
    }

    function rendreCible() {
        const c = etat.cible;
        $('cible-vide').hidden = !!c.verrouillee;
        $('cible-fiche').hidden = !c.verrouillee;
        if (!c.verrouillee) return;
        ecrire('cible-vaisseau', c.vaisseau || 'Contact inconnu');
        ecrire('cible-pilote', [c.pilote, c.rang].filter(Boolean).join(' · ') || 'Scan en cours…');
        ecrire('cible-boucliers', c.boucliers != null ? Math.round(c.boucliers) + ' %' : '—');
        jauge('cible-boucliers', (c.boucliers || 0) / 100, 'ok');
        ecrire('cible-coque', c.coque != null ? Math.round(c.coque) + ' %' : '—');
        jauge('cible-coque', (c.coque || 0) / 100, 'ok');
        ecrire('cible-statut', STATUTS[c.statut] || c.statut || '—');
        ecrire('cible-prime', c.prime ? credits(c.prime) : '—');
        ecrire('cible-faction', c.faction || '—');
        ecrire('cible-sous-systeme', c.sous_systeme ? `${c.sous_systeme}${c.sous_systeme_sante != null ? ' · ' + Math.round(c.sous_systeme_sante) + ' %' : ''}` : '—');
    }

    function rendreCombat() {
        const c = etat.combat;
        ecrire('bilan-eliminations', String(c.eliminations || 0));
        ecrire('bilan-gains', credits((c.primes || 0) + (c.bons || 0)));
        ecrire('bilan-coups', String(c.coups_coque || 0));
    }

    function ligneJournal(e) {
        const li = creer('li');
        li.dataset.gravite = e.gravite;
        if (e.locuteur) li.dataset.locuteur = e.locuteur;          // conversation : 'cmdr' | 'covas'
        const texte = creer('span', 'texte', e.texte);
        if (e.detail) texte.append(creer('small', 'detail', e.detail));
        li.append(creer('time', '', heure(e.h)), texte);
        if (e.n > 1) li.append(creer('span', 'fois', '×' + e.n));
        return li;
    }

    function rendreJournal() {
        const bord = journal.filter(e => e.categorie !== 'comms' && (filtreJournal === 'tous' || e.categorie === filtreJournal));
        remplir($('liste-journal'), bord.map(ligneJournal), 'Rien à signaler pour l\'instant.');
        remplir($('liste-comms'), journal.filter(e => e.categorie === 'comms').map(ligneJournal), 'Aucun message reçu.');
        remplir($('liste-menaces'), journal.filter(e => e.categorie === 'combat').map(ligneJournal), 'Aucune menace enregistrée.');
    }

    const RENDUS = {
        session: [rendrePosition],
        commandant: [rendreEntete, rendreCommandant],
        vaisseau: [rendreEntete, rendreVaisseau],
        position: [rendreEntete, rendrePosition],
        status: [rendreEntete, rendrePosition, rendreVaisseau, rendreStatus, evaluerMode],
        route: [rendreRoute],
        modules: [rendreModules],
        soute: [rendreSoute, rendreVaisseau],
        cible: [rendreCible],
        combat: [rendreCombat],
        missions: [rendreMissions],
        proches: [rendreProches],
    };

    function rendreTout() {
        new Set(Object.values(RENDUS).flat()).forEach(f => f());
        rendreJournal();
    }

    // ----------------------------------------------------------------
    //  CHOIX DE LA VUE (navigation / combat)
    // ----------------------------------------------------------------
    /** Le jeu lève « danger » dès qu'un hostile rôde : seul, ce n'est pas un combat. */
    function sousLeFeu() {
        return drapeau('interdiction') || (drapeau('danger') && Date.now() - derniereMenace < DELAI_ENGAGEMENT * 1000);
    }

    function menaceActive() {
        if (drapeau('amarre')) return false;
        return sousLeFeu() || Date.now() - derniereMenace < DELAI_RETOUR_NAV * 1000;
    }

    function evaluerMode() {
        const combat = modeChoisi === 'combat' || (modeChoisi === 'auto' && menaceActive());
        document.body.dataset.mode = combat ? 'combat' : 'nav';
        ecrire('mode-choisi', { auto: 'auto', combat: 'combat', nav: 'navigation' }[modeChoisi]);
        if (!combat) return;

        const sousMenace = sousLeFeu();
        ecrire('alerte-cause', causeMenace || (drapeau('interdiction') ? 'Interdiction en cours' : 'Contact hostile détecté'));
        const reste = Math.ceil(DELAI_RETOUR_NAV - (Date.now() - derniereMenace) / 1000);
        ecrire('alerte-retour', modeChoisi === 'combat' ? 'Vue combat forcée' : sousMenace ? 'Menace toujours présente' : `Retour à la navigation dans ${Math.max(reste, 0)} s`);
    }

    function signalerMenace(evenement) {
        derniereMenace = Date.now();
        causeMenace = evenement.texte;
        // impact : 'bouclier' | 'effondrement' | 'coque', déduit par le backend (lecteur_logs.py)
        if (evenement.impact) signalerImpact(evenement.impact, IMPACTS_FORTS.has(evenement.nom));
        evaluerMode();
    }

    // ----------------------------------------------------------------
    //  MESSAGES DU BACKEND
    // ----------------------------------------------------------------
    function recevoir(message) {
        if (message.type === 'etat') {
            Object.assign(etat, message.etat);
            memoriserSantes(etat.modules.liste);
            journal = [...(message.historique || [])].reverse();
            rendreTout();
        } else if (message.type === 'maj') {
            // Modules : la santé reçue est comparée au relevé précédent (avant le rendu, pour marquer les lignes)
            if (message.section === 'modules') signalerModulesTouches(modulesTouches(message.donnees.liste));
            etat[message.section] = message.donnees;
            (RENDUS[message.section] || []).forEach(f => f());
        } else if (message.type === 'evenement') {
            const e = message.evenement;
            journal = [e, ...journal.filter(x => x.id !== e.id)].slice(0, LIGNES_JOURNAL_MAX);
            rendreJournal();
            if (e.hostile) signalerMenace(e);
        } else if (message.type === 'rapport_avarie') {
            afficherRapport(message.rapport);
        }
    }

    function envoyerAction(action) {
        if (simulation) {
            window.COVAS_DEMO?.action?.(action);       // la simulation répond elle-même (aucune touche)
            return;
        }
        if (socket && socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ action }));
    }

    /** Phrase écrite au COVAS : le backend la traite comme si elle suivait « Covas ». */
    function envoyerQuestion(question) {
        if (simulation) {
            window.COVAS_DEMO?.question?.(question);
            return true;
        }
        if (!socket || socket.readyState !== WebSocket.OPEN) return false;
        socket.send(JSON.stringify({ question }));
        return true;
    }

    let socket = null;
    function connecter() {
        if (simulation || location.protocol === 'https:') return;   // page hébergée : simulation seulement
        const adresse = `ws://${location.hostname || 'localhost'}:${PORT_WS}`;
        ecrire('adresse-ws', adresse);
        socket = new WebSocket(adresse);
        socket.onopen = () => {
            document.body.dataset.liaison = 'en-ligne';
            ecrire('liaison', 'En ligne');
            fermerAccueil?.();
        };
        socket.onmessage = event => {
            try { recevoir(JSON.parse(event.data)); } catch (erreur) { console.error('Message COVAS illisible', erreur); }
        };
        socket.onclose = () => {
            if (simulation) return;
            document.body.dataset.liaison = 'hors-ligne';
            ecrire('liaison', 'Hors ligne');
            setTimeout(connecter, 3000);
        };
    }

    function lancerSimulation() {
        if (!window.COVAS_DEMO || simulation) return;
        simulation = true;
        if (socket) socket.close();
        document.body.dataset.liaison = 'simulation';
        ecrire('liaison', 'Simulation');
        window.COVAS_DEMO.demarrer(recevoir);
    }

    // ----------------------------------------------------------------
    //  ÉCRAN D'ACCUEIL (application Python : Backend/app.py ouvre interface.html?app)
    //  Le COVAS est en veille ; le bouton central l'active (Api.activer côté Python),
    //  app.py renvoie chaque étape via COVAS_ACCUEIL.recevoir({texte, etat}).
    //  « pret » -> connexion WebSocket -> l'accueil s'efface devant le panneau.
    // ----------------------------------------------------------------
    const MODE_APP = document.body.hasAttribute('data-app');
    let fermerAccueil = null;

    function installerAccueil() {
        const accueil = $('ecran-accueil');
        const bouton = $('bouton-activer');
        const sequence = $('accueil-sequence');
        let derniere = null;

        const etat = (nom, texte, libelle) => {
            accueil.dataset.etat = nom;
            ecrire('accueil-etat', texte);
            if (libelle) ecrire('accueil-libelle', libelle);
        };
        const ajouter = (texte, classe) => {
            if (derniere && !derniere.className) derniere.className = 'fait';
            derniere = creer('li', classe, texte);
            sequence.append(derniere);
            while (sequence.children.length > 8) sequence.firstElementChild.remove();
        };

        const activer = async () => {
            if (!window.pywebview?.api) { etat('erreur', "Liaison avec l'application indisponible"); return; }
            bouton.disabled = true;
            sequence.replaceChildren();
            derniere = null;
            etat('activation', 'Activation en cours', 'Activation');
            try {
                await window.pywebview.api.activer();
            } catch (erreur) {
                ajouter(String(erreur), 'erreur');
                etat('erreur', 'Activation impossible', 'Réessayer');
                bouton.disabled = false;
            }
        };
        bouton.onclick = activer;

        // F11 : quitter / retrouver le plein écran de la fenêtre de l'application
        document.addEventListener('keydown', event => {
            if (event.key !== 'F11') return;
            event.preventDefault();
            window.pywebview?.api?.plein_ecran?.();
        });

        window.COVAS_ACCUEIL = {
            recevoir({ texte, etat: type }) {
                if (type === 'erreur') {
                    ajouter(texte, 'erreur');
                    if (accueil.hidden) {           // le COVAS s'est arrêté après l'allumage : retour à l'accueil
                        accueil.hidden = false;
                        accueil.classList.remove('sortie');
                        if (socket) { socket.onclose = null; socket.close(); }
                        document.body.dataset.liaison = 'veille';
                    }
                    etat('erreur', 'Activation impossible', 'Réessayer');
                    bouton.disabled = false;
                    return;
                }
                if (type === 'attention') { ajouter(texte, 'attention'); return; }
                if (type === 'pret') {
                    ajouter(texte, 'pret');
                    etat('pret', 'Liaison avec le panneau de contrôle', 'En ligne');
                    connecter();
                    return;
                }
                ajouter(texte);
            },
        };

        fermerAccueil = () => {
            if (accueil.hidden || accueil.classList.contains('sortie')) return;
            if (derniere && !derniere.className) derniere.className = 'fait';
            accueil.classList.add('sortie');
            document.body.classList.add('allumage');
            setTimeout(() => {
                accueil.hidden = true;
                document.body.classList.remove('allumage');
            }, 1200);
        };

        // Fenêtre rechargée (F5) alors que le COVAS tourne déjà : on rejoint directement le panneau
        const verifier = async () => {
            try {
                if (await window.pywebview.api.etat() === 'actif') { etat('pret', 'COVAS en ligne', 'En ligne'); connecter(); }
            } catch (_) { /* API pas prête */ }
        };
        if (window.pywebview?.api) verifier();
        else window.addEventListener('pywebviewready', verifier, { once: true });
        bouton.focus();
    }

    // ----------------------------------------------------------------
    //  MISE EN PLACE
    // ----------------------------------------------------------------
    function installer() {
        // Hologramme du vaisseau (vue de dessus) + repères de modules, dans les deux vues.
        // Les étiquettes des repères ne s'affichent que dans le grand hologramme de la vue combat.
        if (window.COVAS_HOLOGRAMMES) {
            const zones = ZONES.map(({ cle, nom }) => ({ cle, nom }));
            hologrammes = [...tous('[data-hologramme]')].map(conteneur =>
                COVAS_HOLOGRAMMES.creer(conteneur, { zones, etiquettes: conteneur.classList.contains('grand') }));
        }

        // Survol d'un module <-> zone de la silhouette
        const surligner = (cle, actif) => cle && tous(`.zone[data-zone="${cle}"], .ligne-module[data-zone="${cle}"]`).forEach(el => el.classList.toggle('survol', actif));
        for (const type of ['mouseover', 'mouseout']) {
            document.addEventListener(type, event => {
                const el = event.target.closest?.('.zone, .ligne-module');
                if (el) surligner(el.dataset.zone, type === 'mouseover');
            });
        }

        // Filtres du journal de bord
        $('filtres-journal').replaceChildren(...Object.entries(CATEGORIES).map(([cle, libelle]) => {
            const bouton = creer('button', '', libelle);
            bouton.type = 'button';
            bouton.setAttribute('aria-pressed', String(cle === filtreJournal));
            bouton.onclick = () => {
                filtreJournal = cle;
                tous('#filtres-journal button').forEach(b => b.setAttribute('aria-pressed', String(b === bouton)));
                rendreJournal();
            };
            return bouton;
        }));

        // Onglets de la route
        tous('[data-onglet]').forEach(bouton => {
            bouton.onclick = () => {
                tous('[data-onglet]').forEach(b => b.setAttribute('aria-selected', String(b === bouton)));
                tous('[data-contenu]').forEach(c => { c.hidden = c.dataset.contenu !== bouton.dataset.onglet; });
            };
        });

        // Boutons d'action (macros du backend) et sélecteur de vue
        tous('[data-action]').forEach(bouton => { bouton.onclick = () => envoyerAction(bouton.dataset.action); });
        $('form-question').onsubmit = event => {
            event.preventDefault();
            const champ = $('champ-question');
            const question = champ.value.trim();
            if (question && envoyerQuestion(question)) champ.value = '';
        };
        $('selecteur-mode').onclick = () => {
            modeChoisi = { auto: 'combat', combat: 'nav', nav: 'auto' }[modeChoisi];
            garderPreference('covas-mode', modeChoisi);
            evaluerMode();
        };
        $('bouton-demo').hidden = !window.COVAS_DEMO;
        $('bouton-demo').onclick = lancerSimulation;

        // Horloge (l'année du jeu = année réelle + 1286) et minuterie de retour en navigation
        const tic = () => {
            const d = new Date();
            ecrire('heure', d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }));
            ecrire('date', d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' }) + ' ' + (d.getFullYear() + 1286));
            evaluerMode();
        };
        tic();
        setInterval(tic, 1000);

        rendreTout();
        if (MODE_APP) installerAccueil();
        else if (new URLSearchParams(location.search).has('demo') || location.protocol === 'https:') lancerSimulation();
        else connecter();
    }

    installer();
})();
