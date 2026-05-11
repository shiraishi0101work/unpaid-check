export interface ReportInput {
  storeName: string;
  month: number;
  year: number;
  achievementDays?: number;
  screenshots: {
    keyword?: string;
    views?: string;
    interactions?: string;
    userActions?: string;
  };
  apiKey: string;
}

export interface SlideData {
  title: string;
  imagePath?: string;
  currentStatus: string;
  analysis: string;
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
