@echo off
rem Lance l'application COVAS (fenêtre native, sans console).
rem Journal du terminal : Backend\data\covas.log
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0Backend\app.py"
