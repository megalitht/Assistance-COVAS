@echo off
rem Lance l'application COVAS avec le terminal habillé visible (diagnostic).
"%~dp0.venv\Scripts\python.exe" "%~dp0Backend\app.py"
pause
