# Script des répliques à enregistrer

**117 répliques** au total.

Chaque ligne = un fichier à enregistrer. Enregistre la phrase, range le fichier à l'emplacement indiqué (dans `Backend/`), et c'est tout : `barks.json` connaît déjà ces fichiers. Tant qu'un fichier n'existe pas, le COVAS l'ignore et répond par un « Bien, commandant » générique ou reste muet.

Tu peux changer les phrases comme tu veux : seul le nom du fichier compte.

## Commandes de cockpit

| Quand | Fichier | Phrase à dire |
|---|---|---|
| `NVG` | `data/son/Cockpit/NVG1.wav` | Vision nocturne. |
| `NVG` | `data/son/Cockpit/NVG2.wav` | Je bascule la vision nocturne, commandant. |
| `nvg_deja_active` | `data/son/Cockpit/NVGDejaActive.wav` | La vision nocturne est déjà active, commandant. |
| `nvg_deja_coupee` | `data/son/Cockpit/NVGDejaCoupee.wav` | La vision nocturne est déjà coupée. |
| `phares` | `data/son/Cockpit/Phares1.wav` | Phares. |
| `phares` | `data/son/Cockpit/Phares2.wav` | Je m'occupe des phares, commandant. |
| `phares_deja_allumes` | `data/son/Cockpit/PharesDejaAllumes.wav` | Les phares sont déjà allumés. |
| `phares_deja_eteints` | `data/son/Cockpit/PharesDejaEteints.wav` | Les phares sont déjà éteints. |
| `armement` | `data/son/Cockpit/Armement1.wav` | Points d'emport. |
| `armement` | `data/son/Cockpit/Armement2.wav` | Armement, à vos ordres. |
| `armement_deja_sorti` | `data/son/Cockpit/ArmementDejaSorti.wav` | Les armes sont déjà déployées, commandant. |
| `armement_deja_rentre` | `data/son/Cockpit/ArmementDejaRentre.wav` | Les armes sont déjà rentrées. |
| `hud` | `data/son/Cockpit/Hud1.wav` | Changement de mode du cockpit. |
| `hud` | `data/son/Cockpit/Hud2.wav` | Affichage basculé, commandant. |
| `hud_deja_analyse` | `data/son/Cockpit/HudDejaAnalyse.wav` | Le cockpit est déjà en mode analyse. |
| `hud_deja_combat` | `data/son/Cockpit/HudDejaCombat.wav` | Le cockpit est déjà en mode combat. |
| `silencieux` | `data/son/Cockpit/Silencieux1.wav` | Mode silencieux. |
| `silencieux` | `data/son/Cockpit/Silencieux2.wav` | Je bascule le mode silencieux. Surveillez la chaleur, commandant. |
| `silencieux_deja_actif` | `data/son/Cockpit/SilencieuxDejaActif.wav` | Le mode silencieux est déjà actif. |
| `silencieux_deja_coupe` | `data/son/Cockpit/SilencieuxDejaCoupe.wav` | Le mode silencieux est déjà coupé. |
| `vitesse_zero` | `data/son/Cockpit/VitesseZero1.wav` | Vitesse zéro. |
| `vitesse_zero` | `data/son/Cockpit/VitesseZero2.wav` | Moteurs à l'arrêt, commandant. |
| `plein_gaz` | `data/son/Cockpit/PleinGaz1.wav` | Plein gaz ! |
| `plein_gaz` | `data/son/Cockpit/PleinGaz2.wav` | Poussée maximale, commandant. |
| `carte_galaxie` | `data/son/Cockpit/CarteGalaxie.wav` | Carte de la galaxie. |
| `carte_systeme` | `data/son/Cockpit/CarteSysteme.wav` | Carte du système. |
| `lock` | `data/son/Cockpit/Lock1.wav` | Cible verrouillée. |
| `lock` | `data/son/Cockpit/Lock2.wav` | Verrouillage. |
| `boost` | `data/son/Cockpit/Boost1.wav` | Boost ! |
| `boost` | `data/son/Cockpit/Boost2.wav` | Postcombustion. |
| `reset` | `data/son/Cockpit/Reset1.wav` | Énergie équilibrée. |
| `reset` | `data/son/Cockpit/Reset2.wav` | Répartition par défaut, commandant. |
| `energie_arm` | `data/son/Cockpit/EnergieArmes.wav` | Énergie aux armes. |
| `energie_sys` | `data/son/Cockpit/EnergieSystemes.wav` | Énergie aux systèmes. |

## Combat

| Quand | Fichier | Phrase à dire |
|---|---|---|
| `fuite` | `data/son/Combat/Fuite1.wav` | On dégage ! Énergie aux boucliers, je charge le FSD. |
| `fuite` | `data/son/Combat/Fuite2.wav` | Manœuvre d'évasion. Accrochez-vous, commandant. |
| `fuite_reussie` | `data/son/Combat/FuiteReussie1.wav` | Nous sommes hors de portée, commandant. |
| `fuite_reussie` | `data/son/Combat/FuiteReussie2.wav` | Évasion réussie. |
| `puce_thermique` | `data/son/Combat/PuceThermique1.wav` | Puce thermique larguée. |
| `puce_thermique` | `data/son/Combat/PuceThermique2.wav` | Purge de chaleur. |
| `leurres` | `data/son/Combat/Leurres1.wav` | Leurres lancés. |
| `leurres` | `data/son/Combat/Leurres2.wav` | Contre-mesures. |
| `cible_menace` | `data/son/Combat/CibleMenace1.wav` | Je cible la menace principale. |
| `cible_menace` | `data/son/Combat/CibleMenace2.wav` | Agresseur verrouillé. |
| `cible_hostile` | `data/son/Combat/CibleHostile1.wav` | Hostile suivant. |
| `cible_hostile` | `data/son/Combat/CibleHostile2.wav` | Cible suivante. |
| `sous_systeme` | `data/son/Combat/SousSysteme1.wav` | Je cherche le sous-système. |
| `sous_systeme` | `data/son/Combat/SousSysteme2.wav` | Ciblage du module, commandant. |
| `refus_pas_de_cible` | `data/son/Refus/PasDeCible.wav` | Aucune cible verrouillée, commandant. |
| `chasseur` | `data/son/Combat/Chasseur1.wav` | Ordre transmis au chasseur. |
| `chasseur` | `data/son/Combat/Chasseur2.wav` | Le pilote a reçu vos ordres, commandant. |
| `refus_pas_de_chasseur` | `data/son/Refus/PasDeChasseur.wav` | Aucun chasseur n'est déployé, commandant. |
| `refus_ordre_inconnu` | `data/son/Refus/OrdreInconnu.wav` | Je n'ai pas compris l'ordre, commandant. Précisez. |
| `drone` | `data/son/Combat/Drone1.wav` | Drone lancé. |
| `drone` | `data/son/Combat/Drone2.wav` | Lancement du drone, commandant. |
| `refus_drone_non_regle` | `data/son/Refus/DroneNonRegle.wav` | Je ne sais pas dans quel groupe de tir se trouve ce drone, commandant. |
| `refus_pas_de_module` | `data/son/Refus/PasDeModule.wav` | Ce module n'est pas installé sur le vaisseau. |
| `rapport_avarie` | `data/son/Combat/RapportAvarie.wav` | Rapport d'avarie à l'écran, commandant. |

Le rapport d'avarie lui-même (coque, boucliers, modules) est lu par la synthèse vocale
(`module/synthese.py`) : son texte change à chaque fois. La réplique ci-dessus ne sert que si
la synthèse est indisponible.

## Station

| Quand | Fichier | Phrase à dire |
|---|---|---|
| `decollage` | `data/son/Station/Decollage1.wav` | Procédure de décollage engagée. |
| `decollage` | `data/son/Station/Decollage2.wav` | Je libère les pinces, commandant. |
| `decollage_a_vous` | `data/son/Station/DecollageAVous.wav` | Train rentré. À vous les commandes pour la sortie. |
| `decollage_degage` | `data/son/Station/DecollageDegage1.wav` | Dégagé de la station. |
| `decollage_degage` | `data/son/Station/DecollageDegage2.wav` | Nous sommes hors de la zone de la station. Bon vol, commandant. |
| `apontage` | `data/son/Station/Apontage1.wav` | Je demande l'autorisation d'apponter. |
| `apontage` | `data/son/Station/Apontage2.wav` | Demande d'appontage envoyée à la station. |
| `apontage_accorde` | `data/son/Station/ApontageAccorde1.wav` | Appontage autorisé, commandant. |
| `apontage_accorde` | `data/son/Station/ApontageAccorde2.wav` | La station nous attend. Plateforme attribuée. |
| `apontage_refuse` | `data/son/Station/ApontageRefuse.wav` | La station refuse l'appontage, commandant. |
| `apontage_expire` | `data/son/Station/ApontageExpire.wav` | Notre autorisation d'appontage a expiré. |
| `services` | `data/son/Station/Services.wav` | Services de la station. |
| `ravitaillement_termine` | `data/son/Station/RavitaillementTermine1.wav` | Ravitaillement terminé, commandant. |
| `ravitaillement_termine` | `data/son/Station/RavitaillementTermine2.wav` | Le vaisseau est prêt à repartir. |
| `ravitaillement_inutile` | `data/son/Station/RavitaillementInutile.wav` | Réservoir plein et coque intacte. Rien à faire, commandant. |

## Autopilote et programmes

| Quand | Fichier | Phrase à dire |
|---|---|---|
| `autopilote_station` | `data/son/Autopilote/Station1.wav` | Autopilote engagé. Cap sur la destination. |
| `autopilote_station` | `data/son/Autopilote/Station2.wav` | Je prends la suite, commandant. Direction la station. |
| `autopilote_assistance` | `data/son/Autopilote/Assistance.wav` | Activez l'assistance de supercroisière, commandant. Je m'occupe du reste. |
| `autopilote_danger` | `data/son/Autopilote/Danger.wav` | Menace détectée. Autopilote coupé, à vous les commandes ! |
| `autopilote_route` | `data/son/Autopilote/Route1.wav` | Route verrouillée. J'enchaîne les sauts, commandant. |
| `voyage_alignement` | `data/son/Autopilote/Alignement.wav` | Alignez-vous sur la cible, commandant. Le saut partira tout seul. |
| `voyage_arrivee` | `data/son/Autopilote/Arrivee.wav` | Destination atteinte. À vous les commandes. |
| `refus_carburant_voyage` | `data/son/Refus/CarburantVoyage.wav` | Carburant insuffisant pour continuer, commandant. Voyage suspendu. |
| `refus_pas_de_destination` | `data/son/Refus/PasDeDestination.wav` | Aucune destination n'est ciblée, commandant. |
| `stop` | `data/son/Autopilote/Stop1.wav` | Programme interrompu. |
| `stop` | `data/son/Autopilote/Stop2.wav` | J'arrête tout, commandant. |
| `stop_rien` | `data/son/Autopilote/StopRien.wav` | Aucun programme en cours, commandant. |
| `refus_programme_en_cours` | `data/son/Refus/ProgrammeEnCours.wav` | Un programme est déjà en cours. Dites stop pour l'annuler. |
| `reactions_actives` | `data/son/Autopilote/ReactionsActives.wav` | Réactions automatiques activées. Je veille, commandant. |
| `reactions_coupees` | `data/son/Autopilote/ReactionsCoupees.wav` | Réactions automatiques désactivées. |
| `reaction_surchauffe` | `data/son/Autopilote/ReactionSurchauffe.wav` | Surchauffe ! Je largue une puce thermique. |
| `reaction_bouclier` | `data/son/Autopilote/ReactionBouclier.wav` | Boucliers tombés ! Énergie aux systèmes. |
| `reaction_interdiction` | `data/son/Autopilote/ReactionInterdiction.wav` | Interdiction ! Je renforce les boucliers. |

## Alertes (dites toutes seules)

| Quand | Fichier | Phrase à dire |
|---|---|---|
| `bouclier_retabli` | `data/son/Alertes/BouclierRetabli1.wav` | Boucliers rétablis. |
| `bouclier_retabli` | `data/son/Alertes/BouclierRetabli2.wav` | Les boucliers sont de nouveau en ligne, commandant. |
| `alerte_attaque` | `data/son/Alertes/Attaque1.wav` | Nous sommes attaqués ! |
| `alerte_attaque` | `data/son/Alertes/Attaque2.wav` | Tirs ennemis, commandant ! |
| `alerte_interdiction` | `data/son/Alertes/Interdiction1.wav` | Interdiction en cours ! |
| `alerte_interdiction` | `data/son/Alertes/Interdiction2.wav` | On nous arrache de la supercroisière, commandant ! |
| `alerte_surchauffe` | `data/son/Alertes/Surchauffe1.wav` | Alerte, surchauffe ! |
| `alerte_surchauffe` | `data/son/Alertes/Surchauffe2.wav` | Température critique, commandant. |
| `alerte_carburant` | `data/son/Alertes/Carburant1.wav` | Niveau de carburant bas. |
| `alerte_carburant` | `data/son/Alertes/Carburant2.wav` | Commandant, il faut faire le plein rapidement. |
| `verriere_brisee` | `data/son/Alertes/VerriereBrisee.wav` | Verrière brisée ! Oxygène de secours activé. |
| `kill_confirme` | `data/son/Alertes/Kill1.wav` | Cible détruite. |
| `kill_confirme` | `data/son/Alertes/Kill2.wav` | Ennemi éliminé. Joli tir, commandant. |
| `kill_confirme` | `data/son/Alertes/Kill3.wav` | Une menace de moins. |

## Refus et erreurs

| Quand | Fichier | Phrase à dire |
|---|---|---|
| `train_deja_sorti` | `data/son/Refus/TrainDejaSorti.wav` | Le train est déjà sorti, commandant. |
| `train_deja_rentre` | `data/son/Refus/TrainDejaRentre.wav` | Le train est déjà rentré. |
| `soute_deja_ouverte` | `data/son/Refus/SouteDejaOuverte.wav` | L'écope de soute est déjà ouverte. |
| `soute_deja_fermee` | `data/son/Refus/SouteDejaFermee.wav` | L'écope de soute est déjà fermée. |
| `refus_supercroisiere` | `data/son/Refus/Supercroisiere.wav` | Impossible en supercroisière, commandant. |
| `refus_amarre` | `data/son/Refus/Amarre.wav` | Impossible, le vaisseau est amarré. |
| `refus_pose` | `data/son/Refus/Pose.wav` | Impossible, le vaisseau est posé. |
| `refus_pas_amarre` | `data/son/Refus/PasAmarre.wav` | Il faut d'abord être amarré à une station, commandant. |
| `refus_pas_de_services` | `data/son/Refus/PasDeServices.wav` | Cette station ne propose pas ce service. |
| `refus_hors_vaisseau` | `data/son/Refus/HorsVaisseau.wav` | Vous n'êtes pas aux commandes du vaisseau, commandant. |
| `refus_masse` | `data/son/Refus/Masse.wav` | Masse verrouillée. Éloignez-vous avant d'activer le FSD. |
| `refus_jeu_absent` | `data/son/Refus/JeuAbsent.wav` | Je ne trouve pas la fenêtre du jeu, commandant. |
| `refus_touche_absente` | `data/son/Refus/ToucheAbsente.wav` | Aucune touche n'est assignée à cette commande, commandant. |
| `macro_echec` | `data/son/Refus/MacroEchec1.wav` | La manœuvre a échoué, commandant. |
| `macro_echec` | `data/son/Refus/MacroEchec2.wav` | Le vaisseau n'a pas répondu. |
| `commande_incomprise` | `data/son/Refus/Incomprise.wav` | Je n'ai pas compris la commande, commandant. |
