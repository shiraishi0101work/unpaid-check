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
let allTemplates  = [];   // { id, title, content, category }
let selectedTool  = 'select';
let textColor     = '#000000';
let shapeColor    = '#000000';
let pendingExportBlob = null;
let pendingExportFilename = '';

// ── Init ──────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  setupUploadZone();
  initFabricCanvas();
  loadLibraryImages();
  loadCompanyInfo();
  loadClients();
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

    // Load with PDF.js
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
  fabricCanvas = new fabric.Canvas('pdf-canvas', {
    preserveObjectStacking: true,
    selection: true,
  });
  fabricCanvas.on('selection:created',  updatePropsPanel);
  fabricCanvas.on('selection:updated',  updatePropsPanel);
  fabricCanvas.on('selection:cleared',  clearPropsPanel);
  fabricCanvas.on('object:modified',    () => saveCurrentState());
}

// ── Render a PDF page ─────────────────────────────
async function renderPage(pageNum) {
  showLoading('ページを読み込み中...');
  try {
    const page     = await pdfDoc.getPage(pageNum);
    const viewport = page.getViewport({ scale: renderScale });
    const W = Math.round(viewport.width);
    const H = Math.round(viewport.height);

    // Resize Fabric canvas
    fabricCanvas.setWidth(W);
    fabricCanvas.setHeight(H);
    document.getElementById('canvas-wrapper').style.width  = W + 'px';
    document.getElementById('canvas-wrapper').style.height = H + 'px';

    // Render PDF page to temp canvas
    const tmp = document.createElement('canvas');
    tmp.width  = W;
    tmp.height = H;
    await page.render({ canvasContext: tmp.getContext('2d'), viewport }).promise;
    const bgDataUrl = tmp.toDataURL('image/png');

    // Set as Fabric background
    await new Promise((resolve) => {
      fabricCanvas.setBackgroundImage(bgDataUrl, () => {
        fabricCanvas.renderAll();
        resolve();
      }, { scaleX: 1, scaleY: 1, originX: 'left', originY: 'top' });
    });

    // Restore saved objects for this page
    if (pageStates[pageNum] && pageStates[pageNum].objects && pageStates[pageNum].objects.length > 0) {
      await new Promise((resolve) => {
        fabricCanvas.loadFromJSON(pageStates[pageNum], () => {
          // Re-apply background (loadFromJSON may overwrite it)
          fabricCanvas.setBackgroundImage(bgDataUrl, () => {
            fabricCanvas.renderAll();
            resolve();
          }, { scaleX: 1, scaleY: 1, originX: 'left', originY: 'top' });
        });
      });
    } else {
      fabricCanvas.getObjects().slice().forEach(o => fabricCanvas.remove(o));
      fabricCanvas.renderAll();
    }
  } finally {
    hideLoading();
  }
}

// ── Save current page objects ─────────────────────
function saveCurrentState() {
  if (!fabricCanvas) return;
  const json = fabricCanvas.toJSON();
  delete json.backgroundImage; // don't store background (it's re-generated per page)
  pageStates[currentPage] = json;
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

// ── ADD IMAGE (direct from device) ───────────────
function addImageDirect(event) {
  const file = event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (e) => placeImage(e.target.result);
  reader.readAsDataURL(file);
  event.target.value = '';
}

// Add from library
function addImageFromLibrary(fileName) {
  placeImage(`/api/images/file/${fileName}`);
}

function placeImage(src) {
  fabric.Image.fromURL(src, (img) => {
    const maxW = fabricCanvas.width  * 0.4;
    const maxH = fabricCanvas.height * 0.4;
    const scale = Math.min(1, maxW / img.width, maxH / img.height);
    img.set({ left: 40, top: 40, scaleX: scale, scaleY: scale });
    img.setCoords();
    fabricCanvas.add(img);
    fabricCanvas.setActiveObject(img);
    fabricCanvas.renderAll();
    saveCurrentState();
  }, { crossOrigin: 'anonymous' });
}

// ── ADD TEXT ──────────────────────────────────────
function addText(content) {
  const text     = content || document.getElementById('text-input').value || 'テキスト';
  const size     = parseInt(document.getElementById('text-size')?.value || 16);
  const bold     = document.getElementById('text-bold')?.checked;
  const color    = textColor;

  const obj = new fabric.IText(text, {
    left: 50, top: 50,
    fontFamily: '"Noto Sans JP", "Hiragino Sans", "Meiryo", sans-serif',
    fontSize: size,
    fontWeight: bold ? 'bold' : 'normal',
    fill: color,
    editable: true,
  });
  fabricCanvas.add(obj);
  fabricCanvas.setActiveObject(obj);
  obj.enterEditing();
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
}

function clearPropsPanel() {
  document.getElementById('no-selection').style.display = 'block';
  document.getElementById('object-props').style.display = 'none';
}

function updateObjProp(prop, val) {
  const obj = fabricCanvas.getActiveObject();
  if (!obj) return;
  obj.set(prop, parseFloat(val));
  obj.setCoords();
  fabricCanvas.renderAll();
  saveCurrentState();
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

    // Render objects to a transparent canvas (no background)
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
    // Export PDF to get output filename
    const pages = await buildExportPayload();
    const res = await fetch('/api/editor/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_file: sourcePdfFile, pages, title }),
    });
    if (!res.ok) throw new Error('エクスポート失敗');

    const outputFilename = res.headers.get('X-Output-Filename') || '';
    const blob = await res.blob();

    // Get thumbnail (first page of current state)
    const thumbnail = await getPageThumbnail(1);

    // Save to DB
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

    // Offer download too
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = title + '.pdf'; a.click();
    URL.revokeObjectURL(url);

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
    { label: '住所',      key: 'address' },
    { label: '電話',      key: 'phone' },
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

  // Logo button
  if (myCompany.logo_path) {
    fields.innerHTML += `
      <button class="btn btn-outline btn-sm" style="justify-content:center" onclick="placeImage('/api/my-company/logo/${myCompany.logo_path}')">
        ロゴを追加
      </button>`;
  }
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
