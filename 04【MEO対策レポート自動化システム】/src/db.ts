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

export interface PromptSet {
  keyword: string;
  views: string;
  interactions: string;
  userActions: string;
}

export const DEFAULT_PROMPTS: PromptSet = {
  keyword: `MEO対策レポートの{month}月度キーワード順位について、クライアント向けの説明文を生成してください。

【現状】は1〜2文で事実を簡潔に記載してください。
【分析】は3〜5文でMEOの専門的な視点から前向きに記述し、課題があれば改善提案も含めてください。`,

  views: `MEO対策レポートの{month}月度閲覧ユーザー数について、クライアント向けの説明文を生成してください。

【現状】は1文で件数を明記してください。
【分析】は3〜5文でマーケティング視点から前向きに記述し、前年比・トレンドにも触れてください。`,

  interactions: `MEO対策レポートの{month}月度インタラクション数について、クライアント向けの説明文を生成してください。

【現状】は1文で件数とインタラクション率を明記してください。
【分析】は3〜5文で「閲覧から行動への転換」という視点で分析し、ポジティブシグナルとしての意味を伝えてください。`,

  userActions: `MEO対策レポートの{month}月度ユーザー行動データについて、クライアント向けの説明文を生成してください。

【現状】は1〜2文で各指標の数値を列挙してください。
【分析】は4〜6文で記述し、強い指標は来店意欲の高さとして評価し、弱い指標はCTA・情報設計の改善提案として伝えてください。`,
};

interface DB {
  stores: Store[];
  reports: Report[];
  defaultPrompts: Partial<PromptSet>;
  storePrompts: Record<string, Partial<PromptSet>>;
}

function ensureDirs(): void {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
  if (!fs.existsSync(REPORTS_DIR)) fs.mkdirSync(REPORTS_DIR, { recursive: true });
}

function readDB(): DB {
  ensureDirs();
  if (!fs.existsSync(DB_FILE)) return { stores: [], reports: [], defaultPrompts: {}, storePrompts: {} };
  const data = JSON.parse(fs.readFileSync(DB_FILE, 'utf-8')) as DB;
  if (!data.defaultPrompts) data.defaultPrompts = {};
  if (!data.storePrompts) data.storePrompts = {};
  return data;
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
