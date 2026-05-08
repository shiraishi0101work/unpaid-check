require('dotenv').config();
const express = require('express');
const multer  = require('multer');
const path    = require('path');
const fs      = require('fs');
const { initDB, getDB } = require('./database');

const app  = express();
const PORT = process.env.PORT || 3001;

app.use(express.json());
app.use(express.static('public'));

// ── PDF アップロード設定 ──────────────────────────────────────────────────────
const makeStorage = (subdir) => multer.diskStorage({
  destination: (req, file, cb) => {
    const dir = path.join(__dirname, 'uploads', subdir);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    cb(null, dir);
  },
  filename: (req, file, cb) => {
    const suffix = Date.now() + '-' + Math.round(Math.random() * 1e9);
    const ext = path.extname(file.originalname);
    cb(null, suffix + ext);
  }
});

const upload = multer({
  storage: makeStorage('invoices'),
  fileFilter: (req, file, cb) => {
    const allowed = ['application/pdf', 'image/png', 'image/jpeg'];
    if (allowed.includes(file.mimetype)) cb(null, true);
    else cb(new Error('PDF・PNG・JPGファイルのみ'));
  },
  limits: { fileSize: 30 * 1024 * 1024 }
});

const uploadContract = multer({
  storage: makeStorage('contracts'),
  fileFilter: (req, file, cb) => {
    if (file.mimetype === 'application/pdf') cb(null, true);
    else cb(new Error('PDFファイルのみアップロード可能です'));
  },
  limits: { fileSize: 30 * 1024 * 1024 }
});

const uploadCSV = multer({
  storage: makeStorage('csv'),
  fileFilter: (req, file, cb) => {
    if (file.mimetype === 'text/csv' || file.originalname.endsWith('.csv')) cb(null, true);
    else cb(new Error('CSVファイルのみアップロード可能です'));
  },
  limits: { fileSize: 5 * 1024 * 1024 }
});

// ── CSV ユーティリティ ────────────────────────────────────────────────────────
function parseCSVRow(line) {
  const result = [];
  let current = '';
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') { current += '"'; i++; }
      else inQuotes = !inQuotes;
    } else if (ch === ',' && !inQuotes) {
      result.push(current.trim());
      current = '';
    } else {
      current += ch;
    }
  }
  result.push(current.trim());
  return result;
}

const CSV_HEADER_MAP = {
  '会社名': 'company_name', '担当者名': 'contact_name', '担当者': 'contact_name',
  'メール': 'contact_email', 'メールアドレス': 'contact_email',
  '電話': 'contact_phone', '電話番号': 'contact_phone',
  '契約開始日': 'contract_start', '状態': 'status', '備考': 'notes',
};

// ── 契約日抽出ユーティリティ ──────────────────────────────────────────────────
function extractContractDate(text) {
  // 令和N年M月D日
  let m = text.match(/令和\s*(\d+)年\s*(\d{1,2})月\s*(\d{1,2})日/);
  if (m) {
    const year = parseInt(m[1]) + 2018;
    return `${year}-${String(m[2]).padStart(2,'0')}-${String(m[3]).padStart(2,'0')}`;
  }
  // 西暦 YYYY年M月D日
  m = text.match(/(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日/);
  if (m) return `${m[1]}-${String(m[2]).padStart(2,'0')}-${String(m[3]).padStart(2,'0')}`;
  // YYYY/MM/DD or YYYY-MM-DD
  m = text.match(/(\d{4})[\/\-](\d{2})[\/\-](\d{2})/);
  if (m) return `${m[1]}-${m[2]}-${m[3]}`;
  return null;
}

initDB();

// ── パートナー ────────────────────────────────────────────────────────────────

// CSV取込（/api/partners/:id より先に定義）
app.post('/api/partners/import-csv', uploadCSV.single('file'), (req, res) => {
  const db = getDB();
  if (!req.file) return res.status(400).json({ error: 'ファイルがありません' });

  let text = fs.readFileSync(req.file.path, 'utf-8');
  // BOM除去
  text = text.replace(/^\uFEFF/, '');
  const lines = text.split(/\r?\n/).filter(l => l.trim());
  if (lines.length < 2) return res.status(400).json({ error: 'データが1件もありません' });

  const rawHeaders = parseCSVRow(lines[0]);
  const headers = rawHeaders.map(h => CSV_HEADER_MAP[h] || h);

  const stmt = db.prepare(`
    INSERT INTO partners (company_name, contact_name, contact_email, contact_phone, contract_start, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `);

  let imported = 0, skipped = 0;
  const errors = [];

  for (let i = 1; i < lines.length; i++) {
    const values = parseCSVRow(lines[i]);
    const row = {};
    headers.forEach((h, idx) => { row[h] = values[idx] || ''; });

    if (!row.company_name) { skipped++; continue; }
    try {
      stmt.run(
        row.company_name, row.contact_name || null, row.contact_email || null,
        row.contact_phone || null, row.contract_start || null,
        row.status === 'inactive' ? 'inactive' : 'active',
        row.notes || null
      );
      imported++;
    } catch (e) {
      errors.push(`行${i + 1}: ${e.message}`);
      skipped++;
    }
  }

  fs.unlinkSync(req.file.path);
  res.json({ message: `${imported}件取込完了 (スキップ: ${skipped}件)`, imported, skipped, errors });
});

app.get('/api/partners', (req, res) => {
  const db = getDB();
  const { search, status } = req.query;
  let q = 'SELECT * FROM partners WHERE 1=1';
  const params = [];
  if (search) { q += ' AND (company_name LIKE ? OR contact_name LIKE ?)'; params.push(`%${search}%`, `%${search}%`); }
  if (status)  { q += ' AND status = ?'; params.push(status); }
  q += ' ORDER BY company_name ASC';
  res.json(db.prepare(q).all(...params));
});

app.get('/api/partners/:id', (req, res) => {
  const db = getDB();
  const partner = db.prepare('SELECT * FROM partners WHERE id = ?').get(req.params.id);
  if (!partner) return res.status(404).json({ error: '見つかりません' });
  res.json(partner);
});

app.post('/api/partners', (req, res) => {
  const db = getDB();
  const { company_name, contact_name, contact_email, contact_phone, contract_start, status, notes } = req.body;
  if (!company_name) return res.status(400).json({ error: '会社名は必須です' });
  const result = db.prepare(`
    INSERT INTO partners (company_name, contact_name, contact_email, contact_phone, contract_start, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `).run(company_name, contact_name, contact_email, contact_phone, contract_start, status || 'active', notes);
  res.json({ id: result.lastInsertRowid, message: '登録しました' });
});

app.put('/api/partners/:id', (req, res) => {
  const db = getDB();
  const { company_name, contact_name, contact_email, contact_phone, contract_start, status, notes } = req.body;
  db.prepare(`
    UPDATE partners SET company_name=?, contact_name=?, contact_email=?, contact_phone=?,
    contract_start=?, status=?, notes=?, updated_at=datetime('now','localtime')
    WHERE id=?
  `).run(company_name, contact_name, contact_email, contact_phone, contract_start, status, notes, req.params.id);
  res.json({ message: '更新しました' });
});

app.delete('/api/partners/:id', (req, res) => {
  const db = getDB();
  db.prepare('DELETE FROM partners WHERE id = ?').run(req.params.id);
  res.json({ message: '削除しました' });
});

// ── 商材 ──────────────────────────────────────────────────────────────────────

app.get('/api/products', (req, res) => {
  const db = getDB();
  const { search } = req.query;
  let q = 'SELECT * FROM products WHERE 1=1';
  const params = [];
  if (search) { q += ' AND (name LIKE ? OR code LIKE ?)'; params.push(`%${search}%`, `%${search}%`); }
  q += ' ORDER BY name ASC';
  res.json(db.prepare(q).all(...params));
});

app.post('/api/products', (req, res) => {
  const db = getDB();
  const { name, code, unit_price, description } = req.body;
  if (!name) return res.status(400).json({ error: '商材名は必須です' });
  const result = db.prepare(`
    INSERT INTO products (name, code, unit_price, description) VALUES (?, ?, ?, ?)
  `).run(name, code, unit_price || 0, description);
  res.json({ id: result.lastInsertRowid, message: '登録しました' });
});

app.put('/api/products/:id', (req, res) => {
  const db = getDB();
  const { name, code, unit_price, description } = req.body;
  db.prepare(`
    UPDATE products SET name=?, code=?, unit_price=?, description=?, updated_at=datetime('now','localtime')
    WHERE id=?
  `).run(name, code, unit_price || 0, description, req.params.id);
  res.json({ message: '更新しました' });
});

app.delete('/api/products/:id', (req, res) => {
  const db = getDB();
  db.prepare('DELETE FROM products WHERE id = ?').run(req.params.id);
  res.json({ message: '削除しました' });
});

// ── 請求書 ────────────────────────────────────────────────────────────────────

app.get('/api/invoices', (req, res) => {
  const db = getDB();
  const { partner_id, year, month, status } = req.query;
  let q = `
    SELECT i.*, p.company_name as partner_name
    FROM invoices i
    LEFT JOIN partners p ON p.id = i.partner_id
    WHERE 1=1
  `;
  const params = [];
  if (partner_id) { q += ' AND i.partner_id = ?'; params.push(partner_id); }
  if (year)  { q += " AND i.billing_month LIKE ?"; params.push(`${year}-%`); }
  if (month) { q += ' AND i.billing_month = ?'; params.push(month); }
  if (status) { q += ' AND i.status = ?'; params.push(status); }
  q += ' ORDER BY i.billing_month DESC, p.company_name ASC';
  res.json(db.prepare(q).all(...params));
});

app.get('/api/invoices/:id', (req, res) => {
  const db = getDB();
  const invoice = db.prepare(`
    SELECT i.*, p.company_name as partner_name
    FROM invoices i LEFT JOIN partners p ON p.id = i.partner_id
    WHERE i.id = ?
  `).get(req.params.id);
  if (!invoice) return res.status(404).json({ error: '見つかりません' });
  const items = db.prepare(`
    SELECT ii.*, pr.name as product_name
    FROM invoice_items ii LEFT JOIN products pr ON pr.id = ii.product_id
    WHERE ii.invoice_id = ?
  `).all(req.params.id);
  res.json({ ...invoice, items });
});

// PDF アップロード → テキスト抽出
app.post('/api/invoices/upload', upload.single('file'), async (req, res) => {
  const db = getDB();
  let extractedText = '';

  if (req.file && req.file.mimetype === 'application/pdf') {
    try {
      const pdfParse = require('pdf-parse');
      const buffer = fs.readFileSync(req.file.path);
      const data = await pdfParse(buffer);
      extractedText = data.text || '';
    } catch (e) {
      console.error('PDF解析エラー:', e.message);
    }
  }

  // 請求金額を推定（合計行を探す）
  let guessedAmount = 0;
  const amountMatch = extractedText.match(/(?:合計|請求金額|ご請求金額)[^\d]*([0-9,，]+)/);
  if (amountMatch) {
    guessedAmount = parseInt(amountMatch[1].replace(/[,，]/g, '')) || 0;
  }

  // 請求月を推定
  let guessedMonth = '';
  const monthMatch = extractedText.match(/(\d{4})[年\/\-](\d{1,2})(?:[月\/\-])/);
  if (monthMatch) {
    guessedMonth = `${monthMatch[1]}-${String(monthMatch[2]).padStart(2, '0')}`;
  }

  // パートナー名を推定（DB上の会社名と照合）
  const partners = db.prepare('SELECT id, company_name FROM partners WHERE status = ?').all('active');
  let guessedPartnerId = null;
  for (const p of partners) {
    if (extractedText.includes(p.company_name)) {
      guessedPartnerId = p.id;
      break;
    }
  }

  const result = db.prepare(`
    INSERT INTO invoices (file_name, file_path, billing_month, total_amount, extracted_text, partner_id, status)
    VALUES (?, ?, ?, ?, ?, ?, 'pending')
  `).run(
    req.file ? req.file.originalname : '手動入力',
    req.file ? req.file.path : '',
    guessedMonth,
    guessedAmount,
    extractedText.slice(0, 5000),
    guessedPartnerId
  );

  res.json({
    id: result.lastInsertRowid,
    guessed_month: guessedMonth,
    guessed_amount: guessedAmount,
    guessed_partner_id: guessedPartnerId,
    extracted_text: extractedText.slice(0, 2000),
    message: 'アップロード完了。内容を確認して保存してください。'
  });
});

// 請求書を手動で新規作成（PDFなし）
app.post('/api/invoices', (req, res) => {
  const db = getDB();
  const { partner_id, billing_month, total_amount, notes, items } = req.body;
  if (!partner_id || !billing_month) return res.status(400).json({ error: 'パートナーと請求月は必須です' });

  const result = db.prepare(`
    INSERT INTO invoices (partner_id, billing_month, total_amount, notes, status)
    VALUES (?, ?, ?, ?, 'confirmed')
  `).run(partner_id, billing_month, total_amount || 0, notes);

  const invoiceId = result.lastInsertRowid;

  if (items && items.length > 0) {
    const stmt = db.prepare(`
      INSERT INTO invoice_items (invoice_id, product_id, description, quantity, unit_price, amount)
      VALUES (?, ?, ?, ?, ?, ?)
    `);
    for (const item of items) {
      stmt.run(invoiceId, item.product_id || null, item.description, item.quantity || 1, item.unit_price || 0, item.amount || 0);
    }
  }

  res.json({ id: invoiceId, message: '登録しました' });
});

// 請求書を確定・更新
app.put('/api/invoices/:id', (req, res) => {
  const db = getDB();
  const { partner_id, billing_month, total_amount, notes, status, items } = req.body;

  db.prepare(`
    UPDATE invoices SET partner_id=?, billing_month=?, total_amount=?, notes=?, status=?,
    updated_at=datetime('now','localtime') WHERE id=?
  `).run(partner_id, billing_month, total_amount || 0, notes, status || 'confirmed', req.params.id);

  if (items !== undefined) {
    db.prepare('DELETE FROM invoice_items WHERE invoice_id = ?').run(req.params.id);
    if (items && items.length > 0) {
      const stmt = db.prepare(`
        INSERT INTO invoice_items (invoice_id, product_id, description, quantity, unit_price, amount)
        VALUES (?, ?, ?, ?, ?, ?)
      `);
      for (const item of items) {
        stmt.run(req.params.id, item.product_id || null, item.description, item.quantity || 1, item.unit_price || 0, item.amount || 0);
      }
    }
  }

  res.json({ message: '更新しました' });
});

app.delete('/api/invoices/:id', (req, res) => {
  const db = getDB();
  db.prepare('DELETE FROM invoices WHERE id = ?').run(req.params.id);
  res.json({ message: '削除しました' });
});

// ── 月別集計 ──────────────────────────────────────────────────────────────────

app.get('/api/monthly-summary', (req, res) => {
  const db = getDB();
  const { year } = req.query;
  const targetYear = year || new Date().getFullYear().toString();

  // パートナー×月の請求合計
  const rows = db.prepare(`
    SELECT
      p.id AS partner_id,
      p.company_name,
      i.billing_month,
      SUM(i.total_amount) AS total
    FROM invoices i
    JOIN partners p ON p.id = i.partner_id
    WHERE i.status = 'confirmed'
      AND i.billing_month LIKE ?
    GROUP BY p.id, i.billing_month
    ORDER BY p.company_name, i.billing_month
  `).all(`${targetYear}-%`);

  // 月一覧を生成 (1月〜12月)
  const months = Array.from({ length: 12 }, (_, i) =>
    `${targetYear}-${String(i + 1).padStart(2, '0')}`
  );

  // パートナーごとにまとめる
  const partnerMap = {};
  for (const row of rows) {
    if (!partnerMap[row.partner_id]) {
      partnerMap[row.partner_id] = { partner_id: row.partner_id, company_name: row.company_name, months: {} };
    }
    partnerMap[row.partner_id].months[row.billing_month] = row.total;
  }

  // 年間合計
  const totalsPerMonth = {};
  for (const p of Object.values(partnerMap)) {
    for (const [m, v] of Object.entries(p.months)) {
      totalsPerMonth[m] = (totalsPerMonth[m] || 0) + v;
    }
  }

  res.json({
    year: targetYear,
    months,
    partners: Object.values(partnerMap),
    monthly_totals: totalsPerMonth
  });
});

// ── 今月サマリー ──────────────────────────────────────────────────────────────

app.get('/api/dashboard', (req, res) => {
  const db = getDB();
  const now = new Date();
  const thisMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  const thisYear  = now.getFullYear().toString();

  const monthlyTotal = db.prepare(`
    SELECT SUM(total_amount) AS total FROM invoices
    WHERE status='confirmed' AND billing_month=?
  `).get(thisMonth)?.total || 0;

  const yearlyTotal = db.prepare(`
    SELECT SUM(total_amount) AS total FROM invoices
    WHERE status='confirmed' AND billing_month LIKE ?
  `).get(`${thisYear}-%`)?.total || 0;

  const partnerCount = db.prepare(`SELECT COUNT(*) AS cnt FROM partners WHERE status='active'`).get()?.cnt || 0;
  const pendingCount = db.prepare(`SELECT COUNT(*) AS cnt FROM invoices WHERE status='pending'`).get()?.cnt || 0;

  const topPartners = db.prepare(`
    SELECT p.company_name, SUM(i.total_amount) AS total
    FROM invoices i JOIN partners p ON p.id = i.partner_id
    WHERE i.status='confirmed' AND i.billing_month LIKE ?
    GROUP BY p.id ORDER BY total DESC LIMIT 5
  `).all(`${thisYear}-%`);

  const recentInvoices = db.prepare(`
    SELECT i.id, i.billing_month, i.total_amount, i.status, p.company_name as partner_name
    FROM invoices i LEFT JOIN partners p ON p.id = i.partner_id
    ORDER BY i.created_at DESC LIMIT 10
  `).all();

  res.json({ thisMonth, monthlyTotal, yearlyTotal, partnerCount, pendingCount, topPartners, recentInvoices });
});

// ── 起動 ──────────────────────────────────────────────────────────────────────

app.listen(PORT, () => {
  console.log(`\nアライアンスパートナー管理システム 起動中`);
  console.log(`http://localhost:${PORT}\n`);
});
