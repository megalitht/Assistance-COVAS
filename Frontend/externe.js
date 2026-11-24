/* =====================================================================
   COVAS — Données externes (Backend/module/externe/)
   - Fiche EDSM du système : résumé dans le panneau Position, détail dans une fenêtre
     (stations et plateformes, corps, valeur estimée comparée à celle du COVAS).
   - Route Spansh (neutron ou galaxy plotter) : fenêtre ouverte depuis le panneau Route ; le
     prochain système se copie pour le coller dans la carte de la galaxie.
   - Profil Inara : une ligne dans le panneau Commandant (seulement avec une clé).
   Aucune requête ne part d'ici : la page demande, le backend interroge (avec ses délais).
   ===================================================================== */
window.COVAS_EXTERNE = (() => {
    'use strict';

    const $ = id => document.getElementById(id);
    let o = null;                  // outils de interface.js (creer, ecrire, creditsCourts...)
    let envoyer = () => false;     // envoie {"demande": ...} au backend
    let dernier = { systeme: {}, route: null, inara: null };
    let explorationCovas = null;   // estimation du COVAS pour le système actuel

    const INDISPONIBLE = 'Données indisponibles';

    /** Copie dans le presse-papiers (aussi en http sur le réseau local, où l'API moderne est refusée). */
    function copier(texte, bouton) {
        const fini = ok => {
            if (!bouton) return;
            const avant = bouton.textContent;
            bouton.textContent = ok ? 'Copié' : 'Échec';
            setTimeout(() => { bouton.textContent = avant; }, 1200);
        };
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(texte).then(() => fini(true), () => fini(false));
            return;
        }
        const zone = document.createElement('textarea');
        zone.value = texte;
        zone.setAttribute('readonly', '');
        zone.style.position = 'fixed';
        zone.style.opacity = '0';
        document.body.append(zone);
        zone.select();
        let ok = false;
        try { ok = document.execCommand('copy'); } catch { ok = false; }
        zone.remove();
        fini(ok);
    }

    // ----------------------------------------------------------------
    //  FICHE DU SYSTÈME (EDSM)
    // ----------------------------------------------------------------
    function resumeSysteme(s) {
        if (!s || s.etat === 'attente') return '—';
        if (s.etat === 'desactive') return 'EDSM désactivé (config.toml [externe]).';
        if (s.etat === 'recherche') return `Recherche de ${s.systeme} sur EDSM…`;
        if (s.etat === 'indisponible') return INDISPONIBLE;
        if (s.etat === 'inconnu') return 'Système inconnu d\'EDSM.';
        const morceaux = [];
        const stations = s.stations;
        if (stations) morceaux.push(stations.length ? `${stations.length} station${stations.length > 1 ? 's' : ''}${stations.some(x => x.plateforme === 'L') ? ' (grandes plateformes)' : stations.length ? ' (moyennes seulement)' : ''}` : 'aucune station');
        if (s.corps) morceaux.push(`${s.corps.total} corps${s.corps.posables ? `, ${s.corps.posables} posables` : ''}`);
        if (s.valeur?.estimation) morceaux.push(`≈ ${o.creditsCourts(s.valeur.estimation)}`);
        return morceaux.join(' · ') || INDISPONIBLE;
    }

    function rendreFiche() {
        const s = dernier.systeme || {};
        o.ecrire('edsm-systeme', s.systeme || '');
        const liste = $('edsm-stations');
        if (!liste) return;
        if (s.etat !== 'ok') {
            o.remplir(liste, [], s.etat === 'recherche' ? 'Recherche…' : resumeSysteme(s));
            o.ecrire('edsm-corps', '');
            o.ecrire('edsm-valeur', '');
            return;
        }
        o.remplir(liste, (s.stations || []).map(st => {
            const li = o.creer('li', 'station-edsm');
            const tete = o.creer('div', 'tete');
            const pad = o.creer('span', 'plateforme', st.plateforme);
            pad.title = { L: 'Grande plateforme', M: 'Plateformes moyennes au plus', '?': 'Taille des plateformes inconnue' }[st.plateforme] || '';
            tete.append(pad, o.creer('span', 'nom', st.nom), o.creer('span', 'discret', st.type || ''),
                o.creer('span', 'valeur', st.distance_ls != null ? `${o.nombre(st.distance_ls)} sl` : ''));
            const services = o.creer('ul', 'pastilles');
            (st.services || []).forEach(x => services.append(o.creer('li', '', x)));
            li.append(tete, services);
            return li;
        }), s.stations ? 'Aucune station.' : INDISPONIBLE);
        const c = s.corps;
        o.ecrire('edsm-corps', c ? `${c.total} corps (${c.connus} connus d'EDSM) · ${c.etoiles} étoile${c.etoiles > 1 ? 's' : ''}, ${c.planetes} planète${c.planetes > 1 ? 's' : ''} · ${c.posables} posable${c.posables > 1 ? 's' : ''} · ${c.terraformables} terraformable${c.terraformables > 1 ? 's' : ''}`
            + (c.notables?.length ? ' · ' + c.notables.map(n => `${n.nom} (${n.type})`).join(', ') : '') : INDISPONIBLE);
        const v = s.valeur;
        let texte = v ? `EDSM : ≈ ${o.creditsCourts(v.estimation)} (≈ ${o.creditsCourts(v.estimation_carto)} cartographié)` : INDISPONIBLE;
        if (v && explorationCovas?.systeme === s.systeme && explorationCovas.total_carto) {
            texte += ` · COVAS : ≈ ${o.creditsCourts(explorationCovas.total_carto)} cartographié, d'après tes scans`;
        }
        o.ecrire('edsm-valeur', texte);
    }

    // ----------------------------------------------------------------
    //  ROUTE SPANSH
    // ----------------------------------------------------------------
    function prochaineEtape(route, systemeActuel) {
        if (!route?.etapes?.length) return null;
        const i = route.etapes.findIndex(e => e.systeme === systemeActuel);
        return route.etapes[i >= 0 ? i + 1 : 1] || null;
    }

    function rendreRoute(systemeActuel) {
        const r = dernier.route;
        const bloc = $('spansh-ligne');
        const prochain = r?.etat === 'ok' ? prochaineEtape(r, systemeActuel) : null;
        if (bloc) {
            bloc.hidden = !prochain;
            if (prochain) o.ecrire('spansh-prochain', prochain.systeme);
        }
        const statut = !r ? 'Aucune route Spansh.'
            : r.etat === 'recherche' ? `Calcul de la route ${r.type === 'neutron' ? 'neutron' : 'galaxie'} vers ${r.arrivee}…`
            : r.etat === 'desactive' ? 'Spansh désactivé (config.toml [externe]).'
            : r.etat === 'erreur' ? (r.message || INDISPONIBLE)
            : `${r.type === 'neutron' ? 'Route neutron' : 'Galaxy plotter'} : ${r.depart} → ${r.arrivee} · ${o.nombre(r.sauts)} saut${r.sauts > 1 ? 's' : ''}${r.distance ? ` · ${o.nombre(r.distance)} al` : ''}${r.portee ? ` · portée ${String(r.portee).replace('.', ',')} al` : ''}`;
        o.ecrire('spansh-statut', statut);
        const liste = $('spansh-etapes');
        if (!liste) return;
        const ici = r?.etapes ? r.etapes.findIndex(e => e.systeme === systemeActuel) : -1;
        o.remplir(liste, (r?.etat === 'ok' ? r.etapes : []).map((e, i) => {
            const li = o.creer('li', i < ici ? 'passe' : i === ici ? 'actuel' : '');
            li.append(o.creer('span', 'nom', e.systeme));
            if (e.neutron) { const m = o.creer('span', 'marque', 'neutron'); m.title = 'Étoile à neutrons : saut surchargé'; li.append(m); }
            if (e.ravitailler) { const m = o.creer('span', 'marque', 'plein'); m.title = 'Faire le plein ici'; li.append(m); }
            else if (e.ravitaillable) { const m = o.creer('span', 'marque', 'écopable'); m.title = 'Étoile récupérable'; li.append(m); }
            if (e.sauts > 1) li.append(o.creer('span', 'discret', `${e.sauts} sauts`));
            li.append(o.creer('span', 'valeur', e.distance ? `${Math.round(e.distance)} al` : ''));
            const bouton = o.creer('button', 'petit', 'Copier');
            bouton.type = 'button';
            bouton.onclick = () => copier(e.systeme, bouton);
            li.append(bouton);
            return li;
        }), r?.etat === 'ok' ? 'Route vide.' : '');
    }

    // ----------------------------------------------------------------
    //  INARA
    // ----------------------------------------------------------------
    function rendreInara() {
        const p = dernier.inara;
        const ligne = $('ligne-inara');
        if (!ligne) return;
        ligne.hidden = !p;
        if (!p) return;
        if (p.etat !== 'ok') { o.ecrire('inara-resume', `Inara : ${p.message || INDISPONIBLE}`); return; }
        o.ecrire('inara-resume', ['Inara', p.commandant, p.escadron && `escadron ${p.escadron}`, p.allegeance, p.puissance].filter(Boolean).join(' · '));
        const lien = $('inara-lien');
        if (lien) { lien.hidden = !p.lien; if (p.lien) lien.href = p.lien; }
    }

    // ----------------------------------------------------------------
    //  ENTRÉES
    // ----------------------------------------------------------------
    function rendre(etat, systemeActuel, exploration) {
        dernier = etat || dernier;
        explorationCovas = exploration || explorationCovas;
        o.ecrire('edsm-resume', resumeSysteme(dernier.systeme));
        rendreFiche();
        rendreRoute(systemeActuel);
        rendreInara();
    }

    function installer(outils) {
        o = outils;
        envoyer = outils.envoyerDemande;
        const fiche = $('fenetre-systeme'), route = $('fenetre-spansh');
        $('bouton-fiche-systeme')?.addEventListener('click', () => { rendreFiche(); fiche.showModal(); });
        $('systeme-fermer')?.addEventListener('click', () => fiche.close());
        $('systeme-actualiser')?.addEventListener('click', () => envoyer({ type: 'edsm' }));
        $('bouton-spansh')?.addEventListener('click', () => route.showModal());
        $('spansh-fermer')?.addEventListener('click', () => route.close());
        $('spansh-effacer')?.addEventListener('click', () => envoyer({ type: 'spansh_effacer' }));
        $('spansh-copier')?.addEventListener('click', evenement => copier(o.lire('spansh-prochain'), evenement.currentTarget));
        $('inara-actualiser')?.addEventListener('click', () => envoyer({ type: 'inara' }));
        const genre = $('spansh-type'), efficacite = $('spansh-efficacite-bloc');
        genre?.addEventListener('change', () => { efficacite.hidden = genre.value !== 'neutron'; });
        $('form-spansh')?.addEventListener('submit', evenement => {
            evenement.preventDefault();
            const destination = $('spansh-destination').value.trim();
            if (!destination) return;
            envoyer({ type: 'spansh', route: genre.value, destination, efficacite: Number($('spansh-efficacite').value) || 60 });
        });
    }

    return { installer, rendre, copier };
})();
