@echo off
cd /d "%~dp0"
title Server Start
tasklist /fi "imagename eq php.exe" 2>nul | find /i "php.exe" >nul
if errorlevel 1 (
  start /min "PHP Server" php -S localhost:8080
  timeout /t 2 /nobreak >nul
)
echo.
echo Server started. Connecting tunnel...
echo.
:loop
ssh -R 80:localhost:8080 nokey@localhost.run
timeout /t 3 /nobreak >nul
goto loop
