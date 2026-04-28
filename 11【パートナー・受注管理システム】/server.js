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
    // Preserve original name in metadata, use safe filename on disk
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
  const result = db.prepare(`
    INSERT INTO partners (company_name, contract_date, rep_name, rep_email, rep_phone, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `).run(company_name, contract_date || null, rep_name || null, rep_email || null, rep_phone || null, status || 'active', notes || null);
  res.json(db.prepare('SELECT * FROM partners WHERE id = ?').get(result.lastInsertRowid));
});

app.put('/api/partners/:id', (req, res) => {
  const db = getDB();
  const { company_name, contract_date, rep_name, rep_email, rep_phone, status, notes } = req.body;
  if (!company_name) return res.status(400).json({ error: '企業名は必須です' });
  db.prepare(`
    UPDATE partners SET company_name=?, contract_date=?, rep_name=?, rep_email=?, rep_phone=?, status=?, notes=?, updated_at=CURRENT_TIMESTAMP
    WHERE id=?
  `).run(company_name, contract_date || null, rep_name || null, rep_email || null, rep_phone || null, status, notes || null, req.params.id);
  res.json(db.prepare('SELECT * FROM partners WHERE id = ?').get(req.params.id));
});

app.delete('/api/partners/:id', (req, res) => {
  const db = getDB();
  db.prepare('DELETE FROM partners WHERE id = ?').run(req.params.id);
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
  const result = db.prepare(`
    INSERT INTO products (name, description, initial_count) VALUES (?, ?, ?)
  `).run(name, description || null, parseInt(initial_count) || 0);
  res.json(db.prepare('SELECT * FROM products WHERE id = ?').get(result.lastInsertRowid));
});

app.put('/api/products/:id', (req, res) => {
  const db = getDB();
  const { name, description, initial_count } = req.body;
  if (!name) return res.status(400).json({ error: '商品名は必須です' });
  db.prepare(`
    UPDATE products SET name=?, description=?, initial_count=?, updated_at=CURRENT_TIMESTAMP WHERE id=?
  `).run(name, description || null, parseInt(initial_count) || 0, req.params.id);
  res.json(db.prepare('SELECT * FROM products WHERE id = ?').get(req.params.id));
});

app.delete('/api/products/:id', (req, res) => {
  const db = getDB();
  db.prepare('DELETE FROM products WHERE id = ?').run(req.params.id);
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
    db.prepare('UPDATE partner_products SET order_count=?, updated_at=CURRENT_TIMESTAMP WHERE id=?')
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
  const { order_count } = req.body;
  db.prepare('UPDATE partner_products SET order_count=?, updated_at=CURRENT_TIMESTAMP WHERE id=?')
    .run(parseInt(order_count) || 0, req.params.id);
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
  const db = getDB();
  db.prepare('DELETE FROM partner_products WHERE id = ?').run(req.params.id);
  res.json({ success: true });
});

// ─── Contracts ────────────────────────────────────────────────────────────────

app.post('/api/contracts/upload', upload.single('pdf'), async (req, res) => {
  try {
    if (!req.file) return res.status(400).json({ error: 'PDFファイルが必要です' });
    const { partner_id } = req.body;
    const file = req.file;
    let extractedData = {};

    if (process.env.ANTHROPIC_API_KEY) {
      try {
        const Anthropic = require('@anthropic-ai/sdk');
        const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
        const pdfBase64 = fs.readFileSync(file.path).toString('base64');

        const response = await client.messages.create({
          model: 'claude-opus-4-6',
          max_tokens: 1024,
          messages: [{
            role: 'user',
            content: [
              { type: 'document', source: { type: 'base64', media_type: 'application/pdf', data: pdfBase64 } },
              {
                type: 'text',
                text: `この契約書PDFから以下の情報をJSON形式で抽出してください。
不明な項目はnullにしてください。

{
  "company_name": "契約先の企業名（法人格含む正式名称）",
  "contract_date": "契約日（YYYY-MM-DD形式）",
  "representative": "代表者名または担当者名",
  "address": "住所",
  "contract_type": "契約の種類（販売代理店契約など）",
  "contract_period": "契約期間"
}

JSONのみ返してください。説明文は不要です。`
              }
            ]
          }]
        });

        const text = response.content[0].text;
        const jsonMatch = text.match(/\{[\s\S]*\}/);
        if (jsonMatch) extractedData = JSON.parse(jsonMatch[0]);
      } catch (e) {
        console.error('Claude API error:', e.message);
      }
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

// ─── Dashboard stats ──────────────────────────────────────────────────────────

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
  console.log(`\n✅ パートナー・受注管理システム起動\n   http://localhost:${PORT}\n`);
});
