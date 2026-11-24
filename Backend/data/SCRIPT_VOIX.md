# Script des répliques du COVAS

**161 répliques** au total.

Chaque ligne = un fichier.

- **Changer une phrase** : modifie-la ici, puis réenregistre-la.
- **Enregistrer une réplique avec ta voix** : lance `STUDIO VOCAL.bat` (à la racine). Le studio liste toutes ces répliques, transforme ta voix en voix du COVAS et range le fichier au bon chemin.
- **Déposer un fichier à la main** : au chemin indiqué, en `.wav` ou en `.mp3` (un `.wav` passe devant le `.mp3`).

`barks.json` connaît déjà ces fichiers. Tant qu'un fichier n'existe pas, le COVAS l'ignore et répond par un « Bien, commandant » générique ou reste muet.

## Commandes de cockpit

| Quand | Fichier | Phrase à dire |
|---|---|---|
| `NVG` | `data/son/Cockpit/NVG1.mp3` | Vision nocturne. |
| `NVG` | `data/son/Cockpit/NVG2.mp3` | Je bascule la vision nocturne, commandant. |
| `nvg_deja_active` | `data/son/Cockpit/NVGDejaActive.mp3` | La vision nocturne est déjà active, commandant. |
| `nvg_deja_coupee` | `data/son/Cockpit/NVGDejaCoupee.mp3` | La vision nocturne est déjà coupée. |
| `phares` | `data/son/Cockpit/Phares1.mp3` | Phares. |
| `phares` | `data/son/Cockpit/Phares2.mp3` | Je m'occupe des phares, commandant. |
| `phares_deja_allumes` | `data/son/Cockpit/PharesDejaAllumes.mp3` | Les phares sont déjà allumés. |
| `phares_deja_eteints` | `data/son/Cockpit/PharesDejaEteints.mp3` | Les phares sont déjà éteints. |
| `armement` | `data/son/Cockpit/Armement1.mp3` | Points d'emport. |
| `armement` | `data/son/Cockpit/Armement2.mp3` | Armement, à vos ordres. |
| `armement_deja_sorti` | `data/son/Cockpit/ArmementDejaSorti.mp3` | Les armes sont déjà déployées, commandant. |
| `armement_deja_rentre` | `data/son/Cockpit/ArmementDejaRentre.mp3` | Les armes sont déjà rentrées. |
| `hud` | `data/son/Cockpit/Hud1.mp3` | Changement de mode du cockpit. |
| `hud` | `data/son/Cockpit/Hud2.mp3` | Affichage basculé, commandant. |
| `hud_deja_analyse` | `data/son/Cockpit/HudDejaAnalyse.mp3` | Le cockpit est déjà en mode analyse. |
| `hud_deja_combat` | `data/son/Cockpit/HudDejaCombat.mp3` | Le cockpit est déjà en mode combat. |
| `silencieux` | `data/son/Cockpit/Silencieux1.mp3` | Mode silencieux. |
| `silencieux` | `data/son/Cockpit/Silencieux2.mp3` | Je bascule le mode silencieux. Surveillez la chaleur, commandant. |
| `silencieux_deja_actif` | `data/son/Cockpit/SilencieuxDejaActif.mp3` | Le mode silencieux est déjà actif. |
| `silencieux_deja_coupe` | `data/son/Cockpit/SilencieuxDejaCoupe.mp3` | Le mode silencieux est déjà coupé. |
| `vitesse_zero` | `data/son/Cockpit/VitesseZero1.mp3` | Vitesse zéro. |
| `vitesse_zero` | `data/son/Cockpit/VitesseZero2.mp3` | Moteurs à l'arrêt, commandant. |
| `plein_gaz` | `data/son/Cockpit/PleinGaz1.mp3` | Poussée à fond ! |
| `plein_gaz` | `data/son/Cockpit/PleinGaz2.mp3` | Poussée maximale, commandant. |
| `carte_galaxie` | `data/son/Cockpit/CarteGalaxie.mp3` | Carte de la galaxie. |
| `carte_systeme` | `data/son/Cockpit/CarteSysteme.mp3` | Carte du système. |
| `lock` | `data/son/Cockpit/Lock1.mp3` | Cible verrouillée. |
| `lock` | `data/son/Cockpit/Lock2.mp3` | Verrouillage. |
| `boost` | `data/son/Cockpit/Boost1.mp3` | Accélération ! |
| `boost` | `data/son/Cockpit/Boost2.mp3` | Postcombustion. |
| `reset` | `data/son/Cockpit/Reset1.mp3` | Énergie équilibrée. |
| `reset` | `data/son/Cockpit/Reset2.mp3` | Répartition par défaut, commandant. |
| `energie_arm` | `data/son/Cockpit/EnergieArmes.mp3` | Énergie aux armes. |
| `energie_sys` | `data/son/Cockpit/EnergieSystemes.mp3` | Énergie aux systèmes. |

## Combat

| Quand | Fichier | Phrase à dire |
|---|---|---|
| `fuite` | `data/son/Combat/Fuite1.mp3` | On dégage ! Énergie aux boucliers, je charge le FSD. |
| `fuite` | `data/son/Combat/Fuite2.mp3` | Manœuvre d'évasion. Accrochez-vous, commandant. |
| `fuite_reussie` | `data/son/Combat/FuiteReussie1.mp3` | Nous sommes hors de portée, commandant. |
| `fuite_reussie` | `data/son/Combat/FuiteReussie2.mp3` | Évasion réussie. |
| `puce_thermique` | `data/son/Combat/PuceThermique1.mp3` | Puce thermique larguée. |
| `puce_thermique` | `data/son/Combat/PuceThermique2.mp3` | Purge de chaleur. |
| `leurres` | `data/son/Combat/Leurres1.mp3` | Leurres lancés. |
| `leurres` | `data/son/Combat/Leurres2.mp3` | Contre-mesures. |
| `cible_menace` | `data/son/Combat/CibleMenace1.mp3` | Je cible la menace principale. |
| `cible_menace` | `data/son/Combat/CibleMenace2.mp3` | Agresseur verrouillé. |
| `cible_hostile` | `data/son/Combat/CibleHostile1.mp3` | Ennemi suivant. |
| `cible_hostile` | `data/son/Combat/CibleHostile2.mp3` | Cible suivante. |
| `sous_systeme` | `data/son/Combat/SousSysteme1.mp3` | Je cherche le sous-système. |
| `sous_systeme` | `data/son/Combat/SousSysteme2.mp3` | Ciblage du module, commandant. |
| `refus_pas_de_cible` | `data/son/Refus/PasDeCible.mp3` | Aucune cible verrouillée, commandant. |
| `chasseur` | `data/son/Combat/Chasseur1.mp3` | Ordre transmis au chasseur. |
| `chasseur` | `data/son/Combat/Chasseur2.mp3` | Le pilote a reçu vos ordres, commandant. |
| `refus_pas_de_chasseur` | `data/son/Refus/PasDeChasseur.mp3` | Aucun chasseur n'est déployé, commandant. |
| `refus_ordre_inconnu` | `data/son/Refus/OrdreInconnu.mp3` | Je n'ai pas compris l'ordre, commandant. Précisez. |
| `drone` | `data/son/Combat/Drone1.mp3` | Drone lancé. |
| `drone` | `data/son/Combat/Drone2.mp3` | Lancement du drone, commandant. |
| `refus_drone_non_regle` | `data/son/Refus/DroneNonRegle.mp3` | Je ne sais pas dans quel groupe de tir se trouve ce drone, commandant. |
| `refus_pas_de_module` | `data/son/Refus/PasDeModule.mp3` | Ce module n'est pas installé sur le vaisseau. |
| `rapport_avarie` | `data/son/Combat/RapportAvarie.mp3` | Rapport d'avarie à l'écran, commandant. |

Le rapport d'avarie lui-même (coque, boucliers, modules) change à chaque fois : le COVAS l'assemble
avec les morceaux du studio vocal (filtre « Rapport, heure, date, position »). Tant qu'il en manque
un, le rapport reste à l'écran et la réplique ci-dessus l'annonce.

## Station

| Quand | Fichier | Phrase à dire |
|---|---|---|
| `decollage` | `data/son/Station/Decollage1.mp3` | Procédure de décollage engagée. |
| `decollage` | `data/son/Station/Decollage2.mp3` | Je libère les pinces, commandant. |
| `decollage_a_vous` | `data/son/Station/DecollageAVous.mp3` | Train rentré. À vous les commandes pour la sortie. |
| `decollage_degage` | `data/son/Station/DecollageDegage1.mp3` | Dégagé de la station. |
| `decollage_degage` | `data/son/Station/DecollageDegage2.mp3` | Nous sommes hors de la zone de la station. Bon vol, commandant. |
| `apontage` | `data/son/Station/Apontage1.mp3` | Je demande l'autorisation d'apponter. |
| `apontage` | `data/son/Station/Apontage2.mp3` | Demande d'appontage envoyée à la station. |
| `apontage_accorde` | `data/son/Station/ApontageAccorde1.mp3` | Appontage autorisé, commandant. |
| `apontage_accorde` | `data/son/Station/ApontageAccorde2.mp3` | La station nous attend. Plateforme attribuée. |
| `apontage_refuse` | `data/son/Station/ApontageRefuse.mp3` | La station refuse l'appontage, commandant. |
| `apontage_expire` | `data/son/Station/ApontageExpire.mp3` | Notre autorisation d'appontage a expiré. |
| `services` | `data/son/Station/Services.mp3` | Services de la station. |
| `ravitaillement_termine` | `data/son/Station/RavitaillementTermine1.mp3` | Ravitaillement terminé, commandant. |
| `ravitaillement_termine` | `data/son/Station/RavitaillementTermine2.mp3` | Le vaisseau est prêt à repartir. |
| `ravitaillement_inutile` | `data/son/Station/RavitaillementInutile.mp3` | Réservoir plein et coque intacte. Rien à faire, commandant. |

## Autopilote et programmes

| Quand | Fichier | Phrase à dire |
|---|---|---|
| `autopilote_station` | `data/son/Autopilote/Station1.mp3` | Autopilote engagé. Cap sur la destination. |
| `autopilote_station` | `data/son/Autopilote/Station2.mp3` | Je prends la suite, commandant. Direction la station. |
| `autopilote_assistance` | `data/son/Autopilote/Assistance.mp3` | Activez l'assistance de supercroisière, commandant. Je m'occupe du reste. |
| `autopilote_danger` | `data/son/Autopilote/Danger.mp3` | Menace détectée. Autopilote coupé, à vous les commandes ! |
| `autopilote_route` | `data/son/Autopilote/Route1.mp3` | Route verrouillée. J'enchaîne les sauts, commandant. |
| `voyage_alignement` | `data/son/Autopilote/Alignement.mp3` | Alignez-vous sur la cible, commandant. Le saut partira tout seul. |
| `voyage_arrivee` | `data/son/Autopilote/Arrivee.mp3` | Destination atteinte. À vous les commandes. |
| `refus_carburant_voyage` | `data/son/Refus/CarburantVoyage.mp3` | Carburant insuffisant pour continuer, commandant. Voyage suspendu. |
| `refus_pas_de_destination` | `data/son/Refus/PasDeDestination.mp3` | Aucune destination n'est ciblée, commandant. |
| `stop` | `data/son/Autopilote/Stop1.mp3` | Programme interrompu. |
| `stop` | `data/son/Autopilote/Stop2.mp3` | J'arrête tout, commandant. |
| `stop_rien` | `data/son/Autopilote/StopRien.mp3` | Aucun programme en cours, commandant. |
| `refus_programme_en_cours` | `data/son/Refus/ProgrammeEnCours.mp3` | Un programme est déjà en cours. Dites stop pour l'annuler. |
| `reactions_actives` | `data/son/Autopilote/ReactionsActives.mp3` | Réactions automatiques activées. Je veille, commandant. |
| `reactions_coupees` | `data/son/Autopilote/ReactionsCoupees.mp3` | Réactions automatiques désactivées. |
| `reaction_surchauffe` | `data/son/Autopilote/ReactionSurchauffe.mp3` | Surchauffe ! Je largue une puce thermique. |
| `reaction_bouclier` | `data/son/Autopilote/ReactionBouclier.mp3` | Boucliers tombés ! Énergie aux systèmes. |
| `reaction_interdiction` | `data/son/Autopilote/ReactionInterdiction.mp3` | Interdiction ! Je renforce les boucliers. |

## Alertes (dites toutes seules)

| Quand | Fichier | Phrase à dire |
|---|---|---|
| `bouclier_retabli` | `data/son/Alertes/BouclierRetabli1.mp3` | Boucliers rétablis. |
| `bouclier_retabli` | `data/son/Alertes/BouclierRetabli2.mp3` | Les boucliers sont de nouveau en ligne, commandant. |
| `alerte_attaque` | `data/son/Alertes/Attaque1.mp3` | Nous sommes attaqués ! |
| `alerte_attaque` | `data/son/Alertes/Attaque2.mp3` | Tirs ennemis, commandant ! |
| `alerte_interdiction` | `data/son/Alertes/Interdiction1.mp3` | Interdiction en cours ! |
| `alerte_interdiction` | `data/son/Alertes/Interdiction2.mp3` | On nous arrache de la supercroisière, commandant ! |
| `alerte_surchauffe` | `data/son/Alertes/Surchauffe1.mp3` | Alerte, surchauffe ! |
| `alerte_surchauffe` | `data/son/Alertes/Surchauffe2.mp3` | Température critique, commandant. |
| `alerte_carburant` | `data/son/Alertes/Carburant1.mp3` | Niveau de carburant bas. |
| `alerte_carburant` | `data/son/Alertes/Carburant2.mp3` | Commandant, il faut faire le plein rapidement. |
| `alerte_carburant_critique` | `data/son/Alertes/CarburantCritique.mp3` | Carburant critique, commandant ! Il faut écoper ou ravitailler sans attendre. |
| `alerte_carburant_route` | `data/son/Alertes/CarburantRoute.mp3` | Commandant, le carburant ne suffira pas pour finir la route. |
| `alerte_carburant_etoile` | `data/son/Alertes/CarburantEtoile.mp3` | Attention, nous n'atteindrons pas la prochaine étoile écopable avec ce carburant. |
| `verriere_brisee` | `data/son/Alertes/VerriereBrisee.mp3` | Verrière brisée ! Oxygène de secours activé. |
| `kill_confirme` | `data/son/Alertes/Kill1.mp3` | Cible détruite. |
| `kill_confirme` | `data/son/Alertes/Kill2.mp3` | Ennemi éliminé. Joli tir, commandant. |
| `kill_confirme` | `data/son/Alertes/Kill3.mp3` | Une menace de moins. |

## Voyage (route tracée)

Le COVAS dit d'abord la phrase avec le nombre de sauts, assemblée avec les morceaux du studio
(groupe « Route » : « Route tracée : » + douze + « sauts. »). Ces répliques fixes, sans nombre,
la remplacent tant qu'un morceau manque, et pour le dernier saut et l'arrivée.

| Quand | Fichier | Phrase à dire |
|---|---|---|
| `route_tracee` | `data/son/Route/RouteTracee.mp3` | Route tracée, commandant. |
| `route_mi_parcours` | `data/son/Route/MiParcours.mp3` | Nous sommes à mi-parcours, commandant. |
| `route_sauts_restants` | `data/son/Route/PlusQueQuelques.mp3` | Plus que quelques sauts avant la destination. |
| `route_dernier_saut` | `data/son/Route/DernierSaut.mp3` | Dernier saut avant la destination, commandant. |
| `route_arrivee` | `data/son/Route/Arrivee.mp3` | Nous sommes arrivés à destination, commandant. |

## Refus et erreurs

| Quand | Fichier | Phrase à dire |
|---|---|---|
| `train_deja_sorti` | `data/son/Refus/TrainDejaSorti.mp3` | Le train est déjà sorti, commandant. |
| `train_deja_rentre` | `data/son/Refus/TrainDejaRentre.mp3` | Le train est déjà rentré. |
| `soute_deja_ouverte` | `data/son/Refus/SouteDejaOuverte.mp3` | L'écope de soute est déjà ouverte. |
| `soute_deja_fermee` | `data/son/Refus/SouteDejaFermee.mp3` | L'écope de soute est déjà fermée. |
| `refus_supercroisiere` | `data/son/Refus/Supercroisiere.mp3` | Impossible en supercroisière, commandant. |
| `refus_amarre` | `data/son/Refus/Amarre.mp3` | Impossible, le vaisseau est amarré. |
| `refus_pose` | `data/son/Refus/Pose.mp3` | Impossible, le vaisseau est posé. |
| `refus_pas_amarre` | `data/son/Refus/PasAmarre.mp3` | Il faut d'abord être amarré à une station, commandant. |
| `refus_pas_de_services` | `data/son/Refus/PasDeServices.mp3` | Cette station ne propose pas ce service. |
| `refus_hors_vaisseau` | `data/son/Refus/HorsVaisseau.mp3` | Vous n'êtes pas aux commandes du vaisseau, commandant. |
| `refus_masse` | `data/son/Refus/Masse.mp3` | Masse verrouillée. Éloignez-vous avant d'activer le FSD. |
| `refus_jeu_absent` | `data/son/Refus/JeuAbsent.mp3` | Je ne trouve pas la fenêtre du jeu, commandant. |
| `refus_touche_absente` | `data/son/Refus/ToucheAbsente.mp3` | Aucune touche n'est assignée à cette commande, commandant. |
| `macro_echec` | `data/son/Refus/MacroEchec1.mp3` | La manœuvre a échoué, commandant. |
| `macro_echec` | `data/son/Refus/MacroEchec2.mp3` | Le vaisseau n'a pas répondu. |
| `commande_incomprise` | `data/son/Refus/Incomprise.mp3` | Je n'ai pas compris la commande, commandant. |

## Actions faites à la main (touche, HOTAS)

| Quand | Fichier | Phrase à dire |
|---|---|---|
| `manuel_train_rentre` | `data/son/Manuel/TrainRentre.mp3` | Train d'atterrissage rentré. |
| `manuel_soute_fermee` | `data/son/Manuel/SouteFermee.mp3` | Écope de soute fermée. |
| `manuel_armes_sorties` | `data/son/Manuel/ArmesSorties.mp3` | Armes déployées. |
| `manuel_armes_rentrees` | `data/son/Manuel/ArmesRentrees.mp3` | Armes rentrées. |
| `manuel_phares_on` | `data/son/Manuel/PharesOn.mp3` | Phares allumés. |
| `manuel_phares_off` | `data/son/Manuel/PharesOff.mp3` | Phares coupés. |
| `manuel_nvg_on` | `data/son/Manuel/NvgOn.mp3` | Vision nocturne activée. |
| `manuel_nvg_off` | `data/son/Manuel/NvgOff.mp3` | Vision nocturne coupée. |
| `manuel_silencieux_on` | `data/son/Manuel/SilencieuxOn.mp3` | Mode silencieux activé. |
| `manuel_silencieux_off` | `data/son/Manuel/SilencieuxOff.mp3` | Mode silencieux coupé. |
| `manuel_analyse` | `data/son/Manuel/ModeAnalyse.mp3` | Mode analyse. |
| `manuel_combat` | `data/son/Manuel/ModeCombat.mp3` | Mode combat. |

## Chasse aux primes

| Quand | Fichier | Phrase à dire |
|---|---|---|
| `chasse_active` | `data/son/Chasse/ChasseActive1.mp3` | Zone de chasse. Mode chasseur de primes activé, commandant. |
| `chasse_active` | `data/son/Chasse/ChasseActive2.mp3` | Bon terrain de chasse. Je vous signale chaque cible scannée. |
| `chasse_coupee` | `data/son/Chasse/ChasseCoupee.mp3` | Mode chasseur de primes coupé. |
| `chasse_fin` | `data/son/Chasse/ChasseFin.mp3` | Fin de la chasse. Le tableau est à l'écran, commandant. |
| `chasse_recherchee` | `data/son/Chasse/Recherchee1.mp3` | Cible recherchée. |
| `chasse_recherchee` | `data/son/Chasse/Recherchee2.mp3` | Celui-là est recherché, commandant. |
| `chasse_recherchee` | `data/son/Chasse/Recherchee3.mp3` | Recherché. Vous pouvez ouvrir le feu. |
| `chasse_clean` | `data/son/Chasse/Clean1.mp3` | Cible en règle. Ne tirez pas. |
| `chasse_clean` | `data/son/Chasse/Clean2.mp3` | Il est clean, commandant. On le laisse tranquille. |
| `chasse_autorite` | `data/son/Chasse/Autorites.mp3` | Vaisseau des autorités. Surtout, ne tirez pas. |
| `chasse_sans_loi` | `data/son/Chasse/SansJuridiction.mp3` | Aucune juridiction ici. Pas de prime sur cette cible. |
| `chasse_joueur` | `data/son/Chasse/Joueur.mp3` | Attention, c'est un autre commandant. |
| `chasse_gros_gibier` | `data/son/Chasse/GrosGibier.mp3` | Gros gibier, commandant. La prime est belle. |
| `chasse_dangereux` | `data/son/Chasse/Dangereux.mp3` | Pilote dangereux. Restez vigilant. |
| `chasse_tir_clean` | `data/son/Chasse/TirClean.mp3` | Commandant, vous venez de toucher une cible en règle ! |

## Exploration et exobiologie

| Quand | Fichier | Phrase à dire |
|---|---|---|
| `scan_valeur` | `data/son/Exploration/ScanValeur.mp3` | Corps de grande valeur, commandant. Le détail est à l'écran. |
| `scan_premiere` | `data/son/Exploration/ScanPremiere.mp3` | Corps de grande valeur, et personne ne l'a encore découvert. |
| `scan_bio` | `data/son/Exploration/ScanBio.mp3` | Signaux biologiques détectés sur ce corps. |
| `exo_analyse` | `data/son/Exploration/ExoAnalyse.mp3` | Analyse terminée, commandant. Échantillon enregistré. |
| `exo_distance_ok` | `data/son/Exploration/ExoDistance.mp3` | Distance suffisante. Vous pouvez prélever. |
