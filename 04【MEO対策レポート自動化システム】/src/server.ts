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
  { name: 'keyword', maxCount: 10 },
  { name: 'views', maxCount: 1 },
  { name: 'interactions', maxCount: 1 },
  { name: 'userActions', maxCount: 1 },
]);

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

// ── Generate API ──────────────────────────────────────────

app.post('/api/generate', uploadFields, async (req, res) => {
  const tmpFiles: string[] = [];

  try {
    const {
      storeName, month, year, apiKey,
      storeId: existingStoreId, commentAI, commentApiKey,
      achievementDays,
      current_keyword, analysis_keyword,
      current_views, analysis_views,
      current_interactions, analysis_interactions,
      current_userActions, analysis_userActions,
    } = req.body as Record<string, string>;

    const provider = (commentAI as CommentProvider | undefined) ?? 'claude';
    const commentKey = commentApiKey?.trim() || apiKey;

    if (!storeName || !month || !year) {
      const missing = [!storeName && 'storeName', !month && 'month', !year && 'year'].filter(Boolean).join(', ');
      res.status(400).json({ error: `必須パラメータが不足しています (${missing})` });
      return;
    }
    // Gemini使用時はClaudeキー不要。それ以外はClaudeキー必須
    if (provider === 'gemini' && !commentKey) {
      res.status(400).json({ error: 'GeminiのAPIキーが設定されていません' });
      return;
    }
    if (provider !== 'gemini' && !apiKey) {
      res.status(400).json({ error: 'Anthropic APIキーが設定されていません（画像解析に使用します）' });
      return;
    }

    const files = req.files as Record<string, Express.Multer.File[]>;
    const screenshots: ReportInput['screenshots'] = {};

    // keyword は複数ファイル対応（最初の1枚をscreenshotsに保持、全パスは別管理）
    const keywordFiles = files['keyword'] ?? [];
    for (const f of keywordFiles) tmpFiles.push(f.path);
    if (keywordFiles.length > 0) {
      screenshots.keyword = keywordFiles[0]!.path;
    }

    for (const key of ['views', 'interactions', 'userActions'] as const) {
      const file = files[key]?.[0];
      if (file) {
        screenshots[key] = file.path;
        tmpFiles.push(file.path);
      }
    }

    const hasManualText = [current_keyword, analysis_keyword, current_views, analysis_views,
      current_interactions, analysis_interactions, current_userActions, analysis_userActions].some(v => v?.trim());
    if (keywordFiles.length === 0 && Object.keys(screenshots).length === 0 && !hasManualText) {
      res.status(400).json({ error: 'スクショまたは手動コメントが必要です' });
      return;
    }

    // Save or get store
    const store = existingStoreId ? (db.getStore(existingStoreId) ?? db.addStore(storeName)) : db.addStore(storeName);

    // Resolve prompts: store-specific overrides default
    const defaultPrompts = db.getDefaultPrompts();
    const storePrompts = db.getStorePrompts(store.id);
    const prompts = { ...defaultPrompts, ...storePrompts };

    const analyzer = new MeoAnalyzer(apiKey, provider, commentKey);
    const monthNum = parseInt(month, 10);
    const slides: {
      keywords?: SlideData[];
      views?: SlideData;
      interactions?: SlideData;
      userActions?: SlideData;
    } = {};

    // Helper: use manual text if provided, otherwise call AI
    const resolveComment = async (
      manualCur: string | undefined, manualAna: string | undefined,
      aiGen: () => Promise<{ current: string; analysis: string }>
    ): Promise<{ current: string; analysis: string }> => {
      const cur = manualCur?.trim() ?? '';
      const ana = manualAna?.trim() ?? '';
      if (cur || ana) return { current: cur, analysis: ana };
      return aiGen();
    };

    if (keywordFiles.length > 0 || current_keyword || analysis_keyword) {
      console.log('🔍 キーワード順位を処理中...');
      const imagePath = keywordFiles[0]?.path;
      const comment = await resolveComment(current_keyword, analysis_keyword, async () => {
        if (!imagePath) return { current: '', analysis: '' };
        const data = await analyzer.extractKeywordData(imagePath);
        return analyzer.generateKeywordComment(data, monthNum, prompts.keyword_current, prompts.keyword_analysis);
      });
      slides.keywords = [{
        title: `${monthNum}月対策キーワード順位ご報告`,
        imagePath,
        currentStatus: comment.current,
        analysis: comment.analysis,
      }];
    }

    if (screenshots.views || current_views || analysis_views) {
      console.log('👁️  閲覧ユーザー数を処理中...');
      const comment = await resolveComment(current_views, analysis_views, async () => {
        if (!screenshots.views) return { current: '', analysis: '' };
        const data = await analyzer.extractViewsData(screenshots.views);
        return analyzer.generateViewsComment(data, monthNum, prompts.views_current, prompts.views_analysis);
      });
      slides.views = { title: '閲覧したユーザー数', imagePath: screenshots.views, currentStatus: comment.current, analysis: comment.analysis };
    }

    if (screenshots.interactions || current_interactions || analysis_interactions) {
      console.log('🔄 インタラクション数を処理中...');
      const comment = await resolveComment(current_interactions, analysis_interactions, async () => {
        if (!screenshots.interactions) return { current: '', analysis: '' };
        const data = await analyzer.extractInteractionData(screenshots.interactions);
        return analyzer.generateInteractionComment(data, monthNum, prompts.interactions_current, prompts.interactions_analysis);
      });
      slides.interactions = { title: 'インタラクション数', imagePath: screenshots.interactions, currentStatus: comment.current, analysis: comment.analysis };
    }

    if (screenshots.userActions || current_userActions || analysis_userActions) {
      console.log('📍 ユーザー行動データを処理中...');
      const comment = await resolveComment(current_userActions, analysis_userActions, async () => {
        if (!screenshots.userActions) return { current: '', analysis: '' };
        const data = await analyzer.extractUserActionData(screenshots.userActions);
        return analyzer.generateUserActionComment(data, monthNum, prompts.userActions_current, prompts.userActions_analysis);
      });
      slides.userActions = { title: 'ユーザー行動データ（来店・売上に直結）', imagePath: screenshots.userActions, currentStatus: comment.current, analysis: comment.analysis };
    }

    const input: ReportInput = {
      storeName, month: monthNum, year: parseInt(year, 10), screenshots, apiKey,
      achievementDays: achievementDays ? parseInt(achievementDays, 10) : undefined,
    };
    const tmpOutput = path.join(os.tmpdir(), `meo-report-${Date.now()}.pptx`);
    tmpFiles.push(tmpOutput);

    const generator = new ReportGenerator();
    await generator.generateReport(input, slides, tmpOutput);

    // Save report permanently
    const saved = db.saveReport({
      storeId: store.id,
      storeName,
      month: monthNum,
      year: parseInt(year, 10),
      generatedAt: new Date().toISOString(),
    }, tmpOutput);

    // Send file
    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.presentationml.presentation');
    res.setHeader('Content-Disposition', `attachment; filename*=UTF-8''${encodeURIComponent(saved.fileName)}`);
    res.setHeader('X-Report-Id', saved.id);
    res.setHeader('X-Store-Id', store.id);
    res.setHeader('X-Comment-Fallback', analyzer.commentFallback ? '1' : '0');
    res.sendFile(saved.filePath, err => {
      if (err) console.error('送信エラー:', err);
      for (const f of tmpFiles) { try { fs.unlinkSync(f); } catch { /* ignore */ } }
    });

  } catch (err) {
    for (const f of tmpFiles) { try { fs.unlinkSync(f); } catch { /* ignore */ } }
    console.error('生成エラー:', err);
    res.status(500).json({ error: err instanceof Error ? err.message : '不明なエラー' });
  }
});

app.listen(PORT, () => {
  console.log('');
  console.log('✅ MEOレポーター 起動完了');
  console.log(`   ブラウザで開く → http://localhost:${PORT}`);
  console.log('');
});
