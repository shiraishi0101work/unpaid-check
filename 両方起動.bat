@echo off
title 両サーバー起動

REM === Della Score (port 8080) ===
tasklist /fi "imagename eq php.exe" 2>nul | find /i "php.exe" >nul
if errorlevel 1 (
  start /min "PHP 8080 DellaScore" php -S localhost:8080 -t "%~dp001営業管理システム【della score】"
  timeout /t 2 /nobreak >nul
)

REM === イワタアシスト (port 8081) ===
start /min "PHP 8081 IwataAssist" php -S localhost:8081 -t "%~dp002仕入れ管理【イワタアシスト】"
timeout /t 2 /nobreak >nul

REM === トンネル (Della Score) ===
start "Tunnel DellaScore" cmd /k "title Tunnel-DellaScore && :loop && ssh -R 80:localhost:8080 nokey@localhost.run && timeout /t 3 /nobreak >nul && goto loop"

REM === トンネル (イワタアシスト) ===
start "Tunnel IwataAssist" cmd /k "title Tunnel-IwataAssist && :loop && ssh -R 80:localhost:8081 nokey@localhost.run && timeout /t 3 /nobreak >nul && goto loop"

echo.
echo 両サーバー起動＆トンネル接続中...
echo DellaScore  : localhost:8080
echo IwataAssist : localhost:8081
echo.
pause
