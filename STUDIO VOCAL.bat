@echo off
rem Lance le studio vocal : enregistre les répliques du COVAS avec ta voix (fenêtre à part, sans console).
rem Indépendant du COVAS (qui peut tourner en même temps). Journal : Backend\data\studio.log
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0Backend\studio_vocal.py"
