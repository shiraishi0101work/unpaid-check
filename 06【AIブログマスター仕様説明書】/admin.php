<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AIブログマスター 仕様説明書</title>
<style>
/* ─── リセット & 共通 ─── */
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', 'Hiragino Kaku Gothic ProN', sans-serif; background: #f0f2f5; color: #1a1a2e; height: 100vh; display: flex; flex-direction: column; }

/* ─── ヘッダー ─── */
header {
  background: linear-gradient(135deg, #1a1a2e, #16213e);
  color: #fff; padding: 0 24px; height: 56px;
  display: flex; align-items: center; justify-content: space-between;
  box-shadow: 0 2px 8px rgba(0,0,0,.3); flex-shrink: 0; z-index: 10;
}
header h1 { font-size: 1.1rem; font-weight: 700; display: flex; align-items: center; gap: 10px; }
.badge { background: #e94560; color: #fff; font-size: 0.65rem; padding: 2px 8px; border-radius: 20px; }
.header-right { display: flex; gap: 8px; align-items: center; }

/* ─── ボタン ─── */
.btn { display: inline-flex; align-items: center; gap: 5px; padding: 7px 14px; border-radius: 7px; border: none; cursor: pointer; font-size: 0.82rem; font-weight: 600; transition: all .18s; white-space: nowrap; }
.btn-primary { background: #e94560; color: #fff; }
.btn-primary:hover { background: #c73651; }
.btn-success { background: #28a745; color: #fff; }
.btn-success:hover { background: #1e7e34; }
.btn-danger  { background: #dc3545; color: #fff; }
.btn-danger:hover  { background: #a71d2a; }
.btn-ghost { background: rgba(255,255,255,.12); color: #fff; border: 1px solid rgba(255,255,255,.25); }
.btn-ghost:hover { background: rgba(255,255,255,.22); }
.btn-tab { background: transparent; color: #888; border: none; padding: 8px 16px; font-size: .85rem; font-weight: 600; cursor: pointer; border-bottom: 3px solid transparent; }
.btn-tab.active { color: #e94560; border-bottom-color: #e94560; }

/* ─── メインレイアウト ─── */
.workspace { display: flex; flex: 1; overflow: hidden; }

/* ─── 左パネル：ページ一覧 ─── */
.sidebar {
  width: 260px; flex-shrink: 0; background: #fff;
  border-right: 1px solid #e8e8e8;
  display: flex; flex-direction: column; overflow: hidden;
}
.sidebar-header {
  padding: 14px 16px; border-bottom: 1px solid #f0f0f0;
  display: flex; align-items: center; justify-content: space-between;
}
.sidebar-header span { font-size: .8rem; font-weight: 700; color: #555; }
.page-list { flex: 1; overflow-y: auto; padding: 8px; }
.page-item {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 10px; border-radius: 8px; cursor: pointer;
  transition: background .15s; margin-bottom: 2px; position: relative;
}
.page-item:hover { background: #f5f5f5; }
.page-item.active { background: #fff5f7; border: 1px solid #ffd0d8; }
.page-item.active .page-num { background: #e94560; }
.page-num {
  background: #ccc; color: #fff; font-size: .7rem; font-weight: 700;
  width: 22px; height: 22px; border-radius: 50%; display: flex;
  align-items: center; justify-content: center; flex-shrink: 0;
  transition: background .15s;
}
.page-name { flex: 1; font-size: .82rem; font-weight: 600; color: #333; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.page-drag { color: #ccc; font-size: 1rem; cursor: grab; flex-shrink: 0; }
.page-drag:active { cursor: grabbing; }
.page-item.dragging { opacity: .4; }
.page-item.drag-over { border: 2px dashed #e94560; background: #fff5f7; }

/* ─── 中央：エディタ ─── */
.editor-pane {
  flex: 1; display: flex; flex-direction: column; overflow: hidden;
  min-width: 0;
}
.tab-bar {
  background: #fff; border-bottom: 1px solid #e8e8e8;
  padding: 0 20px; display: flex; align-items: center; gap: 4px;
  flex-shrink: 0;
}
.editor-body { flex: 1; overflow-y: auto; padding: 24px; }

/* エディタフォーム */
.editor-form { max-width: 900px; }
.form-group { margin-bottom: 18px; }
.form-label { display: block; font-size: .78rem; font-weight: 700; color: #666; margin-bottom: 6px; text-transform: uppercase; letter-spacing: .5px; }
.form-input, .form-textarea {
  width: 100%; padding: 10px 14px; border: 1.5px solid #e0e0e0; border-radius: 8px;
  font-size: .92rem; font-family: inherit; color: #1a1a2e;
  transition: border-color .18s;
}
.form-input:focus, .form-textarea:focus { outline: none; border-color: #e94560; }
.form-textarea { min-height: 160px; resize: vertical; line-height: 1.7; }
.update-note-input { border-color: #ffc107; background: #fffdf0; }
.update-note-input:focus { border-color: #e0a800; }

/* 画像エリア */
.img-drop-area {
  border: 2px dashed #ddd; border-radius: 10px; padding: 28px; text-align: center;
  cursor: pointer; transition: all .2s; background: #fafafa; color: #aaa; font-size: .88rem;
}
.img-drop-area:hover, .img-drop-area.dragover { border-color: #e94560; background: #fff5f7; color: #e94560; }
.img-drop-area input { display: none; }
.img-scroll-wrap { overflow-x: auto; border: 1px solid #e0e0e0; border-radius: 10px; background: #fafafa; padding: 10px; }
.preview-img { display: block; width: auto; height: auto; max-width: none; border-radius: 6px; }
.btn-remove-img { background: none; border: none; color: #dc3545; cursor: pointer; font-size: .78rem; margin-top: 6px; }

/* エディタのアクションバー */
.editor-actions {
  background: #fff; border-top: 1px solid #e8e8e8;
  padding: 12px 24px; display: flex; align-items: center; gap: 10px;
  flex-shrink: 0;
}
.update-note-wrap { flex: 1; display: flex; align-items: center; gap: 8px; }
.update-note-wrap label { font-size: .78rem; font-weight: 700; color: #888; white-space: nowrap; }
.update-note-wrap input { flex: 1; padding: 7px 12px; border: 1.5px solid #e0e0e0; border-radius: 7px; font-size: .82rem; font-family: inherit; }

/* 右パネル：プレビュー */
.preview-pane {
  width: 420px; flex-shrink: 0; border-left: 1px solid #e8e8e8;
  background: #fff; display: flex; flex-direction: column; overflow: hidden;
}
.preview-pane-header {
  padding: 12px 16px; border-bottom: 1px solid #f0f0f0;
  display: flex; align-items: center; justify-content: space-between; flex-shrink: 0;
}
.preview-pane-header span { font-size: .8rem; font-weight: 700; color: #555; }
.preview-content { flex: 1; overflow-y: auto; padding: 16px; }
.preview-doc { }
.preview-page {
  border: 1px solid #e8e8e8; border-radius: 10px; margin-bottom: 12px;
  overflow: hidden; transition: box-shadow .15s;
}
.preview-page.current { border-color: #e94560; box-shadow: 0 0 0 2px rgba(233,69,96,.2); }
.preview-page-header {
  background: linear-gradient(90deg, #1a1a2e, #16213e);
  color: #fff; padding: 8px 12px; display: flex; align-items: center; gap: 8px;
}
.preview-page-num { background: #e94560; color: #fff; font-size: .65rem; font-weight: 700; width: 18px; height: 18px; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.preview-page-title { font-size: .82rem; font-weight: 700; }
.preview-page-body { padding: 10px 12px; font-size: .75rem; color: #555; line-height: 1.6; }
.preview-page-body img { max-width: 100%; border-radius: 4px; margin-top: 6px; }
.preview-empty { text-align: center; padding: 40px 20px; color: #ccc; font-size: .85rem; }

/* 更新履歴 */
.history-section { padding: 0 24px 24px; }
.history-section h3 { font-size: .82rem; font-weight: 700; color: #888; margin-bottom: 10px; text-transform: uppercase; letter-spacing: .5px; }
.history-table { width: 100%; border-collapse: collapse; font-size: .8rem; }
.history-table th { background: #f8f8f8; padding: 6px 10px; text-align: left; color: #888; border-bottom: 1px solid #eee; }
.history-table td { padding: 6px 10px; border-bottom: 1px solid #f5f5f5; color: #555; }
.history-table tr:last-child td { border-bottom: none; }
.history-badge { font-size: .65rem; padding: 1px 6px; border-radius: 4px; font-weight: 700; }
.history-badge.add    { background: #d4edda; color: #155724; }
.history-badge.update { background: #fff3cd; color: #856404; }
.history-badge.delete { background: #f8d7da; color: #721c24; }

/* 空状態 */
.empty-state { text-align: center; padding: 80px 20px; color: #bbb; }
.empty-state .icon { font-size: 2.5rem; margin-bottom: 12px; }
.empty-state p { font-size: .9rem; line-height: 1.8; }

/* プレビュータブ（フルスクリーン） */
.full-preview { display: none; flex: 1; overflow-y: auto; padding: 32px; background: #f0f2f5; }
.full-preview.visible { display: block; }
.doc-paper {
  max-width: 960px; margin: 0 auto; background: #fff;
  border-radius: 12px; box-shadow: 0 4px 24px rgba(0,0,0,.1); overflow: hidden;
}
.doc-cover { background: linear-gradient(135deg, #1a1a2e, #16213e); color: #fff; padding: 48px 48px 36px; }
.doc-cover h2 { font-size: 1.8rem; font-weight: 700; margin-bottom: 8px; }
.doc-cover p { font-size: .88rem; color: rgba(255,255,255,.6); }
.doc-toc { padding: 24px 48px; border-bottom: 1px solid #f0f0f0; }
.doc-toc h3 { font-size: .78rem; font-weight: 700; color: #aaa; text-transform: uppercase; letter-spacing: .5px; margin-bottom: 12px; }
.doc-toc-item { display: flex; align-items: center; gap: 10px; padding: 6px 0; border-bottom: 1px dotted #eee; font-size: .88rem; color: #333; }
.doc-toc-num { color: #e94560; font-weight: 700; font-size: .8rem; width: 20px; }
.doc-pages { padding: 0 48px 48px; }
.doc-page { padding: 32px 0; border-bottom: 1px solid #f0f0f0; }
.doc-page:last-child { border-bottom: none; }
.doc-page-num-label { font-size: .7rem; font-weight: 700; color: #e94560; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 6px; }
.doc-page-title { font-size: 1.3rem; font-weight: 700; color: #1a1a2e; margin-bottom: 14px; padding-bottom: 10px; border-bottom: 2px solid #f0f0f0; }
.doc-page-content { font-size: .9rem; line-height: 1.9; color: #444; white-space: pre-wrap; }
.doc-page-img { margin-top: 20px; overflow-x: auto; border: 1px solid #e8e8e8; border-radius: 10px; background: #fafafa; padding: 10px; }
.doc-page-img img { display: block; width: auto; height: auto; max-width: none; border-radius: 6px; }

/* トースト */
#toast { position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%) translateY(80px); background: #1a1a2e; color: #fff; padding: 10px 20px; border-radius: 8px; font-size: .85rem; opacity: 0; transition: all .25s; z-index: 9999; white-space: nowrap; }
#toast.show { transform: translateX(-50%) translateY(0); opacity: 1; }
#toast.success { background: #28a745; }
#toast.error   { background: #dc3545; }

/* スクロールバー */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #ddd; border-radius: 3px; }
</style>
</head>
<body>

<header>
  <h1>📘 AIブログマスター 仕様説明書 <span class="badge">編集モード</span></h1>
  <div class="header-right">
    <button class="btn btn-ghost" id="btn-preview-full" onclick="toggleFullPreview()">👁 完成形を見る</button>
    <button class="btn btn-success" onclick="exportPPTX()">⬇ PowerPoint出力</button>
  </div>
</header>

<div class="workspace" id="workspace">

  <!-- 左：ページ一覧 -->
  <div class="sidebar">
    <div class="sidebar-header">
      <span>📄 ページ一覧</span>
      <button class="btn btn-primary" style="padding:5px 10px;font-size:.75rem" onclick="addPage()">＋ 追加</button>
    </div>
    <div class="page-list" id="page-list">
      <div style="text-align:center;padding:30px 10px;color:#ccc;font-size:.8rem;">読み込み中...</div>
    </div>
  </div>

  <!-- 中央：エディタ -->
  <div class="editor-pane" id="editor-pane">
    <div class="tab-bar">
      <button class="btn-tab active" id="tab-edit" onclick="switchTab('edit')">✏️ 編集</button>
      <button class="btn-tab" id="tab-history" onclick="switchTab('history')">🕐 更新履歴</button>
    </div>
    <div class="editor-body" id="editor-body">
      <div class="empty-state">
        <div class="icon">📝</div>
        <p>左のページ一覧からページを選ぶか、<br>「＋ 追加」で新しいページを作成してください。</p>
      </div>
    </div>
    <div class="editor-actions" id="editor-actions" style="display:none;">
      <div class="update-note-wrap">
        <label>📝 更新メモ</label>
        <input type="text" id="update-note" placeholder="例：手順①の説明を追記" maxlength="100">
      </div>
      <button class="btn btn-success" onclick="savePage()">💾 保存</button>
      <button class="btn btn-danger"  onclick="deletePage()">🗑 削除</button>
    </div>
  </div>

  <!-- 右：ミニプレビュー -->
  <div class="preview-pane" id="preview-pane">
    <div class="preview-pane-header">
      <span>👁 説明書プレビュー</span>
      <span style="font-size:.7rem;color:#bbb;">リアルタイム更新</span>
    </div>
    <div class="preview-content" id="mini-preview">
      <div class="preview-empty">ページを追加すると<br>ここにプレビューが表示されます</div>
    </div>
  </div>

</div>

<!-- フルプレビュー（タブ切替で表示） -->
<div class="full-preview" id="full-preview">
  <div class="doc-paper" id="doc-paper"></div>
</div>

<div id="toast"></div>

<script>
let pages = [];
let history = [];
let currentId = null;
let currentTab = 'edit';
let isFullPreview = false;
let dragSrcId = null;

// ─── API ───
async function api(action, body = null, isForm = false) {
  const opts = { method: body ? 'POST' : 'GET' };
  if (body) {
    if (isForm) { opts.body = body; }
    else { opts.headers = { 'Content-Type': 'application/json' }; opts.body = JSON.stringify(body); }
  }
  const res = await fetch(`api.php?action=${action}`, opts);
  return res.json();
}

function toast(msg, type = '') {
  const el = document.getElementById('toast');
  el.textContent = msg; el.className = 'show ' + type;
  setTimeout(() => el.className = '', 2500);
}

// ─── 初期ロード ───
async function init() {
  const [pRes, hRes] = await Promise.all([api('list'), api('history')]);
  pages   = pRes.data   || [];
  history = hRes.data   || [];
  renderSidebar();
  renderMiniPreview();
}

// ─── 左ペイン：ページ一覧 ───
function renderSidebar() {
  const list = document.getElementById('page-list');
  if (pages.length === 0) {
    list.innerHTML = '<div style="text-align:center;padding:30px 10px;color:#ccc;font-size:.8rem;">ページがありません<br>「＋ 追加」から作成</div>';
    return;
  }
  list.innerHTML = '';
  pages.forEach((p, i) => {
    const item = document.createElement('div');
    item.className = 'page-item' + (p.id === currentId ? ' active' : '');
    item.dataset.id = p.id;
    item.draggable = true;
    item.innerHTML = `
      <span class="page-drag" title="ドラッグで並び替え">⠿</span>
      <span class="page-num">${i + 1}</span>
      <span class="page-name" title="${escHtml(p.title)}">${escHtml(p.title)}</span>`;
    item.addEventListener('click', () => selectPage(p.id));
    item.addEventListener('dragstart', () => { dragSrcId = p.id; item.classList.add('dragging'); });
    item.addEventListener('dragend',   () => item.classList.remove('dragging'));
    item.addEventListener('dragover',  e => { e.preventDefault(); item.classList.add('drag-over'); });
    item.addEventListener('dragleave', () => item.classList.remove('drag-over'));
    item.addEventListener('drop', async e => {
      e.preventDefault(); item.classList.remove('drag-over');
      if (dragSrcId === p.id) return;
      const si = pages.findIndex(x => x.id == dragSrcId);
      const di = pages.findIndex(x => x.id == p.id);
      const [m] = pages.splice(si, 1); pages.splice(di, 0, m);
      renderSidebar(); renderMiniPreview();
      await api('reorder', { ids: pages.map(x => x.id) });
      toast('並び順を保存しました ✓', 'success');
    });
    list.appendChild(item);
  });
}

// ─── ページ選択 ───
function selectPage(id) {
  currentId = id;
  renderSidebar();
  if (currentTab === 'edit') renderEditor();
  else renderHistoryTab();
  renderMiniPreview();
  document.getElementById('editor-actions').style.display = 'flex';
}

// ─── エディタ描画 ───
function renderEditor() {
  const p = pages.find(x => x.id === currentId);
  if (!p) return;
  const imgHtml = p.image_path
    ? `<div class="img-scroll-wrap"><img src="${p.image_path}" class="preview-img"></div>
       <button class="btn-remove-img" onclick="removeImage()">✕ 画像を削除</button>`
    : `<div class="img-drop-area" id="drop-area"
          ondragover="event.preventDefault();this.classList.add('dragover')"
          ondragleave="this.classList.remove('dragover')"
          ondrop="handleImgDrop(event)">
         <input type="file" accept="image/*" id="img-file" onchange="uploadImage(this)">
         <label for="img-file" style="cursor:pointer;display:block;">
           🖼 クリックまたはドラッグで画像をアップロード<br>
           <small style="color:#ccc;margin-top:6px;display:block;">JPG / PNG / GIF / WEBP</small>
         </label>
       </div>`;

  document.getElementById('editor-body').innerHTML = `
    <div class="editor-form">
      <div class="form-group">
        <label class="form-label">ページタイトル</label>
        <input type="text" class="form-input" id="ed-title" value="${escHtml(p.title)}" placeholder="例：ブログ記事の作成方法">
      </div>
      <div class="form-group">
        <label class="form-label">説明・内容</label>
        <textarea class="form-textarea" id="ed-content" oninput="livePreview()" placeholder="このページで説明する内容を入力してください...">${escHtml(p.content)}</textarea>
      </div>
      <div class="form-group">
        <label class="form-label">画像（スクリーンショットなど）</label>
        <div id="img-area">${imgHtml}</div>
      </div>
    </div>`;

  document.getElementById('update-note').value = '';
  // タイトル変更時もライブプレビュー更新
  document.getElementById('ed-title')?.addEventListener('input', livePreview);
}

// ─── ライブプレビュー更新 ───
function livePreview() {
  const p = pages.find(x => x.id === currentId);
  if (!p) return;
  p._draftTitle   = document.getElementById('ed-title')?.value   || p.title;
  p._draftContent = document.getElementById('ed-content')?.value || p.content;
  renderMiniPreview();
}

// ─── 右パネル：ミニプレビュー ───
function renderMiniPreview() {
  const el = document.getElementById('mini-preview');
  if (pages.length === 0) {
    el.innerHTML = '<div class="preview-empty">ページを追加すると<br>ここにプレビューが表示されます</div>';
    return;
  }
  el.innerHTML = pages.map((p, i) => {
    const title   = p._draftTitle   || p.title;
    const content = p._draftContent || p.content;
    const preview = content.replace(/</g,'&lt;').substring(0, 80) + (content.length > 80 ? '…' : '');
    const isCurrent = p.id === currentId;
    return `<div class="preview-page ${isCurrent ? 'current' : ''}" onclick="selectPage(${p.id})" style="cursor:pointer">
      <div class="preview-page-header">
        <span class="preview-page-num">${i+1}</span>
        <span class="preview-page-title">${escHtml(title)}</span>
      </div>
      <div class="preview-page-body">
        ${preview ? escHtml(preview) : '<span style="color:#ccc">（内容なし）</span>'}
        ${p.image_path ? '<br><img src="' + p.image_path + '" style="max-width:100%;border-radius:4px;margin-top:6px;">' : ''}
      </div>
    </div>`;
  }).join('');
}

// ─── 完成形プレビュー（フル） ───
function toggleFullPreview() {
  isFullPreview = !isFullPreview;
  document.getElementById('workspace').style.display    = isFullPreview ? 'none' : 'flex';
  document.getElementById('full-preview').style.display = isFullPreview ? 'block' : 'none';
  const btn = document.getElementById('btn-preview-full');
  if (isFullPreview) {
    btn.textContent = '← 編集に戻る'; btn.style.background = 'rgba(233,69,96,.3)';
    renderFullPreview();
  } else {
    btn.textContent = '👁 完成形を見る'; btn.style.background = '';
  }
}

function renderFullPreview() {
  const tocItems = pages.map((p, i) =>
    `<div class="doc-toc-item"><span class="doc-toc-num">${i+1}</span>${escHtml(p.title)}</div>`).join('');
  const docPages = pages.map((p, i) => `
    <div class="doc-page">
      <div class="doc-page-num-label">PAGE ${i+1}</div>
      <div class="doc-page-title">${escHtml(p.title)}</div>
      <div class="doc-page-content">${escHtml(p.content)}</div>
      ${p.image_path ? `<div class="doc-page-img"><img src="${p.image_path}"></div>` : ''}
    </div>`).join('');

  document.getElementById('doc-paper').innerHTML = `
    <div class="doc-cover">
      <h2>📘 AIブログマスター<br>仕様説明書</h2>
      <p>最終更新：${new Date().toLocaleDateString('ja-JP')} ／ 全 ${pages.length} ページ</p>
    </div>
    <div class="doc-toc">
      <h3>目次</h3>
      ${tocItems || '<div style="color:#ccc;font-size:.85rem;">ページがありません</div>'}
    </div>
    <div class="doc-pages">
      ${docPages || '<div style="text-align:center;padding:40px;color:#ccc;">ページがありません</div>'}
    </div>`;
}

// ─── 更新履歴タブ ───
function renderHistoryTab() {
  const body = document.getElementById('editor-body');
  const filtered = currentId ? history.filter(h => h.section_id === currentId) : history;
  const rows = filtered.length
    ? filtered.map(h => {
        const type = h.action === 'add' ? 'add' : (h.action === 'delete' ? 'delete' : 'update');
        const label = h.action === 'add' ? '追加' : (h.action === 'delete' ? '削除' : '更新');
        return `<tr>
          <td>${h.updated_at}</td>
          <td>${escHtml(h.page_title || '')}</td>
          <td><span class="history-badge ${type}">${label}</span></td>
          <td>${escHtml(h.note || '')}</td>
        </tr>`;
      }).join('')
    : '<tr><td colspan="4" style="text-align:center;color:#ccc;padding:20px;">履歴がありません</td></tr>';

  body.innerHTML = `
    <div class="history-section">
      <h3>${currentId ? '選択ページの更新履歴' : '全ページ更新履歴'}</h3>
      <table class="history-table">
        <thead><tr><th>日時</th><th>ページ</th><th>種別</th><th>メモ</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

// ─── タブ切替 ───
function switchTab(tab) {
  currentTab = tab;
  document.getElementById('tab-edit').classList.toggle('active', tab === 'edit');
  document.getElementById('tab-history').classList.toggle('active', tab === 'history');
  if (tab === 'edit') { renderEditor(); document.getElementById('editor-actions').style.display = currentId ? 'flex' : 'none'; }
  else { renderHistoryTab(); document.getElementById('editor-actions').style.display = 'none'; }
}

// ─── ページ追加 ───
async function addPage() {
  const res = await api('add', { title: '新しいページ', content: '', image_path: '' });
  if (res.success) {
    pages.push(res.data);
    history.unshift({ section_id: res.data.id, page_title: res.data.title, action: 'add', note: '', updated_at: new Date().toLocaleString('ja-JP') });
    currentId = res.data.id;
    renderSidebar(); renderMiniPreview();
    switchTab('edit');
    document.getElementById('editor-actions').style.display = 'flex';
    setTimeout(() => document.getElementById('ed-title')?.focus(), 50);
    toast('新しいページを追加しました', 'success');
  }
}

// ─── ページ保存 ───
async function savePage() {
  if (!currentId) return;
  const title   = document.getElementById('ed-title')?.value   || '';
  const content = document.getElementById('ed-content')?.value || '';
  const note    = document.getElementById('update-note')?.value || '';
  const p = pages.find(x => x.id === currentId);
  const image_path = p?.image_path || '';

  const res = await api('update', { id: currentId, title, content, image_path, note });
  if (res.success) {
    if (p) { p.title = title; p.content = content; delete p._draftTitle; delete p._draftContent; }
    history.unshift({ section_id: currentId, page_title: title, action: 'update', note, updated_at: new Date().toLocaleString('ja-JP') });
    renderSidebar(); renderMiniPreview();
    document.getElementById('update-note').value = '';
    toast('保存しました ✓', 'success');
  }
}

// ─── ページ削除 ───
async function deletePage() {
  if (!currentId) return;
  const p = pages.find(x => x.id === currentId);
  if (!confirm(`「${p?.title}」を削除しますか？\nこの操作は元に戻せません。`)) return;
  const res = await api('delete', { id: currentId, note: '削除' });
  if (res.success) {
    history.unshift({ section_id: currentId, page_title: p?.title, action: 'delete', note: '', updated_at: new Date().toLocaleString('ja-JP') });
    pages = pages.filter(x => x.id !== currentId);
    currentId = pages[0]?.id || null;
    renderSidebar(); renderMiniPreview();
    if (currentId) { selectPage(currentId); }
    else { document.getElementById('editor-body').innerHTML = '<div class="empty-state"><div class="icon">📝</div><p>ページを選択するか「＋ 追加」から作成してください。</p></div>'; document.getElementById('editor-actions').style.display = 'none'; }
    toast('削除しました', 'error');
  }
}

// ─── 画像アップロード ───
async function uploadImage(input) {
  const file = input.files[0]; if (!file) return;
  const form = new FormData(); form.append('image', file);
  const res = await api('upload_image', form, true);
  if (res.success) { applyImage(res.path); }
  else { toast('アップロード失敗: ' + res.error, 'error'); }
}
async function handleImgDrop(e) {
  e.preventDefault();
  document.getElementById('drop-area')?.classList.remove('dragover');
  const file = e.dataTransfer.files[0];
  if (!file || !file.type.startsWith('image/')) return;
  const form = new FormData(); form.append('image', file);
  const res = await api('upload_image', form, true);
  if (res.success) { applyImage(res.path); }
}
function applyImage(path) {
  const p = pages.find(x => x.id === currentId);
  if (p) p.image_path = path;
  document.getElementById('img-area').innerHTML =
    `<div class="img-scroll-wrap"><img src="${path}" class="preview-img"></div>
     <button class="btn-remove-img" onclick="removeImage()">✕ 画像を削除</button>`;
  renderMiniPreview();
  toast('画像をアップロードしました ✓', 'success');
}
async function removeImage() {
  if (!confirm('画像を削除しますか？')) return;
  const p = pages.find(x => x.id === currentId);
  if (p) p.image_path = '';
  document.getElementById('img-area').innerHTML =
    `<div class="img-drop-area" id="drop-area"
        ondragover="event.preventDefault();this.classList.add('dragover')"
        ondragleave="this.classList.remove('dragover')"
        ondrop="handleImgDrop(event)">
       <input type="file" accept="image/*" id="img-file" onchange="uploadImage(this)">
       <label for="img-file" style="cursor:pointer;display:block;">
         🖼 クリックまたはドラッグで画像をアップロード<br>
         <small style="color:#ccc;margin-top:6px;display:block;">JPG / PNG / GIF / WEBP</small>
       </label>
     </div>`;
  renderMiniPreview();
}

// ─── PowerPoint出力 ───
function exportPPTX() {
  toast('PowerPointを生成中...');
  window.location.href = 'export_pptx.php';
}

// ─── ユーティリティ ───
function escHtml(s) {
  return (s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

init();
</script>
</body>
</html>
