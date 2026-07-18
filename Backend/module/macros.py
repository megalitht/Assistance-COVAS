# macros.py
import pydirectinput

def executer_touches(action: str):
    """
    Reçoit un nom d'action en paramètre et exécute la macro clavier correspondante
    via pydirectinput.
    """
    if action == "train_atterrissage":
        pydirectinput.press('l')
    elif action == "soute":
        pydirectinput.press('home')



    elif action == "energie_mtr":
        pydirectinput.press('down') 
        pydirectinput.press('up', presses=4) 

    elif action == "energie_sys":
        pydirectinput.press('down') 
        pydirectinput.press('left', presses=4)

    elif action == "energie_arm":
        pydirectinput.press('down') 
        pydirectinput.press('right', presses=4)

    elif action == "reset":
        pydirectinput.press('down')



    elif action == "lock":
        pydirectinput.press('t')
    
    elif action == "boost":
        pydirectinput.press('tab')



    elif action == "mode_combat":
        pydirectinput.press('left', presses=4)
        pydirectinput.press('right', presses=4)

    elif action == "mode_croisiere":
        pydirectinput.press('left', presses=4)
        pydirectinput.press('up', presses=4)

    elif action == "mode_récuperation":
        pydirectinput.press('up', presses=4)
        pydirectinput.press('left', presses=4)



    elif action == "fsd":
        pydirectinput.press('j')
    else:
        print(f"[Macros] Aucune touche associée à l'action : {action}")