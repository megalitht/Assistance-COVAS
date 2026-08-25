import os
import glob
import json
import asyncio

# Chemin standard des logs Elite Dangerous sous Windows
CHEMIN_STATUS = os.path.expanduser('~') + r"\Saved Games\Frontier Developments\Elite Dangerous\Status.json"
CHEMIN_LOGS = os.path.expanduser('~') + r"\Saved Games\Frontier Developments\Elite Dangerous\Journal.*.log"
etat_vaisseau_actuel = {}

def obtenir_dernier_journal():
    liste_fichiers = glob.glob(CHEMIN_LOGS)
    if not liste_fichiers:
        return None
    # Trie par date de modification pour choper le log actuel
    return max(liste_fichiers, key=os.path.getctime)

async def surveiller_logs(tts_queue, generer_replique_func):
    fichier_journal = obtenir_dernier_journal()
    if not fichier_journal:
        print("[Logs] Aucun journal Elite Dangerous trouvé.")
        return

    print(f"[Logs] Surveillance activée sur : {os.path.basename(fichier_journal)}")

    with open(fichier_journal, 'r', encoding='utf-8') as f:
        # Se placer à la toute fin du fichier pour ne lire que les nouveaux événements
        f.seek(0, 2)
        
        while True:
            ligne = f.readline()
            if not ligne:
                await asyncio.sleep(0.5) # Polling léger, zéro impact CPU
                continue
            
            try:
                evenement = json.loads(ligne)
                nom_event = evenement.get("event")

                # --- ALERTE BOUCLIER ---
                if nom_event == "ShieldState" and not evenement.get("ShieldsUp"):
                    chemin_audio = await generer_replique_func("alerte_bouclier")
                    if chemin_audio: await tts_queue.put(chemin_audio)

                # --- ALERTE BLINDAGE (<= 30%) ---
                elif nom_event == "HullDamage" and evenement.get("Health", 1.0) <= 0.30:
                    chemin_audio = await generer_replique_func("alerte_blindage")
                    if chemin_audio: await tts_queue.put(chemin_audio)

                # --- ANALYSE DE COMBAT (Kill confirmé) ---
                elif nom_event in ["Bounty", "FactionKillBond"]:
                    chemin_audio = await generer_replique_func("kill_confirme")
                    if chemin_audio: await tts_queue.put(chemin_audio)

            except json.JSONDecodeError:
                pass
            
async def surveiller_status_json():
    """Vérifie en boucle si le fichier Status.json a été modifié par le jeu."""
    global etat_vaisseau_actuel
    derniere_modif = 0
    
    print("[Logs] Surveillance de Status.json activée.")
    
    while True:
        if os.path.exists(CHEMIN_STATUS):
            modif_actuelle = os.path.getmtime(CHEMIN_STATUS)
            
            if modif_actuelle != derniere_modif:
                derniere_modif = modif_actuelle
                try:
                    with open(CHEMIN_STATUS, 'r', encoding='utf-8') as f:
                        etat_vaisseau_actuel = json.load(f)
                        # Le dictionnaire etat_vaisseau_actuel est maintenant à jour en temps réel
                except Exception as e:
                    # Ignore les erreurs de lecture si le jeu est en train d'écrire dans le fichier
                    pass
                    
        await asyncio.sleep(0.5) # Fréquence de rafraîchissement très légère