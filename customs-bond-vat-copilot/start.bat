@echo off
title Customs Bond Audit Intelligence Platform
cd /d "%~dp0"
set LOG=setup-log.txt
echo Customs Bond Audit setup log > "%LOG%" 2>nul

echo.
echo   ============================================================
echo     Customs Bond Audit Intelligence Platform
echo   ============================================================
echo.

REM ---------- 0) Are we in a properly extracted folder? ----------
if not exist "backend\requirements.txt" goto NOTEXTRACTED
if not exist "backend\run_server.py"    goto NOTEXTRACTED

REM ---------- 1) Find Python ----------
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY ( where python >nul 2>nul && set "PY=python" )
if not defined PY goto NOPYTHON

REM ---------- 2) Python version must be 3.10 - 3.13 ----------
REM   pandas has no ready-made packages for 3.14 yet.
%PY% -c "import sys; sys.exit(0 if (3,10)<=sys.version_info[:2]<=(3,13) else 1)" >nul 2>nul
if errorlevel 1 goto BADPYTHON

echo   Python paoa gelo.
echo.

REM ---------- 3) Backend packages ----------
if not exist ".venv\Scripts\python.exe" (
  echo   [1/2] Package namano hocche ^(1-3 minute^)...
  %PY% -m venv .venv >> "%LOG%" 2>&1
  if errorlevel 1 goto FAIL_VENV
  ".venv\Scripts\python.exe" -m pip install --upgrade pip >> "%LOG%" 2>&1
  ".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt >> "%LOG%" 2>&1
  if errorlevel 1 goto FAIL_PIP
) else (
  echo   [1/2] Package agei ache.
)

echo   [2/2] Server chalu hocche...
echo.

REM ---------- 4) Launch ----------
start "" http://localhost:4800
".venv\Scripts\python.exe" backend\run_server.py

echo.
echo   Server bondho hoyeche.
pause
exit /b 0

REM ============================================================
:NOTEXTRACTED
echo   [!] Ei folder-e backend paoa jay nai.
echo.
echo   Sombhoboto ZIP file-ti NA KHULE, tar bhitor theke ei file-ti
echo   chalano hoyeche. Windows ZIP-ke folder-er moto dekhay, kintu
echo   bhitor theke chalale kaj kore na.
echo.
echo   JA KORBEN:
echo     1. ZIP file-e DAN-click korun
echo     2. "Extract All..." bachun, tarpor "Extract"
echo     3. JE NOTUN FOLDER toiri holo, seti khulun
echo     4. sekhan theke start.bat e double-click korun
echo.
goto END

:NOPYTHON
echo   [!] Python paoa jay nai.
echo.
echo   Ekhan theke Python 3.13 install korun:
echo       https://www.python.org/downloads/release/python-3130/
echo.
echo   ** Install-er somoy "Add Python to PATH" box-e tick din. **
echo   Install-er por computer restart korun.
echo.
goto END

:BADPYTHON
echo   [!] Python-er version somorthito noy.
%PY% -c "import sys;print('      Python %%d.%%d' %% sys.version_info[:2])" 2>nul
echo.
echo   Ei software-e Python 3.10 theke 3.13 lage.
echo   ^(3.14 ba tar upore kichu package ekhono toiri hoy nai.^)
echo.
echo   Ekhan theke 3.13 naman:
echo       https://www.python.org/downloads/release/python-3130/
echo.
echo   Ekadhik Python thakle osubidha nai - pashapashi thakte pare.
echo.
goto END

:FAIL_VENV
echo   [!] Python environment toiri hoy nai.
goto LOGHINT

:FAIL_PIP
echo   [!] Package install hoy nai.
echo       Internet connection thik ache kina dekhun.
goto LOGHINT

:LOGHINT
echo.
echo   Bistarito karon ei file-e lekha ache:
echo       %CD%\%LOG%
echo.
echo   File-ti khule sesher koyekti line dekhun, ba amake pathan.
echo.
goto END

:END
echo   ------------------------------------------------------------
echo   Ei window bondho korte Enter chapun.
echo   ^(Uporer lekha-ti age pore nin - window bondho hoye jabe.^)
echo   ------------------------------------------------------------
pause >nul
exit /b 1
