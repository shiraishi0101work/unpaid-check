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

// ── Analyze API（AI解析 → JSON返却、PPTXはまだ生成しない）────

app.post('/api/analyze', uploadFields, async (req, res) => {
  const tmpFiles: string[] = [];
  try {
    const {
      storeName, month, year, apiKey,
      storeId: existingStoreId, commentAI, commentApiKey,
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
    const keywordFiles = files['keyword'] ?? [];
    for (const f of keywordFiles) tmpFiles.push(f.path);
    if (keywordFiles.length > 0) screenshots.keyword = keywordFiles[0]!.path;
    for (const key of ['views', 'interactions', 'userActions'] as const) {
      const file = files[key]?.[0];
      if (file) { screenshots[key] = file.path; tmpFiles.push(file.path); }
    }

    const hasAny = tmpFiles.length > 0 || [
      current_keyword, analysis_keyword, current_views, analysis_views,
      current_interactions, analysis_interactions, current_userActions, analysis_userActions,
    ].some(v => v?.trim());
    if (!hasAny) { res.status(400).json({ error: 'スクショまたは手動コメントが必要です' }); return; }

    const store = existingStoreId ? (db.getStore(existingStoreId) ?? db.addStore(storeName)) : db.addStore(storeName);
    const prompts = { ...db.getDefaultPrompts(), ...db.getStorePrompts(store.id) };
    const analyzer = new MeoAnalyzer(apiKey, provider, commentKey);
    const monthNum = parseInt(month, 10);

    const resolveComment = async (
      manualCur: string | undefined, manualAna: string | undefined,
      aiGen: () => Promise<{ current: string; analysis: string }>
    ) => {
      const cur = manualCur?.trim() ?? '';
      const ana = manualAna?.trim() ?? '';
      if (cur || ana) return { current: cur, analysis: ana };
      return aiGen();
    };

    // キーワードは常にスライドとして含める
    console.log('🔍 キーワード順位を処理中...');
    const kwImagePath = keywordFiles[0]?.path;
    const kwComment = await resolveComment(current_keyword, analysis_keyword, async () => {
      if (!kwImagePath) return { current: '', analysis: '' };
      const data = await analyzer.extractKeywordData(kwImagePath);
      return analyzer.generateKeywordComment(data, monthNum, prompts.keyword_current, prompts.keyword_analysis);
    });
    const sectionKeyword: SectionResult = {
      title: `${monthNum}月対策キーワード順位ご報告`,
      current: kwComment.current,
      analysis: kwComment.analysis,
      hasImage: !!kwImagePath,
    };

    let sectionViews: SectionResult | undefined;
    if (screenshots.views || current_views || analysis_views) {
      console.log('👁️  閲覧ユーザー数を処理中...');
      const c = await resolveComment(current_views, analysis_views, async () => {
        if (!screenshots.views) return { current: '', analysis: '' };
        const data = await analyzer.extractViewsData(screenshots.views);
        return analyzer.generateViewsComment(data, monthNum, prompts.views_current, prompts.views_analysis);
      });
      sectionViews = { title: '閲覧したユーザー数', current: c.current, analysis: c.analysis, hasImage: !!screenshots.views };
    }

    let sectionInteractions: SectionResult | undefined;
    if (screenshots.interactions || current_interactions || analysis_interactions) {
      console.log('🔄 インタラクション数を処理中...');
      const c = await resolveComment(current_interactions, analysis_interactions, async () => {
        if (!screenshots.interactions) return { current: '', analysis: '' };
        const data = await analyzer.extractInteractionData(screenshots.interactions);
        return analyzer.generateInteractionComment(data, monthNum, prompts.interactions_current, prompts.interactions_analysis);
      });
      sectionInteractions = { title: 'インタラクション数', current: c.current, analysis: c.analysis, hasImage: !!screenshots.interactions };
    }

    let sectionUserActions: SectionResult | undefined;
    if (screenshots.userActions || current_userActions || analysis_userActions) {
      console.log('📍 ユーザー行動データを処理中...');
      const c = await resolveComment(current_userActions, analysis_userActions, async () => {
        if (!screenshots.userActions) return { current: '', analysis: '' };
        const data = await analyzer.extractUserActionData(screenshots.userActions);
        return analyzer.generateUserActionComment(data, monthNum, prompts.userActions_current, prompts.userActions_analysis);
      });
      sectionUserActions = { title: 'ユーザー行動データ（来店・売上に直結）', current: c.current, analysis: c.analysis, hasImage: !!screenshots.userActions };
    }

    // セッション保存（画像パスをキープしてfinalizeで使用）
    const sid = newSid();
    sessions.set(sid, {
      storeId: store.id,
      storeName,
      month: monthNum,
      year: parseInt(year, 10),
      apiKey,
      provider,
      commentKey,
      prompts,
      tmpFiles,          // finalizeまで削除しない
      screenshots,
      sections: {
        keyword: sectionKeyword,
        views: sectionViews,
        interactions: sectionInteractions,
        userActions: sectionUserActions,
      },
      createdAt: Date.now(),
    });

    res.json({
      sessionId: sid,
      storeId: store.id,
      commentFallback: analyzer.commentFallback,
      sections: {
        keyword: sectionKeyword,
        views: sectionViews,
        interactions: sectionInteractions,
        userActions: sectionUserActions,
      },
    });

  } catch (err) {
    for (const f of tmpFiles) { try { fs.unlinkSync(f); } catch { /* ignore */ } }
    console.error('解析エラー:', err);
    res.status(500).json({ error: err instanceof Error ? err.message : '不明なエラー' });
  }
});

// ── Regenerate API（1セクションだけAI再生成）──────────────

app.post('/api/regenerate', async (req, res) => {
  const { sessionId, section } = req.body as { sessionId: string; section: string };
  const session = sessions.get(sessionId);
  if (!session) { res.status(404).json({ error: 'セッションが見つかりません（タイムアウトした可能性があります）' }); return; }

  try {
    const analyzer = new MeoAnalyzer(session.apiKey, session.provider, session.commentKey);
    const { prompts, month, screenshots } = session;
    let comment = { current: '', analysis: '' };

    if (section === 'keyword') {
      const imgPath = screenshots.keyword;
      if (imgPath && fs.existsSync(imgPath)) {
        const data = await analyzer.extractKeywordData(imgPath);
        comment = await analyzer.generateKeywordComment(data, month, prompts.keyword_current, prompts.keyword_analysis);
      }
    } else if (section === 'views' && screenshots.views && fs.existsSync(screenshots.views)) {
      const data = await analyzer.extractViewsData(screenshots.views);
      comment = await analyzer.generateViewsComment(data, month, prompts.views_current, prompts.views_analysis);
    } else if (section === 'interactions' && screenshots.interactions && fs.existsSync(screenshots.interactions)) {
      const data = await analyzer.extractInteractionData(screenshots.interactions);
      comment = await analyzer.generateInteractionComment(data, month, prompts.interactions_current, prompts.interactions_analysis);
    } else if (section === 'userActions' && screenshots.userActions && fs.existsSync(screenshots.userActions)) {
      const data = await analyzer.extractUserActionData(screenshots.userActions);
      comment = await analyzer.generateUserActionComment(data, month, prompts.userActions_current, prompts.userActions_analysis);
    }
    res.json(comment);
  } catch (err) {
    console.error('regenerateエラー:', err);
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
