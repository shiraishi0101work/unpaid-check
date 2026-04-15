<?php
header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { exit; }

$db = new PDO('sqlite:' . __DIR__ . '/manual.db');
$db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

// テーブル作成
$db->exec("CREATE TABLE IF NOT EXISTS sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT,
    image_path TEXT,
    order_num INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime'))
)");

$db->exec("CREATE TABLE IF NOT EXISTS update_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    section_id INTEGER,
    page_title TEXT,
    action TEXT DEFAULT 'update',
    note TEXT,
    updated_at TEXT DEFAULT (datetime('now','localtime'))
)");

$method = $_SERVER['REQUEST_METHOD'];
$action = $_GET['action'] ?? '';

// ─── 画像アップロード ───
if ($action === 'upload_image') {
    if (!isset($_FILES['image'])) {
        echo json_encode(['success' => false, 'error' => 'ファイルがありません']);
        exit;
    }
    $uploadDir = __DIR__ . '/uploads/';
    if (!is_dir($uploadDir)) mkdir($uploadDir, 0755, true);
    $ext = strtolower(pathinfo($_FILES['image']['name'], PATHINFO_EXTENSION));
    if (!in_array($ext, ['jpg', 'jpeg', 'png', 'gif', 'webp'])) {
        echo json_encode(['success' => false, 'error' => '対応形式: jpg, png, gif, webp']);
        exit;
    }
    $filename = uniqid('img_') . '.' . $ext;
    move_uploaded_file($_FILES['image']['tmp_name'], $uploadDir . $filename);
    echo json_encode(['success' => true, 'path' => 'uploads/' . $filename]);
    exit;
}

// ─── ページ一覧取得 ───
if ($method === 'GET' && $action === 'list') {
    $rows = $db->query("SELECT * FROM sections ORDER BY order_num ASC, id ASC")->fetchAll(PDO::FETCH_ASSOC);
    echo json_encode(['success' => true, 'data' => $rows]);
    exit;
}

// ─── 更新履歴取得 ───
if ($method === 'GET' && $action === 'history') {
    $rows = $db->query("SELECT * FROM update_history ORDER BY id DESC LIMIT 100")->fetchAll(PDO::FETCH_ASSOC);
    echo json_encode(['success' => true, 'data' => $rows]);
    exit;
}

$body = json_decode(file_get_contents('php://input'), true) ?? [];

// ─── ページ追加 ───
if ($method === 'POST' && $action === 'add') {
    $maxOrder = $db->query("SELECT COALESCE(MAX(order_num),0) FROM sections")->fetchColumn();
    $title = $body['title'] ?? '新しいページ';
    $stmt = $db->prepare("INSERT INTO sections (title, content, image_path, order_num) VALUES (?,?,?,?)");
    $stmt->execute([$title, $body['content'] ?? '', $body['image_path'] ?? '', $maxOrder + 1]);
    $id = $db->lastInsertId();
    $row = $db->query("SELECT * FROM sections WHERE id=$id")->fetch(PDO::FETCH_ASSOC);
    // 履歴記録
    $db->prepare("INSERT INTO update_history (section_id, page_title, action, note) VALUES (?,?,?,?)")
       ->execute([$id, $title, 'add', '新規作成']);
    echo json_encode(['success' => true, 'data' => $row]);
    exit;
}

// ─── ページ更新 ───
if ($method === 'POST' && $action === 'update') {
    $id    = $body['id']    ?? 0;
    $title = $body['title'] ?? '';
    $note  = $body['note']  ?? '';
    $stmt  = $db->prepare("UPDATE sections SET title=?, content=?, image_path=?, updated_at=datetime('now','localtime') WHERE id=?");
    $stmt->execute([$title, $body['content'] ?? '', $body['image_path'] ?? '', $id]);
    // 履歴記録
    $db->prepare("INSERT INTO update_history (section_id, page_title, action, note) VALUES (?,?,?,?)")
       ->execute([$id, $title, 'update', $note]);
    echo json_encode(['success' => true]);
    exit;
}

// ─── 並び替え ───
if ($method === 'POST' && $action === 'reorder') {
    $ids = $body['ids'] ?? [];
    foreach ($ids as $i => $id) {
        $db->prepare("UPDATE sections SET order_num=? WHERE id=?")->execute([$i + 1, $id]);
    }
    echo json_encode(['success' => true]);
    exit;
}

// ─── ページ削除 ───
if ($method === 'POST' && $action === 'delete') {
    $id = $body['id'] ?? 0;
    $row = $db->query("SELECT * FROM sections WHERE id=$id")->fetch(PDO::FETCH_ASSOC);
    // 画像ファイル削除
    if ($row && $row['image_path'] && file_exists(__DIR__ . '/' . $row['image_path'])) {
        unlink(__DIR__ . '/' . $row['image_path']);
    }
    $db->prepare("DELETE FROM sections WHERE id=?")->execute([$id]);
    // 履歴記録
    $db->prepare("INSERT INTO update_history (section_id, page_title, action, note) VALUES (?,?,?,?)")
       ->execute([$id, $row['title'] ?? '', 'delete', '削除']);
    echo json_encode(['success' => true]);
    exit;
}

echo json_encode(['success' => false, 'error' => '不明なアクション']);
