import { ReportInput, SlideData } from './types.js';
interface SlidesInput {
    keyword?: SlideData;
    keywords?: SlideData[];
    views?: SlideData;
    interactions?: SlideData;
    userActions?: SlideData | SlideData[];
}
export declare class ReportGenerator {
    private pptx;
    constructor();
    private containImage;
    private addCoverSlide;
    private addContentSlide;
    private addKeywordsSlide;
    private addUserActionsGridSlide;
    generateReport(input: ReportInput, slides: SlidesInput, outputPath: string): Promise<void>;
}
export {};
//# sourceMappingURL=report-generator.d.ts.map