import Anthropic from '@anthropic-ai/sdk';
import * as fs from 'fs';
import * as path from 'path';
import type {
  KeywordData,
  ViewsData,
  InteractionData,
  UserActionData,
} from './types.js';

export class MeoAnalyzer {
  private client: Anthropic;

  constructor(apiKey: string) {
    this.client = new Anthropic({ apiKey });
  }

  private loadImage(imagePath: string): { base64: string; mediaType: 'image/jpeg' | 'image/png' | 'image/gif' | 'image/webp' } {
    const ext = path.extname(imagePath).toLowerCase();
    const mediaTypeMap: Record<string, 'image/jpeg' | 'image/png' | 'image/gif' | 'image/webp'> = {
      '.jpg': 'image/jpeg',
      '.jpeg': 'image/jpeg',
      '.png': 'image/png',
      '.gif': 'image/gif',
      '.webp': 'image/webp',
    };
    const mediaType = mediaTypeMap[ext] ?? 'image/png';
    const base64 = fs.readFileSync(imagePath).toString('base64');
    return { base64, mediaType };
  }

  async extractKeywordData(imagePath: string): Promise<KeywordData> {
    const image = this.loadImage(imagePath);
    const response = await this.client.messages.create({
      model: 'claude-opus-4-6',
      max_tokens: 1024,
      messages: [{
        role: 'user',
        content: [
          {
            type: 'image',
            source: { type: 'base64', media_type: image.mediaType, data: image.base64 },
          },
          {
            type: 'text',
            text: `このMEO対策のキーワード順位レポート画像から、以下のJSON形式でデータを抽出してください。
順位が表示されていないキーワードは "圏外" と記載してください。

{
  "keywords": [
    { "keyword": "キーワード名", "rank": "順位（数字または圏外）" }
  ],
  "summary": "全体的な順位状況の一言まとめ（例：圏外中心、3〜5位が多い、など）"
}

JSONのみ返してください。`,
          },
        ],
      }],
    });

    const text = response.content[0]?.type === 'text' ? response.content[0].text : '{}';
    const jsonMatch = text.match(/\{[\s\S]*\}/);
    return jsonMatch ? JSON.parse(jsonMatch[0]) as KeywordData : { keywords: [], summary: '順位データなし' };
  }

  async extractViewsData(imagePath: string): Promise<ViewsData> {
    const image = this.loadImage(imagePath);
    const response = await this.client.messages.create({
      model: 'claude-opus-4-6',
      max_tokens: 512,
      messages: [{
        role: 'user',
        content: [
          {
            type: 'image',
            source: { type: 'base64', media_type: image.mediaType, data: image.base64 },
          },
          {
            type: 'text',
            text: `この閲覧ユーザー数グラフから数値を抽出してください。

{
  "currentMonth": 当月件数（数字）,
  "previousYear": 前年同月件数（数字、不明なら0）,
  "trend": "up/down/flat/new のいずれか（newは対策開始初月）"
}

JSONのみ返してください。`,
          },
        ],
      }],
    });

    const text = response.content[0]?.type === 'text' ? response.content[0].text : '{}';
    const jsonMatch = text.match(/\{[\s\S]*\}/);
    return jsonMatch ? JSON.parse(jsonMatch[0]) as ViewsData : { currentMonth: 0, previousYear: 0, trend: 'new' };
  }

  async extractInteractionData(imagePath: string): Promise<InteractionData> {
    const image = this.loadImage(imagePath);
    const response = await this.client.messages.create({
      model: 'claude-opus-4-6',
      max_tokens: 512,
      messages: [{
        role: 'user',
        content: [
          {
            type: 'image',
            source: { type: 'base64', media_type: image.mediaType, data: image.base64 },
          },
          {
            type: 'text',
            text: `このインタラクション数グラフから数値を抽出してください。

{
  "currentMonth": 当月件数（数字）,
  "previousYear": 前年同月件数（数字、不明なら0）,
  "interactionRate": インタラクション率（%の数字、不明なら0）,
  "trend": "up/down/flat/new のいずれか"
}

JSONのみ返してください。`,
          },
        ],
      }],
    });

    const text = response.content[0]?.type === 'text' ? response.content[0].text : '{}';
    const jsonMatch = text.match(/\{[\s\S]*\}/);
    return jsonMatch ? JSON.parse(jsonMatch[0]) as InteractionData : { currentMonth: 0, previousYear: 0, interactionRate: 0, trend: 'new' };
  }

  async extractUserActionData(imagePath: string): Promise<UserActionData> {
    const image = this.loadImage(imagePath);
    const response = await this.client.messages.create({
      model: 'claude-opus-4-6',
      max_tokens: 512,
      messages: [{
        role: 'user',
        content: [
          {
            type: 'image',
            source: { type: 'base64', media_type: image.mediaType, data: image.base64 },
          },
          {
            type: 'text',
            text: `このユーザー行動データから数値を抽出してください（通話数、Webサイト、ルート検索数、予約数）。

{
  "calls": 通話数当月（数字）,
  "website": Webサイト当月（数字）,
  "routes": ルート検索数当月（数字）,
  "reservations": 予約数当月（数字）,
  "previousCalls": 通話数前年同月（数字、不明なら0）,
  "previousWebsite": Webサイト前年同月（数字、不明なら0）,
  "previousRoutes": ルート検索数前年同月（数字、不明なら0）,
  "previousReservations": 予約数前年同月（数字、不明なら0）
}

JSONのみ返してください。`,
          },
        ],
      }],
    });

    const text = response.content[0]?.type === 'text' ? response.content[0].text : '{}';
    const jsonMatch = text.match(/\{[\s\S]*\}/);
    return jsonMatch ? JSON.parse(jsonMatch[0]) as UserActionData : {
      calls: 0, website: 0, routes: 0, reservations: 0,
      previousCalls: 0, previousWebsite: 0, previousRoutes: 0, previousReservations: 0,
    };
  }

  private buildCommentPrompt(instruction: string, month: number, dataText: string): string {
    return `${instruction.replace(/\{month\}/g, String(month))}

データ:
${dataText}

以下のJSON形式で返してください:
{
  "current": "【現状】の説明文",
  "analysis": "【分析】の説明文"
}

JSONのみ返してください。`;
  }

  private async callComment(prompt: string): Promise<{ current: string; analysis: string }> {
    const response = await this.client.messages.create({
      model: 'claude-opus-4-6',
      max_tokens: 800,
      messages: [{ role: 'user', content: prompt }],
    });
    const text = response.content[0]?.type === 'text' ? response.content[0].text : '{}';
    const jsonMatch = text.match(/\{[\s\S]*\}/);
    return jsonMatch ? JSON.parse(jsonMatch[0]) as { current: string; analysis: string } : { current: '', analysis: '' };
  }

  async generateKeywordComment(data: KeywordData, month: number, customPrompt?: string): Promise<{ current: string; analysis: string }> {
    const instruction = customPrompt ?? `MEO対策レポートの{month}月度キーワード順位について、クライアント向けの説明文を生成してください。\n\n【現状】は1〜2文で事実を簡潔に記載してください。\n【分析】は3〜5文でMEOの専門的な視点から前向きに記述し、課題があれば改善提案も含めてください。`;
    return this.callComment(this.buildCommentPrompt(instruction, month, JSON.stringify(data, null, 2)));
  }

  async generateViewsComment(data: ViewsData, month: number, customPrompt?: string): Promise<{ current: string; analysis: string }> {
    const instruction = customPrompt ?? `MEO対策レポートの{month}月度閲覧ユーザー数について、クライアント向けの説明文を生成してください。\n\n【現状】は1文で件数を明記してください。\n【分析】は3〜5文でマーケティング視点から前向きに記述し、前年比・トレンドにも触れてください。`;
    const dataText = `当月: ${data.currentMonth}件 / 前年同月: ${data.previousYear}件 / トレンド: ${data.trend}`;
    return this.callComment(this.buildCommentPrompt(instruction, month, dataText));
  }

  async generateInteractionComment(data: InteractionData, month: number, customPrompt?: string): Promise<{ current: string; analysis: string }> {
    const instruction = customPrompt ?? `MEO対策レポートの{month}月度インタラクション数について、クライアント向けの説明文を生成してください。\n\n【現状】は1文で件数とインタラクション率を明記してください。\n【分析】は3〜5文で「閲覧から行動への転換」という視点で分析し、ポジティブシグナルとしての意味を伝えてください。`;
    const dataText = `当月: ${data.currentMonth}件 / 前年同月: ${data.previousYear}件 / インタラクション率: ${data.interactionRate}% / トレンド: ${data.trend}`;
    return this.callComment(this.buildCommentPrompt(instruction, month, dataText));
  }

  async generateUserActionComment(data: UserActionData, month: number, customPrompt?: string): Promise<{ current: string; analysis: string }> {
    const instruction = customPrompt ?? `MEO対策レポートの{month}月度ユーザー行動データについて、クライアント向けの説明文を生成してください。\n\n【現状】は1〜2文で各指標の数値を列挙してください。\n【分析】は4〜6文で記述し、強い指標は来店意欲の高さとして評価し、弱い指標はCTA・情報設計の改善提案として伝えてください。`;
    const dataText = `通話: ${data.calls}件(前年${data.previousCalls}) / Web: ${data.website}件(前年${data.previousWebsite}) / ルート: ${data.routes}件(前年${data.previousRoutes}) / 予約: ${data.reservations}件(前年${data.previousReservations})`;
    return this.callComment(this.buildCommentPrompt(instruction, month, dataText));
  }
}
