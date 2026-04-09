@echo off
chcp 65001 > nul
title 未入金チェックシステム

cd /d "%~dp0"

echo ===================================
echo  未入金チェックシステム 起動中...
echo ===================================

:: .envが存在しなければ.env.exampleからコピー
if not exist .env (
    echo .envファイルが見つかりません。.env.exampleをコピーします...
    copy .env.example .env
    echo .envを編集してAPIキーを設定してください。
    pause
    exit /b
)

:: 依存パッケージのインストール確認
python -c "import flask" 2>nul
if errorlevel 1 (
    echo 依存パッケージをインストールしています...
    pip install -r requirements.txt
)

:: アプリ起動
python app.py

pause
