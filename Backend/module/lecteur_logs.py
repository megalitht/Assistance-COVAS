import os
import glob
import json
import asyncio
from module.serveur_ws import envoyer_donnees_web

# --- CHEMINS D'ACCÈS CORRIGÉS ---
DOSSIER_ED = r"C:\Users\antoi\Saved Games\Frontier Developments\Elite Dangerous"

CHEMIN_STATUS = os.path.join(DOSSIER_ED, "Status.json")
CHEMIN_LOGS = os.path.join(DOSSIER_ED, "Journal.*.log")
CHEMIN_NAVROUTE = os.path.join(DOSSIER_ED, "NavRoute.json")
CHEMIN_MODULES = os.path.join(DOSSIER_ED, "ModulesInfo.json")

# Vérification au lancement
if not os.path.exists(DOSSIER_ED):
    print(f"[Erreur Critique] Le dossier Elite n'a pas été trouvé à : {DOSSIER_ED}")
else:
    print(f"[Système] Pointage des logs confirmé sur : {DOSSIER_ED}")
    
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
async def surveiller_fichiers_auxiliaires():
    """Surveille les fichiers NavRoute et ModulesInfo pour la nouvelle interface UI."""
    dernieres_modifs = {"navroute": 0, "modules": 0}
    
    print("[Logs] Surveillance de NavRoute et ModulesInfo activée.")
    
    while True:
        # Surveillance de la Route de Navigation
        if os.path.exists(CHEMIN_NAVROUTE):
            modif_nav = os.path.getmtime(CHEMIN_NAVROUTE)
            if modif_nav != dernieres_modifs["navroute"]:
                dernieres_modifs["navroute"] = modif_nav
                try:
                    with open(CHEMIN_NAVROUTE, 'r', encoding='utf-8') as f:
                        donnees_nav = json.load(f)
                        await envoyer_donnees_web({
                            "type": "navroute",
                            "route": donnees_nav.get("Route", [])
                        })
                except Exception:
                    pass

        # Surveillance de l'Intégrité des Modules
        if os.path.exists(CHEMIN_MODULES):
            modif_mod = os.path.getmtime(CHEMIN_MODULES)
            if modif_mod != dernieres_modifs["modules"]:
                dernieres_modifs["modules"] = modif_mod
                try:
                    with open(CHEMIN_MODULES, 'r', encoding='utf-8') as f:
                        donnees_mod = json.load(f)
                        await envoyer_donnees_web({
                            "type": "modulesinfo",
                            "modules": donnees_mod.get("Modules", [])
                        })
                except Exception:
                    pass
                    
        await asyncio.sleep(1.0) # Check toutes les secondes, très léger
            
async def surveiller_status_json():
    global etat_vaisseau_actuel
    derniere_modif = 0
    
    print("[Logs] Surveillance de Status.json activée (avec WebSockets).")
    
    while True:
        if os.path.exists(CHEMIN_STATUS):
            modif_actuelle = os.path.getmtime(CHEMIN_STATUS)
            
            if modif_actuelle != derniere_modif:
                derniere_modif = modif_actuelle
                try:
                    with open(CHEMIN_STATUS, 'r', encoding='utf-8') as f:
                        etat_vaisseau_actuel = json.load(f)
                        
                        # Les "Flags" du Status.json déterminent l'état du vaisseau
                        flags = etat_vaisseau_actuel.get("Flags", 0)
                        
                        # Bit 6 (valeur 64) = HardpointsDeployed (Points d'emports sortis = Mode Combat)
                        en_combat = bool(flags & 64)
                        
                        # Extraction des pips (Sys, Eng, Wep)
                        pips = etat_vaisseau_actuel.get("Pips", [0, 0, 0])
                        
                        donnees_a_envoyer = {
                            "type": "status",
                            "en_combat": en_combat,
                            "flags": flags,
                            "pips_sys": pips[0],
                            "pips_eng": pips[1],
                            "pips_wep": pips[2],
                            "carburant": etat_vaisseau_actuel.get("Fuel", {}).get("FuelMain", 0)
                        }
                        
                        # Envoi en temps réel au 2ème écran
                        await envoyer_donnees_web(donnees_a_envoyer)
                        
                except Exception as e:
                    pass
                    
        await asyncio.sleep(0.5)