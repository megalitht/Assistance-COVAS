# COVAS — Assistance de bord pour Elite Dangerous

COVAS est un assistant vocal de bord pour **Elite Dangerous**, écrit en Python. Il écoute le commandant au micro, comprend ses ordres en français, appuie sur les bonnes touches du jeu et lui répond avec des répliques enregistrées. Il lit en continu les journaux du jeu pour suivre l'état du vaisseau, annoncer ce qui se passe et l'afficher dans une interface holographique aux couleurs d'Elite.

> L'assistant n'est **pas génératif** : toutes ses réponses sont des répliques préenregistrées (voir `Backend/data/SCRIPT_VOIX.md` et `SCRIPT_CONVERSATIONS.md`).

---

## Fonctionnalités

- **Commandes vocales** avec mot de réveil (« Covas… »), reconnaissance vocale locale via Whisper (`faster-whisper`, sur GPU), tolérante aux erreurs d'écoute (sigles épelés, mots approchés).
- **Macros de pilotage** : NVG, phares, armement, mode HUD, mode silencieux, vitesse zéro / plein gaz, décollage et appontage complets, services de la station, cartes, fuite, puce thermique, ciblage, ordres au chasseur, drones, autopilote station et de route, modes d'énergie (pips)… et une commande **« stop »** qui interrompt tout.
- **Lecture automatique des touches** depuis le fichier `.binds` du jeu (AZERTY ou QWERTY détecté). Une commande sans touche clavier reçoit une **touche virtuelle** (F13 à F20) qu'on ne peut pas déclencher par erreur.
- **Suivi du jeu en temps réel** : `Journal.*.log`, `Status.json`, `NavRoute.json`, `ModulesInfo.json`, `Cargo.json`.
- **Annonces et réactions automatiques** : alertes de combat, dégâts, chasse aux primes, scans d'exploration, exobiologie… Réactions optionnelles (surchauffe → puce thermique, boucliers tombés ou interdiction → énergie aux systèmes).
- **Conversations « RP »** : le COVAS répond à des questions sur l'univers et le vaisseau, et peut lancer la conversation tout seul selon le contexte du jeu.
- **Politesse détectée** : « s'il te plaît » change la réplique choisie.
- **Interface holographique** (HTML / CSS / JS) : navigation, combat (la page bascule en mode combat dès qu'on prend des dégâts), surface, journal de bord, communications, hologramme du vaisseau vu de dessus.
- **Réglages intégrés** : modes d'énergie par vaisseau, commandes et séquences, choix du micro et de la sortie audio, **studio vocal** (enregistrement des répliques), **hangar des hologrammes** et **atelier des plans** (création d'un plan de vaisseau à partir d'une capture d'écran).

---

## Prérequis

- **Windows** (envoi des touches, gestion des fenêtres et de l'audio propres à Windows)
- **Python 3** avec un environnement virtuel `.venv` à la racine
- **Carte graphique NVIDIA** avec CUDA : le modèle Whisper tourne sur le GPU en `float16`
- Un **micro**
- Elite Dangerous installé (le COVAS fonctionne aussi jeu fermé : il attend son journal)
- Un deuxième écran est conseillé : l'application s'ouvre en plein écran sur l'écran secondaire, le jeu reste sur le principal

### Dépendances Python

Bibliothèques utilisées par le projet :

```
faster-whisper
SpeechRecognition
PyAudio
sounddevice
numpy
pydirectinput
websockets
pywebview
pygame
nvidia-cublas-cu12
nvidia-cudnn-cu12
```

```bat
python -m venv .venv
.venv\Scripts\pip install faster-whisper SpeechRecognition PyAudio sounddevice numpy pydirectinput websockets pywebview pygame nvidia-cublas-cu12 nvidia-cudnn-cu12
```

Les bibliothèques NVIDIA (cuBLAS, cuDNN) installées dans le `.venv` sont trouvées automatiquement au lancement.

### Modèle vocal

Le modèle Whisper (format CTranslate2) se place dans `Backend/module/` :

| Dossier | Modèle |
|---|---|
| `module/modele_vocal_turbo/` | `large-v3-turbo` (recommandé, meilleur en français) |
| `module/modele_vocal_fr/` | ancien modèle `small`, utilisé en secours si le premier est absent |

Chaque dossier doit contenir un fichier `model.bin`.

---

## Lancement

### Application (recommandé)

Double-clic sur **`COVAS.bat`** (sans console), ou :

```bat
.venv\Scripts\python.exe Backend\app.py
```

La fenêtre s'ouvre sur l'écran d'accueil, **COVAS en veille** (ni micro, ni touches, ni modèle chargé). Le bouton central **Activer** lance le démarrage : chaque étape s'affiche (répliques, modèle vocal, calibrage du micro, sous-systèmes), puis l'écran laisse place au panneau de contrôle.

Au démarrage, le COVAS vérifie le serveur d'interface, le dossier des journaux, le fichier `.binds` et le micro. Si tout va bien, il annonce « systèmes opérationnels » ; sinon il affiche la liste des problèmes.

### En console

```bat
.venv\Scripts\python.exe Backend\main.py
```

Ouvrir ensuite `Frontend/interface.html` : l'interface se connecte toute seule au backend.

### Studio vocal seul

**`STUDIO VOCAL.bat`** ouvre le studio dans sa propre fenêtre. Pendant que le studio est ouvert, l'écoute du COVAS est en pause.

---

## Utilisation

- Dire **« Covas »** suivi d'une commande : *« Covas, sors le train »*, *« Covas, active les NVG s'il te plaît »*.
- Dire seulement **« Covas »** pour passer en écoute active.
- Quand le COVAS vient de poser une question, on peut lui répondre **sans** redire « Covas » (8 secondes).
- **« Covas, stop »** interrompt une macro ou un programme en cours (décollage, autopilote…).
- On peut aussi **écrire** au COVAS dans le champ « Communications » de l'interface, ou utiliser les **boutons** du panneau.
- Les réactions automatiques sont désactivées au lancement : *« Covas, active les réactions »*.

---

## Structure du projet

```
Assistance-COVAS/
├── COVAS.bat                  Lance l'application (sans console)
├── STUDIO VOCAL.bat           Lance le studio vocal seul
├── Backend/
│   ├── app.py                 Application (fenêtre native pywebview, écran d'accueil)
│   ├── main.py                Cœur du COVAS : écoute, Whisper, files d'actions et de voix
│   ├── studio_vocal.py        Studio d'enregistrement des répliques
│   ├── data/
│   │   ├── barks.json             Commandes, mots-clés et répliques associées
│   │   ├── conversations.json     Sujets de conversation et initiatives du COVAS
│   │   ├── exobiologie.json       Données d'exobiologie (espèces, valeurs)
│   │   ├── reglages.json          Réglages enregistrés depuis l'interface
│   │   ├── SCRIPT_VOIX.md         Script des répliques à enregistrer
│   │   ├── SCRIPT_CONVERSATIONS.md
│   │   └── son/                   Répliques enregistrées (.mp3)
│   └── module/
│       ├── dialogue/          Compréhension des phrases, conversations, choix des répliques
│       ├── jeu/               Lecture des journaux, exploration, chasse, avaries, EDSM
│       ├── pilotage/          Macros, lecture du .binds, touches virtuelles, pips, actions
│       ├── interface/         Serveur WebSocket, réglages, terminal stylisé, plans
│       ├── son/               Micro, sortie audio, lecture des voix
│       └── studio/            Pont entre l'application et le studio vocal
└── Frontend/
    ├── interface.html / .css / .js   Panneau holographique principal
    ├── hologramme.js                 Hologramme du vaisseau (vue de dessus)
    ├── vaisseaux/                    Plans des vaisseaux (un fichier .js par type)
    ├── reglages*.js                  Fenêtre des réglages (énergie, commandes, son)
    ├── studio.html / .js / .css      Studio vocal
    ├── hangar.html                   Hangar des hologrammes
    ├── atelier.html / .js            Atelier des plans
    └── demo.js                       Simulation sans jeu ni backend
```

### Fonctionnement en bref

```
Micro ──► Whisper (GPU) ──► compréhension ──► file des actions ──► macros ──► touches du jeu
                                    │                                   │
                                    └────► conversation ──► file des voix ──► haut-parleurs
Journaux du jeu ──► lecteur_logs ──► état du vaisseau ──► WebSocket (ws://localhost:8765) ──► interface
```

L'interface envoie au backend des actions (`{"action": "train_atterrissage"}`), des phrases (`{"question": "..."}`) et des réglages ; le backend lui renvoie l'état du vaisseau et les événements du journal.

---

## Configuration

### Variables d'environnement

| Variable | Rôle |
|---|---|
| `COVAS_DOSSIER_ED` | Dossier des journaux du jeu, s'il n'est pas dans `Saved Games\Frontier Developments\Elite Dangerous` |
| `COVAS_DOSSIER_BINDS` | Dossier des fichiers `.binds`, s'il n'est pas dans `%LOCALAPPDATA%\Frontier Developments\Elite Dangerous\Options\Bindings` |
| `COVAS_DEBUG=1` | Ouvre les outils de développement de la fenêtre |

### Ports utilisés

| Port | Usage |
|---|---|
| `8765` | Liaison WebSocket entre le backend et l'interface (`localhost` uniquement) |
| `8766` | Petit serveur local qui sert l'interface à la fenêtre de l'application |

Un seul COVAS peut tourner à la fois : si le port 8765 est déjà pris, l'activation est refusée.

### Touches virtuelles

Si une commande utilisée par le COVAS n'a pas de touche clavier dans le jeu, le COVAS lui en attribue une (F13 à F20, seule ou avec Maj droite / Ctrl gauche) et l'écrit dans le `.binds` (une sauvegarde `.bak` est faite avant). **Redémarrer le jeu** ensuite pour qu'il les prenne en compte.

### Confidentialité

Le panneau « systèmes proches » interroge **EDSM** et envoie donc le nom du système actuel à `edsm.net`. Désactivable avec `SYSTEMES_PROCHES_ACTIF = False` dans `module/jeu/lecteur_logs.py`. Tout le reste (reconnaissance vocale comprise) fonctionne en local.

---

## Ajouter ou enregistrer des répliques

1. Ajouter la commande et ses mots-clés dans `Backend/data/barks.json`, ou le sujet de conversation dans `conversations.json`.
2. Compléter le script correspondant (`SCRIPT_VOIX.md` ou `SCRIPT_CONVERSATIONS.md`).
3. Enregistrer les phrases dans le **studio vocal** (onglet des réglages ou `STUDIO VOCAL.bat`) ; les fichiers vont dans `Backend/data/son/`.

---

## Diagnostic

Depuis `Backend/` :

```bat
:: Touches lues dans le fichier .binds (ajouter --assigner pour écrire les touches virtuelles)
python module\pilotage\touches.py

:: Vérifier conversations.json sans micro ni jeu
python -m module.dialogue.conversation --verifier

:: Tester la réponse à une phrase
python -m module.dialogue.conversation "comment va le vaisseau"
```

En mode application (sans console), les messages sont écrits dans `Backend/data/covas.log`.

Si Whisper comprend mal un mot qui revient souvent, ajouter une correction dans la liste `CORRECTIONS` de `module/dialogue/comprehension.py`, en s'aidant de ce que la console affiche.

---

## Avertissement

Projet de fan, non affilié à Frontier Developments. *Elite Dangerous* est une marque de Frontier Developments plc. Le COVAS envoie des appuis clavier au jeu : à utiliser en connaissance de cause.
