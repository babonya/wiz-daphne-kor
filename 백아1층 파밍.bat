@echo off
echo WOLF_1F_CHEST> "%~dp0daphne_preset_id.txt"
title Daphne - Wolf1F ChestFarm
cd /d "%~dp0"
if exist "restart_counter.txt" del "restart_counter.txt"
set MACRO_SESSION_START=%date% %time%
echo Starting Wizardry Daphne Bot (Wolf 1F Chest Farm)...
python src/main.py
