<?php
session_start();
header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') exit;

define('PM_PW_DEFAULT', hash('sha256', 'iwata2024')); // デフォルトパスワード

$action = $_GET['action'] ?? '';

// DB接続（認証前に必要なため先に定義）
function getDb() {
    $db = new PDO('sqlite:' . __DIR__ . '/della_score.db');
    $db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $db->exec('CREATE TABLE IF NOT EXISTS store (key TEXT PRIMARY KEY, value TEXT NOT NULL)');
    return $db;
}
function getStoredPwHash() {
    try {
        $db = getDb();
        $s = $db->prepare('SELECT value FROM store WHERE key=?');
        $s->execute(['pm_password_hash']);
        $r = $s->fetch(PDO::FETCH_ASSOC);
        return $r ? $r['value'] : PM_PW_DEFAULT;
    } catch(Exception $e) { return PM_PW_DEFAULT; }
}

if ($action === 'login') {
    $body = json_decode(file_get_contents('php://input'), true);
    if (hash_equals(getStoredPwHash(), hash('sha256', $body['password'] ?? ''))) {
        $_SESSION['pm_auth'] = true;
        echo json_encode(['ok' => true]);
    } else {
        http_response_code(401);
        echo json_encode(['error' => 'パスワードが違います']);
    }
    exit;
}

if ($action === 'change_password') {
    $body = json_decode(file_get_contents('php://input'), true);
    if (!hash_equals(getStoredPwHash(), hash('sha256', $body['current'] ?? ''))) {
        http_response_code(401);
        echo json_encode(['error' => '現在のパスワードが違います']);
        exit;
    }
    $newPw = $body['new'] ?? '';
    if (strlen($newPw) < 4) {
        http_response_code(400);
        echo json_encode(['error' => 'パスワードは4文字以上で設定してください']);
        exit;
    }
    $db = getDb();
    $s = $db->prepare('INSERT OR REPLACE INTO store (key,value) VALUES (?,?)');
    $s->execute(['pm_password_hash', hash('sha256', $newPw)]);
    echo json_encode(['ok' => true]);
    exit;
}
if ($action === 'check') { echo json_encode(['auth' => !empty($_SESSION['pm_auth'])]); exit; }
if ($action === 'logout') { session_destroy(); echo json_encode(['ok' => true]); exit; }

if (empty($_SESSION['pm_auth'])) {
    http_response_code(401); echo json_encode(['error' => '未認証']); exit;
}

$db = getDb();

function dbGet($db, $key) {
    $s = $db->prepare('SELECT value FROM store WHERE key=?');
    $s->execute([$key]);
    $r = $s->fetch(PDO::FETCH_ASSOC);
    return $r ? json_decode($r['value'], true) : null;
}
function dbSet($db, $key, $val) {
    $s = $db->prepare('INSERT OR REPLACE INTO store (key,value) VALUES (?,?)');
    $s->execute([$key, json_encode($val, JSON_UNESCAPED_UNICODE)]);
}

if ($_SERVER['REQUEST_METHOD'] === 'GET') {
    $taxRaw = dbGet($db, 'pm_tax_rate');
    echo json_encode([
        'pm_orders'    => dbGet($db,'pm_orders') ?? [],
        'pm_cards'     => dbGet($db,'pm_cards')  ?? [],
        'pm_tax_rate'  => $taxRaw !== null ? (float)$taxRaw : 10,
    ]);

} elseif ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $body = json_decode(file_get_contents('php://input'), true);
    if (!$body) { http_response_code(400); echo json_encode(['error'=>'invalid json']); exit; }

    if (isset($body['pm_orders']))   dbSet($db, 'pm_orders',   $body['pm_orders']);
    if (isset($body['pm_cards']))    dbSet($db, 'pm_cards',    $body['pm_cards']);
    if (isset($body['pm_tax_rate'])) dbSet($db, 'pm_tax_rate', (float)$body['pm_tax_rate']);

    // Della Scoreの仕入れ請求書に同期（未連携のみ追加）
    if (!empty($body['sync_orders'])) {
        $purchases = dbGet($db, 'purchases') ?? [];
        // 既存のpm_idを収集（重複チェック用）
        $existingPmIds = [];
        foreach ($purchases as $p) {
            if (!empty($p['pm_id'])) $existingPmIds[] = $p['pm_id'];
        }
        foreach ($body['sync_orders'] as $o) {
            // 既に連携済みはスキップ
            if (in_array($o['id'], $existingPmIds)) continue;
            $qty    = (int)($o['qty'] ?? 1);
            $priceEx = (float)($o['price_ex'] ?? 0);
            $priceIn = (float)($o['price_in'] ?? $o['price'] ?? 0);
            // price_exがなければprice_inをそのまま税抜として扱う
            if ($priceEx <= 0) $priceEx = $priceIn;
            $taxAmt = max(0, $priceIn - $priceEx);
            $purchases[] = [
                'id'       => 'pm_' . $o['id'],
                'pm_id'    => $o['id'],
                'supplier' => $o['shop'] ?: ($o['name'] ?? ''),
                'desc'     => $o['name'] ?? '',
                'amount'   => $qty * $priceEx,   // 税抜合計
                'tax'      => $qty * $taxAmt,     // 消費税合計
                'issued'   => $o['date'] ?? '',
                'due'      => $o['due'] ?? '',
                'bank'     => '',
                'owner'    => '岩田',
                'status'   => ($o['status'] ?? '') === '納品済' ? 'paid' : 'unpaid',
                'memo'     => $o['memo'] ?? '',
            ];
        }
        dbSet($db, 'purchases', $purchases);
    }

    echo json_encode(['ok' => true]);
}
