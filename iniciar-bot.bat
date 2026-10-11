@echo off
rem Doble clic: instala todo y deja el bot de Telegram del estudio funcionando.
rem Opciones: iniciar-bot.bat -Estado  |  iniciar-bot.bat -Desinstalar  |  iniciar-bot.bat -Actualizar
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0desplegar-bot.ps1" %*
echo.
pause
