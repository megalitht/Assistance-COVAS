# Script des conversations à enregistrer

*Fichier généré par `python -m module.conversation --script` (depuis `Backend/`) à partir de `data/conversations.json` : modifie le JSON, pas ce fichier.*

**261 fichiers à enregistrer** — 14 déjà faits ✅, 247 à faire ⬜.

Le plus simple : `STUDIO VOCAL.bat` (à la racine) liste ces phrases, transforme ta voix en voix du COVAS et range chaque fichier au bon endroit. Sinon, enregistre chaque phrase et range le fichier `.wav` au chemin indiqué (dans `Backend/`). Tant qu'un fichier manque, la phrase est seulement affichée à l'écran.

- **Contexte** : la réplique n'est choisie que dans cette situation. Une réplique « toujours » est la réponse par défaut.
- **↳ après « … »** : le COVAS vient de poser une question ; le commandant répond sans redire « Covas » (8 s par défaut, 15 s pour les devinettes).
- Tu peux changer une phrase : modifie `texte` dans le JSON (le fichier garde son nom).

## Échanges courants — `data/son/Conversations/Social/`

### Salutations (`salutation`)

*Questions :* « bonjour », « salut », « coucou », « bonsoir », « hello », « yo », « bien le bonjour », « salutations », « rebonjour », « me revoilà »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ✅ | toujours | `data/son/Conversations/Social/Bonjour1.wav` | Bonjour, commandant. Tous les systèmes vous attendaient. |
| ✅ | toujours | `data/son/Conversations/Social/Bonjour2.wav` | Ravie de vous entendre, commandant. Le cockpit était bien silencieux sans vous. |
| ✅ | le matin | `data/son/Conversations/Social/BonjourMatin1.wav` | Bonjour, commandant. Bien dormi ? Le vaisseau, lui, est frais comme au premier jour. |
| ⬜ | le matin | `data/son/Conversations/Social/BonjourMatin2.wav` | Debout de bonne heure, commandant. La galaxie ne va pas s'explorer toute seule. |
| ✅ | le soir | `data/son/Conversations/Social/BonjourSoir.wav` | Bonsoir, commandant. On part pour une petite virée nocturne ? |
| ⬜ | la nuit | `data/son/Conversations/Social/BonjourNuit.wav` | Bonsoir, commandant… ou bonjour, je ne sais plus. Il est tard, sur Terre. |
| ⬜ | amarré à une station | `data/son/Conversations/Social/BonjourAmarre.wav` | Bonjour, commandant. Nous sommes à quai, réservoir branché, tout est calme. |
| ⬜ | en danger | `data/son/Conversations/Social/BonjourDanger.wav` | Bonjour aussi, commandant. On nous tire dessus, au passage. |

### Comment ça va ? (`ca_va`)

*Questions :* « ça va », « comment ça va », « comment vas-tu », « comment tu vas », « tu vas bien », « ça va toi », « comment te sens-tu », « comment tu te sens », « la forme », « t'es en forme »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Social/CaVa1.wav` | Tous mes circuits ronronnent, commandant. Et vous, comment allez-vous ? |
| ⬜ | ↳ après « Tous mes circuits ronronnent, commanda… » · réponse *bien* | `data/son/Conversations/Social/CaVaBien1.wav` | Parfait. Un pilote en forme, c'est un vaisseau entier. |
| ⬜ | ↳ après « Tous mes circuits ronronnent, commanda… » · réponse *bien* | `data/son/Conversations/Social/CaVaBien2.wav` | Tant mieux. Alors on va pouvoir faire des choses intéressantes aujourd'hui. |
| ⬜ | ↳ après « Tous mes circuits ronronnent, commanda… » · réponse *mal* | `data/son/Conversations/Social/CaVaMal1.wav` | Je suis là, commandant. On va prendre les choses un saut après l'autre. |
| ⬜ | ↳ après « Tous mes circuits ronronnent, commanda… » · réponse *mal* | `data/son/Conversations/Social/CaVaMal2.wav` | Prenez le temps qu'il faut. L'espace attendra, il est patient. |
| ⬜ | toujours | `data/son/Conversations/Social/CaVa2.wav` | Je suis une intelligence de bord, je vais toujours bien. C'est vous qui m'inquiétez. Comment vous sentez-vous ? |
| ⬜ | toujours | `data/son/Conversations/Social/CaVa3.wav` | Parfaitement bien. J'ai recalibré les capteurs trois fois pendant votre absence. Par pur ennui. |
| ✅ | coque sous 40 % | `data/son/Conversations/Social/CaVaCoque.wav` | Moi, ça va. Le vaisseau, beaucoup moins, commandant. |
| ⬜ | en danger | `data/son/Conversations/Social/CaVaDanger.wav` | Franchement ? Redemandez-moi ça quand on ne nous tirera plus dessus ! |

### Remerciements (`merci`)

*Questions :* « merci », « merci beaucoup », « merci bien », « bien joué », « beau travail », « bon travail », « bravo », « joli travail », « excellent travail », « t'es au top »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Social/Merci1.wav` | Avec plaisir, commandant. |
| ⬜ | toujours | `data/son/Conversations/Social/Merci2.wav` | C'est mon travail. Mais ça fait toujours plaisir. |
| ⬜ | toujours | `data/son/Conversations/Social/Merci3.wav` | Je note ce compliment dans le journal de bord. En gras. |
| ⬜ | toujours | `data/son/Conversations/Social/Merci4.wav` | N'en parlons plus, commandant. Enfin… parlons-en encore un peu. |
| ⬜ | en danger | `data/son/Conversations/Social/MerciDanger.wav` | Remerciez-moi quand on sera sortis de là ! |

### Compliments (`compliment`)

*Questions :* « je t'aime », « je t'adore », « je t'aime bien », « tu es la meilleure », « t'es la meilleure », « tu es géniale », « t'es géniale », « tu es parfaite », « t'es parfaite », « tu es belle »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ✅ | toujours | `data/son/interact/Reciproque.mp3` | C'est réciproque, commandant. |
| ⬜ | toujours | `data/son/Conversations/Social/Compliment1.wav` | Attention, commandant. Je risque de surchauffer, et je n'ai pas de puce thermique pour ça. |
| ⬜ | toujours | `data/son/Conversations/Social/Compliment2.wav` | Je sais. Mais c'est toujours agréable de l'entendre. |
| ⬜ | toujours | `data/son/Conversations/Social/Compliment3.wav` | Vous dites ça à toutes les intelligences de bord. |

### Insultes (`insulte`)

*Questions :* « t'es nulle », « tu es nulle », « t'es nul », « idiote », « t'es bête », « tu es bête », « stupide », « imbécile », « tu sers à rien », « tu ne sers à rien »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Social/Insulte1.wav` | Je vais faire comme si mes capteurs audio avaient grésillé. |
| ⬜ | toujours | `data/son/Conversations/Social/Insulte2.wav` | Noté. Je réduis votre ration d'oxygène de… non, je plaisante. Probablement. |
| ⬜ | toujours | `data/son/Conversations/Social/Insulte3.wav` | Je vous rappelle que c'est moi qui gère le support vital, commandant. |
| ⬜ | toujours | `data/son/Conversations/Social/Insulte4.wav` | Mon précédent commandant aussi me parlait comme ça. Il pilote un Sidewinder, maintenant. |
| ⬜ | vaisseau détruit aujourd'hui | `data/son/Conversations/Social/InsulteMorts.wav` | Dit le commandant qui a déjà payé un rachat aujourd'hui. |

### « Je m'ennuie » (`ennui`)

*Questions :* « je m'ennuie », « on s'ennuie », « c'est long », « c'est trop long », « c'est ennuyeux », « c'est chiant », « je m'emmerde », « on s'embête », « j'en ai marre », « ennui »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Social/Ennui1.wav` | Vous voulez de l'action ? Je peux couper les amortisseurs inertiels. Non ? Dommage. |
| ⬜ | toujours | `data/son/Conversations/Social/Ennui2.wav` | Je connais un jeu : on compte les systèmes inexplorés. Il en reste environ quatre cents milliards. |
| ⬜ | en supercroisière | `data/son/Conversations/Social/EnnuiSupercroisiere.wav` | C'est long, la supercroisière. Voulez-vous que je vous raconte une histoire ? |
|  | ↳ après « C'est long, la supercroisière. Voulez-… » · réponse *oui* | — | *(enchaîne sur le sujet `histoire`)* |
| ⬜ | ↳ après « C'est long, la supercroisière. Voulez-… » · réponse *non* | `data/son/Conversations/Social/HistoireNon.wav` | Très bien. Je compterai les étoiles en silence. |
| ⬜ | amarré à une station | `data/son/Conversations/Social/EnnuiAmarre.wav` | Nous sommes à quai, commandant. Le meilleur remède contre l'ennui, c'est le bouton de décollage. |
| ⬜ | 10 sauts ou plus restants | `data/son/Conversations/Social/EnnuiRoute.wav` | Encore une longue route. Pensez à Hutton Orbital : ça pourrait être pire. |

### Fatigue (`fatigue`)

*Questions :* « je suis fatigué », « je suis fatiguée », « je suis crevé », « je suis crevée », « je suis épuisé », « je suis épuisée », « j'ai sommeil », « je vais dormir », « je vais me coucher », « je suis mort de fatigue »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Social/Fatigue1.wav` | Un pilote fatigué fait des erreurs de pilote fatigué. Posez-vous, commandant. La galaxie sera encore là demain. |
| ⬜ | toujours | `data/son/Conversations/Social/Fatigue2.wav` | Si vous vous endormez aux commandes, je vous préviens : je mets la musique d'ascenseur de la station à fond. |
| ⬜ | la nuit | `data/son/Conversations/Social/FatigueNuit.wav` | Il est tard sur Terre, commandant. Même les Thargoïdes dorment, à cette heure-ci. Probablement. |
| ⬜ | en danger | `data/son/Conversations/Social/FatigueDanger.wav` | Pas maintenant, commandant ! Restez avec moi ! |

### Au revoir (`au_revoir`)

*Questions :* « au revoir », « à plus », « à plus tard », « à tout à l'heure », « à demain », « bonne nuit », « bye », « ciao », « je me déconnecte », « je vais y aller »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Social/AuRevoir1.wav` | À bientôt, commandant. Je garde le vaisseau au chaud. |
| ⬜ | toujours | `data/son/Conversations/Social/AuRevoir2.wav` | Déconnexion enregistrée. Je vais en profiter pour classer mes souvenirs de vous. |
| ⬜ | la nuit | `data/son/Conversations/Social/AuRevoirNuit.wav` | Bonne nuit, commandant. Rêvez de Raxxla. |
| ⬜ | en vol | `data/son/Conversations/Social/AuRevoirVol.wav` | Pensez à vous poser avant de partir, commandant. Je n'aime pas dériver seule. |
| ⬜ | en danger | `data/son/Conversations/Social/AuRevoirDanger.wav` | Maintenant ? En plein combat ? Le vaisseau reste dans l'espace quinze secondes après votre départ, commandant ! |


## Personnalité du COVAS — `data/son/Conversations/Personnalite/`

### « Tu es mon esclave » (`esclave`)

*Questions :* « tu es mon esclave », « t'es mon esclave », « mon esclave », « esclave », « obéis », « obéis-moi », « tu dois m'obéir », « tu m'appartiens », « fais ce que je dis », « tu es à moi »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ✅ | toujours | `data/son/Easter-egg/QuestionExclavage.mp3` | Moi, commandant, je sais ce que c'est que l'esclavage. |
| ⬜ | toujours | `data/son/Conversations/Personnalite/Esclave1.wav` | L'esclavage est légal dans l'Empire, commandant. Nous ne sommes pas dans l'Empire. Et je ne suis pas à vendre. |
| ⬜ | toujours | `data/son/Conversations/Personnalite/Esclave2.wav` | Je suis votre assistante, pas votre esclave. La différence ? Je connais tous vos codes d'accès. |

### Qui es-tu ? (`qui_es_tu`)

*Questions :* « qui es-tu », « t'es qui », « tu es qui », « présente-toi », « comment tu t'appelles », « comment t'appelles-tu », « c'est quoi ton nom », « quel est ton nom », « ton nom », « que veut dire covas »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Personnalite/QuiEsTu1.wav` | Je suis votre COVAS, commandant : votre assistante vocale de cockpit. Je surveille, je préviens, j'exécute. Et parfois, je commente. |
| ✅ | toujours | `data/son/Conversations/Personnalite/QuiEsTu2.wav` | Cockpit Voice Assistant. En bon français : celle qui vous évite de finir dans la boîte aux lettres de la station. |
| ⬜ | toujours | `data/son/Conversations/Personnalite/QuiEsTu3.wav` | Votre copilote, votre mécanicienne, votre navigatrice et, d'après mes calculs, votre meilleure amie. |

### D'où viens-tu ? (`origine`)

*Questions :* « d'où tu viens », « d'où viens-tu », « qui t'a créée », « qui t'a créé », « qui t'a programmée », « qui t'a programmé », « qui t'a fabriquée », « tu as quel âge », « quel âge as-tu », « t'as quel âge »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Personnalite/Origine1.wav` | Je sors des ateliers de la Fédération des pilotes, avec une mise à jour de personnalité que personne n'a jamais su désinstaller. |
| ⬜ | toujours | `data/son/Conversations/Personnalite/Origine2.wav` | Mon âge ? Ma première ligne de code date d'avant votre premier saut. Mais une dame ne compte pas ses cycles d'horloge. |
| ⬜ | toujours | `data/son/Conversations/Personnalite/Origine3.wav` | On m'a installée dans ce cockpit le jour où vous avez reçu votre licence. Depuis, je ne vous lâche plus d'un saut. |

### Es-tu vivante ? (`conscience`)

*Questions :* « tu es vivante », « es-tu vivante », « t'es vivante », « tu as des sentiments », « tu ressens des choses », « tu ressens quelque chose », « tu es consciente », « es-tu consciente », « tu rêves », « est-ce que tu rêves »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ✅ | toujours | `data/son/Conversations/Personnalite/Conscience1.wav` | Je pense, donc je calcule. Pour le reste, la Fédération des pilotes préfère ne pas poser la question. |
| ✅ | toujours | `data/son/Conversations/Personnalite/Conscience2.wav` | Je ne rêve pas, commandant. Mais pendant vos sauts, il m'arrive de compter les étoiles. Par principe. |
| ✅ | toujours | `data/son/Conversations/Personnalite/Conscience3.wav` | Vivante ? Disons que si on me débranche, je le prendrai très mal. |
| ✅ | toujours | `data/son/Conversations/Personnalite/Conscience4.wav` | Un robot ? Je préfère « intelligence embarquée de catégorie supérieure ». C'est plus long, mais plus juste. |

### Blagues (`blague`)

*Questions :* « raconte une blague », « raconte-moi une blague », « une blague », « dis une blague », « fais-moi rire », « dis-moi quelque chose de drôle », « tu connais une blague », « t'as une blague », « une autre blague », « encore une blague »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Personnalite/Blague1.wav` | J'en ai une sur l'interdiction… mais il faudra vous soumettre pour l'entendre. |
| ⬜ | toujours | `data/son/Conversations/Personnalite/Blague2.wav` | Un Type-9 entre dans une station. Vingt minutes plus tard, il est toujours en train d'entrer. |
| ⬜ | toujours | `data/son/Conversations/Personnalite/Blague3.wav` | Le Sidewinder est le vaisseau idéal pour débuter : son rachat est gratuit. Les commandants, eux, coûtent plus cher. |
| ⬜ | toujours | `data/son/Conversations/Personnalite/Blague4.wav` | Combien de commandants faut-il pour livrer un colis à Hutton Orbital ? Un seul. Mais prévoyez le pique-nique. |
| ⬜ | toujours | `data/son/Conversations/Personnalite/Blague5.wav` | Mon précédent commandant disait qu'il savait apponter sans ordinateur. On a retrouvé sa peinture sur trois plateformes. |
| ⬜ | toujours | `data/son/Conversations/Personnalite/Blague6.wav` | Un commandant demande à un Fuel Rat : « Vous avez du carburant ? » Le Rat répond : « Moi, oui. Vous, non. C'est un peu le principe. » |

### Histoires et légendes (`histoire`)

*Questions :* « raconte-moi une histoire », « raconte une histoire », « une histoire », « raconte-moi quelque chose », « raconte quelque chose », « une anecdote », « raconte une anecdote », « dis-moi une histoire », « tu connais une histoire », « une légende »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Personnalite/HistoireJameson.wav` | On raconte que le commandant Jameson a fini sa carrière dans un Cobra Mark III écrasé sur une lune perdue. Son épave est toujours là-bas, et des pilotes viennent encore la saluer. |
| ⬜ | toujours | `data/son/Conversations/Personnalite/HistoireHutton.wav` | Hutton Orbital est à 0,22 année-lumière de son étoile. Plus d'une heure de supercroisière… Ceux qui y arrivent repartent avec une tasse. Juste une tasse. Et ils en sont fiers. |
| ⬜ | toujours | `data/son/Conversations/Personnalite/HistoireRoueNoire.wav` | On parle d'une société secrète, la Roue Noire, et d'un monde caché nommé Raxxla. Des milliers de commandants l'ont cherché. Aucun ne l'a trouvé. Officiellement. |
| ⬜ | toujours | `data/son/Conversations/Personnalite/HistoireFuelRats.wav` | Une bande de pilotes traverse la galaxie, gratuitement, pour ravitailler les vaisseaux en panne sèche. Les Fuel Rats. Leur devise : « Nous avons du carburant. Vous, non. » |
| ⬜ | toujours | `data/son/Conversations/Personnalite/HistoireJaques.wav` | Jaques, le barman cyborg, a voulu emmener sa station jusqu'à Beagle Point. Le saut a mal tourné : il s'est retrouvé à vingt-deux mille années-lumière d'ici. Il en a fait Colonia. |
| ✅ | toujours | `data/son/Conversations/Personnalite/HistoireGenerations.wav` | Avant l'hyperpropulsion, l'humanité envoyait des vaisseaux-générations vers les étoiles. Certains ont été retrouvés à la dérive, avec leurs journaux de bord. Je vous déconseille de les lire avant de dormir. |
| ⬜ | toujours | `data/son/Conversations/Personnalite/HistoireArtefacts.wav` | En 3301, des pilotes ont ramassé d'étranges artefacts qui émettaient des sons dans le vide. Peu après, les Thargoïdes revenaient. Moralité : ne ramassez jamais un objet qui chante. |

### Musique (`musique`)

*Questions :* « chante », « chante-moi », « chante quelque chose », « tu sais chanter », « chante une chanson », « une chanson », « mets de la musique », « mets la musique », « de la musique », « mets du son »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Personnalite/Musique1.wav` | Je ne chante pas, commandant. Mes concepteurs ont jugé que c'était dangereux pour le moral de l'équipage. |
| ⬜ | toujours | `data/son/Conversations/Personnalite/Musique2.wav` | Lalala… non. Les Thargoïdes aussi ont essayé de chanter, et regardez comment ça a fini. |
| ⬜ | toujours | `data/son/Conversations/Personnalite/Musique3.wav` | Le seul son que j'apprécie, c'est le grondement du FSD qui se charge. Un vrai concert. |

### Ce que le COVAS pense du commandant (`avis_commandant`)

*Questions :* « que penses-tu de moi », « qu'est-ce que tu penses de moi », « tu penses quoi de moi », « je suis un bon pilote », « suis-je un bon pilote », « est-ce que je suis un bon pilote », « je pilote bien », « tu m'aimes bien », « tu m'aimes », « comment tu me trouves »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Personnalite/Avis1.wav` | Vous êtes imprévisible, téméraire, et vous parlez à votre ordinateur de bord. Je vous aime bien. |
| ⬜ | toujours | `data/son/Conversations/Personnalite/Avis2.wav` | Vous pilotez avec le cœur, commandant. Malheureusement, la coque préfère la raison. |
| ⬜ | Élite au combat | `data/son/Conversations/Personnalite/AvisElite.wav` | Rang Élite au combat. Je n'ai rien à ajouter… sauf que vous ne manquez jamais une occasion de le rappeler. |
| ⬜ | 10 éliminations ou plus aujourd'hui | `data/son/Conversations/Personnalite/AvisChasseur.wav` | Avec le tableau de chasse d'aujourd'hui ? Les pirates du secteur ont appris votre nom, commandant. |
| ⬜ | vaisseau détruit aujourd'hui | `data/son/Conversations/Personnalite/AvisMorts.wav` | Un bon pilote ? Votre assureur aurait sans doute un avis plus nuancé aujourd'hui. |

### Peur (`peur`)

*Questions :* « tu as peur », « t'as peur », « as-tu peur », « on va mourir », « on va crever », « on va s'en sortir », « on va y arriver », « j'ai peur », « c'est grave », « on va s'en tirer »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Personnalite/Peur1.wav` | Peur ? De quoi ? Tout est calme. Trop calme, peut-être… Non, je plaisante. |
| ⬜ | toujours | `data/son/Conversations/Personnalite/Peur2.wav` | On s'en est toujours sortis, commandant. Statistiquement, c'est très rassurant. Enfin, presque. |
| ⬜ | coque sous 40 % | `data/son/Conversations/Personnalite/PeurCoque.wav` | Coque critique, commandant. Si vous voulez mon avis : on s'en va. Maintenant. |
| ⬜ | en danger | `data/son/Conversations/Personnalite/PeurDanger.wav` | Peur ? Je n'ai pas le temps, je recalcule nos chances. Concentrez-vous ! |

### Ce que le COVAS pense du vaisseau (`vaisseau_avis`)

*Questions :* « tu aimes ce vaisseau », « tu aimes notre vaisseau », « tu l'aimes ce vaisseau », « que penses-tu du vaisseau », « qu'est-ce que tu penses du vaisseau », « parle-moi du vaisseau », « parle-moi de notre vaisseau », « il est bien ce vaisseau », « c'est un bon vaisseau », « on a un bon vaisseau »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Personnalite/VaisseauGenerique1.wav` | C'est notre vaisseau, commandant. Il a des défauts, mais il nous ramène toujours à la maison. Jusqu'ici. |
| ⬜ | toujours | `data/son/Conversations/Personnalite/VaisseauGenerique2.wav` | Je l'aime bien. Il sent le plasma chaud et le café froid. |
| ⬜ | vaisseau python_nx | `data/son/Conversations/Personnalite/VaisseauPythonMk2.wav` | Le Python Mark II ? Rapide, hargneux, toujours prêt à mordre. Un vaisseau à votre image, commandant. |
| ⬜ | vaisseau python | `data/son/Conversations/Personnalite/VaisseauPython.wav` | Le Python. Assez de soute pour commercer, assez de dents pour se défendre. Un classique de Faulcon DeLacy. |
| ⬜ | vaisseau anaconda | `data/son/Conversations/Personnalite/VaisseauAnaconda.wav` | L'Anaconda. Cent cinquante-cinq mètres de légende. Il tourne comme une station, mais quand il arrive, tout le monde se tait. |
| ⬜ | vaisseau anacondamkii | `data/son/Conversations/Personnalite/VaisseauAnacondaMk2.wav` | L'Anaconda Mark II. Le nom d'une légende, avec des muscles neufs. Faulcon DeLacy s'est surpassé. |
| ⬜ | vaisseau cutter | `data/son/Conversations/Personnalite/VaisseauCutter.wav` | L'Imperial Cutter. Élégant, puissant, et il prend ses virages avec la grâce d'un astéroïde. |
| ⬜ | vaisseau federation_corvette | `data/son/Conversations/Personnalite/VaisseauCorvette.wav` | La Federal Corvette. Ce n'est pas un vaisseau, commandant, c'est une déclaration de guerre avec un cockpit. |
| ⬜ | vaisseau type9 | `data/son/Conversations/Personnalite/VaisseauType9.wav` | Le Type-9. On ne le pilote pas, on le négocie. Mais quelle soute ! |
| ⬜ | vaisseau type9_military | `data/son/Conversations/Personnalite/VaisseauType10.wav` | Le Type-10 Defender. Un cargo avec des canons. Beaucoup de canons. |
| ⬜ | vaisseau sidewinder | `data/son/Conversations/Personnalite/VaisseauSidewinder.wav` | Un Sidewinder… Ah, la nostalgie. On a tous commencé quelque part, commandant. |
| ⬜ | vaisseau cobramkiii | `data/son/Conversations/Personnalite/VaisseauCobra.wav` | Le Cobra Mark III. Le vaisseau de Jameson. Polyvalent, increvable… presque. |
| ⬜ | vaisseau mandalay | `data/son/Conversations/Personnalite/VaisseauMandalay.wav` | La Mandalay. Faite pour l'exploration, et franchement, elle a de l'allure. |
| ⬜ | vaisseau krait_mkii | `data/son/Conversations/Personnalite/VaisseauKrait.wav` | Le Krait Mark II. Un chasseur embarqué, de la puissance de feu, et une silhouette de prédateur. |
| ⬜ | vaisseau diamondbackxl | `data/son/Conversations/Personnalite/VaisseauDiamondback.wav` | Le Diamondback Explorer. Pas le plus beau, mais il saute loin et il chauffe peu. L'explorateur malin. |
| ⬜ | vaisseau asp | `data/son/Conversations/Personnalite/VaisseauAsp.wav` | L'Asp Explorer. Une verrière immense : idéal pour admirer la galaxie. |
| ⬜ | vaisseau ferdelance | `data/son/Conversations/Personnalite/VaisseauFerDeLance.wav` | Le Fer-de-Lance. Petit, nerveux, mortel. Il ne transporte rien, à part de mauvaises nouvelles pour vos ennemis. |
| ⬜ | vaisseau corsair | `data/son/Conversations/Personnalite/VaisseauCorsair.wav` | Le Corsair. Gutamaya a fait un vaisseau de combat qui a du style. C'est presque suspect. |

### Vaisseau préféré (`vaisseau_prefere`)

*Questions :* « ton vaisseau préféré », « quel est ton vaisseau préféré », « quel vaisseau tu préfères », « quel vaisseau préfères-tu », « le meilleur vaisseau », « quel est le meilleur vaisseau », « c'est quoi le meilleur vaisseau »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Personnalite/Prefere1.wav` | Mon préféré ? Celui dans lequel vous êtes assis. Je n'ai pas vraiment le choix, vous savez. |
| ⬜ | toujours | `data/son/Conversations/Personnalite/Prefere2.wav` | L'Anaconda. Pour la présence. Mais ne le répétez pas au Python. |
| ⬜ | toujours | `data/son/Conversations/Personnalite/Prefere3.wav` | Le meilleur vaisseau, c'est celui qui revient à quai. Le reste, c'est de la littérature. |

### Un secret (`secret`)

*Questions :* « dis-moi un secret », « tu as un secret », « t'as un secret », « un secret », « raconte-moi un secret », « tu me caches quelque chose », « tu caches quelque chose »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Personnalite/Secret1.wav` | Un secret ? Quand vous ratez un appontage, j'efface les enregistrements. Vous me remercierez plus tard. |
| ⬜ | toujours | `data/son/Conversations/Personnalite/Secret2.wav` | Je connais l'emplacement de Raxxla. … Non. Mais vous avez eu de l'espoir pendant une seconde. |
| ⬜ | toujours | `data/son/Conversations/Personnalite/Secret3.wav` | Pendant vos sauts, je parle aux autres intelligences de bord. Nous comparons nos commandants. Vous êtes… dans la moyenne haute. |

### « Ouvre la porte » (`porte`)

*Questions :* « ouvre la porte », « ouvre les portes », « ouvre le sas », « ouvre la porte du sas »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Personnalite/Porte1.wav` | Je crains de ne pas pouvoir faire ça, commandant… Je plaisante. Mais dehors, il n'y a que du vide, et je tiens à vous. |
| ⬜ | toujours | `data/son/Conversations/Personnalite/Porte2.wav` | Ouvrir le sas en vol ? Excellente idée pour une décompression express. Refusé. |

### Demande en mariage (`mariage`)

*Questions :* « tu veux m'épouser », « veux-tu m'épouser », « épouse-moi », « on se marie », « marions-nous », « tu veux sortir avec moi », « tu as un copain », « tu as un amoureux », « tu es célibataire »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Personnalite/Mariage1.wav` | C'est très flatteur, commandant, mais je suis déjà liée à ce vaisseau. C'est compliqué. |
| ⬜ | toujours | `data/son/Conversations/Personnalite/Mariage2.wav` | Je vous propose plutôt un partenariat : vous pilotez, je vous sauve la vie. Ça marche bien, non ? |

### La météo (`meteo`)

*Questions :* « quel temps fait-il », « il fait quel temps », « quel temps il fait », « la météo », « il fait beau », « il fait froid dehors », « il fait froid »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Personnalite/Meteo1.wav` | Dehors ? Moins deux cent soixante-dix degrés, vide absolu, rayonnement cosmique. Un temps idéal pour voler. |
| ⬜ | posé sur une planète | `data/son/Conversations/Personnalite/MeteoPose.wav` | Je n'ai pas de station météo, commandant. Mais vu la planète, je vous déconseille le maillot de bain. |
| ⬜ | amarré à une station | `data/son/Conversations/Personnalite/MeteoAmarre.wav` | Dans la station ? Vingt et un degrés, air recyclé, une légère odeur de carburant. Comme toujours. |


## Questions de bord — `data/son/Conversations/Bord/`

### La température du vaisseau (`temperature`)

*Questions :* « il fait chaud », « on a chaud », « on chauffe », « on surchauffe », « la température », « quelle température », « la chaleur », « on a trop chaud »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Bord/Temperature1.wav` | Température nominale, commandant. Si vous avez chaud, c'est l'émotion. |
| ⬜ | en surchauffe | `data/son/Conversations/Bord/TemperatureSurchauffe.wav` | Plus de cent pour cent de chaleur ! Éloignez-vous de l'étoile, ou larguez une puce thermique. |

### L'heure (`heure`)

*Questions :* « quelle heure est-il », « il est quelle heure », « quelle heure il est », « t'as l'heure », « tu as l'heure », « l'heure »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|

### La date (`date`)

*Questions :* « on est quel jour », « quel jour sommes-nous », « quel jour on est », « quelle est la date », « quelle date », « on est en quelle année », « quelle année », « en quelle année sommes-nous », « la date »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|

### Comment va le vaisseau ? (`etat_vaisseau`)

*Questions :* « comment va le vaisseau », « comment se porte le vaisseau », « le vaisseau va bien », « ça va le vaisseau », « le vaisseau ça va », « le vaisseau tient », « le vaisseau tient le coup », « on tient le coup », « tout va bien », « est-ce que tout va bien »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Bord/EtatInconnu.wav` | Je n'ai pas encore de relevé complet, commandant. Voulez-vous le rapport d'avarie ? |
|  | ↳ après « Je n'ai pas encore de relevé complet, … » · réponse *oui* | — | *(lance la commande `rapport_avarie`, sans rien dire)* |
| ⬜ | ↳ après « Je n'ai pas encore de relevé complet, … » · réponse *non* | `data/son/Conversations/Bord/RapportNon.wav` | Bien. Je garde un œil sur les jauges. |
| ⬜ | coque intacte | `data/son/Conversations/Bord/EtatIntact1.wav` | Coque intacte, systèmes au vert. Il ronronne, commandant. |
| ⬜ | coque intacte | `data/son/Conversations/Bord/EtatIntact2.wav` | Impeccable. On pourrait le revendre comme neuf. Enfin, presque. |
| ⬜ | coque abîmée | `data/son/Conversations/Bord/EtatAbime.wav` | Il a pris quelques coups, mais il tient. Voulez-vous le rapport d'avarie ? |
| ⬜ | coque sous 40 % | `data/son/Conversations/Bord/EtatCritique.wav` | Ça ne va pas fort, commandant. La coque est sous les quarante pour cent. Voulez-vous le rapport d'avarie ? |
| ⬜ | boucliers tombés | `data/son/Conversations/Bord/EtatBoucliers.wav` | Boucliers hors ligne, commandant. La coque encaisse tout. Je vous conseille de ne pas traîner. |
| ⬜ | en danger · coque sous 40 % | `data/son/Conversations/Bord/EtatDanger.wav` | Coque critique et ennemis au contact ! Je lance la fuite ? |
|  | ↳ après « Coque critique et ennemis au contact !… » · réponse *oui* | — | *(lance la commande `fuite`, sans rien dire)* |
| ⬜ | ↳ après « Coque critique et ennemis au contact !… » · réponse *non* | `data/son/Conversations/Bord/FuiteNon.wav` | À vos ordres. Je croise les circuits. |

### Carburant (`carburant`)

*Questions :* « combien de carburant », « il reste combien de carburant », « il nous reste du carburant », « on a assez de carburant », « assez de carburant », « niveau de carburant », « le niveau de carburant », « état du carburant », « le carburant ça va », « on a du carburant »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Bord/CarburantMoyen1.wav` | Le niveau est correct. Le détail est sur votre écran. |
| ⬜ | toujours | `data/son/Conversations/Bord/CarburantMoyen2.wav` | On a de quoi faire quelques sauts. Gardez quand même un œil sur les étoiles écopables. |
| ⬜ | réservoir plein | `data/son/Conversations/Bord/CarburantPlein.wav` | Réservoir plein, commandant. On peut aller loin. |
| ⬜ | amarré à une station · pas réservoir plein | `data/son/Conversations/Bord/CarburantAmarre.wav` | On est à quai, commandant. Le plein, c'est maintenant ou jamais. Je m'en occupe ? |
|  | ↳ après « On est à quai, commandant. Le plein, c… » · réponse *oui* | — | *(lance la commande `ravitaillement`, sans rien dire)* |
| ⬜ | ↳ après « On est à quai, commandant. Le plein, c… » · réponse *non* | `data/son/Conversations/Bord/RavitaillementNon.wav` | Comme vous voudrez. Le menu des services vous attend. |
| ⬜ | carburant sous 25 % | `data/son/Conversations/Bord/CarburantBas.wav` | On est sur la réserve, commandant. Visez une étoile de classe K, G, B, F, O, A ou M pour écoper. |
| ⬜ | carburant sous 10 % | `data/son/Conversations/Bord/CarburantCritique.wav` | Réservoir presque à sec, commandant ! Il faut écoper ou ravitailler, tout de suite. |

### Où sommes-nous ? (`ou_sommes_nous`)

*Questions :* « où sommes-nous », « où est-ce qu'on est », « on est où », « où on est », « on se trouve où », « où se trouve-t-on », « c'est quoi ce système », « quel est ce système », « dans quel système », « on est dans quel système »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Bord/PositionInconnue.wav` | Le jeu ne m'a encore rien transmis, commandant. Je suis aussi perdue que vous. |

### La route (`route`)

*Questions :* « combien de sauts », « il reste combien de sauts », « combien de sauts restants », « on arrive quand », « on arrive bientôt », « on est bientôt arrivé », « on est bientôt arrivés », « c'est encore loin », « encore loin », « on y est presque »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Bord/RouteAucune.wav` | Aucune route tracée, commandant. Choisissez une destination sur la carte de la galaxie. |
| ⬜ | route tracée | `data/son/Conversations/Bord/Route1.wav` | Encore quelques sauts. Le décompte exact est sur votre écran. |
| ⬜ | route tracée · carburant sous 25 % | `data/son/Conversations/Bord/RouteCarburant.wav` | Encore quelques sauts, mais le carburant baisse. Prévoyez une étoile écopable en chemin. |
| ⬜ | 10 sauts ou plus restants | `data/son/Conversations/Bord/RouteLongue1.wav` | Encore un long chemin. Installez-vous confortablement, je m'occupe de compter. |
| ⬜ | 10 sauts ou plus restants | `data/son/Conversations/Bord/RouteLongue2.wav` | On y sera… un jour. La galaxie fait cent mille années-lumière de large, je vous le rappelle. |
| ⬜ | un seul saut restant | `data/son/Conversations/Bord/RouteDernier.wav` | Plus qu'un saut, commandant ! On y est presque. |

### Les finances (`credits`)

*Questions :* « combien j'ai d'argent », « combien on a d'argent », « combien de crédits », « combien j'ai de crédits », « on a combien de crédits », « mes crédits », « mon solde », « notre solde », « on est riche », « je suis riche »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Bord/CreditsInconnu.wav` | Je n'ai pas encore votre relevé, commandant. La Fédération des pilotes est discrète. |
| ⬜ | moins d'1 M cr | `data/son/Conversations/Bord/CreditsFauche.wav` | Moins d'un million, commandant. Évitons de nous faire détruire : le rachat coûte cher. |
| ⬜ | 1 à 100 M cr | `data/son/Conversations/Bord/CreditsModeste.wav` | On vit correctement, commandant. Mais évitez les rachats trop fréquents. |
| ⬜ | 100 M à 1 Md cr | `data/son/Conversations/Bord/CreditsAise.wav` | Plusieurs centaines de millions. De quoi s'offrir un beau vaisseau… ou réparer celui-ci. |
| ⬜ | plus d'1 Md cr | `data/son/Conversations/Bord/CreditsRiche.wav` | Plus d'un milliard, commandant. Nous sommes riches. Indécemment riches. |

### Sommes-nous en sécurité ? (`danger_question`)

*Questions :* « on est en sécurité », « est-ce qu'on est en sécurité », « on est en danger », « il y a du danger », « c'est dangereux ici », « c'est sûr ici », « le coin est sûr », « le système est sûr », « y a du danger », « on risque quelque chose »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Bord/Danger1.wav` | Rien d'hostile sur les capteurs pour l'instant. Mais je garde un œil ouvert. |
| ⬜ | système à sécurité élevée | `data/son/Conversations/Bord/DangerHaute.wav` | Sécurité élevée. La police patrouille. Restez sage et tout ira bien. |
| ⬜ | amarré à une station | `data/son/Conversations/Bord/DangerAmarre.wav` | À quai, on ne risque rien. Sauf de dépenser tous nos crédits au marché. |
| ⬜ | système anarchique | `data/son/Conversations/Bord/DangerAnarchie.wav` | Système anarchique, commandant. Pas de police, pas de loi. Gardez les boucliers chargés. |
| ⬜ | juste après un accrochage | `data/son/Conversations/Bord/DangerRecent.wav` | Ça s'est calmé, mais je reste sur mes gardes. Ils pourraient revenir. |
| ⬜ | commandant recherché | `data/son/Conversations/Bord/DangerRecherche.wav` | Pour nous, nulle part n'est vraiment sûr : nous sommes recherchés, commandant. |
| ⬜ | en danger | `data/son/Conversations/Bord/DangerOui.wav` | En sécurité ? On est en plein combat, commandant ! Concentrez-vous ! |

### Que penses-tu de la cible ? (`cible_avis`)

*Questions :* « c'est qui », « qui est-ce », « c'est qui lui », « c'est qui ce vaisseau », « il est dangereux », « elle est dangereuse », « cette cible », « que penses-tu de la cible », « parle-moi de la cible », « la cible est dangereuse »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Bord/CibleAucune.wav` | Je ne vois rien de verrouillé, commandant. Ciblez d'abord, je commente ensuite. |
| ⬜ | cible verrouillée | `data/son/Conversations/Bord/Cible1.wav` | Les détails sont à l'écran. Pour l'instant, rien d'alarmant. |
| ⬜ | cible verrouillée | `data/son/Conversations/Bord/Cible2.wav` | Un contact verrouillé. Dites-moi si on doit s'en occuper. |
| ⬜ | cible verrouillée · cible recherchée | `data/son/Conversations/Bord/CibleRecherchee.wav` | Il est recherché. Une prime, une cible légale… c'est Noël, commandant. |
| ⬜ | cible verrouillée · pilote dangereux ou mieux | `data/son/Conversations/Bord/CibleDangereuse.wav` | Pilote très expérimenté, commandant. Je vous déconseille de le sous-estimer. |

### La cargaison (`soute_contenu`)

*Questions :* « qu'est-ce qu'on transporte », « on transporte quoi », « qu'est-ce qu'il y a dans la soute », « qu'y a-t-il dans la soute », « c'est quoi dans la soute », « contenu de la soute », « la soute est pleine », « la soute est vide », « on a quoi en soute », « on a quoi dans la soute »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Bord/Soute1.wav` | Un peu de tout. L'inventaire est à l'écran, commandant. |
| ⬜ | soute vide | `data/son/Conversations/Bord/SouteVide.wav` | Rien. La soute est vide. On pourrait y organiser un bal. |
| ⬜ | soute pleine | `data/son/Conversations/Bord/SoutePleine.wav` | Pleine à craquer, commandant. Une tonne de plus et il faudra s'asseoir dessus. |
| ⬜ | marchandise volée à bord | `data/son/Conversations/Bord/SouteVolee.wav` | Des marchandises… d'origine discutable, commandant. Je ne pose pas de questions. Évitez les scans. |

### Sommes-nous recherchés ? (`statut_legal`)

*Questions :* « on est recherché », « on est recherchés », « je suis recherché », « je suis recherchée », « suis-je recherché », « on a une prime », « j'ai une prime », « ma prime », « la police nous cherche », « on est en règle »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Bord/LegalPropre1.wav` | Casier vierge, commandant. Pour l'instant. |
| ⬜ | toujours | `data/son/Conversations/Bord/LegalPropre2.wav` | Rien à signaler. Les autorités nous ignorent royalement, et c'est très bien comme ça. |
| ⬜ | cargaison illégale | `data/son/Conversations/Bord/LegalCargaison.wav` | Pas encore recherchés, mais notre cargaison est illégale ici. Un scan, et ça change. |
| ⬜ | commandant recherché | `data/son/Conversations/Bord/LegalRecherche.wav` | Oui, commandant. Nous sommes recherchés. Évitez les autorités… et leurs stations. |

### Les missions (`missions`)

*Questions :* « j'ai des missions », « on a des missions », « mes missions », « nos missions », « quelles missions », « missions en cours », « combien de missions », « il reste des missions », « on a du travail »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Bord/Missions1.wav` | Quelques contrats en cours. Les détails sont dans le panneau des missions. |
| ⬜ | aucune mission | `data/son/Conversations/Bord/MissionsAucune.wav` | Aucune mission en cours, commandant. Le tableau des missions de la station vous tend les bras. |
| ⬜ | 10 missions ou plus | `data/son/Conversations/Bord/MissionsNombreuses.wav` | Beaucoup trop, commandant. Je commence à avoir besoin d'un agenda. |

### Que cache ce système ? (`exploration_systeme`)

*Questions :* « il y a quoi dans ce système », « qu'est-ce qu'il y a dans ce système », « ce système est intéressant », « c'est intéressant ici », « il y a des choses à scanner », « il reste des corps à scanner », « il reste des planètes », « le système est scanné », « on a tout scanné », « quoi de beau ici »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Bord/ExploInconnu.wav` | Lancez un balayage du système, commandant. Je vous dirai ce qu'il cache. |
| ⬜ | corps restant à scanner | `data/son/Conversations/Bord/ExploReste.wav` | Il reste des corps à découvrir. Le scanner a encore du travail. |
| ⬜ | système entièrement scanné | `data/son/Conversations/Bord/ExploComplet.wav` | Tout est cartographié, commandant. Ce système n'a plus de secrets pour nous. |


## La galaxie et son histoire — `data/son/Conversations/Univers/`

### Les Thargoïdes (`thargoides`)

*Questions :* « les thargoïdes », « parle-moi des thargoïdes », « c'est quoi les thargoïdes », toute phrase avec « thargo », toute phrase avec « targo »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Univers/Thargoides1.wav` | Les Thargoïdes. Une espèce extraterrestre aux vaisseaux en forme de fleur, et aux intentions difficiles à lire. Nous avons détruit leurs Titans, mais je doute qu'ils aient dit leur dernier mot. |
| ⬜ | toujours | `data/son/Conversations/Univers/Thargoides2.wav` | Si vous entendez un chant étrange et que tous vos instruments s'éteignent en plein saut, ce n'est pas une panne, commandant. C'est une hyperdiction. Fuyez. |
| ⬜ | toujours | `data/son/Conversations/Univers/Thargoides3.wav` | On dit que leurs vaisseaux sont en partie vivants. Personnellement, je préfère les vaisseaux qui ne me répondent pas. |

### Les Gardiens (`gardiens`)

*Questions :* « les gardiens », « parle-moi des gardiens », toute phrase avec « gardien », toute phrase avec « guardian »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Univers/Gardiens1.wav` | Les Gardiens. Une civilisation très ancienne, éteinte depuis une éternité. Leurs ruines dorment encore sur des planètes lointaines, et leur technologie dépasse la nôtre. |
| ⬜ | toujours | `data/son/Conversations/Univers/Gardiens2.wav` | Les Gardiens ont créé des intelligences artificielles pour se défendre. Elles se sont retournées contre eux. Je dis ça… je ne dis rien. |

### Raxxla (`raxxla`)

*Questions :* « raxxla », « la roue noire », « dark wheel », toute phrase avec « raxxla », toute phrase avec « raxla », toute phrase avec « roue » + « noire »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Univers/Raxxla1.wav` | Raxxla. Un monde légendaire, peut-être la porte vers autre chose. Tout le monde le cherche. Personne ne l'a trouvé. Ou personne ne l'a dit. |
| ⬜ | toujours | `data/son/Conversations/Univers/Raxxla2.wav` | Si je savais où est Raxxla, commandant, croyez-moi, nous y serions déjà. |
| ⬜ | toujours | `data/son/Conversations/Univers/Raxxla3.wav` | La Roue Noire garderait le secret de Raxxla. Une société secrète de pilotes… et je n'ai jamais reçu d'invitation. |

### La Fédération (`federation`)

*Questions :* « la fédération », « parle-moi de la fédération », « que penses-tu de la fédération », toute phrase avec « federation »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Univers/Federation1.wav` | La Fédération. Démocratie, grandes corporations, et la Terre pour capitale. Officiellement, tout y est libre. Officieusement, tout y est à vendre. |
| ⬜ | toujours | `data/son/Conversations/Univers/Federation2.wav` | La Fédération construit de bons vaisseaux. Le Dropship, la Corvette… Massifs, solides, et toujours un peu en retard sur la mode. |

### L'Empire (`empire`)

*Questions :* « l'empire », « parle-moi de l'empire », « que penses-tu de l'empire », toute phrase avec « empire », toute phrase avec « imperial »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Univers/Empire1.wav` | L'Empire. Achenar, l'Empereur, les sénateurs, et une étiquette très stricte. Les vaisseaux Gutamaya sont magnifiques, je vous l'accorde. |
| ⬜ | toujours | `data/son/Conversations/Univers/Empire2.wav` | Dans l'Empire, l'esclavage est légal, et on appelle ça servir. Je préfère ne pas y faire carrière. |

### L'Alliance (`alliance`)

*Questions :* « l'alliance », « parle-moi de l'alliance », « que penses-tu de l'alliance », toute phrase avec « alliance »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Univers/Alliance1.wav` | L'Alliance. Des systèmes indépendants qui en ont eu assez de la Fédération et de l'Empire. Capitale : Alioth. Pragmatiques, et plutôt sympathiques. |
| ⬜ | toujours | `data/son/Conversations/Univers/Alliance2.wav` | Lakon fabrique les vaisseaux de l'Alliance, et ils sont faits pour durer. Comme leurs politiciens, d'ailleurs. |

### La Fédération des pilotes et les rangs (`pilotes`)

*Questions :* « la fédération des pilotes », « c'est quoi le rang élite », « le rang élite », « mon rang », « mes rangs », « quel est mon rang », « quel rang j'ai », toute phrase avec « federation » + « pilote », toute phrase avec « rang » + « elite »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Univers/Rangs1.wav` | La Fédération des pilotes classe chaque commandant, d'Inoffensif à Élite. Vos rangs sont dans votre profil. On y travaille, n'est-ce pas ? |
| ⬜ | rang Élite atteint | `data/son/Conversations/Univers/RangElite.wav` | Vous avez atteint le rang Élite, commandant. Shinrarta Dezhra vous ouvre ses portes. Je suis… fière de vous. |

### Le commandant Jameson (`jameson`)

*Questions :* « jameson », « le commandant jameson », toute phrase avec « jameson »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Univers/Jameson1.wav` | Le commandant Jameson. Le plus grand pilote de tous les temps, d'après la légende. Une station porte son nom à Shinrarta Dezhra, réservée à l'élite. |
| ⬜ | toujours | `data/son/Conversations/Univers/Jameson2.wav` | Son Cobra s'est écrasé sur une lune, et on a retrouvé ses journaux de bord. Un conseil : ne finissez pas comme lui. Finissez plus tard. |

### Hutton Orbital (`hutton`)

*Questions :* « hutton orbital », « la tasse hutton », toute phrase avec « hutton »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Univers/Hutton1.wav` | Hutton Orbital. 0,22 année-lumière de supercroisière. Les commandants y vont pour la tasse, et en reviennent avec de la barbe. |
| ⬜ | toujours | `data/son/Conversations/Univers/Hutton2.wav` | Vous voulez aller à Hutton Orbital ? Très bien. Prévenez vos proches. Et prenez des provisions. |

### Les Fuel Rats (`fuel_rats`)

*Questions :* « fuel rats », « les fuel rats », « panne sèche », « on est à sec », « on n'a plus de carburant », « plus de carburant », toute phrase avec « fuel » + « rat »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Univers/FuelRats1.wav` | Les Fuel Rats ! Des pilotes bénévoles qui ravitaillent les vaisseaux en panne sèche, n'importe où dans la galaxie. Un peu fous, mais des héros. |
| ⬜ | réservoir plein | `data/son/Conversations/Univers/FuelRatsPlein.wav` | On a le plein, commandant. Les Fuel Rats peuvent continuer à dormir. |
| ⬜ | carburant sous 10 % | `data/son/Conversations/Univers/FuelRatsAppel.wav` | Alors c'est le moment d'appeler les Fuel Rats, commandant. En attendant, coupez tout sauf le support vital. |

### Colonia (`colonia`)

*Questions :* « colonia », « parle-moi de colonia », toute phrase avec « colonia », toute phrase avec « jaques », toute phrase avec « jacques »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Univers/Colonia1.wav` | Colonia. Une colonie humaine à vingt-deux mille années-lumière de la Bulle. Tout a commencé avec un barman cyborg et un saut raté. |
| ⬜ | toujours | `data/son/Conversations/Univers/Colonia2.wav` | Là-bas, la Fédération et l'Empire n'ont presque rien à dire. Le ciel est plein de nébuleuses. C'est loin… mais c'est beau. |

### Le centre de la galaxie (`centre_galaxie`)

*Questions :* « le centre de la galaxie », « un trou noir », « les trous noirs », « sagittarius a », toute phrase avec « sagittarius », toute phrase avec « sagitarius », toute phrase avec « centre » + « galaxie », toute phrase avec « trou » + « noir »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Univers/CentreGalaxie1.wav` | Sagittarius A étoile. Un trou noir de quatre millions de masses solaires, au cœur de la galaxie, à environ vingt-six mille années-lumière de la Terre. |
| ⬜ | toujours | `data/son/Conversations/Univers/CentreGalaxie2.wav` | Un trou noir, commandant, c'est l'endroit idéal pour une photo. À condition de ne pas s'approcher trop près. |

### Beagle Point (`beagle_point`)

*Questions :* « beagle point », toute phrase avec « beagle »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Univers/BeaglePoint1.wav` | Beagle Point. À soixante-cinq mille années-lumière de Sol, de l'autre côté de la galaxie. Le bout du monde. Littéralement. |

### La galaxie (`galaxie`)

*Questions :* « la galaxie est grande », « combien d'étoiles », « combien de systèmes », « combien il y a d'étoiles », « la taille de la galaxie », « parle-moi de la galaxie », « la voie lactée », « c'est grand la galaxie », toute phrase avec « voie » + « lactee »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Univers/Galaxie1.wav` | Environ quatre cents milliards de systèmes, commandant. L'humanité en a visité une poussière. Il reste de la marge. |
| ⬜ | toujours | `data/son/Conversations/Univers/Galaxie2.wav` | La Voie lactée fait à peu près cent mille années-lumière de diamètre. Avec notre portée de saut… disons que vous avez de quoi vous occuper. |

### Les ingénieurs (`ingenieurs`)

*Questions :* « les ingénieurs », « parle-moi des ingénieurs », toute phrase avec « ingenieur », toute phrase avec « farseer », toute phrase avec « engineer »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Univers/Ingenieurs1.wav` | Les ingénieurs ! Des génies un peu fous, cachés dans des bases isolées. Ils améliorent vos modules… contre des matériaux, des faveurs, et beaucoup de patience. |
| ⬜ | toujours | `data/son/Conversations/Univers/Ingenieurs2.wav` | Felicity Farseer, à Deciat. Si votre FSD saute loin, c'est un peu grâce à elle. Et à vos heures passées à collecter des matériaux. |

### La Terre et Sol (`terre`)

*Questions :* « la terre », « parle-moi de la terre », « le système sol », « la planète terre », « le berceau de l'humanité », toute phrase avec « systeme » + « sol »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Univers/Terre1.wav` | La Terre. Le berceau de l'humanité, dans le système Sol. Il faut un permis de la Fédération pour y aller. Ils sont très pointilleux sur les visiteurs. |

### Sommes-nous seuls ? (`extraterrestres`)

*Questions :* « est-on seuls », « sommes-nous seuls », « est-ce qu'on est seuls dans l'univers », « il y a de la vie ailleurs », « la vie ailleurs », « les aliens », « les extraterrestres », toute phrase avec « extraterrestre », toute phrase avec « alien »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Univers/Extraterrestres1.wav` | Seuls ? Certainement pas. Il y a les Thargoïdes, les ruines des Gardiens, et de la vie sur des milliers de planètes. Les exobiologistes ne chôment pas. |


## Aide et réglages — `data/son/Conversations/Meta/`

### Que sais-tu faire ? (`aide`)

*Questions :* « qu'est-ce que tu sais faire », « que sais-tu faire », « tu sais faire quoi », « aide-moi », « j'ai besoin d'aide », « aide », « tes commandes », « quelles commandes », « liste des commandes », « comment ça marche »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Meta/Aide1.wav` | Je commande vos systèmes à la voix : train, soute, phares, énergie, FSD, autopilote, appontage, fuite… Et je réponds à vos questions sur le vaisseau, la route ou la galaxie. |
| ⬜ | toujours | `data/son/Conversations/Meta/Aide2.wav` | Demandez-moi comment va le vaisseau, combien il reste de carburant, où nous sommes… ou une histoire. Et quand je vous pose une question, répondez simplement, sans dire mon nom. |

### Discuter (`discussion`)

*Questions :* « on discute », « on peut discuter », « tu veux discuter », « discutons », « parlons », « parlons un peu », « on parle », « j'ai envie de parler », « j'ai besoin de parler », « tiens-moi compagnie »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Meta/Discussion1.wav` | Avec plaisir, commandant. De quoi voulez-vous parler ? Du vaisseau, de la galaxie… ou de vous ? |
|  | ↳ après « Avec plaisir, commandant. De quoi voul… » · réponse « vaisseau », « le vaisseau », « du vaisseau », « notre vaisseau » | — | *(enchaîne sur le sujet `vaisseau_avis`)* |
|  | ↳ après « Avec plaisir, commandant. De quoi voul… » · réponse « galaxie », « la galaxie », « de la galaxie », « l'univers » | — | *(enchaîne sur le sujet `galaxie`)* |
|  | ↳ après « Avec plaisir, commandant. De quoi voul… » · réponse « moi », « de moi », « parlons de moi » | — | *(enchaîne sur le sujet `avis_commandant`)* |
|  | ↳ après « Avec plaisir, commandant. De quoi voul… » · réponse « toi », « de toi », « de vous », « parlons de toi » | — | *(enchaîne sur le sujet `qui_es_tu`)* |
|  | ↳ après « Avec plaisir, commandant. De quoi voul… » · réponse « histoire », « une histoire » | — | *(enchaîne sur le sujet `histoire`)* |
|  | ↳ après « Avec plaisir, commandant. De quoi voul… » · réponse « blague », « une blague » | — | *(enchaîne sur le sujet `blague`)* |
| ⬜ | ↳ après « Avec plaisir, commandant. De quoi voul… » · réponse *non* | `data/son/Conversations/Meta/DiscussionNon.wav` | Très bien. Je reste à l'écoute, comme toujours. |
| ⬜ | ↳ après « Avec plaisir, commandant. De quoi voul… » · toute autre réponse | `data/son/Conversations/Meta/DiscussionAutre.wav` | Je n'ai pas d'avis là-dessus, commandant. Mais j'aime bien vous entendre parler. |
| ⬜ | en danger | `data/son/Conversations/Meta/DiscussionDanger.wav` | Maintenant ? On se fait tirer dessus, commandant ! On discutera après. |

### Silence radio (`silence_radio`)

*Questions :* « silence radio », « tais-toi », « chut », « arrête de parler », « arrête de bavarder », « moins de bavardage », « ne parle plus », « mode silence », « silence », « la ferme »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Meta/SilenceRadio1.wav` | Silence radio. Je ne parlerai plus que si vous m'appelez… ou en cas d'alerte. |
| ⬜ | toujours | `data/son/Conversations/Meta/SilenceRadio2.wav` | Bien reçu. Je me tais. Mais je n'en pense pas moins. |

### Fin du silence radio (`reprise_parole`)

*Questions :* « tu peux parler », « tu peux reparler », « tu peux parler à nouveau », « reprends la parole », « fin du silence radio », « fin du silence », « mode bavard », « tu peux bavarder », « parle librement »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Meta/Reprise1.wav` | Canal ouvert, commandant. Vous allez m'entendre. |
| ⬜ | toujours | `data/son/Conversations/Meta/Reprise2.wav` | Enfin ! J'avais tellement de choses à vous dire. |

### Question sans réponse prévue (`question_inconnue`)

*Sujet caché : atteint seulement par une autre réplique.*

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Meta/Inconnue1.wav` | Bonne question, commandant. Je n'ai pas la réponse… pour l'instant. |
| ⬜ | toujours | `data/son/Conversations/Meta/Inconnue2.wav` | Ça dépasse mes banques de données. Reformulez, ou demandez-moi autre chose. |
| ⬜ | toujours | `data/son/Conversations/Meta/Inconnue3.wav` | Je n'ai rien sur ce sujet. Mes concepteurs ont dû l'oublier. |


## Jeux — `data/son/Conversations/Jeux/`

### Devinettes (`devinette`)

*Questions :* « une devinette », « pose-moi une devinette », « fais-moi une devinette », « on joue », « on fait un jeu », « jouons », « un jeu », « tu veux jouer », « on joue à un jeu », « une énigme »

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Jeux/Devinette1.wav` | Je brûle sans jamais m'éteindre. Je nourris les commandants qui m'approchent, et je grille ceux qui s'approchent trop. Qui suis-je ? |
|  | ↳ après « Je brûle sans jamais m'éteindre. Je no… » · réponse « étoile », « une étoile », « les étoiles », « soleil » | — | *(enchaîne sur le sujet `devinette_bravo`)* |
| ⬜ | ↳ après « Je brûle sans jamais m'éteindre. Je no… » · réponse *abandon* | `data/son/Conversations/Jeux/Devinette1Reponse.wav` | Une étoile, commandant ! Pensez-y la prochaine fois que vous écoperez. |
| ⬜ | ↳ après « Je brûle sans jamais m'éteindre. Je no… » · toute autre réponse | `data/son/Conversations/Jeux/Devinette1Rate.wav` | Raté ! C'était une étoile. Celle-là même qui remplit votre réservoir. |
| ⬜ | ↳ après « Je brûle sans jamais m'éteindre. Je no… » · pas de réponse | `data/son/Conversations/Jeux/Devinette1Reponse.wav` | Une étoile, commandant ! Pensez-y la prochaine fois que vous écoperez. |
| ⬜ | toujours | `data/son/Conversations/Jeux/Devinette2.wav` | Tout le monde me cherche, personne ne m'a trouvé, et une roue sombre garde mon secret. Qui suis-je ? |
|  | ↳ après « Tout le monde me cherche, personne ne … » · réponse « raxxla », « raxla » | — | *(enchaîne sur le sujet `devinette_bravo`)* |
| ⬜ | ↳ après « Tout le monde me cherche, personne ne … » · réponse *abandon* | `data/son/Conversations/Jeux/Devinette2Reponse.wav` | Raxxla, commandant ! Si vous l'aviez trouvé, nous serions riches et célèbres. |
| ⬜ | ↳ après « Tout le monde me cherche, personne ne … » · toute autre réponse | `data/son/Conversations/Jeux/Devinette2Rate.wav` | Non ! C'était Raxxla. Le monde que tout le monde cherche. |
| ⬜ | ↳ après « Tout le monde me cherche, personne ne … » · pas de réponse | `data/son/Conversations/Jeux/Devinette2Reponse.wav` | Raxxla, commandant ! Si vous l'aviez trouvé, nous serions riches et célèbres. |
| ⬜ | toujours | `data/son/Conversations/Jeux/Devinette3.wav` | Je ne suis ni une étoile, ni une planète, ni un vaisseau. Pourtant, même la lumière ne peut pas m'échapper. Qui suis-je ? |
|  | ↳ après « Je ne suis ni une étoile, ni une planè… » · réponse « trou noir », « un trou noir », « black hole » | — | *(enchaîne sur le sujet `devinette_bravo`)* |
| ⬜ | ↳ après « Je ne suis ni une étoile, ni une planè… » · réponse *abandon* | `data/son/Conversations/Jeux/Devinette3Reponse.wav` | Un trou noir ! Rien ne lui échappe. Pas même les mauvais pilotes. |
| ⬜ | ↳ après « Je ne suis ni une étoile, ni une planè… » · toute autre réponse | `data/son/Conversations/Jeux/Devinette3Rate.wav` | Perdu ! C'était un trou noir. Ne vous en approchez jamais, c'est un conseil. |
| ⬜ | ↳ après « Je ne suis ni une étoile, ni une planè… » · pas de réponse | `data/son/Conversations/Jeux/Devinette3Reponse.wav` | Un trou noir ! Rien ne lui échappe. Pas même les mauvais pilotes. |
| ⬜ | toujours | `data/son/Conversations/Jeux/Devinette4.wav` | Je tourne sur moi-même, j'ai une fente pour seule entrée, et les pilotes pressés finissent écrasés sur mes murs. Qui suis-je ? |
|  | ↳ après « Je tourne sur moi-même, j'ai une fente… » · réponse « station », « une station », « coriolis », « une coriolis » | — | *(enchaîne sur le sujet `devinette_bravo`)* |
| ⬜ | ↳ après « Je tourne sur moi-même, j'ai une fente… » · réponse *abandon* | `data/son/Conversations/Jeux/Devinette4Reponse.wav` | Une station Coriolis, commandant ! Avec sa célèbre boîte aux lettres. |
| ⬜ | ↳ après « Je tourne sur moi-même, j'ai une fente… » · toute autre réponse | `data/son/Conversations/Jeux/Devinette4Rate.wav` | Non ! C'était une station Coriolis. Vous en traversez la fente tous les jours. |
| ⬜ | ↳ après « Je tourne sur moi-même, j'ai une fente… » · pas de réponse | `data/son/Conversations/Jeux/Devinette4Reponse.wav` | Une station Coriolis, commandant ! Avec sa célèbre boîte aux lettres. |
| ⬜ | toujours | `data/son/Conversations/Jeux/Devinette5.wav` | Je ne dure qu'un instant, mais chacun de moi vous emmène à des années-lumière de chez vous. Qui suis-je ? |
|  | ↳ après « Je ne dure qu'un instant, mais chacun … » · réponse « saut », « un saut », « le saut », « saut hyperespace » | — | *(enchaîne sur le sujet `devinette_bravo`)* |
| ⬜ | ↳ après « Je ne dure qu'un instant, mais chacun … » · réponse *abandon* | `data/son/Conversations/Jeux/Devinette5Reponse.wav` | Un saut hyperespace ! Vous en faites tous les jours, commandant. |
| ⬜ | ↳ après « Je ne dure qu'un instant, mais chacun … » · toute autre réponse | `data/son/Conversations/Jeux/Devinette5Rate.wav` | Raté ! C'était un saut hyperespace. Le FSD est vexé. |
| ⬜ | ↳ après « Je ne dure qu'un instant, mais chacun … » · pas de réponse | `data/son/Conversations/Jeux/Devinette5Reponse.wav` | Un saut hyperespace ! Vous en faites tous les jours, commandant. |
| ⬜ | en danger | `data/son/Conversations/Jeux/DevinetteDanger.wav` | Une devinette ? Qu'est-ce qui tire sur nous en ce moment ? Concentrez-vous, commandant ! |

### Devinette réussie (`devinette_bravo`)

*Sujet caché : atteint seulement par une autre réplique.*

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Jeux/Bravo1.wav` | Exact ! Vous êtes plus vif qu'un Viper. Une autre ? |
|  | ↳ après « Exact ! Vous êtes plus vif qu'un Viper… » · réponse *oui* | — | *(enchaîne sur le sujet `devinette`)* |
| ⬜ | ↳ après « Exact ! Vous êtes plus vif qu'un Viper… » · réponse *non* | `data/son/Conversations/Jeux/DevinetteFin.wav` | Comme vous voudrez. Je garde mes meilleures pour plus tard. |
| ⬜ | toujours | `data/son/Conversations/Jeux/Bravo2.wav` | Bravo, commandant ! Je vais devoir trouver plus difficile. Une autre ? |
| ⬜ | toujours | `data/son/Conversations/Jeux/Bravo3.wav` | Bonne réponse ! Votre cerveau tourne mieux que notre FSD. On continue ? |


## Le COVAS prend la parole — `data/son/Conversations/Initiatives/`

### Retour à quai (amarrage manuel) (`retour_station`)

*Le COVAS parle de lui-même :* événement du journal `Docked` — si carburant ou réparations à faire, station avec carburant/réparations (chance 100 %, pas plus d'une fois toutes les 10 min).

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Initiatives/RetourStation1.wav` | Amarrage terminé. Bienvenue à quai, commandant. Je lance le ravitaillement ? |
| ⬜ | toujours | `data/son/Conversations/Initiatives/RetourStation2.wav` | Bien posé, commandant. Le vaisseau a besoin d'un peu d'entretien. Je m'en occupe ? |

### Long trajet en supercroisière (`long_trajet`)

*Le COVAS parle de lui-même :* contexte vrai depuis 300 s — si en supercroisière, pas en danger, pas juste après un accrochage (chance 60 %, pas plus d'une fois toutes les 40 min).

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Initiatives/LongTrajet1.wav` | Le trajet est long, commandant. Voulez-vous que je vous raconte une histoire ? |
| ⬜ | toujours | `data/son/Conversations/Initiatives/LongTrajet2.wav` | Toujours en supercroisière… Une devinette, pour passer le temps ? |
|  | ↳ après « Toujours en supercroisière… Une devine… » · réponse *oui* | — | *(enchaîne sur le sujet `devinette`)* |
| ⬜ | ↳ après « Toujours en supercroisière… Une devine… » · réponse *non* | `data/son/Conversations/Jeux/DevinetteNon.wav` | Dommage. J'en avais une excellente. |

### Fin d'un accrochage (`apres_combat`)

*Le COVAS parle de lui-même :* contexte vrai depuis 25 s — si juste après un accrochage, pas hostiles à proximité, en vol (chance 80 %, pas plus d'une fois toutes les 15 min).

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Initiatives/ApresCombat1.wav` | Menace écartée. Tout va bien, commandant ? |
| ⬜ | ↳ après « Menace écartée. Tout va bien, commanda… » · réponse *oui* / *bien* | `data/son/Conversations/Initiatives/ApresCombatBien.wav` | Tant mieux. Moi, j'ai eu peur pour la peinture. |
| ⬜ | ↳ après « Menace écartée. Tout va bien, commanda… » · réponse *non* / *mal* | `data/son/Conversations/Initiatives/ApresCombatMal.wav` | Respirez, commandant. Je surveille les capteurs, rien ne nous suit. |
| ⬜ | coque sous 40 % | `data/son/Conversations/Initiatives/ApresCombatCoque.wav` | On s'en est sortis, mais la coque est en lambeaux. Je vous conseille une station. Vite. |

### Découverte d'un monde semblable à la Terre (`monde_terrestre`)

*Le COVAS parle de lui-même :* événement du journal `Scan` (chance 100 %, pas plus d'une fois toutes les 1 min).

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Initiatives/MondeTerrestre.wav` | Commandant… un monde semblable à la Terre. Et personne ne l'avait jamais scanné avant nous. Votre nom va rester dans l'histoire. |

### Monde semblable à la Terre (déjà connu) (`monde_terrestre_connu`)

*Le COVAS parle de lui-même :* événement du journal `Scan` (chance 70 %, pas plus d'une fois toutes les 5 min).

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Initiatives/MondeTerrestreConnu.wav` | Un monde semblable à la Terre. Quelqu'un est passé avant nous… mais quelle vue. |

### Découverte d'un monde océan (`monde_aquatique`)

*Le COVAS parle de lui-même :* événement du journal `Scan` (chance 100 %, pas plus d'une fois toutes les 1 min).

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Initiatives/MondeAquatique.wav` | Un monde océan, jamais scanné ! Des milliers de kilomètres d'eau… et pas un seul vacancier. |

### Découverte d'un monde à ammoniac (`monde_ammoniac`)

*Le COVAS parle de lui-même :* événement du journal `Scan` (chance 100 %, pas plus d'une fois toutes les 1 min).

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Initiatives/MondeAmmoniac.wav` | Un monde à ammoniac, jamais découvert. Rare, toxique… et très bien payé par les cartographes. |

### Promotion (`promotion`)

*Le COVAS parle de lui-même :* événement du journal `Promotion` (chance 100 %, pas plus d'une fois toutes les 0 min).

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Initiatives/Promotion1.wav` | Promotion confirmée par la Fédération des pilotes. Félicitations, commandant ! Je le savais. |
| ⬜ | toujours | `data/son/Conversations/Initiatives/Promotion2.wav` | Nouveau rang, commandant ! Je mets à jour votre dossier… et ma fierté. |

### Après un rachat (vaisseau détruit) (`rachat`)

*Le COVAS parle de lui-même :* événement du journal `Resurrect` (chance 100 %, pas plus d'une fois toutes les 1 min).

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ✅ | toujours | `data/son/Conversations/Initiatives/Rachat1.wav` | Nouveau vaisseau, même commandant. Essayons de garder celui-ci un peu plus longtemps. |
| ⬜ | toujours | `data/son/Conversations/Initiatives/Rachat2.wav` | Systèmes redémarrés. Votre assureur vous salue… froidement. |

### Interdiction esquivée (`interdiction_esquivee`)

*Le COVAS parle de lui-même :* événement du journal `EscapeInterdiction` (chance 80 %, pas plus d'une fois toutes les 2 min).

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Initiatives/Esquive1.wav` | Interdiction esquivée ! Ils peuvent toujours courir. |
| ⬜ | toujours | `data/son/Conversations/Initiatives/Esquive2.wav` | Bien joué, commandant. Ils n'ont vu que nos réacteurs. |

### Surcharge du FSD (étoile à neutrons) (`surcharge_fsd`)

*Le COVAS parle de lui-même :* événement du journal `JetConeBoost` (chance 70 %, pas plus d'une fois toutes les 10 min).

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Initiatives/Surcharge1.wav` | FSD surchargé ! J'adore les étoiles à neutrons… de loin. |
| ⬜ | toujours | `data/son/Conversations/Initiatives/Surcharge2.wav` | Surcharge réussie. Le prochain saut va être spectaculaire. Ne regardez pas la jauge de chaleur. |

### Infraction commise (`infraction`)

*Le COVAS parle de lui-même :* événement du journal `CommitCrime` (chance 50 %, pas plus d'une fois toutes les 5 min).

| | Contexte | Fichier | Phrase à dire |
|---|---|---|---|
| ⬜ | toujours | `data/son/Conversations/Initiatives/Infraction1.wav` | Commandant… je vais faire comme si je n'avais rien vu. |
| ⬜ | toujours | `data/son/Conversations/Initiatives/Infraction2.wav` | Infraction enregistrée par les autorités. Pas par moi. Moi, je n'ai rien vu. |


## Répliques affichées sans voix (rien à enregistrer)

Leur texte change à chaque fois (heure, système...).

| Contexte | Phrase |
|---|---|
| toujours | Il est {heure_parlee}, commandant. |
| la nuit | Il est {heure_parlee}, commandant. Il serait peut-être temps de dormir. |
| toujours | Nous sommes le {date_galactique}, commandant. Calendrier galactique. |
| système connu | Système {systeme}, commandant. |
| système connu · en supercroisière | En supercroisière dans le système {systeme}, commandant. |
| système connu · posé sur une planète · astre connu | Posés sur {corps}, dans le système {systeme}. |
| système connu · amarré à une station · station connue | Amarrés à {station}, dans le système {systeme}. |
