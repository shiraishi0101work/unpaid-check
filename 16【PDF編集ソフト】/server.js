require('dotenv').config();
const express   = require('express');
const multer    = require('multer');
const path      = require('path');
const fs        = require('fs');
const basicAuth = require('express-basic-auth');
const { PDFDocument } = require('pdf-lib');
const { initDB, getDB } = require('./database');

const app  = express();
const PORT = process.env.PORT || 3016;

// ── Basic認証 ──────────────────────────────────────────────────────────────
const AUTH_USER = process.env.AUTH_USER || 'admin';
const AUTH_PASS = process.env.AUTH_PASS || 'pdf2024';
app.use(basicAuth({
  users: { [AUTH_USER]: AUTH_PASS },
  challenge: true,
  realm: 'PDF Editor',
}));

app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true, limit: '50mb' }));
app.use(express.static('public'));

// ── ディレクトリ作成 ────────────────────────────────────────────────────────
const ensureDir = (d) => { if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true }); };
['pdfs', 'images', 'output', 'logos'].forEach(d =>
  ensureDir(path.join(__dirname, 'uploads', d))
);

// ── ファイル名デコード ─────────────────────────────────────────────────────
function decodeFileName(name) {
  try { return Buffer.from(name, 'latin1').toString('utf8'); } catch { return name; }
}

// ── Multer ────────────────────────────────────────────────────────────────
const makeStorage = (subdir) => multer.diskStorage({
  destination: (req, file, cb) => {
    file.originalname = decodeFileName(file.originalname);
    cb(null, path.join(__dirname, 'uploads', subdir));
  },
  filename: (req, file, cb) => {
    const suffix = Date.now() + '-' + Math.round(Math.random() * 1e9);
    cb(null, suffix + path.extname(file.originalname));
  },
});

const uploadPdf   = multer({ storage: makeStorage('pdfs'),   fileFilter: (req, file, cb) => cb(null, file.mimetype === 'application/pdf' || file.originalname.endsWith('.pdf')) });
const uploadImage = multer({ storage: makeStorage('images'), fileFilter: (req, file, cb) => cb(null, file.mimetype.startsWith('image/')) });
const uploadLogo  = multer({ storage: makeStorage('logos'),  fileFilter: (req, file, cb) => cb(null, file.mimetype.startsWith('image/')) });

// ── DB初期化 ─────────────────────────────────────────────────────────────
initDB();

// ════════════════════════════════════════════════════════
//  EDITOR API
// ════════════════════════════════════════════════════════

// PDFアップロード
app.post('/api/editor/upload', uploadPdf.single('file'), (req, res) => {
  if (!req.file) return res.status(400).json({ error: 'No file' });
  res.json({
    file_name: req.file.filename,
    original_name: req.file.originalname,
  });
});

// PDFファイル配信
app.get('/api/editor/file/:filename', (req, res) => {
  const fp = path.join(__dirname, 'uploads/pdfs', path.basename(req.params.filename));
  if (!fs.existsSync(fp)) return res.status(404).end();
  res.setHeader('Content-Type', 'application/pdf');
  res.sendFile(fp);
});

// PDFエクスポート（各ページのオーバーレイPNGをpdf-libで焼き込み）
app.post('/api/editor/export', async (req, res) => {
  try {
    const { source_file, pages, title } = req.body;
    const pdfPath = path.join(__dirname, 'uploads/pdfs', path.basename(source_file));
    if (!fs.existsSync(pdfPath)) return res.status(404).json({ error: 'Source PDF not found' });

    const pdfBytes = fs.readFileSync(pdfPath);
    const pdfDoc = await PDFDocument.load(pdfBytes);

    for (const pd of (pages || [])) {
      if (!pd.overlay) continue;
      const page = pdfDoc.getPage(pd.page_num - 1);
      const { width, height } = page.getSize();
      const base64 = pd.overlay.replace(/^data:image\/png;base64,/, '');
      const pngImage = await pdfDoc.embedPng(Buffer.from(base64, 'base64'));
      page.drawImage(pngImage, { x: 0, y: 0, width, height });
    }

    const outputBytes = await pdfDoc.save();
    const outputName  = `edited-${Date.now()}.pdf`;
    const outputPath  = path.join(__dirname, 'uploads/output', outputName);
    fs.writeFileSync(outputPath, outputBytes);

    const safeName = encodeURIComponent(title || 'edited');
    res.setHeader('Content-Type', 'application/pdf');
    res.setHeader('Content-Disposition', `attachment; filename*=UTF-8''${safeName}.pdf`);
    res.setHeader('X-Output-Filename', outputName);
    res.send(Buffer.from(outputBytes));
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

// ════════════════════════════════════════════════════════
//  IMAGES LIBRARY
// ════════════════════════════════════════════════════════

app.get('/api/images', (req, res) => {
  const rows = getDB().prepare('SELECT * FROM images ORDER BY created_at DESC').all();
  res.json(rows);
});

app.post('/api/images', uploadImage.single('file'), (req, res) => {
  if (!req.file) return res.status(400).json({ error: 'No file' });
  const { name, tags } = req.body;
  const result = getDB().prepare(
    `INSERT INTO images (name, file_name, file_path, mime_type, file_size, tags) VALUES (?,?,?,?,?,?)`
  ).run(name || req.file.originalname, req.file.filename, req.file.path, req.file.mimetype, req.file.size, tags || '');
  res.json({ id: result.lastInsertRowid });
});

app.delete('/api/images/:id', (req, res) => {
  const db  = getDB();
  const row = db.prepare('SELECT * FROM images WHERE id = ?').get(req.params.id);
  if (!row) return res.status(404).json({ error: 'Not found' });
  try { fs.unlinkSync(row.file_path); } catch {}
  db.prepare('DELETE FROM images WHERE id = ?').run(req.params.id);
  res.json({ ok: true });
});

app.get('/api/images/file/:filename', (req, res) => {
  const fp = path.join(__dirname, 'uploads/images', path.basename(req.params.filename));
  if (!fs.existsSync(fp)) return res.status(404).end();
  res.sendFile(fp);
});

// ════════════════════════════════════════════════════════
//  MY COMPANY
// ════════════════════════════════════════════════════════

app.get('/api/my-company', (req, res) => {
  const row = getDB().prepare('SELECT * FROM my_company WHERE id = 1').get();
  res.json(row || {});
});

app.put('/api/my-company', (req, res) => {
  const db = getDB();
  const { company_name, postal_code, address, branch_address, phone, fax, email, representative, bank_info, notes } = req.body;
  const exists = db.prepare('SELECT id FROM my_company WHERE id = 1').get();
  if (exists) {
    db.prepare(`UPDATE my_company SET company_name=?,postal_code=?,address=?,branch_address=?,phone=?,fax=?,email=?,representative=?,bank_info=?,notes=?,updated_at=datetime('now','localtime') WHERE id=1`)
      .run(company_name, postal_code, address, branch_address, phone, fax, email, representative, bank_info, notes);
  } else {
    db.prepare(`INSERT INTO my_company (id,company_name,postal_code,address,branch_address,phone,fax,email,representative,bank_info,notes) VALUES (1,?,?,?,?,?,?,?,?,?,?)`)
      .run(company_name, postal_code, address, branch_address, phone, fax, email, representative, bank_info, notes);
  }
  res.json({ ok: true });
});

app.post('/api/my-company/logo', uploadLogo.single('file'), (req, res) => {
  if (!req.file) return res.status(400).json({ error: 'No file' });
  const db = getDB();
  const exists = db.prepare('SELECT id FROM my_company WHERE id = 1').get();
  if (exists) {
    db.prepare(`UPDATE my_company SET logo_path=?,updated_at=datetime('now','localtime') WHERE id=1`).run(req.file.filename);
  } else {
    db.prepare(`INSERT INTO my_company (id,logo_path) VALUES (1,?)`).run(req.file.filename);
  }
  res.json({ logo_path: req.file.filename });
});

app.get('/api/my-company/logo/:filename', (req, res) => {
  const fp = path.join(__dirname, 'uploads/logos', path.basename(req.params.filename));
  if (!fs.existsSync(fp)) return res.status(404).end();
  res.sendFile(fp);
});

// ════════════════════════════════════════════════════════
//  CLIENTS
// ════════════════════════════════════════════════════════

app.get('/api/clients', (req, res) => {
  res.json(getDB().prepare('SELECT * FROM clients ORDER BY company_name').all());
});

app.post('/api/clients', (req, res) => {
  const { company_name, contact_name, contact_email, contact_phone, postal_code, address, notes } = req.body;
  if (!company_name) return res.status(400).json({ error: '会社名は必須です' });
  const result = getDB().prepare(
    `INSERT INTO clients (company_name,contact_name,contact_email,contact_phone,postal_code,address,notes) VALUES (?,?,?,?,?,?,?)`
  ).run(company_name, contact_name, contact_email, contact_phone, postal_code, address, notes);
  res.json({ id: result.lastInsertRowid });
});

app.put('/api/clients/:id', (req, res) => {
  const { company_name, contact_name, contact_email, contact_phone, postal_code, address, notes } = req.body;
  getDB().prepare(`UPDATE clients SET company_name=?,contact_name=?,contact_email=?,contact_phone=?,postal_code=?,address=?,notes=?,updated_at=datetime('now','localtime') WHERE id=?`)
    .run(company_name, contact_name, contact_email, contact_phone, postal_code, address, notes, req.params.id);
  res.json({ ok: true });
});

app.delete('/api/clients/:id', (req, res) => {
  getDB().prepare('DELETE FROM clients WHERE id = ?').run(req.params.id);
  res.json({ ok: true });
});

// ════════════════════════════════════════════════════════
//  TEMPLATES (定型文)
// ════════════════════════════════════════════════════════

// 定型文一覧（自社情報も含めて返す）
app.get('/api/templates', (req, res) => {
  const db = getDB();
  const templates = db.prepare('SELECT * FROM templates ORDER BY sort_order, created_at').all();

  // 自社情報を定型文として追加
  const company = db.prepare('SELECT * FROM my_company WHERE id = 1').get() || {};
  const companyItems = [
    { key: 'company_name',   label: '会社名' },
    { key: 'address',        label: '住所' },
    { key: 'phone',          label: '電話番号' },
    { key: 'fax',            label: 'FAX' },
    { key: 'email',          label: 'メール' },
    { key: 'representative', label: '代表者名' },
    { key: 'postal_code',    label: '郵便番号' },
    { key: 'bank_info',      label: '銀行口座' },
  ].filter(i => company[i.key]).map((i, idx) => ({
    id: `company_${i.key}`,
    title: i.label,
    content: company[i.key],
    category: '自社情報',
    is_company: true,
    sort_order: idx,
  }));

  res.json({ templates, company_items: companyItems });
});

app.post('/api/templates', (req, res) => {
  const { title, content, category, sort_order } = req.body;
  if (!title || !content) return res.status(400).json({ error: 'タイトルと内容は必須です' });
  const result = getDB().prepare(
    `INSERT INTO templates (title, content, category, sort_order) VALUES (?,?,?,?)`
  ).run(title, content, category || '一般', sort_order || 0);
  res.json({ id: result.lastInsertRowid });
});

app.put('/api/templates/:id', (req, res) => {
  const { title, content, category, sort_order } = req.body;
  getDB().prepare(
    `UPDATE templates SET title=?, content=?, category=?, sort_order=?, updated_at=datetime('now','localtime') WHERE id=?`
  ).run(title, content, category || '一般', sort_order || 0, req.params.id);
  res.json({ ok: true });
});

app.delete('/api/templates/:id', (req, res) => {
  getDB().prepare('DELETE FROM templates WHERE id = ?').run(req.params.id);
  res.json({ ok: true });
});

// ════════════════════════════════════════════════════════
//  DOCUMENTS (ARCHIVE)
// ════════════════════════════════════════════════════════

app.get('/api/documents', (req, res) => {
  let sql = `SELECT d.*, c.company_name as client_name FROM documents d LEFT JOIN clients c ON d.client_id = c.id`;
  const params = [];
  if (req.query.client_id) { sql += ' WHERE d.client_id = ?'; params.push(req.query.client_id); }
  sql += ' ORDER BY d.created_at DESC';
  res.json(getDB().prepare(sql).all(...params));
});

app.get('/api/documents/:id', (req, res) => {
  const row = getDB().prepare(`SELECT d.*, c.company_name as client_name FROM documents d LEFT JOIN clients c ON d.client_id = c.id WHERE d.id = ?`).get(req.params.id);
  if (!row) return res.status(404).json({ error: 'Not found' });
  res.json(row);
});

app.post('/api/documents', (req, res) => {
  const { title, client_id, original_file_name, output_file_name, thumbnail, editor_state, notes } = req.body;
  const result = getDB().prepare(
    `INSERT INTO documents (title,client_id,original_file_name,output_file_name,thumbnail,editor_state,notes) VALUES (?,?,?,?,?,?,?)`
  ).run(title, client_id || null, original_file_name, output_file_name, thumbnail, editor_state, notes);
  res.json({ id: result.lastInsertRowid });
});

app.put('/api/documents/:id', (req, res) => {
  const { title, client_id, notes } = req.body;
  getDB().prepare(`UPDATE documents SET title=?,client_id=?,notes=?,updated_at=datetime('now','localtime') WHERE id=?`)
    .run(title, client_id || null, notes, req.params.id);
  res.json({ ok: true });
});

app.delete('/api/documents/:id', (req, res) => {
  const db  = getDB();
  const row = db.prepare('SELECT * FROM documents WHERE id = ?').get(req.params.id);
  if (!row) return res.status(404).json({ error: 'Not found' });
  try { if (row.output_file_name) fs.unlinkSync(path.join(__dirname, 'uploads/output', row.output_file_name)); } catch {}
  db.prepare('DELETE FROM documents WHERE id = ?').run(req.params.id);
  res.json({ ok: true });
});

app.get('/api/documents/:id/download', (req, res) => {
  const row = getDB().prepare('SELECT * FROM documents WHERE id = ?').get(req.params.id);
  if (!row || !row.output_file_name) return res.status(404).json({ error: 'Not found' });
  const fp = path.join(__dirname, 'uploads/output', row.output_file_name);
  if (!fs.existsSync(fp)) return res.status(404).json({ error: 'File not found' });
  res.download(fp, `${row.title}.pdf`);
});

// ── 出力ファイル配信 ──────────────────────────────────────────────────────
app.get('/api/output/:filename', (req, res) => {
  const fp = path.join(__dirname, 'uploads/output', path.basename(req.params.filename));
  if (!fs.existsSync(fp)) return res.status(404).end();
  res.setHeader('Content-Type', 'application/pdf');
  res.sendFile(fp);
});

// ── Stats ─────────────────────────────────────────────────────────────────
app.get('/api/stats', (req, res) => {
  const db = getDB();
  res.json({
    doc_count:    db.prepare('SELECT COUNT(*) as c FROM documents').get().c,
    client_count: db.prepare('SELECT COUNT(*) as c FROM clients').get().c,
    image_count:  db.prepare('SELECT COUNT(*) as c FROM images').get().c,
    recent_docs:  db.prepare(`SELECT d.*, c.company_name as client_name FROM documents d LEFT JOIN clients c ON d.client_id = c.id ORDER BY d.created_at DESC LIMIT 6`).all(),
  });
});

app.listen(PORT, () => console.log(`PDF Editor: http://localhost:${PORT}`));
