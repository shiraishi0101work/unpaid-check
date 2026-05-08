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

// ── パートナー取扱商材 ────────────────────────────────────────────────────────

app.get('/api/partners/:id/products', (req, res) => {
  const db = getDB();
  const linked = db.prepare('SELECT product_id FROM partner_products WHERE partner_id = ?').all(req.params.id);
  res.json(linked.map(r => r.product_id));
});

app.put('/api/partners/:id/products', (req, res) => {
  const db = getDB();
  const { product_ids } = req.body; // number[]
  db.prepare('DELETE FROM partner_products WHERE partner_id = ?').run(req.params.id);
  if (product_ids && product_ids.length > 0) {
    const stmt = db.prepare('INSERT OR IGNORE INTO partner_products (partner_id, product_id) VALUES (?, ?)');
    for (const pid of product_ids) stmt.run(req.params.id, pid);
  }
  res.json({ message: '更新しました' });
});

// ── パートナー契約書 ──────────────────────────────────────────────────────────

app.get('/api/partners/:id/contracts', (req, res) => {
  const db = getDB();
  const contracts = db.prepare(
    'SELECT * FROM partner_contracts WHERE partner_id = ? ORDER BY created_at DESC'
  ).all(req.params.id);
  res.json(contracts);
});

app.post('/api/partners/:id/contracts', uploadContract.single('file'), async (req, res) => {
  const db = getDB();
  if (!req.file) return res.status(400).json({ error: 'ファイルがありません' });

  let extractedText = '';
  let extractedDate = null;
  try {
    const pdfParse = require('pdf-parse');
    const buffer = fs.readFileSync(req.file.path);
    const data = await pdfParse(buffer);
    extractedText = data.text || '';
    extractedDate = extractContractDate(extractedText);
  } catch (e) {
    console.error('契約書PDF解析エラー:', e.message);
  }

  const result = db.prepare(`
    INSERT INTO partner_contracts (partner_id, file_name, file_path, contract_date, extracted_text)
    VALUES (?, ?, ?, ?, ?)
  `).run(
    req.params.id,
    req.file.originalname,
    req.file.path,
    extractedDate,
    extractedText.slice(0, 5000)
  );

  res.json({
    id: result.lastInsertRowid,
    extracted_date: extractedDate,
    message: extractedDate
      ? `締結日を自動検出しました: ${extractedDate}`
      : '締結日を自動検出できませんでした。手動で入力してください。'
  });
});

app.put('/api/partners/:id/contracts/:contractId', (req, res) => {
  const db = getDB();
  const { contract_date, notes } = req.body;
  db.prepare('UPDATE partner_contracts SET contract_date=?, notes=? WHERE id=? AND partner_id=?')
    .run(contract_date, notes, req.params.contractId, req.params.id);
  res.json({ message: '更新しました' });
});

app.delete('/api/partners/:id/contracts/:contractId', (req, res) => {
  const db = getDB();
  const row = db.prepare('SELECT file_path FROM partner_contracts WHERE id=? AND partner_id=?')
    .get(req.params.contractId, req.params.id);
  if (row?.file_path && fs.existsSync(row.file_path)) {
    try { fs.unlinkSync(row.file_path); } catch {}
  }
  db.prepare('DELETE FROM partner_contracts WHERE id=? AND partner_id=?')
    .run(req.params.contractId, req.params.id);
  res.json({ message: '削除しました' });
});

app.get('/api/partners/:id/contracts/:contractId/download', (req, res) => {
  const db = getDB();
  const row = db.prepare('SELECT * FROM partner_contracts WHERE id=? AND partner_id=?')
    .get(req.params.contractId, req.params.id);
  if (!row) return res.status(404).json({ error: '見つかりません' });
  if (!fs.existsSync(row.file_path)) return res.status(404).json({ error: 'ファイルが存在しません' });
  res.download(row.file_path, row.file_name);
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

// ── PDF解析ユーティリティ ────────────────────────────────────────────────────

// 明細行を抽出（サジェスト請求書フォーマット対応）
function extractInvoiceItems(text) {
  const items = [];
  const lines = text.split('\n').map(l => l.trim()).filter(l => l);
  const SKIP = /^(納品日|品目|Google\s|税率|小計|合計|消費税|振込先|備考|請求書|株式会社Dell|\d+\s*\/\s*\d+)/;

  for (let i = 0; i < lines.length - 2; i++) {
    const serviceMatch = lines[i].match(/^(Google\s+(?:サジェスト|関連語)【[^】]+】)$/);
    if (!serviceMatch) continue;

    const clientName = lines[i + 1];
    const priceLine  = lines[i + 2];

    // クライアント名行がヘッダー行でないことを確認
    if (SKIP.test(clientName)) continue;

    // "11,0001ヶ月11,000" or "14,0001ヶ月14,000" のパターン
    const priceMatch = priceLine.match(/^([\d,]+)\d+ヶ月([\d,]+)$/);
    if (!priceMatch) continue;

    const unitPrice = parseInt(priceMatch[1].replace(/,/g, ''));
    const amount    = parseInt(priceMatch[2].replace(/,/g, ''));

    items.push({
      description: `${serviceMatch[1]} / ${clientName}`,
      client_name: clientName,
      service_type: serviceMatch[1],
      quantity:   1,
      unit_price: unitPrice,
      amount:     amount,
    });
    i += 2;
  }
  return items;
}

// 宛先（代理店名）抽出: "株式会社アーク御中" → "株式会社アーク"
function extractPartnerNameFromText(text) {
  const m = text.match(/^(.+?)御中$/m);
  return m ? m[1].trim() : null;
}

// 請求月抽出: 件名"4月分〜" + 請求日の年 → "2026-04"
function extractBillingMonth(text) {
  const subjectMatch = text.match(/件名[：:]\s*(\d+)月分/);
  const dateMatch    = text.match(/請求日[：:]\s*(\d{4})\/(\d{2})\/(\d{2})/);
  if (subjectMatch && dateMatch) {
    return `${dateMatch[1]}-${String(subjectMatch[1]).padStart(2, '0')}`;
  }
  // フォールバック
  const m = text.match(/(\d{4})[年\/\-](\d{1,2})(?:[月\/\-])/);
  return m ? `${m[1]}-${String(m[2]).padStart(2, '0')}` : '';
}

async function parseInvoiceFile(file, partners) {
  let extractedText = '';

  if (file && file.mimetype === 'application/pdf') {
    try {
      const pdfParse = require('pdf-parse');
      const buffer = fs.readFileSync(file.path);
      const data = await pdfParse(buffer);
      extractedText = data.text || '';
    } catch (e) {
      console.error('PDF解析エラー:', e.message);
    }
  }

  // 請求金額（ご請求金額 優先）
  let guessedAmount = 0;
  const amountMatch = extractedText.match(/ご請求金額\s*([\d,，]+)\s*円/) ||
                      extractedText.match(/(?:合計|請求金額)[^\d]*([0-9,，]+)/);
  if (amountMatch) guessedAmount = parseInt(amountMatch[1].replace(/[,，]/g, '')) || 0;

  // 請求月（件名 + 請求日の年 優先）
  const guessedMonth = extractBillingMonth(extractedText);

  // 代理店名（御中の前から取得 → DBと照合）
  let guessedPartnerId = null;
  const nameFromPdf = extractPartnerNameFromText(extractedText);
  if (nameFromPdf) {
    // 完全一致 or 部分一致
    const hit = partners.find(p => p.company_name === nameFromPdf) ||
                partners.find(p => nameFromPdf.includes(p.company_name) || p.company_name.includes(nameFromPdf));
    if (hit) guessedPartnerId = hit.id;
  }
  // フォールバック: テキスト全体で会社名検索
  if (!guessedPartnerId) {
    for (const p of partners) {
      if (extractedText.includes(p.company_name)) { guessedPartnerId = p.id; break; }
    }
  }

  // 明細行の抽出
  const extractedItems = extractInvoiceItems(extractedText);

  // 請求書番号・支払期限
  const invoiceNoMatch  = extractedText.match(/請求書番号[：:]\s*(\d+)/);
  const dueDateMatch    = extractedText.match(/お支払期限[：:]\s*(\d{4}\/\d{2}\/\d{2})/);

  return {
    extractedText,
    guessedAmount,
    guessedMonth,
    guessedPartnerId,
    extractedItems,
    invoiceNo: invoiceNoMatch?.[1] || null,
    dueDate:   dueDateMatch?.[1]   || null,
  };
}

// 明細をDBに一括保存するヘルパー
function saveInvoiceItems(db, invoiceId, items) {
  if (!items || items.length === 0) return;
  const stmt = db.prepare(`
    INSERT INTO invoice_items (invoice_id, product_id, description, quantity, unit_price, amount)
    VALUES (?, NULL, ?, ?, ?, ?)
  `);
  for (const item of items) {
    stmt.run(invoiceId, item.description, item.quantity || 1, item.unit_price || 0, item.amount || 0);
  }
}

// PDF 一括アップロード（最大20枚）
app.post('/api/invoices/upload-bulk', upload.array('files', 20), async (req, res) => {
  const db = getDB();
  if (!req.files || req.files.length === 0) return res.status(400).json({ error: 'ファイルがありません' });

  const partners = db.prepare('SELECT id, company_name FROM partners WHERE status = ?').all('active');
  const results = [];

  for (const file of req.files) {
    const { extractedText, guessedAmount, guessedMonth, guessedPartnerId, extractedItems, invoiceNo } =
      await parseInvoiceFile(file, partners);

    const result = db.prepare(`
      INSERT INTO invoices (file_name, file_path, billing_month, total_amount, extracted_text, partner_id, status, notes)
      VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
    `).run(file.originalname, file.path, guessedMonth, guessedAmount,
           extractedText.slice(0, 5000), guessedPartnerId,
           invoiceNo ? `請求書番号: ${invoiceNo}` : null);

    const invoiceId = result.lastInsertRowid;
    saveInvoiceItems(db, invoiceId, extractedItems);

    results.push({
      id: invoiceId,
      file_name: file.originalname,
      guessed_month: guessedMonth,
      guessed_amount: guessedAmount,
      guessed_partner_id: guessedPartnerId,
      guessed_partner_name: partners.find(p => p.id === guessedPartnerId)?.company_name || null,
      items_count: extractedItems.length,
    });
  }

  res.json({ count: results.length, results });
});

// PDF アップロード → テキスト抽出（単体）
app.post('/api/invoices/upload', upload.single('file'), async (req, res) => {
  const db = getDB();
  const partners = db.prepare('SELECT id, company_name FROM partners WHERE status = ?').all('active');
  const { extractedText, guessedAmount, guessedMonth, guessedPartnerId } = await parseInvoiceFile(req.file, partners);

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
