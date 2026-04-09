import express from 'express';
import multer from 'multer';
import * as path from 'path';
import * as fs from 'fs';
import * as os from 'os';
import { MeoAnalyzer } from './analyzer.js';
import { ReportGenerator } from './report-generator.js';
import type { ReportInput, SlideData } from './types.js';

const app = express();
const PORT = process.env['PORT'] ?? 3000;

// Serve static files (frontend)
app.use(express.static(path.join(__dirname, 'public')));

// File upload setup (memory storage)
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
  limits: { fileSize: 20 * 1024 * 1024 }, // 20MB
});

const uploadFields = upload.fields([
  { name: 'keyword', maxCount: 1 },
  { name: 'views', maxCount: 1 },
  { name: 'interactions', maxCount: 1 },
  { name: 'userActions', maxCount: 1 },
]);

app.post('/api/generate', uploadFields, async (req, res) => {
  const tmpFiles: string[] = [];

  try {
    const { storeName, month, year, apiKey } = req.body as Record<string, string>;

    if (!storeName || !month || !year || !apiKey) {
      res.status(400).json({ error: '必須パラメータが不足しています' });
      return;
    }

    const files = req.files as Record<string, Express.Multer.File[]>;
    const screenshots: ReportInput['screenshots'] = {};

    for (const key of ['keyword', 'views', 'interactions', 'userActions'] as const) {
      const file = files[key]?.[0];
      if (file) {
        screenshots[key] = file.path;
        tmpFiles.push(file.path);
      }
    }

    if (Object.keys(screenshots).length === 0) {
      res.status(400).json({ error: 'スクショが1枚もアップロードされていません' });
      return;
    }

    const analyzer = new MeoAnalyzer(apiKey);
    const monthNum = parseInt(month, 10);
    const slides: {
      keyword?: SlideData;
      views?: SlideData;
      interactions?: SlideData;
      userActions?: SlideData;
    } = {};

    // Analyze each screenshot
    if (screenshots.keyword) {
      console.log('🔍 キーワード順位を解析中...');
      const data = await analyzer.extractKeywordData(screenshots.keyword);
      const comment = await analyzer.generateKeywordComment(data, monthNum);
      slides.keyword = {
        title: `${monthNum}月対策キーワード順位ご報告`,
        imagePath: screenshots.keyword,
        currentStatus: comment.current,
        analysis: comment.analysis,
      };
    }

    if (screenshots.views) {
      console.log('👁️  閲覧ユーザー数を解析中...');
      const data = await analyzer.extractViewsData(screenshots.views);
      const comment = await analyzer.generateViewsComment(data, monthNum);
      slides.views = {
        title: '閲覧したユーザー数',
        imagePath: screenshots.views,
        currentStatus: comment.current,
        analysis: comment.analysis,
      };
    }

    if (screenshots.interactions) {
      console.log('🔄 インタラクション数を解析中...');
      const data = await analyzer.extractInteractionData(screenshots.interactions);
      const comment = await analyzer.generateInteractionComment(data, monthNum);
      slides.interactions = {
        title: 'インタラクション数',
        imagePath: screenshots.interactions,
        currentStatus: comment.current,
        analysis: comment.analysis,
      };
    }

    if (screenshots.userActions) {
      console.log('📍 ユーザー行動データを解析中...');
      const data = await analyzer.extractUserActionData(screenshots.userActions);
      const comment = await analyzer.generateUserActionComment(data, monthNum);
      slides.userActions = {
        title: 'ユーザー行動データ（来店・売上に直結）',
        imagePath: screenshots.userActions,
        currentStatus: comment.current,
        analysis: comment.analysis,
      };
    }

    // Generate PowerPoint
    const input: ReportInput = {
      storeName,
      month: monthNum,
      year: parseInt(year, 10),
      screenshots,
      apiKey,
    };

    const outputPath = path.join(os.tmpdir(), `meo-report-${Date.now()}.pptx`);
    tmpFiles.push(outputPath);

    const generator = new ReportGenerator();
    await generator.generateReport(input, slides, outputPath);

    const filename = `MEO対策レポート_${storeName}_${year}年${month}月.pptx`;
    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.presentationml.presentation');
    res.setHeader('Content-Disposition', `attachment; filename*=UTF-8''${encodeURIComponent(filename)}`);
    res.sendFile(outputPath, err => {
      if (err) console.error('送信エラー:', err);
      // Cleanup temp files
      for (const f of tmpFiles) {
        try { fs.unlinkSync(f); } catch { /* ignore */ }
      }
    });

  } catch (err) {
    // Cleanup on error
    for (const f of tmpFiles) {
      try { fs.unlinkSync(f); } catch { /* ignore */ }
    }
    console.error('生成エラー:', err);
    const msg = err instanceof Error ? err.message : '不明なエラー';
    res.status(500).json({ error: msg });
  }
});

app.listen(PORT, () => {
  console.log('');
  console.log('✅ MEOレポーター 起動完了');
  console.log(`   ブラウザで開く → http://localhost:${PORT}`);
  console.log('');
});
