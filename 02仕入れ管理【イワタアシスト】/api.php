<?php
session_start();
header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { exit; }

$action = $_GET['action'] ?? ($_POST['action'] ?? '');
$body   = json_decode(file_get_contents('php://input'), true) ?? [];
if (!$action && isset($body['action'])) $action = $body['action'];

// ── ログアウト ──
if ($action === 'logout') {
    session_destroy();
    echo json_encode(['ok' => true]);
    exit;
}

// ── 未ログインチェック ──
if (!isset($_SESSION['user'])) {
    http_response_code(401);
    echo json_encode(['error' => 'unauthenticated']);
    exit;
}

function getDb() {
    $db = new PDO('sqlite:' . __DIR__ . '/iwata_assist.db');
    $db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $db->exec('PRAGMA journal_mode=WAL');
    $db->exec('CREATE TABLE IF NOT EXISTS orders (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        date    TEXT NOT NULL,
        name    TEXT NOT NULL,
        shop    TEXT DEFAULT "",
        brand   TEXT DEFAULT "",
        url     TEXT DEFAULT "",
        qty     INTEGER DEFAULT 1,
        price   INTEGER DEFAULT 0,
        client  TEXT DEFAULT "",
        cc_id   INTEGER DEFAULT NULL,
        status  TEXT DEFAULT "未発注",
        memo    TEXT DEFAULT ""
    )');
    $db->exec('CREATE TABLE IF NOT EXISTS cards (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        name    TEXT NOT NULL,
        brand   TEXT DEFAULT "",
        last4   TEXT DEFAULT "",
        closing TEXT DEFAULT "",
        payment TEXT DEFAULT ""
    )');
    return $db;
}

// ── 発注一覧 ──
if ($action === 'orders') {
    $db = getDb();
    $rows = $db->query('SELECT * FROM orders ORDER BY date DESC, id DESC')->fetchAll(PDO::FETCH_ASSOC);
    $out = array_map(function($r) {
        return [
            'id'     => (int)$r['id'],
            'date'   => $r['date'],
            'name'   => $r['name'],
            'shop'   => $r['shop'],
            'brand'  => $r['brand'],
            'url'    => $r['url'],
            'qty'    => (int)$r['qty'],
            'price'  => (int)$r['price'],
            'client' => $r['client'],
            'ccId'   => $r['cc_id'] ? (int)$r['cc_id'] : null,
            'status' => $r['status'],
            'memo'   => $r['memo'],
        ];
    }, $rows);
    echo json_encode($out);
    exit;
}

// ── カード一覧 ──
if ($action === 'cards') {
    $db = getDb();
    $rows = $db->query('SELECT * FROM cards ORDER BY id')->fetchAll(PDO::FETCH_ASSOC);
    $out = array_map(function($r) {
        return [
            'id'      => (int)$r['id'],
            'name'    => $r['name'],
            'brand'   => $r['brand'],
            'last4'   => $r['last4'],
            'closing' => $r['closing'],
            'payment' => $r['payment'],
        ];
    }, $rows);
    echo json_encode($out);
    exit;
}

// ── 発注追加 ──
if ($action === 'add_order') {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); echo json_encode(['error'=>'method']); exit; }
    $db = getDb();
    $s = $db->prepare('INSERT INTO orders (date,name,shop,brand,url,qty,price,client,cc_id,status,memo)
                        VALUES (:date,:name,:shop,:brand,:url,:qty,:price,:client,:cc_id,:status,:memo)');
    $s->execute([
        ':date'   => $body['date']   ?? date('Y-m-d'),
        ':name'   => $body['name']   ?? '',
        ':shop'   => $body['shop']   ?? '',
        ':brand'  => $body['brand']  ?? '',
        ':url'    => $body['url']    ?? '',
        ':qty'    => (int)($body['qty']   ?? 1),
        ':price'  => (int)($body['price'] ?? 0),
        ':client' => $body['client'] ?? '',
        ':cc_id'  => $body['ccId']   ? (int)$body['ccId'] : null,
        ':status' => $body['status'] ?? '未発注',
        ':memo'   => $body['memo']   ?? '',
    ]);
    echo json_encode(['ok'=>true, 'id'=>(int)$db->lastInsertId()]);
    exit;
}

// ── 発注削除 ──
if ($action === 'del_order') {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); echo json_encode(['error'=>'method']); exit; }
    $db = getDb();
    $s = $db->prepare('DELETE FROM orders WHERE id=?');
    $s->execute([(int)$body['id']]);
    echo json_encode(['ok'=>true]);
    exit;
}

// ── カード追加 ──
if ($action === 'add_card') {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); echo json_encode(['error'=>'method']); exit; }
    $db = getDb();
    $s = $db->prepare('INSERT INTO cards (name,brand,last4,closing,payment) VALUES (:name,:brand,:last4,:closing,:payment)');
    $s->execute([
        ':name'    => $body['name']    ?? '',
        ':brand'   => $body['brand']   ?? '',
        ':last4'   => $body['last4']   ?? '',
        ':closing' => $body['closing'] ?? '',
        ':payment' => $body['payment'] ?? '',
    ]);
    echo json_encode(['ok'=>true, 'id'=>(int)$db->lastInsertId()]);
    exit;
}

// ── カード削除 ──
if ($action === 'del_card') {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); echo json_encode(['error'=>'method']); exit; }
    $db = getDb();
    $s = $db->prepare('DELETE FROM cards WHERE id=?');
    $s->execute([(int)$body['id']]);
    echo json_encode(['ok'=>true]);
    exit;
}

// ── ステータス更新 ──
if ($action === 'update_status') {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); echo json_encode(['error'=>'method']); exit; }
    $db = getDb();
    $s = $db->prepare('UPDATE orders SET status=? WHERE id=?');
    $s->execute([$body['status'] ?? '未発注', (int)$body['id']]);
    echo json_encode(['ok'=>true]);
    exit;
}

http_response_code(400);
echo json_encode(['error'=>'unknown action']);
