@echo off
rem Doble clic: arranca el bot de Telegram en esta PC (antes, una vez: .\setup.ps1).
cd /d "%~dp0"
".venv\Scripts\asg-telegram.exe"
pause
