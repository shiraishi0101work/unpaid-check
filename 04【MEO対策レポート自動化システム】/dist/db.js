"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.REPORTS_DIR = exports.DEFAULT_PROMPTS = void 0;
exports.getStores = getStores;
exports.addStore = addStore;
exports.getStore = getStore;
exports.deleteStore = deleteStore;
exports.getReports = getReports;
exports.saveReport = saveReport;
exports.getReport = getReport;
exports.deleteReport = deleteReport;
exports.getDefaultPrompts = getDefaultPrompts;
exports.setDefaultPrompts = setDefaultPrompts;
exports.clearDefaultPrompts = clearDefaultPrompts;
exports.getStorePrompts = getStorePrompts;
exports.setStorePrompts = setStorePrompts;
exports.clearAllStorePromptsForKeys = clearAllStorePromptsForKeys;
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
const DATA_DIR = path.join(__dirname, '..', 'data');
const DB_FILE = path.join(DATA_DIR, 'db.json');
const REPORTS_DIR = path.join(DATA_DIR, 'reports');
exports.REPORTS_DIR = REPORTS_DIR;
exports.DEFAULT_PROMPTS = {
    keyword_current: '1〜2文で、対策キーワードの順位状況を事実として簡潔に記載してください。',
    keyword_analysis: '3〜5文で、MEOの専門的な視点から順位の意味を前向きに解説してください。課題があれば改善提案も含めてください。',
    views_current: '1文で、今月の閲覧ユーザー数を明記してください。',
    views_analysis: '3〜5文で、マーケティング視点から閲覧数の意味を前向きに解説してください。前年比・トレンドにも触れてください。',
    interactions_current: '1文で、今月のインタラクション数とインタラクション率を明記してください。',
    interactions_analysis: '3〜5文で、「閲覧から行動への転換」という視点でインタラクション数を分析し、ポジティブシグナルとしての意味を伝えてください。',
    userActions_current: '1〜2文で、通話・Webサイト・ルート検索・予約の各指標の数値を列挙してください。',
    userActions_analysis: '4〜6文で、強い指標は来店意欲の高さとして評価し、弱い指標はCTA・情報設計の改善提案として伝えてください。',
};
function ensureDirs() {
    if (!fs.existsSync(DATA_DIR))
        fs.mkdirSync(DATA_DIR, { recursive: true });
    if (!fs.existsSync(REPORTS_DIR))
        fs.mkdirSync(REPORTS_DIR, { recursive: true });
}
function readDB() {
    ensureDirs();
    if (!fs.existsSync(DB_FILE))
        return { stores: [], reports: [], defaultPrompts: {}, storePrompts: {} };
    const data = JSON.parse(fs.readFileSync(DB_FILE, 'utf-8'));
    if (!data.defaultPrompts)
        data.defaultPrompts = {};
    if (!data.storePrompts)
        data.storePrompts = {};
    return data;
}
function writeDB(db) {
    ensureDirs();
    fs.writeFileSync(DB_FILE, JSON.stringify(db, null, 2), 'utf-8');
}
function generateId() {
    return Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
}
// Stores
function getStores() {
    return readDB().stores;
}
function addStore(name) {
    const db = readDB();
    // Check for duplicate
    const existing = db.stores.find(s => s.name === name);
    if (existing)
        return existing;
    const store = { id: generateId(), name, createdAt: new Date().toISOString() };
    db.stores.push(store);
    writeDB(db);
    return store;
}
function getStore(id) {
    return readDB().stores.find(s => s.id === id);
}
function deleteStore(id) {
    const db = readDB();
    db.stores = db.stores.filter(s => s.id !== id);
    // Also remove reports for this store
    const storeReports = db.reports.filter(r => r.storeId === id);
    for (const r of storeReports) {
        try {
            fs.unlinkSync(r.filePath);
        }
        catch { /* ignore */ }
    }
    db.reports = db.reports.filter(r => r.storeId !== id);
    writeDB(db);
}
// Reports
function getReports(storeId) {
    const db = readDB();
    const reports = storeId ? db.reports.filter(r => r.storeId === storeId) : db.reports;
    return reports.sort((a, b) => new Date(b.generatedAt).getTime() - new Date(a.generatedAt).getTime());
}
function saveReport(data, tmpPath) {
    const db = readDB();
    const storeDir = path.join(REPORTS_DIR, data.storeId);
    if (!fs.existsSync(storeDir))
        fs.mkdirSync(storeDir, { recursive: true });
    const fileName = `MEO対策レポート_${data.storeName}様_${data.year}年${data.month}月.pptx`;
    const filePath = path.join(storeDir, fileName);
    // Copy file to permanent location
    fs.copyFileSync(tmpPath, filePath);
    const report = {
        id: generateId(),
        ...data,
        fileName,
        filePath,
    };
    // Remove old report for same store/month/year if exists
    const oldIdx = db.reports.findIndex(r => r.storeId === data.storeId && r.month === data.month && r.year === data.year);
    if (oldIdx >= 0) {
        try {
            fs.unlinkSync(db.reports[oldIdx].filePath);
        }
        catch { /* ignore */ }
        db.reports.splice(oldIdx, 1);
    }
    db.reports.push(report);
    writeDB(db);
    return report;
}
function getReport(id) {
    return readDB().reports.find(r => r.id === id);
}
function deleteReport(id) {
    const db = readDB();
    const report = db.reports.find(r => r.id === id);
    if (report) {
        try {
            fs.unlinkSync(report.filePath);
        }
        catch { /* ignore */ }
    }
    db.reports = db.reports.filter(r => r.id !== id);
    writeDB(db);
}
// Prompts
function getDefaultPrompts() {
    const db = readDB();
    return { ...exports.DEFAULT_PROMPTS, ...db.defaultPrompts };
}
function setDefaultPrompts(prompts) {
    const db = readDB();
    db.defaultPrompts = { ...db.defaultPrompts, ...prompts };
    writeDB(db);
}
function clearDefaultPrompts() {
    const db = readDB();
    db.defaultPrompts = {};
    writeDB(db);
}
function getStorePrompts(storeId) {
    return readDB().storePrompts[storeId] ?? {};
}
function setStorePrompts(storeId, prompts) {
    const db = readDB();
    db.storePrompts[storeId] = prompts;
    writeDB(db);
}
function clearAllStorePromptsForKeys(keys) {
    const db = readDB();
    for (const storeId of Object.keys(db.storePrompts)) {
        for (const key of keys) {
            delete db.storePrompts[storeId]?.[key];
        }
    }
    writeDB(db);
}
//# sourceMappingURL=db.js.map