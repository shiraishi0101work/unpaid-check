import express from 'express';
import multer from 'multer';
import * as path from 'path';
import * as fs from 'fs';
import * as os from 'os';
import { MeoAnalyzer, type CommentProvider } from './analyzer.js';
import { ReportGenerator } from './report-generator.js';
import * as db from './db.js';
import type { ReportInput, SlideData } from './types.js';

const app = express();
const PORT = process.env['PORT'] ?? 3000;

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

const upload = multer({
  storage: multer.diskStorage({
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
  { name: 'keyword', maxCount: 1 },
  { name: 'views', maxCount: 1 },
  { name: 'interactions', maxCount: 1 },
  { name: 'userActions', maxCount: 1 },
]);

// ── Session storage ───────────────────────────────────────

import type { KeywordData, ViewsData, InteractionData, UserActionData } from './types.js';

interface ExtractedData {
  keyword?: KeywordData;
  views?: ViewsData;
  interactions?: InteractionData;
  userActions?: UserActionData;
}
interface AnalysisSession {
  storeId: string;
  storeName: string;
  month: number;
  year: number;
  apiKey: string;
  provider: CommentProvider;
  commentKey: string;
  prompts: db.PromptSet;
  tmpFiles: string[];
  screenshots: ReportInput['screenshots'];
  extractedData: ExtractedData;  // Step1: 画像から抽出した数値データ
  createdAt: number;
}
const sessions = new Map<string, AnalysisSession>();
function newSid(): string { return Date.now().toString(36) + Math.random().toString(36).slice(2, 8); }

// 2時間超のセッションは定期クリーンアップ
setInterval(() => {
  const cutoff = Date.now() - 2 * 60 * 60 * 1000;
  for (const [id, s] of sessions) {
    if (s.createdAt < cutoff) {
      s.tmpFiles.forEach(f => { try { fs.unlinkSync(f); } catch { /* ignore */ } });
      sessions.delete(id);
    }
  }
}, 30 * 60 * 1000);

// ── Store API ─────────────────────────────────────────────

app.get('/api/stores', (_req, res) => {
  const stores = db.getStores();
  const reports = db.getReports();
  // Attach report count to each store
  const result = stores.map(s => ({
    ...s,
    reportCount: reports.filter(r => r.storeId === s.id).length,
    latestReport: reports.filter(r => r.storeId === s.id)[0] ?? null,
    hasCustomPrompts: Object.keys(db.getStorePrompts(s.id)).length > 0,
  }));
  res.json(result);
});

app.post('/api/stores', (req, res) => {
  const { name } = req.body as { name: string };
  if (!name?.trim()) { res.status(400).json({ error: '店舗名を入力してください' }); return; }
  const store = db.addStore(name.trim());
  res.json(store);
});

app.delete('/api/stores/:id', (req, res) => {
  db.deleteStore(req.params['id'] ?? '');
  res.json({ ok: true });
});

// ── Prompt API ────────────────────────────────────────────

app.get('/api/prompts/default', (_req, res) => {
  res.json(db.getDefaultPrompts());
});

app.put('/api/prompts/default', (req, res) => {
  const { prompts, applyToAll, resetToDefault } = req.body as { prompts: Partial<db.PromptSet>; applyToAll: boolean; resetToDefault?: boolean };
  if (resetToDefault) {
    db.clearDefaultPrompts();
  } else {
    db.setDefaultPrompts(prompts);
    if (applyToAll) {
      db.clearAllStorePromptsForKeys(Object.keys(prompts) as (keyof db.PromptSet)[]);
    }
  }
  res.json({ ok: true });
});

app.get('/api/stores/:storeId/prompts', (req, res) => {
  res.json(db.getStorePrompts(req.params['storeId'] ?? ''));
});

app.put('/api/stores/:storeId/prompts', (req, res) => {
  db.setStorePrompts(req.params['storeId'] ?? '', req.body as Partial<db.PromptSet>);
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

// ── Step1: Extract API（画像から数値データを抽出）──────────

app.post('/api/extract', uploadFields, async (req, res) => {
  const tmpFiles: string[] = [];
  try {
    const { storeName, month, year, apiKey, storeId: existingStoreId, commentAI, commentApiKey } =
      req.body as Record<string, string>;

    const provider = (commentAI as CommentProvider | undefined) ?? 'claude';
    const commentKey = commentApiKey?.trim() || apiKey;

    if (!storeName || !month || !year) {
      const missing = [!storeName && 'storeName', !month && 'month', !year && 'year'].filter(Boolean).join(', ');
      res.status(400).json({ error: `必須パラメータが不足しています (${missing})` }); return;
    }
    if (provider === 'gemini' && !commentKey) {
      res.status(400).json({ error: 'GeminiのAPIキーが設定されていません' }); return;
    }
    if (provider !== 'gemini' && !apiKey) {
      res.status(400).json({ error: 'Anthropic APIキーが設定されていません（画像解析に使用します）' }); return;
    }

    const files = req.files as Record<string, Express.Multer.File[]>;
    const screenshots: ReportInput['screenshots'] = {};
    const keywordFiles = files['keyword'] ?? [];
    for (const f of keywordFiles) tmpFiles.push(f.path);
    if (keywordFiles.length > 0) screenshots.keyword = keywordFiles[0]!.path;
    for (const key of ['views', 'interactions', 'userActions'] as const) {
      const file = files[key]?.[0];
      if (file) { screenshots[key] = file.path; tmpFiles.push(file.path); }
    }
    if (tmpFiles.length === 0) { res.status(400).json({ error: 'スクリーンショットを1枚以上アップロードしてください' }); return; }

    const store = existingStoreId ? (db.getStore(existingStoreId) ?? db.addStore(storeName)) : db.addStore(storeName);
    const prompts = { ...db.getDefaultPrompts(), ...db.getStorePrompts(store.id) };
    const analyzer = new MeoAnalyzer(apiKey, provider, commentKey);
    const monthNum = parseInt(month, 10);

    // 画像から数値のみを抽出（文章生成はしない）
    const extractedData: ExtractedData = {};
    if (screenshots.keyword) {
      console.log('🔍 [解析] キーワード順位...');
      extractedData.keyword = await analyzer.extractKeywordData(screenshots.keyword);
    }
    if (screenshots.views) {
      console.log('👁️  [解析] 閲覧ユーザー数...');
      extractedData.views = await analyzer.extractViewsData(screenshots.views);
    }
    if (screenshots.interactions) {
      console.log('🔄 [解析] インタラクション数...');
      extractedData.interactions = await analyzer.extractInteractionData(screenshots.interactions);
    }
    if (screenshots.userActions) {
      console.log('📍 [解析] ユーザー行動データ...');
      extractedData.userActions = await analyzer.extractUserActionData(screenshots.userActions);
    }

    console.log('📊 [抽出完了] extractedData:', JSON.stringify(extractedData, null, 2).slice(0, 800));

    const sid = newSid();
    sessions.set(sid, {
      storeId: store.id, storeName, month: monthNum, year: parseInt(year, 10),
      apiKey, provider, commentKey, prompts,
      tmpFiles, screenshots, extractedData, createdAt: Date.now(),
    });

    res.json({ sessionId: sid, storeId: store.id, extracted: extractedData, hasImages: Object.keys(screenshots) });

  } catch (err) {
    for (const f of tmpFiles) { try { fs.unlinkSync(f); } catch { /* ignore */ } }
    console.error('抽出エラー:', err);
    res.status(500).json({ error: err instanceof Error ? err.message : '不明なエラー' });
  }
});

// ── Step1b: Re-extract API（1セクション再解析）──────────────

app.post('/api/re-extract', async (req, res) => {
  const { sessionId, section } = req.body as { sessionId: string; section: string };
  const session = sessions.get(sessionId);
  if (!session) { res.status(404).json({ error: 'セッションが見つかりません' }); return; }
  try {
    const analyzer = new MeoAnalyzer(session.apiKey, session.provider, session.commentKey);
    const { screenshots } = session;
    let extracted: ExtractedData[keyof ExtractedData] = undefined;

    if (section === 'keyword' && screenshots.keyword && fs.existsSync(screenshots.keyword)) {
      extracted = await analyzer.extractKeywordData(screenshots.keyword);
      session.extractedData.keyword = extracted as KeywordData;
    } else if (section === 'views' && screenshots.views && fs.existsSync(screenshots.views)) {
      extracted = await analyzer.extractViewsData(screenshots.views);
      session.extractedData.views = extracted as ViewsData;
    } else if (section === 'interactions' && screenshots.interactions && fs.existsSync(screenshots.interactions)) {
      extracted = await analyzer.extractInteractionData(screenshots.interactions);
      session.extractedData.interactions = extracted as InteractionData;
    } else if (section === 'userActions' && screenshots.userActions && fs.existsSync(screenshots.userActions)) {
      extracted = await analyzer.extractUserActionData(screenshots.userActions);
      session.extractedData.userActions = extracted as UserActionData;
    }
    res.json({ section, extracted });
  } catch (err) {
    res.status(500).json({ error: err instanceof Error ? err.message : '不明なエラー' });
  }
});

// ── Step2: Generate Text API（抽出データ → 説明文生成）───────

app.post('/api/generate-text', async (req, res) => {
  const { sessionId, extractedData: overrideData } = req.body as { sessionId: string; extractedData?: ExtractedData };
  const session = sessions.get(sessionId);
  if (!session) { res.status(404).json({ error: 'セッションが見つかりません（タイムアウトした可能性があります）' }); return; }

  try {
    // フォームから送られてきたデータがあればセッションを上書き
    if (overrideData) {
      session.extractedData = { ...session.extractedData, ...overrideData };
    }
    const { extractedData, prompts, month, screenshots } = session;
    const analyzer = new MeoAnalyzer(session.apiKey, session.provider, session.commentKey);

    const sections: Record<string, { title: string; current: string; analysis: string; hasImage: boolean }> = {};

    // キーワードは常に含める（画像なしなら空データで生成）
    console.log('✍️  [文章生成] キーワード順位...');
    const kwData = extractedData.keyword ?? { keywords: [], summary: '' };
    const kwComment = await analyzer.generateKeywordComment(kwData, month, prompts.keyword_current, prompts.keyword_analysis);
    sections['keyword'] = { title: `${month}月対策キーワード順位ご報告`, ...kwComment, hasImage: !!screenshots.keyword };

    if (extractedData.views) {
      console.log('✍️  [文章生成] 閲覧ユーザー数...');
      const c = await analyzer.generateViewsComment(extractedData.views, month, prompts.views_current, prompts.views_analysis);
      sections['views'] = { title: '閲覧したユーザー数', ...c, hasImage: !!screenshots.views };
    }
    if (extractedData.interactions) {
      console.log('✍️  [文章生成] インタラクション数...');
      const c = await analyzer.generateInteractionComment(extractedData.interactions, month, prompts.interactions_current, prompts.interactions_analysis);
      sections['interactions'] = { title: 'インタラクション数', ...c, hasImage: !!screenshots.interactions };
    }
    if (extractedData.userActions) {
      console.log('✍️  [文章生成] ユーザー行動データ...');
      const c = await analyzer.generateUserActionComment(extractedData.userActions, month, prompts.userActions_current, prompts.userActions_analysis);
      sections['userActions'] = { title: 'ユーザー行動データ（来店・売上に直結）', ...c, hasImage: !!screenshots.userActions };
    }

    res.json({ sections, commentFallback: analyzer.commentFallback });
  } catch (err) {
    console.error('文章生成エラー:', err);
    res.status(500).json({ error: err instanceof Error ? err.message : '不明なエラー' });
  }
});

// ── Step2b: Regenerate Text API（1セクションだけテキスト再生成）

app.post('/api/regenerate', async (req, res) => {
  const { sessionId, section } = req.body as { sessionId: string; section: string };
  const session = sessions.get(sessionId);
  if (!session) { res.status(404).json({ error: 'セッションが見つかりません' }); return; }
  try {
    const { extractedData, prompts, month } = session;
    const analyzer = new MeoAnalyzer(session.apiKey, session.provider, session.commentKey);
    let comment = { current: '', analysis: '' };

    if (section === 'keyword') {
      const data = extractedData.keyword ?? { keywords: [], summary: '' };
      comment = await analyzer.generateKeywordComment(data, month, prompts.keyword_current, prompts.keyword_analysis);
    } else if (section === 'views' && extractedData.views) {
      comment = await analyzer.generateViewsComment(extractedData.views, month, prompts.views_current, prompts.views_analysis);
    } else if (section === 'interactions' && extractedData.interactions) {
      comment = await analyzer.generateInteractionComment(extractedData.interactions, month, prompts.interactions_current, prompts.interactions_analysis);
    } else if (section === 'userActions' && extractedData.userActions) {
      comment = await analyzer.generateUserActionComment(extractedData.userActions, month, prompts.userActions_current, prompts.userActions_analysis);
    }
    res.json(comment);
  } catch (err) {
    res.status(500).json({ error: err instanceof Error ? err.message : '不明なエラー' });
  }
});

// ── Finalize API（確認済みコメント → PPTX生成・ダウンロード）

app.post('/api/finalize', async (req, res) => {
  const { sessionId, sections } = req.body as {
    sessionId: string;
    sections: {
      keyword: { current: string; analysis: string };
      views?: { current: string; analysis: string };
      interactions?: { current: string; analysis: string };
      userActions?: { current: string; analysis: string };
    };
  };
  const session = sessions.get(sessionId);
  if (!session) { res.status(404).json({ error: 'セッションが見つかりません（タイムアウトした可能性があります）' }); return; }

  const tmpOutput = path.join(os.tmpdir(), `meo-report-${Date.now()}.pptx`);
  try {
    const { screenshots, storeName, month, year, storeId } = session;

    const slides: {
      keywords?: SlideData[];
      views?: SlideData;
      interactions?: SlideData;
      userActions?: SlideData;
    } = {};

    slides.keywords = [{
      title: `${month}月対策キーワード順位ご報告`,
      imagePath: screenshots.keyword,
      currentStatus: sections.keyword.current,
      analysis: sections.keyword.analysis,
    }];
    if (sections.views) {
      slides.views = { title: '閲覧したユーザー数', imagePath: screenshots.views, currentStatus: sections.views.current, analysis: sections.views.analysis };
    }
    if (sections.interactions) {
      slides.interactions = { title: 'インタラクション数', imagePath: screenshots.interactions, currentStatus: sections.interactions.current, analysis: sections.interactions.analysis };
    }
    if (sections.userActions) {
      slides.userActions = { title: 'ユーザー行動データ（来店・売上に直結）', imagePath: screenshots.userActions, currentStatus: sections.userActions.current, analysis: sections.userActions.analysis };
    }

    const input: ReportInput = { storeName, month, year, screenshots, apiKey: session.apiKey };
    const generator = new ReportGenerator();
    await generator.generateReport(input, slides, tmpOutput);

    const saved = db.saveReport({ storeId, storeName, month, year, generatedAt: new Date().toISOString() }, tmpOutput);

    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.presentationml.presentation');
    res.setHeader('Content-Disposition', `attachment; filename*=UTF-8''${encodeURIComponent(saved.fileName)}`);
    res.setHeader('X-Report-Id', saved.id);
    res.setHeader('X-Store-Id', storeId);
    res.sendFile(saved.filePath, err => {
      if (err) console.error('送信エラー:', err);
      // セッション片付け
      session.tmpFiles.forEach(f => { try { fs.unlinkSync(f); } catch { /* ignore */ } });
      try { fs.unlinkSync(tmpOutput); } catch { /* ignore */ }
      sessions.delete(sessionId);
    });

  } catch (err) {
    try { fs.unlinkSync(tmpOutput); } catch { /* ignore */ }
    console.error('finalizeエラー:', err);
    res.status(500).json({ error: err instanceof Error ? err.message : '不明なエラー' });
  }
});

app.listen(PORT, () => {
  console.log('');
  console.log('✅ MEOレポーター 起動完了');
  console.log(`   ブラウザで開く → http://localhost:${PORT}`);
  console.log('');
});
