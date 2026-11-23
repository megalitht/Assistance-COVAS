"""
Lecture de l'écran du jeu : y a-t-il une étoile droit devant le vaisseau ?

Le jeu n'écrit nulle part « cible obstruée ». On regarde donc le centre de l'image
(là où se trouve la cible quand le vaisseau est aligné) : si une bonne part des pixels
y sont presque blancs, c'est qu'une étoile se trouve dans l'axe et masque la cible.

Capture GDI de Windows (aucune dépendance en plus de numpy). Le jeu doit être en
« plein écran fenêtré » (borderless) ou fenêtré : en plein écran exclusif, Windows
renvoie souvent une image noire.

Calibrage : lance `python -m module.ecran` depuis Backend/, le jeu au premier plan,
et regarde la part affichée face à une étoile puis face au vide.
"""
import ctypes
import os
import time

import numpy as np

from module import macros

_PRET = os.name == "nt"
if _PRET:
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    # Handles 64 bits : sans ces déclarations, ctypes les tronque et tout plante
    user32.FindWindowW.restype = wintypes.HWND
    user32.FindWindowW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR)
    user32.GetClientRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
    user32.ClientToScreen.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.POINT))
    user32.GetDC.restype = wintypes.HDC
    user32.GetDC.argtypes = (wintypes.HWND,)
    user32.ReleaseDC.argtypes = (wintypes.HWND, wintypes.HDC)
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateCompatibleDC.argtypes = (wintypes.HDC,)
    gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
    gdi32.CreateCompatibleBitmap.argtypes = (wintypes.HDC, ctypes.c_int, ctypes.c_int)
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.SelectObject.argtypes = (wintypes.HDC, wintypes.HGDIOBJ)
    gdi32.BitBlt.argtypes = (wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                             wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD)
    gdi32.GetDIBits.argtypes = (wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
                                ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT)
    gdi32.DeleteObject.argtypes = (wintypes.HGDIOBJ,)
    gdi32.DeleteDC.argtypes = (wintypes.HDC,)
    try:
        user32.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
        user32.SetThreadDpiAwarenessContext.argtypes = (ctypes.c_void_p,)
    except AttributeError:          # Windows trop ancien : coordonnées non mises à l'échelle
        pass

    class _BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                    ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                    ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD)]

_SRCCOPY = 0x00CC0020
_DPI_PAR_ECRAN_V2 = -4      # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2


def _zone_jeu(part):
    """(x, y, largeur, hauteur) à l'écran du carré central de la fenêtre du jeu,
    de côté `part` × la hauteur (part=1 : toute la fenêtre). None si pas de fenêtre."""
    fenetre = user32.FindWindowW(macros.FENETRE_JEU, None)
    if not fenetre:
        return None
    rect, coin = wintypes.RECT(), wintypes.POINT(0, 0)
    if not user32.GetClientRect(fenetre, ctypes.byref(rect)) \
            or not user32.ClientToScreen(fenetre, ctypes.byref(coin)):
        return None
    largeur, hauteur = rect.right - rect.left, rect.bottom - rect.top
    if largeur <= 0 or hauteur <= 0:
        return None
    if part >= 1:
        return coin.x, coin.y, largeur, hauteur
    cote = max(8, int(min(largeur, hauteur) * part))
    return coin.x + (largeur - cote) // 2, coin.y + (hauteur - cote) // 2, cote, cote


def _capturer(x, y, largeur, hauteur):
    """Pixels de l'écran dans ce rectangle : tableau (hauteur, largeur, 3) en BGR."""
    ecran = user32.GetDC(None)
    if not ecran:
        return None
    memoire = gdi32.CreateCompatibleDC(ecran)
    image = gdi32.CreateCompatibleBitmap(ecran, largeur, hauteur)
    try:
        ancien = gdi32.SelectObject(memoire, image)
        copie = gdi32.BitBlt(memoire, 0, 0, largeur, hauteur, ecran, x, y, _SRCCOPY)
        gdi32.SelectObject(memoire, ancien)
        if not copie:
            return None
        entete = _BITMAPINFOHEADER(biSize=ctypes.sizeof(_BITMAPINFOHEADER), biWidth=largeur,
                                   biHeight=-hauteur, biPlanes=1, biBitCount=32, biCompression=0)
        tampon = (ctypes.c_ubyte * (largeur * hauteur * 4))()
        # place pour la table de couleurs (inutilisée en 32 bits)
        info = ctypes.create_string_buffer(bytes(entete) + bytes(16))
        if gdi32.GetDIBits(memoire, image, 0, hauteur, tampon, info, 0) != hauteur:
            return None
        return np.frombuffer(tampon, dtype=np.uint8).reshape(hauteur, largeur, 4)[:, :, :3]
    finally:
        gdi32.DeleteObject(image)
        gdi32.DeleteDC(memoire)
        user32.ReleaseDC(None, ecran)


def _image_jeu(part):
    """Capture du centre de la fenêtre du jeu, ou None (pas Windows, jeu caché...)."""
    if not _PRET or not macros.jeu_au_premier_plan():
        return None
    ancien = None
    try:   # coordonnées en vrais pixels, même avec une mise à l'échelle Windows (125 %...)
        ancien = user32.SetThreadDpiAwarenessContext(_DPI_PAR_ECRAN_V2)
    except AttributeError:
        pass
    try:
        zone = _zone_jeu(part)
        return _capturer(*zone) if zone else None
    except OSError:
        return None
    finally:
        if ancien:
            user32.SetThreadDpiAwarenessContext(ancien)


def part_etoile():
    """Part (0 à 1) de pixels presque blancs au centre de l'écran du jeu.
    None si l'écran ne peut pas être lu (jeu pas au premier plan, capture impossible)."""
    image = _image_jeu(macros.ETOILE_ZONE)
    if image is None:
        return None
    return float((image.min(axis=2) >= macros.ETOILE_SEUIL_LUMIERE).mean())


def etoile_devant():
    """True : étoile dans l'axe. False : voie libre. None : écran illisible."""
    part = part_etoile()
    return None if part is None else part >= macros.ETOILE_PART_OBSTRUCTION


def ecran_lisible():
    """False si la capture renvoie une image noire (plein écran exclusif, en général).
    None si on ne peut pas savoir (jeu pas au premier plan)."""
    image = _image_jeu(1)
    if image is None:
        return None
    return bool(image[::8, ::8].max() > 20)      # le HUD du cockpit n'est jamais tout noir


if __name__ == "__main__":
    print("Mets le jeu au premier plan (Ctrl+C pour arrêter)")
    print(f"Seuil d'obstruction : {macros.ETOILE_PART_OBSTRUCTION:.1%}")
    while True:
        p = part_etoile()
        print("écran illisible (jeu caché ?)" if p is None else
              f"pixels blancs au centre : {p:6.1%}  ->  "
              f"{'ÉTOILE DEVANT' if p >= macros.ETOILE_PART_OBSTRUCTION else 'voie libre'}")
        time.sleep(1)
