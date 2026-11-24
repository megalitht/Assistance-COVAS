"""Second écran : réseau local seulement, origine des pages, PIN des commandes, pages servies.
Sans touche, sans micro et sans macros.py ; le serveur écoute seulement ce PC (pas de pare-feu)."""
import asyncio
import json
import os
import sys
import tempfile
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import websockets  # noqa: E402

from module import config  # noqa: E402
from module.interface import second_ecran as se  # noqa: E402
from module.interface import serveur_ws  # noqa: E402

for _flux in (sys.stdout, sys.stderr):                  # comme interface/terminal.py
    if hasattr(_flux, "reconfigure"):
        _flux.reconfigure(errors="replace")


class Reseau(unittest.TestCase):
    def test_reseau_local(self):
        for adresse in ("192.168.1.5", "10.0.0.2", "172.16.3.4", "127.0.0.1", "::1",
                        "::ffff:192.168.1.5", "fe80::1%12", "169.254.10.1"):
            self.assertTrue(se.est_reseau_local(adresse), adresse)
        for adresse in ("8.8.8.8", "2001:4860::1", "::ffff:8.8.8.8", "", None, "pas une adresse", "0.0.0.0"):
            self.assertFalse(se.est_reseau_local(adresse), adresse)

    def test_ce_pc(self):
        self.assertTrue(se.est_ce_pc("127.0.0.1"))
        self.assertTrue(se.est_ce_pc("::1"))
        self.assertTrue(se.est_ce_pc("::ffff:127.0.0.1"))
        self.assertFalse(se.est_ce_pc("192.168.1.5"))

    def test_adresses_locales_sans_loopback(self):
        for adresse in se.adresses_locales():
            self.assertTrue(se.est_reseau_local(adresse))
            self.assertFalse(se.est_ce_pc(adresse))
        self.assertTrue(all(u.startswith("http://") and u.endswith(":8765/") for u in se.adresses_page(8765)))

    def test_hote_sans_nom_de_domaine(self):
        for hote in ("192.168.1.5:8765", "localhost:8765", "[::1]:8765", "127.0.0.1", "LOCALHOST"):
            self.assertTrue(se.hote_autorise(hote), hote)
        for hote in ("evil.com:8765", "", None, "covas.local", "192.168.1.5.nip.io:8765"):
            self.assertFalse(se.hote_autorise(hote), hote)

    def test_origine(self):
        self.assertTrue(se.origine_autorisee(None, "127.0.0.1:8765"))
        self.assertTrue(se.origine_autorisee("null", "127.0.0.1:8765"))                  # page en fichier
        self.assertTrue(se.origine_autorisee("http://127.0.0.1:8766", "localhost:8765"))  # application
        self.assertTrue(se.origine_autorisee("http://192.168.1.5:8765", "192.168.1.5:8765"))  # téléphone
        self.assertFalse(se.origine_autorisee("http://192.168.1.5:8765", "192.168.1.9:8765"))
        self.assertFalse(se.origine_autorisee("https://evil.com", "127.0.0.1:8765"))
        self.assertFalse(se.origine_autorisee("http://evil.com:8765", "evil.com:8765"))  # rebinding


class Pin(unittest.TestCase):
    def setUp(self):
        self.temps = [0.0]
        self.garde = se.GardePin(horloge=lambda: self.temps[0])

    def test_sans_pin_regle_tout_est_refuse(self):
        self.assertEqual(self.garde.verifier("192.168.1.5", "", ""), "absent")
        self.assertEqual(self.garde.verifier("192.168.1.5", "1234", ""), "absent")

    def test_bon_code(self):
        self.assertEqual(self.garde.verifier("a", " 4821 ", "4821"), "ok")
        self.assertEqual(self.garde.verifier("a", 4821, "4821"), "faux")      # jamais autre chose qu'un texte

    def test_blocage_apres_trop_d_erreurs(self):
        for _ in range(4):
            self.assertEqual(self.garde.verifier("a", "0000", "4821", tentatives=5, blocage=300), "faux")
        self.assertEqual(self.garde.verifier("a", "0000", "4821", tentatives=5, blocage=300), "bloque")
        self.assertEqual(self.garde.verifier("a", "4821", "4821"), "bloque")     # même le bon code
        self.assertEqual(self.garde.verifier("b", "4821", "4821"), "ok")         # un autre appareil
        self.temps[0] = 301
        self.assertEqual(self.garde.verifier("a", "4821", "4821"), "ok")

    def test_le_bon_code_efface_les_erreurs(self):
        for _ in range(4):
            self.garde.verifier("a", "0000", "4821")
        self.garde.verifier("a", "4821", "4821")
        self.assertEqual(self.garde.verifier("a", "0000", "4821"), "faux")

    def test_pin_sans_guillemets_dans_la_config(self):
        dossier = tempfile.TemporaryDirectory()
        ancien = config.CHEMIN
        try:
            config.CHEMIN = os.path.join(dossier.name, "config.toml")
            with open(config.CHEMIN, "w", encoding="utf-8") as f:
                f.write("[second_ecran]\npin = 4821\n")
            config.recharger()
            self.assertEqual(config.valeur("second_ecran", "pin"), "4821")
        finally:
            config.CHEMIN = ancien
            config.recharger()
            dossier.cleanup()


class Pages(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        racine = self.racine = self.dossier.name
        os.makedirs(os.path.join(racine, "vaisseaux"))
        for nom in ("interface.html", "interface.css", "vaisseaux/anaconda.js", "secret.py", ".cache.js"):
            with open(os.path.join(racine, *nom.split("/")), "w", encoding="utf-8") as f:
                f.write("x")

    def tearDown(self):
        self.dossier.cleanup()

    def chemin(self, url):
        trouve = se.fichier_demande(url, self.racine)
        return os.path.relpath(trouve, self.racine).replace("\\", "/") if trouve else None

    def test_pages_autorisees(self):
        self.assertEqual(self.chemin("/"), "interface.html")
        self.assertEqual(self.chemin("/interface.css?v=2"), "interface.css")
        self.assertEqual(self.chemin("/vaisseaux/anaconda.js"), "vaisseaux/anaconda.js")

    def test_rien_hors_de_frontend(self):
        for url in ("/../secret.py", "/secret.py", "/%2e%2e/x.js", "/..%2f..%2fwindows/win.ini",
                    "/vaisseaux/../../x.js", "/.cache.js", "/%5c..%5cx.js", "/inexistant.js", "/vaisseaux"):
            self.assertIsNone(self.chemin(url), url)

    def test_vraies_pages(self):
        self.assertTrue(se.fichier_demande("/").endswith("interface.html"))
        self.assertTrue(se.fichier_demande("/second_ecran.js"))
        type_contenu, contenu = se.lire_fichier(se.fichier_demande("/interface.css"))
        self.assertTrue(type_contenu.startswith("text/css") and contenu)

    def test_qr_code(self):
        svg = se.qr_svg("http://192.168.1.23:8765/")
        self.assertTrue(svg.startswith("<svg") and "#070403" in svg)


class FauxWebsocket:
    def __init__(self, adresse):
        self.remote_address = (adresse, 50000)
        self.recus = []

    async def send(self, message):
        self.recus.append(json.loads(message))


class Commandes(unittest.IsolatedAsyncioTestCase):
    """Le PIN est exigé hors de ce PC pour les boutons, les phrases écrites et les réglages."""

    def setUp(self):
        self.file = asyncio.Queue()
        self.anciens = (serveur_ws._file_actions, serveur_ws._questions, config.section, config.valeur)
        self.reglage = {"actif": True, "port": 8765, "pin": "4821", "tentatives": 5, "blocage_minutes": 5}
        config.section = lambda nom: dict(self.reglage) if nom == "second_ecran" else self.anciens[2](nom)
        config.valeur = lambda nom, cle: self.reglage[cle] if nom == "second_ecran" else self.anciens[3](nom, cle)
        serveur_ws._file_actions = self.file
        serveur_ws._garde = se.GardePin()
        self.questions = []

        async def question(texte):
            self.questions.append(texte)

        serveur_ws._questions = question

    def tearDown(self):
        serveur_ws._file_actions, serveur_ws._questions, config.section, config.valeur = self.anciens
        serveur_ws._acces.clear()

    def appareil(self, adresse):
        ws = FauxWebsocket(adresse)
        local = se.est_ce_pc(adresse)
        serveur_ws._acces[ws] = {"adresse": adresse, "local": local, "autorise": local}
        return ws

    async def envoyer(self, ws, **donnees):
        await serveur_ws._traiter_message(json.dumps(donnees), ws)
        await asyncio.sleep(0)

    async def test_telephone_sans_code_refuse(self):
        telephone = self.appareil("192.168.1.40")
        await self.envoyer(telephone, action="train_atterrissage")
        await self.envoyer(telephone, question="sors le train")
        await self.envoyer(telephone, reglages={})
        self.assertTrue(self.file.empty())
        self.assertEqual(self.questions, [])
        self.assertEqual([m["type"] for m in telephone.recus], ["refus"] * 3)

    async def test_telephone_avec_le_bon_code(self):
        telephone = self.appareil("192.168.1.40")
        await self.envoyer(telephone, pin="0000")
        self.assertEqual(telephone.recus[-1]["resultat"], "faux")
        await self.envoyer(telephone, action="phares")
        self.assertTrue(self.file.empty())
        await self.envoyer(telephone, pin="4821")
        self.assertEqual(telephone.recus[-1]["resultat"], "ok")
        await self.envoyer(telephone, action="phares")
        self.assertEqual(self.file.get_nowait(), "phares")

    async def test_ce_pc_sans_code(self):
        pc = self.appareil("127.0.0.1")
        await self.envoyer(pc, action="phares")
        self.assertEqual(self.file.get_nowait(), "phares")

    async def test_sans_pin_regle(self):
        self.reglage["pin"] = ""
        telephone = self.appareil("192.168.1.40")
        await self.envoyer(telephone, pin="")
        self.assertEqual(telephone.recus[-1]["resultat"], "absent")
        await self.envoyer(telephone, action="phares")
        self.assertTrue(self.file.empty())

    async def test_blocage(self):
        telephone = self.appareil("192.168.1.40")
        for _ in range(5):
            await self.envoyer(telephone, pin="0000")
        self.assertEqual(telephone.recus[-1]["resultat"], "bloque")
        self.assertGreater(telephone.recus[-1]["attente"], 200)
        await self.envoyer(telephone, pin="4821")
        self.assertEqual(telephone.recus[-1]["resultat"], "bloque")


class Serveur(unittest.IsolatedAsyncioTestCase):
    """Le vrai serveur, sur ce PC seulement (second écran coupé : aucune carte réseau ouverte)."""

    async def asyncSetUp(self):
        self.anciens = (config.valeur, serveur_ws._instantane)
        reglage = {"actif": False, "port": 18799, "pin": "4821", "tentatives": 5, "blocage_minutes": 5}
        config.valeur = lambda nom, cle: reglage[cle] if nom == "second_ecran" else self.anciens[0](nom, cle)
        serveur_ws._instantane = None
        self.tache = asyncio.create_task(serveur_ws.demarrer_serveur_web(asyncio.Queue()))
        await asyncio.sleep(0.4)

    async def asyncTearDown(self):
        self.tache.cancel()
        await asyncio.gather(self.tache, return_exceptions=True)
        config.valeur, serveur_ws._instantane = self.anciens

    def get(self, chemin, hote="127.0.0.1:18799"):
        requete = urllib.request.Request("http://127.0.0.1:18799" + chemin, headers={"Host": hote})
        try:
            with urllib.request.urlopen(requete, timeout=3) as reponse:
                return reponse.status, reponse.headers.get("Content-Type"), reponse.read()
        except urllib.error.HTTPError as erreur:
            return erreur.code, None, erreur.read()

    async def test_pages_et_refus(self):
        statut, type_contenu, contenu = await asyncio.to_thread(self.get, "/")
        self.assertEqual((statut, type_contenu), (200, "text/html; charset=utf-8"))
        self.assertIn(b"second_ecran.js", contenu)
        self.assertEqual((await asyncio.to_thread(self.get, "/../Backend/main.py"))[0], 404)
        self.assertEqual((await asyncio.to_thread(self.get, "/", "evil.example:18799"))[0], 403)

    async def test_liaison_du_pc(self):
        async with websockets.connect("ws://127.0.0.1:18799", origin="http://127.0.0.1:8766") as ws:
            acces = json.loads(await ws.recv())
            self.assertEqual(acces, {"type": "acces", "local": True, "autorise": True, "pin_regle": True})
            types = [json.loads(await ws.recv())["type"] for _ in range(3)]
            self.assertEqual(types, ["reglages", "programme", "second_ecran"])
            self.assertEqual(serveur_ws.interfaces_locales_ouvertes(), 1)

    async def test_site_exterieur_refuse(self):
        with self.assertRaises(websockets.exceptions.InvalidStatus):
            async with websockets.connect("ws://127.0.0.1:18799", origin="https://evil.example"):
                pass


if __name__ == "__main__":
    unittest.main()
