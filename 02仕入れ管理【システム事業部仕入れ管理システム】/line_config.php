<?php
// LINE Messaging API 設定
// LINE Developers (https://developers.line.biz/) で取得した値を設定してください

// チャネルシークレット（Messaging API チャネル → チャネル基本設定）
define('LINE_CHANNEL_SECRET', 'ここにチャネルシークレットを貼り付け');

// チャネルアクセストークン（Messaging API チャネル → Messaging API設定 → 長期トークン発行）
define('LINE_CHANNEL_ACCESS_TOKEN', 'ここにチャネルアクセストークンを貼り付け');

// LIFF ID（LINE Developers → LIFFタブ → LIFF アプリ追加で取得）
define('LINE_LIFF_ID', 'ここにLIFF IDを貼り付け');

// 通知先グループID
// Botをグループに招待後、Webhookイベントの source.groupId で確認できます
// （初回招待時にログに出力されます）
define('LINE_GROUP_ID', 'ここにグループIDを貼り付け');

// このサーバーの公開URL（末尾スラッシュなし）
// 例: https://example.com  や  https://xxxx.ngrok-free.app
define('LINE_BASE_URL', 'ここにサーバーの公開URLを貼り付け');
