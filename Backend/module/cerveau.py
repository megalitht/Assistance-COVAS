# module/cerveau.py
import asyncio
import json
import random

CHEMIN_BARKS = "D:/Assistance-COVAS/Backend/data/barks.json"

async def generer_replique_ia(action: str, texte_utilisateur: str = "") -> str:
    """
    Lit le JSON et retourne le chemin d'un fichier audio au hasard pour l'action donnée.
    """
    try:
        with open(CHEMIN_BARKS, "r", encoding="utf-8") as f:
            barks = json.load(f)
            
        # On vérifie si l'action existe bien dans le dictionnaire
        if action in barks and "reponses" in barks[action]:
            chemins_possibles = barks[action]["reponses"]
            
            if chemins_possibles:
                # On choisit un fichier au hasard dans la liste
                chemin_choisi = random.choice(chemins_possibles)
                # On retourne un chemin absolu propre
                return f"D:/Assistance-COVAS/Backend/{chemin_choisi}"
                
    except Exception as e:
        print(f"[Cerveau] Erreur lors de la lecture du JSON : {e}")
        
    return None