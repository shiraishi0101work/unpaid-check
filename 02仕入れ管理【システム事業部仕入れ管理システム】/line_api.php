<?php
/**
 * LINE 購入報告 API エンドポイント
 * LIFFフォームからの報告送信・納品先管理
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
        status       TEXT DEFAULT "registered",
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

// ── 購入報告送信（LIFFフォームから）→ 即時orders登録 ──
if ($action === 'submit_report') {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); echo json_encode(['error'=>'method']); exit; }
    $db = getDb();

    $name      = trim($body['name'] ?? '');
    $price     = (int)($body['price'] ?? 0);
    $client    = trim($body['client'] ?? '');
    $requester = trim($body['requester'] ?? '');

    if (!$name)       { echo json_encode(['error'=>'商品名を入力してください']); exit; }
    if ($price <= 0)  { echo json_encode(['error'=>'仕入単価を入力してください']); exit; }
    if (!$client)     { echo json_encode(['error'=>'納品先を選択してください']); exit; }

    $qty         = max(1, (int)($body['qty'] ?? 1));
    $sellPrice   = (int)($body['sellPrice'] ?? 0);
    $shop        = trim($body['shop'] ?? '');
    $category    = trim($body['category'] ?? '物品');
    $memo        = trim($body['memo'] ?? '');
    $requesterId = trim($body['requesterId'] ?? '');

    // ── 1. ordersテーブルに即時登録 ──
    $clientName = $client;
    try { $db->prepare('INSERT OR IGNORE INTO clients (name,created) VALUES (?,?)')->execute([$clientName, date('Y-m-d')]); } catch(Exception $e) {}

    $s = $db->prepare('INSERT INTO orders (date,name,shop,brand,url,qty,price,sell_price,delivery_date,client,cc_id,status,memo,category,owner)
        VALUES (:date,:name,:shop,:brand,:url,:qty,:price,:sell_price,:delivery_date,:client,:cc_id,:status,:memo,:category,:owner)');
    $owner = $requester ?: '不明';
    $s->execute([
        ':date'          => date('Y-m-d'),
        ':name'          => $name,
        ':shop'          => $shop,
        ':brand'         => '',
        ':url'           => '',
        ':qty'           => $qty,
        ':price'         => $price,
        ':sell_price'    => $sellPrice,
        ':delivery_date' => '',
        ':client'        => $clientName,
        ':cc_id'         => null,
        ':status'        => '発注済',
        ':memo'          => $memo,
        ':category'      => $category,
        ':owner'         => $owner,
    ]);
    $orderId = (int)$db->lastInsertId();

    // ── 2. DellaScore仕入れ同期 ──
    syncToDellaScore($orderId, $name, $shop, $price, $qty, $owner);

    // ── 3. 報告履歴に記録 ──
    $s = $db->prepare('INSERT INTO purchase_requests
        (request_date, requester, requester_id, name, shop, qty, price, sell_price, client, category, memo, status, order_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "registered", ?)');
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
        $orderId,
    ]);

    // ── 4. グループLINEに通知 ──
    sendGroupNotification($requester, $name, $shop, $price, $qty, $sellPrice, $client, $category, $memo);

    echo json_encode(['ok'=>true, 'orderId'=>$orderId]);
    exit;
}

// ── 報告履歴一覧（管理画面用）──
if ($action === 'reports') {
    $db = getDb();
    $rows = $db->query('SELECT * FROM purchase_requests ORDER BY id DESC')->fetchAll(PDO::FETCH_ASSOC);
    echo json_encode($rows);
    exit;
}

// ═══════════════════════════════════════════
//  ヘルパー関数
// ═══════════════════════════════════════════

/**
 * グループLINEに購入報告通知を送信
 */
function sendGroupNotification($requester, $name, $shop, $price, $qty, $sellPrice, $client, $category, $memo) {
    $subtotal = $price * $qty;

    $flexContents = [
        'type' => 'bubble',
        'header' => [
            'type' => 'box',
            'layout' => 'vertical',
            'backgroundColor' => '#00A89D',
            'paddingAll' => '16px',
            'contents' => [
                ['type' => 'text', 'text' => '新規入力ありがとうございます', 'color' => '#ffffff', 'weight' => 'bold', 'size' => 'md'],
                ['type' => 'text', 'text' => '報告者: ' . $requester, 'color' => '#ffffffcc', 'size' => 'sm', 'margin' => 'sm'],
            ]
        ],
        'body' => [
            'type' => 'box',
            'layout' => 'vertical',
            'spacing' => 'md',
            'paddingAll' => '16px',
            'contents' => [
                infoRow('商品名', $name),
                infoRow('購入先', $shop ?: '未記入'),
                infoRow('単価(税抜)', '\\' . number_format($price)),
                infoRow('数量', (string)$qty),
                infoRow('小計(税抜)', '\\' . number_format($subtotal)),
                infoRow('納品先', $client),
                infoRow('カテゴリ', $category),
            ]
        ],
    ];

    if ($sellPrice > 0) {
        $profit = $sellPrice * $qty - $subtotal;
        $flexContents['body']['contents'][] = infoRow('販売価格', '\\' . number_format($sellPrice));
        $flexContents['body']['contents'][] = infoRow('粗利', '\\' . number_format($profit));
    }

    if ($memo) {
        $flexContents['body']['contents'][] = [
            'type' => 'separator', 'margin' => 'lg',
        ];
        $flexContents['body']['contents'][] = [
            'type' => 'box', 'layout' => 'vertical', 'margin' => 'md',
            'contents' => [
                ['type' => 'text', 'text' => 'メモ', 'size' => 'xs', 'color' => '#8C8C8C'],
                ['type' => 'text', 'text' => $memo, 'size' => 'sm', 'wrap' => true, 'margin' => 'xs'],
            ]
        ];
    }

    $message = [
        'type' => 'flex',
        'altText' => '【購入報告】' . $name . ' - ' . $requester,
        'contents' => $flexContents,
    ];

    linePush(LINE_GROUP_ID, [$message]);
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
}

/**
 * DellaScore仕入れ同期
 */
function syncToDellaScore($orderId, $name, $shop, $price, $qty, $owner) {
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

        $amount = $price * $qty;
        $purchases[] = [
            'id'          => 'iw_' . $orderId,
            'supplier'    => $shop ?: '（購入先未記入）',
            'desc'        => $name . ($qty > 1 ? 'x' . $qty : ''),
            'amount'      => $amount,
            'tax'         => (int)round($amount * 0.1),
            'issued'      => date('Y-m-d'),
            'due'         => '',
            'bank'        => '',
            'items'       => '',
            'status'      => 'unpaid',
            'owner'       => $owner,
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
