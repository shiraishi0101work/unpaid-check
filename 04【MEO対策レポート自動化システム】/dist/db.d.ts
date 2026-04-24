declare const REPORTS_DIR: string;
export interface Store {
    id: string;
    name: string;
    createdAt: string;
}
export interface Report {
    id: string;
    storeId: string;
    storeName: string;
    month: number;
    year: number;
    fileName: string;
    filePath: string;
    generatedAt: string;
}
export interface PromptSet {
    keyword_current: string;
    keyword_analysis: string;
    views_current: string;
    views_analysis: string;
    interactions_current: string;
    interactions_analysis: string;
    userActions_current: string;
    userActions_analysis: string;
}
export declare const DEFAULT_PROMPTS: PromptSet;
export declare function getStores(): Store[];
export declare function addStore(name: string): Store;
export declare function getStore(id: string): Store | undefined;
export declare function deleteStore(id: string): void;
export declare function getReports(storeId?: string): Report[];
export declare function saveReport(data: Omit<Report, 'id' | 'filePath' | 'fileName'>, tmpPath: string): Report;
export declare function getReport(id: string): Report | undefined;
export declare function deleteReport(id: string): void;
export declare function getDefaultPrompts(): PromptSet;
export declare function setDefaultPrompts(prompts: Partial<PromptSet>): void;
export declare function clearDefaultPrompts(): void;
export declare function getStorePrompts(storeId: string): Partial<PromptSet>;
export declare function setStorePrompts(storeId: string, prompts: Partial<PromptSet>): void;
export declare function clearAllStorePromptsForKeys(keys: (keyof PromptSet)[]): void;
export { REPORTS_DIR };
