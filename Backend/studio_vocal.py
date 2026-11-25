"""
studio_vocal.py — Studio vocal du COVAS : enregistre les répliques avec ta voix, entends-la aussitôt
transformée en voix du COVAS, garde la prise si elle te plaît.

Application à part (fenêtre native, page Frontend/studio.html), indépendante du COVAS : elle ne
charge ni le modèle vocal au démarrage, ni les touches, ni le jeu. Le COVAS peut tourner en même temps.

Lancement : « STUDIO VOCAL.bat » (journal dans data/studio.log)
        ou  depuis l'onglet Studio des réglages du COVAS (option --service, voir module/studio/pont_studio.py)
Variable COVAS_DEBUG=1 : ouvre les outils de développement de la fenêtre.

Le travail (nettoyage, effet, rangement, étalonnage) est dans module/studio/studio.py et module/studio/effet_voix.py ;
ici seulement le micro, le haut-parleur et le lien avec la page.
"""
import collections
import json
import logging
import os
import pathlib
import sys
import threading

DOSSIER_BACKEND = os.path.dirname(os.path.abspath(__file__))
DOSSIER_FRONTEND = os.path.join(os.path.dirname(DOSSIER_BACKEND), "Frontend")
TITRE = "COVAS — Studio vocal"

JOURNAL = os.path.join(DOSSIER_BACKEND, "data", "studio.log")
_log = logging.getLogger("studio")

sys.path.insert(0, DOSSIER_BACKEND)

import numpy as np  # noqa: E402
import sounddevice as sd  # noqa: E402

from module.studio import effet_voix, studio  # noqa: E402
from module.son import sons  # noqa: E402


def _propre(objet):
    """Valeurs numpy -> types Python (la page reçoit du JSON)."""
    def convertir(v):
        if isinstance(v, np.generic):
            return v.item()
        if isinstance(v, np.ndarray):
            return v.tolist()
        raise TypeError(type(v).__name__)
    return json.loads(json.dumps(objet, default=convertir))


# =====================================================================
#  MICRO : ouvert tant que le studio l'est (niveau en direct), enregistre à la demande
# =====================================================================
class Micro:
    TAUX = 48000
    BLOC = 0.02                 # secondes par bloc reçu
    AVANT = 0.25                # secondes gardées avant l'appui (une syllabe dite trop tôt n'est pas perdue)
    DUREE_MAX = 30.0            # secondes : au-delà, la prise s'arrête d'elle-même

    def __init__(self):
        self._flux = None
        self.taux = self.TAUX
        self.nom = None
        self.erreur = None
        self.enregistre = False
        self._avant = collections.deque(maxlen=int(self.AVANT / self.BLOC) + 1)
        self._morceaux = []
        self._echantillons = 0
        self._niveau = -120.0
        self._crete = 0.0

    @staticmethod
    def liste():
        """Micros de l'interface audio par défaut de Windows (sans doublons ni « mappeur »)."""
        try:
            interface = sd.default.hostapi
            noms = []
            for d in sd.query_devices():
                nom = d["name"]
                if d["max_input_channels"] > 0 and d["hostapi"] == interface and nom not in noms \
                        and "mapper" not in nom.lower() and "mappeur" not in nom.lower():
                    noms.append(nom)
            return noms
        except Exception:
            return []

    @property
    def ouvert(self):
        return self._flux is not None

    def ouvrir(self, nom=None):
        """Ouvre le micro `nom` (None = celui de Windows). Renvoie True si c'est fait."""
        self.fermer()
        index = None
        if nom:
            for i, d in enumerate(sd.query_devices()):
                if d["name"] == nom and d["max_input_channels"] > 0 and d["hostapi"] == sd.default.hostapi:
                    index = i
                    break
        essais = [self.TAUX]
        try:
            defaut = int(sd.query_devices(index if index is not None else sd.default.device[0])["default_samplerate"])
            essais.append(defaut)
        except Exception:
            pass
        for taux in essais:
            try:
                flux = sd.InputStream(device=index, channels=1, samplerate=taux, dtype="float32",
                                      blocksize=int(taux * self.BLOC), callback=self._recu)
                flux.start()
            except Exception as erreur:
                self.erreur = str(erreur)
                continue
            self._flux, self.taux, self.nom, self.erreur = flux, taux, (nom if index is not None else None), None
            return True
        _log.warning(f"Micro inaccessible : {self.erreur}")
        return False

    def fermer(self):
        if self._flux is not None:
            try:
                self._flux.stop()
                self._flux.close()
            except Exception:
                pass
        self._flux = None
        self.enregistre = False

    def _recu(self, donnees, _n, _temps, _statut):
        bloc = donnees[:, 0].copy()
        self._niveau = 20 * float(np.log10(np.sqrt(np.mean(bloc ** 2)) + 1e-9))
        self._crete = max(self._crete, float(np.abs(bloc).max()))
        if self.enregistre:
            if self._echantillons < self.DUREE_MAX * self.taux:
                self._morceaux.append(bloc)
                self._echantillons += len(bloc)
        else:
            self._avant.append(bloc)

    def commencer(self):
        self._morceaux = list(self._avant)
        self._echantillons = sum(len(m) for m in self._morceaux)
        self.enregistre = True

    def finir(self):
        self.enregistre = False
        morceaux, self._morceaux = self._morceaux, []
        brut = np.concatenate(morceaux) if morceaux else np.zeros(0, dtype=np.float32)
        return brut, self.taux

    def niveau(self):
        crete, self._crete = self._crete, 0.0
        return {"niveau": round(self._niveau, 1), "crete": round(20 * float(np.log10(crete + 1e-9)), 1),
                "enregistre": self.enregistre, "duree": round(self._echantillons / self.taux, 2),
                "plein": self._echantillons >= self.DUREE_MAX * self.taux, "ouvert": self.ouvert}


# =====================================================================
#  LIEN AVEC LA PAGE : window.pywebview.api.<nom>()
# =====================================================================
class Api:
    def __init__(self):
        self._studio = studio.Studio()
        self._micro = Micro()
        self._fenetre = None
        self._ligne = None                  # réplique en cours d'enregistrement (None = essai libre)
        self._verif = {"etat": "aucune"}
        self._jeton = 0
        self._whisper_pret = False
        self._verrou_whisper = threading.Lock()

    # --- état -----------------------------------------------------------
    def demarrer(self):
        """Appelé par la page une fois chargée : ouvre le micro choisi."""
        if not self._micro.ouvert:
            self._micro.ouvrir(self._studio.reglages["micro"])
        return self.etat()

    def etat(self):
        s = self._studio
        return _propre({
            "reglages": s.reglages,
            "reglables": studio.REGLABLES,
            "debruitage": studio.DEBRUITAGE,
            "profils": list(effet_voix.PROFILS),
            "micros": Micro.liste(),
            "micro": {"nom": self._micro.nom, "taux": self._micro.taux, "erreur": self._micro.erreur,
                      "ouvert": self._micro.ouvert},
            "etalonnage": self._etalonnage(),
            "compteurs": s.compteurs(),
            "sources": studio.SOURCES,
            "etats": studio.ETATS,
            "prise": s.resume(),
        })

    def _etalonnage(self):
        return {"fait": self._studio.reglages["etalonnage"], "disponible": self._studio.voix_disponible(),
                "conseille": studio.PAROLE_ETALONNAGE, "minimum": studio.PAROLE_ETALONNAGE_MIN}

    def repliques(self):
        return _propre(self._studio.inventaire())

    def niveau(self):
        return self._micro.niveau()

    # --- prise ----------------------------------------------------------
    def enregistrer(self, ident=None):
        sd.stop()
        if not self._micro.ouvert and not self._micro.ouvrir(self._studio.reglages["micro"]):
            return {"erreur": f"micro inaccessible ({self._micro.erreur})"}
        self._ligne = ident or None
        self._jeton += 1                     # une vérification en cours ne concerne plus rien
        self._verif = {"etat": "aucune"}
        self._micro.commencer()
        return {"ok": True}

    def arreter(self):
        if not self._micro.enregistre:
            return {"erreur": "aucun enregistrement en cours"}
        brut, taux = self._micro.finir()
        try:
            resume = self._studio.traiter(brut, taux, self._ligne)
        except Exception as erreur:
            _log.exception("Studio")
            return {"erreur": f"traitement impossible ({erreur})"}
        resultat = {"prise": resume, "etalonnage": self._etalonnage()}
        if resume["parole"] > 0:
            self._lancer_verification()
            if self._studio.reglages["ecoute_auto"]:
                resultat["lecture"] = self._jouer("covas")
        return _propre(resultat)

    def annuler(self):
        self._micro.finir()
        return {"ok": True}

    def veille(self):
        """Onglet Studio quitté : plus de micro ni de son, le reste du studio attend."""
        sd.stop()
        self._micro.fermer()
        return {"ok": True}

    def _jouer(self, quoi, ident=None):
        p = self._studio.prise
        if quoi in ("covas", "brut", "propre") and p:
            x = p[quoi]
            taux = p["taux"]
        elif quoi == "actuelle" and ident:
            chemin = sons.trouver(studio.absolu(studio.relatif_mp3(ident)))
            if not chemin:
                return {"erreur": "cette réplique n'a pas encore de fichier"}
            x, taux = sons.lire(chemin)
        else:
            return {"erreur": "rien à écouter pour l'instant"}
        if not len(x):
            return {"erreur": "rien à écouter pour l'instant"}
        sd.stop()
        sd.play(x, taux)
        return {"quoi": quoi, "duree": round(len(x) / taux, 2)}

    def ecouter(self, quoi, ident=None):
        try:
            return _propre(self._jouer(quoi, ident))
        except Exception as erreur:
            _log.exception("Studio")
            return {"erreur": f"lecture impossible ({erreur})"}

    def silence(self):
        sd.stop()
        return {"ok": True}

    def garder(self, ident=None):
        try:
            ligne = self._studio.garder(ident or self._ligne)
        except ValueError as erreur:
            return {"erreur": str(erreur)}
        except Exception as erreur:
            _log.exception("Studio")
            return {"erreur": f"enregistrement impossible ({erreur})"}
        return _propre({"ligne": ligne, "compteurs": self._studio.compteurs(), "etalonnage": self._etalonnage()})

    # --- réglages -------------------------------------------------------
    def _apres_reglage(self, son_change):
        resultat = {"reglages": self._studio.reglages, "compteurs": self._studio.compteurs(),
                    "etalonnage": self._etalonnage()}
        p = self._studio.prise
        if son_change and p:
            resultat["prise"] = self._studio.resume()
            if p["bilan"]["parole"] > 0:
                self._lancer_verification()
                if self._studio.reglages["ecoute_auto"]:
                    resultat["lecture"] = self._jouer("covas")
        return _propre(resultat)

    def regler(self, changements):
        try:
            son_change = self._studio.regler(changements or {})
            if "micro" in (changements or {}):
                self._micro.ouvrir(self._studio.reglages["micro"])
                if not self._micro.ouvert:
                    return {"erreur": f"micro inaccessible ({self._micro.erreur})", **self.etat()}
            return self._apres_reglage(son_change)
        except Exception as erreur:
            _log.exception("Studio")
            return {"erreur": f"réglage impossible ({erreur})"}

    def reinitialiser(self):
        self._studio.reinitialiser(garder_etalonnage=True)
        return self._apres_reglage(True)

    def etalonner(self):
        try:
            self._studio.etalonner()
        except ValueError as erreur:
            return {"erreur": str(erreur)}
        except Exception as erreur:
            _log.exception("Studio")
            return {"erreur": f"étalonnage impossible ({erreur})"}
        return self._apres_reglage(True)

    def oublier_etalonnage(self):
        self._studio.oublier_etalonnage()
        return self._apres_reglage(True)

    def appliquer_a_toutes(self):
        if not self._studio.travail["en_cours"]:
            threading.Thread(target=self._studio.appliquer_a_toutes, name="Studio-toutes", daemon=True).start()
        return self.travail()

    def travail(self):
        return _propre({**self._studio.travail, "compteurs": self._studio.compteurs()})

    # --- vérification par Whisper ---------------------------------------
    def _lancer_verification(self):
        p = self._studio.prise
        if not self._studio.reglages["verifier"] or not p or not len(p["covas"]):
            self._verif = {"etat": "aucune"}
            return
        self._jeton += 1
        jeton, numero = self._jeton, p["numero"]
        ligne = self._studio.ligne(p["ligne"]) if p["ligne"] else None
        texte = ligne["texte"] if ligne else None
        covas, taux = p["covas"], p["taux"]
        self._verif = {"etat": "en_cours" if self._whisper_pret else "chargement", "numero": numero}

        def verifier():
            with self._verrou_whisper:          # une écoute à la fois ; les prises dépassées sont sautées
                if jeton != self._jeton:
                    return
                try:
                    score, entendu = self._studio.verifier(texte, covas, taux)
                    self._whisper_pret = True
                except Exception as erreur:
                    _log.exception("Studio")
                    if jeton == self._jeton:
                        self._verif = {"etat": "erreur", "message": str(erreur), "numero": numero}
                    return
            if jeton == self._jeton:
                self._verif = {"etat": "fini", "score": score, "entendu": entendu, "numero": numero,
                               "texte": texte}

        threading.Thread(target=verifier, name="Studio-whisper", daemon=True).start()

    def verification(self):
        return _propre(self._verif)


def _ouvrir_journal():
    """Pas de console : les problèmes (et les erreurs imprévues) vont dans data/studio.log."""
    journal = open(JOURNAL, "w", encoding="utf-8", buffering=1)
    sys.stderr = journal
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    logging.basicConfig(stream=journal, level=logging.WARNING,
                        format="%(asctime)s %(levelname)s %(name)s : %(message)s", datefmt="%d/%m %H:%M:%S")
    return journal


def lancer():
    import webview
    _ouvrir_journal()
    api = Api()
    page = pathlib.Path(DOSSIER_FRONTEND, "studio.html").as_uri()
    fenetre = webview.create_window(TITRE, url=page, js_api=api, background_color="#070403",
                                    width=1500, height=900, min_size=(1100, 680), text_select=True)
    api._fenetre = fenetre
    webview.start(gui="edgechromium", debug=os.environ.get("COVAS_DEBUG") == "1", private_mode=False)
    # Fenêtre fermée : on coupe tout (micro, lecture, Whisper)
    api._micro.fermer()
    os._exit(0)


def service():
    """Sans fenêtre, pour l'onglet Studio des réglages : une demande JSON par ligne sur l'entrée,
    une réponse par ligne sur la sortie. Entrée fermée (COVAS quitté) : micro coupé, fin."""
    sortie = os.fdopen(os.dup(1), "wb", buffering=0)
    # Ce que les bibliothèques écrivent sur la sortie ne doit pas se mêler aux réponses
    journal = _ouvrir_journal()
    os.dup2(journal.fileno(), 1)
    os.dup2(journal.fileno(), 2)
    sys.stdout = journal

    api = Api()
    permis = {nom for nom, f in vars(Api).items() if callable(f) and not nom.startswith("_")}
    verrou = threading.Lock()

    def traiter(demande):
        reponse = {"id": demande.get("id")}
        nom = demande.get("nom")
        try:
            if nom not in permis:
                raise ValueError(f"commande inconnue : {nom}")
            reponse["resultat"] = getattr(api, nom)(*(demande.get("args") or []))
            ligne = json.dumps(reponse)
        except Exception as erreur:
            _log.exception("Studio")
            ligne = json.dumps({"id": demande.get("id"), "erreur": str(erreur)})
        with verrou:
            sortie.write(ligne.encode("ascii") + b"\n")

    for brut in sys.stdin.buffer:
        try:
            demande = json.loads(brut)
        except ValueError:
            continue
        if isinstance(demande, dict):
            threading.Thread(target=traiter, args=(demande,), name="Studio-appel", daemon=True).start()
    api._micro.fermer()
    sd.stop()
    os._exit(0)


def principal(arguments):
    if "--service" in arguments:
        service()
    else:
        lancer()


if __name__ == "__main__":
    principal(sys.argv[1:])
