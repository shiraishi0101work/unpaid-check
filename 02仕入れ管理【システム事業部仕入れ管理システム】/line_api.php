<?php
/**
 * LINE LIFF / Webhook 用 API エンドポイント
 * 既存の api.php とは別に、LINE専用の処理をまとめる
 */
header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { exit; }

require_once __DIR__ . '/line_config.php';

$action = $_GET['action'] ?? '';
$body   = json_decode(file_get_contents('php://input'), true) ?? [];

function getDb() {
    $db = new PDO('sqlite:' . __DIR__ . '/iwata_assist.db');
    $db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $db->exec('PRAGMA journal_mode=WAL');
    // purchase_requests テーブル確保
    $db->exec('CREATE TABLE IF NOT EXISTS purchase_requests (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        request_date TEXT NOT NULL,
        requester    TEXT NOT NULL DEFAULT "",
        requester_id TEXT DEFAULT "",
        name         TEXT NOT NULL,
        shop         TEXT DEFAULT "",
        qty          INTEGER DEFAULT 1,
        price        INTEGER DEFAULT 0,
        sell_price   INTEGER DEFAULT 0,
        client       TEXT DEFAULT "",
        category     TEXT DEFAULT "物品",
        memo         TEXT DEFAULT "",
        status       TEXT DEFAULT "pending",
        approved_by  TEXT DEFAULT "",
        approved_at  TEXT DEFAULT "",
        order_id     INTEGER DEFAULT NULL
    )');
    return $db;
}

// ── 納品先一覧（LIFFフォーム用）──
if ($action === 'clients') {
    $db = getDb();
    $db->exec('CREATE TABLE IF NOT EXISTS clients (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        name    TEXT NOT NULL UNIQUE,
        created TEXT DEFAULT ""
    )');
    $rows = $db->query('SELECT * FROM clients ORDER BY name')->fetchAll(PDO::FETCH_ASSOC);
    echo json_encode(array_map(fn($r) => ['id'=>(int)$r['id'],'name'=>$r['name']], $rows));
    exit;
}

// ── 納品先追加（LIFFフォームから）──
if ($action === 'add_client') {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); echo json_encode(['error'=>'method']); exit; }
    $db = getDb();
    $name = trim($body['name'] ?? '');
    if (!$name) { echo json_encode(['error'=>'名前を入力してください']); exit; }
    try {
        $db->exec('CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, created TEXT DEFAULT "")');
        $s = $db->prepare('INSERT OR IGNORE INTO clients (name, created) VALUES (?, ?)');
        $s->execute([$name, date('Y-m-d')]);
        echo json_encode(['ok'=>true, 'name'=>$name]);
    } catch (Exception $e) {
        echo json_encode(['ok'=>true, 'name'=>$name]);
    }
    exit;
}

// ── 申請送信（LIFFフォームから）──
if ($action === 'submit_request') {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); echo json_encode(['error'=>'method']); exit; }
    $db = getDb();

    $name      = trim($body['name'] ?? '');
    $price     = (int)($body['price'] ?? 0);
    $client    = trim($body['client'] ?? '');
    $requester = trim($body['requester'] ?? '');

    if (!$name)       { echo json_encode(['error'=>'商品名を入力してください']); exit; }
    if ($price <= 0)  { echo json_encode(['error'=>'仕入単価を入力してください']); exit; }
    if (!$client)     { echo json_encode(['error'=>'納品先を選択してください']); exit; }

    $qty       = max(1, (int)($body['qty'] ?? 1));
    $sellPrice = (int)($body['sellPrice'] ?? 0);
    $shop      = trim($body['shop'] ?? '');
    $category  = trim($body['category'] ?? '物品');
    $memo      = trim($body['memo'] ?? '');
    $requesterId = trim($body['requesterId'] ?? '');

    $s = $db->prepare('INSERT INTO purchase_requests
        (request_date, requester, requester_id, name, shop, qty, price, sell_price, client, category, memo, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "pending")');
    $s->execute([
        date('Y-m-d H:i:s'),
        $requester,
        $requesterId,
        $name,
        $shop,
        $qty,
        $price,
        $sellPrice,
        $client,
        $category,
        $memo,
    ]);
    $requestId = (int)$db->lastInsertId();

    // 管理者にLINE通知
    sendApprovalNotification($requestId, [
        'requester' => $requester,
        'name'      => $name,
        'shop'      => $shop,
        'qty'       => $qty,
        'price'     => $price,
        'sellPrice' => $sellPrice,
        'client'    => $client,
        'category'  => $category,
        'memo'      => $memo,
    ]);

    echo json_encode(['ok'=>true, 'id'=>$requestId]);
    exit;
}

// ── 申請一覧（管理画面用）──
if ($action === 'requests') {
    $db = getDb();
    $status = $_GET['status'] ?? '';
    $sql = 'SELECT * FROM purchase_requests';
    if ($status) {
        $sql .= ' WHERE status = ?';
        $s = $db->prepare($sql . ' ORDER BY id DESC');
        $s->execute([$status]);
    } else {
        $s = $db->query($sql . ' ORDER BY id DESC');
    }
    $rows = $s->fetchAll(PDO::FETCH_ASSOC);
    echo json_encode($rows);
    exit;
}

// ── 承認処理（Webhookから呼ばれる）──
if ($action === 'approve') {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); echo json_encode(['error'=>'method']); exit; }
    $db = getDb();
    $id = (int)($body['id'] ?? 0);

    $st = $db->prepare('SELECT * FROM purchase_requests WHERE id=? AND status="pending"');
    $st->execute([$id]);
    $req = $st->fetch(PDO::FETCH_ASSOC);
    if (!$req) { echo json_encode(['error'=>'申請が見つかりません']); exit; }

    // ordersテーブルに登録
    $db->exec('CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL, name TEXT NOT NULL, shop TEXT DEFAULT "",
        brand TEXT DEFAULT "", url TEXT DEFAULT "", qty INTEGER DEFAULT 1,
        price INTEGER DEFAULT 0, sell_price INTEGER DEFAULT 0,
        delivery_date TEXT DEFAULT "", client TEXT DEFAULT "",
        cc_id INTEGER DEFAULT NULL, status TEXT DEFAULT "未発注",
        memo TEXT DEFAULT "", category TEXT DEFAULT "物品", owner TEXT DEFAULT "岩田"
    )');

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
    syncToDellaScore($orderId, $req);

    // 申請ステータス更新
    $s = $db->prepare('UPDATE purchase_requests SET status="approved", approved_at=?, order_id=? WHERE id=?');
    $s->execute([date('Y-m-d H:i:s'), $orderId, $id]);

    // 申請者に承認通知
    if ($req['requester_id']) {
        sendReplyToRequester($req['requester_id'], $req['name'], 'approved');
    }

    echo json_encode(['ok'=>true, 'orderId'=>$orderId]);
    exit;
}

// ── 却下処理（Webhookから呼ばれる）──
if ($action === 'reject') {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); echo json_encode(['error'=>'method']); exit; }
    $db = getDb();
    $id = (int)($body['id'] ?? 0);

    $st = $db->prepare('SELECT * FROM purchase_requests WHERE id=? AND status="pending"');
    $st->execute([$id]);
    $req = $st->fetch(PDO::FETCH_ASSOC);
    if (!$req) { echo json_encode(['error'=>'申請が見つかりません']); exit; }

    $s = $db->prepare('UPDATE purchase_requests SET status="rejected", approved_at=? WHERE id=?');
    $s->execute([date('Y-m-d H:i:s'), $id]);

    // 申請者に却下通知
    if ($req['requester_id']) {
        sendReplyToRequester($req['requester_id'], $req['name'], 'rejected');
    }

    echo json_encode(['ok'=>true]);
    exit;
}

// ═══════════════════════════════════════════
//  LINE Messaging API ヘルパー関数
// ═══════════════════════════════════════════

/**
 * 管理者に承認依頼のFlex Messageを送信
 */
function sendApprovalNotification($requestId, $data) {
    $subtotal = $data['price'] * $data['qty'];
    $profitText = '';
    if ($data['sellPrice'] > 0) {
        $profit = $data['sellPrice'] * $data['qty'] - $subtotal;
        $profitText = '粗利: \\' . number_format($profit);
    }

    $flexContents = [
        'type' => 'bubble',
        'header' => [
            'type' => 'box',
            'layout' => 'vertical',
            'backgroundColor' => '#00A89D',
            'contents' => [
                ['type' => 'text', 'text' => '備品購入申請', 'color' => '#ffffff', 'weight' => 'bold', 'size' => 'lg'],
                ['type' => 'text', 'text' => '申請者: ' . $data['requester'], 'color' => '#ffffffcc', 'size' => 'sm', 'margin' => 'sm'],
            ]
        ],
        'body' => [
            'type' => 'box',
            'layout' => 'vertical',
            'spacing' => 'md',
            'contents' => [
                infoRow('商品名', $data['name']),
                infoRow('購入先', $data['shop'] ?: '未記入'),
                infoRow('単価', '\\' . number_format($data['price'])),
                infoRow('数量', (string)$data['qty']),
                infoRow('小計(税抜)', '\\' . number_format($subtotal)),
                infoRow('納品先', $data['client']),
                infoRow('カテゴリ', $data['category']),
            ]
        ],
        'footer' => [
            'type' => 'box',
            'layout' => 'horizontal',
            'spacing' => 'md',
            'contents' => [
                [
                    'type' => 'button',
                    'action' => ['type' => 'postback', 'label' => '承認', 'data' => 'action=approve&id=' . $requestId],
                    'style' => 'primary',
                    'color' => '#00A89D',
                    'height' => 'sm',
                ],
                [
                    'type' => 'button',
                    'action' => ['type' => 'postback', 'label' => '却下', 'data' => 'action=reject&id=' . $requestId],
                    'style' => 'secondary',
                    'height' => 'sm',
                ],
            ]
        ]
    ];

    if ($data['sellPrice'] > 0) {
        $flexContents['body']['contents'][] = infoRow('販売価格', '\\' . number_format($data['sellPrice']));
    }
    if ($profitText) {
        $flexContents['body']['contents'][] = infoRow('粗利', $profitText);
    }
    if ($data['memo']) {
        $flexContents['body']['contents'][] = [
            'type' => 'box', 'layout' => 'vertical', 'margin' => 'lg',
            'contents' => [
                ['type' => 'text', 'text' => 'メモ', 'size' => 'xs', 'color' => '#8C8C8C'],
                ['type' => 'text', 'text' => $data['memo'], 'size' => 'sm', 'wrap' => true],
            ]
        ];
    }

    $message = [
        'type' => 'flex',
        'altText' => '【備品購入申請】' . $data['name'] . ' - ' . $data['requester'],
        'contents' => $flexContents,
    ];

    linePush(LINE_ADMIN_USER_ID, [$message]);
}

function infoRow($label, $value) {
    return [
        'type' => 'box',
        'layout' => 'horizontal',
        'contents' => [
            ['type' => 'text', 'text' => $label, 'size' => 'sm', 'color' => '#8C8C8C', 'flex' => 3],
            ['type' => 'text', 'text' => $value, 'size' => 'sm', 'weight' => 'bold', 'flex' => 5, 'wrap' => true],
        ]
    ];
}

/**
 * 申請者に承認/却下の結果を通知
 */
function sendReplyToRequester($userId, $itemName, $result) {
    if ($result === 'approved') {
        $text = "【承認されました】\n\n商品: {$itemName}\n\n購入を進めてください。";
    } else {
        $text = "【却下されました】\n\n商品: {$itemName}\n\n詳細は管理者にお問い合わせください。";
    }
    linePush($userId, [['type' => 'text', 'text' => $text]]);
}

/**
 * LINE Push Message 送信
 */
function linePush($to, $messages) {
    $ch = curl_init('https://api.line.me/v2/bot/message/push');
    curl_setopt_array($ch, [
        CURLOPT_POST => true,
        CURLOPT_HTTPHEADER => [
            'Content-Type: application/json',
            'Authorization: Bearer ' . LINE_CHANNEL_ACCESS_TOKEN,
        ],
        CURLOPT_POSTFIELDS => json_encode([
            'to' => $to,
            'messages' => $messages,
        ], JSON_UNESCAPED_UNICODE),
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => 10,
    ]);
    $res = curl_exec($ch);
    $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    if ($code !== 200) {
        error_log("LINE Push failed: HTTP {$code} - {$res}");
    }
    return $code === 200;
}

/**
 * DellaScore仕入れ同期
 */
function syncToDellaScore($orderId, $req) {
    $dsDbPath = __DIR__ . '/../01営業管理システム【della score】/della_score.db';
    if (!file_exists($dsDbPath)) return;
    try {
        $db = new PDO('sqlite:' . $dsDbPath);
        $db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        $db->exec('CREATE TABLE IF NOT EXISTS store (key TEXT PRIMARY KEY, value TEXT NOT NULL)');
        $s = $db->prepare('SELECT value FROM store WHERE key=?');
        $s->execute(['purchases']);
        $r = $s->fetch();
        $purchases = $r ? (json_decode($r['value'], true) ?: []) : [];

        $amount = (int)$req['price'] * (int)$req['qty'];
        $tax = (int)round($amount * 0.1);
        $purchases[] = [
            'id'          => 'iw_' . $orderId,
            'supplier'    => $req['shop'] ?: '（購入先未記入）',
            'desc'        => $req['name'] . ((int)$req['qty'] > 1 ? 'x' . $req['qty'] : ''),
            'amount'      => $amount,
            'tax'         => $tax,
            'issued'      => date('Y-m-d'),
            'due'         => '',
            'bank'        => '',
            'items'       => '',
            'status'      => 'unpaid',
            'owner'       => $req['requester'],
            'iw_order_id' => $orderId,
        ];

        $s = $db->prepare('INSERT OR REPLACE INTO store (key, value) VALUES (?, ?)');
        $s->execute(['purchases', json_encode(array_values($purchases), JSON_UNESCAPED_UNICODE)]);
    } catch (Exception $e) {
        error_log('DS sync error: ' . $e->getMessage());
    }
}

http_response_code(400);
echo json_encode(['error' => 'unknown action']);
