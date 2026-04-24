import type { KeywordData, ViewsData, InteractionData, UserActionData } from './types.js';
export type CommentProvider = 'claude' | 'openai' | 'gemini';
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
    generateKeywordComment(data: KeywordData, month: number, curInst?: string, anaInst?: string): Promise<{
        current: string;
        analysis: string;
    }>;
    generateViewsComment(data: ViewsData, month: number, curInst?: string, anaInst?: string): Promise<{
        current: string;
        analysis: string;
    }>;
    generateInteractionComment(data: InteractionData, month: number, curInst?: string, anaInst?: string): Promise<{
        current: string;
        analysis: string;
    }>;
    generateUserActionComment(data: UserActionData, month: number, curInst?: string, anaInst?: string): Promise<{
        current: string;
        analysis: string;
    }>;
    getTemplateKeyword(data: KeywordData, month: number): {
        current: string;
        analysis: string;
    };
    getTemplateViews(data: ViewsData, month: number): {
        current: string;
        analysis: string;
    };
    getTemplateInteractions(data: InteractionData, month: number): {
        current: string;
        analysis: string;
    };
    getTemplateUserActions(data: UserActionData, month: number): {
        current: string;
        analysis: string;
    };
}
