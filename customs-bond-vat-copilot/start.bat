@echo off
chcp 65001 >nul
title Customs Bond Audit Intelligence Platform
cd /d "%~dp0"

echo.
echo   ============================================================
echo     Customs Bond Audit Intelligence Platform
echo   ============================================================
echo.

REM ---------- 1) Find Python ----------
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY ( where python >nul 2>nul && set "PY=python" )

if not defined PY (
  echo   [!] Python paoa jay nai.
  echo.
  echo   Ei link theke Python 3.11 ba tar poroborti version install korun:
  echo       https://www.python.org/downloads/
  echo.
  echo   ** Install korar somoy "Add Python to PATH" box-e tick din. **
  echo.
  pause
  exit /b 1
)

REM ---------- 2) First run: build environment ----------
if not exist ".venv\Scripts\python.exe" (
  echo   Prothombar chalu hocche - proyojoniyo package install kora hocche.
  echo   Ei kaj-ti 2-5 minute nite pare. Onugroho kore opekkha korun...
  echo.
  %PY% -m venv .venv
  if errorlevel 1 (
    echo   [!] Environment toiri hoy nai. Python thik moto install hoyeche kina dekhun.
    pause
    exit /b 1
  )
  ".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
  ".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
  if errorlevel 1 (
    echo.
    echo   [!] Package install e somossa hoyeche. Internet connection dekhun.
    pause
    exit /b 1
  )
  echo.
  echo   Environment toiri holo.
  echo.
)

REM ---------- 3) Launch ----------
echo   Server chalu hocche... Browser nije-i khule jabe.
echo   Bondho korte ei window-te CTRL+C chapun.
echo.
start "" http://localhost:4800
".venv\Scripts\python.exe" backend\run_server.py

echo.
echo   Server bondho hoyeche.
pause
