"""Carburant : consommation, sauts possibles, alertes de seuil et de route, fichier de configuration.
Sans touche, sans micro, sans réseau et sans macros.py : le journal est simulé."""
import asyncio
import importlib.util
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from module import config  # noqa: E402
from module.jeu import carburant  # noqa: E402
from module.jeu.carburant import Reservoir, conso_max_fsd  # noqa: E402

DOSSIER_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Comme le COVAS (interface/terminal.py) : un caractère que la console ne sait pas écrire (≈)
# ne doit pas interrompre une alerte.
for _flux in (sys.stdout, sys.stderr):
    if hasattr(_flux, "reconfigure"):
        _flux.reconfigure(errors="replace")
REGLAGES = {"seuil_bas": 25, "seuil_critique": 10, "rearmement": 3, "sauts_moyenne": 10,
            "secours_par_saut": 5.0, "marge_route": 1.1}


def loadout(ship_id=1, capacite=32.0, fsd="int_hyperdrive_overcharge_size5_class5", collecteur=True,
            ingenierie=None):
    modules = [{"Slot": "FrameShiftDrive", "Item": fsd, "On": True, "Health": 1.0}]
    if ingenierie:
        modules[0]["Engineering"] = ingenierie
    if collecteur:
        modules.append({"Slot": "Slot03_Size5", "Item": "int_fuelscoop_size5_class5", "On": True})
    return {"event": "Loadout", "Ship": "python", "ShipID": ship_id,
            "FuelCapacity": {"Main": capacite, "Reserve": 0.83}, "Modules": modules}


def etapes(*classes):
    """Étapes à venir, une par classe d'étoile (M est récupérable ; L, T, D, N ne le sont pas)."""
    return [{"systeme": f"S{i}", "classe": c, "ravitaillable": c[0] in "KGBFOAM"}
            for i, c in enumerate(classes, 1)]


class TableFSD(unittest.TestCase):
    def test_fsd_classiques_et_sco(self):
        self.assertEqual(conso_max_fsd("int_hyperdrive_size5_class5"), 5.0)
        self.assertEqual(conso_max_fsd("int_hyperdrive_size3_class1"), 1.2)
        self.assertEqual(conso_max_fsd("int_hyperdrive_overcharge_size5_class5"), 5.2)
        self.assertEqual(conso_max_fsd("int_hyperdrive_overcharge_size8_class1"), 13.6)
        self.assertEqual(conso_max_fsd("Int_Hyperdrive_Size7_Class4"), 10.6)    # majuscules

    def test_fsd_mk2_du_caspian(self):
        self.assertEqual(conso_max_fsd("int_hyperdrive_overcharge_size8_class5_overchargebooster_mkii"), 6.8)

    def test_ingenierie_passe_devant_la_table(self):
        ing = {"Modifiers": [{"Label": "Mass", "Value": 10}, {"Label": "MaxFuelPerJump", "Value": 5.5}]}
        self.assertEqual(conso_max_fsd("int_hyperdrive_size5_class5", ing), 5.5)

    def test_inconnu(self):
        self.assertIsNone(conso_max_fsd("int_fuelscoop_size5_class5"))
        self.assertIsNone(conso_max_fsd(None))
        self.assertIsNone(conso_max_fsd("int_hyperdrive_size9_class5"))


class Consommation(unittest.TestCase):
    def test_sources_dans_l_ordre(self):
        r = Reservoir()
        self.assertEqual(r.conso(secours=5.0), (5.0, "config"))
        self.assertEqual(r.conso(), (None, None))
        r.equipement(loadout())
        self.assertEqual(r.conso(), (5.2, "fsd"))                 # sans historique : le pire cas
        for consomme in (2.0, 3.0, 4.0):
            r.saut({"FuelUsed": consomme, "FuelLevel": 20.0})
        self.assertEqual(r.conso(), (3.0, "historique"))
        self.assertEqual(r.conso(nombre=2), (3.5, "historique"))  # seulement les 2 derniers
        self.assertEqual(r.niveau, 20.0)

    def test_historique_par_vaisseau(self):
        r = Reservoir()
        r.equipement(loadout(ship_id=1))
        r.saut({"FuelUsed": 2.0})
        r.equipement(loadout(ship_id=2, fsd="int_hyperdrive_size3_class5"))
        self.assertEqual(r.conso(), (1.8, "fsd"))
        r.equipement(loadout(ship_id=1))
        self.assertEqual(r.conso(), (2.0, "historique"))

    def test_collecteur_eteint_ne_compte_pas(self):
        r = Reservoir()
        e = loadout()
        e["Modules"][1]["On"] = False
        r.equipement(e)
        self.assertFalse(r.collecteur)

    def test_vue(self):
        r = Reservoir()
        r.equipement(loadout())
        r.saut({"FuelUsed": 2.5})
        r.mesurer(10.0)
        v = r.vue(etapes("L", "K", "L"), REGLAGES)
        self.assertEqual(v["sauts"], 4)
        self.assertEqual(v["etat"], "ok")
        self.assertAlmostEqual(v["part"], 10 / 32, places=3)
        self.assertEqual(v["route"], {"cible": "etoile", "sauts": 2, "besoin": 5.0, "suffisant": True})
        r.mesurer(2.0)
        self.assertEqual(r.vue([], REGLAGES)["etat"], "critique")


class Seuils(unittest.TestCase):
    def setUp(self):
        self.r = Reservoir()
        self.r.equipement(loadout(capacite=100.0))

    def niveau(self, t, route=()):
        self.r.mesurer(t)
        return self.r.controler(list(route), REGLAGES)

    def test_premier_releve_muet(self):
        self.assertEqual(self.niveau(5), [])           # démarrage déjà sous les seuils : silence
        self.assertEqual(self.niveau(4), [])           # et pas d'alerte ensuite pour les mêmes seuils

    def test_une_fois_par_seuil(self):
        self.niveau(50)
        self.assertEqual(self.niveau(24), ["bas"])
        self.assertEqual(self.niveau(23), [])
        self.assertEqual(self.niveau(26), [])          # pas encore réarmé (25 + 3)
        self.assertEqual(self.niveau(24), [])
        self.assertEqual(self.niveau(9), ["critique"])
        self.assertEqual(self.niveau(8), [])

    def test_rearmement_apres_le_plein(self):
        self.niveau(50)
        self.niveau(24)
        self.niveau(30)                                # écopé au-dessus de 28 %
        self.assertEqual(self.niveau(24), ["bas"])

    def test_deux_seuils_d_un_coup_annonce_le_plus_grave(self):
        self.niveau(50)
        self.assertEqual(self.niveau(5), ["critique"])
        self.assertEqual(self.niveau(30), [])
        self.assertEqual(self.niveau(20), ["bas"])     # le seuil bas a été réarmé à 30 %

    def test_releve_muet_pendant_la_relecture(self):
        self.niveau(50)
        self.r.mesurer(20)
        self.assertEqual(self.r.controler([], REGLAGES, parler=False), [])
        self.assertEqual(self.niveau(19), [])          # déjà compté comme dit

    def test_changement_de_vaisseau_repart_muet(self):
        self.niveau(50)
        self.r.equipement(loadout(ship_id=7, capacite=100.0))
        self.assertEqual(self.niveau(5), [])

    def test_seuils_reglables(self):
        reglages = dict(REGLAGES, seuil_bas=50)
        self.r.mesurer(60)
        self.r.controler([], reglages)
        self.r.mesurer(45)
        self.assertEqual(self.r.controler([], reglages), ["bas"])


class Route(unittest.TestCase):
    def setUp(self):
        self.r = Reservoir()
        self.r.equipement(loadout(capacite=100.0, collecteur=False))
        for _ in range(3):
            self.r.saut({"FuelUsed": 5.0})          # 5 t par saut

    def controle(self, t, route):
        self.r.mesurer(t)
        return self.r.controler(route, REGLAGES)

    def test_route_trop_longue_prioritaire(self):
        self.controle(60, [])
        # 12 sauts × 5 t × 1,1 = 66 t > 20 t, et le seuil bas est franchi en même temps
        self.assertEqual(self.controle(20, etapes(*"L" * 12)), ["route"])
        self.assertEqual(self.controle(19, etapes(*"L" * 12)), [])       # une seule fois
        self.assertTrue(self.r.dites["bas"])                              # le seuil ne reparlera pas

    def test_route_suffisante_puis_insuffisante(self):
        self.controle(80, [])
        self.assertEqual(self.controle(80, etapes(*"L" * 10)), [])       # 55 t nécessaires
        self.assertEqual(self.controle(50, etapes(*"L" * 10)), ["route"])
        self.assertEqual(self.controle(90, etapes(*"L" * 10)), [])       # ravitaillé : réarmé
        self.assertEqual(self.controle(50, etapes(*"L" * 10)), ["route"])

    def test_nouvelle_destination(self):
        self.controle(80, [])
        self.assertEqual(self.controle(50, etapes(*"L" * 10)), ["route"])
        autre = etapes(*"L" * 11)
        autre[-1]["systeme"] = "Ailleurs"
        self.assertEqual(self.controle(50, autre), ["route"])

    def test_avec_collecteur_la_prochaine_etoile_suffit(self):
        self.r.collecteur = True
        self.controle(80, [])
        route = etapes("L", "T", "K", *"L" * 20)               # étoile K au 3e saut
        self.assertEqual(self.controle(30, route), [])         # 3 × 5 × 1,1 = 16,5 t
        self.assertEqual(self.controle(15, route), ["etoile"])

    def test_avec_collecteur_sans_etoile_sur_la_route(self):
        self.r.collecteur = True
        self.controle(80, [])
        self.assertEqual(self.controle(50, etapes(*"N" * 10)), ["route"])

    def test_destination_seule_etoile_recuperable(self):
        self.r.collecteur = True
        besoin = self.r.besoin_route(etapes("L", "D", "G"), 5.0)
        self.assertEqual(besoin, {"cible": "destination", "sauts": 3, "besoin": 15.0})


class Configuration(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.ancien = config.CHEMIN
        config.CHEMIN = os.path.join(self.dossier.name, "config.toml")
        config.recharger()

    def tearDown(self):
        config.CHEMIN = self.ancien
        config.recharger()
        self.dossier.cleanup()

    def ecrire(self, texte):
        with open(config.CHEMIN, "w", encoding="utf-8") as f:
            f.write(texte)
        config.recharger()

    def test_sans_fichier_valeurs_par_defaut(self):
        self.assertEqual(config.valeur("carburant", "seuil_bas"), 25)
        self.assertFalse(os.path.exists(config.CHEMIN))         # la lecture n'écrit jamais

    def test_preparer_cree_un_fichier_lisible(self):
        self.assertEqual(config.preparer(), list(config.SECTIONS))
        self.assertEqual(config.section("carburant"), config.DEFAUTS["carburant"])
        with open(config.CHEMIN, encoding="utf-8") as f:
            self.assertIn("seuil_bas = 25", f.read())
        self.assertEqual(config.preparer(), [])                  # rien à ajouter la 2e fois

    def test_valeur_modifiee_et_valeur_invalide(self):
        self.ecrire('[carburant]\nseuil_bas = 30\nseuil_critique = "dix"\nmarge_route = 1\ninconnu = 3\n')
        self.assertEqual(config.valeur("carburant", "seuil_bas"), 30)
        self.assertEqual(config.valeur("carburant", "seuil_critique"), 10)   # invalide : défaut
        self.assertIsInstance(config.valeur("carburant", "marge_route"), float)

    def test_section_manquante_ajoutee_sans_toucher_au_reste(self):
        self.ecrire("# mon commentaire\n[autre]\nx = 1\n")
        self.assertEqual(config.preparer(), list(config.SECTIONS))
        with open(config.CHEMIN, encoding="utf-8") as f:
            texte = f.read()
        self.assertTrue(texte.startswith("# mon commentaire\n[autre]\nx = 1\n"))
        self.assertIn("[carburant]", texte)

    def test_fichier_illisible_garde_les_reglages(self):
        self.ecrire("[carburant]\nseuil_bas = 40\n")
        self.assertEqual(config.valeur("carburant", "seuil_bas"), 40)
        with open(config.CHEMIN, "w", encoding="utf-8") as f:
            f.write("[carburant\nseuil_bas = \n")
        os.utime(config.CHEMIN, (1, 1))                          # date différente : relu
        config._etat["verifie"] = 0.0
        self.assertEqual(config.valeur("carburant", "seuil_bas"), 40)
        self.assertEqual(config.preparer(), [])                  # illisible : on n'y écrit rien


def _lecteur_prive():
    """Copie du lecteur de journal propre à ce fichier (voir test_chasse_exploration.py)."""
    avant = set(sys.modules)
    chemin = os.path.join(DOSSIER_BACKEND, "module", "jeu", "lecteur_logs.py")
    spec = importlib.util.spec_from_file_location("covas_lecteur_logs_carburant", chemin)
    copie = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copie)
    for nom in ("module.interface.serveur_ws", "module.jeu.edsm"):
        if nom in sys.modules and nom not in avant:
            del sys.modules[nom]
            paquet, _, enfant = nom.rpartition(".")
            delattr(sys.modules[paquet], enfant)
    return copie


_copie = []


def _lecteur():
    if not _copie:
        _copie.append(_lecteur_prive())
    return _copie[0]


class Journal(unittest.IsolatedAsyncioTestCase):
    """Le vrai lecteur de journal : Loadout, sauts, route et relevés de Status.json."""

    logs = None

    @classmethod
    def setUpClass(cls):
        cls.logs = _lecteur()

    def setUp(self):
        logs = self.logs
        self.dit, self.envoye = [], []
        self.origines = (logs.envoyer_donnees_web, logs._dire, logs.SYSTEMES_PROCHES_ACTIF)

        async def envoyer(message):
            self.envoye.append(message)

        async def dire(cle, urgent=False, secours=None):
            self.dit.append((cle, urgent))

        logs.envoyer_donnees_web, logs._dire, logs.SYSTEMES_PROCHES_ACTIF = envoyer, dire, False
        logs._reservoir = Reservoir()
        logs._reinitialiser_etat()
        logs._suivi["en_direct"] = True

    def tearDown(self):
        logs = self.logs
        logs.envoyer_donnees_web, logs._dire, logs.SYSTEMES_PROCHES_ACTIF = self.origines
        logs._reinitialiser_etat()
        logs._suivi["en_direct"] = False

    async def ev(self, nom, **champs):
        await self.logs._traiter_ligne(json.dumps({"timestamp": "2026-11-24T20:00:00Z", "event": nom, **champs}),
                                       en_direct=True)

    async def releve(self, t):
        self.logs._reservoir.mesurer(t)
        await self.logs._controler_carburant()

    async def test_saut_puis_seuils(self):
        await self.ev("Loadout", **{k: v for k, v in loadout(capacite=40.0).items() if k != "event"})
        await self.ev("FSDJump", StarSystem="Sol", SystemAddress=1, StarPos=[0, 0, 0], JumpDist=10.0,
                      FuelUsed=4.0, FuelLevel=30.0)
        c = self.logs.ETAT["carburant"]
        self.assertEqual((c["conso"], c["source"], c["sauts"]), (4.0, "historique", 7))
        self.assertTrue(any(m.get("section") == "carburant" for m in self.envoye))
        await self.releve(30.0)
        self.assertEqual(self.dit, [])
        await self.releve(9.0)                            # 22,5 % : seuil bas
        await self.releve(3.0)                            # 7,5 % : seuil critique
        self.assertEqual(self.dit, [("alerte_carburant", False), ("alerte_carburant_critique", False)])
        lignes = [m["evenement"]["texte"] for m in self.envoye if m.get("type") == "evenement"]
        self.assertTrue(any(t.startswith("Carburant critique") for t in lignes))

    async def test_route_insuffisante_urgente(self):
        await self.ev("Loadout", **{k: v for k, v in loadout(capacite=40.0, collecteur=False).items()
                                    if k != "event"})
        await self.ev("Location", StarSystem="S0", SystemAddress=1, StarPos=[0, 0, 0])
        await self.releve(30.0)
        self.logs._maj_route({"Route": [{"StarSystem": f"S{i}", "StarPos": [i * 10, 0, 0], "StarClass": "L"}
                                        for i in range(8)]})
        await self.logs._controler_carburant()           # 7 sauts × 5,2 t (FSD) × 1,1 > 30 t
        self.assertEqual(self.dit, [("alerte_carburant_route", True)])
        self.assertFalse(self.logs.ETAT["carburant"]["route"]["suffisant"])


class FileVocale(unittest.IsolatedAsyncioTestCase):
    async def test_annonce_urgente_en_tete(self):
        logs = _lecteur()
        file = asyncio.Queue()
        await file.put("a")
        await file.put("b")
        logs._devant(file, "urgent")
        self.assertEqual([file.get_nowait() for _ in range(3)], ["urgent", "a", "b"])
        for _ in range(3):
            file.task_done()                              # les compteurs restent justes
        await asyncio.wait_for(file.join(), 1)


class SurLesVraisJournaux(unittest.TestCase):
    """La table des FSD ne doit jamais être dépassée par une consommation réelle (journaux du
    commandant, lecture seule). Ignoré si le dossier du jeu est absent."""

    def test_aucun_saut_ne_depasse_le_maximum_du_fsd(self):
        dossier = os.path.join(os.path.expanduser("~"), "Saved Games", "Frontier Developments", "Elite Dangerous")
        if not os.path.isdir(dossier):
            self.skipTest("journaux du jeu absents")
        r, verifies, depassements = Reservoir(), 0, []
        for nom in sorted(os.listdir(dossier)):
            if not nom.startswith("Journal."):
                continue
            with open(os.path.join(dossier, nom), encoding="utf-8", errors="replace") as f:
                for ligne in f:
                    if '"Loadout"' not in ligne and '"FSDJump"' not in ligne:
                        continue
                    try:
                        e = json.loads(ligne)
                    except ValueError:
                        continue
                    if e.get("event") == "Loadout":
                        r.equipement(e)
                    elif e.get("event") == "FSDJump" and r.fsd_max and e.get("FuelUsed"):
                        verifies += 1
                        if e["FuelUsed"] > r.fsd_max + 0.01:
                            depassements.append((nom, e["FuelUsed"], r.fsd_max))
        self.assertEqual(depassements, [], f"{len(depassements)} sauts sur {verifies}")


if __name__ == "__main__":
    unittest.main()
