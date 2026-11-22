/* =====================================================================
   COVAS — Studio vocal : page de la fenêtre Backend/studio_vocal.py.
   Tout le travail (micro, transformation, rangement) est côté Python, appelé par
   window.pywebview.api.<nom>() ; la page affiche et envoie les ordres.
   ===================================================================== */
"use strict";

const $ = (selecteur) => document.querySelector(selecteur);
const ESSAI = null;                       // « réplique » de l'essai libre (rien n'est rangé)
const NOMS_PROFILS = {
    fidele: "Fidèle (comme les enregistrements)",
    monocorde: "Monocorde",
    metal: "Métal",
    vocodeur: "Vocodeur",
    vocodeur_chantant: "Vocodeur chantant",
};

const etat = {
    infos: null,            // api.etat() : réglages, curseurs, micros, étalonnage...
    lignes: [],             // toutes les répliques
    selection: ESSAI,
    prise: null,            // résumé de la dernière prise affichée
    gardee: null,           // numéro de la prise déjà gardée
    confirmer: null,        // réplique dont on attend la confirmation (remplacer un original)
    enregistre: "non",      // "non" | "oui" | "traitement"
    lecture: null,          // {quoi, debut, duree}
    verification: null,     // numéro de la prise que Whisper écoute
    creteAffichee: -60,
};
let api = null;

// ---------------------------------------------------------------- outils
const pause = (ms) => new Promise((r) => setTimeout(r, ms));
const nombre = (x, decimales = 1) => Number(x).toFixed(decimales).replace(".", ",");
const normaliser = (s) => (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
const ligneParId = (id) => (id === ESSAI ? null : etat.lignes.find((l) => l.id === id) || null);

function message(texte, genre = "") {
    const m = $("#message");
    m.textContent = texte;
    m.className = genre;
}

async function appeler(nom, ...args) {
    try {
        const r = await api[nom](...args);
        if (r && r.erreur) message(r.erreur, "erreur");
        return r;
    } catch (erreur) {
        message(`Erreur (${nom}) : ${erreur.message || erreur}`, "erreur");
        return { erreur: String(erreur) };
    }
}

function element(balise, classe, texte) {
    const e = document.createElement(balise);
    if (classe) e.className = classe;
    if (texte !== undefined) e.textContent = texte;
    return e;
}

// ---------------------------------------------------------------- démarrage
window.addEventListener("pywebviewready", demarrer);
setTimeout(() => {
    if (!api) message("Cette page s'ouvre avec « STUDIO VOCAL.bat » (la fenêtre du studio).", "erreur");
}, 2500);

async function demarrer() {
    if (api) return;
    api = window.pywebview.api;
    const infos = await appeler("demarrer");
    if (!infos || infos.erreur) return;
    etat.infos = infos;
    construireReglages(infos);
    remplirMicros(infos);
    remplirSources(infos);
    afficherReglages(infos.reglages);
    majEtalonnage(infos.etalonnage);
    compteurs(infos.compteurs);
    message("Chargement des répliques…");
    etat.lignes = (await appeler("repliques")) || [];
    afficherListe();
    choisir(infos.reglages.etalonnage ? premiereAFaire() : ESSAI);
    if (infos.micro.ouvert) {
        message(infos.reglages.etalonnage
            ? "Prêt. Espace pour enregistrer la réplique, Entrée pour la garder."
            : "Prêt. Commence par quelques essais libres (Espace), puis étalonne ta voix à droite.");
    } else {
        message(`Micro inaccessible : ${infos.micro.erreur || "aucun micro"}. Choisis-en un en haut à droite.`, "erreur");
    }
    boucleNiveau();
}

function premiereAFaire() {
    const visibles = lignesVisibles();
    const l = visibles.find((v) => v.etat !== "studio") || visibles[0];
    return l ? l.id : ESSAI;
}

// ---------------------------------------------------------------- liste des répliques
function remplirSources(infos) {
    const choix = $("#filtre-source");
    for (const [cle, nom] of Object.entries(infos.sources)) {
        const o = element("option", "", nom);
        o.value = cle;
        choix.append(o);
    }
    for (const id of ["#filtre-source", "#filtre-etat"]) {
        $(id).addEventListener("change", () => { afficherListe(); $(id).blur(); });
    }
    $("#recherche").addEventListener("input", afficherListe);
}

function lignesVisibles() {
    const recherche = normaliser($("#recherche").value.trim());
    const source = $("#filtre-source").value;
    const filtre = $("#filtre-etat").value;
    return etat.lignes.filter((l) =>
        (!source || l.source === source)
        && (!filtre || (filtre === "afaire" ? l.etat !== "studio" : l.etat === filtre))
        && (!recherche || normaliser(`${l.texte} ${l.contexte} ${l.groupe} ${l.id}`).includes(recherche)));
}

function boutonLigne(id, texte, detail, etatFichier) {
    const b = element("button");
    b.type = "button";
    b.dataset.id = id === ESSAI ? "" : id;
    const pastille = element("span", "pastille");
    pastille.dataset.etat = etatFichier;
    b.append(pastille, element("span", "texte", texte), element("small", "", detail));
    b.addEventListener("click", () => choisir(id));
    const li = element("li");
    li.append(b);
    return li;
}

function afficherListe() {
    const liste = $("#lignes");
    liste.replaceChildren(boutonLigne(ESSAI, "Essai libre", "pour régler ta voix — rien n'est rangé", "essai"));
    const visibles = lignesVisibles();
    let groupe = null;
    for (const l of visibles) {
        const titre = l.source === "conversations" ? `Conversations · ${l.groupe}` : l.groupe;
        if (titre !== groupe) {
            groupe = titre;
            liste.append(element("li", "groupe", titre));
        }
        const detail = `${etat.infos.etats[l.etat]} · ${l.contexte}`;
        liste.append(boutonLigne(l.id, l.texte, detail, l.etat));
    }
    if (!visibles.length) liste.append(element("li", "vide", "Aucune réplique ne correspond."));
    marquerSelection(false);
    avancement();
}

function marquerSelection(defiler = true) {
    const cle = etat.selection === ESSAI ? "" : etat.selection;
    let courant = null;
    for (const b of document.querySelectorAll("#lignes button")) {
        const oui = b.dataset.id === cle;
        b.setAttribute("aria-current", oui ? "true" : "false");
        if (oui) courant = b;
    }
    if (courant && defiler) courant.scrollIntoView({ block: "nearest" });
}

function avancement() {
    const total = etat.lignes.length;
    const faites = etat.lignes.filter((l) => l.etat === "studio").length;
    $("#avancement-barre").style.width = total ? `${(faites / total) * 100}%` : "0";
    $("#avancement-texte").textContent = `Ta voix : ${faites} / ${total} répliques`;
}

function choisir(id, defiler = true) {
    if (etat.enregistre !== "non") return;           // pas pendant une prise
    etat.selection = id;
    etat.confirmer = null;
    const l = ligneParId(id);
    const source = l ? etat.infos.sources[l.source] : "";
    $("#groupe").textContent = !l ? "Essai libre" : l.groupe === source ? source : `${source} › ${l.groupe}`;
    $("#contexte").textContent = l ? l.contexte : "";
    $("#phrase").textContent = l ? l.texte : "Dis ce que tu veux pour entendre ta voix de COVAS.";
    $("#note").hidden = !(l && l.note);
    $("#note").textContent = (l && l.note) || "";
    $("#pastille").dataset.etat = l ? l.etat : "essai";
    $("#etat-texte").textContent = l ? etat.infos.etats[l.etat] : "rien n'est rangé";
    $("#fichier").textContent = l ? l.id.replace(/^data\/son\//, "") : "";
    $("#actuelle").disabled = !l || l.etat === "manquante";
    if (etat.prise && etat.prise.ligne !== id) effacerPrise();
    majGarder();
    marquerSelection(defiler);
}

function deplacer(sens) {
    const ids = [ESSAI, ...lignesVisibles().map((l) => l.id)];
    const i = Math.max(0, ids.indexOf(etat.selection));
    choisir(ids[Math.max(0, Math.min(ids.length - 1, i + sens))]);
}

// ---------------------------------------------------------------- prise
function regleEnregistre(valeur) {
    etat.enregistre = valeur;
    document.body.dataset.enregistre = valeur;
    $("#enregistrer-texte").textContent = valeur === "oui" ? "Arrêter" : valeur === "traitement" ? "Transformation…" : "Enregistrer";
    $("#enregistrer").disabled = valeur === "traitement";
}

async function basculerEnregistrement() {
    if (!api || etat.enregistre === "traitement") return;
    if (etat.enregistre === "non") {
        arreterLecture(false);
        const r = await appeler("enregistrer", etat.selection);
        if (!r || r.erreur) return;
        regleEnregistre("oui");
        $("#chrono").textContent = "0,0 s";
        message("Enregistrement… parle, puis Espace pour arrêter (Échap pour annuler).");
        return;
    }
    regleEnregistre("traitement");
    message("Transformation de ta voix…");
    const r = await appeler("arreter");
    regleEnregistre("non");
    if (!r || r.erreur) return;
    afficherPrise(r.prise);
    majEtalonnage(r.etalonnage);
    if (r.lecture && !r.lecture.erreur) demarrerLecture(r.lecture);
    if (r.prise.parole > 0) {
        const l = ligneParId(r.prise.ligne);
        message(l ? "Écoute. Entrée pour garder, Espace pour refaire." : "Écoute (V : COVAS, B : ta voix). Règle la voix à droite si besoin.");
        suivreVerification(r.prise.numero);
    } else {
        message("Rien entendu.", "erreur");
    }
}

async function annulerPrise() {
    await appeler("annuler");
    regleEnregistre("non");
    message("Prise annulée.");
}

function afficherPrise(p) {
    etat.prise = p;
    etat.gardee = null;
    dessiner("#onde-brut", p.forme_brut, p.zone, false);
    dessiner("#onde-covas", p.forme_covas, null, true);
    $("#infos-brut").textContent = `${nombre(p.duree_brut)} s enregistrées · parole ${nombre(p.parole)} s`;
    $("#infos-covas").textContent = p.parole > 0 ? `${nombre(p.duree_covas)} s` : "—";
    document.querySelector('[data-ecouter="covas"]').disabled = !(p.parole > 0);
    document.querySelector('[data-ecouter="brut"]').disabled = !(p.duree_brut > 0);
    const mesures = $("#mesures");
    mesures.replaceChildren();
    const ajouter = (nom, valeur) => {
        const li = element("li");
        li.append(element("span", "", nom), element("b", "", valeur));
        mesures.append(li);
    };
    if (p.parole > 0) {
        ajouter("Hauteur", !p.hauteur ? "—" : p.hauteur_visee ? `${p.hauteur} Hz → ${p.hauteur_visee} Hz` : `${p.hauteur} Hz`);
        ajouter("Voix", `${nombre(p.niveau_db, 0)} dB`);
        ajouter("Crête", `${nombre(p.crete_db, 0)} dB`);
        ajouter("Fond", `${nombre(p.bruit_db, 0)} dB`);
    }
    $("#conseils").replaceChildren(...p.conseils.map((c) => element("li", "", c)));
    $("#whisper").hidden = true;
    majGarder();
}

function effacerPrise() {
    etat.prise = null;
    etat.gardee = null;
    etat.verification = null;
    dessiner("#onde-brut", [], null, false);
    dessiner("#onde-covas", [], null, true);
    $("#infos-brut").textContent = "telle que le micro l'entend";
    $("#infos-covas").textContent = "après transformation";
    for (const b of document.querySelectorAll("[data-ecouter]")) b.disabled = true;
    $("#mesures").replaceChildren();
    $("#conseils").replaceChildren();
    $("#whisper").hidden = true;
}

function majGarder() {
    const bouton = $("#garder");
    const l = ligneParId(etat.selection);
    const prete = !!(l && etat.prise && etat.prise.ligne === l.id && etat.prise.parole > 0);
    const gardee = prete && etat.gardee === etat.prise.numero;
    const confirmer = prete && etat.confirmer === l.id;
    bouton.disabled = !prete;
    bouton.classList.toggle("confirmer", confirmer);
    bouton.classList.toggle("garde", gardee);
    bouton.firstChild.textContent = confirmer ? "Remplacer l'enregistrement d'origine ? "
        : gardee ? "Gardée ✓ — suivante " : "✓ Garder ";
}

async function garder() {
    const l = ligneParId(etat.selection);
    const p = etat.prise;
    if (!l || !p || p.ligne !== l.id || !(p.parole > 0)) return;
    if (etat.gardee === p.numero) { deplacer(1); return; }
    if (l.etat === "origine" && etat.confirmer !== l.id) {
        etat.confirmer = l.id;
        majGarder();
        message("Cette réplique a un enregistrement d'origine : Entrée une 2e fois pour le remplacer (il sera mis de côté, pas effacé).");
        return;
    }
    const suivante = (() => {
        const visibles = lignesVisibles();
        const i = visibles.findIndex((v) => v.id === l.id);
        if (i < 0) return undefined;
        const apres = visibles.slice(i + 1);         // on saute celles qui sont déjà ta voix
        const prochaine = apres.find((v) => v.etat !== "studio") || apres[0];
        return prochaine ? prochaine.id : undefined;
    })();
    const r = await appeler("garder", l.id);
    if (!r || r.erreur) return;
    Object.assign(l, { etat: r.ligne.etat, date: r.ligne.date });
    etat.gardee = p.numero;
    etat.confirmer = null;
    compteurs(r.compteurs);
    majEtalonnage(r.etalonnage);
    message(r.ligne.remplace ? `Gardée ✓ — l'ancien fichier est rangé dans ${r.ligne.remplace}.`
        : "Gardée ✓ — le COVAS la jouera désormais.", "bien");
    afficherListe();
    if (suivante !== undefined) choisir(suivante);
    else choisir(l.id);
}

// ---------------------------------------------------------------- vérification par Whisper
async function suivreVerification(numero) {
    etat.verification = numero;
    const zone = $("#whisper");
    if (!etat.infos.reglages.verifier) { zone.hidden = true; return; }
    for (let i = 0; i < 600; i++) {
        if (etat.verification !== numero) return;
        const v = await appeler("verification");
        if (etat.verification !== numero) return;
        if (!v || v.erreur || v.etat === "aucune") { zone.hidden = true; return; }
        if (v.numero === numero || v.numero === undefined) {
            zone.hidden = false;
            zone.className = "whisper";
            if (v.etat === "chargement") zone.textContent = "Whisper se prépare (première écoute : quelques secondes)…";
            else if (v.etat === "en_cours") zone.textContent = "Whisper écoute…";
            else if (v.etat === "erreur") { zone.textContent = `Whisper indisponible : ${v.message}`; return; }
            else if (v.etat === "fini") { afficherVerdict(v); return; }
        }
        await pause(300);
    }
}

function afficherVerdict(v) {
    const zone = $("#whisper");
    zone.replaceChildren();
    if (v.score === null || v.score === undefined) {
        zone.append("Whisper entend : ", element("q", "", v.entendu || "(rien)"));
        return;
    }
    const pc = Math.round(v.score * 100);
    zone.className = `whisper ${pc >= 85 ? "bien" : pc >= 70 ? "moyen" : "mal"}`;
    zone.append("Whisper comprend à ", element("b", "", `${pc} %`), " : ", element("q", "", v.entendu || "(rien)"));
    if (pc < 85) zone.append(" — articule un peu plus, ou baisse « Métal » / « Vocodeur ».");
}

// ---------------------------------------------------------------- écoute
async function ecouter(quoi) {
    if (etat.enregistre !== "non") return;
    if (quoi !== "actuelle" && !etat.prise) return;
    const r = await appeler("ecouter", quoi, quoi === "actuelle" ? etat.selection : null);
    if (r && !r.erreur) demarrerLecture(r);
}

function demarrerLecture(r) {
    arreterLecture(false);
    etat.lecture = { quoi: r.quoi, debut: performance.now(), duree: r.duree * 1000 };
    const bouton = r.quoi === "actuelle" ? $("#actuelle") : document.querySelector(`[data-ecouter="${r.quoi}"]`);
    if (bouton) bouton.classList.add("joue");
    requestAnimationFrame(animerLecture);
}

function animerLecture() {
    const l = etat.lecture;
    if (!l) return;
    const avance = (performance.now() - l.debut) / l.duree;
    if (avance >= 1) { arreterLecture(false); return; }
    const piste = l.quoi === "brut" ? "#piste-brut" : l.quoi === "covas" ? "#piste-covas" : null;
    if (piste) {
        const onde = $(`${piste} .onde`);
        onde.classList.add("lecture");
        onde.querySelector(".tete").style.left = `${avance * 100}%`;
    }
    requestAnimationFrame(animerLecture);
}

function arreterLecture(couper = true) {
    if (couper && api) appeler("silence");
    etat.lecture = null;
    for (const e of document.querySelectorAll(".onde.lecture")) e.classList.remove("lecture");
    for (const e of document.querySelectorAll(".joue")) e.classList.remove("joue");
}

// ---------------------------------------------------------------- dessin des ondes
function dessiner(selecteur, paires, zone, normaliserHauteur) {
    const toile = $(selecteur);
    const rect = toile.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    toile.width = Math.max(1, Math.round(rect.width * dpr));
    toile.height = Math.max(1, Math.round(rect.height * dpr));
    toile._donnees = { paires, zone, normaliserHauteur };
    const g = toile.getContext("2d");
    const w = toile.width;
    const h = toile.height;
    const style = getComputedStyle(document.documentElement);
    g.clearRect(0, 0, w, h);
    if (zone) {
        g.fillStyle = "rgba(255, 122, 20, 0.08)";
        g.fillRect(zone[0] * w, 0, (zone[1] - zone[0]) * w, h);
    }
    g.fillStyle = "rgba(255, 122, 20, 0.25)";
    g.fillRect(0, Math.floor(h / 2), w, Math.max(1, dpr));
    if (!paires || !paires.length) return;
    const crete = normaliserHauteur
        ? Math.max(0.01, ...paires.map((p) => Math.max(-p[0], p[1])))
        : 1;
    const milieu = h / 2;
    const largeur = Math.max(1, w / paires.length - 0.4 * dpr);
    g.fillStyle = (normaliserHauteur ? style.getPropertyValue("--orange") : style.getPropertyValue("--ambre")).trim() || "#ff7a14";
    paires.forEach((p, i) => {
        const haut = milieu - (Math.min(1, p[1] / crete)) * milieu * 0.94;
        const bas = milieu - (Math.max(-1, p[0] / crete)) * milieu * 0.94;
        g.fillRect((i / paires.length) * w, haut, largeur, Math.max(dpr, bas - haut));
    });
    if (!normaliserHauteur) {                      // saturation : traits rouges en haut et en bas
        g.fillStyle = "#ff3a1c";
        paires.forEach((p, i) => {
            if (p[1] > 0.98 || p[0] < -0.98) g.fillRect((i / paires.length) * w, 0, largeur, 3 * dpr);
        });
    }
}

window.addEventListener("resize", () => {
    for (const id of ["#onde-brut", "#onde-covas"]) {
        const d = $(id)._donnees;
        if (d) dessiner(id, d.paires, d.zone, d.normaliserHauteur);
    }
});

// ---------------------------------------------------------------- micro et vumètre
function remplirMicros(infos) {
    const choix = $("#micro");
    choix.replaceChildren();
    const defaut = element("option", "", "Micro de Windows (par défaut)");
    defaut.value = "";
    choix.append(defaut);
    for (const nom of infos.micros) {
        const o = element("option", "", nom);
        o.value = nom;
        choix.append(o);
    }
    choix.value = infos.reglages.micro || "";
    choix.onchange = async () => {
        choix.blur();
        const r = await appeler("regler", { micro: choix.value || null });
        if (r && !r.erreur) message(`Micro : ${choix.value || "celui de Windows"}.`);
    };
}

let niveauEnCours = false;
function boucleNiveau() {
    setInterval(async () => {
        if (niveauEnCours || !api) return;
        niveauEnCours = true;
        try {
            const n = await api.niveau();
            vumetre(n);
            if (etat.enregistre === "oui") {
                $("#chrono").textContent = `${nombre(n.duree)} s`;
                if (n.plein) {
                    message("30 secondes : la prise s'arrête d'elle-même.");
                    basculerEnregistrement();
                }
            }
        } catch {
            /* la fenêtre se ferme */
        } finally {
            niveauEnCours = false;
        }
    }, 70);
}

function vumetre(n) {
    const echelle = (db) => Math.max(0, Math.min(100, ((db + 60) / 60) * 100));
    $(".vu-niveau").style.width = `${echelle(n.niveau)}%`;
    etat.creteAffichee = Math.max(n.crete, etat.creteAffichee - 1.2);
    $(".vu-crete").style.left = `${echelle(etat.creteAffichee)}%`;
    $("#vumetre").classList.toggle("sature", n.crete > -1);
}

// ---------------------------------------------------------------- réglages
function construireReglages(infos) {
    const profil = $("#profil");
    for (const nom of infos.profils) {
        const o = element("option", "", NOMS_PROFILS[nom] || nom);
        o.value = nom;
        profil.append(o);
    }
    profil.addEventListener("change", () => { profil.blur(); regler({ profil: profil.value }); });

    const zone = $("#curseurs");
    for (const r of [...infos.reglables, infos.debruitage]) {
        const ligne = element("label", "curseur");
        ligne.title = r.aide;
        const curseur = element("input");
        Object.assign(curseur, { type: "range", min: r.min, max: r.max, step: r.pas });
        curseur.dataset.cle = r.cle;
        const sortie = element("output");
        const afficher = () => {
            const v = Number(curseur.value);
            if (r.unite === "demi-tons") sortie.textContent = `${v > 0 ? "+" : v < 0 ? "−" : ""}${nombre(Math.abs(v), 1)} dt`;
            else sortie.textContent = r.unite ? `${Math.round(v)} ${r.unite}` : nombre(v, r.pas < 1 ? 2 : 0);
        };
        curseur._afficher = afficher;
        curseur.addEventListener("input", afficher);
        curseur.addEventListener("change", () => { curseur.blur(); regler({ [r.cle]: Number(curseur.value) }); });
        ligne.append(element("span", "", r.nom), curseur, sortie);
        zone.append(ligne);
    }
    for (const cle of ["ecoute_auto", "verifier"]) {
        $(`#${cle}`).addEventListener("change", (e) => { e.target.blur(); regler({ [cle]: e.target.checked }); });
    }
    $("#reinitialiser").addEventListener("click", async () => apresReglage(await appeler("reinitialiser")));
    $("#etalonner").addEventListener("click", etalonner);
    $("#oublier").addEventListener("click", async () => {
        const r = await appeler("oublier_etalonnage");
        if (r && !r.erreur) { apresReglage(r); message("Étalonnage oublié : timbre provisoire."); }
    });
    $("#appliquer").addEventListener("click", appliquerATous);
    for (const b of document.querySelectorAll("[data-ecouter]")) {
        b.addEventListener("click", () => ecouter(b.dataset.ecouter));
    }
    $("#actuelle").addEventListener("click", () => ecouter("actuelle"));
    $("#enregistrer").addEventListener("click", basculerEnregistrement);
    $("#garder").addEventListener("click", garder);
    $("#suivante").addEventListener("click", () => deplacer(1));
}

function afficherReglages(reglages) {
    $("#profil").value = reglages.profil;
    for (const curseur of document.querySelectorAll("#curseurs input")) {
        const cle = curseur.dataset.cle;
        curseur.value = cle === "debruitage" ? reglages.debruitage : reglages.valeurs[cle];
        curseur._afficher();
    }
    $("#ecoute_auto").checked = reglages.ecoute_auto;
    $("#verifier").checked = reglages.verifier;
}

async function regler(changements) {
    const r = await appeler("regler", changements);
    if (r && !r.erreur) apresReglage(r);
}

function apresReglage(r) {
    if (!r || r.erreur) return;
    etat.infos.reglages = r.reglages;
    afficherReglages(r.reglages);
    compteurs(r.compteurs);
    majEtalonnage(r.etalonnage);
    if (r.prise && r.prise.ligne === etat.selection) {        // la prise de la réplique affichée
        afficherPrise(r.prise);
        suivreVerification(r.prise.numero);
    }
    if (r.lecture && !r.lecture.erreur) demarrerLecture(r.lecture);
}

function majEtalonnage(e) {
    if (!e) return;
    etat.infos.etalonnage = e;
    const fait = e.fait;
    const bouton = $("#etalonner");
    const part = Math.min(1, e.disponible / e.conseille);
    $("#etalonnage-jauge i").style.width = `${part * 100}%`;
    $("#etalonnage-jauge").classList.toggle("pleine", part >= 1);
    if (fait) {
        const date = new Date(fait.date).toLocaleDateString("fr-FR", { day: "numeric", month: "long" });
        $("#etalonnage-texte").textContent = `Étalonné le ${date} sur ${nombre(fait.secondes)} s de ta voix `
            + `(${fait.prises} prises, ta hauteur : ${fait.hauteur_hz ? Math.round(fait.hauteur_hz) : "?"} Hz). `
            + `Voix disponible maintenant : ${nombre(e.disponible)} s.`;
        bouton.textContent = "Refaire l'étalonnage";
    } else {
        $("#etalonnage-texte").textContent = "Timbre provisoire : pas encore étalonné sur ta voix. Fais quelques prises "
            + `(essai libre ou répliques), puis étalonne. Voix disponible : ${nombre(e.disponible)} s `
            + `sur ${nombre(e.conseille, 0)} s conseillées.`;
        bouton.textContent = "Étalonner";
    }
    bouton.disabled = e.disponible < e.minimum;
    bouton.title = bouton.disabled ? `Il faut au moins ${nombre(e.minimum, 0)} s de ta voix.` : "";
    $("#oublier").hidden = !fait;
}

async function etalonner() {
    message("Étalonnage sur ta voix…");
    const r = await appeler("etalonner");
    if (!r || r.erreur) return;
    apresReglage(r);
    message("Étalonné : la voix du COVAS suit maintenant ton timbre. Les répliques déjà gardées gardent l'ancien "
        + "réglage tant que tu ne les refais pas (à droite).", "bien");
}

function compteurs(c) {
    if (!c) return;
    $("#gardees").textContent = c.gardees
        ? `${c.gardees} réplique${c.gardees > 1 ? "s" : ""} dite${c.gardees > 1 ? "s" : ""} avec ta voix`
          + (c.anciennes ? ` — ${c.anciennes} avec d'anciens réglages.` : ", toutes à jour.")
        : "Aucune pour l'instant.";
    $("#appliquer").disabled = !c.gardees;
}

async function appliquerATous() {
    const r = await appeler("appliquer_a_toutes");
    if (!r || r.erreur) return;
    const zone = $("#travail");
    zone.hidden = false;
    $("#appliquer").disabled = true;
    for (;;) {
        const t = await appeler("travail");
        if (!t || t.erreur) break;
        zone.textContent = `${t.fait} / ${t.total} répliques refaites…`;
        if (!t.en_cours) {
            zone.textContent = t.message;
            compteurs(t.compteurs);
            message(t.message, t.message.includes("erreur") ? "erreur" : "bien");
            break;
        }
        await pause(400);
    }
}

// ---------------------------------------------------------------- clavier
document.addEventListener("click", (e) => {
    const bouton = e.target.closest("button");
    if (bouton && e.detail > 0) bouton.blur();          // clic souris : Espace reste au studio
});

document.addEventListener("keydown", (e) => {
    if (!api) return;
    if (e.key === "Escape") {
        if (etat.enregistre === "oui") annulerPrise();
        else arreterLecture();
        if (document.activeElement && document.activeElement !== document.body) document.activeElement.blur();
        return;
    }
    const cible = e.target;
    if (cible.closest && cible.closest("input, select, textarea")) return;   // on tape une recherche...
    if (cible.closest && cible.closest("button") && (e.key === " " || e.key === "Enter")) return;
    if (e.repeat || e.ctrlKey || e.altKey || e.metaKey) return;
    const actions = {
        " ": basculerEnregistrement,
        Enter: garder,
        ArrowDown: () => deplacer(1),
        ArrowUp: () => deplacer(-1),
        v: () => ecouter("covas"),
        b: () => ecouter("brut"),
        a: () => ecouter("actuelle"),
    };
    const action = actions[e.key.length === 1 ? e.key.toLowerCase() : e.key];
    if (action) {
        e.preventDefault();
        action();
    }
});
