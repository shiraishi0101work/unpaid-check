@echo off
cd /d "%~dp0"
title AIブログマスター 仕様説明書管理

tasklist /fi "imagename eq php.exe" 2>nul | find /i "php.exe" >nul
if errorlevel 1 (
  start /min "PHP Server" php -S localhost:8086
  timeout /t 2 /nobreak >nul
)

start http://localhost:8086/viewer.php
echo.
echo ガイド閲覧: http://localhost:8086/viewer.php
echo 管理者ページ: http://localhost:8086/admin.php
echo このウィンドウを閉じるとサーバーが停止します。
pause
