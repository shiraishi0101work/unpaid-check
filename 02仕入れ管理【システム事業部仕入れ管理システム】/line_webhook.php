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

    // ── フォローイベント（友だち追加時）──
    if ($type === 'follow') {
        $replyToken = $event['replyToken'] ?? '';
        lineReply($replyToken, [[
            'type' => 'text',
            'text' => "システム事業部 備品購入申請Botです。\n\n備品を購入する前に、このBotから事前申請をお願いします。\n\n画面下部のメニューから「購入申請」をタップしてください。",
        ]]);
        // 管理者用：ユーザーIDを通知（初回設定用）
        error_log("LINE new follower userId: " . $userId);
        continue;
    }

    // ── メッセージイベント ──
    if ($type === 'message') {
        $text = $event['message']['text'] ?? '';
        $replyToken = $event['replyToken'] ?? '';

        if (mb_strpos($text, '申請') !== false || mb_strpos($text, '購入') !== false) {
            // LIFF URLを案内
            $liffUrl = 'https://liff.line.me/' . LINE_LIFF_ID;
            lineReply($replyToken, [[
                'type' => 'text',
                'text' => "以下のリンクから購入申請フォームを開いてください。\n\n" . $liffUrl,
            ]]);
        } elseif (mb_strpos($text, '状況') !== false || mb_strpos($text, '確認') !== false) {
            // 自分の申請状況を確認
            $requests = getMyRequests($userId);
            if (empty($requests)) {
                lineReply($replyToken, [[
                    'type' => 'text',
                    'text' => '現在、未処理の申請はありません。',
                ]]);
            } else {
                $lines = ["あなたの申請状況:\n"];
                foreach ($requests as $r) {
                    $statusLabel = match($r['status']) {
                        'pending'  => '承認待ち',
                        'approved' => '承認済',
                        'rejected' => '却下',
                        default    => $r['status'],
                    };
                    $lines[] = "- {$r['name']} \\{$r['price']}  [{$statusLabel}]";
                }
                lineReply($replyToken, [[
                    'type' => 'text',
                    'text' => implode("\n", $lines),
                ]]);
            }
        } else {
            lineReply($replyToken, [[
                'type' => 'text',
                'text' => "以下のキーワードで操作できます:\n\n「申請」... 購入申請フォームを開く\n「確認」... 申請状況を確認する",
            ]]);
        }
        continue;
    }

    // ── Postbackイベント（承認/却下ボタン）──
    if ($type === 'postback') {
        $data = $event['postback']['data'] ?? '';
        $replyToken = $event['replyToken'] ?? '';
        parse_str($data, $params);

        $pbAction = $params['action'] ?? '';
        $pbId     = (int)($params['id'] ?? 0);

        if ($pbAction === 'approve' && $pbId > 0) {
            $result = callLocalApi('approve', ['id' => $pbId]);
            if (isset($result['ok']) && $result['ok']) {
                lineReply($replyToken, [[
                    'type' => 'text',
                    'text' => "申請 #{$pbId} を承認しました。\n発注一覧に登録されました。",
                ]]);
            } else {
                lineReply($replyToken, [[
                    'type' => 'text',
                    'text' => '処理できませんでした: ' . ($result['error'] ?? '不明なエラー'),
                ]]);
            }
        } elseif ($pbAction === 'reject' && $pbId > 0) {
            $result = callLocalApi('reject', ['id' => $pbId]);
            if (isset($result['ok']) && $result['ok']) {
                lineReply($replyToken, [[
                    'type' => 'text',
                    'text' => "申請 #{$pbId} を却下しました。",
                ]]);
            } else {
                lineReply($replyToken, [[
                    'type' => 'text',
                    'text' => '処理できませんでした: ' . ($result['error'] ?? '不明なエラー'),
                ]]);
            }
        }
        continue;
    }
}

http_response_code(200);
echo json_encode(['ok' => true]);

// ═══════════════════════════════════════════
//  ヘルパー関数
// ═══════════════════════════════════════════

/**
 * LINE Reply Message
 */
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

/**
 * 自分の申請を取得
 */
function getMyRequests($userId) {
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

/**
 * ローカルAPIを内部呼び出し（承認/却下処理）
 */
function callLocalApi($action, $data) {
    // 直接DB操作する（HTTPリクエストを避ける）
    try {
        $db = new PDO('sqlite:' . __DIR__ . '/iwata_assist.db');
        $db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        $db->exec('PRAGMA journal_mode=WAL');
        $id = (int)$data['id'];

        $st = $db->prepare('SELECT * FROM purchase_requests WHERE id=? AND status="pending"');
        $st->execute([$id]);
        $req = $st->fetch(PDO::FETCH_ASSOC);
        if (!$req) return ['error' => '申請が見つからないか、既に処理済みです'];

        if ($action === 'approve') {
            // ordersテーブルに登録
            $s = $db->prepare('INSERT INTO orders (date,name,shop,qty,price,sell_price,client,status,memo,category,owner)
                VALUES (?,?,?,?,?,?,?,"未発注",?,?,?)');
            $s->execute([
                date('Y-m-d'),
                $req['name'],
                $req['shop'],
                (int)$req['qty'],
                (int)$req['price'],
                (int)$req['sell_price'],
                $req['client'],
                $req['memo'],
                $req['category'],
                $req['requester'],
            ]);
            $orderId = (int)$db->lastInsertId();

            // DellaScore同期
            $dsDbPath = __DIR__ . '/../01営業管理システム【della score】/della_score.db';
            if (file_exists($dsDbPath)) {
                try {
                    $dsDb = new PDO('sqlite:' . $dsDbPath);
                    $dsDb->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
                    $dsDb->exec('CREATE TABLE IF NOT EXISTS store (key TEXT PRIMARY KEY, value TEXT NOT NULL)');
                    $ss = $dsDb->prepare('SELECT value FROM store WHERE key=?');
                    $ss->execute(['purchases']);
                    $r = $ss->fetch();
                    $purchases = $r ? (json_decode($r['value'], true) ?: []) : [];
                    $amount = (int)$req['price'] * (int)$req['qty'];
                    $purchases[] = [
                        'id' => 'iw_' . $orderId,
                        'supplier' => $req['shop'] ?: '（購入先未記入）',
                        'desc' => $req['name'],
                        'amount' => $amount,
                        'tax' => (int)round($amount * 0.1),
                        'issued' => date('Y-m-d'),
                        'due' => '', 'bank' => '', 'items' => '',
                        'status' => 'unpaid',
                        'owner' => $req['requester'],
                        'iw_order_id' => $orderId,
                    ];
                    $ss = $dsDb->prepare('INSERT OR REPLACE INTO store (key, value) VALUES (?, ?)');
                    $ss->execute(['purchases', json_encode(array_values($purchases), JSON_UNESCAPED_UNICODE)]);
                } catch (Exception $e) { /* ignore */ }
            }

            $s = $db->prepare('UPDATE purchase_requests SET status="approved", approved_at=?, order_id=? WHERE id=?');
            $s->execute([date('Y-m-d H:i:s'), $orderId, $id]);

            // 申請者に通知
            if ($req['requester_id']) {
                $msg = "【承認されました】\n\n商品: {$req['name']}\n\n購入を進めてください。";
                linePushFromWebhook($req['requester_id'], $msg);
            }

            return ['ok' => true, 'orderId' => $orderId];

        } elseif ($action === 'reject') {
            $s = $db->prepare('UPDATE purchase_requests SET status="rejected", approved_at=? WHERE id=?');
            $s->execute([date('Y-m-d H:i:s'), $id]);

            if ($req['requester_id']) {
                $msg = "【却下されました】\n\n商品: {$req['name']}\n\n詳細は管理者にお問い合わせください。";
                linePushFromWebhook($req['requester_id'], $msg);
            }

            return ['ok' => true];
        }

        return ['error' => '不明なアクション'];
    } catch (Exception $e) {
        return ['error' => $e->getMessage()];
    }
}

function linePushFromWebhook($to, $text) {
    $ch = curl_init('https://api.line.me/v2/bot/message/push');
    curl_setopt_array($ch, [
        CURLOPT_POST => true,
        CURLOPT_HTTPHEADER => [
            'Content-Type: application/json',
            'Authorization: Bearer ' . LINE_CHANNEL_ACCESS_TOKEN,
        ],
        CURLOPT_POSTFIELDS => json_encode([
            'to' => $to,
            'messages' => [['type' => 'text', 'text' => $text]],
        ], JSON_UNESCAPED_UNICODE),
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => 10,
    ]);
    curl_exec($ch);
    curl_close($ch);
}
