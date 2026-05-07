@echo off
cd /d "%~dp0"
title Della Score サーバー

tasklist /fi "imagename eq php.exe" 2>/dev/null | find /i "php.exe" >/dev/null
if errorlevel 1 (
    echo PHPサーバーを起動中...
    powershell -WindowStyle Hidden -Command "Set-Location \047%~dp0\047; php -S localhost:8080"  &
    timeout /t 2 /nobreak >/dev/null
) else (
    echo PHPサーバーは既に起動しています
)

echo.
echo ===================================
echo  サーバー起動完了
echo  ローカル: http://localhost:8080
echo ===================================
echo.
echo 公開URLを取得中... (自動再接続あり)
echo このウィンドウは閉じないでください
echo.

:reconnect
ssh -o StrictHostKeyChecking=no -R 80:localhost:8080 nokey@localhost.run
echo.
echo [切断されました。3秒後に再接続します...]
timeout /t 3 /nobreak >/dev/null
goto reconnect
