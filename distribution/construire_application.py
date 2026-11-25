"""
construire_application.py — Fabrique l'application COVAS à partager : Application/COVAS/COVAS.exe

    CONSTRUIRE APPLICATION.bat           (à la racine du projet)
    CONSTRUIRE APPLICATION.bat --installateur   (+ « Application/Installer COVAS.exe », à envoyer)
    CONSTRUIRE APPLICATION.bat --zip            (+ Application/COVAS.zip)

L'installateur (distribution/covas.iss, Inno Setup 6) détecte la carte graphique : NVIDIA -> version
complète, sinon version processeur (sans le grand modèle ni les bibliothèques NVIDIA).

Besoin : PyInstaller dans .venv (pip install pyinstaller). Le dossier produit ne demande rien
d'installé chez la personne qui le reçoit : Python, les bibliothèques, les modèles vocaux et les
bibliothèques NVIDIA sont dedans.

Le dossier garde la forme des sources (COVAS.exe, Backend/, Frontend/) : les modules retrouvent
data/, les modèles et l'interface aux mêmes places relatives.

N'y vont PAS : les données personnelles (config.toml avec PIN et clé Inara, suivi de jeu, réglages
de l'interface, journaux, profil de la fenêtre), les prises brutes du studio vocal, les tests,
les anciens plans de vaisseaux.
"""
import json
from datetime import date
import os
import shutil
import subprocess
import sys
import zipfile

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(ICI)
BACKEND = os.path.join(RACINE, "Backend")
FRONTEND = os.path.join(RACINE, "Frontend")
SORTIE = os.path.join(RACINE, "Application")
TRAVAIL = os.path.join(RACINE, ".construction")
APPLI = os.path.join(SORTIE, "COVAS")
CONTENU = os.path.join(APPLI, "Backend")        # dossier interne de PyInstaller, nommé comme les sources

DONNEES = ["barks.json", "conversations.json", "exobiologie.json", "SCRIPT_VOIX.md",
           "SCRIPT_CONVERSATIONS.md", "son", os.path.join("studio", "originaux.json")]
LISEZ_MOI = "LISEZ-MOI.txt"
MODELES = ["modele_vocal_turbo", "modele_vocal_fr"]
NVIDIA = ["cublas", "cudnn", "cuda_nvrtc"]       # bibliothèques de Whisper sur carte graphique
NVIDIA_INUTILES = {"nvblas64_12.dll"}


def _site_packages():
    return next(p for p in sys.path if p.endswith("site-packages") and os.path.isdir(p))


def _modules_du_covas():
    """Tous les modules de Backend/module : ils sont importés dans des fonctions, au clic."""
    noms = ["main", "studio_vocal"]
    for dossier, _, fichiers in os.walk(os.path.join(BACKEND, "module")):
        if "__pycache__" in dossier:
            continue
        for fichier in fichiers:
            if fichier.endswith(".py"):
                chemin = os.path.relpath(os.path.join(dossier, fichier[:-3]), BACKEND)
                noms.append(chemin.replace(os.sep, ".").removesuffix(".__init__"))
    return sorted(noms)


def pyinstaller():
    arguments = [
        sys.executable, "-m", "PyInstaller", os.path.join(BACKEND, "app.py"),
        "--name", "COVAS", "--windowed", "--onedir", "--noconfirm", "--clean",
        "--contents-directory", "Backend",
        "--distpath", SORTIE, "--workpath", os.path.join(TRAVAIL, "build"),
        "--specpath", TRAVAIL, "--paths", BACKEND,
        "--collect-all", "faster_whisper", "--collect-all", "ctranslate2",
        "--collect-all", "webview",
        "--exclude-module", "tkinter", "--exclude-module", "pytest",
    ]
    for nom in _modules_du_covas():
        arguments += ["--hidden-import", nom]
    subprocess.run(arguments, check=True, cwd=RACINE)


def _copier(source, destination, ignorer=None):
    if os.path.isdir(source):
        shutil.copytree(source, destination, ignore=ignorer, dirs_exist_ok=True)
    else:
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copy2(source, destination)


def fichiers():
    caches = shutil.ignore_patterns("__pycache__", ".cache", "*.pyc")
    # Interface (les anciens plans mis de côté par l'atelier restent ici)
    _copier(FRONTEND, os.path.join(APPLI, "Frontend"), shutil.ignore_patterns("anciens", "__pycache__"))
    # Répliques, sons, conversations
    for nom in DONNEES:
        _copier(os.path.join(BACKEND, "data", nom), os.path.join(CONTENU, "data", nom), caches)
    # Studio vocal : les réglages de la voix, sans le micro ni l'étalonnage (propres à ce PC et à cette voix)
    with open(os.path.join(BACKEND, "data", "studio", "reglages.json"), encoding="utf-8") as f:
        studio = json.load(f)
    studio.update(micro=None, egalisation=None, reference_hz=None, etalonnage=None)
    with open(os.path.join(CONTENU, "data", "studio", "reglages.json"), "w", encoding="utf-8") as f:
        json.dump(studio, f, ensure_ascii=False, indent=2)
        f.write("\n")
    # Modèles de reconnaissance vocale
    for nom in MODELES:
        source = os.path.join(BACKEND, "module", nom)
        if os.path.isfile(os.path.join(source, "model.bin")):
            _copier(source, os.path.join(CONTENU, "module", nom), caches)
        else:
            print(f"Attention : modèle {nom} absent, l'application s'en passera.")
    # Bibliothèques NVIDIA (chargées par module/son/whisper.py)
    for nom in NVIDIA:
        source = os.path.join(_site_packages(), "nvidia", nom, "bin")
        if not os.path.isdir(source):
            print(f"Attention : nvidia/{nom} absent : pas de reconnaissance vocale sur carte graphique.")
            continue
        for dll in os.listdir(source):
            if dll.lower().endswith(".dll") and dll not in NVIDIA_INUTILES:
                _copier(os.path.join(source, dll), os.path.join(CONTENU, "nvidia", nom, "bin", dll))


def archiver():
    chemin = os.path.join(SORTIE, "COVAS.zip")
    with zipfile.ZipFile(chemin, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for dossier, _, noms in os.walk(APPLI):
            for nom in noms:
                complet = os.path.join(dossier, nom)
                archive.write(complet, os.path.relpath(complet, SORTIE))
    return chemin


def _iscc():
    for base in (os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs"),
                 os.environ.get("ProgramFiles(x86)", ""), os.environ.get("ProgramFiles", "")):
        chemin = os.path.join(base, "Inno Setup 6", "ISCC.exe")
        if os.path.isfile(chemin):
            return chemin
    raise SystemExit("Inno Setup 6 introuvable : winget install JRSoftware.InnoSetup")


def installateur():
    subprocess.run([_iscc(), f"/DSource={APPLI}", f"/DVersion={date.today():%Y.%m.%d}",
                    os.path.join(ICI, "covas.iss")], check=True)
    return os.path.join(SORTIE, "Installer COVAS.exe")


def taille(dossier):
    return sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(dossier) for f in fs)


if __name__ == "__main__":
    if "--sans-exe" not in sys.argv:          # --sans-exe : reprend Application/COVAS tel quel
        if os.path.isdir(APPLI):
            shutil.rmtree(APPLI)
        pyinstaller()
        fichiers()
    _copier(os.path.join(ICI, LISEZ_MOI), os.path.join(APPLI, LISEZ_MOI))
    print(f"\nApplication prête : {APPLI}  ({taille(APPLI) / 1e9:.1f} Go)")
    if "--installateur" in sys.argv:
        print(f"Installateur : {installateur()}")
    if "--zip" in sys.argv:
        print(f"Archive : {archiver()}")
