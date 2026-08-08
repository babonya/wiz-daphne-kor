@echo off
chcp 65001 >nul
title Stop Daphne Remote Control (Background)
cd /d "%~dp0"
python -c "import server; server.stop_background_server()"
pause
