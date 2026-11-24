/* =====================================================================
   COVAS — Interface de bord
   Reçoit l'état du vaisseau par WebSocket (Backend/module/interface/serveur_ws.py)
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
    const DUREE_CARTE_SCAN = 40;      // secondes d'affichage du dernier corps scanné
    const DUREE_LIGNE_TOUCHEE = 4;    // secondes : ligne d'un module qui vient de perdre de l'intégrité
    const DUREE_RAPPORT = 25;         // secondes : modules cités par le rapport d'avarie mis en évidence
    const DUREE_GRESILLEMENT = 250;   // ms : parasites à chaque changement d'interface
    const MILIEU_GRESILLEMENT = 100;  // ms : l'interface change au plus fort des parasites
    const ECART_GRESILLEMENTS = 800;  // ms entre deux grésillements, même si l'état du jeu oscille
    const ECART_GRESILLEMENTS_CLICS = 400; // ms : clics rapprochés sur les onglets, sans effet stroboscopique
    const PROTECTION_COMMANDES = 500; // ms sans clic après un changement de boutons (évite un décollage par erreur)
    const CONTEXTES_COMMANDES = { vol: 'en vol', station: 'à quai', sol: 'au sol' };
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
        frein: 12, tourelle: 13, sousVaisseau: 14, conduiteAssistee: 15, pleinsPhares: 31,
    };
    // Second champ de drapeaux, surtout pour le pied à terre
    const BIT2 = {
        aPied: 0, viseur: 5, oxygeneBas: 6, santeBasse: 7, froid: 8, chaud: 9, tresFroid: 10,
        tresChaud: 11, planeur: 12, respirable: 16,
    };

    const VOYANTS = {
        vrs: [
            ['frein', 'Frein à main', 'attention'], ['conduiteAssistee', 'Conduite assistée'],
            ['feux', 'Phares'], ['pleinsPhares', 'Pleins phares'], ['tourelle', 'Vue tourelle'],
            ['sousVaisseau', 'Sous le vaisseau', 'attention'], ['ecope', 'Écope de soute'],
            ['visionNuit', 'Vision nocturne'], ['danger', 'Hostiles proches', 'attention'],
            ['surchauffe', 'Surchauffe', 'alerte'],
        ],
        pied: [
            ['oxygeneBas', 'Oxygène bas', 'alerte'], ['santeBasse', 'Santé basse', 'alerte'],
            ['froid', 'Froid', 'attention'], ['chaud', 'Chaud', 'attention'],
            ['tresFroid', 'Grand froid', 'alerte'], ['tresChaud', 'Forte chaleur', 'alerte'],
            ['respirable', 'Air respirable'], ['visionNuit', 'Vision nocturne'],
            ['viseur', 'Visée'], ['danger', 'Hostiles proches', 'attention'],
        ],
        nomade: [
            ['pose', 'Posé'], ['train', 'Train sorti'], ['feux', 'Phares'], ['visionNuit', 'Vision nocturne'],
            ['danger', 'Hostiles proches', 'attention'], ['surchauffe', 'Surchauffe', 'alerte'],
        ],
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
    const TYPES_ETOILES = {
        O: 'Étoile bleue (O)', B: 'Étoile bleu-blanc (B)', A: 'Étoile blanche (A)', F: 'Étoile jaune-blanc (F)',
        G: 'Étoile jaune (G)', K: 'Étoile orange (K)', M: 'Naine rouge (M)', L: 'Naine brune (L)', T: 'Naine brune (T)',
        Y: 'Naine brune (Y)', TTS: 'Étoile T Tauri', AeBe: 'Étoile de Herbig Ae/Be', N: 'Étoile à neutrons',
        H: 'Trou noir', SupermassiveBlackHole: 'Trou noir supermassif', X: 'Exotique',
        A_BlueWhiteSuperGiant: 'Supergéante blanche (A)', F_WhiteSuperGiant: 'Supergéante blanche (F)',
        M_RedSuperGiant: 'Supergéante rouge (M)', M_RedGiant: 'Géante rouge (M)', K_OrangeGiant: 'Géante orange (K)',
    };

    // ----------------------------------------------------------------
    //  ÉTAT
    // ----------------------------------------------------------------
    const etat = {
        session: {}, commandant: { rangs: {}, progression: {} }, vaisseau: {}, position: {},
        status: {}, route: { etapes: [] }, modules: { liste: [] }, soute: { inventaire: [] },
        cible: {}, combat: {}, missions: { liste: [] }, proches: { liste: [] },
        sol: { vaisseau: {} }, pilotage: {},
        chasse: { profil: {}, a_encaisser: {} }, exploration: { corps: [], session: {} },
        carburant: {},
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
    const drapeau = nom => (nom in BIT2
        ? Math.floor((etat.status.flags2 || 0) / 2 ** BIT2[nom]) % 2 === 1
        : Math.floor((etat.status.flags || 0) / 2 ** BIT[nom]) % 2 === 1);
    const nombre = n => (n == null ? '—' : Math.round(n).toLocaleString('fr-FR'));
    const credits = n => (n == null ? '—' : nombre(n) + ' cr');
    const pourcent = x => (x == null ? '—' : Math.round(x * 100) + ' %');
    const palier = x => (x == null ? '' : x < 0.3 ? 'critique' : x < 0.6 ? 'attention' : 'ok');
    /** 12 400 cr, 3,4 M cr, 1,2 Md cr */
    const creditsCourts = n => {
        if (n == null) return '—';
        for (const [seuil, unite] of [[1e9, 'Md'], [1e6, 'M']]) {
            if (n >= seuil) return (n / seuil).toLocaleString('fr-FR', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + ` ${unite} cr`;
        }
        return credits(n);
    };
    const decimales = (x, n) => x.toLocaleString('fr-FR', { minimumFractionDigits: n, maximumFractionDigits: n });
    const fourchette = (a, b) => (a === b ? creditsCourts(b) : `${creditsCourts(a).replace(/ cr$/, '')} à ${creditsCourts(b)}`);

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
        if (drapeau('aPied')) return 'À pied';        // Flags peut valoir 0 à pied en station
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

    /** Type d'étoile en clair (classe de NavRoute.json, FSDTarget ou EDSM). */
    function typeEtoile(classe) {
        const c = (classe || '').split('_')[0];
        if (!c || c === '?') return 'Étoile inconnue';
        const nom = TYPES_ETOILES[classe] || TYPES_ETOILES[c];
        if (nom) return nom;
        if (c.startsWith('D')) return `Naine blanche (${c})`;
        if (c.startsWith('W')) return `Wolf-Rayet (${c})`;
        if (c.startsWith('C') || c === 'MS' || c === 'S') return `Étoile carbonée (${c})`;
        return `Étoile de classe ${c}`;
    }

    function iconePlein() {
        const ns = 'http://www.w3.org/2000/svg', texte = 'Étoile récupérable : on peut y écoper du carburant';
        const svg = document.createElementNS(ns, 'svg');
        svg.setAttribute('class', 'icone-plein');
        svg.setAttribute('viewBox', '0 0 24 24');
        svg.setAttribute('role', 'img');
        svg.setAttribute('aria-label', texte);
        const titre = document.createElementNS(ns, 'title');
        titre.textContent = texte;
        const usage = document.createElementNS(ns, 'use');
        usage.setAttribute('href', '#icone-carburant');
        svg.append(titre, usage);
        return svg;
    }

    function ligneEtoile(nom, classe, distance, ravitaillable) {
        const li = creer('li');
        const pastille = creer('span', 'etoile', (classe || '?').split('_')[0].slice(0, 3));
        pastille.dataset.classe = (classe || '?')[0];
        pastille.title = typeEtoile(classe);
        li.append(pastille, creer('span', 'nom', nom));
        if (ravitaillable) li.append(iconePlein());
        li.append(creer('span', 'valeur', distance != null ? distance.toFixed(1) + ' al' : ''));
        return li;
    }

    function rendreRoute() {
        const r = etat.route, { etapes = [], indice_actuel: indice, prochain } = r;
        // Sauts et distance restants : calculés par Backend/module/jeu/route.py (décompte du jeu compris)
        const sauts = r.sauts_restants ?? (etapes.length ? etapes.length - 1 - (indice ?? 0) : prochain?.sauts_restants);
        const restantes = sauts ? etapes.slice(-sauts) : [];
        const suivant = restantes[0] || (prochain && { systeme: prochain.systeme, classe: prochain.classe });
        const restante = r.distance_restante ?? (etapes.length ? restantes.reduce((t, e) => t + (e.distance || 0), 0) : null);
        ecrire('prochain-saut', sauts === 0 ? 'Arrivé' : suivant ? suivant.systeme : '—');
        ecrire('sauts-restants', sauts != null ? String(sauts) : '—');
        ecrire('distance-restante', restante != null ? decimales(restante, 1) + ' al' : '—');

        // Barre de progression (distance parcourue sur la distance totale)
        const bloc = $('progression-route');
        bloc.hidden = etapes.length < 2 || r.progression == null;
        if (!bloc.hidden) {
            bloc.dataset.etat = sauts === 0 ? 'arrivee' : '';
            ecrire('route-destination', `→ ${r.destination || etapes[etapes.length - 1].systeme}`);
            ecrire('route-pourcent', Math.round(r.progression * 100) + ' %');
            jauge('route', r.progression, 'ok');
            const total = r.nombre_sauts ?? etapes.length - 1;
            ecrire('route-detail', `${decimales(r.distance_parcourue ?? 0, 1)} / ${decimales(r.distance_totale ?? 0, 1)} al · saut ${total - (sauts ?? total)} sur ${total}`
                + (r.source === 'jeu' ? ' · décompte du jeu' : ''));
        }

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
        window.COVAS_REGLAGES?.majVaisseau(v.type);
        tous('.vital:not([data-libre])').forEach(el => { el.dataset.etat = el.classList.contains('bouclier') ? (boucliers === false ? 'critique' : '') : palier(v.coque); });

        rendreCarburant();
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

    /** Réservoir : orange sous le seuil bas, rouge clignotant sous le seuil critique (seuils de
        Backend/data/config.toml, envoyés par le backend), et le nombre de sauts estimé. */
    function rendreCarburant() {
        const c = etat.carburant || {}, s = etat.status, v = etat.vaisseau;
        const niveau = s.carburant ?? c.niveau, capacite = c.capacite ?? v.carburant_max;
        const part = niveau != null && capacite ? niveau / capacite : null;
        const bas = c.seuil_bas ?? 0.25, critique = c.seuil_critique ?? 0.1;
        const etatJauge = part == null ? 'ok' : part < critique ? 'alarme' : part < bas ? 'attention' : 'ok';
        ecrire('carburant', niveau != null ? `${niveau.toFixed(1)}${capacite ? ' / ' + capacite : ''} t` : '—');
        jauge('carburant', part ?? 0, etatJauge);
        tous('[data-bloc="carburant"]').forEach(el => { el.dataset.etat = etatJauge; });

        let note = c.sauts != null ? `≈ ${nombre(c.sauts)} saut${c.sauts > 1 ? 's' : ''}` : '';
        if (c.sauts != null && c.source === 'fsd') note += ' (au pire)';
        if (c.route && !c.route.suffisant) note = c.route.cible === 'etoile' ? 'Trop juste : étoile' : 'Trop juste : route';
        ecrire('carburant-sauts', note);
        tous('[data-v="carburant-sauts"]').forEach(el => {
            el.dataset.alerte = c.route && !c.route.suffisant ? 'oui' : '';
            el.title = c.conso ? `Consommation ≈ ${c.conso.toLocaleString('fr-FR')} t par saut (${{ historique: `moyenne des ${c.historique} derniers sauts`, fsd: 'maximum du FSD, faute d\'historique', config: 'valeur de secours de config.toml' }[c.source] || ''})`
                + (c.route ? ` · route : ≈ ${c.route.besoin.toLocaleString('fr-FR')} t pour ${c.route.sauts} saut(s)` : '') : '';
        });
    }

    function rendreStatus() {
        const pips = etat.status.pips || [0, 0, 0];
        window.COVAS_REGLAGES?.majPips(etat.status.pips);
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
        tous('[data-cible-vide]').forEach(el => { el.hidden = !!c.verrouillee; });
        tous('[data-cible-fiche]').forEach(el => { el.hidden = !c.verrouillee; });
        rendreVerdict(c);
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

    /** Recherché, en règle, autorités... : la couleur et le conseil, dans la vue combat et au viseur. */
    function rendreVerdict(c) {
        const v = c.verrouillee ? c.verdict : null;
        tous('[data-verdict]').forEach(el => {
            el.hidden = !v;
            if (v) el.dataset.code = v.code;
        });
        tous('[data-teinte-verdict]').forEach(el => { el.dataset.teinteVerdict = v?.code || 'aucun'; });
        const precisions = v ? [v.joueur && 'Commandant', v.gros && 'Gros gibier', v.tirer && v.dangereux && 'Pilote dangereux', v.conseil].filter(Boolean).join(' · ') : '';
        ecrire('cible-verdict', v?.libelle || '');
        ecrire('cible-conseil', [v?.prime ? creditsCourts(v.prime) : null, precisions].filter(Boolean).join(' · '));
        ecrire('viseur-verdict', v?.libelle || (c.verrouillee ? 'Scan en cours' : 'Aucune cible'));
        ecrire('viseur-prime', v?.prime ? credits(v.prime) : '');
        ecrire('viseur-conseil', precisions || (c.verrouillee ? '' : 'Verrouillez un contact'));
    }

    // ----------------------------------------------------------------
    //  MODE CHASSEUR DE PRIMES
    // ----------------------------------------------------------------
    function rendreTauxChasse() {
        const c = etat.chasse || {};
        const heures = c.depuis ? (Date.now() - Date.parse(c.depuis)) / 3600000 : 0;
        ecrire('chasse-taux', c.actif && c.gains && heures > 1 / 60 ? `${creditsCourts(c.gains / heures)}/h` : '—');
    }

    function rendreChasse() {
        const c = etat.chasse || {};
        const actif = !!c.actif;
        document.body.toggleAttribute('data-chasse', actif);
        ecrire('chasse-etat', actif ? (c.zone_nom?.replace("Site d'extraction ", 'Site ') || (c.manuel ? 'activé à la main' : 'en chasse')) : c.profil?.pret ? 'en veille' : 'vaisseau peu armé');
        ecrire('chasse-eliminations', String(c.eliminations || 0));
        ecrire('chasse-gains', creditsCourts(c.gains || 0));
        ecrire('chasse-meilleure', c.meilleure ? credits(c.meilleure) : '—');
        ecrire('chasse-encaisser', credits(c.a_encaisser_total || 0));
        rendreTauxChasse();
        const lignes = () => Object.entries(c.a_encaisser || {}).sort((a, b) => b[1] - a[1]).map(([faction, montant]) => {
            const li = creer('li');
            li.append(creer('span', 'nom', faction), creer('span', 'valeur', creditsCourts(montant)));
            return li;
        });
        tous('[data-liste-primes]').forEach(l => l.replaceChildren(...lignes()));
        tous('[data-bouton-chasse]').forEach(b => {
            b.dataset.action = actif ? 'chasse|coupe' : 'chasse|active';
            b.textContent = actif ? 'Couper le mode chasse' : 'Activer le mode chasse';
        });
        evaluerMode();
    }

    function rendrePilotage() {
        const p = etat.pilotage || {};
        ecrire('pilotage-modele', p.modele || '');
        ecrire('pilotage-coque', pourcent(p.coque));
        jauge('pilotage-coque', p.coque ?? 0);
        tous('.vital[data-libre]').forEach(el => { el.dataset.etat = palier(p.coque); });
        evaluerMode();
        rendreSurface();
    }

    // ----------------------------------------------------------------
    //  EXPLORATION : VALEUR DES CORPS ET VIE
    // ----------------------------------------------------------------
    let cleDernierScan = null, finCarteScan = 0;

    /** Le corps où l'on est, sinon le dernier scanné. */
    function ficheActuelle() {
        const x = etat.exploration || {}, ici = etat.status.corps || etat.position.corps;
        const corps = (x.corps || []).filter(f => f.connu);
        return corps.find(f => f.nom === ici) || corps.find(f => f.id === x.dernier) || null;
    }

    function ficheDernier() {
        const x = etat.exploration || {};
        return (x.corps || []).find(f => f.id === x.dernier && f.connu) || null;
    }

    const cleScan = f => (f ? `${etat.exploration.systeme}|${f.id}|${f.valeur}|${f.bio?.signaux || 0}` : null);

    function signalerScan() {
        const cle = cleScan(ficheDernier());
        if (cle && cle !== cleDernierScan) finCarteScan = Date.now() + DUREE_CARTE_SCAN * 1000;
        cleDernierScan = cle;
    }

    function pastillesCorps(f) {
        const p = [];
        if (f.etoile) p.push([f.premiere_decouverte ? 'Première découverte' : 'Déjà découverte', f.premiere_decouverte && 'or']);
        else {
            p.push([f.premiere_decouverte ? 'Première découverte' : 'Déjà découvert', f.premiere_decouverte && 'or']);
            p.push([f.cartographie ? 'Cartographié' : f.premiere_carto ? 'Jamais cartographié' : 'Déjà cartographié', !f.cartographie && f.premiere_carto && 'or']);
        }
        if (f.terraformable) p.push(['Terraformable']);
        if (f.atterrissable) p.push([f.premier_pas ? 'Aucun pas posé · bonus ×5' : 'Déjà foulé', f.premier_pas && f.bio && 'vie']);
        if (f.balise) p.push(['Données de balise']);
        return p.map(([texte, type]) => { const li = creer('li', '', texte); if (type) li.dataset.t = type; return li; });
    }

    const valeurVie = bio => (!bio ? 'Aucune' : bio.max_bonus ? fourchette(bio.min_bonus, bio.max_bonus) : `${bio.signaux} signal${bio.signaux > 1 ? 'ux' : ''}`);

    function ligneCorps(f, ici) {
        const li = creer('li', f.id === ici ? 'ici' : '');
        li.append(creer('span', 'nom', f.court || f.nom || `Corps ${f.id}`));
        li.lastChild.title = [f.classe, f.distance_ls != null && `${nombre(f.distance_ls)} sl`].filter(Boolean).join(' · ');
        if (f.premiere_decouverte) { const m = creer('span', 'marque', '1re'); m.title = 'Première découverte'; li.append(m); }
        if (f.bio) { const m = creer('span', 'marque', `Vie ${f.bio.signaux}`); m.dataset.t = 'vie'; m.title = valeurVie(f.bio); li.append(m); }
        li.append(creer('span', 'valeur', f.connu ? creditsCourts(f.potentiel) : '—'));
        return li;
    }

    /** facteur : 5 si personne n'a encore posé le pied ici, comme le total affiché au-dessus. */
    function ligneBio(l, facteur) {
        const li = creer('li');
        li.dataset.etat = l.etat;
        li.append(creer('span', 'nom', l.espece || l.genre));
        li.append(creer('span', 'valeur', l.max ? fourchette(l.min * facteur, l.max * facteur) : '—'));
        const detail = { analyse: 'Analyse terminée', prelevement: 'Prélèvement en cours' }[l.etat]
            || (l.espece ? `${l.genre} · espèce probable` : `${l.possibles} espèce${l.possibles > 1 ? 's' : ''} possible${l.possibles > 1 ? 's' : ''}`);
        li.append(creer('span', 'detail-bio', detail));
        return li;
    }

    function rendreCarteScan() {
        const f = ficheDernier();
        const visible = !!f && Date.now() < finCarteScan;
        $('carte-scan').hidden = !visible;
        if (!visible) return;
        ecrire('scan-nom', f.court || f.nom);
        ecrire('scan-classe', f.classe || '');
        ecrire('scan-valeur', f.balise ? '—' : `≈ ${creditsCourts(f.valeur)}`);
        ecrire('scan-carto', f.etoile || f.balise ? '—' : `≈ ${creditsCourts(f.valeur_carto)}`);
        ecrire('scan-vie', valeurVie(f.bio));
        $('scan-pastilles').replaceChildren(...pastillesCorps(f));
    }

    function rendreCorpsActuel() {
        const f = ficheActuelle(), bio = f?.bio;
        ecrire('corps-nom', f ? f.court || f.nom : 'aucun scan');
        ecrire('corps-valeur', f ? `≈ ${creditsCourts(f.valeur)}` : '—');
        ecrire('corps-carto', f && !f.etoile ? `≈ ${creditsCourts(f.valeur_carto)}` : '—');
        ecrire('corps-vie', f ? valeurVie(bio) : '—');
        $('corps-pastilles').replaceChildren(...(f ? pastillesCorps(f) : []));
        ecrire('bio-resume', bio ? `${bio.signaux} forme${bio.signaux > 1 ? 's' : ''} de vie` : '');
        tous('[data-bio-vide]').forEach(el => { el.hidden = !!bio; });
        tous('[data-bio-liste]').forEach(l => l.replaceChildren(...(bio?.lignes || []).map(ligne => ligneBio(ligne, bio.bonus ? 5 : 1))));
    }

    function rendreExploration() {
        const x = etat.exploration || {}, session = x.session || {};
        const ici = ficheActuelle()?.id;
        ecrire('explo-total', x.total ? `≈ ${creditsCourts(x.total_carto)}` : '—');
        ecrire('explo-vie', x.bio_max ? `≤ ${creditsCourts(x.bio_max)}` : '—');
        ecrire('explo-vendre', creditsCourts(session.a_vendre || 0));
        ecrire('exo-vendre', creditsCourts(session.exo || 0));
        ecrire('explo-resume', x.corps?.length ? `${x.corps.length} corps connus · ${x.premieres || 0} première${x.premieres > 1 ? 's' : ''} découverte${x.premieres > 1 ? 's' : ''} · exobiologie à vendre ${creditsCourts(session.exo || 0)}` : 'Lancez un balayage du système pour estimer ses corps.');
        remplir($('liste-corps'), (x.corps || []).map(f => ligneCorps(f, ici)), 'Aucun corps scanné dans ce système.');
        remplir($('liste-corps-nomade'), (x.corps || []).filter(f => f.bio || f.atterrissable).slice(0, 12).map(f => ligneCorps(f, ici)), 'Aucun corps posable scanné.');
        rendreCarteScan();
        rendreCorpsActuel();
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
        remplir($('liste-journal-surface'), journal.filter(e => e.categorie !== 'comms').map(ligneJournal), 'Rien à signaler pour l\'instant.');
        remplir($('liste-comms-surface'), journal.filter(e => e.categorie === 'comms').map(ligneJournal), 'Aucun message reçu.');
        remplir($('liste-menaces'), journal.filter(e => e.categorie === 'combat').map(ligneJournal), 'Aucune menace enregistrée.');
        remplir($('liste-menaces-chasseur'), journal.filter(e => e.categorie === 'combat').map(ligneJournal), 'Aucune menace enregistrée.');
        remplir($('liste-comms-chasseur'), journal.filter(e => e.categorie === 'comms').map(ligneJournal), 'Aucun message reçu.');
    }

    // ----------------------------------------------------------------
    //  SURFACE : VRS ET PIED À TERRE
    // ----------------------------------------------------------------
    const distanceLisible = m => (m == null ? '—' : m >= 1000
        ? (m / 1000).toLocaleString('fr-FR', { maximumFractionDigits: 2 }) + ' km' : Math.round(m) + ' m');
    const angle = x => (x == null ? '—' : decimales(x, 4) + '°');

    /** Où se trouve le cap visé par rapport au regard du commandant. */
    function directionRelative(capCible, cap) {
        if (capCible == null || cap == null) return '—';
        const ecart = ((capCible - cap + 540) % 360) - 180;
        if (Math.abs(ecart) <= 8) return 'Droit devant';
        if (Math.abs(ecart) >= 165) return 'Derrière vous';
        return `${ecart > 0 ? 'À droite' : 'À gauche'} de ${Math.abs(Math.round(ecart))}°`;
    }

    function installerBoussole() {
        const SVG = 'http://www.w3.org/2000/svg';
        const cadran = $('boussole-cadran');
        for (let a = 0; a < 360; a += 5) {
            const trait = document.createElementNS(SVG, 'line');
            const majeure = a % 30 === 0;
            trait.setAttribute('class', 'boussole-graduation' + (majeure ? ' majeure' : ''));
            trait.setAttribute('x1', 200);
            trait.setAttribute('x2', 200);
            trait.setAttribute('y1', 10);
            trait.setAttribute('y2', majeure ? 30 : 20);
            trait.setAttribute('transform', `rotate(${a} 200 200)`);
            cadran.append(trait);
        }
        for (const [lettre, degres] of [['N', 0], ['E', 90], ['S', 180], ['O', 270]]) {
            const texte = document.createElementNS(SVG, 'text');
            texte.setAttribute('class', 'boussole-lettre' + (lettre === 'N' ? ' nord' : ''));
            texte.dataset.degres = degres;
            texte.textContent = lettre;
            $('boussole-cardinaux').append(texte);
        }
    }

    function rendreBoussole(cap, capVaisseau) {
        const regard = cap ?? 0;
        $('boussole-cadran').setAttribute('transform', `rotate(${-regard} 200 200)`);
        $('boussole-cardinaux').querySelectorAll('text').forEach(t => {
            const a = (Number(t.dataset.degres) - regard) * Math.PI / 180;
            t.setAttribute('x', (200 + 142 * Math.sin(a)).toFixed(1));
            t.setAttribute('y', (200 - 142 * Math.cos(a)).toFixed(1));
        });
        const fleche = $('boussole-vaisseau');
        const visible = capVaisseau != null && cap != null;
        fleche.toggleAttribute('hidden', !visible);
        if (visible) fleche.setAttribute('transform', `rotate(${capVaisseau - cap} 200 200)`);
    }

    function rendreExobio(exo) {
        $('exo-vide').hidden = !!exo;
        $('exo-fiche').hidden = !exo;
        ecrire('exo-progres', exo ? `${exo.echantillons} / 3` : '');
        if (!exo) return;
        ecrire('exo-espece', exo.espece || exo.genre || 'Espèce inconnue');
        ecrire('exo-variante', exo.variante || exo.genre || '');
        [...$('exo-points').children].forEach((li, i) => li.classList.toggle('fait', i < exo.echantillons));
        const portee = exo.portee ? distanceLisible(exo.portee) : null;
        ecrire('exo-distance', exo.termine ? '—' : `${distanceLisible(exo.distance)}${portee ? ' / ' + portee : ''}`);
        jauge('exo-distance', exo.termine ? 1 : exo.portee ? (exo.distance || 0) / exo.portee : 0, exo.termine || exo.libre ? 'ok' : 'attention');
        const consigne = tous('[data-v="exo-consigne"]')[0];
        let texte = 'Position du dernier prélèvement inconnue.';
        if (exo.termine) texte = 'Analyse terminée.';
        else if (exo.libre) texte = 'Assez loin : prélèvement suivant possible.';
        else if (exo.distance != null && exo.portee) texte = `Éloignez-vous encore de ${distanceLisible(exo.portee - exo.distance)}.`;
        consigne.textContent = texte;
        consigne.dataset.etat = exo.termine || exo.libre ? 'ok' : '';
        ecrire('exo-valeur', exo.valeur ? `${credits(exo.valeur)}${exo.premier_pas ? ` · ${creditsCourts(exo.valeur * 5)} avec le premier pas` : ''}` : '');
    }

    function rendreSurface() {
        const s = etat.status, p = etat.position, sol = etat.sol || {}, v = sol.vaisseau || {};
        const aPied = drapeau('aPied');
        const enNomad = !aPied && etat.pilotage?.genre === 'nomade';
        ecrire('surface-situation', aPied ? 'à pied' : enNomad ? 'en Nomad' : 'en VRS');
        ecrire('nomade-etat', drapeau('pose') ? 'posé' : 'en vol');
        ecrire('surface-corps', s.corps || p.corps || p.station?.nom || '—');
        ecrire('surface-lat', angle(s.latitude));
        ecrire('surface-lon', angle(s.longitude));
        ecrire('surface-alt', s.altitude != null ? nombre(s.altitude) + ' m' : '—');
        ecrire('surface-cap', s.cap != null ? s.cap + '°' : '—');
        ecrire('surface-gravite', s.gravite != null ? decimales(s.gravite, 2) + ' g' : '—');
        ecrire('surface-air', drapeau('respirable') ? 'Respirable' : aPied ? 'Non respirable' : '—');

        // Descendu du Nomad : c'est lui qu'il faut retrouver, le vaisseau mère est resté en orbite
        const engin = etat.pilotage?.genre === 'nomade' ? 'Nomad' : 'Vaisseau';
        ecrire('retour-titre', engin);
        ecrire('retour-nom', engin === 'Nomad' ? '' : etat.vaisseau.nom || nomVaisseau(etat.vaisseau.type, etat.vaisseau.modele));
        const present = v.etat === 'pose';
        ecrire('retour-etat', present ? 'Posé' : v.etat === 'parti' ? 'En orbite' : 'Position inconnue');
        ecrire('retour-distance', distanceLisible(v.distance));
        ecrire('retour-direction', directionRelative(v.cap, s.cap));
        ecrire('boussole-distance', v.distance != null ? distanceLisible(v.distance) : '—');
        ecrire('boussole-consigne', v.distance != null ? directionRelative(v.cap, s.cap)
            : v.etat === 'parti' ? `${engin} en orbite` : `${engin} non localisé`);
        rendreBoussole(s.cap, enNomad ? null : v.cap);
        if (enNomad) {               // le vaisseau mère reste en orbite : on suit surtout l'altitude
            ecrire('boussole-distance', s.altitude != null ? distanceLisible(s.altitude) : '—');
            ecrire('boussole-consigne', s.altitude != null ? 'Altitude' : 'En vol');
        }
        $('bouton-rappel').firstChild.textContent = present ? 'Renvoyer le vaisseau' : 'Rappeler le vaisseau';

        ecrire('vrs-modele', sol.vrs?.modele || 'VRS');
        const carburant = s.carburant != null || s.reserve != null ? (s.carburant || 0) + (s.reserve || 0) : null;
        ecrire('vrs-carburant', carburant != null ? decimales(carburant, 2) + ' t' : '—');

        const c = sol.combinaison || {};
        ecrire('pied-combinaison', c.nom || '—');
        ecrire('pied-chargement', c.chargement || '—');
        ecrire('pied-arme', s.arme || '—');
        remplir($('liste-armes'), (c.armes || []).map(a => { const li = creer('li'); li.append(creer('span', 'nom', a)); return li; }));

        ecrire('pied-oxygene', pourcent(s.oxygene));
        jauge('pied-oxygene', s.oxygene ?? 0, s.oxygene == null ? 'ok' : s.oxygene < 0.25 ? 'critique' : s.oxygene < 0.5 ? 'attention' : 'ok');
        ecrire('pied-sante', pourcent(s.sante));
        jauge('pied-sante', s.sante ?? 0);
        const kelvins = s.temperature;
        ecrire('pied-temperature', kelvins != null ? `${Math.round(kelvins - 273.15)} °C` : '—');
        const extreme = drapeau('tresFroid') || drapeau('tresChaud');
        const inconfort = drapeau('froid') || drapeau('chaud');
        jauge('pied-temperature', kelvins != null ? Math.min(1, kelvins / 600) : 0, extreme ? 'critique' : inconfort ? 'attention' : 'ok');
        rendreExobio(sol.exobio);
        rendreCorpsActuel();
    }

    /** Boutons VRS et à pied sans touche dans le jeu : marqués, le clic expliquera quoi régler. */
    function marquerTouches(document_) {
        const groupes = document_?.catalogue?.groupes;
        if (!groupes) return;
        const lignes = new Map(groupes.flatMap(g => g.commandes).map(c => [c.id, c]));
        const perso = document_.commandes?.touches || {};
        tous('.vue-surface [data-action]').forEach(bouton => {
            const c = lignes.get(bouton.dataset.action);
            if (!c) return;
            const manque = !(perso[c.id] || c.jeu || c.secours);
            bouton.classList.toggle('sans-touche', manque);
            bouton.title = manque ? `Aucune touche dans le jeu : « ${c.libelle} » (Options > Commandes)` : '';
        });
    }

    const RENDUS = {
        session: [rendrePosition],
        commandant: [rendreEntete, rendreCommandant],
        vaisseau: [rendreEntete, rendreVaisseau],
        position: [rendreEntete, rendrePosition, rendreSurface, rendreExploration],
        sol: [rendreSurface],
        chasse: [rendreChasse],
        pilotage: [rendrePilotage],
        exploration: [rendreExploration],
        status: [rendreEntete, rendrePosition, rendreVaisseau, rendreStatus, rendreSurface, evaluerMode],
        route: [rendreRoute],
        modules: [rendreModules],
        soute: [rendreSoute, rendreVaisseau],
        cible: [rendreCible],
        combat: [rendreCombat],
        missions: [rendreMissions],
        proches: [rendreProches],
        carburant: [rendreCarburant],
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

    /** Jeu de commandes selon la situation. Au menu du jeu (aucun drapeau), on garde le dernier. */
    function contexteCommandes() {
        if (!etat.status.flags) return voulue.commandes;
        return drapeau('amarre') ? 'station' : drapeau('pose') ? 'sol' : 'vol';
    }

    /** 'vrs', 'pied' ou null. Au menu du jeu (aucun drapeau), on garde la dernière situation. */
    let derniereSurface = null;
    function situationSurface() {
        if (!etat.status.flags && !etat.status.flags2) return derniereSurface;
        derniereSurface = drapeau('aPied') ? 'pied' : drapeau('vrs') ? 'vrs' : null;
        return derniereSurface;
    }

    /** 'nomade', 'chasseur' ou null : l'engin embarqué que le commandant pilote lui-même.
        Le Nomad est reconnu par le journal : on ne sait pas quel drapeau le jeu lui donne. */
    function situationPilotage() {
        if (drapeau('aPied')) return null;
        if (etat.pilotage?.genre === 'nomade') return 'nomade';
        return drapeau('chasseur') ? 'chasseur' : null;
    }

    function evaluerMode() {
        const menace = menaceActive();
        const pilotage = situationPilotage();
        const surface = pilotage ? null : situationSurface();
        const chasse = etat.chasse || {};
        // Hors du vaisseau, la vue combat (coque, FSD, sous-systèmes) ne servirait à rien :
        // on reste sur la vue de l'engin ou de surface, avec le bandeau d'alerte.
        // En chasse aux primes, la vue combat reste affichée même entre deux cibles.
        const auto = pilotage || surface || (menace || chasse.actif ? 'combat' : 'nav');
        const mode = modeChoisi === 'auto' ? auto : modeChoisi;
        demanderInterface(mode, contexteCommandes());
        ecrire('mode-choisi', { auto: 'auto', combat: 'combat', nav: 'navigation' }[modeChoisi]);
        const alerteSurface = ['vrs', 'pied', 'nomade', 'chasseur'].includes(mode) && menace;
        document.body.toggleAttribute('data-alerte', alerteSurface);
        const chasseCalme = mode === 'combat' && !!chasse.actif && !menace;
        document.body.toggleAttribute('data-chasse-calme', chasseCalme);
        ecrire('alerte-titre', chasseCalme ? 'Chasse aux primes' : 'Alerte combat');
        if (chasseCalme) {
            ecrire('alerte-cause', chasse.zone_nom || 'Mode chasseur de primes');
            ecrire('alerte-retour', `${chasse.eliminations || 0} élimination${chasse.eliminations > 1 ? 's' : ''} · ${creditsCourts(chasse.gains || 0)}`);
            return;
        }
        if (mode !== 'combat' && !alerteSurface) return;

        const sousMenace = sousLeFeu();
        ecrire('alerte-cause', causeMenace || (drapeau('interdiction') ? 'Interdiction en cours' : 'Contact hostile détecté'));
        const reste = Math.max(Math.ceil(DELAI_RETOUR_NAV - (Date.now() - derniereMenace) / 1000), 0);
        const fin = alerteSurface ? `Fin de l'alerte dans ${reste} s` : `Retour à la navigation dans ${reste} s`;
        ecrire('alerte-retour', modeChoisi === 'combat' ? 'Vue combat forcée' : sousMenace ? 'Menace toujours présente' : fin);
    }

    function signalerMenace(evenement) {
        derniereMenace = Date.now();
        causeMenace = evenement.texte;
        // impact : 'bouclier' | 'effondrement' | 'coque', déduit par le backend (lecteur_logs.py)
        if (evenement.impact) signalerImpact(evenement.impact, IMPACTS_FORTS.has(evenement.nom));
        evaluerMode();
    }

    // ----------------------------------------------------------------
    //  CHANGEMENT D'INTERFACE : grésillement d'un quart de seconde
    //  Tout se joue sur un canvas posé par-dessus : l'hologramme n'est jamais redessiné.
    // ----------------------------------------------------------------
    const voulue = { mode: 'nav', commandes: 'vol' };
    let affichee = null;              // ce qui est à l'écran (null avant le premier rendu)
    let interfacePrete = false;       // le premier état reçu s'affiche sans effet
    let minuterieBascule = 0, prochainGresillement = 0, protectionCommandes = 0;

    const interfaceAJour = () => affichee?.mode === voulue.mode && affichee?.commandes === voulue.commandes;
    // En vue combat, le panneau de commandes de navigation est caché : rien à montrer
    const changementVisible = () => affichee.mode !== voulue.mode || voulue.mode === 'nav';

    function appliquerInterface() {
        if (affichee && affichee.mode !== voulue.mode) protectionCommandes = performance.now() + PROTECTION_COMMANDES;
        document.body.dataset.mode = voulue.mode;
        if (affichee?.commandes !== voulue.commandes) {
            tous('[data-commandes]').forEach(bloc => { bloc.hidden = bloc.dataset.commandes !== voulue.commandes; });
            ecrire('commandes-contexte', CONTEXTES_COMMANDES[voulue.commandes]);
            if (affichee) protectionCommandes = performance.now() + PROTECTION_COMMANDES;
        }
        affichee = { ...voulue };
    }

    function demanderInterface(mode, commandes) {
        voulue.mode = mode;
        voulue.commandes = commandes;
        if (interfaceAJour() || minuterieBascule) return;
        const accueilVisible = MODE_APP && !$('ecran-accueil').hidden;
        if (!affichee || !interfacePrete || accueilVisible) { appliquerInterface(); return; }
        minuterieBascule = setTimeout(gresiller, Math.max(0, prochainGresillement - performance.now()));
    }

    function gresiller() {
        minuterieBascule = 0;
        if (interfaceAJour()) return;                 // l'état est revenu entre-temps
        if (document.hidden || !changementVisible()) { appliquerInterface(); return; }
        prochainGresillement = performance.now() + ECART_GRESILLEMENTS;
        jouerParasites(voulue.mode, MILIEU_GRESILLEMENT);
        minuterieBascule = setTimeout(() => {
            minuterieBascule = 0;
            appliquerInterface();
        }, MILIEU_GRESILLEMENT);
    }

    /** Changement d'écran immédiat (réglages, accueil) : les parasites partent de leur maximum
        et couvrent le changement fait juste après, sans retarder le clic. */
    function gresillerEcran() {
        const maintenant = performance.now();
        if (document.hidden || maintenant < prochainGresillement - ECART_GRESILLEMENTS + ECART_GRESILLEMENTS_CLICS) return;
        prochainGresillement = maintenant + ECART_GRESILLEMENTS;
        jouerParasites(voulue.mode, 0);
    }

    let parasitesEnCours = 0, finParasites = 0;

    function cacherParasites() {
        const toile = $('gresillement');
        if (toile.matches('[popover]:popover-open')) toile.hidePopover();
        toile.removeAttribute('popover');
        toile.hidden = true;
    }

    function jouerParasites(mode, montee) {
        const toile = $('gresillement');
        const contexte = toile.getContext('2d');
        if (!contexte) return;
        clearTimeout(finParasites);
        cacherParasites();
        const jeton = ++parasitesEnCours;
        toile.width = 320;                            // basse définition : de gros grains, peu de calcul
        toile.height = Math.max(90, Math.round(320 * innerHeight / Math.max(innerWidth, 1)));
        const image = contexte.createImageData(toile.width, toile.height);
        const pixels = new Uint32Array(image.data.buffer);
        const [rouge, vert, bleu] = { combat: [255, 74, 40], vrs: [240, 190, 70], pied: [150, 215, 115], nomade: [80, 216, 196], chasseur: [199, 155, 255] }[mode] || [255, 158, 72];
        const debut = performance.now();

        const trame = () => {
            if (toile.hidden || jeton !== parasitesEnCours) return;
            const t = Math.min(1, (performance.now() - debut) / DUREE_GRESILLEMENT);
            const pic = montee / DUREE_GRESILLEMENT;
            const force = t < pic ? t / pic : (1 - t) / (1 - pic);
            for (let y = 0, i = 0; y < toile.height; y++) {
                const tirage = Math.random();         // lignes déchirées : plus claires ou noires
                const gain = tirage < 0.07 ? 1.5 : tirage < 0.16 ? 0.12 : 1;
                for (let x = 0; x < toile.width; x++, i++) {
                    const grain = Math.random();
                    const lumiere = Math.min(1, grain * grain * gain);
                    const alpha = Math.round(255 * force * (0.72 + 0.28 * grain));
                    pixels[i] = (alpha << 24) | (Math.round(bleu * lumiere) << 16)
                        | (Math.round(vert * lumiere) << 8) | Math.round(rouge * lumiere);
                }
            }
            contexte.putImageData(image, 0, 0);
            requestAnimationFrame(trame);
        };
        toile.hidden = false;
        if (document.querySelector('dialog[open]')) {  // une fenêtre modale passe au-dessus de tout le reste
            toile.setAttribute('popover', 'manual');
            toile.showPopover();
        }
        trame();
        finParasites = setTimeout(cacherParasites, DUREE_GRESILLEMENT);   // même si la fenêtre ne se redessine plus
    }

    // ----------------------------------------------------------------
    //  MESSAGES DU BACKEND
    // ----------------------------------------------------------------
    /** Le bouton Stop n'existe à l'écran que pendant un programme du backend. */
    function afficherStop(actif) {
        $('bouton-stop').hidden = !actif;
    }

    function recevoir(message) {
        if (message.type === 'programme') {
            afficherStop(Boolean(message.nom));
        } else if (message.type === 'etat') {
            Object.assign(etat, message.etat);
            memoriserSantes(etat.modules.liste);
            cleDernierScan = cleScan(ficheDernier());      // déjà connu : pas de carte à l'ouverture
            journal = [...(message.historique || [])].reverse();
            rendreTout();
            interfacePrete = true;
        } else if (message.type === 'maj') {
            // Modules : la santé reçue est comparée au relevé précédent (avant le rendu, pour marquer les lignes)
            if (message.section === 'modules') signalerModulesTouches(modulesTouches(message.donnees.liste));
            etat[message.section] = message.donnees;
            if (message.section === 'exploration') signalerScan();
            (RENDUS[message.section] || []).forEach(f => f());
        } else if (message.type === 'evenement') {
            const e = message.evenement;
            journal = [e, ...journal.filter(x => x.id !== e.id)].slice(0, LIGNES_JOURNAL_MAX);
            rendreJournal();
            if (e.hostile) signalerMenace(e);
        } else if (message.type === 'rapport_avarie') {
            afficherRapport(message.rapport);
        } else if (message.type === 'reglages') {
            window.COVAS_REGLAGES?.recevoir(message);
            marquerTouches(message.reglages);
        }
    }

    /** Réglages modifiés (reglages.js) : le backend les enregistre et les renvoie à toutes les interfaces. */
    function envoyerReglages(reglages, rev) {
        if (simulation) {
            recevoir({ type: 'reglages', reglages, rev });
            return true;
        }
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ reglages, rev }));
            return true;
        }
        // Écran d'accueil : le COVAS est en veille, l'application enregistre elle-même
        const api = window.pywebview?.api;
        if (!MODE_APP || document.body.dataset.liaison !== 'veille' || !api?.reglages_ecrire) return false;
        api.reglages_ecrire(reglages).then(r => recevoir({ type: 'reglages', ...r, rev }));
        return true;
    }

    /** Plan installé depuis l'atelier : l'hologramme du vaisseau change tout de suite. */
    function majPlan(plan) {
        window.COVAS_HOLOGRAMMES?.enregistrer(plan);
        hologrammes.forEach(h => { if (h.id === plan.id) h.poserPlan(plan, plan.id); });
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
            afficherStop(false);        // plus de backend : plus rien à arrêter
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
                        gresillerEcran();
                        accueil.hidden = false;
                        if (socket) { socket.onclose = null; socket.close(); }
                        afficherStop(false);
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
            if (accueil.hidden) return;
            if (derniere && !derniere.className) derniere.className = 'fait';
            gresillerEcran();
            accueil.hidden = true;
            document.body.classList.add('allumage');
            setTimeout(() => document.body.classList.remove('allumage'), 1200);
        };

        // Fenêtre rechargée (F5) alors que le COVAS tourne déjà : on rejoint directement le panneau
        const verifier = async () => {
            try {
                const reglages = await window.pywebview.api.reglages_lire?.();
                if (reglages) recevoir({ type: 'reglages', reglages });
                if (await window.pywebview.api.etat() === 'actif') { etat('pret', 'COVAS en ligne', 'En ligne'); connecter(); }
            } catch (_) { /* API pas prête */ }
        };
        if (window.pywebview?.api) verifier();
        else window.addEventListener('pywebviewready', verifier, { once: true });
        bouton.focus();
    }

    // ----------------------------------------------------------------
    //  QUITTER L'APPLICATION
    //  Deux clics : le premier arme le bouton quelques secondes. Un double-clic ne suffit pas,
    //  pour ne pas couper le COVAS par erreur en plein vol.
    // ----------------------------------------------------------------
    const DUREE_CONFIRMATION = 4000;  // ms pendant lesquelles le bouton reste armé
    const DELAI_ANTI_DOUBLE = 350;    // ms avant que le second clic soit accepté

    function installerQuitter() {
        if (!MODE_APP) return;          // dans un navigateur, il n'y a pas d'application à fermer
        tous('[data-quitter]').forEach(bouton => {
            let armeDepuis = 0, minuterie = 0;
            const desarmer = () => {
                clearTimeout(minuterie);
                armeDepuis = 0;
                bouton.classList.remove('arme');
                bouton.setAttribute('aria-label', 'Quitter le COVAS');
            };
            bouton.hidden = false;
            bouton.onblur = desarmer;
            bouton.onclick = () => {
                if (!armeDepuis) {
                    armeDepuis = performance.now();
                    bouton.classList.add('arme');
                    bouton.setAttribute('aria-label', 'Confirmer : quitter le COVAS');
                    minuterie = setTimeout(desarmer, DUREE_CONFIRMATION);
                    return;
                }
                if (performance.now() - armeDepuis < DELAI_ANTI_DOUBLE) return;
                const api = window.pywebview?.api;
                if (!api?.quitter) { desarmer(); return; }
                clearTimeout(minuterie);
                bouton.disabled = true;
                api.quitter();
            };
        });
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
        tous('[data-action]').forEach(bouton => {
            bouton.onclick = () => {
                if (bouton.closest('[data-commandes], .vue-surface, .vue-chasseur') && performance.now() < protectionCommandes) return;
                envoyerAction(bouton.dataset.action);
            };
        });
        tous('.parler').forEach(formulaire => {
            formulaire.onsubmit = event => {
                event.preventDefault();
                const champ = formulaire.querySelector('input');
                const question = champ.value.trim();
                if (question && envoyerQuestion(question)) champ.value = '';
            };
        });
        installerBoussole();
        installerQuitter();
        $('selecteur-mode').onclick = () => {
            modeChoisi = { auto: 'combat', combat: 'nav', nav: 'auto' }[modeChoisi];
            garderPreference('covas-mode', modeChoisi);
            evaluerMode();
        };
        window.COVAS_REGLAGES?.installer({ envoyer: envoyerReglages, action: envoyerAction, noms: VAISSEAUX, majPlan, gresiller: gresillerEcran });
        $('bouton-demo').hidden = !window.COVAS_DEMO;
        $('bouton-demo').onclick = lancerSimulation;

        // Horloge (l'année du jeu = année réelle + 1286) et minuterie de retour en navigation
        const tic = () => {
            const d = new Date();
            ecrire('heure', d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }));
            ecrire('date', d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' }) + ' ' + (d.getFullYear() + 1286));
            rendreTauxChasse();
            rendreCarteScan();
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
