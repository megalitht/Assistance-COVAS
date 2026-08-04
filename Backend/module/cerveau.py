# module/cerveau.py
import json
import random

CHEMIN_BARKS = "D:/Assistance-COVAS/Backend/data/barks.json"

async def obtenir_chemin_audio(action: str, polite: bool = False) -> str:
    """
    Cherche et retourne le chemin d'un fichier audio depuis barks.json. 
    Gère la politesse (30%) et les easter eggs génériques (15%).
    """
    if polite and random.random() < 0.30:
        return "D:/Assistance-COVAS/Backend/data/son/Easter-egg/SVP.wav"

    try:
        with open(CHEMIN_BARKS, "r", encoding="utf-8") as f:
            barks = json.load(f)
            
        if action in barks:
            if "easter_egg" in barks[action] and barks[action]["easter_egg"]:
                if random.random() < 0.15: 
                    chemin_choisi = random.choice(barks[action]["easter_egg"])
                    return f"D:/Assistance-COVAS/Backend/{chemin_choisi}"

            if "reponses" in barks[action] and barks[action]["reponses"]:
                chemin_choisi = random.choice(barks[action]["reponses"])
                # On évite de crasher si la chaîne est vide (comme dans "energie_arm")
                if chemin_choisi: 
                    return f"D:/Assistance-COVAS/Backend/{chemin_choisi}"
                
    except Exception as e:
        print(f"[Routeur Audio] Erreur lors de la lecture du JSON : {e}")
        
    return None