require('dotenv').config();
const express = require('express');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const { initDB, getDB } = require('./database');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static('public'));

// PDF upload config
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    const dir = path.join(__dirname, 'uploads');
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    cb(null, dir);
  },
  filename: (req, file, cb) => {
    const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1e9);
    cb(null, uniqueSuffix + '.pdf');
  }
});
const upload = multer({
  storage,
  fileFilter: (req, file, cb) => {
    if (file.mimetype === 'application/pdf') cb(null, true);
    else cb(new Error('PDFファイルのみアップロード可能です'));
  },
  limits: { fileSize: 30 * 1024 * 1024 }
});

initDB();

// ─── Partners ────────────────────────────────────────────────────────────────

app.get('/api/partners', (req, res) => {
  const db = getDB();
  const { search } = req.query;
  let query = 'SELECT * FROM partners';
  const params = [];
  if (search) {
    query += ' WHERE company_name LIKE ? OR rep_name LIKE ?';
    params.push(`%${search}%`, `%${search}%`);
  }
  query += ' ORDER BY company_name ASC';
  res.json(db.prepare(query).all(...params));
});

app.post('/api/partners', (req, res) => {
  const db = getDB();
  const { company_name, contract_date, rep_name, rep_email, rep_phone, status, notes } = req.body;
  if (!company_name) return res.status(400).json({ error: '企業名は必須です' });
  const stmt = db.prepare(`
    INSERT INTO partners (company_name, contract_date, rep_name, rep_email, rep_phone, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `);
  const result = stmt.run(company_name, contract_date || null, rep_name || null, rep_email || null, rep_phone || null, status || 'active', notes || null);
  res.json(db.prepare('SELECT * FROM partners WHERE id = ?').get(result.lastInsertRowid));
});

app.put('/api/partners/:id', (req, res) => {
  const db = getDB();
  const { company_name, contract_date, rep_name, rep_email, rep_phone, status, notes } = req.body;
  if (!company_name) return res.status(400).json({ error: '企業名は必須です' });
  db.prepare(`
    UPDATE partners SET company_name=?, contract_date=?, rep_name=?, rep_email=?, rep_phone=?, status=?, notes=?,
    updated_at=datetime('now','localtime') WHERE id=?
  `).run(company_name, contract_date || null, rep_name || null, rep_email || null, rep_phone || null, status, notes || null, req.params.id);
  res.json(db.prepare('SELECT * FROM partners WHERE id = ?').get(req.params.id));
});

app.delete('/api/partners/:id', (req, res) => {
  getDB().prepare('DELETE FROM partners WHERE id = ?').run(req.params.id);
  res.json({ success: true });
});

// ─── Products ─────────────────────────────────────────────────────────────────

app.get('/api/products', (req, res) => {
  const db = getDB();
  const products = db.prepare(`
    SELECT p.*, COUNT(pp.id) as partner_count, COALESCE(SUM(pp.order_count), 0) as total_orders
    FROM products p
    LEFT JOIN partner_products pp ON pp.product_id = p.id
    GROUP BY p.id
    ORDER BY p.name ASC
  `).all();
  res.json(products);
});

app.post('/api/products', (req, res) => {
  const db = getDB();
  const { name, description, initial_count } = req.body;
  if (!name) return res.status(400).json({ error: '商品名は必須です' });
  const result = db.prepare('INSERT INTO products (name, description, initial_count) VALUES (?, ?, ?)')
    .run(name, description || null, parseInt(initial_count) || 0);
  res.json(db.prepare('SELECT * FROM products WHERE id = ?').get(result.lastInsertRowid));
});

app.put('/api/products/:id', (req, res) => {
  const db = getDB();
  const { name, description, initial_count } = req.body;
  if (!name) return res.status(400).json({ error: '商品名は必須です' });
  db.prepare(`UPDATE products SET name=?, description=?, initial_count=?, updated_at=datetime('now','localtime') WHERE id=?`)
    .run(name, description || null, parseInt(initial_count) || 0, req.params.id);
  res.json(db.prepare('SELECT * FROM products WHERE id = ?').get(req.params.id));
});

app.delete('/api/products/:id', (req, res) => {
  getDB().prepare('DELETE FROM products WHERE id = ?').run(req.params.id);
  res.json({ success: true });
});

// ─── Partner Products (Orders) ────────────────────────────────────────────────

app.get('/api/partner-products', (req, res) => {
  const db = getDB();
  const { partner_id, product_id } = req.query;
  let query = `
    SELECT pp.*, pt.company_name, pt.status as partner_status,
           pr.name as product_name, pr.initial_count
    FROM partner_products pp
    JOIN partners pt ON pp.partner_id = pt.id
    JOIN products pr ON pp.product_id = pr.id
    WHERE 1=1
  `;
  const params = [];
  if (partner_id) { query += ' AND pp.partner_id = ?'; params.push(partner_id); }
  if (product_id) { query += ' AND pp.product_id = ?'; params.push(product_id); }
  query += ' ORDER BY pt.company_name ASC, pr.name ASC';
  res.json(db.prepare(query).all(...params));
});

app.post('/api/partner-products', (req, res) => {
  const db = getDB();
  const { partner_id, product_id, order_count } = req.body;
  if (!partner_id || !product_id) return res.status(400).json({ error: '代理店と商品は必須です' });

  const existing = db.prepare('SELECT * FROM partner_products WHERE partner_id=? AND product_id=?').get(partner_id, product_id);
  let id;
  if (existing) {
    db.prepare(`UPDATE partner_products SET order_count=?, updated_at=datetime('now','localtime') WHERE id=?`)
      .run(parseInt(order_count) || 0, existing.id);
    id = existing.id;
  } else {
    const result = db.prepare('INSERT INTO partner_products (partner_id, product_id, order_count) VALUES (?, ?, ?)')
      .run(partner_id, product_id, parseInt(order_count) || 0);
    id = result.lastInsertRowid;
  }

  const record = db.prepare(`
    SELECT pp.*, pt.company_name, pt.status as partner_status,
           pr.name as product_name, pr.initial_count
    FROM partner_products pp
    JOIN partners pt ON pp.partner_id = pt.id
    JOIN products pr ON pp.product_id = pr.id
    WHERE pp.id = ?
  `).get(id);
  res.json(record);
});

app.put('/api/partner-products/:id', (req, res) => {
  const db = getDB();
  db.prepare(`UPDATE partner_products SET order_count=?, updated_at=datetime('now','localtime') WHERE id=?`)
    .run(parseInt(req.body.order_count) || 0, req.params.id);
  const record = db.prepare(`
    SELECT pp.*, pt.company_name, pt.status as partner_status,
           pr.name as product_name, pr.initial_count
    FROM partner_products pp
    JOIN partners pt ON pp.partner_id = pt.id
    JOIN products pr ON pp.product_id = pr.id
    WHERE pp.id = ?
  `).get(req.params.id);
  res.json(record);
});

app.delete('/api/partner-products/:id', (req, res) => {
  getDB().prepare('DELETE FROM partner_products WHERE id = ?').run(req.params.id);
  res.json({ success: true });
});

// ─── Contracts ────────────────────────────────────────────────────────────────

// PDF text extraction and parsing (free, no API required)
async function extractFromPdf(filePath) {
  const pdfParse = require('pdf-parse');
  const buffer = fs.readFileSync(filePath);
  const data = await pdfParse(buffer);
  const text = data.text;

  const result = {
    company_name: null,
    contract_date: null,
    representative: null,
    address: null,
    contract_type: null,
    contract_period: null,
    raw_text_preview: text.slice(0, 300),
  };

  // ── 企業名 ────────────────────────────────────────────
  // 株式会社・有限会社・合同会社・一般社団法人 etc.
  const companyPatterns = [
    /(?:株式会社|有限会社|合同会社|一般社団法人|公益社団法人|一般財団法人|公益財団法人|医療法人|社会福祉法人|特定非営利活動法人|NPO法人)\s*[\u3040-\u9FFF\w\s・]+?(?=\s|　|（|「|,|、|。|\n|$)/,
    /[\u3040-\u9FFF\w\s・]+?(?:株式会社|有限会社|合同会社)(?=\s|　|（|「|,|、|。|\n|$)/,
  ];
  for (const pat of companyPatterns) {
    const m = text.match(pat);
    if (m) { result.company_name = m[0].trim(); break; }
  }

  // ── 契約日 ────────────────────────────────────────────
  // 令和X年X月X日 / 西暦YYYY年MM月DD日 / YYYY-MM-DD / YYYY/MM/DD
  const datePatterns = [
    { re: /令和\s*(\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日/, fn: (m) => { const y = 2018 + parseInt(m[1]); return `${y}-${String(m[2]).padStart(2,'0')}-${String(m[3]).padStart(2,'0')}`; } },
    { re: /平成\s*(\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日/, fn: (m) => { const y = 1988 + parseInt(m[1]); return `${y}-${String(m[2]).padStart(2,'0')}-${String(m[3]).padStart(2,'0')}`; } },
    { re: /(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日/, fn: (m) => `${m[1]}-${String(m[2]).padStart(2,'0')}-${String(m[3]).padStart(2,'0')}` },
    { re: /(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})/, fn: (m) => `${m[1]}-${String(m[2]).padStart(2,'0')}-${String(m[3]).padStart(2,'0')}` },
  ];
  for (const { re, fn } of datePatterns) {
    const m = text.match(re);
    if (m) { result.contract_date = fn(m); break; }
  }

  // ── 代表者名 ───────────────────────────────────────────
  const repPatterns = [
    /代表取締役\s*([^\s　\n（「]{2,10})/,
    /代表者\s*[:：]?\s*([^\s　\n（「]{2,10})/,
    /担当者\s*[:：]?\s*([^\s　\n（「]{2,10})/,
  ];
  for (const pat of repPatterns) {
    const m = text.match(pat);
    if (m) { result.representative = m[1].trim(); break; }
  }

  // ── 契約種別 ───────────────────────────────────────────
  const typeMatch = text.match(/(?:販売代理店|業務委託|パートナー|代理店|販売|取引基本|秘密保持|NDA)\s*契約/);
  if (typeMatch) result.contract_type = typeMatch[0].trim();

  // ── 住所 ──────────────────────────────────────────────
  const addrMatch = text.match(/〒?\d{3}[-－]\d{4}[^\n]{5,50}/);
  if (addrMatch) result.address = addrMatch[0].trim();

  return result;
}

app.post('/api/contracts/upload', upload.single('pdf'), async (req, res) => {
  try {
    if (!req.file) return res.status(400).json({ error: 'PDFファイルが必要です' });
    const { partner_id } = req.body;
    const file = req.file;
    let extractedData = {};

    try {
      extractedData = await extractFromPdf(file.path);
    } catch (e) {
      console.error('PDF parse error:', e.message);
    }

    const db = getDB();
    const result = db.prepare(`
      INSERT INTO contracts (partner_id, file_name, file_path, extracted_company_name, extracted_contract_date, extracted_data)
      VALUES (?, ?, ?, ?, ?, ?)
    `).run(
      partner_id || null,
      req.file.originalname,
      file.path,
      extractedData.company_name || null,
      extractedData.contract_date || null,
      JSON.stringify(extractedData)
    );

    const contract = db.prepare('SELECT * FROM contracts WHERE id = ?').get(result.lastInsertRowid);
    res.json({ ...contract, extracted: extractedData });
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: e.message });
  }
});

app.get('/api/contracts', (req, res) => {
  const db = getDB();
  const { partner_id } = req.query;
  let query = 'SELECT * FROM contracts';
  const params = [];
  if (partner_id) { query += ' WHERE partner_id = ?'; params.push(partner_id); }
  query += ' ORDER BY created_at DESC';
  res.json(db.prepare(query).all(...params));
});

app.get('/api/contracts/:id/file', (req, res) => {
  const db = getDB();
  const contract = db.prepare('SELECT * FROM contracts WHERE id = ?').get(req.params.id);
  if (!contract) return res.status(404).json({ error: '契約書が見つかりません' });
  res.sendFile(path.resolve(contract.file_path));
});

app.delete('/api/contracts/:id', (req, res) => {
  const db = getDB();
  const contract = db.prepare('SELECT * FROM contracts WHERE id = ?').get(req.params.id);
  if (contract && fs.existsSync(contract.file_path)) {
    try { fs.unlinkSync(contract.file_path); } catch (e) {}
  }
  db.prepare('DELETE FROM contracts WHERE id = ?').run(req.params.id);
  res.json({ success: true });
});

// ─── Excel Import ─────────────────────────────────────────────────────────────

const xlsxUpload = multer({
  storage: multer.memoryStorage(),
  fileFilter: (req, file, cb) => {
    const ok = file.mimetype.includes('spreadsheet') ||
               file.mimetype.includes('excel') ||
               file.originalname.match(/\.(xlsx|xls)$/i);
    if (ok) cb(null, true);
    else cb(new Error('Excel ファイル（.xlsx / .xls）のみ対応です'));
  },
  limits: { fileSize: 10 * 1024 * 1024 },
});

// 列名の揺れを吸収するマッピング
function colVal(row, candidates) {
  for (const k of candidates) {
    if (row[k] !== undefined && row[k] !== null && String(row[k]).trim() !== '') {
      return String(row[k]).trim();
    }
  }
  return null;
}

// パートナー一覧インポート
app.post('/api/partners/import', xlsxUpload.single('excel'), (req, res) => {
  try {
    if (!req.file) return res.status(400).json({ error: 'Excelファイルが必要です' });
    const XLSX = require('xlsx');
    const wb = XLSX.read(req.file.buffer, { type: 'buffer', cellDates: true });
    const ws = wb.Sheets[wb.SheetNames[0]];
    const rows = XLSX.utils.sheet_to_json(ws, { defval: null });

    const db = getDB();
    let inserted = 0, skipped = 0;
    const errors = [];

    for (const [i, row] of rows.entries()) {
      const company_name = colVal(row, ['企業名', 'company_name', '会社名', '法人名']);
      if (!company_name) { skipped++; continue; }

      const contract_date_raw = colVal(row, ['契約日', 'contract_date', '契約年月日']);
      let contract_date = null;
      if (contract_date_raw) {
        // Date objects from cellDates:true
        if (contract_date_raw instanceof Date || (typeof contract_date_raw === 'object' && contract_date_raw?.toISOString)) {
          const d = new Date(contract_date_raw);
          contract_date = d.toISOString().slice(0, 10);
        } else {
          // Try parsing string
          const d = new Date(contract_date_raw);
          contract_date = isNaN(d) ? contract_date_raw : d.toISOString().slice(0, 10);
        }
      }

      const status_raw = colVal(row, ['ステータス', 'status', '状態']);
      const statusMap = { '契約中': 'active', '検討中': 'pending', '解約': 'inactive', 'active': 'active', 'pending': 'pending', 'inactive': 'inactive' };
      const status = statusMap[status_raw] || 'active';

      try {
        db.prepare(`
          INSERT INTO partners (company_name, contract_date, rep_name, rep_email, rep_phone, status, notes)
          VALUES (?, ?, ?, ?, ?, ?, ?)
        `).run(
          company_name,
          contract_date,
          colVal(row, ['担当者名', '担当者', 'rep_name', '担当']),
          colVal(row, ['メール', 'メールアドレス', 'email', 'rep_email', 'Email']),
          colVal(row, ['電話', '電話番号', 'phone', 'rep_phone', 'TEL']),
          status,
          colVal(row, ['備考', 'notes', 'メモ', '備考欄'])
        );
        inserted++;
      } catch (e) {
        errors.push(`行${i + 2}: ${e.message}`);
      }
    }

    res.json({ inserted, skipped, errors });
  } catch (e) {
    res.status(400).json({ error: e.message });
  }
});

// 商品一覧インポート
app.post('/api/products/import', xlsxUpload.single('excel'), (req, res) => {
  try {
    const XLSX = require('xlsx');
    const wb = XLSX.read(req.file.buffer, { type: 'buffer' });
    const ws = wb.Sheets[wb.SheetNames[0]];
    const rows = XLSX.utils.sheet_to_json(ws, { defval: null });

    const db = getDB();
    let inserted = 0, skipped = 0;
    const errors = [];

    for (const [i, row] of rows.entries()) {
      const name = colVal(row, ['商品名', 'name', '品名', '製品名', 'サービス名']);
      if (!name) { skipped++; continue; }

      const count_raw = colVal(row, ['初期取扱数', 'initial_count', '取扱数', '数量']);
      const initial_count = parseInt(count_raw) || 0;

      try {
        db.prepare('INSERT INTO products (name, description, initial_count) VALUES (?, ?, ?)')
          .run(name, colVal(row, ['説明', 'description', '備考', '詳細']), initial_count);
        inserted++;
      } catch (e) {
        errors.push(`行${i + 2}: ${e.message}`);
      }
    }

    res.json({ inserted, skipped, errors });
  } catch (e) {
    res.status(400).json({ error: e.message });
  }
});

// ひな型DL（現在のデータをExcelで書き出し）
app.get('/api/partners/template', (req, res) => {
  const XLSX = require('xlsx');
  const sample = [{ 企業名: '株式会社サンプル', 契約日: '2026-01-01', 担当者名: '田中 一郎', メール: 'tanaka@sample.co.jp', 電話: '03-0000-0000', ステータス: '契約中', 備考: '' }];
  const ws = XLSX.utils.json_to_sheet(sample);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'パートナー一覧');
  const buf = XLSX.write(wb, { type: 'buffer', bookType: 'xlsx' });
  res.setHeader('Content-Disposition', 'attachment; filename="partners_template.xlsx"');
  res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
  res.send(buf);
});

app.get('/api/products/template', (req, res) => {
  const XLSX = require('xlsx');
  const sample = [{ 商品名: 'スタンダードプラン', 説明: 'プランの説明', 初期取扱数: 100 }];
  const ws = XLSX.utils.json_to_sheet(sample);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, '商品一覧');
  const buf = XLSX.write(wb, { type: 'buffer', bookType: 'xlsx' });
  res.setHeader('Content-Disposition', 'attachment; filename="products_template.xlsx"');
  res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
  res.send(buf);
});

// ─── Stats ────────────────────────────────────────────────────────────────────

app.get('/api/stats', (req, res) => {
  const db = getDB();
  const partner_count = db.prepare("SELECT COUNT(*) as c FROM partners WHERE status='active'").get().c;
  const product_count = db.prepare('SELECT COUNT(*) as c FROM products').get().c;
  const total_orders = db.prepare('SELECT COALESCE(SUM(order_count), 0) as c FROM partner_products').get().c;
  const contract_count = db.prepare('SELECT COUNT(*) as c FROM contracts').get().c;
  const recent = db.prepare(`
    SELECT pp.*, pt.company_name, pr.name as product_name
    FROM partner_products pp
    JOIN partners pt ON pp.partner_id = pt.id
    JOIN products pr ON pp.product_id = pr.id
    ORDER BY pp.updated_at DESC LIMIT 5
  `).all();
  res.json({ partner_count, product_count, total_orders, contract_count, recent });
});

app.listen(PORT, () => {
  console.log(`\n✅ パートナー・受注管理システム起動`);
  console.log(`   http://localhost:${PORT}\n`);
});
