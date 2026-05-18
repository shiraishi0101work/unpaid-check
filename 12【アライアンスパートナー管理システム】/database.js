const { DatabaseSync } = require('node:sqlite');
const path = require('path');

let db;

function initDB() {
  db = new DatabaseSync(path.join(__dirname, 'data.db'));

  db.exec(`
    -- パートナー（代理店）
    CREATE TABLE IF NOT EXISTS partners (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      company_name TEXT NOT NULL,
      contact_name TEXT,
      contact_email TEXT,
      contact_phone TEXT,
      contract_start TEXT,
      status TEXT DEFAULT 'active',
      notes TEXT,
      created_at TEXT DEFAULT (datetime('now','localtime')),
      updated_at TEXT DEFAULT (datetime('now','localtime'))
    );

    -- 商材
    CREATE TABLE IF NOT EXISTS products (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      code TEXT,
      unit_price INTEGER DEFAULT 0,
      description TEXT,
      created_at TEXT DEFAULT (datetime('now','localtime')),
      updated_at TEXT DEFAULT (datetime('now','localtime'))
    );

    -- 請求書
    CREATE TABLE IF NOT EXISTS invoices (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      partner_id INTEGER,
      file_name TEXT,
      file_path TEXT,
      billing_month TEXT,
      total_amount INTEGER DEFAULT 0,
      extracted_text TEXT,
      status TEXT DEFAULT 'pending',
      notes TEXT,
      created_at TEXT DEFAULT (datetime('now','localtime')),
      updated_at TEXT DEFAULT (datetime('now','localtime')),
      FOREIGN KEY (partner_id) REFERENCES partners(id) ON DELETE SET NULL
    );

    -- 請求明細
    CREATE TABLE IF NOT EXISTS invoice_items (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      invoice_id INTEGER NOT NULL,
      product_id INTEGER,
      description TEXT,
      quantity INTEGER DEFAULT 1,
      unit_price INTEGER DEFAULT 0,
      amount INTEGER DEFAULT 0,
      FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
      FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
    );

    -- パートナー契約書
    CREATE TABLE IF NOT EXISTS partner_contracts (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      partner_id INTEGER NOT NULL,
      file_name TEXT NOT NULL,
      file_path TEXT NOT NULL,
      contract_date TEXT,
      extracted_text TEXT,
      notes TEXT,
      created_at TEXT DEFAULT (datetime('now','localtime')),
      FOREIGN KEY (partner_id) REFERENCES partners(id) ON DELETE CASCADE
    );

    -- パートナー取扱商材
    CREATE TABLE IF NOT EXISTS partner_products (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      partner_id INTEGER NOT NULL,
      product_id INTEGER NOT NULL,
      created_at TEXT DEFAULT (datetime('now','localtime')),
      FOREIGN KEY (partner_id) REFERENCES partners(id) ON DELETE CASCADE,
      FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
      UNIQUE(partner_id, product_id)
    );

    -- エンド（直接売上先）
    CREATE TABLE IF NOT EXISTS clients (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      company_name TEXT NOT NULL,
      contact_name TEXT,
      contact_email TEXT,
      contact_phone TEXT,
      notes TEXT,
      status TEXT DEFAULT 'active',
      created_at TEXT DEFAULT (datetime('now','localtime')),
      updated_at TEXT DEFAULT (datetime('now','localtime'))
    );

    -- エンド契約書
    CREATE TABLE IF NOT EXISTS client_contracts (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      client_id INTEGER NOT NULL,
      file_name TEXT NOT NULL,
      file_path TEXT NOT NULL,
      contract_date TEXT,
      extracted_text TEXT,
      notes TEXT,
      doc_type TEXT DEFAULT '契約書',
      created_at TEXT DEFAULT (datetime('now','localtime')),
      FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
    );

    -- PDF名→パートナー/エンド 学習マッピング
    CREATE TABLE IF NOT EXISTS invoice_name_map (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      extracted_name TEXT NOT NULL UNIQUE,
      partner_id INTEGER,
      client_id INTEGER,
      created_at TEXT DEFAULT (datetime('now','localtime')),
      FOREIGN KEY (partner_id) REFERENCES partners(id) ON DELETE SET NULL,
      FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL
    );
  `);

  // マイグレーション: doc_type カラム追加
  try { db.exec(`ALTER TABLE partner_contracts ADD COLUMN doc_type TEXT DEFAULT '契約書'`); } catch {}
  // マイグレーション: products.category カラム追加
  try { db.exec(`ALTER TABLE products ADD COLUMN category TEXT`); } catch {}
  // マイグレーション: products.price_type カラム追加
  try { db.exec(`ALTER TABLE products ADD COLUMN price_type TEXT DEFAULT 'monthly'`); } catch {}
  // マイグレーション: products.cost_price カラム追加
  try { db.exec(`ALTER TABLE products ADD COLUMN cost_price INTEGER DEFAULT 0`); } catch {}
  // マイグレーション: invoices.client_id カラム追加
  try { db.exec(`ALTER TABLE invoices ADD COLUMN client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL`); } catch {}

  return db;
}

function getDB() {
  if (!db) initDB();
  return db;
}

module.exports = { initDB, getDB };
