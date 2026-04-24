import type { ReportInput, SlideData } from './types.js';
export declare class ReportGenerator {
    private pptx;
    constructor();
    private containImage;
    private addCoverSlide;
    private addContentSlide;
    private addKeywordsSlide;
    generateReport(input: ReportInput, slides: {
        keywords?: SlideData[];
        keyword?: SlideData;
        views?: SlideData;
        interactions?: SlideData;
        userActions?: SlideData;
    }, outputPath: string): Promise<void>;
}
