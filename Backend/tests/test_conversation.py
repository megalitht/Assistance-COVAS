"""
Tests des conversations du COVAS (module/conversation.py + data/conversations.json).

Lancer depuis Backend/ :
    ..\\.venv\\Scripts\\python.exe -m unittest discover -s tests -v

Aucun micro, aucune touche, aucun accès au jeu : module/macros.py et module/actions.py ne
sont JAMAIS importés (leur import peut réécrire le fichier de touches d'Elite).
"""
import asyncio
import json
import os
import sys
import time
import unittest
from datetime import datetime
from unittest import mock

DOSSIER_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, DOSSIER_BACKEND)

from module import comprehension, conversation  # noqa: E402

with open(os.path.join(DOSSIER_BACKEND, "data", "barks.json"), encoding="utf-8") as _f:
    BARKS = json.load(_f)
IGNOREES = {"mots_reveil", "politesse"}

# Bits de Status.json
AMARRE, POSE, BOUCLIERS, SC, DANGER, VAISSEAU = 1 << 0, 1 << 1, 1 << 3, 1 << 4, 1 << 22, 1 << 24


def etat(flags=VAISSEAU | BOUCLIERS, **sections):
    """Un ETAT minimal (même forme que lecteur_logs.ETAT)."""
    base = {"status": {"flags": flags}, "vaisseau": {}, "position": {}, "route": {"etapes": []},
            "modules": {"liste": []}, "soute": {"total": 0, "inventaire": []},
            "cible": {"verrouillee": False}, "combat": {}, "missions": {"liste": []},
            "commandant": {}}
    for nom, valeur in sections.items():
        base[nom] = {**base.get(nom, {}), **valeur}
    return base


def decider(phrase, etat_=None, **options):
    return conversation.decider(phrase, BARKS, IGNOREES, etat_ or etat(), **options)


class Base(unittest.TestCase):
    def setUp(self):
        self.erreurs = conversation.charger(actions=BARKS)
        conversation.annuler_attente()
        conversation._memoire["paroles"].clear()
        conversation._memoire["combat"] = -1e9


class Contenu(Base):
    def test_json_sans_erreur(self):
        self.assertEqual(self.erreurs, [])

    def test_chaque_question_mene_a_son_sujet(self):
        echecs = []
        for cle, sujet in conversation._contenu["sujets"].items():
            for question in sujet.get("questions") or []:
                d = decider(f"Covas, {question}")
                if d.type != "conversation" or d.sujet != cle:
                    echecs.append(f"« {question} » ({cle}) -> {d.type} {d.action or d.sujet}")
        self.assertEqual(echecs, [])

    def test_chaque_mot_cle_de_commande_reste_une_commande(self):
        echecs = []
        for cle, donnees in BARKS.items():
            if cle in IGNOREES:
                continue
            for mot_cle in donnees.get("mots_cles", []):
                d = decider(f"Covas {mot_cle}")
                attendu = comprehension.trouver_action(mot_cle, BARKS, IGNOREES)
                if d.type != "commande" or d.action != attendu:
                    echecs.append(f"« {mot_cle} » -> {d.type} {d.action or d.sujet}")
        self.assertEqual(echecs, [])


class Decisions(Base):
    def test_ordres_courants(self):
        for phrase, action in [
            ("sors le train", "train_atterrissage"), ("ferme la soute", "soute"),
            ("rentre le train merci", "train_atterrissage"),
            ("bonjour, mets les NVG", "NVG"), ("active le fsd tout de suite", "fsd"),
            ("est-ce que tu peux sortir le train", "train_atterrissage"),
            ("qui nous tire dessus", "cible_menace"), ("mode silencieux", "silencieux"),
            ("rapport d'avarie", "rapport_avarie"), ("état du vaisseau", "rapport_avarie"),
            ("fais le plein", "ravitaillement"), ("suis la route", "autopilote_route"),
            ("ouvre la suite", "soute"), ("sors l'armement", "armement"),
        ]:
            with self.subTest(phrase=phrase):
                d = decider(f"Covas {phrase}")
                self.assertEqual((d.type, d.action), ("commande", action))

    def test_mots_cles_en_debut_de_mot(self):
        # « tir » (énergie aux armes) ne doit plus se déclencher dans « sortir »
        self.assertIsNone(comprehension.trouver_action("il faut sortir d'ici", BARKS, IGNOREES))
        self.assertIsNone(comprehension.trouver_action("on va partir", BARKS, IGNOREES))
        self.assertEqual(comprehension.trouver_action("ravitaillement", BARKS, IGNOREES),
                         "ravitaillement")

    def test_une_question_n_est_pas_un_ordre(self):
        for phrase in ("comment sont nos boucliers", "c'est quoi le mode combat",
                       "pourquoi le moteur fait ce bruit"):
            with self.subTest(phrase=phrase):
                self.assertEqual(decider(f"Covas {phrase}").type, "conversation")

    def test_questions(self):
        for phrase, sujet in [
            ("comment va le vaisseau", "etat_vaisseau"), ("comment vont les boucliers", "etat_vaisseau"),
            ("parle-moi des Thargoïdes", "thargoides"), ("tu connais Raxxla", "raxxla"),
            ("c'est quoi la Fédération des pilotes", "pilotes"), ("on a assez de carburant", "carburant"),
            ("raconte moi une blague", "blague"), ("silence radio", "silence_radio"),
            ("comment il va le vaisseau", "etat_vaisseau"),       # approché
        ]:
            with self.subTest(phrase=phrase):
                d = decider(f"Covas, {phrase} ?")
                self.assertEqual((d.type, d.sujet), ("conversation", sujet))

    def test_question_inconnue(self):
        d = decider("Covas, pourquoi le ciel est noir ?")
        self.assertEqual((d.type, d.sujet), ("conversation", "question_inconnue"))
        self.assertEqual(decider("Covas, blablabla").type, "rien")

    def test_sans_mot_de_reveil(self):
        self.assertEqual(decider("comment va le vaisseau", reveil=False).type, "ignore")


class Contextes(Base):
    def test_carburant(self):
        bas = etat(status={"carburant": 5.0}, vaisseau={"carburant_max": 32})
        d = decider("Covas combien de carburant", bas)
        self.assertEqual(d.replique["id"], "CarburantBas")
        texte, detail = conversation.texte_de(d.replique, bas)
        self.assertIn("5,0 t sur 32 t", detail)

        critique = etat(status={"carburant": 1.0}, vaisseau={"carburant_max": 32})
        self.assertEqual(decider("Covas combien de carburant", critique).replique["id"],
                         "CarburantCritique")

    def test_detail_cache_si_valeur_inconnue(self):
        d = decider("Covas combien de carburant", etat())
        self.assertIsNone(conversation.texte_de(d.replique, etat())[1])

    def test_danger_prioritaire(self):
        e = etat(flags=VAISSEAU | DANGER, vaisseau={"coque": 0.3})
        d = decider("Covas comment va le vaisseau", e)
        self.assertEqual(d.replique["id"], "EtatDanger")

    def test_vaisseau_du_commandant(self):
        e = etat(vaisseau={"type": "python_nx"})
        self.assertEqual(decider("Covas tu aimes ce vaisseau", e).replique["id"], "VaisseauPythonMk2")

    def test_heure(self):
        with mock.patch.object(conversation, "_maintenant", lambda: datetime(2026, 11, 19, 7, 30)):
            d = decider("Covas bonjour")
            self.assertIn(d.replique["id"], ("BonjourMatin1", "BonjourMatin2"))
            heure = decider("Covas quelle heure est-il")
            self.assertEqual(conversation.texte_de(heure.replique, etat())[0],
                             "Il est 7 heures 30, commandant.")

    def test_pas_deux_fois_la_meme(self):
        vues = [decider("Covas raconte une blague").replique["id"] for _ in range(6)]
        self.assertTrue(all(a != b for a, b in zip(vues, vues[1:])))


class Suites(Base):
    def jouer(self, replique, e=None):
        dits, commandes = [], []

        async def dire(chemin):
            dits.append(chemin)

        async def afficher(texte, detail):
            dits.append(texte)

        async def commander(c):
            commandes.append(c)

        async def synthetiser(texte):
            return None

        asyncio.run(conversation.jouer(replique, e or etat(), dire=dire, afficher=afficher,
                                       commander=commander, synthetiser=synthetiser))
        return dits, commandes

    def test_oui_lance_le_rapport(self):
        e = etat(vaisseau={"coque": 0.6})
        d = decider("Covas comment va le vaisseau", e)
        self.assertEqual(d.replique["id"], "EtatAbime")
        self.jouer(d.replique, e)
        self.assertTrue(conversation.attend_reponse())
        reponse = decider("oui vas-y", e, reveil=False)
        self.assertEqual(reponse.type, "conversation")
        _, commandes = self.jouer(reponse.replique, e)
        self.assertEqual(commandes, ["rapport_avarie"])
        self.assertFalse(conversation.attend_reponse())

    def test_reponse_sans_rapport_ignoree(self):
        d = decider("Covas comment va le vaisseau", etat(vaisseau={"coque": 0.6}))
        self.jouer(d.replique)
        self.assertEqual(decider("tu as vu le match hier", reveil=False).type, "ignore")
        self.assertTrue(conversation.attend_reponse())

    def test_devinette(self):
        with mock.patch.object(conversation.random, "choice", lambda l: l[0]):
            d = decider("Covas une devinette")
            self.assertEqual(d.replique["id"], "Devinette1")
            self.jouer(d.replique)
            bonne = decider("une étoile", reveil=False)
            self.assertEqual(bonne.replique["id"], "Bravo1")
            self.jouer(bonne.replique)
            self.assertTrue(conversation.attend_reponse())          # « Une autre ? »
            autre = decider("oui", reveil=False)
            self.assertTrue(autre.replique["id"].startswith("Devinette"))
            self.jouer(autre.replique)
            rate = decider("un vaisseau thargoïde", reveil=False)
            self.assertTrue(rate.replique["id"].endswith("Rate"))

    def test_ordre_pendant_une_devinette(self):
        with mock.patch.object(conversation.random, "choice", lambda l: l[0]):
            self.jouer(decider("Covas une devinette").replique)
        d = decider("Covas sors le train", reveil=True)
        self.assertEqual((d.type, d.action), ("commande", "train_atterrissage"))

    def test_echo_de_la_voix_du_covas(self):
        d = decider("Covas qui es-tu")
        self.jouer(d.replique)
        texte = conversation.texte_de(d.replique, etat())[0]
        self.assertEqual(decider(texte, echo_possible=True).type, "ignore")

    def test_silence_radio(self):
        self.jouer(decider("Covas silence radio").replique)
        self.assertFalse(conversation.initiatives_actives())
        self.jouer(decider("Covas tu peux parler").replique)
        self.assertTrue(conversation.initiatives_actives())


class Initiatives(Base):
    def setUp(self):
        super().setUp()
        conversation._initiatives.update(actives=True, derniere=-1e9, repos={}, programmees=[],
                                         depuis={})

    def tour(self, e, occupe=False):
        jouees = []

        async def jouer_initiative(replique):
            jouees.append(replique)

        asyncio.run(conversation.tour_initiatives(e, jouer_initiative, lambda: occupe))
        return jouees

    def test_retour_a_quai(self):
        e = etat(flags=AMARRE | VAISSEAU, status={"carburant": 10}, vaisseau={"carburant_max": 32},
                 position={"station": {"nom": "Jameson Memorial", "services": ["refuel", "repair"]}})
        conversation.observer_evenement({"event": "Docked"})
        self.assertEqual(self.tour(e), [])                       # délai pas encore écoulé
        conversation._initiatives["programmees"][0]["a"] = time.monotonic() - 1
        self.assertEqual(self.tour(e, occupe=True), [])          # le COVAS parle déjà
        jouees = self.tour(e)
        self.assertEqual(len(jouees), 1)
        self.assertTrue(jouees[0]["id"].startswith("RetourStation"))

    def test_rien_a_faire_a_quai(self):
        e = etat(flags=AMARRE | VAISSEAU, status={"carburant": 32}, vaisseau={"carburant_max": 32, "coque": 1},
                 position={"station": {"services": ["refuel"]}})
        conversation.observer_evenement({"event": "Docked"})
        conversation._initiatives["programmees"][0]["a"] = time.monotonic() - 1
        self.assertEqual(self.tour(e), [])

    def test_monde_terrestre(self):
        conversation.observer_evenement({"event": "Scan", "PlanetClass": "Earthlike body",
                                         "WasDiscovered": False})
        conversation._initiatives["programmees"][0]["a"] = time.monotonic() - 1
        self.assertEqual([r["id"] for r in self.tour(etat())], ["MondeTerrestre"])

    def test_fin_de_combat(self):
        conversation.observer_evenement({"event": "UnderAttack", "Target": "You"})
        e = etat()
        self.assertEqual(self.tour(e), [])                       # contexte vrai depuis 0 s
        conversation._initiatives["depuis"]["apres_combat"] -= 30
        with mock.patch.object(conversation.random, "random", lambda: 0.0):
            self.assertEqual([r["id"] for r in self.tour(e)], ["ApresCombat1"])

    def test_silence_radio_bloque(self):
        conversation.appliquer_interne("initiatives_off")
        conversation.observer_evenement({"event": "Promotion"})
        conversation._initiatives["programmees"][0]["a"] = time.monotonic() - 1
        self.assertEqual(self.tour(etat()), [])

    def test_question_sans_reponse(self):
        devinette = conversation.sujet("devinette")["repliques"][0]
        conversation.attendre_reponse(devinette["suite"])
        conversation._attente["jusqu_a"] = time.monotonic() - 1
        self.assertEqual([r["id"] for r in self.tour(etat())], ["Devinette1Reponse"])


class Script(Base):
    def test_script_genere(self):
        chemin = os.path.join(DOSSIER_BACKEND, "tests", "_script_essai.md")
        try:
            total, faits = conversation.ecrire_script(chemin)
            with open(chemin, encoding="utf-8") as f:
                texte = f.read()
            self.assertGreater(total, 200)
            self.assertIn("data/son/Conversations/Bord/EtatAbime.wav", texte)
            self.assertIn("réponse *oui*", texte)
        finally:
            if os.path.exists(chemin):
                os.remove(chemin)


if __name__ == "__main__":
    unittest.main()
