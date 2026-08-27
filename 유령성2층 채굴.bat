@echo off
echo GHOST_2F_MINE> "%~dp0daphne_preset_id.txt"
title Daphne - Ghost2F Mine
cd /d "%~dp0"
set MACRO_SESSION_START=%date% %time%
echo Starting Wizardry Daphne Bot...
python src/main.py
