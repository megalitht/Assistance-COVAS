"""Sens des ordres (sortir / rentrer) : sans touche, sans micro, sans le vrai macros.py."""
import asyncio
import importlib
import json
import os
import sys
import types
import unittest
from unittest import mock

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from module.pilotage import annonces  # noqa: E402
from module.dialogue import comprehension  # noqa: E402
from module.dialogue.comprehension import intention, ordre_nie, trouver_action  # noqa: E402

with open(os.path.join(RACINE, "data", "barks.json"), encoding="utf-8") as f:
    BARKS = json.load(f)
IGNOREES = {"mots_reveil", "politesse"}

OBJETS = {
    "train_atterrissage": ("le train", "le train d'atterrissage", "les traits d'atterrissage",
                           "les pattes"),
    "soute": ("la soute", "l'écope", "le cargo"),
    "armement": ("les points d'emport", "les armes", "tes armes", "l'armement"),
    "phares": ("les phares", "les lumières"),
    "NVG": ("les NVG", "la vision nocturne"),
    "silencieux": ("le mode silencieux", "le mode furtif"),
}
VERBES = {
    "rentrer": ("rentre", "rentrez", "remballe", "range", "replie", "escamote", "planque", "cache",
                "retire", "enlève", "coupe", "ferme", "éteins", "désactive", "relève", "remonte"),
    "sortir": ("sors", "sortez", "sort", "déploie", "ouvre", "allume", "active", "mets",
               "descends", "baisse", "lance", "réactive"),
}


class Sens(unittest.TestCase):
    def test_tous_les_verbes_sur_toutes_les_macros(self):
        for sens, verbes in VERBES.items():
            for verbe in verbes:
                for cle, objets in OBJETS.items():
                    for objet in objets:
                        phrase = f"covas, {verbe} {objet}"
                        self.assertEqual(intention(phrase), sens, phrase)
                        self.assertEqual(trouver_action(phrase, BARKS, IGNOREES), cle, phrase)

    def test_tournures(self):
        for phrase, sens in (("sors du mode silencieux", "rentrer"),
                             ("rentre en mode silencieux", "sortir"),
                             ("phares off", "rentrer"), ("phares on", "sortir"),
                             ("armes dehors", "sortir"), ("mets les phares hors tension", "rentrer"),
                             ("est-ce que tu peux rentrer le train", "rentrer"),
                             ("n'oublie pas de sortir le train", "sortir"),
                             ("ne sors pas le train, rentre-le", "rentrer"),
                             ("le train", None), ("de sorte que le train", None)):
            self.assertEqual(intention(phrase), sens, phrase)

    def test_negations(self):
        for phrase in ("ne sors pas le train", "n'ouvre pas la soute", "ne les sors pas",
                       "sors pas le train", "ne touche plus aux phares"):
            self.assertTrue(ordre_nie(phrase), phrase)
        for phrase in ("sors le train", "n'oublie pas de sortir le train",
                       "ne sors pas le train, rentre-le", "je n'ai plus de munitions",
                       "il n'y a plus de bouclier", "on n'a pas de train"):
            self.assertFalse(ordre_nie(phrase), phrase)

    def test_energie_et_armes_ne_se_melangent_pas(self):
        for phrase in ("énergie aux armes", "mets tout aux armes", "mets l'énergie sur les armes"):
            self.assertEqual(trouver_action(phrase, BARKS, IGNOREES), "energie_arm", phrase)

    def test_coupe_les_moteurs_ne_les_alimente_pas(self):
        self.assertEqual(trouver_action("coupe les moteurs", BARKS, IGNOREES), "vitesse_zero")

    def test_assistance_de_vol_comprise(self):
        for phrase, sens in (("coupe l'assistance", "rentrer"), ("désactive l'assistance", "rentrer"),
                             ("coupe-moi l'assistance", "rentrer"), ("enlève l'assistance de vol", "rentrer"),
                             ("assistance off", "rentrer"), ("flight assist off", "rentrer"),
                             ("fa off", "rentrer"), ("active l'assistance", "sortir"),
                             ("remets l'assistance", "sortir"), ("réactive l'aide au vol", "sortir"),
                             ("assistance on", "sortir"), ("fa on", "sortir")):
            self.assertEqual(trouver_action(phrase, BARKS, IGNOREES), "assistance_vol", phrase)
            self.assertEqual(intention(phrase), sens, phrase)

    def test_autres_phrases_ne_touchent_pas_l_assistance(self):
        for phrase in ("active l'assistance de supercroisière", "quelle est la distance de vol",
                       "j'ai besoin d'assistance", "lance un appel à l'assistance",
                       "quelle est la résistance du vaisseau", "tu es une bonne assistante",
                       "à quelle distance est la station"):
            self.assertNotEqual(trouver_action(phrase, BARKS, IGNOREES), "assistance_vol", phrase)
        self.assertEqual(trouver_action("coupe l'assistance de conduite", BARKS, IGNOREES),
                         "vrs_assistance")

    def test_chaque_reponse_dit_le_bon_sens(self):
        attendues = {"train_atterrissage": ("manuel_train_sorti", "manuel_train_rentre"),
                     "soute": ("manuel_soute_ouverte", "manuel_soute_fermee"),
                     "armement": ("manuel_armes_sorties", "manuel_armes_rentrees"),
                     "phares": ("manuel_phares_on", "manuel_phares_off"),
                     "NVG": ("manuel_nvg_on", "manuel_nvg_off"),
                     "silencieux": ("manuel_silencieux_on", "manuel_silencieux_off"),
                     "hud": ("manuel_analyse", "manuel_combat")}
        for action, (allume, eteint) in attendues.items():
            self.assertEqual(annonces.replique_ordre(action, "sortir"), allume)
            self.assertEqual(annonces.replique_ordre(action, "rentrer"), eteint)
            self.assertEqual(annonces.replique_ordre(action, None), "affirmation")
            self.assertTrue(BARKS[allume]["reponses"] and BARKS[eteint]["reponses"])
        self.assertEqual(annonces.replique_ordre("boost", "sortir"), "boost")


class Execution(unittest.TestCase):
    """actions.py avec un faux macros.py : aucune touche, le fichier .binds n'est pas ouvert."""
    TRAIN, ARMES, CHARGE, VAISSEAU = 1 << 2, 1 << 6, 1 << 17, 1 << 24
    ASSISTANCE_COUPEE = 1 << 5

    def setUp(self):
        self.appuis, self.dits = [], []
        faux = types.ModuleType("module.pilotage.macros")
        faux.normaliser = lambda n: comprehension.sans_accents(n or "").lower().strip()
        faux.REACTIONS_AU_DEMARRAGE = False
        faux.MACROS = {"reset": [("pips_equilibre", 1)]}
        faux.STOP = mock.Mock()
        faux.touche_connue = lambda nom: True
        faux.nom_touche = lambda nom: nom
        faux.focaliser_jeu = lambda: True
        faux.relacher_tout = lambda: None

        def appuyer(nom, fois=1, duree=None):
            self.appuis.append(nom)
            self.logs.ETAT["status"]["flags"] ^= {"train": self.TRAIN, "armement": self.ARMES,
                                                  "saut": self.CHARGE,
                                                  "assistance_vol": self.ASSISTANCE_COUPEE
                                                  }.get(nom, 0)
            return True
        faux.appuyer = appuyer
        faux.executer_touches = lambda cle: self.appuis.append(cle) or True

        self.logs = types.ModuleType("module.jeu.lecteur_logs")
        self.logs.ETAT = {"status": {"flags": self.VAISSEAU, "flags2": 0}, "vaisseau": {},
                          "modules": {"liste": []}, "cible": {}, "sol": {"vaisseau": {"etat": None}}}
        self.logs.CHEMIN_STATUS = ""
        self.logs.annoncer = mock.AsyncMock()
        ws = types.ModuleType("module.interface.serveur_ws")
        ws.signaler_programme = lambda nom: None
        ecran = types.ModuleType("module.pilotage.ecran")

        self.modules = mock.patch.dict(sys.modules, {
            "module.pilotage.macros": faux, "module.jeu.lecteur_logs": self.logs, "module.interface.serveur_ws": ws,
            "module.pilotage.ecran": ecran})
        self.modules.start()
        sys.modules.pop("module.pilotage.actions", None)
        self.actions = importlib.import_module("module.pilotage.actions")

    def tearDown(self):
        sys.modules.pop("module.pilotage.actions", None)
        self.modules.stop()
        sys.modules.pop("module.pilotage.actions", None)
        for nom in ("pilotage.actions", "pilotage.macros", "jeu.lecteur_logs",
                    "interface.serveur_ws", "pilotage.ecran"):
            groupe, enfant = nom.split(".")
            paquet = sys.modules.get(f"module.{groupe}")
            if paquet and getattr(getattr(paquet, enfant, None), "__file__", None) is None:
                paquet.__dict__.pop(enfant, None)

    def ordre(self, action, phrase):
        async def dire(*cles, poli=False):
            self.dits.append(cles[0])
            return True
        asyncio.run(self.actions.executer_commande(action, phrase, dire))

    def nomade(self):
        self.logs.ETAT["pilotage"] = {"genre": "nomade"}
        self.logs.ETAT["status"]["flags"] = 1 << 26     # le jeu le signale comme un VRS

    def test_nomade_utilise_les_touches_du_vaisseau(self):
        self.nomade()
        self.ordre("train_atterrissage", "sors le train")
        self.ordre("phares", "allume les phares")
        self.assertEqual(self.appuis, ["train", "phares"])

    def test_nomade_amarrage_par_sa_sequence(self):
        self.nomade()
        async def dire(*cles, poli=False):
            self.dits.append(cles[0])
            return True
        with mock.patch.object(self.actions, "fermer_panneaux", mock.AsyncMock(return_value=True)), \
                mock.patch.object(self.actions.reglages, "sequence", return_value=["chasseur_rappel"]):
            asyncio.run(self.actions._amarrage_nomade(dire))
        self.assertEqual(self.appuis, ["chasseur_rappel"])
        self.assertEqual(self.dits, ["apontage"])

    def test_nomade_refuse_le_vaisseau_principal(self):
        self.nomade()
        for action, phrase in (("fsd", "lance le fsd"), ("decollage", "décolle"), ("fuite", "fuis"),
                               ("autopilote_route", "lance le voyage"), ("chasseur", "rappelle le chasseur")):
            self.ordre(action, phrase)
        self.assertEqual(self.appuis, [])
        self.assertEqual(set(self.dits), {"refus_hors_vaisseau"})

    def test_a_pied_depuis_le_nomade_ce_n_est_plus_le_nomade(self):
        self.nomade()
        self.logs.ETAT["status"].update(flags=0, flags2=1)
        self.assertEqual(self.actions.situation(), "pied")

    def test_remballer_armes_rentrees_n_appuie_pas(self):
        self.ordre("armement", "remballe les points d'emport")
        self.assertEqual(self.appuis, [])
        self.assertEqual(self.dits, ["armement_deja_rentre"])

    def test_remballer_armes_sorties(self):
        self.logs.ETAT["status"]["flags"] |= self.ARMES
        self.ordre("armement", "remballe les points d'emport")
        self.assertEqual(self.appuis, ["armement"])
        self.assertEqual(self.dits, ["manuel_armes_rentrees"])

    def test_rentrer_le_train_dit_rentre(self):
        self.logs.ETAT["status"]["flags"] |= self.TRAIN
        self.ordre("train_atterrissage", "rentre le train d'atterrissage")
        self.assertEqual(self.dits, ["manuel_train_rentre"])

    def test_bascule_sans_verbe_dit_le_nouvel_etat(self):
        self.ordre("train_atterrissage", "le train")
        self.assertEqual(self.dits, ["manuel_train_sorti"])

    def test_ordre_negatif_ne_touche_a_rien(self):
        self.ordre("train_atterrissage", "ne sors pas le train")
        self.assertEqual(self.appuis, [])

    def test_couper_le_fsd_sans_charge_ne_le_lance_pas(self):
        self.ordre("fsd", "coupe le fsd")
        self.assertEqual(self.appuis, [])

    def test_couper_le_fsd_en_charge(self):
        self.logs.ETAT["status"]["flags"] |= self.CHARGE
        self.ordre("fsd", "coupe le fsd")
        self.assertEqual(self.appuis, ["saut"])

    def test_relancer_le_fsd_en_charge_ne_l_annule_pas(self):
        self.logs.ETAT["status"]["flags"] |= self.CHARGE
        self.ordre("fsd", "lance le fsd")
        self.assertEqual(self.appuis, [])

    def test_couper_l_autopilote_ne_le_lance_pas(self):
        self.ordre("autopilote_station", "coupe l'autopilote")
        self.assertEqual(self.dits, ["stop_rien"])
        self.assertEqual(self.appuis, [])

    def test_quitter_un_mode_equilibre(self):
        self.ordre("mode_Combat", "quitte le mode combat")
        self.assertEqual(self.appuis, ["reset"])

    def test_couper_l_assistance(self):
        self.ordre("assistance_vol", "coupe l'assistance")
        self.assertEqual(self.appuis, ["assistance_vol"])

    def test_assistance_deja_active(self):
        self.ordre("assistance_vol", "active l'assistance de vol")
        self.assertEqual(self.appuis, [])

    def test_reactiver_l_assistance(self):
        self.logs.ETAT["status"]["flags"] |= self.ASSISTANCE_COUPEE
        self.ordre("assistance_vol", "remets l'assistance de vol")
        self.assertEqual(self.appuis, ["assistance_vol"])

    def test_assistance_deja_coupee(self):
        self.logs.ETAT["status"]["flags"] |= self.ASSISTANCE_COUPEE
        self.ordre("assistance_vol", "désactive l'assistance")
        self.assertEqual(self.appuis, [])

    def test_fermer_une_carte_fermee(self):
        self.ordre("carte_galaxie", "ferme la carte galactique")
        self.assertEqual(self.appuis, [])


if __name__ == "__main__":
    unittest.main()
