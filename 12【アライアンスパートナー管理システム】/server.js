require('dotenv').config();
const express    = require('express');
const multer     = require('multer');
const path       = require('path');
const fs         = require('fs');
const basicAuth  = require('express-basic-auth');
const { initDB, getDB } = require('./database');

const app  = express();
const PORT = process.env.PORT || 3001;

// ── Basic認証（外部公開時のパスワード保護）──────────────────────────────────
const AUTH_USER = process.env.AUTH_USER || 'admin';
const AUTH_PASS = process.env.AUTH_PASS || 'della2024';
app.use(basicAuth({
  users: { [AUTH_USER]: AUTH_PASS },
  challenge: true,
  realm: 'Alliance Partner System',
}));

app.use(express.json());
app.use(express.static('public'));

// ── ファイル名デコードユーティリティ（multerはLatin-1で受け取るためUTF-8に変換）────
function decodeFileName(name) {
  try {
    return Buffer.from(name, 'latin1').toString('utf8');
  } catch {
    return name;
  }
}

// ── PDF アップロード設定 ──────────────────────────────────────────────────────
const makeStorage = (subdir) => multer.diskStorage({
  destination: (req, file, cb) => {
    file.originalname = decodeFileName(file.originalname);
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

// ── 契約書PDFから締結日のみ抽出（他は手入力）────────────────────────────────
function extractPartnerInfoFromText(text) {
  return { contractDate: extractContractDate(text) };
}

initDB();

// ── パートナー ────────────────────────────────────────────────────────────────

// ── 契約書PDF一括読み込み → パートナー情報抽出（/api/partners/:id より先に定義）
const uploadPDFBulk = multer({
  storage: makeStorage('tmp_contracts'),
  fileFilter: (req, file, cb) => {
    if (file.mimetype === 'application/pdf') cb(null, true);
    else cb(new Error('PDFファイルのみ'));
  },
  limits: { fileSize: 30 * 1024 * 1024 }
});

app.post('/api/partners/import-pdf-preview', uploadPDFBulk.array('files', 30), async (req, res) => {
  if (!req.files || req.files.length === 0) return res.status(400).json({ error: 'ファイルがありません' });

  const results = [];
  for (const file of req.files) {
    let text = '';
    try {
      const buffer = fs.readFileSync(file.path);
      text = await parsePDFText(buffer);
    } catch (e) {
      console.error('PDF解析エラー:', e.message);
    }

    const { contractDate } = extractPartnerInfoFromText(text);
    results.push({
      file_name:      file.originalname,
      file_path:      file.path,
      company_name:   '',
      contact_name:   '',
      contact_phone:  '',
      contact_email:  '',
      contract_start: contractDate || '',
      extracted_text: text.slice(0, 5000),
    });
  }
  res.json(results);
});

app.post('/api/partners/import-pdf-save', express.json(), async (req, res) => {
  const db = getDB();
  const { entries } = req.body; // [{ company_name, contact_name, ... , file_path, file_name }]
  if (!entries || entries.length === 0) return res.status(400).json({ error: 'データがありません' });

  const results = [];
  for (const e of entries) {
    if (!e.company_name) { results.push({ skipped: true, file_name: e.file_name }); continue; }
    const r = db.prepare(`
      INSERT INTO partners (company_name, contact_name, contact_email, contact_phone, contract_start, status, notes)
      VALUES (?, ?, ?, ?, ?, 'active', ?)
    `).run(e.company_name, e.contact_name || null, e.contact_email || null,
           e.contact_phone || null, e.contract_start || null, null);
    const partnerId = r.lastInsertRowid;

    // 契約書をpartner_contractsに紐付け
    if (e.file_path && fs.existsSync(e.file_path)) {
      // 保存先を正式フォルダに移動
      const destDir = path.join(__dirname, 'uploads', 'contracts');
      if (!fs.existsSync(destDir)) fs.mkdirSync(destDir, { recursive: true });
      const destPath = path.join(destDir, path.basename(e.file_path));
      fs.renameSync(e.file_path, destPath);

      db.prepare(`
        INSERT INTO partner_contracts (partner_id, file_name, file_path, contract_date, extracted_text, doc_type)
        VALUES (?, ?, ?, ?, ?, '契約書')
      `).run(partnerId, e.file_name, destPath, e.contract_start || null, e.extracted_text?.slice(0, 5000) || '');
    }
    results.push({ id: partnerId, company_name: e.company_name });
  }
  res.json({ count: results.filter(r => !r.skipped).length, results });
});

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

// 請求グレード（A/B/C）を計算してステータスを自動反映
function computePartnerStatuses(db, partners) {
  const now = new Date();
  const months6 = [];
  for (let i = 0; i < 6; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    months6.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`);
  }
  const months3 = months6.slice(0, 3);
  const oldest  = months6[5];

  // 直近6ヶ月の (partner_id, billing_month) 一覧を一括取得
  const recentRows = db.prepare(`
    SELECT DISTINCT partner_id, billing_month FROM invoices
    WHERE status='confirmed' AND billing_month >= ? AND partner_id IS NOT NULL
  `).all(oldest);
  const recentMap = {};
  for (const r of recentRows) {
    if (!recentMap[r.partner_id]) recentMap[r.partner_id] = new Set();
    recentMap[r.partner_id].add(r.billing_month);
  }

  // 一度でも請求があるパートナーID集合
  const everBilled = new Set(
    db.prepare("SELECT DISTINCT partner_id FROM invoices WHERE status='confirmed' AND partner_id IS NOT NULL")
      .all().map(r => r.partner_id)
  );

  return partners.map(p => {
    const pMonths = recentMap[p.id] || new Set();
    const cnt3 = months3.filter(m => pMonths.has(m)).length;
    const cnt6 = months6.filter(m => pMonths.has(m)).length;

    let grade, status;
    if (!everBilled.has(p.id)) {
      grade = null; status = 'inactive'; // 請求書未発生のパートナーはinactive
    } else if (cnt3 === 3) {
      grade = 'A'; status = 'active';
    } else if (cnt3 >= 1) {
      grade = 'B'; status = 'active';
    } else {
      grade = 'C'; status = 'inactive';
    }

    // DBのstatusも更新（差分があるときだけ）
    if (p.status !== status) {
      db.prepare("UPDATE partners SET status=? WHERE id=?").run(status, p.id);
    }

    return { ...p, status, grade };
  });
}

app.get('/api/partners', (req, res) => {
  const db = getDB();
  const { search } = req.query;
  let q = 'SELECT * FROM partners WHERE 1=1';
  const params = [];
  if (search) { q += ' AND (company_name LIKE ? OR contact_name LIKE ?)'; params.push(`%${search}%`, `%${search}%`); }
  q += ' ORDER BY company_name ASC';
  let partners = db.prepare(q).all(...params);

  // グレード計算 → ステータス自動反映
  partners = computePartnerStatuses(db, partners);

  // statusフィルターはグレード計算後に適用
  const { status } = req.query;
  if (status) partners = partners.filter(p => p.status === status);

  res.json(partners);
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
  `).run(
    company_name ?? null,
    contact_name ?? null,
    contact_email ?? null,
    contact_phone ?? null,
    contract_start ?? null,
    status ?? 'active',
    notes ?? null,
    req.params.id
  );
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

  const docType = req.body.doc_type || '契約書';

  let extractedText = '';
  let extractedDate = null;
  try {
    const buffer = fs.readFileSync(req.file.path);
    extractedText = await parsePDFText(buffer);
    extractedDate = extractContractDate(extractedText);
  } catch (e) {
    console.error('契約書PDF解析エラー:', e.message);
  }

  const result = db.prepare(`
    INSERT INTO partner_contracts (partner_id, file_name, file_path, contract_date, extracted_text, doc_type)
    VALUES (?, ?, ?, ?, ?, ?)
  `).run(
    req.params.id,
    req.file.originalname,
    req.file.path,
    extractedDate,
    extractedText.slice(0, 5000),
    docType
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

// PDF インライン表示（ブラウザで直接開く）
app.get('/api/partners/:id/contracts/:contractId/view', (req, res) => {
  const db = getDB();
  const row = db.prepare('SELECT * FROM partner_contracts WHERE id=? AND partner_id=?')
    .get(req.params.contractId, req.params.id);
  if (!row) return res.status(404).send('見つかりません');
  if (!fs.existsSync(row.file_path)) return res.status(404).send('ファイルが存在しません');
  res.setHeader('Content-Type', 'application/pdf');
  res.setHeader('Content-Disposition', `inline; filename*=UTF-8''${encodeURIComponent(row.file_name)}`);
  res.sendFile(path.resolve(row.file_path));
});

// ── 商材 ──────────────────────────────────────────────────────────────────────

// CSV一括取込（/api/products/:id より先に定義）
app.post('/api/products/import-csv', express.json(), (req, res) => {
  const db = getDB();
  const { category, products } = req.body;
  if (!products || products.length === 0) return res.status(400).json({ error: 'データがありません' });

  const findStmt   = db.prepare(`SELECT id FROM products WHERE name = ?`);
  const insertStmt = db.prepare(`
    INSERT INTO products (name, unit_price, price_type, cost_price, description, category) VALUES (?, ?, ?, ?, ?, ?)
  `);
  const updateStmt = db.prepare(`
    UPDATE products SET unit_price=?, price_type=?, cost_price=?, description=?, category=?, updated_at=datetime('now','localtime')
    WHERE id=?
  `);

  let inserted = 0, updated = 0, skipped = 0;
  const errors = [];
  for (const p of products) {
    if (!p.name) { skipped++; continue; }
    try {
      const existing = findStmt.get(p.name);
      if (existing) {
        updateStmt.run(p.unit_price || 0, p.price_type || 'monthly', p.cost_price || 0, p.description || null, category || null, existing.id);
        updated++;
      } else {
        insertStmt.run(p.name, p.unit_price || 0, p.price_type || 'monthly', p.cost_price || 0, p.description || null, category || null);
        inserted++;
      }
    } catch (e) {
      errors.push(e.message);
      skipped++;
    }
  }
  res.json({ message: `新規${inserted}件・更新${updated}件（スキップ: ${skipped}件）`, inserted, updated, skipped, errors });
});

app.get('/api/products', (req, res) => {
  const db = getDB();
  const { search, category } = req.query;
  let q = 'SELECT * FROM products WHERE 1=1';
  const params = [];
  if (search) { q += ' AND (name LIKE ? OR code LIKE ? OR category LIKE ?)'; params.push(`%${search}%`, `%${search}%`, `%${search}%`); }
  if (category) { q += ' AND category = ?'; params.push(category); }
  q += ' ORDER BY category ASC, name ASC';
  res.json(db.prepare(q).all(...params));
});

app.post('/api/products', (req, res) => {
  const db = getDB();
  const { name, unit_price, price_type, cost_price, description, category } = req.body;
  if (!name) return res.status(400).json({ error: '商材名は必須です' });
  const result = db.prepare(`
    INSERT INTO products (name, unit_price, price_type, cost_price, description, category) VALUES (?, ?, ?, ?, ?, ?)
  `).run(name, unit_price || 0, price_type || 'monthly', cost_price ?? 0, description ?? null, category ?? null);
  res.json({ id: result.lastInsertRowid, message: '登録しました' });
});

app.put('/api/products/:id', (req, res) => {
  const db = getDB();
  const { name, unit_price, price_type, cost_price, description, category } = req.body;
  db.prepare(`
    UPDATE products SET name=?, unit_price=?, price_type=?, cost_price=?, description=?, category=?, updated_at=datetime('now','localtime')
    WHERE id=?
  `).run(name ?? null, unit_price || 0, price_type || 'monthly', cost_price ?? 0, description ?? null, category ?? null, req.params.id);
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

async function parsePDFText(buffer) {
  const pdfjsLib = require('pdfjs-dist/legacy/build/pdf.js');
  const cmapUrl = path.join(require.resolve('pdfjs-dist/package.json'), '..', 'cmaps') + path.sep;

  const loadingTask = pdfjsLib.getDocument({
    data: new Uint8Array(buffer),
    cMapUrl: cmapUrl,
    cMapPacked: true,
    disableWorker: true,
  });

  const pdfDoc = await loadingTask.promise;
  let text = '';
  for (let i = 1; i <= pdfDoc.numPages; i++) {
    const page = await pdfDoc.getPage(i);
    const content = await page.getTextContent();
    text += content.items.map(item => item.str).join('') + '\n';
  }
  return text;
}

async function parseInvoiceFile(file, partners) {
  let extractedText = '';

  if (file && file.mimetype === 'application/pdf') {
    try {
      const buffer = fs.readFileSync(file.path);
      extractedText = await parsePDFText(buffer);
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
  const { extractedText, guessedAmount, guessedMonth, guessedPartnerId, extractedItems, invoiceNo, dueDate } =
    await parseInvoiceFile(req.file, partners);

  const result = db.prepare(`
    INSERT INTO invoices (file_name, file_path, billing_month, total_amount, extracted_text, partner_id, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
  `).run(
    req.file ? req.file.originalname : '手動入力',
    req.file ? req.file.path : '',
    guessedMonth,
    guessedAmount,
    extractedText.slice(0, 5000),
    guessedPartnerId,
    invoiceNo ? `請求書番号: ${invoiceNo}` : null
  );

  const invoiceId = result.lastInsertRowid;
  saveInvoiceItems(db, invoiceId, extractedItems);

  res.json({
    id: invoiceId,
    guessed_month: guessedMonth,
    guessed_amount: guessedAmount,
    guessed_partner_id: guessedPartnerId,
    extracted_text: extractedText.slice(0, 2000),
    items_count: extractedItems.length,
    invoice_no: invoiceNo,
    due_date: dueDate,
    message: `アップロード完了。明細${extractedItems.length}件を自動取得しました。内容を確認して保存してください。`
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

// ── 分析グラフ用 API ──────────────────────────────────────────────────────────

app.get('/api/analytics', (req, res) => {
  const db = getDB();
  const year = req.query.year || new Date().getFullYear().toString();
  const thisYear = parseInt(year);

  // ① 月別 累計代理店数 / 新規登録数 / ② 月別 請求代理店数（選択年 × 12ヶ月）
  const monthlyPartners = [];
  for (let m = 1; m <= 12; m++) {
    const month = `${year}-${String(m).padStart(2, '0')}`;
    // 累計: その月末時点での登録済み総数
    const total = db.prepare(
      "SELECT COUNT(*) as cnt FROM partners WHERE strftime('%Y-%m', created_at) <= ?"
    ).get(month)?.cnt || 0;
    // 新規: その月に新規登録されたパートナー数
    const newCount = db.prepare(
      "SELECT COUNT(*) as cnt FROM partners WHERE strftime('%Y-%m', created_at) = ?"
    ).get(month)?.cnt || 0;
    // 請求あり: その月に確定請求書があるパートナー数
    const active = db.prepare(
      "SELECT COUNT(DISTINCT partner_id) as cnt FROM invoices WHERE status='confirmed' AND billing_month=? AND partner_id IS NOT NULL"
    ).get(month)?.cnt || 0;
    monthlyPartners.push({ month, total, new: newCount, active });
  }

  // ⑤ 月別売上合計（選択年）
  const monthlyRevenue = [];
  for (let m = 1; m <= 12; m++) {
    const month = `${year}-${String(m).padStart(2, '0')}`;
    const amount = db.prepare(
      "SELECT COALESCE(SUM(total_amount),0) as s FROM invoices WHERE status='confirmed' AND billing_month=?"
    ).get(month)?.s || 0;
    monthlyRevenue.push({ month, amount });
  }

  // ④ 商品別売上 年間合計（円グラフ・棒グラフ用）
  const productRevenue = db.prepare(`
    SELECT
      COALESCE(pr.name, '（未紐付け）') as product_name,
      COALESCE(SUM(ii.amount), 0) as amount
    FROM invoice_items ii
    LEFT JOIN products pr ON pr.id = ii.product_id
    INNER JOIN invoices i ON i.id = ii.invoice_id
    WHERE i.status = 'confirmed' AND i.billing_month LIKE ?
    GROUP BY COALESCE(pr.name, '（未紐付け）')
    ORDER BY amount DESC
  `).all(`${year}-%`);

  // ④ 商品別売上 月次内訳（積み上げ棒グラフ用）
  const rawMonthlyProduct = db.prepare(`
    SELECT
      i.billing_month,
      COALESCE(pr.name, '（未紐付け）') as product_name,
      COALESCE(SUM(ii.amount), 0) as amount
    FROM invoice_items ii
    LEFT JOIN products pr ON pr.id = ii.product_id
    INNER JOIN invoices i ON i.id = ii.invoice_id
    WHERE i.status = 'confirmed' AND i.billing_month LIKE ?
    GROUP BY i.billing_month, COALESCE(pr.name, '（未紐付け）')
  `).all(`${year}-%`);

  // 月×商品の2次元マップに変換
  const productNames = [...new Set(rawMonthlyProduct.map(r => r.product_name))];
  const monthlyProductRevenue = {};
  for (const pName of productNames) {
    monthlyProductRevenue[pName] = Array(12).fill(0);
  }
  for (const row of rawMonthlyProduct) {
    const mIdx = parseInt(row.billing_month.split('-')[1]) - 1;
    if (!monthlyProductRevenue[row.product_name]) monthlyProductRevenue[row.product_name] = Array(12).fill(0);
    monthlyProductRevenue[row.product_name][mIdx] = row.amount;
  }

  // ③ 商品別受注数（新規/継続/解約）月ごとに partner×product の組み合わせで集計
  const prevDecKey = `${thisYear - 1}-12`;
  const monthSets = {};

  // 前年12月
  const prevDecItems = db.prepare(`
    SELECT DISTINCT i.partner_id, COALESCE(pr.name, '（未紐付け）') as product_name
    FROM invoice_items ii
    LEFT JOIN products pr ON pr.id = ii.product_id
    INNER JOIN invoices i ON i.id = ii.invoice_id
    WHERE i.status = 'confirmed' AND i.billing_month = ? AND i.partner_id IS NOT NULL
  `).all(prevDecKey);
  monthSets[prevDecKey] = new Set(prevDecItems.map(x => `${x.partner_id}::${x.product_name}`));

  for (let m = 1; m <= 12; m++) {
    const month = `${year}-${String(m).padStart(2, '0')}`;
    const items = db.prepare(`
      SELECT DISTINCT i.partner_id, COALESCE(pr.name, '（未紐付け）') as product_name
      FROM invoice_items ii
      LEFT JOIN products pr ON pr.id = ii.product_id
      INNER JOIN invoices i ON i.id = ii.invoice_id
      WHERE i.status = 'confirmed' AND i.billing_month = ? AND i.partner_id IS NOT NULL
    `).all(month);
    monthSets[month] = new Set(items.map(x => `${x.partner_id}::${x.product_name}`));
  }

  // 全商品名を収集
  const allProducts = new Set();
  for (let m = 1; m <= 12; m++) {
    const month = `${year}-${String(m).padStart(2, '0')}`;
    const prevMonth = m === 1 ? prevDecKey : `${year}-${String(m - 1).padStart(2, '0')}`;
    for (const key of [...(monthSets[month] || []), ...(monthSets[prevMonth] || [])]) {
      allProducts.add(key.split('::').slice(1).join('::'));
    }
  }

  const productOrderMap = {};
  for (const pName of allProducts) {
    productOrderMap[pName] = Array(12).fill(null).map(() => ({ new: 0, continued: 0, cancelled: 0 }));
  }

  for (let m = 1; m <= 12; m++) {
    const month = `${year}-${String(m).padStart(2, '0')}`;
    const prevMonth = m === 1 ? prevDecKey : `${year}-${String(m - 1).padStart(2, '0')}`;
    const thisSet = monthSets[month] || new Set();
    const prevSet = monthSets[prevMonth] || new Set();

    for (const key of thisSet) {
      const pName = key.split('::').slice(1).join('::');
      if (!productOrderMap[pName]) productOrderMap[pName] = Array(12).fill(null).map(() => ({ new: 0, continued: 0, cancelled: 0 }));
      if (prevSet.has(key)) productOrderMap[pName][m - 1].continued++;
      else                  productOrderMap[pName][m - 1].new++;
    }
    for (const key of prevSet) {
      const pName = key.split('::').slice(1).join('::');
      if (!thisSet.has(key)) {
        if (!productOrderMap[pName]) productOrderMap[pName] = Array(12).fill(null).map(() => ({ new: 0, continued: 0, cancelled: 0 }));
        productOrderMap[pName][m - 1].cancelled++;
      }
    }
  }

  res.json({
    year,
    monthly_partners: monthlyPartners,
    monthly_revenue: monthlyRevenue,
    product_revenue: productRevenue,
    monthly_product_revenue: monthlyProductRevenue,
    product_orders: productOrderMap,
  });
});

// パートナー稼働率（A/B/C）
app.get('/api/analytics/partner-activity', (req, res) => {
  const db = getDB();
  const now = new Date();

  const months6 = [];
  for (let i = 0; i < 6; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    months6.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`);
  }
  const months3 = months6.slice(0, 3);
  const oldest = months6[months6.length - 1];

  const partners = db.prepare('SELECT id, company_name, status FROM partners ORDER BY company_name ASC').all();

  const result = partners.map(p => {
    const invoiceMonths = db.prepare(`
      SELECT DISTINCT billing_month FROM invoices
      WHERE partner_id = ? AND status = 'confirmed' AND billing_month >= ?
    `).all(p.id, oldest).map(r => r.billing_month);

    const cnt3 = months3.filter(m => invoiceMonths.includes(m)).length;
    const cnt6 = months6.filter(m => invoiceMonths.includes(m)).length;

    const lastInvoice = db.prepare(
      "SELECT billing_month FROM invoices WHERE partner_id=? AND status='confirmed' ORDER BY billing_month DESC LIMIT 1"
    ).get(p.id)?.billing_month || null;

    // A=毎月(直近3ヶ月すべて), B=3ヶ月に1回(直近3ヶ月に1件以上), C=半年以上なし
    let grade;
    if (cnt6 === 0) grade = 'C';
    else if (cnt3 === 3) grade = 'A';
    else if (cnt3 >= 1) grade = 'B';
    else grade = 'C';

    return { id: p.id, company_name: p.company_name, status: p.status, grade, cnt3, cnt6, last_invoice: lastInvoice };
  });

  res.json(result);
});

// ── 起動 ──────────────────────────────────────────────────────────────────────

app.listen(PORT, () => {
  console.log(`\nアライアンスパートナー管理システム 起動中`);
  console.log(`http://localhost:${PORT}\n`);
});
