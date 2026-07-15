<?php
/**
 * LINE Webhook エンドポイント
 * LINE Developers の Webhook URL にこのファイルのURLを設定する
 * 例: https://example.com/line_webhook.php
 */
require_once __DIR__ . '/line_config.php';

// 署名検証
$body = file_get_contents('php://input');
$signature = $_SERVER['HTTP_X_LINE_SIGNATURE'] ?? '';
$hash = base64_encode(hash_hmac('sha256', $body, LINE_CHANNEL_SECRET, true));

if ($signature !== $hash) {
    http_response_code(403);
    exit;
}

$events = json_decode($body, true)['events'] ?? [];

foreach ($events as $event) {
    $type   = $event['type'] ?? '';
    $userId = $event['source']['userId'] ?? '';

    // ── グループ参加イベント（groupId確認用）──
    if ($type === 'join') {
        $groupId = $event['source']['groupId'] ?? '';
        error_log("LINE Bot joined group. groupId: " . $groupId);
        $replyToken = $event['replyToken'] ?? '';
        lineReply($replyToken, [[
            'type' => 'text',
            'text' => "備品購入報告Botです。\nグループID: " . $groupId . "\n\nこのIDを line_config.php の LINE_GROUP_ID に設定してください。",
        ]]);
        continue;
    }

    // ── フォローイベント（友だち追加時）──
    if ($type === 'follow') {
        $replyToken = $event['replyToken'] ?? '';
        $liffUrl = 'https://liff.line.me/' . LINE_LIFF_ID;
        lineReply($replyToken, [[
            'type' => 'text',
            'text' => "備品購入報告Botです。\n\n備品を購入したら、以下から報告をお願いします。\n\n" . $liffUrl,
        ]]);
        error_log("LINE new follower userId: " . $userId);
        continue;
    }

    // ── メッセージイベント ──
    if ($type === 'message') {
        $text = $event['message']['text'] ?? '';
        $replyToken = $event['replyToken'] ?? '';

        if (mb_strpos($text, '報告') !== false || mb_strpos($text, '購入') !== false || mb_strpos($text, '入力') !== false) {
            $liffUrl = 'https://liff.line.me/' . LINE_LIFF_ID;
            lineReply($replyToken, [[
                'type' => 'text',
                'text' => "以下から購入報告フォームを開いてください。\n\n" . $liffUrl,
            ]]);
        } elseif (mb_strpos($text, '履歴') !== false || mb_strpos($text, '確認') !== false) {
            $reports = getMyReports($userId);
            if (empty($reports)) {
                lineReply($replyToken, [[
                    'type' => 'text',
                    'text' => '報告履歴はまだありません。',
                ]]);
            } else {
                $lines = ["あなたの報告履歴（直近10件）:\n"];
                foreach ($reports as $r) {
                    $date = substr($r['request_date'], 0, 10);
                    $lines[] = "{$date}  {$r['name']}  \\{$r['price']}  → {$r['client']}";
                }
                lineReply($replyToken, [[
                    'type' => 'text',
                    'text' => implode("\n", $lines),
                ]]);
            }
        } else {
            $liffUrl = 'https://liff.line.me/' . LINE_LIFF_ID;
            lineReply($replyToken, [[
                'type' => 'text',
                'text' => "以下のキーワードで操作できます:\n\n「報告」... 購入報告フォームを開く\n「履歴」... 報告履歴を確認する\n\n" . $liffUrl,
            ]]);
        }
        continue;
    }
}

http_response_code(200);
echo json_encode(['ok' => true]);

// ═══════════════════════════════════════════
//  ヘルパー関数
// ═══════════════════════════════════════════

function lineReply($replyToken, $messages) {
    if (!$replyToken) return;
    $ch = curl_init('https://api.line.me/v2/bot/message/reply');
    curl_setopt_array($ch, [
        CURLOPT_POST => true,
        CURLOPT_HTTPHEADER => [
            'Content-Type: application/json',
            'Authorization: Bearer ' . LINE_CHANNEL_ACCESS_TOKEN,
        ],
        CURLOPT_POSTFIELDS => json_encode([
            'replyToken' => $replyToken,
            'messages'   => $messages,
        ], JSON_UNESCAPED_UNICODE),
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => 10,
    ]);
    curl_exec($ch);
    curl_close($ch);
}

function getMyReports($userId) {
    try {
        $db = new PDO('sqlite:' . __DIR__ . '/iwata_assist.db');
        $db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        $s = $db->prepare('SELECT * FROM purchase_requests WHERE requester_id=? ORDER BY id DESC LIMIT 10');
        $s->execute([$userId]);
        return $s->fetchAll(PDO::FETCH_ASSOC);
    } catch (Exception $e) {
        return [];
    }
}
