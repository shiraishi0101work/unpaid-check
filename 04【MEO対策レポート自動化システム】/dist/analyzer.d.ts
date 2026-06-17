import { KeywordData, ViewsData, InteractionData, UserActionData } from './types.js';
type CommentProvider = 'claude' | 'gemini' | 'openai';
interface CommentResult {
    current: string;
    analysis: string;
}
export declare class MeoAnalyzer {
    private client;
    private commentProvider;
    private commentApiKey;
    commentFallback: boolean;
    templateFallback: boolean;
    lastError: string | null;
    constructor(anthropicKey: string, commentProvider?: CommentProvider, commentApiKey?: string);
    private loadImage;
    private extractWithGemini;
    private extractWithClaude;
    private extractImage;
    extractKeywordData(imagePath: string): Promise<KeywordData>;
    extractViewsData(imagePath: string): Promise<ViewsData>;
    extractInteractionData(imagePath: string): Promise<InteractionData>;
    extractUserActionData(imagePath: string): Promise<UserActionData>;
    private callClaudeComment;
    private callGeminiText;
    private recordError;
    private callComment;
    private buildPrompt;
    private templateKeyword;
    private templateViews;
    private templateInteractions;
    private templateUserActions;
    private withTemplateFallback;
    generateKeywordComment(data: KeywordData, month: number, curInst?: string, anaInst?: string): Promise<CommentResult>;
    generateViewsComment(data: ViewsData, month: number, curInst?: string, anaInst?: string): Promise<CommentResult>;
    generateInteractionComment(data: InteractionData, month: number, curInst?: string, anaInst?: string): Promise<CommentResult>;
    generateUserActionComment(data: UserActionData, month: number, curInst?: string, anaInst?: string): Promise<CommentResult>;
    getTemplateKeyword(data: KeywordData, month: number): CommentResult;
    getTemplateViews(data: ViewsData, month: number): CommentResult;
    getTemplateInteractions(data: InteractionData, month: number): CommentResult;
    getTemplateUserActions(data: UserActionData, month: number): CommentResult;
}
export {};
//# sourceMappingURL=analyzer.d.ts.map