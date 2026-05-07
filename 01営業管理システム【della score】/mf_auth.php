<?php
session_start();

define('MF_CLIENT_ID',    '236289199630974');
define('MF_REDIRECT_URI', 'http://localhost:8080/mf_callback.php');
define('MF_AUTH_URL',     'https://api.biz.moneyforward.com/authorize');

// フォーム送信時 → セッションに日付保存してOAuthへ
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $_SESSION['mf_date_from'] = $_POST['date_from'] ?? '2026-01-01';
    $_SESSION['mf_date_to']   = $_POST['date_to']   ?? date('Y-m-d');
    $_SESSION['mf_debug']     = !empty($_POST['debug']);
    $state = bin2hex(random_bytes(16));
    $_SESSION['mf_state'] = $state;
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

// 年月の選択肢生成（2024-01〜今月）
$months = [];
$start = new DateTime('2024-01-01');
$end   = new DateTime();
$end->modify('first day of this month');
while ($start <= $end) {
    $months[] = $start->format('Y-m');
    $start->modify('+1 month');
}
$months = array_reverse($months);
$thisMonth = date('Y-m');
?>
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>MF同期 — Della Score</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Hiragino Kaku Gothic ProN',sans-serif;background:#F4F6FB;display:flex;align-items:center;justify-content:center;min-height:100vh}
.card{background:#fff;border-radius:12px;padding:32px;width:380px;box-shadow:0 4px 20px rgba(27,43,75,.1)}
h2{font-size:16px;font-weight:700;color:#1B2B4B;margin-bottom:6px}
p{font-size:13px;color:#8892B0;margin-bottom:24px}
label{font-size:12px;font-weight:600;color:#4A5578;display:block;margin-bottom:5px}
select{width:100%;padding:8px 10px;border:1px solid #DDE2EF;border-radius:8px;font-size:13px;font-family:inherit;color:#1B2340;background:#fff;margin-bottom:16px}
.row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.btn{width:100%;padding:10px;background:#1B2B4B;color:#fff;border:none;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;margin-top:8px;font-family:inherit}
.btn:hover{background:#243660}
.back{display:block;text-align:center;margin-top:14px;font-size:12px;color:#8892B0;text-decoration:none}
.back:hover{color:#1B2B4B}
.tag{display:inline-block;background:#E3F4F7;color:#0E6673;font-size:11px;font-weight:600;padding:2px 8px;border-radius:20px;margin-bottom:16px}
</style>
</head>
<body>
<div class="card">
  <span class="tag">MF クラウド請求書</span>
  <h2>取得期間を選択</h2>
  <p>作成日でフィルターします（請求書・見積書の作成日が対象期間内のものを取得）</p>
  <form method="POST">
    <div class="row">
      <div>
        <label>開始月</label>
        <select name="date_from">
          <?php foreach($months as $m): ?>
            <option value="<?= $m ?>-01" <?= $m==='2026-01'?'selected':'' ?>><?= str_replace('-','年',$m) ?>月</option>
          <?php endforeach; ?>
        </select>
      </div>
      <div>
        <label>終了月</label>
        <select name="date_to">
          <?php foreach($months as $m): ?>
            <option value="<?= $m ?>-<?= date('t',strtotime($m.'-01')) ?>" <?= $m===$thisMonth?'selected':'' ?>><?= str_replace('-','年',$m) ?>月</option>
          <?php endforeach; ?>
        </select>
      </div>
    </div>
    <button type="submit" class="btn">マネーフォワードと同期する</button>
    <button type="submit" name="debug" value="1" class="btn" style="margin-top:8px;background:#EEF1F8;color:#1B2B4B;border:1px solid #C8D0E8">APIレスポンス確認（デバッグ）</button>
  </form>
  <a href="/della_score.html" class="back">← Della Scoreに戻る</a>
</div>
</body>
</html>
