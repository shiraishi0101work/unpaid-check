<?php
session_start();
if (isset($_SESSION['user'])) {
    header('Location: /');
    exit;
}

$error = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $pass = $_POST['password'] ?? '';

    $db = new PDO('sqlite:' . __DIR__ . '/iwata_assist.db');
    $db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $db->exec("CREATE TABLE IF NOT EXISTS users (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        display  TEXT DEFAULT ''
    )");
    // デフォルトユーザーがいなければ作成
    if ((int)$db->query('SELECT COUNT(*) FROM users')->fetchColumn() === 0) {
        $st = $db->prepare('INSERT INTO users (username, password, display) VALUES (?,?,?)');
        $st->execute(['admin',  password_hash('iwata2024', PASSWORD_DEFAULT), '管理者']);
    }

    // パスワードがいずれかのユーザーと一致するか確認
    $rows = $db->query('SELECT * FROM users')->fetchAll(PDO::FETCH_ASSOC);
    $matched = null;
    foreach ($rows as $row) {
        if (password_verify($pass, $row['password'])) {
            $matched = $row;
            break;
        }
    }

    if ($matched) {
        $_SESSION['user']    = $matched['username'];
        $_SESSION['display'] = $matched['display'];
        header('Location: /');
        exit;
    } else {
        $error = 'パスワードが違います';
    }
}
?>
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ログイン - イワタアシスト</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Hiragino Kaku Gothic ProN', 'Noto Sans JP', sans-serif;
    background: #F2F5F5;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .card {
    background: #fff;
    border-radius: 14px;
    padding: 40px 36px;
    width: 360px;
    box-shadow: 0 4px 24px rgba(0,168,157,0.12);
  }
  .logo {
    text-align: center;
    margin-bottom: 28px;
  }
  .logo-title {
    font-size: 22px;
    font-weight: 800;
    color: #00A89D;
    letter-spacing: -0.02em;
  }
  .logo-sub {
    font-size: 12px;
    color: #5A7170;
    margin-top: 4px;
  }
  label {
    display: block;
    font-size: 12px;
    font-weight: 600;
    color: #5A7170;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    margin-bottom: 6px;
    margin-top: 18px;
  }
  input {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid #D8E4E3;
    border-radius: 8px;
    font-size: 14px;
    color: #1A2A29;
    outline: none;
    transition: border-color 0.15s;
  }
  input:focus { border-color: #00A89D; }
  .btn {
    margin-top: 24px;
    width: 100%;
    padding: 12px;
    background: #00A89D;
    color: #fff;
    border: none;
    border-radius: 8px;
    font-size: 15px;
    font-weight: 700;
    cursor: pointer;
    transition: background 0.15s;
  }
  .btn:hover { background: #007F77; }
  .error {
    margin-top: 14px;
    padding: 10px 12px;
    background: #FDECEC;
    color: #9A2020;
    border-radius: 8px;
    font-size: 13px;
    text-align: center;
  }
</style>
</head>
<body>
<div class="card">
  <div class="logo">
    <div class="logo-title">イワタアシスト</div>
    <div class="logo-sub">仕入れ管理システム</div>
  </div>
  <form method="post">
    <label>パスワード</label>
    <input type="password" name="password" autocomplete="current-password" required autofocus>
    <button type="submit" class="btn">ログイン</button>
    <?php if ($error): ?>
    <div class="error"><?= htmlspecialchars($error) ?></div>
    <?php endif; ?>
  </form>
</div>
</body>
</html>
