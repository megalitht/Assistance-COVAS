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

from module import annonces, comprehension  # noqa: E402
from module.comprehension import intention, ordre_nie, trouver_action  # noqa: E402

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

    def setUp(self):
        self.appuis, self.dits = [], []
        faux = types.ModuleType("module.macros")
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
                                                  "saut": self.CHARGE}.get(nom, 0)
            return True
        faux.appuyer = appuyer
        faux.executer_touches = lambda cle: self.appuis.append(cle) or True

        self.logs = types.ModuleType("module.lecteur_logs")
        self.logs.ETAT = {"status": {"flags": self.VAISSEAU, "flags2": 0}, "vaisseau": {},
                          "modules": {"liste": []}, "cible": {}, "sol": {"vaisseau": {"etat": None}}}
        self.logs.CHEMIN_STATUS = ""
        self.logs.annoncer = mock.AsyncMock()
        ws = types.ModuleType("module.serveur_ws")
        ws.signaler_programme = lambda nom: None
        ecran = types.ModuleType("module.ecran")

        self.modules = mock.patch.dict(sys.modules, {
            "module.macros": faux, "module.lecteur_logs": self.logs, "module.serveur_ws": ws,
            "module.ecran": ecran})
        self.modules.start()
        sys.modules.pop("module.actions", None)
        self.actions = importlib.import_module("module.actions")

    def tearDown(self):
        sys.modules.pop("module.actions", None)
        self.modules.stop()
        sys.modules.pop("module.actions", None)
        paquet = sys.modules["module"]
        for nom in ("actions", "macros", "lecteur_logs", "serveur_ws", "ecran"):
            if getattr(getattr(paquet, nom, None), "__file__", None) is None:
                paquet.__dict__.pop(nom, None)

    def ordre(self, action, phrase):
        async def dire(*cles, poli=False):
            self.dits.append(cles[0])
            return True
        asyncio.run(self.actions.executer_commande(action, phrase, dire))

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

    def test_fermer_une_carte_fermee(self):
        self.ordre("carte_galaxie", "ferme la carte galactique")
        self.assertEqual(self.appuis, [])


if __name__ == "__main__":
    unittest.main()
