@echo off
echo GHOST_4F_CHEST> "%~dp0daphne_preset_id.txt"
title Daphne - Ghost4F ChestFarm
cd /d "%~dp0"
set MACRO_SESSION_START=%date% %time%
echo Starting Wizardry Daphne Bot (Ghost 4F Chest Farm)...
python src/main.py
