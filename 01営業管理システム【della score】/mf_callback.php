<?php
session_start();
set_time_limit(300);

define('MF_CLIENT_ID',     '236289199630974');
define('MF_CLIENT_SECRET', 'zocDfXdqbj-iVtFADIxhLUHSepDCKVqzdP0Z_FdKTa7yAcs03StPylEyIxyxm17_N8fKSenIN8w3JlEQMRrOhw');
define('MF_REDIRECT_URI',  'http://localhost:8080/mf_callback.php');
define('MF_TOKEN_URL',     'https://api.biz.moneyforward.com/token');
define('MF_API_BASE',      'https://invoice.moneyforward.com/api/v3');

$DATE_FROM = $_SESSION['mf_date_from'] ?? '2026-01-01';
$DATE_TO   = $_SESSION['mf_date_to']   ?? date('Y-m-d');

// stateチェック
if (empty($_GET['state']) || $_GET['state'] !== ($_SESSION['mf_state'] ?? '')) {
    die('不正なリクエストです (state mismatch)');
}
if (empty($_GET['code'])) {
    die('認証コードがありません: ' . htmlspecialchars($_GET['error'] ?? 'unknown'));
}

// アクセストークン取得
$tokenRes = mf_post(MF_TOKEN_URL, [
    'grant_type'   => 'authorization_code',
    'code'         => $_GET['code'],
    'redirect_uri' => MF_REDIRECT_URI,
], true);

if (empty($tokenRes['access_token'])) {
    die('トークン取得失敗: ' . json_encode($tokenRes, JSON_UNESCAPED_UNICODE));
}

$token = $tokenRes['access_token'];
$DEBUG = !empty($_SESSION['mf_debug']);

// ── デバッグ ──
if ($DEBUG) {
    echo "<pre style='font-size:12px'>";
    echo "DATE_FROM: $DATE_FROM / DATE_TO: $DATE_TO\n\n";
    $r = mf_get(MF_API_BASE . '/billings?per_page=3&page=1', $token);
    echo "=== 請求書1ページ目 ===\n" . json_encode($r, JSON_UNESCAPED_UNICODE|JSON_PRETTY_PRINT) . "\n\n";
    $r2 = mf_get(MF_API_BASE . '/quotes?per_page=3&page=1', $token);
    echo "=== 見積書1ページ目 ===\n" . json_encode($r2, JSON_UNESCAPED_UNICODE|JSON_PRETTY_PRINT) . "\n";
    echo "</pre>";
    $_SESSION['mf_debug'] = false;
    exit;
}

// ── DB接続 ──
$db = new PDO('sqlite:' . __DIR__ . '/della_score.db');
$db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
$db->exec('CREATE TABLE IF NOT EXISTS store (key TEXT PRIMARY KEY, value TEXT NOT NULL)');

// 既存データをフル読み込み
function loadFull($db, $key) {
    $s = $db->prepare('SELECT value FROM store WHERE key=?');
    $s->execute([$key]);
    $r = $s->fetch(PDO::FETCH_ASSOC);
    return $r ? (json_decode($r['value'], true) ?: []) : [];
}

$existingInvoices = loadFull($db, 'mf_invoices');
$existingQuotes   = loadFull($db, 'mf_quotes');

// 既存データをキー別マップに変換（id / billing_number / quote_number）
function buildMaps($arr, $numKey) {
    $byId = []; $byNum = [];
    foreach ($arr as $item) {
        if (!empty($item['id']))     $byId[$item['id']]   = $item;
        if (!empty($item[$numKey]))  $byNum[$item[$numKey]] = $item;
    }
    return [$byId, $byNum];
}

[$existingInvById, $existingInvByNum] = buildMaps($existingInvoices, 'billing_number');
[$existingQuoById, $existingQuoByNum] = buildMaps($existingQuotes,   'quote_number');

// ── 請求書取得・マージ ──
$newInvIds  = [];  // 今回の同期で取得したid
$newInvNums = [];  // 今回の同期で取得したbilling_number
$mergedInvoices = $existingInvoices; // まず既存を全部入れる
$page = 1;
$addedInv = 0; $updatedInv = 0;

while (true) {
    $params = http_build_query(['page' => $page, 'per_page' => 100]);
    $res = mf_get(MF_API_BASE . '/billings?' . $params, $token);
    if (empty($res['data'])) break;
    foreach ($res['data'] as $b) {
        $created = substr($b['created_at'] ?? '', 0, 10);
        if ($created === '') continue;
        if ($created < $DATE_FROM || $created > $DATE_TO) continue;

        $id     = $b['id'] ?? '';
        $bilNum = $b['billing_number'] ?? '';
        $item   = [
            'id'             => $id,
            'billing_number' => $bilNum,
            'title'          => $b['title'] ?? '',
            'billing_date'   => str_replace('/', '-', $b['billing_date'] ?? ''),
            'due_date'       => str_replace('/', '-', $b['due_date'] ?? ''),
            'total_price'    => (float)($b['subtotal_price'] ?? $b['total_price'] ?? 0),
            'tax'            => (float)($b['tax_price'] ?? 0),
            'status'         => $b['payment_status'] ?? '',
            'partner'        => $b['partner_name'] ?? '',
            'created_at'     => $created,
        ];

        if ($id) $newInvIds[$id] = true;
        if ($bilNum) $newInvNums[$bilNum] = true;

        // 既存に同じidがある → 更新
        if ($id && isset($existingInvById[$id])) {
            foreach ($mergedInvoices as &$m) {
                if ($m['id'] === $id) { $m = array_merge($m, $item); $updatedInv++; break; }
            }
            unset($m);
        }
        // 既存に同じbilling_numberがある（idは別） → 更新
        elseif ($bilNum && isset($existingInvByNum[$bilNum])) {
            foreach ($mergedInvoices as &$m) {
                if (($m['billing_number'] ?? '') === $bilNum) { $m = array_merge($m, $item); $updatedInv++; break; }
            }
            unset($m);
        }
        // 新規
        else {
            $mergedInvoices[] = $item;
            $addedInv++;
        }
    }
    $paging = $res['pagination'] ?? $res['meta'] ?? [];
    if (empty($paging) || ($paging['current_page'] ?? 1) >= ($paging['total_pages'] ?? 1)) break;
    $page++;
}
$invPageCount = $page;

// ── 見積書取得・マージ ──
$newQuoIds  = [];
$newQuoNums = [];
$mergedQuotes = $existingQuotes;
$page = 1;
$addedQuo = 0; $updatedQuo = 0;

while (true) {
    $params = http_build_query(['page' => $page, 'per_page' => 100]);
    $res = mf_get(MF_API_BASE . '/quotes?' . $params, $token);
    if (empty($res['data'])) break;
    foreach ($res['data'] as $q) {
        $created = substr($q['created_at'] ?? '', 0, 10);
        if ($created === '') continue;
        if ($created < $DATE_FROM || $created > $DATE_TO) continue;

        $id     = $q['id'] ?? '';
        $quoNum = $q['quote_number'] ?? '';
        $item   = [
            'id'           => $id,
            'quote_number' => $quoNum,
            'title'        => $q['title'] ?? '',
            'quote_date'   => str_replace('/', '-', $q['quote_date'] ?? ''),
            'expired_date' => str_replace('/', '-', $q['expired_date'] ?? ''),
            'total_price'  => (float)($q['subtotal_price'] ?? $q['total_price'] ?? 0),
            'status'       => $q['order_status'] ?? $q['status'] ?? '',
            'partner'      => $q['partner_name'] ?? '',
            'created_at'   => $created,
        ];

        if ($id) $newQuoIds[$id] = true;
        if ($quoNum) $newQuoNums[$quoNum] = true;

        if ($id && isset($existingQuoById[$id])) {
            foreach ($mergedQuotes as &$m) {
                if ($m['id'] === $id) { $m = array_merge($m, $item); $updatedQuo++; break; }
            }
            unset($m);
        } elseif ($quoNum && isset($existingQuoByNum[$quoNum])) {
            foreach ($mergedQuotes as &$m) {
                if (($m['quote_number'] ?? '') === $quoNum) { $m = array_merge($m, $item); $updatedQuo++; break; }
            }
            unset($m);
        } else {
            $mergedQuotes[] = $item;
            $addedQuo++;
        }
    }
    $paging = $res['pagination'] ?? $res['meta'] ?? [];
    if (empty($paging) || ($paging['current_page'] ?? 1) >= ($paging['total_pages'] ?? 1)) break;
    $page++;
}
$quoPageCount = $page;

// ── DBに保存（マージ結果） ──
$stmt = $db->prepare('INSERT OR REPLACE INTO store (key, value) VALUES (?, ?)');
$stmt->execute(['mf_invoices', json_encode(array_values($mergedInvoices), JSON_UNESCAPED_UNICODE)]);
$stmt->execute(['mf_quotes',   json_encode(array_values($mergedQuotes),   JSON_UNESCAPED_UNICODE)]);

// ── 完了画面 ──
echo "<!DOCTYPE html><html lang='ja'><head><meta charset='UTF-8'><title>MF連携完了</title>
<style>body{font-family:sans-serif;padding:40px;background:#F4F6FB;color:#1B2340}
.box{background:#fff;border-radius:10px;padding:30px;max-width:480px;margin:0 auto;box-shadow:0 2px 12px rgba(0,0,0,.08)}
h2{margin-bottom:16px}p{margin:6px 0;color:#4A5578}.new{color:#1A6644;font-weight:700}.upd{color:#1A4A8A;font-weight:700}
a{display:inline-block;margin-top:20px;padding:9px 20px;background:#1B2B4B;color:#fff;border-radius:8px;text-decoration:none}</style>
</head><body><div class='box'>
<h2>マネーフォワード同期完了</h2>
<p>期間：{$DATE_FROM} ～ {$DATE_TO}</p>
<p>請求書：<span class='new'>新規 {$addedInv}件</span> / <span class='upd'>更新 {$updatedInv}件</span>（合計 " . count($mergedInvoices) . "件保持）</p>
<p>見積書：<span class='new'>新規 {$addedQuo}件</span> / <span class='upd'>更新 {$updatedQuo}件</span>（合計 " . count($mergedQuotes) . "件保持）</p>
<a href='/della_score.html'>Della Scoreに戻る</a>
</div></body></html>";

// ── ヘルパー関数 ──
function mf_post($url, $params, $useBasicAuth = false) {
    $ch = curl_init($url);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, http_build_query($params));
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
    $headers = ['Accept: application/json'];
    if ($useBasicAuth) curl_setopt($ch, CURLOPT_USERPWD, MF_CLIENT_ID . ':' . MF_CLIENT_SECRET);
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
    $res = curl_exec($ch); curl_close($ch);
    return json_decode($res, true);
}
function mf_get($url, $token) {
    $ch = curl_init($url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
    curl_setopt($ch, CURLOPT_HTTPHEADER, ['Authorization: Bearer ' . $token, 'Accept: application/json']);
    $res = curl_exec($ch); curl_close($ch);
    return json_decode($res, true);
}
