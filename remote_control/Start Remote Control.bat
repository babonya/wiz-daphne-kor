@echo off
title Daphne Remote Control Server
cd /d "%~dp0"
echo 원격 제어 수신 서버를 시작합니다...
python server.py
pause
