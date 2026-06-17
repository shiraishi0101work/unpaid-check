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
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = __importDefault(require("express"));
const multer_1 = __importDefault(require("multer"));
const path = __importStar(require("path"));
const fs = __importStar(require("fs"));
const os = __importStar(require("os"));
const report_generator_js_1 = require("./report-generator.js");
const db = __importStar(require("./db.js"));
const app = (0, express_1.default)();
const PORT = process.env['PORT'] ?? 3000;
app.use(express_1.default.json());
app.use(express_1.default.static(path.join(__dirname, 'public')));
const upload = (0, multer_1.default)({
    storage: multer_1.default.diskStorage({
        destination: (_req, _file, cb) => {
            const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'meo-'));
            cb(null, tmpDir);
        },
        filename: (_req, file, cb) => {
            cb(null, file.fieldname + path.extname(file.originalname));
        },
    }),
    limits: { fileSize: 20 * 1024 * 1024 },
});
const uploadFields = upload.fields([
    { name: 'keyword', maxCount: 5 },
    { name: 'views', maxCount: 1 },
    { name: 'interactions', maxCount: 1 },
    { name: 'userActions', maxCount: 4 },
    { name: 'csv', maxCount: 1 },
]);
// ── CSV パーサー ───────────────────────────────────────────
function parseCSVRow(line) {
    const cols = [];
    let field = '';
    let inQuote = false;
    for (let i = 0; i < line.length; i++) {
        const c = line[i];
        if (c === '"') {
            if (inQuote && line[i + 1] === '"') {
                field += '"';
                i++;
            }
            else {
                inQuote = !inQuote;
            }
        }
        else if (c === ',' && !inQuote) {
            cols.push(field);
            field = '';
        }
        else {
            field += c;
        }
    }
    cols.push(field);
    return cols;
}
function parseCSV(text) {
    const cleaned = text.replace(/^\uFEFF/, '').replace(/\r\n/g, '\n').replace(/\r/g, '\n');
    const lines = cleaned.split('\n').filter(l => l.trim());
    const result = [];
    for (let i = 1; i < lines.length; i++) { // ヘッダー行をスキップ
        const cols = parseCSVRow(lines[i]);
        result.push({ current: (cols[1] ?? '').trim(), analysis: (cols[2] ?? '').trim() });
    }
    return result;
}
// ── CSV テンプレートダウンロード ────────────────────────────
app.get('/api/csv-template', (req, res) => {
    const month = req.query['month'] ?? '〇';
    const bom = '\uFEFF';
    const rows = [
        ['ページ', '【現状】テキスト', '【分析】テキスト'],
        [`キーワード順位（2ページ目）`, `${month}月のキーワード順位を記載してください`, `キーワード順位の分析コメントを記載してください`],
        [`閲覧ユーザー数（3ページ目）`, `${month}月の閲覧ユーザー数を記載してください`, `閲覧数の分析コメントを記載してください`],
        [`インタラクション数（4ページ目）`, `${month}月のインタラクション数を記載してください`, `インタラクションの分析コメントを記載してください`],
        [`ユーザー行動データ（5ページ目）`, `${month}月のユーザー行動データを記載してください`, `ユーザー行動の分析コメントを記載してください`],
    ];
    const csv = rows.map(r => r.map(c => `"${c.replace(/"/g, '""')}"`).join(',')).join('\r\n');
    const filename = encodeURIComponent(`MEOレポートテキスト_ひな型.csv`);
    res.setHeader('Content-Type', 'text/csv; charset=utf-8');
    res.setHeader('Content-Disposition', `attachment; filename*=UTF-8''${filename}`);
    res.send(bom + csv);
});
// ── Store API ─────────────────────────────────────────────
app.get('/api/stores', (_req, res) => {
    const stores = db.getStores();
    const reports = db.getReports();
    const result = stores.map(s => ({
        ...s,
        reportCount: reports.filter(r => r.storeId === s.id).length,
        latestReport: reports.filter(r => r.storeId === s.id)[0] ?? null,
    }));
    res.json(result);
});
app.post('/api/stores', (req, res) => {
    const { name } = req.body;
    if (!name?.trim()) {
        res.status(400).json({ error: '店舗名を入力してください' });
        return;
    }
    const store = db.addStore(name.trim());
    res.json(store);
});
app.delete('/api/stores/:id', (req, res) => {
    db.deleteStore(req.params['id'] ?? '');
    res.json({ ok: true });
});
// ── Report API ────────────────────────────────────────────
app.get('/api/stores/:storeId/reports', (req, res) => {
    const reports = db.getReports(req.params['storeId']);
    res.json(reports);
});
app.get('/api/reports/:id/download', (req, res) => {
    const report = db.getReport(req.params['id'] ?? '');
    if (!report || !fs.existsSync(report.filePath)) {
        res.status(404).json({ error: 'ファイルが見つかりません' });
        return;
    }
    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.presentationml.presentation');
    res.setHeader('Content-Disposition', `attachment; filename*=UTF-8''${encodeURIComponent(report.fileName)}`);
    res.sendFile(report.filePath);
});
app.delete('/api/reports/:id', (req, res) => {
    db.deleteReport(req.params['id'] ?? '');
    res.json({ ok: true });
});
// ── レポート生成: 画像 + CSV → PPTX ────────────────────────
app.post('/api/generate-report', uploadFields, async (req, res) => {
    const tmpFiles = [];
    const tmpOutput = path.join(os.tmpdir(), `meo-report-${Date.now()}.pptx`);
    try {
        const { storeName, month, year, storeId: existingStoreId } = req.body;
        if (!storeName || !month || !year) {
            const missing = [!storeName && 'storeName', !month && 'month', !year && 'year'].filter(Boolean).join(', ');
            res.status(400).json({ error: `必須パラメータが不足しています (${missing})` });
            return;
        }
        const files = req.files;
        // CSV ファイルを読み込む
        const csvFile = files['csv']?.[0];
        if (!csvFile) {
            res.status(400).json({ error: 'CSVファイルをアップロードしてください' });
            return;
        }
        tmpFiles.push(csvFile.path);
        const csvText = fs.readFileSync(csvFile.path, 'utf-8');
        const csvData = parseCSV(csvText);
        // csvData[0]=キーワード, [1]=閲覧, [2]=インタラクション, [3]=ユーザー行動
        // 画像ファイルを収集
        const screenshots = {};
        const keywordFiles = files['keyword'] ?? [];
        for (const f of keywordFiles)
            tmpFiles.push(f.path);
        if (keywordFiles.length > 0)
            screenshots.keyword = keywordFiles[0].path;
        for (const key of ['views', 'interactions']) {
            const file = files[key]?.[0];
            if (file) {
                screenshots[key] = file.path;
                tmpFiles.push(file.path);
            }
        }
        // 店舗を登録 or 取得
        const store = existingStoreId
            ? (db.getStore(existingStoreId) ?? db.addStore(storeName))
            : db.addStore(storeName);
        const monthNum = parseInt(month, 10);
        const yearNum = parseInt(year, 10);
        // スライドデータを構築
        const slides = {};
        const kwData = csvData[0];
        if (kwData) {
            if (keywordFiles.length > 1) {
                slides.keywords = keywordFiles.map((f, i) => ({
                    title: `${monthNum}月対策キーワード順位ご報告`,
                    imagePath: f.path,
                    currentStatus: i === 0 ? kwData.current : '',
                    analysis: i === 0 ? kwData.analysis : '',
                }));
            }
            else {
                slides.keywords = [{
                        title: `${monthNum}月対策キーワード順位ご報告`,
                        imagePath: screenshots.keyword,
                        currentStatus: kwData.current,
                        analysis: kwData.analysis,
                    }];
            }
        }
        const viewsData = csvData[1];
        if (viewsData && (viewsData.current || viewsData.analysis || screenshots.views)) {
            slides.views = {
                title: '閲覧したユーザー数',
                imagePath: screenshots.views,
                currentStatus: viewsData.current,
                analysis: viewsData.analysis,
            };
        }
        const interactData = csvData[2];
        if (interactData && (interactData.current || interactData.analysis || screenshots.interactions)) {
            slides.interactions = {
                title: 'インタラクション数',
                imagePath: screenshots.interactions,
                currentStatus: interactData.current,
                analysis: interactData.analysis,
            };
        }
        const userActFiles = files['userActions'] ?? [];
        for (const f of userActFiles)
            tmpFiles.push(f.path);
        const userActData = csvData[3];
        if (userActData && (userActData.current || userActData.analysis || userActFiles.length > 0)) {
            if (userActFiles.length > 1) {
                // 複数枚 → グリッドスライド
                slides.userActions = userActFiles.map((f, i) => ({
                    title: 'ユーザー行動データ（来店・売上に直結）',
                    imagePath: f.path,
                    currentStatus: i === 0 ? userActData.current : '',
                    analysis: i === 0 ? userActData.analysis : '',
                }));
            }
            else {
                slides.userActions = {
                    title: 'ユーザー行動データ（来店・売上に直結）',
                    imagePath: userActFiles[0]?.path ?? screenshots.userActions,
                    currentStatus: userActData.current,
                    analysis: userActData.analysis,
                };
            }
        }
        const input = { storeName, month: monthNum, year: yearNum, screenshots, apiKey: '' };
        const generator = new report_generator_js_1.ReportGenerator();
        await generator.generateReport(input, slides, tmpOutput);
        const saved = db.saveReport({ storeId: store.id, storeName, month: monthNum, year: yearNum, generatedAt: new Date().toISOString() }, tmpOutput);
        res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.presentationml.presentation');
        res.setHeader('Content-Disposition', `attachment; filename*=UTF-8''${encodeURIComponent(saved.fileName)}`);
        res.setHeader('X-Report-Id', saved.id);
        res.setHeader('X-Store-Id', store.id);
        res.sendFile(saved.filePath, err => {
            if (err)
                console.error('送信エラー:', err);
            tmpFiles.forEach(f => { try {
                fs.unlinkSync(f);
            }
            catch { /* ignore */ } });
            try {
                fs.unlinkSync(tmpOutput);
            }
            catch { /* ignore */ }
        });
    }
    catch (err) {
        tmpFiles.forEach(f => { try {
            fs.unlinkSync(f);
        }
        catch { /* ignore */ } });
        try {
            fs.unlinkSync(tmpOutput);
        }
        catch { /* ignore */ }
        console.error('レポート生成エラー:', err);
        res.status(500).json({ error: err instanceof Error ? err.message : '不明なエラー' });
    }
});
app.listen(PORT, () => {
    console.log('');
    console.log('✅ MEOレポーター 起動完了');
    console.log(`   ブラウザで開く → http://localhost:${PORT}`);
    console.log('');
});
//# sourceMappingURL=server.js.map