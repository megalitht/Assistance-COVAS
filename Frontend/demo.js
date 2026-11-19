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

    // Noms des modules que le scénario abîme (le vrai rapport vient de Backend/module/avaries.py)
    const NOMS = { MediumHardpoint2: 'Laser à impulsions tourelle', MainEngines: 'Propulseurs', Slot04_Size5: 'Cellules de bouclier', PowerPlant: 'Générateur', Radar: 'Capteurs', ShipCockpit: 'Verrière' };
    let actionCourante = null;       // réponse de la simulation aux boutons de l'interface

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
        actionCourante = nom => {
            if (nom !== 'rapport_avarie') return;               // les autres boutons n'ont rien à simuler
            const r = rapportAvarie();
            note('COVAS', 'vaisseau', r.texte, r.gravite);
            recevoir({ type: 'rapport_avarie', rapport: r });
        };

        function scenario() {
            const [type, modele, nom, immat] = VITRINE[rang % VITRINE.length];
            status = { flags: D.vaisseau | D.boucliers | D.supercroisiere, flags2: 0, pips: [4, 4, 4], groupe_tir: 0, carburant: 24.3, reserve: 0.41, soute: 14, statut_legal: 'Clean', credits: 148230511, destination: 'Alpha Centauri' };
            etat = {
                session: { jeu_actif: true },
                commandant: { nom: 'Démo', credits: 148230511, mode_jeu: 'Solo', rangs: { Combat: 6, Trade: 5, Explore: 4, Exobiologist: 2, Federation: 4, Empire: 3 }, progression: { Combat: 41, Trade: 77, Explore: 12, Exobiologist: 5, Federation: 60, Empire: 30 } },
                vaisseau: { type, modele, nom, immat, coque: 1, boucliers: true, portee_saut: 31.42, soute_max: 32, carburant_max: 32, reserve_max: 0.63, rachat: 6234110, verriere_brisee: false, chasseur: null },
                position: { systeme: 'Sol', corps: 'Mars', allegeance: 'Federation', economie: 'Raffinerie', gouvernement: 'Démocratie', securite: 'Sécurité haute', population: 22780919531, faction: 'Mother Gaia', amarre: false, station: null, corps_total: 40, corps_scannes: 12 },
                status,
                route: { etapes: etapes(), distance_totale: 43.1, indice_actuel: 0, prochain: { systeme: 'Alpha Centauri', classe: 'G', ravitaillable: true, sauts_restants: 7 } },
                modules: { liste: MODULES(), releve: new Date().toISOString() },
                soute: { total: 14, inventaire: [{ nom: 'Or', quantite: 8, vole: false }, { nom: 'Painite', quantite: 4, vole: false }, { nom: 'Générateurs', quantite: 2, vole: true }] },
                cible: { verrouillee: false },
                combat: { eliminations: 0, primes: 0, bons: 0, coups_coque: 0, boucliers_tombes: 0, interdictions: 0, morts: 0 },
                missions: { liste: [{ id: 1, nom: 'Livrer 8 unités d\'or', systeme: 'Sirius', station: 'Patterson Enterprise' }], anterieures: 2 },
                proches: { etat: 'ok', systeme: 'Sol', rayon: 31.42, total: 7, liste: [['Alpha Centauri', 'G', 4.38], ['Barnard\'s Star', 'M', 5.95], ['Luhman 16', 'L', 6.57], ['Wolf 359', 'M', 7.78], ['Lalande 21185', 'M', 8.29], ['Sirius', 'A', 8.59], ['Duamta', 'M', 9.88]].map(([nom, classe, distance]) => ({ nom, classe, distance, ravitaillable: 'KGBFOAM'.includes(classe) })) },
            };
            recevoir({ type: 'etat', etat, historique: [] });
            note('LoadGame', 'systeme', 'Session ouverte — CMDR Démo', 'succes');
            note('ReceiveText', 'comms', 'Contrôle de Mars High : Bon vol, commandant.');

            const etapesScenario = [
                [3, () => { majStatus({ flags: status.flags | D.fsdCharge }); note('StartJump', 'navigation', 'Saut hyperespace vers Alpha Centauri (classe G)'); }],
                [7, () => majStatus({ flags: D.vaisseau | D.boucliers | D.saut })],
                [10, () => {
                    maj('position', { systeme: 'Alpha Centauri', corps: 'Alpha Centauri A', allegeance: 'Federation', economie: 'Industrie', gouvernement: 'Corporation', securite: 'Sécurité moyenne', population: 825000, faction: 'Hutton Truckers', corps_total: 17, corps_scannes: 0 });
                    maj('route', { indice_actuel: 1, prochain: { systeme: 'Wolf 359', classe: 'M', ravitaillable: true, sauts_restants: 6 } });
                    majStatus({ flags: D.vaisseau | D.boucliers | D.supercroisiere | D.fsdRefroid, carburant: 21.9, destination: 'Wolf 359' });
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

        scenario();
        return () => { minuteries.forEach(clearTimeout); actionCourante = null; };
    }

    /** Bouton de l'interface pendant la simulation (aucune touche n'est envoyée). */
    const action = nom => actionCourante?.(nom);

    return { demarrer, action };
})();
