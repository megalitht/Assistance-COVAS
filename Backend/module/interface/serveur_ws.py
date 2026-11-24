"""
serveur_ws.py — Pont WebSocket entre le backend COVAS et l'interface web, et pages du second écran.

  backend   -> interface : envoyer_donnees_web({...})   (état du vaisseau, événements)
  interface -> backend   : {"action": "train_atterrissage"}  -> file des macros
                           (mêmes noms d'action que dans macros.py)
                           {"question": "comment va le vaisseau ?"} -> comme une phrase dite
                           au micro après « Covas » (voir definir_questions)
                           {"reglages": {...}, "rev": n} -> enregistré (reglages.py), puis
                           renvoyé à toutes les interfaces
                           {"pin": "4821"} -> autorise les commandes d'un autre appareil

Second écran (téléphone, tablette : voir second_ecran.py et data/config.toml [second_ecran]) :
le serveur écoute alors sur toutes les cartes réseau, et le même port sert aussi les pages de
Frontend/ : http://<adresse du PC>:<port>/. Les commandes d'un autre appareil exigent le PIN.

Messages propres à chaque interface (en plus de l'état du vaisseau) :
  {"type": "acces", "local": bool, "autorise": bool, "pin_regle": bool}   à la connexion
  {"type": "pin", "resultat": "ok" | "faux" | "bloque" | "absent", "attente": s}
  {"type": "refus", "raison": "pin", "action": ...}     commande refusée faute de PIN
  {"type": "second_ecran", ...}                          adresse et QR code (PC seulement)

Dépendance : pip install websockets (segno pour le QR code)
"""
import asyncio
import email.utils
import http
import json

import websockets

from module import config
from module.interface import reglages
from module.interface import second_ecran

# Sans second écran : ce PC seulement (IPv4 et IPv6). Avec : toutes les cartes réseau (None), les
# appareils hors du réseau local étant refusés à la connexion.
HOTE = "localhost"
PORT = 8765

_clients = set()
_acces = {}            # websocket -> {"adresse", "local", "autorise"}
_garde = second_ecran.GardePin()
_instantane = None     # fonction qui renvoie l'état complet, envoyé à chaque nouvelle interface
_file_actions = None   # file asyncio des macros (fournie par main.py)
_questions = None      # async fonction(texte) : phrase tapée dans l'interface (main.py)
_taches = set()
_programme = None      # nom du programme en cours (décollage, voyage...), None sinon
_reseau = {"actif": False, "port": PORT, "adresses": []}    # second écran tel qu'il a démarré
LONGUEUR_MAX_QUESTION = 300


def definir_questions(fonction):
    """Enregistre la fonction qui traite une phrase tapée dans l'interface."""
    global _questions
    _questions = fonction


def definir_instantane(fonction):
    """Enregistre la fonction qui fabrique l'état complet envoyé à la connexion."""
    global _instantane
    _instantane = fonction


def interfaces_ouvertes() -> int:
    """Nombre d'interfaces web connectées en ce moment (PC et autres appareils)."""
    return len(_clients)


def interfaces_locales_ouvertes() -> int:
    """Nombre d'interfaces ouvertes sur ce PC (fenêtre de l'application, navigateur)."""
    return sum(1 for client in list(_clients) if _acces.get(client, {}).get("local"))


def port_configure():
    """Port de l'interface (data/config.toml [second_ecran] port)."""
    port = config.valeur("second_ecran", "port")
    return port if isinstance(port, int) and 1024 <= port <= 65535 else 8765


def infos_second_ecran():
    """Ce que l'interface du PC affiche dans « Second écran » (le QR code de la 1re adresse)."""
    adresses = _reseau["adresses"]
    return {"type": "second_ecran", "actif": _reseau["actif"], "port": _reseau["port"],
            "adresses": adresses, "qr": second_ecran.qr_svg(adresses[0]) if adresses else None,
            "pin_regle": bool(config.valeur("second_ecran", "pin"))}


async def envoyer_donnees_web(donnees: dict):
    """Diffuse un message JSON à toutes les interfaces ouvertes (ne fait rien s'il n'y en a pas)."""
    if not _clients:
        return
    message = json.dumps(donnees, ensure_ascii=False, default=str)
    # Une interface fermée entre-temps lève une erreur : elle est retirée par son gestionnaire.
    await asyncio.gather(*(client.send(message) for client in list(_clients)),
                         return_exceptions=True)


def programme_actuel():
    """Nom du programme en cours (décollage, voyage...), None sinon."""
    return _programme


def signaler_programme(nom):
    """Programme en cours (son nom, ou None) : l'interface n'affiche Stop que dans ce cas.
    À appeler depuis la boucle asyncio. Gardé ici pour le renvoyer à chaque nouvelle interface."""
    global _programme
    _programme = nom
    tache = asyncio.create_task(envoyer_donnees_web({"type": "programme", "nom": nom}))
    _taches.add(tache)
    tache.add_done_callback(_taches.discard)


# =====================================================================
#  REQUÊTES HTTP : pages du second écran, et contrôle avant la liaison
# =====================================================================
def _reponse(connexion, statut, contenu=b"", type_contenu="text/plain; charset=utf-8"):
    """Réponse HTTP complète (le serveur ferme la connexion après l'avoir envoyée)."""
    reponse = connexion.respond(statut, "")
    for nom in ("Content-Type", "Content-Length"):
        del reponse.headers[nom]
    reponse.headers["Content-Type"] = type_contenu
    reponse.headers["Content-Length"] = str(len(contenu))
    reponse.headers["Cache-Control"] = "no-cache"            # le téléphone voit les mises à jour
    reponse.headers["X-Content-Type-Options"] = "nosniff"
    if not reponse.headers.get("Date"):
        reponse.headers["Date"] = email.utils.formatdate(usegmt=True)
    reponse.body = contenu
    return reponse


def _adresse_distante(connexion):
    try:
        return connexion.remote_address[0]
    except (TypeError, IndexError, AttributeError):
        return None


def _controle_requete(connexion, requete):
    """Avant toute réponse : réseau local seulement, et adresse demandée sans nom de domaine.
    Une demande de liaison (WebSocket) vient-elle bien d'une page du COVAS ? Une simple requête
    HTTP reçoit la page demandée (lecture seule)."""
    adresse = _adresse_distante(connexion)
    if not second_ecran.est_reseau_local(adresse):
        return _reponse(connexion, http.HTTPStatus.FORBIDDEN, "Réseau local seulement.".encode())
    hote = requete.headers.get("Host", "")
    if not second_ecran.hote_autorise(hote):
        return _reponse(connexion, http.HTTPStatus.FORBIDDEN, "Adresse refusée.".encode())
    if requete.headers.get("Upgrade", "").lower() == "websocket":
        if not second_ecran.origine_autorisee(requete.headers.get("Origin"), hote):
            print(f"[Web] Liaison refusée : origine {requete.headers.get('Origin')!r}")
            return _reponse(connexion, http.HTTPStatus.FORBIDDEN, "Origine refusée.".encode())
        return None                                   # liaison acceptée
    if not _reseau["actif"] and not second_ecran.est_ce_pc(adresse):
        return _reponse(connexion, http.HTTPStatus.FORBIDDEN, "Second écran désactivé.".encode())
    chemin = second_ecran.fichier_demande(requete.path)
    if chemin is None:
        return _reponse(connexion, http.HTTPStatus.NOT_FOUND, "Page introuvable.".encode())
    try:
        type_contenu, contenu = second_ecran.lire_fichier(chemin)
    except OSError:
        return _reponse(connexion, http.HTTPStatus.NOT_FOUND, "Page illisible.".encode())
    return _reponse(connexion, http.HTTPStatus.OK, contenu, type_contenu)


# =====================================================================
#  LIAISON AVEC CHAQUE INTERFACE
# =====================================================================
async def _envoyer(websocket, donnees):
    await websocket.send(json.dumps(donnees, ensure_ascii=False, default=str))


async def _gerer_interface(websocket, *_):
    # *_ : les anciennes versions de `websockets` passent aussi le chemin de l'URL.
    adresse = _adresse_distante(websocket)
    local = second_ecran.est_ce_pc(adresse)
    _acces[websocket] = {"adresse": adresse, "local": local, "autorise": local}
    _clients.add(websocket)
    print(f"[Web] Interface connectée{'' if local else ' depuis ' + str(adresse)} "
          f"({len(_clients)} ouverte(s)).")
    try:
        await _envoyer(websocket, {"type": "acces", "local": local, "autorise": local,
                                   "pin_regle": bool(config.valeur("second_ecran", "pin"))})
        if _instantane:
            await _envoyer(websocket, _instantane())
        await _envoyer(websocket, {"type": "reglages", "reglages": reglages.document()})
        await _envoyer(websocket, {"type": "programme", "nom": _programme})
        if local:
            await _envoyer(websocket, infos_second_ecran())
        async for message in websocket:
            await _traiter_message(message, websocket)
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        _clients.discard(websocket)
        _acces.pop(websocket, None)
        print(f"[Web] Interface déconnectée ({len(_clients)} ouverte(s)).")


async def _verifier_pin(websocket, acces, saisi):
    reglage = config.section("second_ecran")
    resultat = _garde.verifier(acces["adresse"], saisi, reglage["pin"], reglage["tentatives"],
                               reglage["blocage_minutes"] * 60)
    acces["autorise"] = acces["local"] or resultat == "ok"
    if resultat != "ok":
        print(f"[Web] PIN {resultat} depuis {acces['adresse']}")
    await _envoyer(websocket, {"type": "pin", "resultat": resultat,
                               "attente": round(_garde.bloque_pour(acces["adresse"]))})


async def _traiter_message(message, websocket=None):
    try:
        donnees = json.loads(message)
    except (TypeError, ValueError):
        return
    if not isinstance(donnees, dict):
        return
    # Sans websocket (appel interne) : comme le PC lui-même
    acces = _acces.get(websocket) or {"adresse": None, "local": True, "autorise": True}
    if "pin" in donnees and websocket is not None:
        await _verifier_pin(websocket, acces, donnees["pin"])
        return
    # Tout ce qui suit agit sur le jeu ou sur les réglages : PIN exigé hors de ce PC
    if not acces["autorise"]:
        if websocket is not None:
            await _envoyer(websocket, {"type": "refus", "raison": "pin",
                                       "pin_regle": bool(config.valeur("second_ecran", "pin")),
                                       "action": donnees.get("action")})
        return
    if "reglages" in donnees:
        document, erreur = reglages.enregistrer(donnees["reglages"])
        await envoyer_donnees_web({"type": "reglages", "reglages": document,
                                   "rev": donnees.get("rev"), "erreur": erreur})
        return
    question = donnees.get("question")
    if isinstance(question, str) and question.strip() and _questions is not None:
        # En tâche à part : la réponse (voix comprise) ne bloque pas la réception
        tache = asyncio.create_task(_questions(question.strip()[:LONGUEUR_MAX_QUESTION]))
        _taches.add(tache)
        tache.add_done_callback(_taches.discard)
        return
    action = donnees.get("action")
    # Seuls les noms connus de macros.py déclenchent des touches ; le reste y est ignoré.
    if isinstance(action, str) and _file_actions is not None:
        await _file_actions.put(action)


async def demarrer_serveur_web(file_actions=None):
    """Lance le serveur. `file_actions` : la file des macros, pour les boutons de l'interface."""
    global _file_actions, _programme, PORT
    _file_actions = file_actions
    _programme = None      # COVAS réactivé dans la même application : rien ne tourne encore
    PORT = port_configure()
    actif = bool(config.valeur("second_ecran", "actif"))
    hote = None if actif else HOTE                     # None : toutes les cartes réseau
    _reseau.update(actif=actif, port=PORT, adresses=second_ecran.adresses_page(PORT) if actif else [])
    try:
        async with websockets.serve(_gerer_interface, hote, PORT, process_request=_controle_requete):
            print(f"[Web] Serveur d'interface prêt sur ws://localhost:{PORT}")
            if actif:
                for adresse in _reseau["adresses"] or ["(aucune adresse réseau trouvée)"]:
                    print(f"[Web] Second écran : {adresse}")
            await asyncio.Future()   # tourne jusqu'à l'arrêt du programme
    except OSError as erreur:
        print(f"[Web] Impossible d'ouvrir le port {PORT} : {erreur}")
