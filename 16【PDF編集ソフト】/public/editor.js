// ═══════════════════════════════════════════════════
//  PDF Editor — editor.js
// ═══════════════════════════════════════════════════

pdfjsLib.GlobalWorkerOptions.workerSrc =
  'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

// ── State ──────────────────────────────────────────
let pdfDoc       = null;
let currentPage  = 1;
let totalPages   = 0;
let renderScale  = 1.5;
let fabricCanvas = null;
let pageStates   = {};   // { "1": fabricJSON, ... }
let sourcePdfFile = '';  // server filename
let srcOrigName   = '';
let myCompany     = {};
let allTemplates  = [];
let selectedTool  = 'select';
let textColor     = '#000000';
let shapeColor    = '#000000';
let pendingExportBlob = null;
let pendingExportFilename = '';
let textPlacementMode  = false;  // テキスト配置モード
let imagePlacementMode = false;  // 画像配置モード
let pendingImageSrc    = '';     // 配置待ち画像URL
let autosaveTimer = null;

// ── Init ──────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  setupUploadZone();
  initFabricCanvas();
  loadLibraryImages();
  loadCompanyInfo();
  loadTemplates();
  loadClients();
  checkForDraft();

  // Escキーで配置モードキャンセル
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (textPlacementMode)  cancelTextPlacement();
      if (imagePlacementMode) cancelImagePlacement();
    }
  });

  // ページ離脱・タブ閉じ時に即時保存
  window.addEventListener('beforeunload', () => {
    if (sourcePdfFile) saveDraft();
  });

  // サイドバーのナビリンクをクリック時にも即時保存してから遷移
  document.querySelectorAll('.nav-item').forEach(link => {
    link.addEventListener('click', (e) => {
      if (!sourcePdfFile) return; // 編集中でなければそのまま
      e.preventDefault();
      saveCurrentState();
      saveDraft();
      window.location.href = link.href;
    });
  });
});

// ── Upload zone ───────────────────────────────────
function setupUploadZone() {
  const zone  = document.getElementById('drop-zone');
  const input = document.getElementById('file-input');

  zone.addEventListener('click', () => input.click());
  input.addEventListener('change', (e) => {
    if (e.target.files[0]) handleFile(e.target.files[0]);
  });

  zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', (e) => {
    e.preventDefault(); zone.classList.remove('drag-over');
    const f = e.dataTransfer.files[0];
    if (f && (f.type === 'application/pdf' || f.name.endsWith('.pdf'))) handleFile(f);
    else alert('PDFファイルを選択してください');
  });
}

async function handleFile(file) {
  showLoading('PDFをアップロード中...');
  try {
    const fd = new FormData();
    fd.append('file', file);
    const res  = await fetch('/api/editor/upload', { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Upload failed');
    sourcePdfFile = data.file_name;
    srcOrigName   = data.original_name;
    document.getElementById('doc-title').value = file.name.replace(/\.pdf$/i, '');

    const arrayBuffer = await file.arrayBuffer();
    pdfDoc      = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
    totalPages  = pdfDoc.numPages;
    currentPage = 1;
    pageStates  = {};

    updatePageNav();
    await renderPage(currentPage);
    showEditor();
  } catch (err) {
    alert('エラー: ' + err.message);
  } finally {
    hideLoading();
  }
}

// ── Fabric canvas ─────────────────────────────────
function initFabricCanvas() {
  // Canvaスタイルのデフォルトハンドル設定
  fabric.Object.prototype.set({
    borderColor:        '#18a0fb',
    borderScaleFactor:  2,
    cornerColor:        '#ffffff',
    cornerStrokeColor:  '#18a0fb',
    cornerSize:         10,
    cornerStyle:        'circle',
    transparentCorners: false,
    padding:            4,
  });

  fabricCanvas = new fabric.Canvas('pdf-canvas', {
    preserveObjectStacking:  true,
    selection:               true,
    hoverCursor:             'grab',
    moveCursor:              'grabbing',
    selectionColor:          'rgba(24,160,251,0.08)',
    selectionBorderColor:    '#18a0fb',
    selectionLineWidth:      1.5,
  });

  fabricCanvas.on('selection:created',  () => { updatePropsPanel(); updateFloatingControls(); });
  fabricCanvas.on('selection:updated',  () => { updatePropsPanel(); updateFloatingControls(); });
  fabricCanvas.on('selection:cleared',  () => { clearPropsPanel(); hideFloatingControls(); });
  fabricCanvas.on('object:modified',    () => { saveCurrentState(); updateFloatingControls(); });
  fabricCanvas.on('object:moving',      updateFloatingControls);
  fabricCanvas.on('object:scaling',     updateFloatingControls);

  // 配置モード: キャンバスクリックで配置
  fabricCanvas.on('mouse:down', (opt) => {
    const pointer = fabricCanvas.getPointer(opt.e);
    if (textPlacementMode) {
      placeTextAt(pointer.x, pointer.y);
      cancelTextPlacement();
    } else if (imagePlacementMode) {
      placeImageAt(pointer.x, pointer.y, pendingImageSrc);
      cancelImagePlacement();
    }
  });

  // テキスト編集終了: editable を false に戻す
  fabricCanvas.on('text:editing:exited', (opt) => {
    opt.target.set('editable', false);
    saveCurrentState();
    updateFloatingControls();
  });
}

// ── Render a PDF page ─────────────────────────────
async function renderPage(pageNum) {
  showLoading('ページを読み込み中...');
  try {
    const page     = await pdfDoc.getPage(pageNum);
    const viewport = page.getViewport({ scale: renderScale });
    const W = Math.round(viewport.width);
    const H = Math.round(viewport.height);

    fabricCanvas.setWidth(W);
    fabricCanvas.setHeight(H);
    document.getElementById('canvas-wrapper').style.width  = W + 'px';
    document.getElementById('canvas-wrapper').style.height = H + 'px';

    const tmp = document.createElement('canvas');
    tmp.width  = W;
    tmp.height = H;
    await page.render({ canvasContext: tmp.getContext('2d'), viewport }).promise;
    const bgDataUrl = tmp.toDataURL('image/png');

    await new Promise((resolve) => {
      fabricCanvas.setBackgroundImage(bgDataUrl, () => {
        fabricCanvas.renderAll();
        resolve();
      }, { scaleX: 1, scaleY: 1, originX: 'left', originY: 'top' });
    });

    if (pageStates[pageNum] && pageStates[pageNum].objects && pageStates[pageNum].objects.length > 0) {
      await new Promise((resolve) => {
        fabricCanvas.loadFromJSON(pageStates[pageNum], () => {
          fabricCanvas.setBackgroundImage(bgDataUrl, () => {
            fabricCanvas.renderAll();
            resolve();
          }, { scaleX: 1, scaleY: 1, originX: 'left', originY: 'top' });
        });
      });
      // ロード後にeditable=falseを確保
      fabricCanvas.getObjects().forEach(o => {
        if (o.type === 'i-text') o.set('editable', false);
      });
      fabricCanvas.renderAll();
    } else {
      fabricCanvas.getObjects().slice().forEach(o => fabricCanvas.remove(o));
      fabricCanvas.renderAll();
    }
    hideFloatingControls();
  } finally {
    hideLoading();
  }
}

// ── Save current page objects ─────────────────────
function saveCurrentState() {
  if (!fabricCanvas) return;
  const json = fabricCanvas.toJSON();
  delete json.backgroundImage;
  pageStates[currentPage] = json;
  scheduleDraftSave();
}

// ── Page navigation ───────────────────────────────
async function changePage(delta) {
  const next = currentPage + delta;
  if (next < 1 || next > totalPages) return;
  saveCurrentState();
  currentPage = next;
  updatePageNav();
  await renderPage(currentPage);
}

function updatePageNav() {
  document.getElementById('page-info').textContent = `${currentPage} / ${totalPages}`;
  document.getElementById('prev-btn').disabled = currentPage <= 1;
  document.getElementById('next-btn').disabled = currentPage >= totalPages;
}

// ── Show / hide screens ───────────────────────────
function showEditor() {
  document.getElementById('upload-screen').style.display = 'none';
  document.getElementById('editor-layout').classList.add('visible');
}

function showLoading(msg) {
  document.getElementById('loading-msg').textContent = msg || '処理中...';
  document.getElementById('loading').classList.add('show');
}
function hideLoading() {
  document.getElementById('loading').classList.remove('show');
}

// ── Panel tabs ────────────────────────────────────
function switchTab(tab) {
  document.querySelectorAll('.panel-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
  document.querySelectorAll('.panel-section').forEach(s => s.classList.toggle('active', s.id === 'panel-' + tab));
}

// ── Tools ─────────────────────────────────────────
function setTool(tool) {
  selectedTool = tool;
  document.querySelectorAll('.tool-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tool-' + tool)?.classList.add('active');
}

// ── ADD IMAGE ────────────────────────────────────
function addImageDirect(event) {
  const file = event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (e) => placeImage(e.target.result);
  reader.readAsDataURL(file);
  event.target.value = '';
}

function addImageFromLibrary(fileName) {
  placeImage(`/api/images/file/${fileName}`);
}

// 画像配置モードに入る
function placeImage(src) {
  if (!fabricCanvas) return;
  if (!sourcePdfFile && !pdfDoc) { alert('先にPDFを開いてください'); return; }
  pendingImageSrc    = src;
  imagePlacementMode = true;
  fabricCanvas.defaultCursor = 'crosshair';
  fabricCanvas.hoverCursor   = 'crosshair';
  showPlacementHint('クリックして画像を配置　[Esc] でキャンセル');
}

// 画像配置モードキャンセル
function cancelImagePlacement() {
  imagePlacementMode = false;
  pendingImageSrc    = '';
  fabricCanvas.defaultCursor = 'default';
  fabricCanvas.hoverCursor   = 'grab';
  hidePlacementHint();
}

// 指定座標に画像を配置
function placeImageAt(x, y, src) {
  fabric.Image.fromURL(src, (img) => {
    const maxW  = fabricCanvas.width  * 0.4;
    const maxH  = fabricCanvas.height * 0.4;
    const scale = Math.min(1, maxW / img.width, maxH / img.height);
    img.set({
      left:    x,
      top:     y,
      originX: 'center',
      originY: 'center',
      scaleX:  scale,
      scaleY:  scale,
    });
    img.setCoords();
    fabricCanvas.add(img);
    fabricCanvas.setActiveObject(img);
    fabricCanvas.renderAll();
    saveCurrentState();
  }, { crossOrigin: 'anonymous' });
}

// ── ADD TEXT ──────────────────────────────────────
// 「テキストを追加」ボタン押下 → 配置モードへ
function addText(content) {
  // 定型文・自社情報から呼ばれた場合はすぐ配置モードへ
  if (content) {
    document.getElementById('text-input').value = content;
    switchTab('text');
  }
  if (!fabricCanvas) return;
  if (!sourcePdfFile && !pdfDoc) {
    alert('先にPDFを開いてください');
    return;
  }

  // 配置モード開始
  textPlacementMode = true;
  fabricCanvas.defaultCursor = 'crosshair';
  fabricCanvas.hoverCursor   = 'crosshair';
  showPlacementHint('クリックしてテキストを配置　[Esc] でキャンセル');
}

// テキスト配置モードキャンセル
function cancelTextPlacement() {
  textPlacementMode = false;
  fabricCanvas.defaultCursor = 'default';
  fabricCanvas.hoverCursor   = 'grab';
  hidePlacementHint();
}

// ── 配置ヒント共通 ────────────────────────────────
function showPlacementHint(msg) {
  const hint = document.getElementById('placement-hint');
  if (!hint) return;
  hint.textContent  = msg;
  hint.style.display = 'block';
}
function hidePlacementHint() {
  const hint = document.getElementById('placement-hint');
  if (hint) hint.style.display = 'none';
}

// 指定座標にテキストを配置
function placeTextAt(x, y) {
  const text  = document.getElementById('text-input').value || 'テキスト';
  const size  = parseInt(document.getElementById('text-size')?.value || 16);
  const bold  = document.getElementById('text-bold')?.checked;
  const color = textColor;

  const obj = new fabric.IText(text, {
    left:    x,
    top:     y,
    originX: 'center',
    originY: 'center',
    fontFamily: '"Noto Sans JP", "Hiragino Sans", "Meiryo", sans-serif',
    fontSize:   size,
    fontWeight: bold ? 'bold' : 'normal',
    fill:       color,
    editable:   false,   // 鉛筆ボタンを押すまで編集不可
  });

  fabricCanvas.add(obj);
  fabricCanvas.setActiveObject(obj);
  fabricCanvas.renderAll();
  saveCurrentState();
}

function selectColor(el) {
  document.querySelectorAll('.color-swatches .color-swatch').forEach(s => s.classList.remove('active'));
  el.classList.add('active');
  textColor = el.dataset.color;
}

function selectShapeColor(el) {
  document.querySelectorAll('#shape-color-swatches .color-swatch').forEach(s => s.classList.remove('active'));
  el.classList.add('active');
  shapeColor = el.dataset.color;
}

// ── テキスト編集モード（鉛筆ボタン）────────────────
function enterTextEdit() {
  const obj = fabricCanvas.getActiveObject();
  if (!obj || obj.type !== 'i-text') return;
  obj.set('editable', true);
  fabricCanvas.setActiveObject(obj);
  obj.enterEditing();
  obj.selectAll();
  fabricCanvas.renderAll();
  hideFloatingControls();
}

// ── ADD SHAPES ────────────────────────────────────
function addRect() {
  const rect = new fabric.Rect({
    left: 50, top: 50, width: 120, height: 60,
    fill: 'transparent', stroke: shapeColor, strokeWidth: 2,
  });
  fabricCanvas.add(rect);
  fabricCanvas.setActiveObject(rect);
  fabricCanvas.renderAll();
  saveCurrentState();
}

function addLine() {
  const line = new fabric.Line([50, 100, 250, 100], {
    stroke: shapeColor, strokeWidth: 2,
  });
  fabricCanvas.add(line);
  fabricCanvas.setActiveObject(line);
  fabricCanvas.renderAll();
  saveCurrentState();
}

// ── Floating controls (鉛筆 + 削除ボタン) ─────────
function updateFloatingControls() {
  const obj = fabricCanvas.getActiveObject();
  const ctrl = document.getElementById('object-controls');
  if (!ctrl) return;

  if (!obj || fabricCanvas.getActiveObjects().length > 1) {
    hideFloatingControls();
    return;
  }

  const bound = obj.getBoundingRect(true);
  const canvasEl = document.getElementById('pdf-canvas');
  // Fabricのlower-canvas座標系がcanvas-wrapperの左上を基準にしている
  const x = bound.left + bound.width / 2;
  const y = Math.max(0, bound.top - 8);

  ctrl.style.display = 'flex';
  ctrl.style.left    = x + 'px';
  ctrl.style.top     = y + 'px';

  // テキスト以外は鉛筆ボタンを非表示
  const pencilBtn = document.getElementById('ctrl-pencil');
  if (pencilBtn) {
    pencilBtn.style.display = (obj.type === 'i-text') ? 'flex' : 'none';
  }
}

function hideFloatingControls() {
  const ctrl = document.getElementById('object-controls');
  if (ctrl) ctrl.style.display = 'none';
}

// ── Properties panel ──────────────────────────────
function updatePropsPanel() {
  const obj = fabricCanvas.getActiveObject();
  if (!obj) return;
  document.getElementById('no-selection').style.display = 'none';
  document.getElementById('object-props').style.display = 'block';

  document.getElementById('prop-x').value     = Math.round(obj.left);
  document.getElementById('prop-y').value     = Math.round(obj.top);
  document.getElementById('prop-w').value     = Math.round(obj.getScaledWidth());
  document.getElementById('prop-h').value     = Math.round(obj.getScaledHeight());
  document.getElementById('prop-angle').value = Math.round(obj.angle || 0);
  const op = Math.round((obj.opacity || 1) * 100);
  document.getElementById('prop-opacity').value = op;
  document.getElementById('prop-opacity-val').textContent = op + '%';

  // テキストの場合: フォントサイズ欄を表示
  const fsRow = document.getElementById('prop-fontsize-row');
  if (fsRow) {
    if (obj.type === 'i-text' || obj.type === 'text') {
      fsRow.style.display = 'flex';
      document.getElementById('prop-fontsize').value = Math.round(obj.fontSize || 16);
    } else {
      fsRow.style.display = 'none';
    }
  }
}

function clearPropsPanel() {
  document.getElementById('no-selection').style.display = 'block';
  document.getElementById('object-props').style.display = 'none';
  const fsRow = document.getElementById('prop-fontsize-row');
  if (fsRow) fsRow.style.display = 'none';
}

function updateObjProp(prop, val) {
  const obj = fabricCanvas.getActiveObject();
  if (!obj) return;
  obj.set(prop, parseFloat(val));
  obj.setCoords();
  fabricCanvas.renderAll();
  saveCurrentState();
}

function updateTextFontSize(val) {
  const obj = fabricCanvas.getActiveObject();
  if (!obj || (obj.type !== 'i-text' && obj.type !== 'text')) return;
  obj.set('fontSize', parseInt(val));
  obj.setCoords();
  fabricCanvas.renderAll();
  saveCurrentState();
  updateFloatingControls();
}

function getActiveObjOrigW() {
  const obj = fabricCanvas.getActiveObject();
  return obj ? (obj.width || 1) : 1;
}
function getActiveObjOrigH() {
  const obj = fabricCanvas.getActiveObject();
  return obj ? (obj.height || 1) : 1;
}

function deleteSelected() {
  const obj = fabricCanvas.getActiveObject();
  if (!obj) return;
  if (obj.type === 'activeSelection') {
    obj.getObjects().forEach(o => fabricCanvas.remove(o));
  } else {
    fabricCanvas.remove(obj);
  }
  fabricCanvas.discardActiveObject();
  fabricCanvas.renderAll();
  saveCurrentState();
  clearPropsPanel();
  hideFloatingControls();
}

// ── Auto-save draft (localStorage) ───────────────
function scheduleDraftSave() {
  clearTimeout(autosaveTimer);
  autosaveTimer = setTimeout(saveDraft, 2000);
}

function saveDraft() {
  if (!sourcePdfFile) return;
  try {
    const draft = {
      sourcePdfFile,
      srcOrigName,
      pageStates,
      currentPage,
      totalPages,
      title: document.getElementById('doc-title')?.value || '',
      savedAt: new Date().toISOString(),
    };
    localStorage.setItem('pdf_editor_draft', JSON.stringify(draft));
    showDraftIndicator();
  } catch (e) {
    console.warn('Draft save failed:', e);
  }
}

function showDraftIndicator() {
  const el = document.getElementById('draft-indicator');
  if (!el) return;
  el.textContent = '自動保存済み ' + new Date().toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' });
  el.style.opacity = '1';
  setTimeout(() => { el.style.opacity = '0'; }, 3000);
}

function checkForDraft() {
  try {
    const raw = localStorage.getItem('pdf_editor_draft');
    if (!raw) return;
    const draft = JSON.parse(raw);
    if (!draft.sourcePdfFile) return;

    const banner = document.getElementById('draft-banner');
    const timeEl = document.getElementById('draft-time');
    if (!banner) return;

    const savedAt = new Date(draft.savedAt);
    const now = new Date();
    const diffH = (now - savedAt) / 3600000;
    if (diffH > 48) { localStorage.removeItem('pdf_editor_draft'); return; } // 48時間超は破棄

    if (timeEl) timeEl.textContent = savedAt.toLocaleString('ja-JP');
    banner.style.display = 'flex';
  } catch {}
}

async function restoreDraft() {
  try {
    const raw = localStorage.getItem('pdf_editor_draft');
    if (!raw) return;
    const draft = JSON.parse(raw);

    document.getElementById('draft-banner').style.display = 'none';
    showLoading('前回のデータを復元中...');

    // PDFをサーバーから取得
    const res = await fetch(`/api/editor/file/${draft.sourcePdfFile}`);
    if (!res.ok) throw new Error('PDFファイルが見つかりません（サーバー上のファイルが削除された可能性があります）');

    const arrayBuffer = await res.arrayBuffer();
    pdfDoc        = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
    sourcePdfFile = draft.sourcePdfFile;
    srcOrigName   = draft.srcOrigName || '';
    pageStates    = draft.pageStates || {};
    totalPages    = draft.totalPages || pdfDoc.numPages;
    currentPage   = draft.currentPage || 1;

    if (draft.title) document.getElementById('doc-title').value = draft.title;

    updatePageNav();
    await renderPage(currentPage);
    showEditor();
  } catch (err) {
    alert('復元エラー: ' + err.message);
  } finally {
    hideLoading();
  }
}

function discardDraft() {
  localStorage.removeItem('pdf_editor_draft');
  document.getElementById('draft-banner').style.display = 'none';
}

// ── Export ────────────────────────────────────────
async function buildExportPayload() {
  saveCurrentState();
  const pages = [];

  for (let pn = 1; pn <= totalPages; pn++) {
    const state = pageStates[pn];
    if (!state || !state.objects || state.objects.length === 0) {
      pages.push({ page_num: pn, overlay: null });
      continue;
    }

    const page     = await pdfDoc.getPage(pn);
    const viewport = page.getViewport({ scale: renderScale });
    const W = Math.round(viewport.width);
    const H = Math.round(viewport.height);

    const overlay = await new Promise((resolve) => {
      const offscreen = new fabric.StaticCanvas(null, { width: W, height: H });
      offscreen.loadFromJSON(state, () => {
        offscreen.setBackgroundImage(null, () => {
          offscreen.backgroundColor = 'rgba(0,0,0,0)';
          offscreen.renderAll();
          resolve(offscreen.toDataURL({ format: 'png' }));
          offscreen.dispose();
        });
      });
    });

    pages.push({ page_num: pn, overlay });
  }

  return pages;
}

async function downloadPdf() {
  showLoading('PDFを生成中...');
  try {
    const pages = await buildExportPayload();
    const title = document.getElementById('doc-title').value || 'edited';
    const res = await fetch('/api/editor/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_file: sourcePdfFile, pages, title }),
    });
    if (!res.ok) throw new Error('エクスポート失敗');

    pendingExportFilename = res.headers.get('X-Output-Filename') || '';
    const blob = await res.blob();
    pendingExportBlob = blob;

    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = (title || 'edited') + '.pdf';
    a.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    alert('エラー: ' + err.message);
  } finally {
    hideLoading();
  }
}

// ── Archive modal ─────────────────────────────────
function openArchiveModal() {
  const title = document.getElementById('doc-title').value;
  document.getElementById('archive-title').value = title;
  document.getElementById('archive-modal').classList.add('open');
}
function closeArchiveModal() {
  document.getElementById('archive-modal').classList.remove('open');
}

async function saveToArchive() {
  const title    = document.getElementById('archive-title').value.trim();
  const clientId = document.getElementById('archive-client').value;
  const notes    = document.getElementById('archive-notes').value;

  if (!title) { alert('タイトルを入力してください'); return; }

  showLoading('保存中...');
  closeArchiveModal();
  try {
    const pages = await buildExportPayload();
    const res = await fetch('/api/editor/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_file: sourcePdfFile, pages, title }),
    });
    if (!res.ok) throw new Error('エクスポート失敗');

    const outputFilename = res.headers.get('X-Output-Filename') || '';
    const blob = await res.blob();
    const thumbnail = await getPageThumbnail(1);

    const saveRes = await fetch('/api/documents', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title,
        client_id: clientId || null,
        original_file_name: srcOrigName,
        output_file_name: outputFilename,
        thumbnail,
        editor_state: JSON.stringify({ pages: pageStates, source_pdf: sourcePdfFile, page_count: totalPages }),
        notes,
      }),
    });
    if (!saveRes.ok) throw new Error('DB保存失敗');

    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = title + '.pdf'; a.click();
    URL.revokeObjectURL(url);

    // アーカイブ保存後はドラフトを削除
    localStorage.removeItem('pdf_editor_draft');

    alert('✅ アーカイブに保存しました');
  } catch (err) {
    alert('エラー: ' + err.message);
  } finally {
    hideLoading();
  }
}

async function getPageThumbnail(pageNum) {
  try {
    const page     = await pdfDoc.getPage(pageNum);
    const viewport = page.getViewport({ scale: 0.3 });
    const tmp = document.createElement('canvas');
    tmp.width  = Math.round(viewport.width);
    tmp.height = Math.round(viewport.height);
    await page.render({ canvasContext: tmp.getContext('2d'), viewport }).promise;
    return tmp.toDataURL('image/jpeg', 0.6);
  } catch { return ''; }
}

// ── Load library images ───────────────────────────
async function loadLibraryImages() {
  const grid = document.getElementById('lib-images-grid');
  try {
    const res  = await fetch('/api/images');
    const data = await res.json();
    if (!data.length) {
      grid.innerHTML = `<p style="font-size:12px;color:var(--text-muted);grid-column:1/-1"><a href="/images.html" style="color:var(--primary)">ライブラリに画像を追加</a>するとここから選択できます</p>`;
      return;
    }
    grid.innerHTML = data.map(img => `
      <div class="lib-image-item" onclick="addImageFromLibrary('${img.file_name}')" title="${img.name}">
        <img src="/api/images/file/${img.file_name}" alt="${img.name}" crossorigin="anonymous">
        <div class="name">${img.name}</div>
      </div>
    `).join('');
  } catch {
    grid.innerHTML = '<p style="font-size:12px;color:var(--text-muted);grid-column:1/-1">読み込み失敗</p>';
  }
}

// ── Load company info ─────────────────────────────
async function loadCompanyInfo() {
  try {
    const res = await fetch('/api/my-company');
    myCompany  = await res.json();
    renderCompanyFields();
  } catch {}
}

function renderCompanyFields() {
  const fields = document.getElementById('company-fields');
  const items = [
    { label: '会社名',    key: 'company_name' },
    { label: '住所（本社）', key: 'address' },
    { label: '住所（支店）', key: 'branch_address' },
    { label: '電話',         key: 'phone' },
    { label: 'FAX',       key: 'fax' },
    { label: 'メール',    key: 'email' },
    { label: '代表者名',  key: 'representative' },
    { label: '銀行口座',  key: 'bank_info' },
  ];

  const hasData = items.some(i => myCompany[i.key]);
  if (!hasData) {
    fields.innerHTML = `<p style="font-size:12px;color:var(--text-muted)"><a href="/my-company.html" style="color:var(--primary)">自社情報を登録</a>するとここから追加できます</p>`;
    return;
  }

  fields.innerHTML = items
    .filter(i => myCompany[i.key])
    .map(i => `
      <button class="btn btn-ghost btn-sm" style="justify-content:flex-start;text-align:left" onclick="addText('${(myCompany[i.key] || '').replace(/'/g, "\\'")}')">
        <span style="color:var(--text-muted);font-size:10px;min-width:56px">${i.label}</span>
        <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${myCompany[i.key]}</span>
      </button>
    `).join('');

  if (myCompany.logo_path) {
    fields.innerHTML += `
      <button class="btn btn-outline btn-sm" style="justify-content:center" onclick="placeImage('/api/my-company/logo/${myCompany.logo_path}')">
        ロゴを追加
      </button>`;
  }
}

// ── Load & render templates ───────────────────────
async function loadTemplates() {
  try {
    const res  = await fetch('/api/templates');
    const data = await res.json();
    allTemplates = [
      ...data.company_items,
      ...data.templates,
    ];
    renderTemplateList();
  } catch {}
}

function renderTemplateList() {
  const q    = (document.getElementById('tmpl-search')?.value || '').toLowerCase();
  const list = allTemplates.filter(t =>
    !q ||
    t.title.toLowerCase().includes(q) ||
    t.content.toLowerCase().includes(q) ||
    (t.category || '').toLowerCase().includes(q) ||
    (t.yomigana || '').includes(q)
  );

  const container = document.getElementById('template-list');
  if (!list.length) {
    container.innerHTML = q
      ? `<p style="font-size:12px;color:var(--text-muted)">見つかりません</p>`
      : `<p style="font-size:12px;color:var(--text-muted)"><a href="/templates.html" target="_blank" style="color:var(--primary)">定型文を登録</a>するとここに表示されます</p>`;
    return;
  }

  const groups = {};
  list.forEach(t => {
    const cat = t.category || '一般';
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(t);
  });

  container.innerHTML = Object.entries(groups).map(([cat, items]) => `
    <div style="margin-bottom:8px">
      <div style="font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.06em;padding:4px 0 6px">${cat}</div>
      ${items.map(t => `
        <button class="tmpl-item" onclick="insertTemplate(${JSON.stringify(t.content).replace(/"/g,'&quot;')})"
          title="${t.content.replace(/"/g,'&quot;')}"
          style="width:100%;text-align:left;background:#f8fafc;border:1px solid var(--border);border-radius:5px;padding:7px 10px;margin-bottom:4px;cursor:pointer;transition:all .12s;font-size:12px;font-family:inherit">
          <div style="font-weight:600;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${t.title}</div>
          <div style="color:var(--text-muted);font-size:11px;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${t.content}</div>
        </button>
      `).join('')}
    </div>
  `).join('');

  container.querySelectorAll('.tmpl-item').forEach(el => {
    el.addEventListener('mouseenter', () => { el.style.background = 'var(--primary-light)'; el.style.borderColor = 'var(--primary)'; });
    el.addEventListener('mouseleave', () => { el.style.background = '#f8fafc'; el.style.borderColor = 'var(--border)'; });
  });
}

function insertTemplate(content) {
  const textInput = document.getElementById('text-input');
  if (textInput) textInput.value = content;
  addText(content);
  switchTab('text');
}

// ── Load clients for archive modal ───────────────
async function loadClients() {
  try {
    const res     = await fetch('/api/clients');
    const clients = await res.json();
    const sel = document.getElementById('archive-client');
    sel.innerHTML = '<option value="">— 紐付けなし —</option>' +
      clients.map(c => `<option value="${c.id}">${c.company_name}</option>`).join('');
  } catch {}
}
