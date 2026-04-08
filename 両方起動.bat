@echo off
title 両サーバー起動

REM === Della Score (port 8080) ===
tasklist /fi "imagename eq php.exe" 2>nul | find /i "php.exe" >nul
if errorlevel 1 (
  start /min "PHP 8080 DellaScore" php -S 0.0.0.0:8080 -t "%~dp001営業管理システム【della score】"
  timeout /t 2 /nobreak >nul
)

REM === イワタアシスト (port 8081) ===
start /min "PHP 8081 IwataAssist" php -S 0.0.0.0:8081 -t "%~dp002仕入れ管理【イワタアシスト】"
timeout /t 2 /nobreak >nul

echo.
echo 両サーバー起動完了
echo.
echo ■ DellaScore
echo   http://100.67.184.75:8080
echo.
echo ■ イワタアシスト
echo   http://100.67.184.75:8081
echo.
echo ※ Tailscaleが入っているデバイスからのみアクセス可能
echo.
pause
