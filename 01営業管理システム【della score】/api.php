<?php
session_start();

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');
header('Access-Control-Allow-Credentials: true');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { exit; }

// ── 認証情報 ──
define('VALID_EMAIL',   'info@dellaforce.com');
define('VALID_PW_DEFAULT', 'f09dc3f17f50e87d240af25bd2fc11199f4d28d9e2eb45e358ff22bb10dcf972'); // sha256('della1567')

function getDbSimple() {
    $db = new PDO('sqlite:' . __DIR__ . '/della_score.db');
    $db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $db->exec('CREATE TABLE IF NOT EXISTS store (key TEXT PRIMARY KEY, value TEXT NOT NULL)');
    return $db;
}
function getStoredPwHash() {
    try {
        $db = getDbSimple();
        $s = $db->prepare('SELECT value FROM store WHERE key=?');
        $s->execute(['ds_password_hash']);
        $r = $s->fetch(PDO::FETCH_ASSOC);
        return $r ? $r['value'] : VALID_PW_DEFAULT;
    } catch(Exception $e) { return VALID_PW_DEFAULT; }
}

$action = $_GET['action'] ?? '';

// ── ログイン ──
if ($action === 'login') {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
        http_response_code(405); echo json_encode(['error' => 'method not allowed']); exit;
    }
    $body = json_decode(file_get_contents('php://input'), true);
    $email = strtolower(trim($body['email'] ?? ''));
    $pw    = $body['password'] ?? '';
    if (
        hash_equals(VALID_EMAIL, $email) &&
        hash_equals(getStoredPwHash(), hash('sha256', $pw))
    ) {
        $_SESSION['auth'] = true;
        echo json_encode(['ok' => true]);
    } else {
        http_response_code(401);
        echo json_encode(['error' => '認証失敗']);
    }
    exit;
}

// ── パスワード変更 ──
if ($action === 'change_password') {
    if (empty($_SESSION['auth'])) { http_response_code(401); echo json_encode(['error' => '未認証']); exit; }
    $body = json_decode(file_get_contents('php://input'), true);
    if (!hash_equals(getStoredPwHash(), hash('sha256', $body['current'] ?? ''))) {
        http_response_code(401); echo json_encode(['error' => '現在のパスワードが違います']); exit;
    }
    $newPw = $body['new'] ?? '';
    if (strlen($newPw) < 4) {
        http_response_code(400); echo json_encode(['error' => 'パスワードは4文字以上で設定してください']); exit;
    }
    $db = getDbSimple();
    $s = $db->prepare('INSERT OR REPLACE INTO store (key,value) VALUES (?,?)');
    $s->execute(['ds_password_hash', hash('sha256', $newPw)]);
    echo json_encode(['ok' => true]);
    exit;
}

// ── ログアウト ──
if ($action === 'logout') {
    session_destroy();
    echo json_encode(['ok' => true]);
    exit;
}

// ── セッション確認 ──
if ($action === 'check') {
    echo json_encode(['auth' => !empty($_SESSION['auth'])]);
    exit;
}

// ── セッションチェック（login/logout 以外は認証必須） ──
if (empty($_SESSION['auth'])) {
    http_response_code(401);
    echo json_encode(['error' => '未認証']);
    exit;
}

// ── DB接続 ──
$db = new PDO('sqlite:' . __DIR__ . '/della_score.db');
$db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
$db->exec('CREATE TABLE IF NOT EXISTS store (key TEXT PRIMARY KEY, value TEXT NOT NULL)');

$keys = ['prospects','invoices','purchases','orders','recurringInv','recurringPur','clients','mf_invoices','mf_quotes','mf_deleted_warnings'];

if ($_SERVER['REQUEST_METHOD'] === 'GET') {
    $stmt = $db->prepare('SELECT key, value FROM store WHERE key = ?');
    $result = [];
    $hasAny = false;
    foreach ($keys as $k) {
        $stmt->execute([$k]);
        $row = $stmt->fetch(PDO::FETCH_ASSOC);
        if ($row) {
            $result[$k] = json_decode($row['value'], true);
            $hasAny = true;
        }
    }
    echo $hasAny ? json_encode($result) : '{}';

} elseif ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $body = json_decode(file_get_contents('php://input'), true);
    if (!$body) { http_response_code(400); echo json_encode(['error' => 'invalid json']); exit; }

    // ── イワタアシスト連携：デラスコアで iw_* 仕入れが削除された場合にIW側も削除 ──
    if (isset($body['purchases'])) {
        try {
            $s = $db->prepare('SELECT value FROM store WHERE key=?');
            $s->execute(['purchases']);
            $row = $s->fetch(PDO::FETCH_ASSOC);
            $oldPurchases = $row ? (json_decode($row['value'], true) ?: []) : [];

            // 旧データのiw_*IDセット
            $oldIwIds = [];
            foreach ($oldPurchases as $p) {
                $pid = $p['id'] ?? '';
                if (substr($pid, 0, 3) === 'iw_') {
                    $oldIwIds[] = $pid;
                }
            }
            // 新データのiw_*IDセット
            $newIwIds = [];
            foreach ($body['purchases'] as $p) {
                $pid = $p['id'] ?? '';
                if (substr($pid, 0, 3) === 'iw_') {
                    $newIwIds[] = $pid;
                }
            }
            // 削除されたiw_*をIWのDBからも削除
            $deletedIwIds = array_diff($oldIwIds, $newIwIds);
            if (!empty($deletedIwIds)) {
                $iwDbPath = __DIR__ . '/../02仕入れ管理【イワタアシスト】/iwata_assist.db';
                if (file_exists($iwDbPath)) {
                    $iwDb = new PDO('sqlite:' . $iwDbPath);
                    $iwDb->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
                    $del = $iwDb->prepare('DELETE FROM orders WHERE id=?');
                    foreach ($deletedIwIds as $iwDsId) {
                        $iwOrderId = (int)substr($iwDsId, 3);
                        $del->execute([$iwOrderId]);
                    }
                }
            }
        } catch (Exception $e) { /* IW未起動・DB不在時は無視 */ }
    }

    $stmt = $db->prepare('INSERT OR REPLACE INTO store (key, value) VALUES (?, ?)');
    foreach ($keys as $k) {
        if (isset($body[$k])) {
            $stmt->execute([$k, json_encode($body[$k], JSON_UNESCAPED_UNICODE)]);
        }
    }
    echo json_encode(['ok' => true]);

} else {
    http_response_code(405);
    echo json_encode(['error' => 'method not allowed']);
}
