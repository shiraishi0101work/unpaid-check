import * as fs from 'fs';
import * as path from 'path';

const DATA_DIR = path.join(__dirname, '..', 'data');
const DB_FILE = path.join(DATA_DIR, 'db.json');
const REPORTS_DIR = path.join(DATA_DIR, 'reports');

export interface Store {
  id: string;
  name: string;
  createdAt: string;
}

export interface Report {
  id: string;
  storeId: string;
  storeName: string;
  month: number;
  year: number;
  fileName: string;
  filePath: string;
  generatedAt: string;
}

interface DB {
  stores: Store[];
  reports: Report[];
}

function ensureDirs(): void {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
  if (!fs.existsSync(REPORTS_DIR)) fs.mkdirSync(REPORTS_DIR, { recursive: true });
}

function readDB(): DB {
  ensureDirs();
  if (!fs.existsSync(DB_FILE)) return { stores: [], reports: [] };
  return JSON.parse(fs.readFileSync(DB_FILE, 'utf-8')) as DB;
}

function writeDB(db: DB): void {
  ensureDirs();
  fs.writeFileSync(DB_FILE, JSON.stringify(db, null, 2), 'utf-8');
}

function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
}

// Stores
export function getStores(): Store[] {
  return readDB().stores;
}

export function addStore(name: string): Store {
  const db = readDB();
  // Check for duplicate
  const existing = db.stores.find(s => s.name === name);
  if (existing) return existing;

  const store: Store = { id: generateId(), name, createdAt: new Date().toISOString() };
  db.stores.push(store);
  writeDB(db);
  return store;
}

export function getStore(id: string): Store | undefined {
  return readDB().stores.find(s => s.id === id);
}

export function deleteStore(id: string): void {
  const db = readDB();
  db.stores = db.stores.filter(s => s.id !== id);
  // Also remove reports for this store
  const storeReports = db.reports.filter(r => r.storeId === id);
  for (const r of storeReports) {
    try { fs.unlinkSync(r.filePath); } catch { /* ignore */ }
  }
  db.reports = db.reports.filter(r => r.storeId !== id);
  writeDB(db);
}

// Reports
export function getReports(storeId?: string): Report[] {
  const db = readDB();
  const reports = storeId ? db.reports.filter(r => r.storeId === storeId) : db.reports;
  return reports.sort((a, b) => new Date(b.generatedAt).getTime() - new Date(a.generatedAt).getTime());
}

export function saveReport(data: Omit<Report, 'id' | 'filePath' | 'fileName'>, tmpPath: string): Report {
  const db = readDB();
  const storeDir = path.join(REPORTS_DIR, data.storeId);
  if (!fs.existsSync(storeDir)) fs.mkdirSync(storeDir, { recursive: true });

  const fileName = `MEO対策レポート_${data.storeName}_${data.year}年${data.month}月.pptx`;
  const filePath = path.join(storeDir, fileName);

  // Copy file to permanent location
  fs.copyFileSync(tmpPath, filePath);

  const report: Report = {
    id: generateId(),
    ...data,
    fileName,
    filePath,
  };

  // Remove old report for same store/month/year if exists
  const oldIdx = db.reports.findIndex(r => r.storeId === data.storeId && r.month === data.month && r.year === data.year);
  if (oldIdx >= 0) {
    try { fs.unlinkSync(db.reports[oldIdx]!.filePath); } catch { /* ignore */ }
    db.reports.splice(oldIdx, 1);
  }

  db.reports.push(report);
  writeDB(db);
  return report;
}

export function getReport(id: string): Report | undefined {
  return readDB().reports.find(r => r.id === id);
}

export function deleteReport(id: string): void {
  const db = readDB();
  const report = db.reports.find(r => r.id === id);
  if (report) {
    try { fs.unlinkSync(report.filePath); } catch { /* ignore */ }
  }
  db.reports = db.reports.filter(r => r.id !== id);
  writeDB(db);
}

export { REPORTS_DIR };
