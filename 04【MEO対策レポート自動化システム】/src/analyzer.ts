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
    // Gemini使用時はClaudeを呼ばないので、ダミーキーでSDKを初期化する（空文字列だとSDKがエラーを投げるため）
    this.client = new Anthropic({ apiKey: anthropicKey || 'dummy-not-used' });
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

  // Gemini Vision で画像解析
  private async extractWithGemini(imagePath: string, prompt: string): Promise<string> {
    const image = this.loadImage(imagePath);
    const res = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${this.commentApiKey}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ parts: [
            { inline_data: { mime_type: image.mediaType, data: image.base64 } },
            { text: prompt },
          ]}],
        }),
      }
    );
    if (!res.ok) {
      console.warn(`[Gemini Vision] エラー ${res.status}`);
      return '{}';
    }
    const data = await res.json() as { candidates: Array<{ content: { parts: Array<{ text: string }> } }> };
    return data.candidates?.[0]?.content?.parts?.[0]?.text ?? '{}';
  }

  // Claude Vision で画像解析
  private async extractWithClaude(imagePath: string, prompt: string, maxTokens = 1024): Promise<string> {
    const image = this.loadImage(imagePath);
    const response = await this.client.messages.create({
      model: 'claude-sonnet-4-6',
      max_tokens: maxTokens,
      messages: [{
        role: 'user',
        content: [
          { type: 'image', source: { type: 'base64', media_type: image.mediaType, data: image.base64 } },
          { type: 'text', text: prompt },
        ],
      }],
    });
    return response.content[0]?.type === 'text' ? response.content[0].text : '{}';
  }

  private async extractImage(imagePath: string, prompt: string, maxTokens = 512): Promise<string> {
    return this.commentProvider === 'gemini'
      ? this.extractWithGemini(imagePath, prompt)
      : this.extractWithClaude(imagePath, prompt, maxTokens);
  }

  async extractKeywordData(imagePath: string): Promise<KeywordData> {
    const text = await this.extractImage(imagePath, `画像はGoogleビジネスプロフィールのMEO対策キーワード順位レポートです。
画像内に表示されているすべてのキーワードとその順位を読み取り、以下のJSON形式で返してください。
順位が表示されていないキーワードは rank を "圏外" としてください。
必ずJSONのみを返してください（説明文不要）。

{"keywords":[{"keyword":"キーワード文字列","rank":"数字または圏外"}],"summary":"順位状況の一言まとめ"}`, 1024);
    const jsonMatch = text.match(/\{[\s\S]*\}/);
    try {
      return jsonMatch ? JSON.parse(jsonMatch[0]) as KeywordData : { keywords: [], summary: '順位データなし' };
    } catch {
      console.warn('[extractKeywordData] JSON parse failed:', text.slice(0, 300));
      return { keywords: [], summary: '解析失敗（再解析を試してください）' };
    }
  }

  async extractViewsData(imagePath: string): Promise<ViewsData> {
    const text = await this.extractImage(imagePath, `画像はGoogleビジネスプロフィールの閲覧ユーザー数グラフです。
グラフから当月と前年同月の数値を読み取り、以下のJSON形式のみを返してください（説明文不要）。
trend は前年比で増加なら"up"、減少なら"down"、横ばいなら"flat"、初月なら"new"。

{"currentMonth":数字,"previousYear":数字,"trend":"up/down/flat/new"}`);
    const jsonMatch = text.match(/\{[\s\S]*\}/);
    try {
      return jsonMatch ? JSON.parse(jsonMatch[0]) as ViewsData : { currentMonth: 0, previousYear: 0, trend: 'new' };
    } catch {
      console.warn('[extractViewsData] JSON parse failed:', text.slice(0, 300));
      return { currentMonth: 0, previousYear: 0, trend: 'new' };
    }
  }

  async extractInteractionData(imagePath: string): Promise<InteractionData> {
    const text = await this.extractImage(imagePath, `画像はGoogleビジネスプロフィールのインタラクション数グラフです。
グラフから当月・前年同月の数値とインタラクション率を読み取り、以下のJSON形式のみを返してください（説明文不要）。
trend は前年比で増加なら"up"、減少なら"down"、横ばいなら"flat"、初月なら"new"。

{"currentMonth":数字,"previousYear":数字,"interactionRate":パーセントの数字,"trend":"up/down/flat/new"}`);
    const jsonMatch = text.match(/\{[\s\S]*\}/);
    try {
      return jsonMatch ? JSON.parse(jsonMatch[0]) as InteractionData : { currentMonth: 0, previousYear: 0, interactionRate: 0, trend: 'new' };
    } catch {
      console.warn('[extractInteractionData] JSON parse failed:', text.slice(0, 300));
      return { currentMonth: 0, previousYear: 0, interactionRate: 0, trend: 'new' };
    }
  }

  async extractUserActionData(imagePath: string): Promise<UserActionData> {
    const text = await this.extractImage(imagePath, `画像はGoogleビジネスプロフィールのユーザー行動データです（通話数・Webサイト・ルート検索・予約数が含まれます）。
各指標の当月と前年同月の数値を読み取り、以下のJSON形式のみを返してください（説明文不要）。
表示されていない項目は0としてください。

{"calls":数字,"website":数字,"routes":数字,"reservations":数字,"previousCalls":数字,"previousWebsite":数字,"previousRoutes":数字,"previousReservations":数字}`);
    const jsonMatch = text.match(/\{[\s\S]*\}/);
    try {
      return jsonMatch ? JSON.parse(jsonMatch[0]) as UserActionData : {
        calls: 0, website: 0, routes: 0, reservations: 0,
        previousCalls: 0, previousWebsite: 0, previousRoutes: 0, previousReservations: 0,
      };
    } catch {
      console.warn('[extractUserActionData] JSON parse failed:', text.slice(0, 300));
      return {
        calls: 0, website: 0, routes: 0, reservations: 0,
        previousCalls: 0, previousWebsite: 0, previousRoutes: 0, previousReservations: 0,
      };
    }
  }

  private async callClaudeComment(prompt: string): Promise<string> {
    // prefill でJSONを強制（{"current":" から始まる応答を保証）
    const prefill = '{"current":"';
    const response = await this.client.messages.create({
      model: 'claude-sonnet-4-6',
      max_tokens: 1024,
      messages: [
        { role: 'user', content: prompt },
        { role: 'assistant', content: prefill },
      ],
    });
    const rawText = response.content[0]?.type === 'text' ? response.content[0].text : '';
    const fullText = prefill + rawText;
    console.log('[Claude comment] raw response:', fullText.slice(0, 400));
    return fullText;
  }

  private async callGeminiText(prompt: string): Promise<string> {
    const res = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${this.commentApiKey}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ parts: [{ text: prompt }] }],
        }),
      }
    );
    if (!res.ok) {
      const body = await res.text().catch(() => '');
      const reason = res.status === 429 ? '無料枠超過 (429)' : `エラー ${res.status}: ${body.slice(0, 300)}`;
      throw new Error(`[Gemini] ${reason}`);
    }
    const data = await res.json() as { candidates: Array<{ content: { parts: Array<{ text: string }> } }> };
    const text = data.candidates?.[0]?.content?.parts?.[0]?.text ?? '';
    console.log('[Gemini comment] raw response:', text.slice(0, 400));
    return text;
  }

  private async callComment(prompt: string): Promise<{ current: string; analysis: string }> {
    let text = '';
    try {
      if (this.commentProvider === 'openai') {
        const res = await fetch('https://api.openai.com/v1/chat/completions', {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${this.commentApiKey}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ model: 'gpt-4o', messages: [{ role: 'user', content: prompt }], max_tokens: 800,
            response_format: { type: 'json_object' } }),
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
        try {
          text = await this.callGeminiText(prompt);
        } catch (err) {
          console.warn(`${err} → Claude にフォールバック`);
          this.commentFallback = true;
          try { text = await this.callClaudeComment(prompt); } catch { /* ignore */ }
        }

      } else {
        text = await this.callClaudeComment(prompt);
      }
    } catch (err) {
      console.error(`[${this.commentProvider}] 文章生成エラー:`, err);
    }

    // コードブロック内のJSONも抽出できるように
    const codeMatch = text.match(/```(?:json)?\s*(\{[\s\S]*?\})\s*```/);
    const rawJson = codeMatch?.[1] ?? text.match(/\{[\s\S]*\}/)?.[0] ?? '';
    if (!rawJson) {
      console.warn('[callComment] JSON not found in response:', text.slice(0, 300));
      // フォールバック: "current" / "analysis" キーをテキストから直接抽出
      const cur = text.match(/"current"\s*:\s*"([\s\S]*?)(?<!\\)"(?:\s*,|\s*\})/)?.[1] ?? '';
      const ana = text.match(/"analysis"\s*:\s*"([\s\S]*?)(?<!\\)"(?:\s*\})/)?.[1] ?? '';
      return { current: cur.replace(/\\n/g, '\n'), analysis: ana.replace(/\\n/g, '\n') };
    }
    try {
      const parsed = JSON.parse(rawJson) as { current?: string; analysis?: string };
      const result = { current: parsed.current ?? '', analysis: parsed.analysis ?? '' };
      console.log('[callComment] parsed OK:', JSON.stringify(result).slice(0, 200));
      return result;
    } catch {
      // 制御文字・改行をエスケープして再試行
      try {
        const cleaned = rawJson.replace(/[\x00-\x1F\x7F]/g, c => {
          if (c === '\n') return '\\n';
          if (c === '\r') return '\\r';
          if (c === '\t') return '\\t';
          return '';
        });
        const parsed = JSON.parse(cleaned) as { current?: string; analysis?: string };
        return { current: parsed.current ?? '', analysis: parsed.analysis ?? '' };
      } catch {
        // 最終フォールバック: 正規表現でキー値を直接取り出す
        console.warn('[callComment] JSON parse error after cleanup:', rawJson.slice(0, 300));
        const cur = rawJson.match(/"current"\s*:\s*"([\s\S]*?)(?<!\\)"(?:\s*,|\s*\})/)?.[1] ?? '';
        const ana = rawJson.match(/"analysis"\s*:\s*"([\s\S]*?)(?<!\\)"(?:\s*\})/)?.[1] ?? '';
        return {
          current: cur.replace(/\\n/g, '\n'),
          analysis: ana.replace(/\\n/g, '\n'),
        };
      }
    }
  }

  private buildPrompt(sectionLabel: string, month: number, dataText: string, curInst: string, anaInst: string): string {
    return `MEO対策レポートの${month}月度${sectionLabel}について、クライアント向けの説明文を日本語で生成してください。

データ:
${dataText}

【現状】の指示: ${curInst}
【分析】の指示: ${anaInst}

以下のJSON形式で返してください。currentキーに【現状】の文章、analysisキーに【分析】の文章を入れてください。
改行は\\nで表してください。JSONのみ返してください。
{"current":"...","analysis":"..."}`;
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
