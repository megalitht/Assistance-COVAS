"""Route tracée : distances, sauts restants, progression et annonces du voyage.
Sans touche, sans micro, sans réseau et sans macros.py : le journal est simulé."""
import importlib.util
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from module.dialogue import morceaux  # noqa: E402
from module.jeu import route  # noqa: E402
from module.jeu.carburant import Reservoir  # noqa: E402

DOSSIER_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _flux in (sys.stdout, sys.stderr):                  # comme interface/terminal.py
    if hasattr(_flux, "reconfigure"):
        _flux.reconfigure(errors="replace")

# Copie du NavRoute.json du commandant (23/11/2026)
NAVROUTE = {"timestamp": "2026-11-23T23:11:49Z", "event": "NavRoute", "Route": [
    {"StarSystem": "BD-15 447", "SystemAddress": 2007997813450, "StarPos": [8.0, -81.25, -40.125], "StarClass": "K"},
    {"StarSystem": "LTT 10823", "SystemAddress": 358730371778, "StarPos": [-24.5, -81.15625, -70.09375], "StarClass": "K"},
    {"StarSystem": "Kharwa", "SystemAddress": 2869172118913, "StarPos": [-55.59375, -98.53125, -97.25], "StarClass": "M"},
    {"StarSystem": "Arietis Sector QI-T b3-4", "SystemAddress": 9465973384561,
     "StarPos": [-65.71875, -107.75, -136.03125], "StarClass": "M"},
]}
REGLAGES = {"annonces": True, "sauts_restants": 5, "sauts_min_mi_parcours": 6}


def navroute(n, depart=0, classe="M", nom="S"):
    """Route de n sauts en ligne droite, 10 al par saut : S0 ... Sn."""
    return {"Route": [{"StarSystem": f"{nom}{i}", "SystemAddress": 1000 + i, "StarPos": [i * 10.0, 0, 0],
                       "StarClass": classe} for i in range(depart, depart + n + 1)]}


class Lecture(unittest.TestCase):
    def test_navroute_du_commandant(self):
        etapes = route.lire_navroute(NAVROUTE)
        self.assertEqual([e["systeme"] for e in etapes][0], "BD-15 447")
        self.assertEqual(etapes[0]["distance"], 0.0)
        self.assertAlmostEqual(etapes[1]["distance"], 44.25, places=1)
        self.assertTrue(all(e["ravitaillable"] for e in etapes))
        resume = route.resume(etapes, 0)
        self.assertEqual(resume["sauts_restants"], 3)
        self.assertAlmostEqual(resume["distance_totale"], sum(e["distance"] for e in etapes), places=2)
        self.assertEqual(resume["progression"], 0.0)

    def test_route_vide(self):
        self.assertEqual(route.lire_navroute({"Route": []}), [])
        self.assertEqual(route.lire_navroute(None), [])
        self.assertIsNone(route.resume([], None))

    def test_classes_ravitaillables(self):
        for classe in "KGBFOAM":
            self.assertTrue(route.ravitaillable(classe))
        for classe in ("N", "DA", "L", "T", "TTS", "H", "", None):
            self.assertFalse(route.ravitaillable(classe))
        self.assertTrue(route.ravitaillable("M_RedGiant"))


class Position(unittest.TestCase):
    def setUp(self):
        self.etapes = route.lire_navroute(navroute(10))

    def test_indice_par_adresse_puis_par_nom(self):
        self.assertEqual(route.indice(self.etapes, "S3", 1003), 3)
        self.assertEqual(route.indice(self.etapes, "S3", None), 3)
        self.assertIsNone(route.indice(self.etapes, "S3", 9999))      # même nom, autre système
        self.assertIsNone(route.indice(self.etapes, "Ailleurs", None))

    def test_resume_en_chemin(self):
        r = route.resume(self.etapes, 4)
        self.assertEqual((r["sauts_restants"], r["nombre_sauts"], r["source"]), (6, 10, "route"))
        self.assertEqual((r["distance_restante"], r["distance_parcourue"]), (60.0, 40.0))
        self.assertEqual(r["progression"], 0.4)
        self.assertEqual(r["destination"], "S10")

    def test_arrive(self):
        r = route.resume(self.etapes, 10)
        self.assertEqual((r["sauts_restants"], r["distance_restante"], r["progression"]), (0, 0.0, 1.0))

    def test_le_jeu_l_emporte_s_il_differe(self):
        # FSDTarget vise le système suivant (S5) et compte 7 sauts au lieu de 6
        r = route.resume(self.etapes, 4, {"systeme": "S5", "sauts_restants": 7})
        self.assertEqual((r["sauts_restants"], r["source"]), (7, "jeu"))
        self.assertEqual(r["distance_restante"], 70.0)

    def test_cible_pendant_le_saut_ne_change_rien(self):
        # Pendant le saut vers S5, le jeu vise déjà S6 et compte ce qui restera à l'arrivée en S5
        r = route.resume(self.etapes, 4, {"systeme": "S6", "sauts_restants": 5})
        self.assertEqual((r["sauts_restants"], r["source"]), (6, "route"))

    def test_hors_de_la_route(self):
        r = route.resume(self.etapes, None, {"systeme": "S8", "sauts_restants": 3})
        self.assertEqual((r["sauts_restants"], r["source"]), (3, "jeu"))
        self.assertEqual(r["distance_restante"], 30.0)
        self.assertIsNone(route.resume(self.etapes, None)["sauts_restants"])
        # Cible manuelle hors de la route : le décompte du jeu ne la concerne pas
        self.assertIsNone(route.resume(self.etapes, None, {"systeme": "Ailleurs", "sauts_restants": 0})["sauts_restants"])


class Annonces(unittest.TestCase):
    def setUp(self):
        self.a = route.Annonceur()
        self.a.nouvelle_route([])                          # premier relevé au démarrage : muet

    def tracer(self, n, nom="S"):
        etapes = route.lire_navroute(navroute(n, nom=nom))
        return etapes, self.a.nouvelle_route(etapes)

    def voyage(self, etapes, reglages=REGLAGES):
        """Saute d'étape en étape ; renvoie {indice: annonces}."""
        dites = {}
        for i in range(1, len(etapes)):
            r = route.resume(etapes, i)
            annonces = self.a.arrivee(r, reglages, systeme=etapes[i]["systeme"])
            if annonces:
                dites[i] = annonces
        return dites

    def test_premiere_route_au_demarrage_muette(self):
        a = route.Annonceur()
        self.assertIsNone(a.nouvelle_route(route.lire_navroute(navroute(3))))
        self.assertEqual(a.nouvelle_route(route.lire_navroute(navroute(3, nom="T"))), "route_tracee")

    def test_route_tracee_une_fois_par_destination(self):
        etapes, annonce = self.tracer(12)
        self.assertEqual(annonce, "route_tracee")
        # Le jeu recalcule la route en chemin (même destination) : pas de nouvelle annonce
        recalculee = route.lire_navroute(navroute(9, depart=3))
        self.assertIsNone(self.a.nouvelle_route(recalculee))
        self.assertIsNone(self.a.nouvelle_route([]))       # fichier vidé : on attend NavRouteClear

    def test_voyage_complet(self):
        etapes, _ = self.tracer(12)
        dites = self.voyage(etapes)
        # 12 sauts : mi-parcours au 6e (il en reste 6), « 5 sauts » au 7e, dernier saut au 11e, arrivée
        self.assertEqual(dites, {6: [("mi_parcours", 6)], 7: [("sauts_restants", 5)],
                                 11: [("dernier_saut", 1)], 12: [("arrivee", 0)]})

    def test_mi_parcours_et_cinq_sauts_ensemble(self):
        etapes, _ = self.tracer(10)
        dites = self.voyage(etapes)
        self.assertEqual(dites[5], [("mi_parcours", 5)])   # une seule phrase : « Il reste cinq sauts »
        self.assertNotIn(("sauts_restants", 5), [x for v in dites.values() for x in v])

    def test_route_courte(self):
        etapes, _ = self.tracer(4)
        self.assertEqual(self.voyage(etapes), {3: [("dernier_saut", 1)], 4: [("arrivee", 0)]})
        etapes, _ = self.tracer(1, nom="U")
        self.assertEqual(self.voyage(etapes), {1: [("arrivee", 0)]})

    def test_sauts_restants_reglable(self):
        etapes, _ = self.tracer(12)
        dites = self.voyage(etapes, dict(REGLAGES, sauts_restants=0, sauts_min_mi_parcours=99))
        self.assertEqual(sorted(dites), [11, 12])

    def test_arrivee_apres_effacement_pendant_le_dernier_saut(self):
        etapes, _ = self.tracer(3)
        for i in (1, 2):
            self.a.arrivee(route.resume(etapes, i), REGLAGES, systeme=etapes[i]["systeme"])
        # StartJump vers S3, NavRouteClear, puis FSDJump dans S3 (vu 268 fois dans les journaux)
        self.a.route_effacee(saut_vers="S3")
        self.assertEqual(self.a.arrivee(None, REGLAGES, systeme="S3"), [("arrivee", 0)])
        self.assertEqual(self.a.arrivee(None, REGLAGES, systeme="S3"), [])

    def test_effacement_a_la_main(self):
        etapes, _ = self.tracer(3)
        self.a.route_effacee(saut_vers=None)
        self.assertEqual(self.a.arrivee(None, REGLAGES, systeme="S1"), [])
        # Même destination retracée après effacement : c'est une nouvelle route
        self.assertEqual(self.a.nouvelle_route(etapes), "route_tracee")

    def test_effacement_pendant_un_saut_ailleurs(self):
        self.tracer(3)
        self.a.route_effacee(saut_vers="S3")
        self.assertEqual(self.a.arrivee(None, REGLAGES, systeme="Ailleurs"), [])

    def test_relecture_muette(self):
        etapes, _ = self.tracer(4)
        for i in range(1, 5):
            self.assertEqual(self.a.arrivee(route.resume(etapes, i), REGLAGES, parler=False,
                                            systeme=etapes[i]["systeme"]), [])


class Voix(unittest.TestCase):
    def ids(self, annonce, n):
        return [i.rsplit("/", 1)[-1] if i else None for i in morceaux.pour_route(annonce, n)]

    def test_phrases_assemblees(self):
        self.assertEqual(self.ids("route_tracee", 12), ["RouteTracee.mp3", "012.mp3", "Sauts.mp3"])
        self.assertEqual(self.ids("sauts_restants", 1), ["IlReste.mp3", "001.mp3", "Saut.mp3"])
        self.assertEqual(self.ids("mi_parcours", 136),
                         ["MiParcours.mp3", None, "IlReste.mp3", "100.mp3", "036.mp3", "Sauts.mp3"])

    def test_sans_nombre(self):
        self.assertIsNone(morceaux.pour_route("dernier_saut", 1))
        self.assertIsNone(morceaux.pour_route("arrivee", 0))
        self.assertIsNone(morceaux.pour_route("route_tracee", 1000))

    def test_morceaux_au_catalogue(self):
        ids = {l["id"] for l in morceaux.catalogue()}
        for nom in ("RouteTracee", "MiParcours", "IlReste", "Saut", "Sauts"):
            self.assertIn(f"data/son/Morceaux/Route/{nom}.mp3", ids)

    def test_repliques_fixes_dans_barks(self):
        with open(os.path.join(DOSSIER_BACKEND, "data", "barks.json"), encoding="utf-8") as f:
            barks = json.load(f)
        for cle in ("route_tracee", "route_mi_parcours", "route_sauts_restants", "route_dernier_saut",
                    "route_arrivee"):
            self.assertIn(cle, barks)


def _lecteur_prive():
    avant = set(sys.modules)
    chemin = os.path.join(DOSSIER_BACKEND, "module", "jeu", "lecteur_logs.py")
    spec = importlib.util.spec_from_file_location("covas_lecteur_logs_route", chemin)
    copie = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copie)
    for nom in ("module.interface.serveur_ws", "module.jeu.edsm"):
        if nom in sys.modules and nom not in avant:
            del sys.modules[nom]
            paquet, _, enfant = nom.rpartition(".")
            delattr(sys.modules[paquet], enfant)
    return copie


logs = _lecteur_prive()


class Journal(unittest.IsolatedAsyncioTestCase):
    """Le vrai lecteur : NavRoute.json, StartJump, FSDTarget, NavRouteClear et FSDJump."""

    def setUp(self):
        self.dit, self.envoye = [], []
        self.origines = (logs.envoyer_donnees_web, logs._dire, logs._dire_morceaux,
                         logs.SYSTEMES_PROCHES_ACTIF, logs.programme_actuel)

        async def envoyer(message):
            self.envoye.append(message)

        async def dire(cle, urgent=False, secours=None):
            self.dit.append(cle)

        async def dire_morceaux(ids, secours):
            self.dit.append(secours + ":" + "+".join(i.rsplit("/", 1)[-1][:-4] for i in ids if i))

        logs.envoyer_donnees_web, logs._dire, logs._dire_morceaux = envoyer, dire, dire_morceaux
        logs.SYSTEMES_PROCHES_ACTIF = False
        logs.programme_actuel = lambda: None
        logs._reservoir = Reservoir()
        logs._annonceur = route.Annonceur()
        logs._reinitialiser_etat()
        logs._suivi["en_direct"] = True

    def tearDown(self):
        (logs.envoyer_donnees_web, logs._dire, logs._dire_morceaux,
         logs.SYSTEMES_PROCHES_ACTIF, logs.programme_actuel) = self.origines
        logs._reinitialiser_etat()
        logs._suivi["en_direct"] = False

    async def ev(self, nom, **champs):
        await logs._traiter_ligne(json.dumps({"timestamp": "2026-11-24T20:00:00Z", "event": nom, **champs}),
                                  en_direct=True)

    async def navroute(self, donnees):
        logs._maj_route(donnees)
        await logs._annoncer_route_tracee()

    async def sauter(self, i, n, effacer=False):
        await self.ev("StartJump", JumpType="Hyperspace", StarSystem=f"S{i}", StarClass="M")
        if i < n:
            await self.ev("FSDTarget", Name=f"S{i + 1}", StarClass="M", RemainingJumpsInRoute=n - i)
        if effacer:
            await self.ev("NavRouteClear")
            await self.navroute({"Route": []})
        await self.ev("FSDJump", StarSystem=f"S{i}", SystemAddress=1000 + i, StarPos=[i * 10.0, 0, 0],
                      JumpDist=10.0, FuelUsed=1.0, FuelLevel=30.0)

    async def test_voyage_de_douze_sauts(self):
        await self.navroute({"Route": []})                 # démarrage : rien à annoncer
        await self.ev("Location", StarSystem="S0", SystemAddress=1000, StarPos=[0, 0, 0])
        await self.navroute(navroute(12))
        await self.ev("FSDTarget", Name="S1", StarClass="M", RemainingJumpsInRoute=12)
        r = logs.ETAT["route"]
        self.assertEqual((r["sauts_restants"], r["distance_restante"], r["destination"]), (12, 120.0, "S12"))
        for i in range(1, 13):
            await self.sauter(i, 12, effacer=(i == 12))
        self.assertEqual(self.dit, ["route_tracee:RouteTracee+012+Sauts",
                                    "route_mi_parcours:MiParcours+IlReste+006+Sauts",
                                    "route_sauts_restants:IlReste+005+Sauts",
                                    "route_dernier_saut", "route_arrivee"])
        lignes = [m["evenement"]["texte"] for m in self.envoye if m.get("type") == "evenement"]
        self.assertIn("Destination atteinte : S12", lignes)
        self.assertIn("Route tracée vers S12 — 12 sauts, 120.0 al", lignes)

    async def test_voyage_automatique_annonce_seul_son_arrivee(self):
        logs.programme_actuel = lambda: logs.PROGRAMME_VOYAGE
        await self.navroute({"Route": []})
        await self.ev("Location", StarSystem="S0", SystemAddress=1000, StarPos=[0, 0, 0])
        await self.navroute(navroute(2))
        await self.sauter(1, 2)
        await self.sauter(2, 2, effacer=True)
        self.assertEqual(self.dit, ["route_tracee:RouteTracee+002+Sauts", "route_dernier_saut"])

    async def test_annonces_coupees(self):
        from module import config
        ancien = config._etat["valeurs"]
        config._etat["valeurs"] = {**config.DEFAUTS, "route": dict(config.DEFAUTS["route"], annonces=False)}
        config._etat["verifie"] = float("inf")
        try:
            await self.navroute({"Route": []})
            await self.ev("Location", StarSystem="S0", SystemAddress=1000, StarPos=[0, 0, 0])
            await self.navroute(navroute(2))
            await self.sauter(1, 2)
            self.assertEqual(self.dit, [])
            lignes = [m["evenement"]["texte"] for m in self.envoye if m.get("type") == "evenement"]
            self.assertIn("Dernier saut avant S2", lignes)
        finally:
            config._etat.update(valeurs=ancien, verifie=0.0)

    async def test_carburant_suit_le_decompte_de_la_route(self):
        await self.navroute({"Route": []})
        await self.ev("Location", StarSystem="S0", SystemAddress=1000, StarPos=[0, 0, 0])
        await self.navroute(navroute(4, classe="L"))
        self.assertEqual([e["systeme"] for e in logs._etapes_a_venir()], ["S1", "S2", "S3", "S4"])


if __name__ == "__main__":
    unittest.main()
