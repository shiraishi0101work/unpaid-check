@echo off
chcp 65001 > nul
echo.
echo  ╔══════════════════════════════════╗
echo  ║       MEOレポーター 起動中        ║
echo  ╚══════════════════════════════════╝
echo.
cd /d "%~dp0"
start "" "http://localhost:3000"
node dist/server.js
pause
