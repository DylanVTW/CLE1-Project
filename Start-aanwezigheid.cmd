@echo off
cd /d "%~dp0"
set "NODE=%~dp0.runtime\node-v24.22.1-win-x64\node.exe"
if not exist "%NODE%" set "NODE=node"
"%NODE%" -e "if(Number(process.versions.node.split('.')[0])<24)process.exit(1)" >nul 2>nul
if errorlevel 1 (
  echo Installeer Node.js 24 of nieuwer en probeer opnieuw.
  pause
  exit /b 1
)
if not exist "node_modules\serialport\package.json" (
  if exist ".runtime\node-v24.22.1-win-x64\node_modules\npm\bin\npm-cli.js" (
    "%NODE%" ".runtime\node-v24.22.1-win-x64\node_modules\npm\bin\npm-cli.js" ci --no-audit --no-fund
  ) else (
    call npm ci --no-audit --no-fund
  )
  if errorlevel 1 (
    pause
    exit /b 1
  )
)
if not defined PORT set "PORT=8080"
"%NODE%" -e "fetch('http://127.0.0.1:'+process.env.PORT+'/api/attendance').then(r=>r.json()).then(d=>process.exit(d.people&&d.reader?0:1)).catch(()=>process.exit(1))" >nul 2>nul
if not errorlevel 1 (
  start "" "http://127.0.0.1:%PORT%/aanwezigheid.html"
  exit /b 0
)
start "" "http://127.0.0.1:%PORT%/aanwezigheid.html"
"%NODE%" "Back-end\attendance_server.js"
pause
