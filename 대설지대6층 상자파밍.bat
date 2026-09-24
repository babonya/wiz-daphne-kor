@echo off
echo ISBERG_HEAVYSNOW_6F_CHEST> "%~dp0daphne_preset_id.txt"
title Daphne - Heavysnow6F ChestFarm
cd /d "%~dp0"
if exist "restart_counter.txt" del "restart_counter.txt"
if exist "macro.pid" del "macro.pid"
set MACRO_SESSION_START=%date% %time%
echo Starting Wizardry Daphne Bot (Isberg Heavysnow 6F Chest Farm)...

:loop
python src/main.py

set DAPHNE_MISS_COUNT=0
:check_replacement
REM [외부 슈퍼바이저] python이 방금 반환됨 - os.execv 자체재시작(윈도우는 새 PID로 새 프로세스를 띄우고
REM 원래 프로세스만 끝내는 방식이라 이 줄이 즉시 리턴됨) 도중일 수 있으니, macro.pid로 진짜 생존
REM 여부를 5회(약 5초) 연속 미확인해야 확정한다(느린 기동 오탐 방지 - 안 그러면 중복 인스턴스가 뜬다).
timeout /t 1 /nobreak >nul
set DAPHNE_CHILD_PID=
if exist "macro.pid" set /p DAPHNE_CHILD_PID=<macro.pid
if "%DAPHNE_CHILD_PID%"=="" goto miss
tasklist /FI "PID eq %DAPHNE_CHILD_PID%" /FO CSV /NH 2>NUL | find /I "python.exe" >NUL
if errorlevel 1 goto miss
set DAPHNE_MISS_COUNT=0
goto check_replacement

:miss
set /a DAPHNE_MISS_COUNT+=1
if %DAPHNE_MISS_COUNT% LSS 5 goto check_replacement

:real_death
echo.
echo [슈퍼바이저] 매크로 프로세스의 완전한 종료를 감지했습니다(자체재시작 후속 프로세스 없음) - 3초 후 재시작합니다.
timeout /t 3 /nobreak >nul
goto loop
