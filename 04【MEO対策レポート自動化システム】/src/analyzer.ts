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
  public commentFallback = false;    // Gemini/OpenAI → Claude フォールバックが発生したか
  public templateFallback = false;   // AI全滅 → テンプレート文章を使用したか
  public lastError: string | null = null; // 最後に発生したAPIエラーメッセージ

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

  // Gemini Vision で画像解析（JSON強制モード）
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
          generationConfig: { responseMimeType: 'application/json' },
        }),
      }
    );
    if (!res.ok) {
      const body = await res.text().catch(() => '');
      const reason = res.status === 429 ? '無料枠超過 (429)' : `エラー ${res.status}: ${body.slice(0, 200)}`;
      this.recordError(new Error(reason), 'Gemini Vision');
      return '{}';
    }
    const data = await res.json() as { candidates: Array<{ content: { parts: Array<{ text: string }> } }> };
    const text = data.candidates?.[0]?.content?.parts?.[0]?.text ?? '{}';
    console.log('[Gemini Vision] response:', text.slice(0, 300));
    return text;
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

  private recordError(err: unknown, context: string): void {
    const msg = err instanceof Error ? err.message : String(err);
    this.lastError = `[${context}] ${msg}`;
    console.error(this.lastError);
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
          const body = await res.text().catch(() => '');
          const errMsg = `OpenAI APIエラー ${res.status}: ${body.slice(0, 200)}`;
          this.lastError = errMsg;
          console.warn(`${errMsg} → Claude にフォールバック`);
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
          this.recordError(err, 'Gemini');
          console.warn(`${this.lastError} → Claude にフォールバック`);
          this.commentFallback = true;
          try {
            text = await this.callClaudeComment(prompt);
          } catch (claudeErr) {
            this.recordError(claudeErr, 'Claude(fallback)');
          }
        }

      } else {
        text = await this.callClaudeComment(prompt);
      }
    } catch (err) {
      this.recordError(err, this.commentProvider);
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

  // ─── テンプレートフォールバック（AIが応答しない場合に使用）────────────────

  private templateKeyword(data: KeywordData, month: number): { current: string; analysis: string } {
    const ranked = data.keywords.filter(k => String(k.rank) !== '圏外' && String(k.rank) !== '');
    const gaiken = data.keywords.filter(k => String(k.rank) === '圏外');
    const rankList = ranked.map(k => `「${k.keyword}」${k.rank}位`).join('、');
    const gaikenList = gaiken.map(k => `「${k.keyword}」`).join('、');

    const cur = ranked.length > 0
      ? `${month}月の対策キーワード順位は、${rankList}となっています。${gaiken.length > 0 ? `${gaikenList}は現在圏外です。` : ''}`
      : `${month}月の対策キーワードは現在圏外が中心の状況です。`;

    const ana = `Googleマップ検索での表示順位は、MEO対策の継続によって徐々に改善されていきます。\n上位表示を目指すためには、口コミの獲得・丁寧な返信対応、写真や投稿の定期的な更新が重要です。\n特に検索数の多いキーワードで上位表示されると、閲覧数・来店数の大幅な向上が期待できます。\n引き続き対策を継続し、安定した上位表示の維持を目指してまいります。`;

    return { current: cur, analysis: ana };
  }

  private templateViews(data: ViewsData, month: number): { current: string; analysis: string } {
    const cur = `${month}月の閲覧ユーザー数は${data.currentMonth.toLocaleString()}件でした。`;
    const ratio = data.previousYear > 0
      ? `前年同月（${data.previousYear.toLocaleString()}件）比${Math.round(data.currentMonth / data.previousYear * 100)}%`
      : null;
    const trendMap: Record<string, string> = { up: '上昇傾向にあり', down: '前年を下回っており', flat: '前年並みで', new: 'MEO対策開始初月であり' };
    const trendText = trendMap[data.trend] ?? '';

    const ana = `Googleマップ上での閲覧ユーザーが${data.currentMonth.toLocaleString()}件を記録しました。\n${ratio ? ratio + 'と、' : ''}${trendText}、MEO対策の効果が着実に積み重なっています。\n閲覧数の増加はGoogleマップ上での認知度向上を示す重要な指標です。\n引き続きプロフィール情報の充実・写真の追加・口コミ対応を継続することで、さらなる閲覧数の向上が期待できます。`;

    return { current: cur, analysis: ana };
  }

  private templateInteractions(data: InteractionData, month: number): { current: string; analysis: string } {
    const cur = `${month}月のインタラクション数は${data.currentMonth.toLocaleString()}件（インタラクション率${data.interactionRate}%）でした。`;
    const total = data.currentMonth;
    const ana = `${month}月は閲覧ユーザーのうち${data.interactionRate}%にあたる${total.toLocaleString()}件のインタラクション（行動）が発生しました。\nこれは、Googleマップを見たユーザーが実際に「興味を持って行動した」ことを示すポジティブなシグナルです。\nインタラクション率をさらに高めるには、魅力的な写真の追加、正確な営業時間・サービス情報の掲載が効果的です。\n引き続き情報の充実を図り、閲覧から来店への転換率向上を目指してまいります。`;

    return { current: cur, analysis: ana };
  }

  private templateUserActions(data: UserActionData, month: number): { current: string; analysis: string } {
    const total = data.calls + data.website + data.routes + data.reservations;
    const cur = `${month}月のユーザー行動は、通話${data.calls}件・Webサイト${data.website}件・ルート検索${data.routes}件・予約${data.reservations}件でした。`;

    const highlights: string[] = [];
    if (data.calls > 0) highlights.push(`通話${data.calls}件は直接問い合わせへの意欲が高いことを示しています`);
    if (data.routes > 0) highlights.push(`ルート検索${data.routes}件は来店意欲の高さを示す重要な指標です`);
    if (data.website > 0) highlights.push(`Webサイト訪問${data.website}件はさらなる情報収集への関心を示しています`);

    const ana = `${month}月は来店・問い合わせに直結するユーザー行動が合計${total.toLocaleString()}件発生しました。\n${highlights.slice(0, 2).join('。\n')}。\n各指標を向上させるには、電話番号・Webサイトリンクの正確な掲載と、魅力的な写真・最新情報の投稿継続が重要です。\n引き続きGoogleビジネスプロフィールの充実を図り、来店数の増加を目指してまいります。`;

    return { current: cur, analysis: ana };
  }

  // ─── コメント生成（AI → テンプレートフォールバック）──────────────────────

  private withTemplateFallback<T>(
    aiResult: { current: string; analysis: string },
    templateFn: () => { current: string; analysis: string }
  ): { current: string; analysis: string } {
    if (!aiResult.current && !aiResult.analysis) {
      console.warn('[analyzer] AI returned empty text → using template fallback');
      this.templateFallback = true;
      return templateFn();
    }
    return aiResult;
  }

  async generateKeywordComment(data: KeywordData, month: number, curInst?: string, anaInst?: string): Promise<{ current: string; analysis: string }> {
    const ai = await this.callComment(this.buildPrompt(
      'キーワード順位', month, JSON.stringify(data, null, 2),
      curInst ?? '1〜2文で、対策キーワードの順位状況を事実として簡潔に記載してください。',
      anaInst ?? '3〜5文で、MEOの専門的な視点から順位の意味を前向きに解説してください。課題があれば改善提案も含めてください。',
    ));
    return this.withTemplateFallback(ai, () => this.templateKeyword(data, month));
  }

  async generateViewsComment(data: ViewsData, month: number, curInst?: string, anaInst?: string): Promise<{ current: string; analysis: string }> {
    const dataText = `当月: ${data.currentMonth}件 / 前年同月: ${data.previousYear}件 / トレンド: ${data.trend}`;
    const ai = await this.callComment(this.buildPrompt(
      '閲覧ユーザー数', month, dataText,
      curInst ?? '1文で、今月の閲覧ユーザー数を明記してください。',
      anaInst ?? '3〜5文で、マーケティング視点から閲覧数の意味を前向きに解説してください。前年比・トレンドにも触れてください。',
    ));
    return this.withTemplateFallback(ai, () => this.templateViews(data, month));
  }

  async generateInteractionComment(data: InteractionData, month: number, curInst?: string, anaInst?: string): Promise<{ current: string; analysis: string }> {
    const dataText = `当月: ${data.currentMonth}件 / 前年同月: ${data.previousYear}件 / インタラクション率: ${data.interactionRate}% / トレンド: ${data.trend}`;
    const ai = await this.callComment(this.buildPrompt(
      'インタラクション数', month, dataText,
      curInst ?? '1文で、今月のインタラクション数とインタラクション率を明記してください。',
      anaInst ?? '3〜5文で、「閲覧から行動への転換」という視点で分析し、ポジティブシグナルとしての意味を伝えてください。',
    ));
    return this.withTemplateFallback(ai, () => this.templateInteractions(data, month));
  }

  async generateUserActionComment(data: UserActionData, month: number, curInst?: string, anaInst?: string): Promise<{ current: string; analysis: string }> {
    const dataText = `通話: ${data.calls}件(前年${data.previousCalls}) / Web: ${data.website}件(前年${data.previousWebsite}) / ルート: ${data.routes}件(前年${data.previousRoutes}) / 予約: ${data.reservations}件(前年${data.previousReservations})`;
    const ai = await this.callComment(this.buildPrompt(
      'ユーザー行動データ', month, dataText,
      curInst ?? '1〜2文で、各指標の数値を列挙してください。',
      anaInst ?? '4〜6文で、強い指標は来店意欲の高さとして評価し、弱い指標はCTA・情報設計の改善提案として伝えてください。',
    ));
    return this.withTemplateFallback(ai, () => this.templateUserActions(data, month));
  }
}
