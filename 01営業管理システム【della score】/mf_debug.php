<?php
session_start();

define('MF_CLIENT_ID',     '236289199630974');
define('MF_CLIENT_SECRET', 'zocDfXdqbj-iVtFADIxhLUHSepDCKVqzdP0Z_FdKTa7yAcs03StPylEyIxyxm17_N8fKSenIN8w3JlEQMRrOhw');
define('MF_REDIRECT_URI',  'http://localhost:8080/mf_debug.php');
define('MF_AUTH_URL',      'https://api.biz.moneyforward.com/authorize');
define('MF_TOKEN_URL',     'https://api.biz.moneyforward.com/token');
define('MF_API_BASE',      'https://invoice.moneyforward.com/api/v3');

echo "<pre style='font-size:13px;font-family:monospace'>";

// ── Step1: 認証コードがない場合はOAuthへ ──
if (empty($_GET['code'])) {
    $state = bin2hex(random_bytes(16));
    $_SESSION['mf_dbg_state'] = $state;
    $params = http_build_query([
        'client_id'     => MF_CLIENT_ID,
        'redirect_uri'  => MF_REDIRECT_URI,
        'response_type' => 'code',
        'scope'         => 'mfc/invoice/data.read mfc/invoice/data.write',
        'state'         => $state,
    ]);
    header('Location: ' . MF_AUTH_URL . '?' . $params);
    exit;
}

// ── Step2: トークン取得 ──
echo "=== トークン取得 ===\n";
$tokenRes = mf_post(MF_TOKEN_URL, [
    'grant_type'   => 'authorization_code',
    'code'         => $_GET['code'],
    'redirect_uri' => MF_REDIRECT_URI,
], true);
echo "レスポンス: " . json_encode($tokenRes, JSON_UNESCAPED_UNICODE|JSON_PRETTY_PRINT) . "\n\n";

if (empty($tokenRes['access_token'])) { echo "トークン取得失敗"; exit; }
$token = $tokenRes['access_token'];

// ── Step3: 請求書1ページ目を生で確認 ──
echo "=== 請求書 1ページ目（生レスポンス） ===\n";
$res = mf_get(MF_API_BASE . '/billings?per_page=5&page=1', $token);
echo json_encode($res, JSON_UNESCAPED_UNICODE|JSON_PRETTY_PRINT) . "\n\n";

// ── Step4: 見積書1ページ目を生で確認 ──
echo "=== 見積書 1ページ目（生レスポンス） ===\n";
$res2 = mf_get(MF_API_BASE . '/quotes?per_page=5&page=1', $token);
echo json_encode($res2, JSON_UNESCAPED_UNICODE|JSON_PRETTY_PRINT) . "\n\n";

echo "</pre>";

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
    curl_setopt($ch, CURLOPT_HTTPHEADER, [
        'Authorization: Bearer ' . $token,
        'Accept: application/json',
    ]);
    $res = curl_exec($ch); curl_close($ch);
    return json_decode($res, true);
}
