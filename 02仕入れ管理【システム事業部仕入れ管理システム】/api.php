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
    $amount = (int)$iw['price'] * (int)($iw['qty'] ?? 1); // 税抜き金額
    $tax    = (int)round($amount * 0.1);                   // 消費税額
    return [
        'id'          => 'iw_' . $iw['id'],
        'supplier'    => $iw['shop'] ?: '（購入先未記入）',
        'desc'        => $iw['name'] . ($iw['qty'] > 1 ? '×' . $iw['qty'] : ''),
        'amount'      => $amount,
        'tax'         => $tax,
        'issued'      => $iw['date'],
        'due'         => '',
        'bank'        => '',
        'items'       => '',
        'status'      => 'unpaid',
        'owner'       => $iw['owner'] ?? IW_OWNER,
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
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        date          TEXT NOT NULL,
        name          TEXT NOT NULL,
        shop          TEXT DEFAULT "",
        brand         TEXT DEFAULT "",
        url           TEXT DEFAULT "",
        qty           INTEGER DEFAULT 1,
        price         INTEGER DEFAULT 0,
        sell_price    INTEGER DEFAULT 0,
        delivery_date TEXT DEFAULT "",
        client        TEXT DEFAULT "",
        cc_id         INTEGER DEFAULT NULL,
        status        TEXT DEFAULT "未発注",
        memo          TEXT DEFAULT "",
        category      TEXT DEFAULT "物品",
        owner         TEXT DEFAULT "岩田"
    )');
    // カラム追加（既存DBへの対応）
    try { $db->exec('ALTER TABLE orders ADD COLUMN sell_price INTEGER DEFAULT 0'); } catch(Exception $e) {}
    try { $db->exec('ALTER TABLE orders ADD COLUMN delivery_date TEXT DEFAULT ""'); } catch(Exception $e) {}
    try { $db->exec('ALTER TABLE orders ADD COLUMN category TEXT DEFAULT "物品"'); } catch(Exception $e) {}
    try { $db->exec('ALTER TABLE orders ADD COLUMN owner TEXT DEFAULT "岩田"'); } catch(Exception $e) {}
    $db->exec('CREATE TABLE IF NOT EXISTS clients (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        name    TEXT NOT NULL UNIQUE,
        created TEXT DEFAULT ""
    )');
    $db->exec('CREATE TABLE IF NOT EXISTS suppliers (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        name    TEXT NOT NULL UNIQUE,
        url     TEXT DEFAULT "",
        memo    TEXT DEFAULT "",
        created TEXT DEFAULT ""
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

// ── 納品先一覧 ──
if ($action === 'clients') {
    $db = getDb();
    $rows = $db->query('SELECT * FROM clients ORDER BY name')->fetchAll(PDO::FETCH_ASSOC);
    echo json_encode(array_map(fn($r) => ['id'=>(int)$r['id'],'name'=>$r['name']], $rows));
    exit;
}

// ── 納品先追加 ──
if ($action === 'add_client') {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); echo json_encode(['error'=>'method']); exit; }
    $db = getDb();
    $name = trim($body['name'] ?? '');
    if (!$name) { echo json_encode(['error'=>'名前を入力してください']); exit; }
    try {
        $s = $db->prepare('INSERT INTO clients (name, created) VALUES (?, ?)');
        $s->execute([$name, date('Y-m-d')]);
        echo json_encode(['ok'=>true, 'id'=>(int)$db->lastInsertId(), 'name'=>$name]);
    } catch (Exception $e) {
        // UNIQUE制約違反（重複）
        $row = $db->prepare('SELECT id FROM clients WHERE name=?');
        $row->execute([$name]);
        $r = $row->fetch(PDO::FETCH_ASSOC);
        echo json_encode(['ok'=>true, 'id'=>(int)($r['id']??0), 'name'=>$name]);
    }
    exit;
}

// ── 納品先削除 ──
if ($action === 'del_client') {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); echo json_encode(['error'=>'method']); exit; }
    $db = getDb();
    $s = $db->prepare('DELETE FROM clients WHERE id=?');
    $s->execute([(int)$body['id']]);
    echo json_encode(['ok'=>true]);
    exit;
}

// ── 仕入れ先一覧 ──
if ($action === 'suppliers') {
    $db = getDb();
    $rows = $db->query('SELECT * FROM suppliers ORDER BY name')->fetchAll(PDO::FETCH_ASSOC);
    echo json_encode(array_map(fn($r) => ['id'=>(int)$r['id'],'name'=>$r['name'],'url'=>$r['url'],'memo'=>$r['memo']], $rows));
    exit;
}

// ── 仕入れ先追加 ──
if ($action === 'add_supplier') {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); echo json_encode(['error'=>'method']); exit; }
    $db = getDb();
    $name = trim($body['name'] ?? '');
    if (!$name) { echo json_encode(['error'=>'名前を入力してください']); exit; }
    try {
        $s = $db->prepare('INSERT INTO suppliers (name, url, memo, created) VALUES (?, ?, ?, ?)');
        $s->execute([$name, trim($body['url'] ?? ''), trim($body['memo'] ?? ''), date('Y-m-d')]);
        echo json_encode(['ok'=>true, 'id'=>(int)$db->lastInsertId(), 'name'=>$name]);
    } catch (Exception $e) {
        $row = $db->prepare('SELECT id FROM suppliers WHERE name=?');
        $row->execute([$name]);
        $r = $row->fetch(PDO::FETCH_ASSOC);
        echo json_encode(['ok'=>true, 'id'=>(int)($r['id']??0), 'name'=>$name]);
    }
    exit;
}

// ── 仕入れ先削除 ──
if ($action === 'del_supplier') {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); echo json_encode(['error'=>'method']); exit; }
    $db = getDb();
    $db->prepare('DELETE FROM suppliers WHERE id=?')->execute([(int)$body['id']]);
    echo json_encode(['ok'=>true]);
    exit;
}

// ── 発注一覧 ──
if ($action === 'orders') {
    $db = getDb();
    $rows = $db->query('SELECT * FROM orders ORDER BY date DESC, id DESC')->fetchAll(PDO::FETCH_ASSOC);
    $out = array_map(function($r) {
        return [
            'id'           => (int)$r['id'],
            'date'         => $r['date'],
            'name'         => $r['name'],
            'shop'         => $r['shop'],
            'brand'        => $r['brand'],
            'url'          => $r['url'],
            'qty'          => (int)$r['qty'],
            'price'        => (int)$r['price'],
            'sellPrice'    => (int)($r['sell_price'] ?? 0),
            'deliveryDate' => $r['delivery_date'] ?? '',
            'client'       => $r['client'],
            'ccId'         => $r['cc_id'] ? (int)$r['cc_id'] : null,
            'status'       => $r['status'],
            'memo'         => $r['memo'],
            'category'     => $r['category'] ?? '物品',
            'owner'        => $r['owner'] ?? '岩田',
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
    $clientName = trim($body['client'] ?? '');
    // 新しい納品先なら自動登録
    if ($clientName) {
        try { $db->prepare('INSERT OR IGNORE INTO clients (name,created) VALUES (?,?)')->execute([$clientName, date('Y-m-d')]); } catch(Exception $e) {}
    }
    $s = $db->prepare('INSERT INTO orders (date,name,shop,brand,url,qty,price,sell_price,delivery_date,client,cc_id,status,memo,category,owner)
                        VALUES (:date,:name,:shop,:brand,:url,:qty,:price,:sell_price,:delivery_date,:client,:cc_id,:status,:memo,:category,:owner)');
    $owner = in_array($body['owner'] ?? '', ['岩田','谷藤']) ? $body['owner'] : '岩田';
    $s->execute([
        ':date'          => $body['date']         ?? date('Y-m-d'),
        ':name'          => $body['name']          ?? '',
        ':shop'          => $body['shop']          ?? '',
        ':brand'         => $body['brand']         ?? '',
        ':url'           => $body['url']           ?? '',
        ':qty'           => (int)($body['qty']     ?? 1),
        ':price'         => (int)($body['price']   ?? 0),
        ':sell_price'    => (int)($body['sellPrice'] ?? 0),
        ':delivery_date' => $body['deliveryDate']  ?? '',
        ':client'        => $clientName,
        ':cc_id'         => $body['ccId'] ? (int)$body['ccId'] : null,
        ':status'        => $body['status']        ?? '未発注',
        ':memo'          => $body['memo']          ?? '',
        ':category'      => $body['category']      ?? '物品',
        ':owner'         => $owner,
    ]);
    $newId = (int)$db->lastInsertId();
    dsSyncAdd([
        'id'    => $newId,
        'date'  => $body['date']   ?? date('Y-m-d'),
        'name'  => $body['name']   ?? '',
        'shop'  => $body['shop']   ?? '',
        'price' => (int)($body['price'] ?? 0),
        'qty'   => (int)($body['qty']   ?? 1),
        'owner' => $owner,
    ]);
    echo json_encode(['ok'=>true, 'id'=>$newId]);
    exit;
}

// ── CSV一括インポート ──
if ($action === 'import_csv') {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); echo json_encode(['error'=>'method']); exit; }
    $db = getDb();
    $rows = $body['rows'] ?? [];
    $imported = 0;
    $errors = [];
    foreach ($rows as $i => $r) {
        $date      = trim($r['date']      ?? date('Y-m-d'));
        $shop      = trim($r['shop']      ?? '');
        $name      = trim($r['name']      ?? $shop);
        $price     = (int)($r['price']    ?? 0);
        $qty       = max(1, (int)($r['qty'] ?? 1));
        $client    = trim($r['client']    ?? '');
        $sellPrice = (int)($r['sellPrice'] ?? 0);
        $category  = trim($r['category']  ?? '物品');
        $owner     = trim($r['owner']     ?? '岩田');
        if (!in_array($category, ['物品','サーバー','外注費','その他'])) $category = '物品';
        if (!in_array($owner, ['岩田','谷藤'])) $owner = '岩田';
        if (!$name || $price <= 0) { $errors[] = ($i+1).'行目: 商品名または単価が不正'; continue; }
        if ($client) {
            try { $db->prepare('INSERT OR IGNORE INTO clients (name,created) VALUES (?,?)')->execute([$client, date('Y-m-d')]); } catch(Exception $e) {}
        }
        $s = $db->prepare('INSERT INTO orders (date,name,shop,brand,url,qty,price,sell_price,delivery_date,client,cc_id,status,memo,category,owner)
                            VALUES (:date,:name,:shop,:brand,:url,:qty,:price,:sell_price,:delivery_date,:client,:cc_id,:status,:memo,:category,:owner)');
        $s->execute([
            ':date'          => $date,
            ':name'          => $name,
            ':shop'          => $shop,
            ':brand'         => '',
            ':url'           => '',
            ':qty'           => $qty,
            ':price'         => $price,
            ':sell_price'    => $sellPrice,
            ':delivery_date' => '',
            ':client'        => $client,
            ':cc_id'         => null,
            ':status'        => '発注済',
            ':memo'          => '',
            ':category'      => $category,
            ':owner'         => $owner,
        ]);
        $newId = (int)$db->lastInsertId();
        dsSyncAdd(['id'=>$newId,'date'=>$date,'name'=>$name,'shop'=>$shop,'price'=>$price,'qty'=>$qty,'owner'=>$owner]);
        $imported++;
    }
    echo json_encode(['ok'=>true, 'imported'=>$imported, 'errors'=>$errors]);
    exit;
}

// ── 全発注を DellaScore へ再同期 ──
if ($action === 'resync_all') {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); echo json_encode(['error'=>'method']); exit; }
    $db = getDb();
    $rows = $db->query('SELECT * FROM orders')->fetchAll(PDO::FETCH_ASSOC);
    foreach ($rows as $r) {
        dsSyncAdd([
            'id'    => $r['id'],
            'date'  => $r['date'],
            'name'  => $r['name'],
            'shop'  => $r['shop'],
            'price' => (int)$r['price'],
            'qty'   => (int)$r['qty'],
        ]);
    }
    echo json_encode(['ok'=>true, 'count'=>count($rows)]);
    exit;
}

// ── 発注複製 ──
if ($action === 'duplicate_order') {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); echo json_encode(['error'=>'method']); exit; }
    $db = getDb();
    $id = (int)$body['id'];
    $st = $db->prepare('SELECT * FROM orders WHERE id=?');
    $st->execute([$id]);
    $orig = $st->fetch(PDO::FETCH_ASSOC);
    if (!$orig) { echo json_encode(['error'=>'not found']); exit; }
    $s = $db->prepare('INSERT INTO orders (date,name,shop,brand,url,qty,price,sell_price,delivery_date,client,cc_id,status,memo,category,owner)
                        VALUES (:date,:name,:shop,:brand,:url,:qty,:price,:sell_price,:delivery_date,:client,:cc_id,:status,:memo,:category,:owner)');
    $s->execute([
        ':date'          => date('Y-m-d'),
        ':name'          => $orig['name'],
        ':shop'          => $orig['shop'],
        ':brand'         => $orig['brand'],
        ':url'           => $orig['url'],
        ':qty'           => (int)$orig['qty'],
        ':price'         => (int)$orig['price'],
        ':sell_price'    => (int)($orig['sell_price'] ?? 0),
        ':delivery_date' => $orig['delivery_date'] ?? '',
        ':client'        => $orig['client'],
        ':cc_id'         => $orig['cc_id'] ?: null,
        ':status'        => '未発注',
        ':memo'          => $orig['memo'],
        ':category'      => $orig['category'] ?? '物品',
        ':owner'         => $orig['owner'] ?? '岩田',
    ]);
    $newId = (int)$db->lastInsertId();
    dsSyncAdd([
        'id'    => $newId,
        'date'  => date('Y-m-d'),
        'name'  => $orig['name'],
        'shop'  => $orig['shop'],
        'price' => (int)$orig['price'],
        'qty'   => (int)$orig['qty'],
        'owner' => $orig['owner'] ?? '岩田',
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

// ── 発注更新 ──
if ($action === 'update_order') {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); echo json_encode(['error'=>'method']); exit; }
    $db = getDb();
    $id = (int)$body['id'];
    $clientName = trim($body['client'] ?? '');
    if ($clientName) {
        try { $db->prepare('INSERT OR IGNORE INTO clients (name,created) VALUES (?,?)')->execute([$clientName, date('Y-m-d')]); } catch(Exception $e) {}
    }
    $owner = in_array($body['owner'] ?? '', ['岩田','谷藤']) ? $body['owner'] : '岩田';
    $s = $db->prepare('UPDATE orders SET date=:date,name=:name,shop=:shop,brand=:brand,url=:url,qty=:qty,price=:price,sell_price=:sell_price,delivery_date=:delivery_date,client=:client,cc_id=:cc_id,status=:status,memo=:memo,category=:category,owner=:owner WHERE id=:id');
    $s->execute([
        ':date'          => $body['date']          ?? date('Y-m-d'),
        ':name'          => $body['name']          ?? '',
        ':shop'          => $body['shop']          ?? '',
        ':brand'         => $body['brand']         ?? '',
        ':url'           => $body['url']           ?? '',
        ':qty'           => (int)($body['qty']     ?? 1),
        ':price'         => (int)($body['price']   ?? 0),
        ':sell_price'    => (int)($body['sellPrice'] ?? 0),
        ':delivery_date' => $body['deliveryDate']  ?? '',
        ':client'        => $clientName,
        ':cc_id'         => $body['ccId'] ? (int)$body['ccId'] : null,
        ':status'        => $body['status']        ?? '未発注',
        ':memo'          => $body['memo']          ?? '',
        ':category'      => $body['category']      ?? '物品',
        ':owner'         => $owner,
        ':id'            => $id,
    ]);
    dsSyncAdd([
        'id'    => $id,
        'date'  => $body['date']   ?? date('Y-m-d'),
        'name'  => $body['name']   ?? '',
        'shop'  => $body['shop']   ?? '',
        'price' => (int)($body['price'] ?? 0),
        'qty'   => (int)($body['qty']   ?? 1),
        'owner' => $owner,
    ]);
    echo json_encode(['ok' => true]);
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

// ── パスワード変更 ──
if ($action === 'change_password') {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); echo json_encode(['error'=>'method']); exit; }
    $current = $body['current'] ?? '';
    $newpass  = $body['new']     ?? '';
    if (!$current || !$newpass) { echo json_encode(['error'=>'入力が不正です']); exit; }
    if (mb_strlen($newpass) < 4) { echo json_encode(['error'=>'新しいパスワードは4文字以上にしてください']); exit; }
    $db   = getDb();
    $user = $_SESSION['user'];
    $row  = $db->prepare('SELECT password FROM users WHERE username=?');
    $row->execute([$user]);
    $row  = $row->fetch(PDO::FETCH_ASSOC);
    if (!$row || !password_verify($current, $row['password'])) {
        echo json_encode(['error'=>'現在のパスワードが違います']); exit;
    }
    $hash = password_hash($newpass, PASSWORD_DEFAULT);
    $st   = $db->prepare('UPDATE users SET password=? WHERE username=?');
    $st->execute([$hash, $user]);
    echo json_encode(['ok'=>true]);
    exit;
}

http_response_code(400);
echo json_encode(['error'=>'unknown action']);
