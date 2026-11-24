"""Données externes (EDSM, Spansh, Inara) : tout est simulé, AUCUNE requête ne part vers Internet.
Vérifie aussi que le COVAS ne bloque jamais et affiche « Données indisponibles » en cas de panne."""
import asyncio
import glob
import io
import json
import os
import sys
import time
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from module.externe import edsm, inara, reseau, service, spansh  # noqa: E402
from module.externe.cache import Cache  # noqa: E402
from module.externe.reseau import ErreurExterne  # noqa: E402

DOSSIER_ED = os.path.join(os.path.expanduser("~"), "Saved Games", "Frontier Developments", "Elite Dangerous")
for _flux in (sys.stdout, sys.stderr):
    if hasattr(_flux, "reconfigure"):
        _flux.reconfigure(errors="replace")

# Loadout réel du commandant (Caspian Explorer, FSD Mk II), réduit à ce qui sert
CASPIAN = {"Ship": "explorer_nx", "UnladenMass": 1210.400024, "FuelCapacity": {"Main": 128.0, "Reserve": 1.14},
           "MaxJumpRange": 50.0364, "Modules": [
               {"Slot": "FrameShiftDrive", "Item": "int_hyperdrive_overcharge_size8_class5_overchargebooster_mkii"}]}


class FausseReponse(io.BytesIO):
    def __init__(self, donnees, statut=200):
        super().__init__(json.dumps(donnees).encode())
        self.status = statut

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class Reseau(unittest.TestCase):
    def test_reponse_et_user_agent(self):
        vu = {}

        def ouvrir(requete, timeout):
            vu.update(url=requete.full_url, ua=requete.get_header("User-agent"), delai=timeout)
            return FausseReponse({"ok": 1})
        with mock.patch("urllib.request.urlopen", ouvrir):
            self.assertEqual(reseau.requete_json("https://x.test/a", {"q": "Sol B"}, delai=3), (200, {"ok": 1}))
        self.assertEqual(vu["url"], "https://x.test/a?q=Sol+B")
        self.assertIn("COVAS-Assistance", vu["ua"])
        self.assertEqual(vu["delai"], 3)

    def test_erreurs(self):
        erreur_http = urllib.error.HTTPError("u", 400, "Bad", {}, io.BytesIO(b'{"error": "starting system"}'))
        with mock.patch("urllib.request.urlopen", side_effect=erreur_http):
            with self.assertRaises(ErreurExterne) as contexte:
                reseau.requete_json("https://x.test")
        self.assertEqual((contexte.exception.statut, contexte.exception.corps), (400, {"error": "starting system"}))
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("hors ligne")):
            self.assertRaises(ErreurExterne, reseau.requete_json, "https://x.test")
        with mock.patch("urllib.request.urlopen", side_effect=TimeoutError()):
            self.assertRaises(ErreurExterne, reseau.requete_json, "https://x.test")


class CacheLocal(unittest.TestCase):
    def test_duree_de_vie(self):
        temps = [1000.0]
        c = Cache(horloge=lambda: temps[0])
        c.ecrire("a", {"x": 1}, 60)
        self.assertEqual(c.lire("a"), {"x": 1})
        temps[0] += 61
        self.assertIsNone(c.lire("a"))

    def test_une_panne_n_est_pas_gardee(self):
        c = Cache()
        appels = []

        def panne():
            appels.append(1)
            raise ErreurExterne("hors ligne")
        self.assertRaises(ErreurExterne, c.ou_calculer, "b", 60, panne)
        self.assertEqual(c.ou_calculer("b", 60, lambda: [1]), [1])
        self.assertEqual(c.ou_calculer("b", 60, panne), [1])            # en cache : pas de requête
        self.assertEqual(len(appels), 1)


class Edsm(unittest.TestCase):
    STATIONS = {"name": "Sol", "stations": [
        {"name": "Furukawa Enterprise", "type": "Planetary Outpost", "distanceToArrival": 157, "economy": "Industrial",
         "haveMarket": True, "haveShipyard": True, "haveOutfitting": True,
         "otherServices": ["Refuel", "Universal Cartographics", "Vista Genomics", "Bartender"]},
        {"name": "Petit Poste", "type": "Outpost", "distanceToArrival": 30, "haveMarket": True, "otherServices": []}]}
    CORPS = {"name": "Sol", "bodyCount": 40, "bodies": [
        {"name": "Sol", "type": "Star", "subType": "G (White-Yellow) Star"},
        {"name": "Earth", "type": "Planet", "subType": "Earth-like world", "distanceToArrival": 507, "isLandable": False,
         "terraformingState": "Not terraformable"},
        {"name": "Mars", "type": "Planet", "subType": "High metal content world", "isLandable": True,
         "terraformingState": "Candidate for terraforming"}]}

    def faux(self, reponses):
        def requete(url, parametres=None, **_):
            for fin, reponse in reponses.items():
                if url.endswith(fin):
                    if isinstance(reponse, Exception):
                        raise reponse
                    return 200, reponse
            raise AssertionError(url)
        return mock.patch.object(edsm, "requete_json", requete)

    def test_fiche(self):
        with self.faux({"stations": self.STATIONS, "bodies": self.CORPS,
                        "estimated-value": {"estimatedValue": 1024710, "estimatedValueMapped": 3896040, "valuableBodies": []}}):
            fiche = edsm.fiche_systeme("Sol")
        self.assertTrue(fiche["connu"])
        self.assertEqual([(s["nom"], s["plateforme"]) for s in fiche["stations"]],
                         [("Furukawa Enterprise", "L"), ("Petit Poste", "M")])     # grandes plateformes d'abord
        self.assertIn("Cartographie", fiche["stations"][0]["services"])
        self.assertNotIn("Bartender", fiche["stations"][0]["services"])
        self.assertEqual((fiche["corps"]["total"], fiche["corps"]["posables"], fiche["corps"]["terraformables"]), (40, 1, 1))
        self.assertEqual(fiche["corps"]["notables"][0]["nom"], "Earth")
        self.assertEqual(fiche["valeur"]["estimation_carto"], 3896040)

    def test_systeme_inconnu_et_panne_partielle(self):
        with self.faux({"stations": {}, "bodies": {}, "estimated-value": {}}):
            fiche = edsm.fiche_systeme("Inconnu")
        self.assertEqual((fiche["stations"], fiche["corps"], fiche["valeur"], fiche["connu"]), ([], None, None, False))
        with self.faux({"stations": self.STATIONS, "bodies": ErreurExterne("HTTP 500"), "estimated-value": {}}):
            fiche = edsm.fiche_systeme("Sol")
        self.assertTrue(fiche["connu"])
        self.assertIsNone(fiche["corps"])
        self.assertEqual(len(fiche["erreurs"]), 1)


class Spansh(unittest.TestCase):
    def test_portee_du_caspian(self):
        vaisseau = spansh.parametres_vaisseau(CASPIAN)
        self.assertEqual((vaisseau["max_fuel_per_jump"], vaisseau["tank_size"], vaisseau["range_boost"]), (6.8, 128.0, 0))
        self.assertAlmostEqual(spansh.portee(vaisseau), CASPIAN["MaxJumpRange"], places=1)

    def test_ingenierie_et_booster(self):
        loadout = {**CASPIAN, "Modules": [
            {"Item": "int_hyperdrive_size5_class5", "Engineering": {"Modifiers": [
                {"Label": "FSDOptimalMass", "Value": 1500.0}, {"Label": "MaxFuelPerJump", "Value": 5.5}]}},
            {"Item": "int_guardianfsdbooster_size5"}]}
        vaisseau = spansh.parametres_vaisseau(loadout)
        self.assertEqual((vaisseau["optimal_mass"], vaisseau["max_fuel_per_jump"], vaisseau["range_boost"]), (1500.0, 5.5, 10.5))
        self.assertIsNone(spansh.parametres_vaisseau({"Modules": [{"Item": "int_fuelscoop_size5_class5"}]}))

    def faux(self, reponses):
        suite = iter(reponses)

        def requete(url, parametres=None, methode="GET", **_):
            reponse = next(suite)
            if isinstance(reponse, Exception):
                raise reponse
            return reponse
        return mock.patch.object(spansh, "requete_json", requete)

    def test_route_neutron(self):
        resultat = {"total_jumps": 17, "distance": 1200.5, "system_jumps": [
            {"system": "Sol", "distance_jumped": 0, "distance_left": 1200.5, "jumps": 0, "neutron_star": False},
            {"system": "Joseph's Lighthouse", "distance_jumped": 696.7, "distance_left": 500, "jumps": 16, "neutron_star": True}]}
        with self.faux([(202, {"job": "J"}), (202, {"status": "queued"}), (200, {"status": "ok", "result": resultat})]):
            route = spansh.route_neutron("Sol", "Colonia", 50, 60, dormir=lambda _s: None)
        self.assertEqual((route["sauts"], route["etapes"][1]["systeme"], route["etapes"][1]["neutron"]), (17, "Joseph's Lighthouse", True))

    def test_route_galaxie(self):
        resultat = {"jumps": [
            {"name": "Sol", "distance": 0, "distance_to_destination": 139.4, "fuel_in_tank": 32, "has_neutron": False, "is_scoopable": False, "must_refuel": False},
            {"name": "Sanuku", "distance": 34.9, "distance_to_destination": 104.9, "fuel_in_tank": 28.0, "has_neutron": False, "is_scoopable": True, "must_refuel": True}]}
        with self.faux([(202, {"job": "J"}), (200, {"status": "ok", "result": resultat})]):
            route = spansh.route_galaxie("Sol", "Achenar", spansh.parametres_vaisseau(CASPIAN), dormir=lambda _s: None)
        self.assertEqual((route["sauts"], route["distance"]), (1, 139.4))
        self.assertTrue(route["etapes"][1]["ravitailler"])

    def test_refus_et_trop_long(self):
        refus = ErreurExterne("HTTP 400", 400, {"error": "Could not find starting system"})
        with self.faux([(202, {"job": "J"}), refus]):
            with self.assertRaises(ErreurExterne) as contexte:
                spansh.route_neutron("Nulle Part", "Colonia", 50, dormir=lambda _s: None)
        self.assertIn("starting system", str(contexte.exception))
        with self.faux([(202, {"job": "J"})] + [(202, {"status": "queued"})] * 50):
            self.assertRaises(ErreurExterne, spansh.route_neutron, "Sol", "Colonia", 50,
                              attente_max=0, dormir=lambda _s: None)

    def test_portee_sur_les_vrais_loadout(self):
        """La portée calculée redonne celle du jeu pour (presque) tous les Loadout du commandant."""
        justes = total = 0
        for chemin in glob.glob(os.path.join(DOSSIER_ED, "Journal.*.log")):
            with open(chemin, encoding="utf-8", errors="replace") as f:
                for ligne in f:
                    if '"event":"Loadout"' in ligne:
                        e = json.loads(ligne)
                        vaisseau = spansh.parametres_vaisseau(e)
                        if vaisseau and e.get("MaxJumpRange"):
                            total += 1
                            justes += abs(spansh.portee(vaisseau) - e["MaxJumpRange"]) < 0.05
        if not total:
            self.skipTest("journaux du jeu absents")
        self.assertGreater(justes / total, 0.9, f"{justes}/{total}")


class Inara(unittest.TestCase):
    def test_limiteur_deux_par_minute(self):
        temps = [0.0]
        limiteur = inara.Limiteur(horloge=lambda: temps[0])
        self.assertTrue(limiteur.prendre())
        self.assertTrue(limiteur.prendre())
        self.assertFalse(limiteur.prendre())
        temps[0] = 59.9
        self.assertFalse(limiteur.prendre())
        temps[0] = 60.1
        self.assertTrue(limiteur.prendre())

    def test_profil(self):
        envoye = {}
        reponse = {"header": {"eventStatus": 200}, "events": [{"eventStatus": 200, "eventData": {
            "commanderName": "Test", "commanderRanksPilot": [{"rankName": "combat", "rankValue": 6, "rankProgress": 0.41}],
            "preferredAllegianceName": "Federation", "commanderSquadron": {"squadronName": "Les Rats"},
            "inaraURL": "https://inara.cz/cmdr/1/"}}]}

        def requete(url, methode="GET", corps=None, **_):
            envoye.update(corps=corps)
            return 200, reponse
        with mock.patch.object(inara, "requete_json", requete):
            profil = inara.profil("CLE", "Test", limiteur=inara.Limiteur())
        self.assertEqual((profil["escadron"], profil["lien"], profil["rangs"][0]["valeur"]), ("Les Rats", "https://inara.cz/cmdr/1/", 6))
        evenement = envoye["corps"]["events"][0]
        self.assertEqual((evenement["eventName"], envoye["corps"]["header"]["APIkey"]), ("getCommanderProfile", "CLE"))

    def test_sans_cle_rien_ne_part(self):
        with mock.patch.object(inara, "requete_json", side_effect=AssertionError("requête envoyée !")):
            self.assertRaises(ErreurExterne, inara.profil, "", "Test", limiteur=inara.Limiteur())


class Service(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.reglages = {"actif": True, "edsm": True, "spansh": True, "delai_secondes": 1, "cache_heures": 1,
                         "inara_cle": "", "inara_commandant": ""}
        self.publies = []

        async def publier(etat):
            self.publies.append(json.loads(json.dumps(etat)))
        self.s = service.ServiceExterne(lambda: dict(self.reglages), publier, cache=Cache())

    async def test_fiche_et_panne(self):
        with mock.patch.object(edsm, "fiche_systeme", return_value={"systeme": "Sol", "stations": [], "corps": None,
                                                                     "valeur": {"estimation": 1}, "erreurs": [], "connu": True}):
            await self.s.systeme("Sol")
        self.assertEqual([p["systeme"]["etat"] for p in self.publies], ["recherche", "ok"])
        with mock.patch.object(edsm, "fiche_systeme", side_effect=ErreurExterne("hors ligne")):
            await self.s.systeme("Achenar")
        self.assertEqual(self.publies[-1]["systeme"]["etat"], "indisponible")

    async def test_jamais_bloque(self):
        async def lent(*_a, **_k):
            raise asyncio.TimeoutError
        with mock.patch.object(self.s, "_en_fond", lent):
            await self.s.systeme("Sol")
        self.assertEqual(self.publies[-1]["systeme"]["etat"], "indisponible")
        debut = time.monotonic()
        with self.assertRaises(asyncio.TimeoutError):
            await self.s._en_fond(time.sleep, 2, limite=0.1)
        self.assertLess(time.monotonic() - debut, 1)

    async def test_desactive(self):
        self.reglages["actif"] = False
        with mock.patch.object(edsm, "fiche_systeme", side_effect=AssertionError("requête envoyée !")):
            await self.s.systeme("Sol")
        self.assertEqual(self.publies[-1]["systeme"]["etat"], "desactive")
        await self.s.tracer({"route": "neutron", "destination": "Colonia"}, "Sol", CASPIAN)
        self.assertEqual(self.publies[-1]["route"]["etat"], "desactive")

    async def test_route(self):
        await self.s.tracer({"route": "neutron", "destination": "Colonia"}, "Sol", {})
        self.assertIn("FSD", self.publies[-1]["route"]["message"])
        route = {"type": "neutron", "depart": "Sol", "arrivee": "Colonia", "sauts": 2, "distance": 9,
                 "etapes": [{"systeme": "Sol"}, {"systeme": "Colonia"}]}
        with mock.patch.object(spansh, "route_neutron", return_value=route) as appel:
            await self.s.tracer({"route": "neutron", "destination": "Colonia", "efficacite": 75}, "Sol", CASPIAN)
        self.assertEqual(appel.call_args.args[:2], ("Sol", "Colonia"))
        self.assertEqual(appel.call_args.args[3], 75)
        self.assertEqual(self.publies[-1]["route"]["etat"], "ok")
        self.assertAlmostEqual(self.publies[-1]["route"]["portee"], 50.04, places=1)
        self.assertEqual(appel.call_args.args[2], CASPIAN["MaxJumpRange"])          # portée écrite par le jeu
        sans_portee = {k: v for k, v in CASPIAN.items() if k != "MaxJumpRange"}
        with mock.patch.object(spansh, "route_neutron", return_value=route) as appel:
            await self.s.tracer({"route": "neutron", "destination": "Colonia"}, "Sol", sans_portee)
        self.assertAlmostEqual(appel.call_args.args[2], spansh.portee(spansh.parametres_vaisseau(CASPIAN)))

    async def test_inara_seulement_avec_une_cle(self):
        with mock.patch.object(inara, "profil", side_effect=AssertionError("requête envoyée !")):
            await self.s.inara("Test")
        self.assertIsNone(self.s.etat["inara"])
        self.reglages["inara_cle"] = "CLE"
        with mock.patch.object(inara, "profil", return_value={"commandant": "Test"}) as appel:
            await self.s.inara("Test")
            await self.s.inara("Test")                      # deuxième fois : cache, pas de requête
        self.assertEqual(appel.call_count, 1)
        self.assertEqual(self.s.etat["inara"]["etat"], "ok")


class Demandes(unittest.IsolatedAsyncioTestCase):
    """Une demande venue d'un téléphone sans code est refusée comme une commande."""

    async def test_pin_exige(self):
        from module.interface import serveur_ws
        recues = []

        async def demandes(d):
            recues.append(d)
        anciens = (serveur_ws._demandes, serveur_ws.config.valeur)
        serveur_ws._demandes = demandes
        serveur_ws.config.valeur = lambda s, c: "4821" if c == "pin" else anciens[1](s, c)
        try:
            class Faux:
                def __init__(self):
                    self.recus = []

                async def send(self, m):
                    self.recus.append(json.loads(m))
            telephone, pc = Faux(), Faux()
            serveur_ws._acces[telephone] = {"adresse": "192.168.1.9", "local": False, "autorise": False}
            serveur_ws._acces[pc] = {"adresse": "127.0.0.1", "local": True, "autorise": True}
            await serveur_ws._traiter_message(json.dumps({"demande": {"type": "spansh"}}), telephone)
            await serveur_ws._traiter_message(json.dumps({"demande": {"type": "inara"}}), pc)
            await asyncio.sleep(0)
            self.assertEqual(telephone.recus[0]["type"], "refus")
            self.assertEqual(recues, [{"type": "inara"}])
        finally:
            serveur_ws._demandes, serveur_ws.config.valeur = anciens
            serveur_ws._acces.clear()


if __name__ == "__main__":
    unittest.main()
