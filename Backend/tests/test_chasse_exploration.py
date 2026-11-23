"""Chasse aux primes, valeur des corps, exobiologie, chasseur et Nomad.
Sans touche, sans micro, sans réseau et sans macros.py : le journal est simulé."""
import importlib.util
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import module  # noqa: E402
from module import chasse, exploration, morceaux  # noqa: E402

DOSSIER_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_DATA = os.path.join(DOSSIER_BACKEND, "data")


def _lecteur_prive():
    """Copie du lecteur de journal propre à ce fichier : test_sens.py remplace le module partagé
    par un faux, et une version déjà importée prendrait sa place."""
    avant = set(sys.modules)
    chemin = os.path.join(DOSSIER_BACKEND, "module", "lecteur_logs.py")
    spec = importlib.util.spec_from_file_location("covas_lecteur_logs_test", chemin)
    copie = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copie)
    for nom in ("module.serveur_ws", "module.edsm"):
        if nom in sys.modules and nom not in avant:
            del sys.modules[nom]
            delattr(module, nom.split(".")[1])
    return copie


logs = _lecteur_prive()


def cible(statut, prime=None, pilote="$npc_name_decorate:#name=Rex;", rang="Expert", stage=3, **autres):
    e = {"event": "ShipTargeted", "TargetLocked": True, "Ship": "python", "ScanStage": stage,
         "PilotName": pilote, "PilotRank": rang, "LegalStatus": statut, **autres}
    if prime is not None:
        e["Bounty"] = prime
    return e


class Verdict(unittest.TestCase):
    def code(self, *a, **k):
        return chasse.verdict(cible(*a, **k))["code"]

    def test_statuts(self):
        self.assertEqual(self.code("Wanted", 1000), "recherche")
        self.assertEqual(self.code("Clean"), "clean")
        self.assertEqual(self.code("Lawless"), "sans_loi")
        self.assertEqual(self.code("Warrant", 500), "mandat")
        self.assertEqual(self.code("Enemy"), "ennemi")

    def test_none_avec_prime_est_recherche(self):
        # Vu dans les journaux : 20 cibles « None » avec prime, toutes payées à la destruction
        self.assertEqual(self.code("None", 373686), "recherche")
        self.assertEqual(self.code("None"), "sans_loi")

    def test_autorites_et_equipage_passent_avant_le_statut(self):
        self.assertEqual(self.code("Clean", pilote="$ShipName_Police_Independent;"), "autorite")
        self.assertEqual(self.code("Lawless", pilote="$RolePanel2_unmanned; $cmdr_decorate:#name=X;"), "allie")

    def test_scan_incomplet(self):
        fiche = chasse.verdict(cible("Wanted", 1000, stage=2))
        self.assertEqual((fiche["code"], fiche["tirer"], fiche["prime"]), ("inconnu", None, 0))

    def test_ne_jamais_conseiller_de_tirer_sur_un_clean(self):
        self.assertIs(chasse.verdict(cible("Clean"))["tirer"], False)
        self.assertIs(chasse.verdict(cible("Clean", pilote="$ShipName_Police_Federation;"))["tirer"], False)

    def test_repliques(self):
        gros = chasse.verdict(cible("Wanted", chasse.SEUIL_GROS_GIBIER))
        self.assertEqual(chasse.repliques_cible(gros), ["chasse_recherchee", "chasse_gros_gibier"])
        joueur = chasse.verdict(cible("Clean", pilote="$cmdr_decorate:#name=Autre;"))
        self.assertEqual(chasse.repliques_cible(joueur), ["chasse_clean", "chasse_joueur"])
        dangereux = chasse.verdict(cible("Wanted", 1000, rang="Elite"))
        self.assertEqual(chasse.repliques_cible(dangereux), ["chasse_recherchee", "chasse_dangereux"])
        clean_elite = chasse.verdict(cible("Clean", rang="Elite"))
        self.assertEqual(chasse.repliques_cible(clean_elite), ["chasse_clean"])

    def test_chaque_replique_existe(self):
        with open(os.path.join(DOSSIER_DATA, "barks.json"), encoding="utf-8") as f:
            barks = json.load(f)
        for cle in logs.DELAIS_REPLIQUES:
            self.assertTrue(barks[cle]["reponses"], cle)
            self.assertEqual(barks[cle]["mots_cles"], [], cle)     # jamais prises pour une commande


class Profil(unittest.TestCase):
    def test_armes_de_combat_seulement(self):
        modules = [{"emplacement": "LargeHardpoint1", "objet": "hpt_beamlaser_gimbal_large"},
                   {"emplacement": "MediumHardpoint1", "objet": "hpt_multicannon_gimbal_medium"},
                   {"emplacement": "SmallHardpoint1", "objet": "hpt_mininglaser_fixed_small"},
                   {"emplacement": "TinyHardpoint1", "objet": "hpt_crimescanner_size0_class5"}]
        self.assertEqual(chasse.profil(modules), {"armes": 2, "scanner": True, "pret": True})

    def test_vaisseau_de_minage_n_est_pas_un_chasseur(self):
        modules = [{"emplacement": "MediumHardpoint1", "objet": "hpt_mining_subsurfdispmisle_fixed_medium"},
                   {"emplacement": "MediumHardpoint2", "objet": "hpt_mining_seismchrgwarhd_fixed_medium"},
                   {"emplacement": "SmallHardpoint1", "objet": "hpt_mininglaser_fixed_small"}]
        self.assertFalse(chasse.profil(modules)["pret"])


class Tableau(unittest.TestCase):
    def test_primes_par_faction_puis_encaissement(self):
        c = chasse.vierge()
        chasse.activer(c, "t")
        chasse.prime(c, {"TotalReward": 300, "Rewards": [{"Faction": "A", "Reward": 200}, {"Faction": "B", "Reward": 100}]})
        chasse.prime(c, {"TotalReward": 50, "Rewards": [{"Faction": "A", "Reward": 50}]})
        self.assertEqual((c["eliminations"], c["gains"], c["meilleure"], c["a_encaisser_total"]), (2, 350, 300, 350))
        chasse.encaisser(c, {"Type": "bounty", "Factions": [{"Faction": "A", "Amount": 250}]})
        self.assertEqual(c["a_encaisser"], {"B": 100})
        self.assertFalse(chasse.encaisser(c, {"Type": "CombatBond"}))
        chasse.perdre_primes(c)
        self.assertEqual(c["a_encaisser_total"], 0)

    def test_les_primes_survivent_a_la_fin_de_la_chasse(self):
        c = chasse.vierge()
        chasse.activer(c, "t")
        chasse.prime(c, {"TotalReward": 10, "Rewards": [{"Faction": "A", "Reward": 10}]})
        self.assertEqual(chasse.arreter(c), {"eliminations": 1, "gains": 10})
        self.assertEqual(c["a_encaisser_total"], 10)
        self.assertIsNone(chasse.arreter(c))

    def test_veille_une_seule_annonce(self):
        v, e = chasse.Veille(), cible("Wanted", 10)
        self.assertTrue(v.nouvelle(e, 100))
        self.assertFalse(v.nouvelle(e, 150))
        self.assertTrue(v.nouvelle(e, 100 + chasse.REPOS_ANNONCE + 1))


def scan_planete(ident=5, **autres):
    return {"event": "Scan", "ScanType": "Detailed", "BodyName": f"Sys {ident}", "BodyID": ident, "StarSystem": "Sys",
            "SystemAddress": 1, "PlanetClass": "Rocky body", "MassEM": 0.1, "TerraformState": "", "Landable": True,
            "AtmosphereType": "CarbonDioxide", "SurfaceGravity": 2.0, "SurfaceTemperature": 180.0,
            "SurfacePressure": 1000.0, "Volcanism": "", "WasDiscovered": False, "WasMapped": False,
            "WasFootfalled": False, **autres}


class Valeurs(unittest.TestCase):
    def test_reference_de_la_formule(self):
        # Monde terrestre de 1 masse terrestre : valeurs de référence de la formule de MattG
        k = 64831 + 116295
        base = k + k * 0.56591828
        self.assertEqual(exploration.valeur_planete("Earthlike body", False, 1.0, False), round(base))
        carte = base * (10 / 3)
        carte = (carte + carte * 0.3) * 1.25
        self.assertEqual(exploration.valeur_planete("Earthlike body", False, 1.0, False, True, False), round(carte))

    def test_premiere_decouverte_rapporte_plus(self):
        v = lambda *a: exploration.valeur_planete("Water world", True, 0.5, *a)
        self.assertAlmostEqual(v(True), v(False) * 2.6, delta=2)
        self.assertGreater(v(True, True, True), v(False, True, True))
        self.assertGreater(v(False, True, True), v(False, True, False))

    def test_plancher_de_500(self):
        self.assertEqual(exploration.valeur_planete("Icy body", False, 0.0001, False), 500)

    def test_etoiles(self):
        self.assertGreater(exploration.valeur_etoile("N", 1.4, False), exploration.valeur_etoile("K", 1.4, False))
        self.assertEqual(exploration.valeur_etoile("G", 0, True), round(1200 * 2.6))


class Exobiologie(unittest.TestCase):
    def test_prix_reels_vendus_par_le_commandant(self):
        attendus = {"$Codex_Ent_Stratum_07_Name;": 19010800, "$Codex_Ent_Tubus_05_Name;": 7774700,
                    "$Codex_Ent_Tussocks_03_Name;": 1849000, "$Codex_Ent_Bacterial_05_Name;": 1000000}
        especes = exploration._especes_par_id()
        for ident, prix in attendus.items():
            self.assertEqual(especes[ident]["valeur"], prix)

    def test_regle_elimine(self):
        regle = {"body_type": ["Rocky body"], "atmosphere": ["CarbonDioxide"], "min_temperature": 170, "max_gravity": 0.3}
        self.assertTrue(exploration.regle_ok(regle, scan_planete()))
        self.assertFalse(exploration.regle_ok(regle, scan_planete(SurfaceTemperature=120)))
        self.assertFalse(exploration.regle_ok(regle, scan_planete(PlanetClass="Icy body")))
        self.assertFalse(exploration.regle_ok(regle, scan_planete(SurfaceGravity=9.8)))
        self.assertFalse(exploration.regle_ok({"atmosphere": "Any"}, scan_planete(AtmosphereType="None")))

    def test_volcanisme(self):
        self.assertTrue(exploration.regle_ok({"volcanism": "None"}, scan_planete()))
        self.assertFalse(exploration.regle_ok({"volcanism": "Any"}, scan_planete()))
        self.assertTrue(exploration.regle_ok({"volcanism": ["silicate"]}, scan_planete(Volcanism="minor silicate vapour geysers volcanism")))
        self.assertFalse(exploration.regle_ok({"volcanism": "!silicate"}, scan_planete(Volcanism="minor silicate vapour geysers volcanism")))

    def test_bio_fourchette_puis_valeur_exacte(self):
        c = exploration.Carnet()
        c.scan(scan_planete())
        genre, espece = "$Codex_Ent_Stratum_Genus_Name;", "$Codex_Ent_Stratum_07_Name;"
        fiche = c.signaux_saa({"BodyID": 5, "BodyName": "Sys 5", "SystemAddress": 1,
                               "Signals": [{"Type": "$SAA_SignalType_Biological;", "Count": 1}],
                               "Genuses": [{"Genus": genre, "Genus_Localised": "Stratum"}]})
        self.assertLessEqual(fiche["bio"]["min"], fiche["bio"]["max"])
        self.assertTrue(fiche["bio"]["bonus"])
        analyse = {"ScanType": "Log", "Genus": genre, "Species": espece, "Species_Localised": "Stratum Tectonicas",
                   "SystemAddress": 1, "Body": 5, "WasLogged": False}
        self.assertIsNone(c.organique(analyse))
        fiche = c.fiche_id(5)
        self.assertEqual((fiche["bio"]["min"], fiche["bio"]["max"]), (19010800, 19010800))
        self.assertEqual(fiche["bio"]["max_bonus"], 19010800 * 5)
        self.assertEqual(c.organique({**analyse, "ScanType": "Analyse"}), (19010800 * 5, True))
        self.assertEqual(c.vue()["session"]["exo"], 19010800 * 5)

    def test_pas_de_bonus_si_deja_foule_ou_deja_repertorie(self):
        c = exploration.Carnet()
        c.scan(scan_planete(WasFootfalled=True))
        e = {"ScanType": "Analyse", "Genus": "$Codex_Ent_Stratum_Genus_Name;", "Species": "$Codex_Ent_Stratum_07_Name;",
             "SystemAddress": 1, "Body": 5, "WasLogged": False}
        self.assertEqual(c.organique(e), (19010800, False))
        c = exploration.Carnet()
        c.scan(scan_planete())
        self.assertEqual(c.organique({**e, "WasLogged": True}), (19010800, False))

    def test_vente_et_mort(self):
        c = exploration.Carnet()
        c.scan(scan_planete())
        self.assertGreater(c.vue()["session"]["a_vendre"], 0)
        c.vente_exploration({"Discovered": [{"SystemName": "Sys", "NumBodies": 1}], "TotalEarnings": 900})
        self.assertEqual((c.vue()["session"]["a_vendre"], c.vue()["session"]["vendu"]), (0, 900))
        c.scan(scan_planete(ident=6))
        c.perdre_donnees()
        self.assertEqual(c.vue()["session"]["a_vendre"], 0)

    def test_balise_non_vendable_et_ne_remplace_pas_un_scan(self):
        c = exploration.Carnet()
        c.scan(scan_planete(ScanType="NavBeaconDetail"))
        self.assertEqual(c.vue()["session"]["a_vendre"], 0)
        c.scan(scan_planete())
        self.assertGreater(c.vue()["session"]["a_vendre"], 0)
        fiche, _ = c.scan(scan_planete(ScanType="NavBeaconDetail"))
        self.assertFalse(fiche["balise"])


class Voix(unittest.TestCase):
    def texte(self, ids):
        catalogue = {l["id"]: l["texte"] for l in morceaux.catalogue()}
        return " ".join(catalogue[i] for i in ids if i is not morceaux.PAUSE)

    def test_montants(self):
        self.assertEqual(self.texte(morceaux.montant(3_400_000)), "trois virgule quatre millions de crédits")
        self.assertEqual(self.texte(morceaux.montant(1_000_000)), "un million de crédits")
        self.assertEqual(self.texte(morceaux.montant(168_764)), "cent soixante-neuf mille crédits")
        self.assertEqual(self.texte(morceaux.montant(1_200)), "mille crédits")
        self.assertEqual(self.texte(morceaux.montant(999_960)), "un million de crédits")
        self.assertEqual(self.texte(morceaux.montant(95_054_000)), "quatre-vingt-quinze virgule un millions de crédits")
        self.assertEqual(self.texte(morceaux.montant(1_500_000_000)), "un virgule cinq milliard de crédits")
        self.assertEqual(self.texte(morceaux.montant(240)), "deux cent quarante crédits")

    def test_phrases_entierement_au_catalogue(self):
        connus = {l["id"] for l in morceaux.catalogue()}
        phrases = [morceaux.pour_cible(668_764), morceaux.pour_analyse(95_054_000, True),
                   morceaux.pour_corps({"valeur_carto": 7_842_100, "premiere_decouverte": True}),
                   morceaux.pour_bio({"max_bonus": 112_700_000, "bonus": True})]
        for phrase in phrases:
            self.assertFalse([i for i in phrase if i is not morceaux.PAUSE and i not in connus])


class Journal(unittest.IsolatedAsyncioTestCase):
    """Événements rejoués dans le vrai lecteur de journal, voix et interface remplacées."""

    def setUp(self):
        self.dit, self.envoye = [], []
        self.origines = (logs.envoyer_donnees_web, logs._dire, logs._dire_morceaux, logs.SYSTEMES_PROCHES_ACTIF)

        async def envoyer(message):
            self.envoye.append(message)

        async def dire(cle):
            self.dit.append(cle)

        async def dire_morceaux(_ids, secours):
            self.dit.append(secours)

        logs.envoyer_donnees_web, logs._dire, logs._dire_morceaux = envoyer, dire, dire_morceaux
        logs.SYSTEMES_PROCHES_ACTIF = False
        logs._carnet.nouvelle_session()
        logs._veille.oublier()
        logs._corps_annonces.clear()
        logs._reinitialiser_etat()

    def tearDown(self):
        logs.envoyer_donnees_web, logs._dire, logs._dire_morceaux, logs.SYSTEMES_PROCHES_ACTIF = self.origines
        logs._carnet.nouvelle_session()
        logs._reinitialiser_etat()

    async def ev(self, nom, **champs):
        await logs._traiter_ligne(json.dumps({"timestamp": "2026-11-23T20:00:00Z", "event": nom, **champs}), en_direct=True)

    async def armer(self):
        await self.ev("Loadout", Ship="python", Modules=[
            {"Slot": "LargeHardpoint1", "Item": "hpt_beamlaser_gimbal_large", "On": True, "Health": 1.0},
            {"Slot": "MediumHardpoint1", "Item": "hpt_multicannon_gimbal_medium", "On": True, "Health": 1.0}])

    async def test_hazres_active_la_chasse_et_annonce_les_cibles(self):
        await self.armer()
        await self.ev("SupercruiseDestinationDrop", Type="$MULTIPLAYER_SCENARIO79_TITLE;")
        self.assertTrue(logs.ETAT["chasse"]["actif"])
        self.assertEqual(logs.ETAT["chasse"]["zone"], "res_danger")
        self.assertIn("chasse_active", self.dit)
        self.dit.clear()
        await self.ev("ShipTargeted", TargetLocked=True, Ship="python", ScanStage=3, PilotName="$npc_name_decorate:#name=A;", PilotRank="Expert", LegalStatus="Wanted", Bounty=1000)
        await self.ev("ShipTargeted", TargetLocked=True, Ship="python", ScanStage=3, PilotName="$npc_name_decorate:#name=A;", PilotRank="Expert", LegalStatus="Wanted", Bounty=1000)
        await self.ev("ShipTargeted", TargetLocked=True, Ship="eagle", ScanStage=3, PilotName="$npc_name_decorate:#name=B;", PilotRank="Expert", LegalStatus="Clean")
        self.assertEqual(self.dit, ["chasse_recherchee", "chasse_clean"])
        self.assertEqual(logs.ETAT["cible"]["verdict"]["code"], "clean")

    async def test_pas_de_chasse_sans_armes(self):
        await self.ev("SupercruiseDestinationDrop", Type="$MULTIPLAYER_SCENARIO79_TITLE;")
        self.assertFalse(logs.ETAT["chasse"]["actif"])

    async def test_hors_chasse_la_cible_est_jugee_mais_silencieuse(self):
        await self.ev("ShipTargeted", TargetLocked=True, Ship="python", ScanStage=3, PilotName="$npc_name_decorate:#name=A;", LegalStatus="Wanted", Bounty=1000)
        self.assertEqual(logs.ETAT["cible"]["verdict"]["code"], "recherche")
        self.assertEqual(self.dit, [])

    async def test_fin_de_chasse_en_supercroisiere_primes_gardees(self):
        await self.armer()
        await self.ev("SupercruiseDestinationDrop", Type="$MULTIPLAYER_SCENARIO79_TITLE;")
        await self.ev("Bounty", TotalReward=5000, Rewards=[{"Faction": "A", "Reward": 5000}], Target="python")
        await self.ev("SupercruiseEntry", StarSystem="Sys")
        self.assertFalse(logs.ETAT["chasse"]["actif"])
        self.assertEqual(logs.ETAT["chasse"]["a_encaisser_total"], 5000)
        self.assertIn("chasse_fin", self.dit)

    async def test_mode_a_la_voix_survit_a_la_supercroisiere(self):
        await logs.commander_chasse(True)
        await self.ev("SupercruiseEntry", StarSystem="Sys")
        self.assertTrue(logs.ETAT["chasse"]["actif"])
        await logs.commander_chasse(False)
        self.assertFalse(logs.ETAT["chasse"]["actif"])
        self.assertIn("chasse_coupee", self.dit)

    async def test_mort_perd_les_primes(self):
        await self.armer()
        await self.ev("Bounty", TotalReward=5000, Rewards=[{"Faction": "A", "Reward": 5000}], Target="python")
        await self.ev("Died")
        self.assertEqual(logs.ETAT["chasse"]["a_encaisser_total"], 0)
        self.assertFalse(logs.ETAT["chasse"]["actif"])

    async def test_tir_sur_un_clean_en_chasse(self):
        await logs.commander_chasse(True)
        self.dit.clear()
        await self.ev("CommitCrime", CrimeType="assault", Faction="A", Fine=400)
        self.assertEqual(self.dit, ["chasse_tir_clean"])

    async def test_nomad_du_lancement_au_retour(self):
        await self.ev("LaunchVessel", VesselType="lander01", VesselType_Localised="Nomad", Loadout="base", ID=28, PlayerControlled=True)
        self.assertEqual(logs.ETAT["pilotage"]["genre"], "nomade")
        self.assertIsNone(logs.ETAT["vaisseau"]["chasseur"])
        await self.ev("Disembark", SRV=False, OnPlanet=True, Body="A 1")
        self.assertEqual(logs.ETAT["pilotage"]["genre"], "nomade")
        await self.ev("DockSRV", SRVType="lander01", ID=28)
        self.assertIsNone(logs.ETAT["pilotage"]["genre"])

    async def test_ancien_journal_du_nomad(self):
        await self.ev("LaunchFighter", Loadout="base", ID=28, PlayerControlled=True)
        self.assertEqual(logs.ETAT["pilotage"]["genre"], "nomade")

    async def test_chasseur_pilote_et_coque(self):
        await self.ev("LaunchFighter", Loadout="zero", ID=44, PlayerControlled=True)
        self.assertEqual(logs.ETAT["pilotage"]["genre"], "chasseur")
        await self.ev("HullDamage", Health=0.6, Fighter=True, PlayerPilot=True)
        self.assertEqual(logs.ETAT["pilotage"]["coque"], 0.6)
        await self.ev("VehicleSwitch", To="Mothership")
        self.assertIsNone(logs.ETAT["pilotage"]["genre"])

    async def test_chasseur_de_l_equipage_ne_change_pas_la_vue(self):
        await self.ev("LaunchFighter", Loadout="three", ID=44, PlayerControlled=False)
        self.assertIsNone(logs.ETAT["pilotage"]["genre"])
        self.assertEqual(logs.ETAT["vaisseau"]["chasseur"], "deploye")

    async def test_partie_reprise_en_nomad_garde_le_vaisseau(self):
        await self.ev("LoadGame", Commander="X", Ship="python", Ship_Localised="Python", ShipName="", ShipIdent="")
        await self.ev("LoadGame", Commander="X", Ship="Lander01", Ship_Localised="Nomad", ShipName="", ShipIdent="")
        self.assertEqual(logs.ETAT["vaisseau"]["type"], "python")
        self.assertEqual(logs.ETAT["pilotage"]["genre"], "nomade")

    async def test_scan_de_valeur_dit_une_seule_fois(self):
        e = scan_planete(PlanetClass="Earthlike body", MassEM=1.0, Landable=False)
        await self.ev("Scan", **{k: v for k, v in e.items() if k != "event"})
        await self.ev("Scan", **{k: v for k, v in e.items() if k != "event"})
        self.assertEqual(self.dit.count("scan_premiere"), 1)

    async def test_petit_corps_reste_a_l_ecran(self):
        e = scan_planete(PlanetClass="Icy body", MassEM=0.01)
        await self.ev("Scan", **{k: v for k, v in e.items() if k != "event"})
        self.assertEqual(self.dit, [])
        lignes = [m["evenement"]["texte"] for m in self.envoye if m.get("type") == "evenement"]
        self.assertTrue(any("première découverte" in t and "≈" in t for t in lignes))


if __name__ == "__main__":
    unittest.main()
