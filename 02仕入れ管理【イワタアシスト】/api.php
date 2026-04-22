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

// ── DellaScore 仕入れ連携ヘルパー ──────────────────────────────
define('DS_DB', __DIR__ . '/../01営業管理システム【della score】/della_score.db');
define('IW_OWNER', '岩田');

function dsLoad($key) {
    try {
        $db = new PDO('sqlite:' . DS_DB);
        $s  = $db->prepare('SELECT value FROM store WHERE key=?');
        $s->execute([$key]);
        $r = $s->fetch();
        return $r ? (json_decode($r['value'], true) ?: []) : [];
    } catch (Exception $e) { return []; }
}

function dsSave($key, $data) {
    try {
        $db = new PDO('sqlite:' . DS_DB);
        $db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        $db->exec('CREATE TABLE IF NOT EXISTS store (key TEXT PRIMARY KEY, value TEXT NOT NULL)');
        $s = $db->prepare('INSERT OR REPLACE INTO store (key, value) VALUES (?, ?)');
        $s->execute([$key, json_encode(array_values($data), JSON_UNESCAPED_UNICODE)]);
    } catch (Exception $e) { /* DS未起動時は無視 */ }
}

// IWの発注1件 → DSの仕入れレコードに変換
function iwToDsPurchase($iw) {
    return [
        'id'          => 'iw_' . $iw['id'],
        'supplier'    => $iw['shop'] ?: '（購入先未記入）',
        'desc'        => $iw['name'] . ($iw['qty'] > 1 ? '×' . $iw['qty'] : ''),
        'amount'      => (int)$iw['price'] * (int)($iw['qty'] ?? 1),
        'tax'         => 0,
        'issued'      => $iw['date'],
        'due'         => '',
        'bank'        => '',
        'items'       => '',
        'status'      => 'unpaid',
        'owner'       => IW_OWNER,
        'iw_order_id' => (int)$iw['id'],
    ];
}

// DS仕入れに追加/更新
function dsSyncAdd($iwOrder) {
    $purchases = dsLoad('purchases');
    $dsId = 'iw_' . $iwOrder['id'];
    $new  = iwToDsPurchase($iwOrder);
    $found = false;
    foreach ($purchases as &$p) {
        if (($p['id'] ?? '') === $dsId) { $p = array_merge($p, $new); $found = true; break; }
    }
    unset($p);
    if (!$found) $purchases[] = $new;
    dsSave('purchases', $purchases);
}

// DS仕入れから削除
function dsSyncDel($iwId) {
    $purchases = dsLoad('purchases');
    $purchases = array_filter($purchases, fn($p) => ($p['id'] ?? '') !== 'iw_' . $iwId);
    dsSave('purchases', $purchases);
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
    $db->exec('CREATE TABLE IF NOT EXISTS card_statements (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        date    TEXT NOT NULL,
        shop    TEXT DEFAULT "",
        amount  INTEGER NOT NULL,
        card_id INTEGER DEFAULT NULL,
        memo    TEXT DEFAULT "",
        status  TEXT DEFAULT "pending"
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
    $newId = (int)$db->lastInsertId();
    // DellaScore仕入れに同期
    dsSyncAdd([
        'id'    => $newId,
        'date'  => $body['date']   ?? date('Y-m-d'),
        'name'  => $body['name']   ?? '',
        'shop'  => $body['shop']   ?? '',
        'price' => (int)($body['price'] ?? 0),
        'qty'   => (int)($body['qty']   ?? 1),
    ]);
    echo json_encode(['ok'=>true, 'id'=>$newId]);
    exit;
}

// ── 発注削除 ──
if ($action === 'del_order') {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); echo json_encode(['error'=>'method']); exit; }
    $db = getDb();
    $id = (int)$body['id'];
    $s = $db->prepare('DELETE FROM orders WHERE id=?');
    $s->execute([$id]);
    // DellaScore仕入れからも削除
    dsSyncDel($id);
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

// ── カード明細一覧 ──
if ($action === 'card_statements') {
    $db = getDb();
    $rows = $db->query("SELECT * FROM card_statements WHERE status='pending' ORDER BY date DESC, id DESC")->fetchAll(PDO::FETCH_ASSOC);
    $out = array_map(function($r) {
        return [
            'id'     => (int)$r['id'],
            'date'   => $r['date'],
            'shop'   => $r['shop'],
            'amount' => (int)$r['amount'],
            'cardId' => $r['card_id'] ? (int)$r['card_id'] : null,
            'memo'   => $r['memo'],
        ];
    }, $rows);
    echo json_encode($out);
    exit;
}

// ── カード明細一括追加（重複判定あり）──
if ($action === 'add_statements') {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); echo json_encode(['error'=>'method']); exit; }
    $db = getDb();
    $items  = $body['items'] ?? [];
    $cardId = $body['cardId'] ? (int)$body['cardId'] : null;

    // 既存発注の小計リストを取得
    $existingOrders = $db->query('SELECT price, qty FROM orders')->fetchAll(PDO::FETCH_ASSOC);
    $subtotals = array_map(fn($o) => (int)$o['price'] * (int)$o['qty'], $existingOrders);

    $pending = 0;
    $added   = 0;
    foreach ($items as $item) {
        $amount = (int)($item['amount'] ?? 0);
        $date   = $item['date'] ?? date('Y-m-d');
        $shop   = $item['shop'] ?? '';
        $memo   = $item['memo'] ?? '';
        if ($amount <= 0) continue;

        // 重複判定：税込み一致 or 税抜き一致
        $isDup = false;
        foreach ($subtotals as $sub) {
            $subTax = (int)round($sub * 1.1);
            if ($amount === $sub || $amount === $subTax) { $isDup = true; break; }
        }

        if ($isDup) {
            // 確認タブへ
            $s = $db->prepare('INSERT INTO card_statements (date,shop,amount,card_id,memo,status) VALUES (?,?,?,?,?,?)');
            $s->execute([$date, $shop, $amount, $cardId, $memo, 'pending']);
            $pending++;
        } else {
            // 即発注一覧へ
            $s = $db->prepare('INSERT INTO orders (date,name,shop,brand,url,qty,price,client,cc_id,status,memo)
                                VALUES (:date,:name,:shop,:brand,:url,:qty,:price,:client,:cc_id,:status,:memo)');
            $s->execute([
                ':date'   => $date,
                ':name'   => $shop ?: '（店名不明）',
                ':shop'   => $shop,
                ':brand'  => '',
                ':url'    => '',
                ':qty'    => 1,
                ':price'  => $amount,
                ':client' => '',
                ':cc_id'  => $cardId,
                ':status' => '発注済',
                ':memo'   => $memo,
            ]);
            $newId = (int)$db->lastInsertId();
            dsSyncAdd(['id'=>$newId,'date'=>$date,'name'=>$shop?:'（店名不明）','shop'=>$shop,'price'=>$amount,'qty'=>1]);
            $added++;
        }
    }
    echo json_encode(['ok'=>true, 'added'=>$added, 'pending'=>$pending]);
    exit;
}

// ── カード明細：「発注一覧にない」→ 発注一覧に追加して削除 ──
if ($action === 'approve_statement') {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); echo json_encode(['error'=>'method']); exit; }
    $db = getDb();
    $id = (int)$body['id'];
    $st = $db->prepare('SELECT * FROM card_statements WHERE id=?');
    $st->execute([$id]);
    $row = $st->fetch(PDO::FETCH_ASSOC);
    if (!$row) { echo json_encode(['error'=>'not found']); exit; }

    $s = $db->prepare('INSERT INTO orders (date,name,shop,brand,url,qty,price,client,cc_id,status,memo)
                        VALUES (:date,:name,:shop,:brand,:url,:qty,:price,:client,:cc_id,:status,:memo)');
    $s->execute([
        ':date'   => $row['date'],
        ':name'   => $row['shop'] ?: '（店名不明）',
        ':shop'   => $row['shop'],
        ':brand'  => '',
        ':url'    => '',
        ':qty'    => 1,
        ':price'  => (int)$row['amount'],
        ':client' => $body['client'] ?? '',
        ':cc_id'  => $row['card_id'] ?: null,
        ':status' => '発注済',
        ':memo'   => $row['memo'],
    ]);
    $newId = (int)$db->lastInsertId();
    dsSyncAdd(['id'=>$newId,'date'=>$row['date'],'name'=>$row['shop']?:'（店名不明）','shop'=>$row['shop'],'price'=>(int)$row['amount'],'qty'=>1]);

    $db->prepare('DELETE FROM card_statements WHERE id=?')->execute([$id]);
    echo json_encode(['ok'=>true, 'orderId'=>$newId]);
    exit;
}

// ── カード明細：「発注一覧にある」→ 削除のみ ──
if ($action === 'skip_statement') {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); echo json_encode(['error'=>'method']); exit; }
    $db = getDb();
    $db->prepare('DELETE FROM card_statements WHERE id=?')->execute([(int)$body['id']]);
    echo json_encode(['ok'=>true]);
    exit;
}

// ── カード明細：個別削除 ──
if ($action === 'delete_statement') {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); echo json_encode(['error'=>'method']); exit; }
    $db = getDb();
    $db->prepare('DELETE FROM card_statements WHERE id=?')->execute([(int)$body['id']]);
    echo json_encode(['ok'=>true]);
    exit;
}

// ── カード明細：一括削除 ──
if ($action === 'clear_statements') {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); echo json_encode(['error'=>'method']); exit; }
    $db = getDb();
    $db->exec("DELETE FROM card_statements WHERE status='pending'");
    echo json_encode(['ok'=>true]);
    exit;
}

http_response_code(400);
echo json_encode(['error'=>'unknown action']);
