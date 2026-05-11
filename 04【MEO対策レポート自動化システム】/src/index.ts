import * as path from 'path';
import * as fs from 'fs';
import { MeoAnalyzer } from './analyzer.js';
import { ReportGenerator } from './report-generator.js';

function printUsage() {
  console.log(`
使い方:
  node dist/index.js [オプション]

必須オプション:
  --store <店舗名>           店舗名
  --month <月>              対象月 (1-12)
  --year <年>               対象年 (例: 2026)

スクショ画像 (PNG/JPG):
  --keyword <ファイルパス>   キーワード順位スクショ
  --views <ファイルパス>     閲覧ユーザー数スクショ
  --interactions <パス>     インタラクション数スクショ
  --user-actions <パス>     ユーザー行動データスクショ

その他:
  --output <ファイルパス>    出力先 (デフォルト: ./output/レポート_店舗名_年月.pptx)
  --api-key <APIキー>       Anthropic APIキー (環境変数 ANTHROPIC_API_KEY でも可)

例:
  node dist/index.js \\
    --store "○○整骨院" \\
    --month 1 \\
    --year 2026 \\
    --keyword ./screenshots/keyword.png \\
    --views ./screenshots/views.png \\
    --interactions ./screenshots/interactions.png \\
    --user-actions ./screenshots/user-actions.png
`);
}

function parseArgs(args: string[]): Record<string, string> {
  const result: Record<string, string> = {};
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg?.startsWith('--') && i + 1 < args.length) {
      const key = arg.slice(2);
      result[key] = args[i + 1] ?? '';
      i++;
    }
  }
  return result;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));

  if (!args['store'] || !args['month'] || !args['year']) {
    printUsage();
    process.exit(1);
  }

  const apiKey = args['api-key'] ?? process.env['ANTHROPIC_API_KEY'] ?? '';
  if (!apiKey) {
    console.error('❌ Anthropic APIキーが必要です。--api-key または ANTHROPIC_API_KEY 環境変数を設定してください。');
    process.exit(1);
  }

  const input = {
    storeName: args['store'],
    month: parseInt(args['month'] ?? '1', 10),
    year: parseInt(args['year'] ?? '2026', 10),
    screenshots: {
      keyword: args['keyword'],
      views: args['views'],
      interactions: args['interactions'],
      userActions: args['user-actions'],
    },
    apiKey,
  };

  const outputPath = args['output'] ?? path.join(
    process.cwd(), 'output',
    `MEO対策レポート_${input.storeName}_${input.year}年${input.month}月.pptx`
  );

  // Create output directory
  const outputDir = path.dirname(outputPath);
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  const analyzer = new MeoAnalyzer(apiKey);
  const slides: any = {};

  console.log(`📊 MEO対策レポート生成開始`);
  console.log(`   店舗: ${input.storeName}`);
  console.log(`   対象: ${input.year}年${input.month}月`);
  console.log('');

  // Process keyword slide
  if (input.screenshots.keyword && fs.existsSync(input.screenshots.keyword)) {
    console.log('🔍 キーワード順位データを解析中...');
    const data = await analyzer.extractKeywordData(input.screenshots.keyword);
    const comment = await analyzer.generateKeywordComment(data, input.month);
    slides.keyword = {
      title: `${input.month}月対策キーワード順位ご報告`,
      imagePath: input.screenshots.keyword,
      currentStatus: comment.current,
      analysis: comment.analysis,
    };
    console.log('   ✅ 完了');
  } else if (input.screenshots.keyword) {
    console.log(`⚠️  キーワード画像が見つかりません: ${input.screenshots.keyword}`);
  }

  // Process views slide
  if (input.screenshots.views && fs.existsSync(input.screenshots.views)) {
    console.log('👁️  閲覧ユーザー数データを解析中...');
    const data = await analyzer.extractViewsData(input.screenshots.views);
    const comment = await analyzer.generateViewsComment(data, input.month);
    slides.views = {
      title: '閲覧したユーザー数',
      imagePath: input.screenshots.views,
      currentStatus: comment.current,
      analysis: comment.analysis,
    };
    console.log('   ✅ 完了');
  }

  // Process interactions slide
  if (input.screenshots.interactions && fs.existsSync(input.screenshots.interactions)) {
    console.log('🔄 インタラクション数データを解析中...');
    const data = await analyzer.extractInteractionData(input.screenshots.interactions);
    const comment = await analyzer.generateInteractionComment(data, input.month);
    slides.interactions = {
      title: 'インタラクション数',
      imagePath: input.screenshots.interactions,
      currentStatus: comment.current,
      analysis: comment.analysis,
    };
    console.log('   ✅ 完了');
  }

  // Process user actions slide
  if (input.screenshots.userActions && fs.existsSync(input.screenshots.userActions)) {
    console.log('📍 ユーザー行動データを解析中...');
    const data = await analyzer.extractUserActionData(input.screenshots.userActions);
    const comment = await analyzer.generateUserActionComment(data, input.month);
    slides.userActions = {
      title: 'ユーザー行動データ（来店・売上に直結）',
      imagePath: input.screenshots.userActions,
      currentStatus: comment.current,
      analysis: comment.analysis,
    };
    console.log('   ✅ 完了');
  }

  // Generate PowerPoint
  console.log('');
  console.log('📝 PowerPointを生成中...');
  const generator = new ReportGenerator();
  await generator.generateReport(input, slides, outputPath);
}

main().catch(err => {
  console.error('❌ エラーが発生しました:', err);
  process.exit(1);
});
