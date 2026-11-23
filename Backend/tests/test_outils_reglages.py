"""Outils des onglets de réglages : installation des plans, pont du studio.
Aucun micro, aucune touche, rien n'est écrit hors d'un dossier temporaire."""
import json
import os
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from module.son import ecoute  # noqa: E402
from module.interface import plans  # noqa: E402
from module.studio.pont_studio import PontStudio  # noqa: E402

ENTETE = "window.COVAS_HOLOGRAMMES && window.COVAS_HOLOGRAMMES.enregistrer("


def fichier(identifiant="python_nx", **champs):
    plan = {"id": identifiant, "nom": "Essai", "source": "capture", "largeur": 700.5, "longueur": 1000,
            "coque": "M0 0L10 10z", "traits": "", "details": "", **champs}
    return f"/* Plan d'essai */\n{ENTETE}{json.dumps(plan)});\n"


class Plans(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dossier = self.temp.name

    def tearDown(self):
        self.temp.cleanup()

    def lire(self, *chemin):
        with open(os.path.join(self.dossier, *chemin), encoding="utf-8") as f:
            return f.read()

    def test_nouveau_plan_sans_sauvegarde(self):
        self.assertEqual(plans.installer(self.dossier, "python_nx", fichier()),
                         {"ok": True, "sauvegarde": None})
        self.assertEqual(self.lire("python_nx.js"), fichier())

    def test_ancien_plan_jamais_perdu(self):
        premier, deuxieme, troisieme = (fichier(largeur=l) for l in (100, 200, 300))
        plans.installer(self.dossier, "python_nx", premier)
        a = plans.installer(self.dossier, "python_nx", deuxieme)["sauvegarde"]
        b = plans.installer(self.dossier, "python_nx", troisieme)["sauvegarde"]
        self.assertNotEqual(a, b)
        self.assertEqual(self.lire("anciens", os.path.basename(a)), premier)
        self.assertEqual(self.lire("anciens", os.path.basename(b)), deuxieme)
        self.assertEqual(self.lire("python_nx.js"), troisieme)

    def test_code_refuse(self):
        bon = fichier()
        for mauvais in (bon + "alert(1);\n",
                        "alert(1);\n" + bon,
                        bon.replace("*/\n", "*/ alert(1); /* */\n", 1),
                        bon.replace('{"id"', 'alert(1) || {"id"', 1),
                        f"/* x */\n{ENTETE}" + '{"id":"python_nx"}' + ");alert(1);(" + '{"a":1}' + ");\n",
                        "", None, 3):
            with self.assertRaises(ValueError, msg=repr(mauvais)[:60]):
                plans.verifier("python_nx", mauvais)

    def test_chemin_et_contenu_refuses(self):
        for identifiant in ("../evil", "a/b", "A", "", None, "x" * 41):
            with self.assertRaises(ValueError):
                plans.installer(self.dossier, identifiant, fichier())
        for champs in ({"longueur": 900}, {"coque": "x"}, {"largeur": True}, {"largeur": 0}, {"traits": 3}):
            with self.assertRaises(ValueError, msg=champs):
                plans.verifier("python_nx", fichier(**champs))
        with self.assertRaises(ValueError):
            plans.verifier("anaconda", fichier("python_nx"))
        self.assertEqual(os.listdir(self.dossier), [])


FAUX_STUDIO = r"""
import json, os, sys, threading, time
def repondre(d):
    if d["nom"] == "lent":
        time.sleep(0.25)
    if d["nom"] == "plante":
        os._exit(3)
    r = {"id": d["id"], "erreur": "inconnu"} if d["nom"] == "mauvais" else {"id": d["id"], "resultat": {"nom": d["nom"], "args": d["args"]}}
    with verrou:
        sys.stdout.write(json.dumps(r) + "\n"); sys.stdout.flush()
verrou = threading.Lock()
print("bruit qui n'est pas du JSON", flush=True)
for ligne in sys.stdin:
    threading.Thread(target=repondre, args=(json.loads(ligne),), daemon=True).start()
"""


class Pont(unittest.TestCase):
    def setUp(self):
        self.pont = PontStudio([sys.executable, "-c", FAUX_STUDIO])
        self.pont.demarrer()

    def tearDown(self):
        self.pont.arreter()
        ecoute.PAUSE.clear()

    def test_aller_retour(self):
        self.assertEqual(self.pont.appeler("ecouter", ["covas", None]),
                         {"nom": "ecouter", "args": ["covas", None]})
        self.assertEqual(self.pont.appeler("mauvais"), {"erreur": "inconnu"})

    def test_appels_simultanes_sans_melange(self):
        resultats = {}
        def appel(i):
            resultats[i] = self.pont.appeler("lent" if i % 2 else "vite", [i])
        fils = [threading.Thread(target=appel, args=(i,)) for i in range(12)]
        for f in fils:
            f.start()
        for f in fils:
            f.join()
        for i in range(12):
            self.assertEqual(resultats[i]["args"], [i])

    def test_studio_qui_plante(self):
        self.assertIn("erreur", self.pont.appeler("plante"))
        self.pont._processus.wait(5)
        self.assertFalse(self.pont.actif)
        self.assertIn("erreur", self.pont.appeler("niveau"))
        self.pont.demarrer()
        self.assertEqual(self.pont.appeler("niveau")["nom"], "niveau")

    def test_arret(self):
        processus = self.pont._processus
        self.pont.arreter()
        self.assertIsNotNone(processus.poll())
        self.assertIn("erreur", self.pont.appeler("niveau"))


if __name__ == "__main__":
    unittest.main()
