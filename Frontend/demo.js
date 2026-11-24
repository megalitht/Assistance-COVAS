/* =====================================================================
   COVAS — Simulation
   Rejoue un scénario fictif (route, saut, interdiction, combat, amarrage)
   avec les mêmes messages que le backend, pour tester l'interface sans le jeu.
   Ouvre interface.html?demo ou clique « Lancer la simulation ».
   Ce fichier est facultatif : supprime-le et le bouton disparaît.
   ===================================================================== */
window.COVAS_DEMO = (() => {
    'use strict';

    const D = { amarre: 1, train: 4, boucliers: 8, supercroisiere: 16, armes: 64, feux: 256, masse: 65536, fsdCharge: 131072, fsdRefroid: 262144, danger: 4194304, interdiction: 8388608, vaisseau: 16777216, saut: 1073741824 };

    const module = (emplacement, objet, sante = 1, actif = true, ingenierie = null) =>
        ({ emplacement, objet, sante, actif, priorite: 0, puissance: 1.2, ingenierie });

    const MODULES = () => [
        module('LargeHardpoint1', 'hpt_beamlaser_gimbal_large', 1, true, { plan: 'Weapon_Efficient', niveau: 5, effet: 'Ventilation thermique' }),
        module('LargeHardpoint2', 'hpt_multicannon_gimbal_large'),
        module('MediumHardpoint1', 'hpt_multicannon_gimbal_medium'),
        module('MediumHardpoint2', 'hpt_pulselaser_turret_medium'),
        module('TinyHardpoint1', 'hpt_shieldbooster_size0_class5'),
        module('TinyHardpoint2', 'hpt_chafflauncher_tiny'),
        module('TinyHardpoint3', 'hpt_heatsinklauncher_turret_tiny'),
        module('Armour', 'krait_mkii_armour_grade3'),
        module('PowerPlant', 'int_powerplant_size7_class5', 1, true, { plan: 'PowerPlant_Armoured', niveau: 4 }),
        module('MainEngines', 'int_engine_size6_class5', 1, true, { plan: 'Engine_Dirty', niveau: 5 }),
        module('FrameShiftDrive', 'int_hyperdrive_overcharge_size5_class5'),
        module('LifeSupport', 'int_lifesupport_size4_class2'),
        module('PowerDistributor', 'int_powerdistributor_size7_class5'),
        module('Radar', 'int_sensors_size6_class2'),
        module('FuelTank', 'int_fueltank_size5_class3'),
        module('Slot01_Size6', 'int_shieldgenerator_size6_class3_fast'),
        module('Slot02_Size6', 'int_cargorack_size5_class1'),
        module('Slot03_Size5', 'int_fuelscoop_size5_class5'),
        module('Slot04_Size5', 'int_shieldcellbank_size5_class5'),
        module('Slot05_Size4', 'int_repairer_size4_class5', 1, false),
        module('Slot06_Size3', 'int_hullreinforcement_size3_class2'),
        module('Slot08_Size2', 'int_dockingcomputer_advanced'),
        module('ShipCockpit', 'krait_mkii_cockpit'),
        module('CargoHatch', 'modularcargobaydoor'),
    ];

    const ROUTE = [['Sol', 'G', 0], ['Alpha Centauri', 'G', 4.38], ['Wolf 359', 'M', 8.33], ['Lalande 21185', 'M', 4.09],
        ['Ross 128', 'M', 8.71], ['Procyon', 'F', 9.93], ['Luyten\'s Star', 'M', 1.2], ['Sirius', 'A', 6.5]];

    const etapes = () => ROUTE.map(([systeme, classe, distance]) => ({ systeme, classe, distance, ravitaillable: 'KGBFOAM'.includes(classe) }));
    // Même résumé que Backend/module/jeu/route.py (sauts et distance restants, progression)
    const routeDemo = indice => {
        const liste = etapes(), total = liste.reduce((t, e) => t + e.distance, 0);
        const restante = liste.slice(indice + 1).reduce((t, e) => t + e.distance, 0);
        return {
            etapes: liste, distance_totale: total, indice_actuel: indice, sauts_restants: liste.length - 1 - indice,
            nombre_sauts: liste.length - 1, distance_restante: restante, distance_parcourue: total - restante,
            progression: (total - restante) / total, destination: liste[liste.length - 1].systeme, source: 'route',
        };
    };

    // Vaisseaux présentés à tour de rôle : un changement au chantier naval à chaque fin de boucle
    const VITRINE = [
        ['krait_mkii', 'Krait Mk II', 'Vent Solaire', 'CV-08K'],
        ['python_nx', 'Python Mk II', 'Aiguillon', 'CV-21P'],
        ['explorer_nx', 'Caspian Explorer', 'Horizon Lointain', 'CV-77C'],
        ['anacondamkii', 'Anaconda Mk II', 'Grand Serpent', 'CV-02A'],
        ['cutter', 'Imperial Cutter', 'Lame Pourpre', 'CV-19I'],
        ['mandalay', 'Mandalay', 'Albatros', 'CV-44M'],
    ];
    const depart = new URLSearchParams(location.search).get('vaisseau');
    let rang = Math.max(0, VITRINE.findIndex(v => v[0] === depart));

    // Noms des modules que le scénario abîme (le vrai rapport vient de Backend/module/jeu/avaries.py)
    const NOMS = { MediumHardpoint2: 'Laser à impulsions tourelle', MainEngines: 'Propulseurs', Slot04_Size5: 'Cellules de bouclier', PowerPlant: 'Générateur', Radar: 'Capteurs', ShipCockpit: 'Verrière' };
    // Mêmes valeurs de départ que Backend/module/interface/reglages.py
    const mode = (id, nom, declencheur, applicable = true) => ({ id, nom, base: true, declencheur, applicable });
    const REGLAGES = {
        pips: {
            modes: [mode('mode_combat', 'Combat', '« mode combat »'), mode('mode_esquive', 'Esquive', '« mode esquive »'),
                mode('mode_croisiere', 'Croisière', '« mode croisière »'), mode('mode_recuperation', 'Récupération', '« récupération »'),
                mode('pips_defense', 'Défense', 'Fuite et interdiction'), mode('fsd', 'Saut FSD', 'Au lancement du FSD', false)],
            defaut: { mode_combat: [4, 0, 8], mode_esquive: [6, 6, 0], mode_croisiere: [4, 8, 0], mode_recuperation: [8, 4, 0], pips_defense: [8, 4, 0], fsd: [4, 8, 0] },
            vaisseaux: { python_nx: { mode_combat: [6, 0, 6] } },
        },
    };
    // interface.html?demo=vrs ou ?demo=pied : aperçu de la vue de surface
    const SCENE = ['vrs', 'pied', 'nomade', 'chasseur', 'chasse', 'explo', 'carburant'].find(s => s === new URLSearchParams(location.search).get('demo')) || null;

    // Corps d'exemple pour les vues exploration, Nomad et pied à terre
    const biologie = (signaux, lignes, bonus) => {
        const min = lignes.reduce((t, l) => t + l.min, 0), max = lignes.reduce((t, l) => t + l.max, 0), f = bonus ? 5 : 1;
        return { signaux, lignes, min, max, min_bonus: min * f, max_bonus: max * f, bonus, approx: false, analysees: lignes.filter(l => l.etat === 'analyse').length };
    };
    const corpsDemo = (id, court, classe, valeur, valeur_carto, options = {}) => ({
        id, nom: `Alpha Centauri ${court}`, court, classe, etoile: false, terraformable: false, atterrissable: true, distance_ls: 1200 + id * 310, connu: true,
        premiere_decouverte: false, premiere_carto: false, premier_pas: false, balise: false, cartographie: false, valeur, valeur_carto, bio: null, ...options,
        potentiel: valeur_carto + (options.bio ? options.bio.max_bonus : 0),
    });
    const explorationDemo = () => {
        const corps = [
            corpsDemo(7, 'A 2 b', 'Rocheux', 1480, 18340, { premiere_decouverte: true, premiere_carto: true, premier_pas: true, bio: biologie(3, [
                { genre: 'Stratum', espece: 'Stratum Tectonicas', min: 19010800, max: 19010800, etat: 'prelevement', possibles: 1 },
                { genre: 'Bacterium', espece: null, min: 1000000, max: 1689800, etat: 'detecte', possibles: 3 },
                { genre: 'Touradon', espece: 'Touradon Ignis', min: 1849000, max: 1849000, etat: 'analyse', possibles: 1 },
            ], true) }),
            corpsDemo(4, 'A 1', 'Monde terrestre', 695400, 7842100, { atterrissable: false, premiere_decouverte: true, premiere_carto: true, terraformable: true }),
            corpsDemo(9, 'A 3', 'Haute teneur en métaux', 13200, 142800, { terraformable: true, cartographie: true, valeur: 142800 }),
            corpsDemo(12, 'B 1 a', 'Glacé', 520, 2380, { bio: biologie(1, [{ genre: 'Fonticulua', espece: null, min: 1000000, max: 1804100, etat: 'detecte', possibles: 2 }], false) }),
            corpsDemo(15, 'B 2', 'Géante gazeuse I', 3820, 14900, { atterrissable: false }),
        ].sort((a, b) => b.potentiel - a.potentiel);
        return {
            systeme: 'Alpha Centauri', corps, dernier: 7, total: corps.reduce((t, c) => t + c.valeur, 0), total_carto: corps.reduce((t, c) => t + c.valeur_carto, 0),
            bio_min: corps.reduce((t, c) => t + (c.bio?.min_bonus || 0), 0), bio_max: corps.reduce((t, c) => t + (c.bio?.max_bonus || 0), 0), premieres: 2,
            session: { a_vendre: 8420300, corps: 23, exo: 9245000, exo_especes: 1, vendu: 0, exo_vendu: 0 },
        };
    };
    // Réservoir (même forme que Backend/module/jeu/carburant.py, Reservoir.vue)
    const carburantDemo = (niveau, restants = 6, capacite = 32, conso = 2.4) => {
        const part = niveau / capacite, besoin = restants * conso;
        return {
            niveau, capacite, part, etat: part < 0.1 ? 'critique' : part < 0.25 ? 'bas' : 'ok', seuil_bas: 0.25, seuil_critique: 0.1,
            conso, source: 'historique', historique: 10, sauts: Math.floor(niveau / conso), fsd_max: 5.2, collecteur: true,
            route: restants ? { cible: 'destination', sauts: restants, besoin: Math.round(besoin * 10) / 10, suffisant: niveau >= besoin * 1.1 } : null,
        };
    };
    const verdictDemo = (code, libelle, tirer, conseil, prime = 0, extra = {}) => ({ code, libelle, tirer, conseil, prime, joueur: false, dangereux: false, gros: prime >= 500000, ...extra });
    const CIBLES_DEMO = [
        { vaisseau: 'Python', pilote: 'Lawrence Yuki', rang: 'Deadly', faction: 'Pikum Family', statut: 'Wanted', prime: 668764, boucliers: 100, coque: 100, verdict: verdictDemo('recherche', 'Recherché', true, 'Feu autorisé', 668764, { dangereux: true }) },
        { vaisseau: 'Eagle', pilote: 'Joseph Pimley', rang: 'Expert', faction: 'Pranav Antal', statut: 'Clean', boucliers: 82, coque: 100, verdict: verdictDemo('clean', 'En règle', false, 'Ne tirez pas') },
        { vaisseau: 'Viper Mk III', pilote: 'Vaisseau des autorités', rang: 'Expert', faction: 'Pikum Public Group', statut: 'Clean', boucliers: 100, coque: 100, verdict: verdictDemo('autorite', 'Autorités', false, 'Ne tirez surtout pas') },
        { vaisseau: 'Cobra Mk III', pilote: 'Will Blackburn', rang: 'Master', faction: 'Baldr Camorra', statut: 'Wanted', prime: 73686, boucliers: 45, coque: 88, verdict: verdictDemo('recherche', 'Recherché', true, 'Feu autorisé', 73686) },
    ];
    const BASCULES_VRS = { vrs_frein: 1 << 12, vrs_assistance: 1 << 15, vrs_phares: 1 << 8, vrs_tourelle: 1 << 13, vrs_soute: 1 << 9 };
    let actionCourante = null;       // réponse de la simulation aux boutons de l'interface
    let questionCourante = null;     // réponse de la simulation aux phrases écrites au COVAS

    function demarrer(recevoir) {
        let identifiant = 0, minuteries = [], derniere = null;
        let etat, status;

        const maj = (section, donnees) => { Object.assign(etat[section], donnees); recevoir({ type: 'maj', section, donnees: etat[section] }); };
        const majStatus = donnees => { Object.assign(status, donnees); recevoir({ type: 'maj', section: 'status', donnees: status }); };
        // Comme le backend : les salves successives se fondent en une seule ligne (×n)
        const note = (nom, categorie, texte, gravite = 'info', hostile = false, impact = null) => {
            const fusion = nom === 'UnderAttack' && derniere?.nom === 'UnderAttack';
            derniere = { id: fusion ? derniere.id : ++identifiant, h: new Date().toISOString(), nom, categorie, gravite, texte, hostile, n: fusion ? derniere.n + 1 : 1, ...(impact && { impact }) };
            recevoir({ type: 'evenement', evenement: derniere });
        };
        // Le jeu n'écrit la coque qu'aux paliers 80, 60, 40, 20 % (HullDamage)
        const coque = sante => { maj('vaisseau', { coque: sante, coque_palier: true, dernier_coup: new Date().toISOString() }); maj('combat', { coups_coque: etat.combat.coups_coque + 1 }); note('HullDamage', 'combat', `Coque touchée — intégrité ${Math.round(sante * 100)} %`, sante <= 0.3 ? 'alerte' : 'attention', true, 'coque'); };
        // Salve reçue : absorbée par le bouclier ou encaissée par la coque
        const salve = impact => note('UnderAttack', 'combat', 'Sous le feu ennemi', 'alerte', true, impact);
        // En vrai, la santé des modules n'arrive qu'à certains moments (retour du chasseur...) ; la démo la donne à chaque coup
        const abimer = (emplacement, sante) => { etat.modules.liste.find(m => m.emplacement === emplacement).sante = sante; etat.modules.releve = new Date().toISOString(); maj('modules', {}); };

        // Rapport d'avarie, version simulation (même forme que le message du backend)
        function rapportAvarie() {
            const v = etat.vaisseau, boucliers = !!(status.flags & D.boucliers), pc = x => Math.round(x * 100);
            const avaries = etat.modules.liste.filter(m => m.sante != null && m.sante < 0.8).sort((a, b) => a.sante - b.sante)
                .map(m => ({ emplacement: m.emplacement, nom: NOMS[m.emplacement] || m.emplacement, sante: m.sante, hs: m.sante <= 0 }));
            const etatCoque = v.coque >= 0.995 ? 'coque intacte' : v.coque_palier ? `coque < ${Math.min(100, Math.max(20, Math.ceil(v.coque * 5 - 1e-9) * 20))} %` : `coque ${pc(v.coque)} %`;
            const compte = avaries.length ? `${avaries.length} avarie${avaries.length > 1 ? 's' : ''}` : 'aucune avarie';
            const debut = [etatCoque, v.verriere_brisee && 'verrière brisée', boucliers ? 'boucliers en ligne' : 'boucliers hors ligne'].filter(Boolean);
            const detail = avaries.map(a => `${a.nom} ${a.hs ? 'HS' : pc(a.sante) + ' %'}`).join(', ');
            const gravite = avaries.some(a => a.hs) || v.verriere_brisee || v.coque < 0.3 ? 'alerte' : avaries.length || !boucliers || v.coque < 0.8 ? 'attention' : 'succes';
            return {
                h: new Date().toISOString(), coque: v.coque, coque_palier: !!v.coque_palier, boucliers, verriere_brisee: !!v.verriere_brisee,
                avaries, releve: etat.modules.releve, perime: false, gravite,
                texte: `Rapport d'avarie — ${[...debut, compte + (detail ? ' : ' + detail : '')].join(' · ')}`, resume: [...debut, compte].join(' · '),
            };
        }
        // Phrase écrite au COVAS : la simulation n'a pas le moteur de conversation (backend)
        questionCourante = texte => {
            const ligne = (locuteur, t, detail) => recevoir({ type: 'evenement', evenement: { id: ++identifiant, h: new Date().toISOString(), nom: locuteur, categorie: 'comms', gravite: 'info', texte: `${locuteur} : ${t}`, hostile: false, n: 1, locuteur: locuteur.toLowerCase(), ...(detail && { detail }) } });
            ligne('CMDR', texte);
            ligne('COVAS', 'Simulation : je vous répondrai quand le backend sera lancé, commandant.', 'Backend/main.py');
        };
        actionCourante = nom => {
            const pips = window.COVAS_REGLAGES?.pipsPour(nom);
            if (pips) { majStatus({ pips }); return; }           // mode d'énergie : aucune touche, juste l'affichage
            if (nom !== 'rapport_avarie') return;               // les autres boutons n'ont rien à simuler
            const r = rapportAvarie();
            note('COVAS', 'vaisseau', r.texte, r.gravite);
            recevoir({ type: 'rapport_avarie', rapport: r });
        };

        /** Le commandant s'éloigne du vaisseau en tournant : la boussole et les distances vivent. */
        function scenarioSurface() {
            const enVrs = SCENE === 'vrs';
            Object.assign(status, {
                flags: enVrs ? (1 << 26) | (1 << 21) | (1 << 15) | (1 << 8) : 1 << 21,
                flags2: enVrs ? 0 : 1 | (1 << 4) | (1 << 15),
                pips: enVrs ? [4, 6, 2] : [0, 0, 0], groupe_tir: 0, carburant: 0, reserve: 0.41,
                corps: 'Alpha Centauri A 2 b', latitude: -20.6143, longitude: 102.1771, altitude: 0, cap: 40, rayon: 1800000,
                ...(enVrs ? {} : { oxygene: 0.82, sante: 1, temperature: 214, gravite: 0.31, arme: 'Échantillonneur génétique' }),
            });
            etat.position.corps = status.corps;
            etat.sol = {
                vaisseau: { etat: 'pose', latitude: -20.6, longitude: 102.17, corps: status.corps, distance: 412, cap: 118 },
                vrs: enVrs ? { modele: 'Scarabée VRS' } : null,
                combinaison: enVrs ? null : { nom: 'Combinaison Artemis', chargement: 'ANALYSE', armes: ['Karma AR-50', 'Karma P-15'] },
                exobio: enVrs ? null : { id: 'demo', espece: 'Stratum Tectonicas', genre: 'Stratum', variante: 'Stratum Tectonicas - Vert', portee: 500, echantillons: 1, termine: false, points: [[-20.6, 102.17]], corps: status.corps, distance: 312, libre: false },
            };
            recevoir({ type: 'etat', etat, historique: [] });
            note('LoadGame', 'systeme', 'Session ouverte — CMDR Démo', 'succes');
            note(enVrs ? 'LaunchSRV' : 'Disembark', 'vaisseau', enVrs ? 'VRS déployé' : 'Débarquement à pied');
            if (!enVrs) note('ScanOrganic', 'exploration', 'Prélèvement 1/3 — Stratum Tectonicas');

            actionCourante = action => {
                if (BASCULES_VRS[action]) majStatus({ flags: status.flags ^ BASCULES_VRS[action] });
                note('COVAS', 'covas', `Simulation : ${action} (aucune touche envoyée)`);
            };
            let tours = 0;
            minuteries = [setInterval(() => {
                tours++;
                const sol = etat.sol, exo = sol.exobio;
                sol.vaisseau.distance = 412 + tours * 9;
                sol.vaisseau.cap = (118 + tours) % 360;
                if (exo && !exo.libre) { exo.distance += 15; exo.libre = exo.distance >= exo.portee; }
                recevoir({ type: 'maj', section: 'sol', donnees: sol });
                majStatus({ cap: (status.cap + 6) % 360, latitude: status.latitude + 0.0002 });
            }, 1500)];
        }

        /** Chasse aux primes, chasseur embarqué, Nomad ou exploration : un état fixe, les cibles défilent. */
        function scenarioChasse() {
            const chasseur = SCENE === 'chasseur';
            Object.assign(status, { flags: chasseur ? D.boucliers | D.danger | (1 << 25) : D.vaisseau | D.boucliers | D.armes | D.danger, pips: [4, 2, 6] });
            etat.pilotage = chasseur ? { genre: 'chasseur', modele: 'Gu-97', coque: 0.8 } : { genre: null, modele: null, coque: null };
            etat.vaisseau.chasseur = chasseur ? 'deploye' : null;
            etat.position.corps = 'Alpha Centauri A 2 Ring';
            etat.chasse = {
                actif: true, manuel: false, zone: 'res_danger', zone_nom: "Site d'extraction [Danger]", depuis: new Date(Date.now() - 1460000).toISOString(),
                profil: { armes: 6, scanner: true, pret: true }, eliminations: 14, gains: 8650400, meilleure: 1240500, scannes: 31, recherches: 18,
                a_encaisser: { 'Pikum Public Group': 6120300, 'Alliance de Baldr': 2530100 }, a_encaisser_total: 8650400,
            };
            etat.cible = { verrouillee: true, scan: 3, ...CIBLES_DEMO[0] };
            recevoir({ type: 'etat', etat, historique: [] });
            note('Chasse', 'combat', "Mode chasseur de primes activé — Site d'extraction [Danger]", 'succes');
            note('ShipTargeted', 'combat', 'Cible recherchée : Lawrence Yuki — prime 668 764 cr', 'attention');
            let i = 0;
            minuteries = [setInterval(() => {
                i = (i + 1) % CIBLES_DEMO.length;
                recevoir({ type: 'maj', section: 'cible', donnees: { verrouillee: true, scan: 3, ...CIBLES_DEMO[i] } });
            }, 4000)];
            actionCourante = action => {
                if (!action.startsWith('chasse|')) return;
                etat.chasse.actif = action === 'chasse|active';
                recevoir({ type: 'maj', section: 'chasse', donnees: etat.chasse });
            };
        }

        function scenarioNomade() {
            Object.assign(status, { flags: D.boucliers | (1 << 26) | (1 << 21), flags2: 0, pips: [4, 4, 4], corps: 'Alpha Centauri A 2 b', latitude: -20.6143, longitude: 102.1771, altitude: 842, cap: 40, rayon: 1800000 });
            etat.position.corps = status.corps;
            etat.pilotage = { genre: 'nomade', modele: 'Nomad', coque: 1 };
            recevoir({ type: 'etat', etat, historique: [] });
            note('LaunchVessel', 'exploration', 'Nomad déployé');
            note('SAASignalsFound', 'exploration', 'Vie sur Alpha Centauri A 2 b : Stratum, Bacterium, Touradon', 'succes');
            minuteries = [setInterval(() => majStatus({ cap: (status.cap + 4) % 360, altitude: Math.max(40, status.altitude - 25) }), 1200)];
        }

        /** ?demo=carburant : le réservoir se vide (orange sous 25 %, rouge clignotant sous 10 %), puis le plein. */
        function scenarioCarburant() {
            Object.assign(status, { flags: D.vaisseau | D.boucliers | D.supercroisiere, carburant: 12 });
            etat.carburant = carburantDemo(12);
            recevoir({ type: 'etat', etat, historique: [] });
            minuteries = [setInterval(() => {
                const niveau = status.carburant <= 1 ? 32 : Math.round((status.carburant - 1.5) * 10) / 10;
                majStatus({ carburant: niveau });
                recevoir({ type: 'maj', section: 'carburant', donnees: (etat.carburant = carburantDemo(niveau)) });
                if (niveau === 32) note('RefuelAll', 'station', 'Ravitaillement +31,0 t — 1 550 cr');
            }, 1500)];
        }

        function scenarioExplo() {
            Object.assign(status, { flags: D.vaisseau | D.boucliers | D.supercroisiere });
            recevoir({ type: 'etat', etat, historique: [] });
            note('FSSDiscoveryScan', 'exploration', 'Balayage du système — 17 corps détectés');
            let i = 1;
            const relancer = () => {
                const liste = etat.exploration.corps;
                etat.exploration = { ...etat.exploration, dernier: liste[i++ % liste.length].id };
                recevoir({ type: 'maj', section: 'exploration', donnees: etat.exploration });
            };
            relancer();
            minuteries = [setInterval(relancer, 6000)];
            document.querySelector('[data-onglet="exploration"]')?.click();
        }

        function scenario() {
            const [type, modele, nom, immat] = VITRINE[rang % VITRINE.length];
            status = { flags: D.vaisseau | D.boucliers | D.supercroisiere, flags2: 0, pips: [4, 4, 4], groupe_tir: 0, carburant: 24.3, reserve: 0.41, soute: 14, statut_legal: 'Clean', credits: 148230511, destination: 'Alpha Centauri' };
            etat = {
                session: { jeu_actif: true },
                commandant: { nom: 'Démo', credits: 148230511, mode_jeu: 'Solo', rangs: { Combat: 6, Trade: 5, Explore: 4, Exobiologist: 2, Federation: 4, Empire: 3 }, progression: { Combat: 41, Trade: 77, Explore: 12, Exobiologist: 5, Federation: 60, Empire: 30 } },
                vaisseau: { type, modele, nom, immat, coque: 1, boucliers: true, portee_saut: 31.42, soute_max: 32, carburant_max: 32, reserve_max: 0.63, rachat: 6234110, verriere_brisee: false, chasseur: null },
                position: { systeme: 'Sol', corps: 'Mars', allegeance: 'Federation', economie: 'Raffinerie', gouvernement: 'Démocratie', securite: 'Sécurité haute', population: 22780919531, faction: 'Mother Gaia', amarre: false, station: null, corps_total: 40, corps_scannes: 12 },
                status,
                route: { ...routeDemo(0), prochain: { systeme: 'Alpha Centauri', classe: 'G', ravitaillable: true, sauts_restants: 6 } },
                modules: { liste: MODULES(), releve: new Date().toISOString() },
                soute: { total: 14, inventaire: [{ nom: 'Or', quantite: 8, vole: false }, { nom: 'Painite', quantite: 4, vole: false }, { nom: 'Générateurs', quantite: 2, vole: true }] },
                cible: { verrouillee: false },
                combat: { eliminations: 0, primes: 0, bons: 0, coups_coque: 0, boucliers_tombes: 0, interdictions: 0, morts: 0 },
                missions: { liste: [{ id: 1, nom: 'Livrer 8 unités d\'or', systeme: 'Sirius', station: 'Patterson Enterprise' }], anterieures: 2 },
                proches: { etat: 'ok', systeme: 'Sol', rayon: 31.42, total: 7, liste: [['Alpha Centauri', 'G', 4.38], ['Barnard\'s Star', 'M', 5.95], ['Luhman 16', 'L', 6.57], ['Wolf 359', 'M', 7.78], ['Lalande 21185', 'M', 8.29], ['Sirius', 'A', 8.59], ['Duamta', 'M', 9.88]].map(([nom, classe, distance]) => ({ nom, classe, distance, ravitaillable: 'KGBFOAM'.includes(classe) })) },
            };
            etat.exploration = explorationDemo();
            etat.carburant = carburantDemo(24.3, 7);
            // Prospecteurs (même forme que Backend/module/jeu/prospection.py, vue())
            const roche = (contenu, materiaux, extra = {}) => ({ h: new Date().toISOString(), contenu, niveau: null, noyau: null, restant: 100,
                materiaux: materiaux.map(([nom, pourcentage, interessant = false]) => ({ cle: nom, nom, pourcentage, interessant })), interessant: materiaux.some(x => x[2]), ...extra });
            etat.minage = { prospectes: 23, interessants: 4, derniers: [
                roche('Élevé', [['Platine', 31.8, true], ['Bertrandite', 12.2], ['Argent', 6.4]]),
                roche('Moyen', [['Tritium', 26.2, true], ['Bromellite', 9.1], ['Eau', 7.5]], { noyau: 'Alexandrite', interessant: true }),
                roche('Faible', [['Hématite', 24.3], ['Indite', 9.9], ['Cobalt', 7.6]]),
            ] };
            // Commerce (même forme que Backend/module/jeu/commerce.py, vue())
            const trajet = (de, vers, marchandises, profit, extra = {}) => ({ debut: null, fin: new Date().toISOString(), issue: 'vente', de, vers, marchandises, cout: 0, recette: profit, frais: 0, pertes: 0, unites_perdues: 0, profit, ...extra });
            etat.commerce = {
                soute: { quantite: 14, capacite: 32 }, stock: [{ nom: 'Or', quantite: 8, prix_moyen: 9120 }, { nom: 'Painite', quantite: 4, prix_moyen: 0 }],
                en_cours: { ...trajet('Mars High', '—', ['Or', 'Painite'], -72960, { fin: null, issue: null, cout: 72960 }) },
                dernier: trajet('Minage', 'Rushworth Station', ['Cobalt', 'Coltan', 'Gallite'], 952787, { frais: 21715 }),
                historique: [trajet('Minage', 'Rushworth Station', ['Cobalt', 'Coltan', 'Gallite'], 952787, { frais: 21715 }),
                    trajet('Abraham Lincoln', 'Hutton Orbital', ['Or'], 184300, { cout: 1240000 }),
                    trajet('Mars High', '—', ['Méta-alliages'], -246598, { issue: 'mort', pertes: 246598, unites_perdues: 1 })],
                session: { debut: null, profit: 1137087, trajets: 2, pertes: 0 },
            };
            // Données non vendues (même forme que Backend/module/jeu/suivi_exploration.py, vue())
            etat.donnees_explo = {
                total: 31840200, cartographie: 22595200, bonus: 23000, bio: 9245000, corps: 87, systemes: 12, especes: 3,
                top: [
                    { nom: 'Alpha Centauri A 1', systeme: 'Alpha Centauri', classe: 'Monde terrestre', valeur: 7842100, valeur_carto: 7842100, cartographie: true, premiere_decouverte: true },
                    { nom: 'Synuefe XT-L b55-1 3', systeme: 'Synuefe XT-L b55-1', classe: "Monde d'eau", valeur: 1210400, valeur_carto: 3254800, cartographie: false, premiere_decouverte: false },
                    { nom: 'HIP 117776 A 4', systeme: 'HIP 117776', classe: 'Haute teneur en métaux', valeur: 812300, valeur_carto: 812300, cartographie: true, premiere_decouverte: false },
                ],
                bio_liste: [{ nom: 'Stratum Tectonicas', systeme: 'Alpha Centauri', valeur: 9245000, bonus: true }],
                derniere_vente: { h: new Date().toISOString(), systemes: 4, reconnus: 4, estimation: 138191, paye: 210795 },
                vendu: { cartographie: 210795, bio: 0 }, paliers: [10, 50, 100],
            };
            etat.chasse = { actif: false, profil: { armes: 6, scanner: true, pret: true }, eliminations: 0, gains: 0, meilleure: 0, a_encaisser: {}, a_encaisser_total: 0 };
            etat.pilotage = { genre: null, modele: null, coque: null };
            if (SCENE === 'chasse' || SCENE === 'chasseur') { scenarioChasse(); return; }
            if (SCENE === 'nomade') { scenarioNomade(); return; }
            if (SCENE === 'explo') { scenarioExplo(); return; }
            if (SCENE === 'carburant') { scenarioCarburant(); return; }
            if (SCENE) { scenarioSurface(); return; }
            recevoir({ type: 'etat', etat, historique: [] });
            note('LoadGame', 'systeme', 'Session ouverte — CMDR Démo', 'succes');
            note('ReceiveText', 'comms', 'Contrôle de Mars High : Bon vol, commandant.');

            const etapesScenario = [
                [3, () => { majStatus({ flags: status.flags | D.fsdCharge }); note('StartJump', 'navigation', 'Saut hyperespace vers Alpha Centauri (classe G)'); }],
                [7, () => majStatus({ flags: D.vaisseau | D.boucliers | D.saut })],
                [10, () => {
                    maj('position', { systeme: 'Alpha Centauri', corps: 'Alpha Centauri A', allegeance: 'Federation', economie: 'Industrie', gouvernement: 'Corporation', securite: 'Sécurité moyenne', population: 825000, faction: 'Hutton Truckers', corps_total: 17, corps_scannes: 0 });
                    maj('route', { ...routeDemo(1), prochain: { systeme: 'Wolf 359', classe: 'M', ravitaillable: true, sauts_restants: 5 } });
                    majStatus({ flags: D.vaisseau | D.boucliers | D.supercroisiere | D.fsdRefroid, carburant: 21.9, destination: 'Wolf 359' });
                    maj('carburant', carburantDemo(21.9, 6));
                    note('FSDJump', 'navigation', 'Arrivée dans Alpha Centauri — 4,4 al', 'succes');
                    note('FSSDiscoveryScan', 'exploration', 'Balayage du système — 17 corps détectés');
                }],
                [14, () => { majStatus({ flags: D.vaisseau | D.boucliers | D.supercroisiere | D.interdiction }); }],
                [17, () => {
                    majStatus({ flags: D.vaisseau | D.boucliers | D.danger | D.masse | D.fsdRefroid });
                    maj('combat', { interdictions: 1, assaillant: 'Rex Varga' });
                    note('Interdicted', 'combat', 'Interdiction par Rex Varga (arraché de supercroisière)', 'alerte', true);
                    note('ReceiveText', 'comms', 'Rex Varga : Largue ta cargaison et tu vivras.');
                }],
                [19, () => { majStatus({ flags: status.flags | D.armes, pips: [4, 2, 6] }); maj('cible', { verrouillee: true, vaisseau: 'Fer-de-Lance', scan: 3, pilote: 'Rex Varga', rang: 'Deadly', boucliers: 100, coque: 100, faction: 'Gang de Hutton', statut: 'Wanted', prime: 412000 }); salve('bouclier'); }],
                [19.7, () => salve('bouclier')],
                [20.4, () => salve('bouclier')],
                [21.2, () => salve('bouclier')],
                [22, () => { maj('vaisseau', { boucliers: false }); majStatus({ flags: status.flags & ~D.boucliers, pips: [8, 0, 4] }); maj('combat', { boucliers_tombes: 1 }); note('ShieldState', 'combat', 'Boucliers hors ligne', 'alerte', true, 'effondrement'); }],
                [22.9, () => salve('coque')],
                [23.5, () => salve('coque')],
                [24, () => { coque(0.79); abimer('MediumHardpoint2', 0.62); maj('cible', { boucliers: 35, coque: 100 }); }],
                [25.3, () => salve('coque')],
                [26.2, () => salve('coque')],
                [27, () => { coque(0.58); abimer('MainEngines', 0.44); abimer('Slot04_Size5', 0.7); }],
                [28.4, () => salve('coque')],
                [29.2, () => salve('coque')],
                [30, () => { coque(0.27); abimer('MediumHardpoint2', 0); abimer('PowerPlant', 0.52); abimer('Radar', 0.33); maj('cible', { boucliers: 0, coque: 41, sous_systeme: 'Générateur', sous_systeme_sante: 22 }); }],
                [31, () => { abimer('ShipCockpit', 0); maj('vaisseau', { verriere_brisee: true }); note('CockpitBreached', 'combat', 'Verrière brisée — oxygène de secours', 'alerte', true, 'coque'); }],
                [32.5, () => actionCourante?.('rapport_avarie')],      // « COVAS, rapport d'avarie »
                [34, () => { maj('cible', { verrouillee: false }); maj('combat', { eliminations: 1, primes: 412000 }); note('Bounty', 'combat', 'Fer-de-Lance détruit — prime 412 000 cr', 'succes'); majStatus({ flags: status.flags & ~D.danger & ~D.masse & ~D.fsdRefroid, pips: [8, 4, 0] }); }],
                [44, () => { maj('vaisseau', { boucliers: true }); majStatus({ flags: (status.flags | D.boucliers) & ~D.armes, pips: [4, 4, 4] }); note('ShieldState', 'combat', 'Boucliers rétablis', 'succes'); }],
                [62, () => { majStatus({ flags: D.vaisseau | D.boucliers | D.supercroisiere }); note('StartJump', 'navigation', 'Passage en supercroisière'); }],
                [67, () => { majStatus({ flags: D.vaisseau | D.boucliers | D.train | D.feux | D.masse }); maj('position', { corps: 'Hutton Orbital', station: { nom: 'Hutton Orbital', type: 'Outpost', plateforme: 2, services: [] } }); note('DockingGranted', 'station', 'Appontage autorisé — plateforme 2', 'succes'); }],
                [72, () => {
                    majStatus({ flags: D.vaisseau | D.amarre | D.train | D.feux | D.masse });
                    maj('position', { amarre: true, station: { nom: 'Hutton Orbital', type: 'Outpost', plateforme: 2, distance_ls: 6784404, economie: 'Extraction', services: ['commodities', 'outfitting', 'repair', 'refuel', 'rearm', 'missions', 'contacts'] } });
                    note('Docked', 'station', 'Amarré à Hutton Orbital', 'succes');
                }],
                [77, () => { etat.modules.liste.forEach(m => { m.sante = 1; }); maj('modules', {}); maj('vaisseau', { coque: 1, coque_palier: false, dernier_coup: null, verriere_brisee: false }); note('RepairAll', 'station', 'Réparation complète — 184 220 cr', 'succes'); }],
                [82, () => {
                    rang++;
                    const [type, modele, nom, immat] = VITRINE[rang % VITRINE.length];
                    maj('vaisseau', { type, modele, nom, immat });
                    note('ShipyardSwap', 'station', `Changement de vaisseau : ${modele}`, 'succes');
                }],
                [90, scenario],
            ];
            minuteries = etapesScenario.map(([secondes, action]) => setTimeout(action, secondes * 1000));
        }

        recevoir({ type: 'reglages', reglages: JSON.parse(JSON.stringify(REGLAGES)) });
        scenario();
        return () => { minuteries.forEach(clearTimeout); actionCourante = null; questionCourante = null; };
    }

    /** Bouton de l'interface pendant la simulation (aucune touche n'est envoyée). */
    const action = nom => actionCourante?.(nom);
    /** Phrase écrite au COVAS pendant la simulation. */
    const question = texte => questionCourante?.(texte);

    return { demarrer, action, question };
})();
