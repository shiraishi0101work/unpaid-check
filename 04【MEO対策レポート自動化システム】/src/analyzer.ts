import Anthropic from '@anthropic-ai/sdk';
import * as fs from 'fs';
import * as path from 'path';
import type {
  KeywordData,
  ViewsData,
  InteractionData,
  UserActionData,
} from './types.js';

export type CommentProvider = 'claude' | 'openai' | 'gemini';

export class MeoAnalyzer {
  private client: Anthropic;
  private commentProvider: CommentProvider;
  private commentApiKey: string;
  public commentFallback = false; // Gemini/OpenAI → Claude フォールバックが発生したか

  constructor(anthropicKey: string, commentProvider: CommentProvider = 'claude', commentApiKey?: string) {
    this.client = new Anthropic({ apiKey: anthropicKey });
    this.commentProvider = commentProvider;
    this.commentApiKey = commentApiKey ?? anthropicKey;
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

  private async callClaudeComment(prompt: string): Promise<string> {
    const response = await this.client.messages.create({
      model: 'claude-opus-4-6',
      max_tokens: 800,
      messages: [{ role: 'user', content: prompt }],
    });
    return response.content[0]?.type === 'text' ? response.content[0].text : '{}';
  }

  private async callComment(prompt: string): Promise<{ current: string; analysis: string }> {
    let text = '';
    try {
      if (this.commentProvider === 'openai') {
        const res = await fetch('https://api.openai.com/v1/chat/completions', {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${this.commentApiKey}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ model: 'gpt-4o', messages: [{ role: 'user', content: prompt }], max_tokens: 800 }),
        });
        if (!res.ok) {
          console.warn(`[OpenAI] エラー ${res.status} → Claude にフォールバック`);
          this.commentFallback = true;
          text = await this.callClaudeComment(prompt);
        } else {
          const data = await res.json() as { choices: Array<{ message: { content: string } }> };
          text = data.choices?.[0]?.message?.content ?? '{}';
        }

      } else if (this.commentProvider === 'gemini') {
        const res = await fetch(
          `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${this.commentApiKey}`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ contents: [{ parts: [{ text: prompt }] }] }),
          }
        );
        if (!res.ok) {
          const reason = res.status === 429 ? '無料枠超過 (429)' : `エラー ${res.status}`;
          console.warn(`[Gemini] ${reason} → Claude にフォールバック`);
          this.commentFallback = true;
          text = await this.callClaudeComment(prompt);
        } else {
          const data = await res.json() as { candidates: Array<{ content: { parts: Array<{ text: string }> } }> };
          text = data.candidates?.[0]?.content?.parts?.[0]?.text ?? '{}';
        }

      } else {
        text = await this.callClaudeComment(prompt);
      }
    } catch (err) {
      console.error(`[${this.commentProvider}] 文章生成エラー → Claude にフォールバック:`, err);
      this.commentFallback = true;
      try { text = await this.callClaudeComment(prompt); } catch { /* ignore */ }
    }
    const jsonMatch = text.match(/\{[\s\S]*\}/);
    return jsonMatch ? JSON.parse(jsonMatch[0]) as { current: string; analysis: string } : { current: '', analysis: '' };
  }

  private buildPrompt(sectionLabel: string, month: number, dataText: string, curInst: string, anaInst: string): string {
    return `MEO対策レポートの${month}月度${sectionLabel}について、クライアント向けの説明文を生成してください。

データ:
${dataText}

【現状】の指示: ${curInst}
【分析】の指示: ${anaInst}

以下のJSON形式で返してください:
{
  "current": "【現状】の説明文",
  "analysis": "【分析】の説明文"
}

JSONのみ返してください。`;
  }

  async generateKeywordComment(data: KeywordData, month: number, curInst?: string, anaInst?: string): Promise<{ current: string; analysis: string }> {
    return this.callComment(this.buildPrompt(
      'キーワード順位', month, JSON.stringify(data, null, 2),
      curInst ?? '1〜2文で、対策キーワードの順位状況を事実として簡潔に記載してください。',
      anaInst ?? '3〜5文で、MEOの専門的な視点から順位の意味を前向きに解説してください。課題があれば改善提案も含めてください。',
    ));
  }

  async generateViewsComment(data: ViewsData, month: number, curInst?: string, anaInst?: string): Promise<{ current: string; analysis: string }> {
    const dataText = `当月: ${data.currentMonth}件 / 前年同月: ${data.previousYear}件 / トレンド: ${data.trend}`;
    return this.callComment(this.buildPrompt(
      '閲覧ユーザー数', month, dataText,
      curInst ?? '1文で、今月の閲覧ユーザー数を明記してください。',
      anaInst ?? '3〜5文で、マーケティング視点から閲覧数の意味を前向きに解説してください。前年比・トレンドにも触れてください。',
    ));
  }

  async generateInteractionComment(data: InteractionData, month: number, curInst?: string, anaInst?: string): Promise<{ current: string; analysis: string }> {
    const dataText = `当月: ${data.currentMonth}件 / 前年同月: ${data.previousYear}件 / インタラクション率: ${data.interactionRate}% / トレンド: ${data.trend}`;
    return this.callComment(this.buildPrompt(
      'インタラクション数', month, dataText,
      curInst ?? '1文で、今月のインタラクション数とインタラクション率を明記してください。',
      anaInst ?? '3〜5文で、「閲覧から行動への転換」という視点で分析し、ポジティブシグナルとしての意味を伝えてください。',
    ));
  }

  async generateUserActionComment(data: UserActionData, month: number, curInst?: string, anaInst?: string): Promise<{ current: string; analysis: string }> {
    const dataText = `通話: ${data.calls}件(前年${data.previousCalls}) / Web: ${data.website}件(前年${data.previousWebsite}) / ルート: ${data.routes}件(前年${data.previousRoutes}) / 予約: ${data.reservations}件(前年${data.previousReservations})`;
    return this.callComment(this.buildPrompt(
      'ユーザー行動データ', month, dataText,
      curInst ?? '1〜2文で、各指標の数値を列挙してください。',
      anaInst ?? '4〜6文で、強い指標は来店意欲の高さとして評価し、弱い指標はCTA・情報設計の改善提案として伝えてください。',
    ));
  }
}
