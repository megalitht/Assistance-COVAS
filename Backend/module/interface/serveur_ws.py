"""
serveur_ws.py — Pont WebSocket entre le backend COVAS et l'interface web.

  backend   -> interface : envoyer_donnees_web({...})   (état du vaisseau, événements)
  interface -> backend   : {"action": "train_atterrissage"}  -> file des macros
                           (mêmes noms d'action que dans macros.py)
                           {"question": "comment va le vaisseau ?"} -> comme une phrase dite
                           au micro après « Covas » (voir definir_questions)
                           {"reglages": {...}, "rev": n} -> enregistré (reglages.py), puis
                           renvoyé à toutes les interfaces

Dépendance : pip install websockets
"""
import asyncio
import json

import websockets

from module import reglages

# Ce PC seulement (IPv4 et IPv6). L'interface peut appuyer sur les touches du jeu : None
# l'ouvrirait à tout le réseau local (une tablette... mais aussi n'importe quel appareil).
HOTE = "localhost"
PORT = 8765

_clients = set()
_instantane = None     # fonction qui renvoie l'état complet, envoyé à chaque nouvelle interface
_file_actions = None   # file asyncio des macros (fournie par main.py)
_questions = None      # async fonction(texte) : phrase tapée dans l'interface (main.py)
_taches = set()
_programme = None      # nom du programme en cours (décollage, voyage...), None sinon
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
    """Nombre d'interfaces web connectées en ce moment."""
    return len(_clients)


async def envoyer_donnees_web(donnees: dict):
    """Diffuse un message JSON à toutes les interfaces ouvertes (ne fait rien s'il n'y en a pas)."""
    if not _clients:
        return
    message = json.dumps(donnees, ensure_ascii=False, default=str)
    # Une interface fermée entre-temps lève une erreur : elle est retirée par son gestionnaire.
    await asyncio.gather(*(client.send(message) for client in list(_clients)),
                         return_exceptions=True)


def signaler_programme(nom):
    """Programme en cours (son nom, ou None) : l'interface n'affiche Stop que dans ce cas.
    À appeler depuis la boucle asyncio. Gardé ici pour le renvoyer à chaque nouvelle interface."""
    global _programme
    _programme = nom
    tache = asyncio.create_task(envoyer_donnees_web({"type": "programme", "nom": nom}))
    _taches.add(tache)
    tache.add_done_callback(_taches.discard)


async def _gerer_interface(websocket, *_):
    # *_ : les anciennes versions de `websockets` passent aussi le chemin de l'URL.
    _clients.add(websocket)
    print(f"[Web] Interface connectée ({len(_clients)} ouverte(s)).")
    try:
        if _instantane:
            await websocket.send(json.dumps(_instantane(), ensure_ascii=False, default=str))
        await websocket.send(json.dumps({"type": "reglages", "reglages": reglages.document()},
                                        ensure_ascii=False))
        await websocket.send(json.dumps({"type": "programme", "nom": _programme}, ensure_ascii=False))
        async for message in websocket:
            await _traiter_message(message)
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        _clients.discard(websocket)
        print(f"[Web] Interface déconnectée ({len(_clients)} ouverte(s)).")


async def _traiter_message(message):
    try:
        donnees = json.loads(message)
    except (TypeError, ValueError):
        return
    if not isinstance(donnees, dict):
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
    global _file_actions, _programme
    _file_actions = file_actions
    _programme = None      # COVAS réactivé dans la même application : rien ne tourne encore
    try:
        async with websockets.serve(_gerer_interface, HOTE, PORT):
            print(f"[Web] Serveur d'interface prêt sur ws://localhost:{PORT}")
            await asyncio.Future()   # tourne jusqu'à l'arrêt du programme
    except OSError as erreur:
        print(f"[Web] Impossible d'ouvrir le port {PORT} : {erreur}")