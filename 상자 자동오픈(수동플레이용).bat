@echo off
title Daphne - Chest Auto Open (manual play)
cd /d "%~dp0"
echo Chest auto-open only: handles chest screens while you play manually.
python src/chest_only.py
if %errorlevel%==3 pause
