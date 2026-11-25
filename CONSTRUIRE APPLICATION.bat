@echo off
rem Fabrique l'application a partager : Application\COVAS\COVAS.exe (voir distribution\construire_application.py).
rem Ajoute --zip pour obtenir aussi Application\COVAS.zip.
"%~dp0.venv\Scripts\python.exe" "%~dp0distribution\construire_application.py" %*
pause
