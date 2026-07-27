@echo off
title Wizardry Daphne Antigravity Bot - 1.14.1-hotfix10
cd /d "%~dp0"
set MACRO_SESSION_START=%date% %time%
echo Starting Wizardry Daphne Bot...
python src/main.py
pause