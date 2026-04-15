<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AIブログマスター 仕様説明書管理</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', 'Hiragino Kaku Gothic ProN', sans-serif; background: #f0f2f5; color: #1a1a2e; }

  /* ヘッダー */
  header {
    background: linear-gradient(135deg, #1a1a2e, #16213e);
    color: #fff;
    padding: 16px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
  }
  header h1 { font-size: 1.2rem; font-weight: 700; }
  header .badge { background: #e94560; color: #fff; font-size: 0.7rem; padding: 2px 8px; border-radius: 20px; margin-left: 10px; }
  .btn {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 8px 16px; border-radius: 8px; border: none; cursor: pointer;
    font-size: 0.85rem; font-weight: 600; transition: all 0.2s;
  }
  .btn-primary { background: #e94560; color: #fff; }
  .btn-primary:hover { background: #c73651; }
  .btn-success { background: #28a745; color: #fff; }
  .btn-success:hover { background: #1e7e34; }
  .btn-danger  { background: #dc3545; color: #fff; }
  .btn-danger:hover  { background: #a71d2a; }
  .btn-secondary { background: #6c757d; color: #fff; }
  .btn-secondary:hover { background: #545b62; }
  .btn-outline { background: transparent; border: 2px solid #1a1a2e; color: #1a1a2e; }
  .btn-outline:hover { background: #1a1a2e; color: #fff; }

  /* レイアウト */
  .container { max-width: 1200px; margin: 0 auto; padding: 24px; }
  .top-bar {
    display: flex; gap: 10px; align-items: center; margin-bottom: 24px;
    background: #fff; padding: 16px 20px; border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  }
  .top-bar h2 { flex: 1; font-size: 1rem; color: #555; }

  /* セクションリスト */
  #section-list { display: flex; flex-direction: column; gap: 12px; }
  .section-card {
    background: #fff; border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.07);
    overflow: hidden; transition: box-shadow 0.2s;
  }
  .section-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.12); }
  .section-card.dragging { opacity: 0.5; }
  .section-card.drag-over { border: 2px dashed #e94560; }

  .card-header {
    display: flex; align-items: center; gap: 12px;
    padding: 14px 16px;
    background: linear-gradient(90deg, #1a1a2e, #16213e);
    color: #fff; cursor: pointer;
  }
  .drag-handle { cursor: grab; font-size: 1.2rem; color: #aaa; }
  .drag-handle:active { cursor: grabbing; }
  .card-num {
    background: #e94560; color: #fff; font-size: 0.75rem; font-weight: 700;
    width: 24px; height: 24px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  }
  .card-title { flex: 1; font-weight: 600; font-size: 0.95rem; }
  .card-actions { display: flex; gap: 6px; }
  .card-body { padding: 16px; display: none; }
  .card-body.open { display: block; }

  /* フォーム */
  .form-group { margin-bottom: 14px; }
  label { display: block; font-size: 0.8rem; font-weight: 600; color: #555; margin-bottom: 4px; }
  input[type="text"], textarea {
    width: 100%; padding: 10px 12px; border: 1px solid #ddd; border-radius: 8px;
    font-size: 0.9rem; font-family: inherit; color: #333;
    transition: border-color 0.2s;
  }
  input[type="text"]:focus, textarea:focus { outline: none; border-color: #e94560; }
  textarea { min-height: 120px; resize: vertical; }

  /* 画像アップロード */
  .image-upload-area {
    border: 2px dashed #ddd; border-radius: 8px; padding: 20px; text-align: center;
    cursor: pointer; transition: all 0.2s; background: #fafafa;
  }
  .image-upload-area:hover, .image-upload-area.dragover { border-color: #e94560; background: #fff5f7; }
  .image-upload-area input { display: none; }
  .preview-img { max-width: 100%; max-height: 200px; border-radius: 8px; margin-top: 10px; }
  .remove-img { background: none; border: none; color: #dc3545; cursor: pointer; font-size: 0.8rem; margin-top: 4px; }

  /* 空状態 */
  .empty-state {
    text-align: center; padding: 60px 20px;
    background: #fff; border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.07);
    color: #999;
  }
  .empty-state .icon { font-size: 3rem; margin-bottom: 12px; }

  /* トースト */
  #toast {
    position: fixed; bottom: 24px; right: 24px;
    background: #1a1a2e; color: #fff; padding: 12px 20px; border-radius: 10px;
    font-size: 0.9rem; transform: translateY(100px); opacity: 0;
    transition: all 0.3s; z-index: 9999;
  }
  #toast.show { transform: translateY(0); opacity: 1; }
  #toast.success { background: #28a745; }
  #toast.error { background: #dc3545; }

  /* ローディング */
  .loading { text-align: center; padding: 40px; color: #999; }
</style>
</head>
<body>

<header>
  <div style="display:flex;align-items:center;gap:10px;">
    <h1>AIブログマスター 仕様説明書</h1>
    <span class="badge">管理画面</span>
  </div>
  <div style="display:flex;gap:8px;">
    <button class="btn btn-success" onclick="exportPPTX()">⬇ PowerPointで出力</button>
  </div>
</header>

<div class="container">
  <div class="top-bar">
    <h2 id="section-count">読み込み中...</h2>
    <button class="btn btn-primary" onclick="addSection()">＋ セクションを追加</button>
  </div>
  <div id="section-list">
    <div class="loading">読み込み中...</div>
  </div>
</div>

<div id="toast"></div>

<script>
let sections = [];
let dragSrcId = null;

async function api(action, body = null, isForm = false) {
  const url = `api.php?action=${action}`;
  const opts = { method: body ? 'POST' : 'GET' };
  if (body) {
    if (isForm) { opts.body = body; delete opts.headers; }
    else { opts.headers = { 'Content-Type': 'application/json' }; opts.body = JSON.stringify(body); }
  }
  const res = await fetch(url, opts);
  return res.json();
}

function toast(msg, type = '') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = 'show ' + type;
  setTimeout(() => el.className = '', 2500);
}

async function load() {
  const res = await api('list');
  sections = res.data || [];
  render();
}

function render() {
  const list = document.getElementById('section-list');
  document.getElementById('section-count').textContent = `全 ${sections.length} セクション`;
  if (sections.length === 0) {
    list.innerHTML = `<div class="empty-state"><div class="icon">📄</div><p>セクションがありません<br>「セクションを追加」から始めましょう</p></div>`;
    return;
  }
  list.innerHTML = '';
  sections.forEach((s, i) => {
    const card = document.createElement('div');
    card.className = 'section-card';
    card.dataset.id = s.id;
    card.draggable = true;

    const imgHtml = s.image_path
      ? `<img src="${s.image_path}" class="preview-img"><br><button class="remove-img" onclick="removeImage(${s.id})">✕ 画像を削除</button>`
      : `<div class="image-upload-area" ondragover="event.preventDefault();this.classList.add('dragover')" ondragleave="this.classList.remove('dragover')" ondrop="handleDrop(event,${s.id},this)">
           <input type="file" accept="image/*" id="file-${s.id}" onchange="uploadImage(${s.id},this)">
           <label for="file-${s.id}" style="cursor:pointer;">
             🖼 クリックまたはドラッグで画像をアップロード
           </label>
         </div>`;

    card.innerHTML = `
      <div class="card-header" onclick="toggleCard(${s.id})">
        <span class="drag-handle" draggable="true" onmousedown="event.stopPropagation()">⠿</span>
        <span class="card-num">${i + 1}</span>
        <span class="card-title">${escHtml(s.title)}</span>
        <div class="card-actions" onclick="event.stopPropagation()">
          <button class="btn btn-success" style="padding:5px 10px;font-size:0.75rem" onclick="saveSection(${s.id})">保存</button>
          <button class="btn btn-danger"  style="padding:5px 10px;font-size:0.75rem" onclick="deleteSection(${s.id})">削除</button>
        </div>
      </div>
      <div class="card-body" id="body-${s.id}">
        <div class="form-group">
          <label>タイトル</label>
          <input type="text" id="title-${s.id}" value="${escHtml(s.title)}">
        </div>
        <div class="form-group">
          <label>内容</label>
          <textarea id="content-${s.id}">${escHtml(s.content)}</textarea>
        </div>
        <div class="form-group">
          <label>画像</label>
          <div id="img-area-${s.id}">${imgHtml}</div>
        </div>
      </div>`;

    // ドラッグ&ドロップ並び替え
    card.addEventListener('dragstart', () => { dragSrcId = s.id; card.classList.add('dragging'); });
    card.addEventListener('dragend',   () => card.classList.remove('dragging'));
    card.addEventListener('dragover',  e => { e.preventDefault(); card.classList.add('drag-over'); });
    card.addEventListener('dragleave', () => card.classList.remove('drag-over'));
    card.addEventListener('drop', async e => {
      e.preventDefault();
      card.classList.remove('drag-over');
      if (dragSrcId === s.id) return;
      const srcIdx = sections.findIndex(x => x.id == dragSrcId);
      const dstIdx = sections.findIndex(x => x.id == s.id);
      const [moved] = sections.splice(srcIdx, 1);
      sections.splice(dstIdx, 0, moved);
      render();
      await api('reorder', { ids: sections.map(x => x.id) });
      toast('並び順を保存しました', 'success');
    });

    list.appendChild(card);
  });
}

function toggleCard(id) {
  const body = document.getElementById('body-' + id);
  body.classList.toggle('open');
}

async function addSection() {
  const res = await api('add', { title: '新しいセクション', content: '', image_path: '' });
  if (res.success) {
    sections.push(res.data);
    render();
    // 追加したカードを開く
    setTimeout(() => {
      document.getElementById('body-' + res.data.id)?.classList.add('open');
      document.getElementById('title-' + res.data.id)?.focus();
      document.getElementById('title-' + res.data.id)?.select();
    }, 50);
    toast('セクションを追加しました', 'success');
  }
}

async function saveSection(id) {
  const title   = document.getElementById('title-'   + id)?.value || '';
  const content = document.getElementById('content-' + id)?.value || '';
  const sec = sections.find(s => s.id == id);
  const image_path = sec?.image_path || '';
  const res = await api('update', { id, title, content, image_path });
  if (res.success) {
    const s = sections.find(x => x.id == id);
    if (s) { s.title = title; s.content = content; }
    // タイトルだけ更新
    const titleEl = document.querySelector(`[data-id="${id}"] .card-title`);
    if (titleEl) titleEl.textContent = title;
    toast('保存しました ✓', 'success');
  }
}

async function deleteSection(id) {
  if (!confirm('このセクションを削除しますか？')) return;
  const res = await api('delete', { id });
  if (res.success) {
    sections = sections.filter(s => s.id != id);
    render();
    toast('削除しました', 'error');
  }
}

async function uploadImage(id, input) {
  const file = input.files[0];
  if (!file) return;
  const form = new FormData();
  form.append('image', file);
  const res = await api('upload_image', form, true);
  if (res.success) {
    const s = sections.find(x => x.id == id);
    if (s) s.image_path = res.path;
    // 自動保存
    const title   = document.getElementById('title-'   + id)?.value || '';
    const content = document.getElementById('content-' + id)?.value || '';
    await api('update', { id, title, content, image_path: res.path });
    // プレビュー更新
    document.getElementById('img-area-' + id).innerHTML =
      `<img src="${res.path}" class="preview-img"><br><button class="remove-img" onclick="removeImage(${id})">✕ 画像を削除</button>`;
    toast('画像をアップロードしました ✓', 'success');
  } else {
    toast('アップロード失敗: ' + res.error, 'error');
  }
}

async function handleDrop(e, id, area) {
  e.preventDefault();
  area.classList.remove('dragover');
  const file = e.dataTransfer.files[0];
  if (!file || !file.type.startsWith('image/')) return;
  const form = new FormData();
  form.append('image', file);
  const res = await api('upload_image', form, true);
  if (res.success) {
    const s = sections.find(x => x.id == id);
    if (s) s.image_path = res.path;
    const title   = document.getElementById('title-'   + id)?.value || '';
    const content = document.getElementById('content-' + id)?.value || '';
    await api('update', { id, title, content, image_path: res.path });
    document.getElementById('img-area-' + id).innerHTML =
      `<img src="${res.path}" class="preview-img"><br><button class="remove-img" onclick="removeImage(${id})">✕ 画像を削除</button>`;
    toast('画像をアップロードしました ✓', 'success');
  }
}

async function removeImage(id) {
  if (!confirm('画像を削除しますか？')) return;
  const s = sections.find(x => x.id == id);
  if (s) s.image_path = '';
  const title   = document.getElementById('title-'   + id)?.value || '';
  const content = document.getElementById('content-' + id)?.value || '';
  await api('update', { id, title, content, image_path: '' });
  document.getElementById('img-area-' + id).innerHTML =
    `<div class="image-upload-area" ondragover="event.preventDefault();this.classList.add('dragover')" ondragleave="this.classList.remove('dragover')" ondrop="handleDrop(event,${id},this)">
       <input type="file" accept="image/*" id="file-${id}" onchange="uploadImage(${id},this)">
       <label for="file-${id}" style="cursor:pointer;">🖼 クリックまたはドラッグで画像をアップロード</label>
     </div>`;
  toast('画像を削除しました');
}

function exportPPTX() {
  toast('PowerPointを生成中...');
  window.location.href = 'export_pptx.php';
}

function escHtml(s) {
  return (s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

load();
</script>
</body>
</html>
