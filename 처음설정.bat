@echo off
title Daphne - First Setup
cd /d "%~dp0"
echo ================================================================
echo   위저드리 다프네 매크로 - 처음설정
echo   처음 쓸 때, 그리고 업데이트(새 버전 덮어쓰기) 뒤에 꼭 한 번 실행하세요.
echo ================================================================
echo [1단계] 파이썬 설치 여부를 검사합니다...
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 goto NOPY
python src\first_setup.py
echo.
pause
exit /b

:NOPY
echo.
echo   [X] 파이썬이 없거나 3.10 미만입니다. 아래 순서대로 설치해 주세요.
echo     1) https://www.python.org/downloads/ 에서 Windows용 Python 3.10 이상을 받습니다.
echo     2) 설치 첫 화면 아래쪽의 "Add python.exe to PATH" 를 반드시 체크하고 Install Now.
echo     3) 설치가 끝나면 이 창을 닫고, 처음설정.bat 을 다시 실행합니다.
echo        (창을 새로 열어야 설치한 파이썬이 인식됩니다)
echo.
pause
exit /b
