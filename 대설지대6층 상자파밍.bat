@echo off
echo ISBERG_HEAVYSNOW_6F_CHEST> "%~dp0daphne_preset_id.txt"
title Daphne - Heavysnow6F ChestFarm
cd /d "%~dp0"
if exist "restart_counter.txt" del "restart_counter.txt"
set MACRO_SESSION_START=%date% %time%
echo Starting Wizardry Daphne Bot (Isberg Heavysnow 6F Chest Farm)...
python src/main.py
