"""
serveur_ws.py — Pont WebSocket entre le backend COVAS et l'interface web.

  backend   -> interface : envoyer_donnees_web({...})   (état du vaisseau, événements)
  interface -> backend   : {"action": "train_atterrissage"}  -> file des macros
                           (mêmes noms d'action que dans macros.py)

Dépendance : pip install websockets
"""
import asyncio
import json

import websockets

HOTE = "localhost"   # "0.0.0.0" pour ouvrir l'interface depuis un autre appareil du réseau local
PORT = 8765

_clients = set()
_instantane = None     # fonction qui renvoie l'état complet, envoyé à chaque nouvelle interface
_file_actions = None   # file asyncio des macros (fournie par main.py)


def definir_instantane(fonction):
    """Enregistre la fonction qui fabrique l'état complet envoyé à la connexion."""
    global _instantane
    _instantane = fonction


async def envoyer_donnees_web(donnees: dict):
    """Diffuse un message JSON à toutes les interfaces ouvertes (ne fait rien s'il n'y en a pas)."""
    if not _clients:
        return
    message = json.dumps(donnees, ensure_ascii=False, default=str)
    # Une interface fermée entre-temps lève une erreur : elle est retirée par son gestionnaire.
    await asyncio.gather(*(client.send(message) for client in list(_clients)),
                         return_exceptions=True)


async def _gerer_interface(websocket, *_):
    # *_ : les anciennes versions de `websockets` passent aussi le chemin de l'URL.
    _clients.add(websocket)
    print(f"[Web] Interface connectée ({len(_clients)} ouverte(s)).")
    try:
        if _instantane:
            await websocket.send(json.dumps(_instantane(), ensure_ascii=False, default=str))
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
    action = donnees.get("action") if isinstance(donnees, dict) else None
    # Seuls les noms connus de macros.py déclenchent des touches ; le reste y est ignoré.
    if isinstance(action, str) and _file_actions is not None:
        await _file_actions.put(action)


async def demarrer_serveur_web(file_actions=None):
    """Lance le serveur. `file_actions` : la file des macros, pour les boutons de l'interface."""
    global _file_actions
    _file_actions = file_actions
    try:
        async with websockets.serve(_gerer_interface, HOTE, PORT):
            print(f"[Web] Serveur d'interface prêt sur ws://{HOTE}:{PORT}")
            await asyncio.Future()   # tourne jusqu'à l'arrêt du programme
    except OSError as erreur:
        print(f"[Web] Impossible d'ouvrir le port {PORT} : {erreur}")