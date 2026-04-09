export interface ReportInput {
  storeName: string;
  month: number; // 1-12
  year: number;
  screenshots: {
    keyword?: string;       // キーワード順位スクショのパス
    views?: string;         // 閲覧ユーザー数スクショのパス
    interactions?: string;  // インタラクション数スクショのパス
    userActions?: string;   // ユーザー行動データスクショのパス
  };
  apiKey: string;
}

export interface SlideData {
  title: string;
  imagePath?: string;
  currentStatus: string;  // 【現状】
  analysis: string;       // 【分析】
}

export interface ExtractedData {
  keyword?: KeywordData;
  views?: ViewsData;
  interactions?: InteractionData;
  userActions?: UserActionData;
}

export interface KeywordData {
  keywords: { keyword: string; rank: string | number }[];
  summary: string;
}

export interface ViewsData {
  currentMonth: number;
  previousYear: number;
  trend: 'up' | 'down' | 'flat' | 'new';
}

export interface InteractionData {
  currentMonth: number;
  previousYear: number;
  interactionRate: number;
  trend: 'up' | 'down' | 'flat' | 'new';
}

export interface UserActionData {
  calls: number;
  website: number;
  routes: number;
  reservations: number;
  previousCalls: number;
  previousWebsite: number;
  previousRoutes: number;
  previousReservations: number;
}
