const { DatabaseSync } = require('node:sqlite');
const path = require('path');

let db;

function initDB() {
  db = new DatabaseSync(path.join(__dirname, 'data.db'));

  db.exec(`
    -- 自社情報
    CREATE TABLE IF NOT EXISTS my_company (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      company_name TEXT,
      postal_code TEXT,
      address TEXT,
      phone TEXT,
      fax TEXT,
      email TEXT,
      representative TEXT,
      bank_info TEXT,
      logo_path TEXT,
      notes TEXT,
      updated_at TEXT DEFAULT (datetime('now','localtime'))
    );

    -- 取引先
    CREATE TABLE IF NOT EXISTS clients (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      company_name TEXT NOT NULL,
      contact_name TEXT,
      contact_email TEXT,
      contact_phone TEXT,
      postal_code TEXT,
      address TEXT,
      notes TEXT,
      created_at TEXT DEFAULT (datetime('now','localtime')),
      updated_at TEXT DEFAULT (datetime('now','localtime'))
    );

    -- 画像ライブラリ
    CREATE TABLE IF NOT EXISTS images (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      file_name TEXT NOT NULL,
      file_path TEXT NOT NULL,
      mime_type TEXT,
      file_size INTEGER,
      tags TEXT,
      created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    -- 定型文
    CREATE TABLE IF NOT EXISTS templates (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL,
      content TEXT NOT NULL,
      category TEXT DEFAULT '一般',
      sort_order INTEGER DEFAULT 0,
      created_at TEXT DEFAULT (datetime('now','localtime')),
      updated_at TEXT DEFAULT (datetime('now','localtime'))
    );

    -- 書類アーカイブ
    CREATE TABLE IF NOT EXISTS documents (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL,
      client_id INTEGER,
      original_file_name TEXT,
      output_file_name TEXT,
      thumbnail TEXT,
      editor_state TEXT,
      notes TEXT,
      created_at TEXT DEFAULT (datetime('now','localtime')),
      updated_at TEXT DEFAULT (datetime('now','localtime')),
      FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL
    );
  `);

  return db;
}

function getDB() {
  if (!db) initDB();
  return db;
}

module.exports = { initDB, getDB };
