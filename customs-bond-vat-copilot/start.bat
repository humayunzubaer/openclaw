@echo off
REM Windows — এই ফাইলে ডাবল-ক্লিক করলেই অ্যাপ চালু হয়ে ব্রাউজার খোলে।
cd /d "%~dp0"

where node >nul 2>nul
if errorlevel 1 (
  echo.
  echo   [!] Node.js paoa jayni.
  echo   Prothome https://nodejs.org theke Node.js ^(LTS^) install korun,
  echo   tarpor abar ei file-e double-click korun.
  echo.
  pause
  exit /b 1
)

echo   Customs Bond ^& VAT Audit Copilot chalu hocche...
start "" http://localhost:4700
node src\server.js
pause
