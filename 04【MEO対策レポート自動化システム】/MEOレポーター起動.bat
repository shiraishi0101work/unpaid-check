@echo off
chcp 65001 > nul
echo.
echo  ╔══════════════════════════════════╗
echo  ║       MEOレポーター 起動中        ║
echo  ╚══════════════════════════════════╝
echo.

cd /d "%~dp0"

REM ポート3000を使用中のプロセスを終了
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":3000 "') do (
  taskkill /f /pid %%a > nul 2>&1
)

timeout /t 1 /nobreak > nul

start "" "http://localhost:3000"
node dist/server.js
pause
