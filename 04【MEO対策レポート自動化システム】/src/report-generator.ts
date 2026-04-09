import PptxGenJS from 'pptxgenjs';
import * as fs from 'fs';
import * as path from 'path';
import type { ReportInput, SlideData } from './types.js';

// Color constants matching the template
const COLORS = {
  headerBg: '3D8FD4',      // Blue header background
  headerText: 'FFFFFF',    // White header text
  bodyBg: 'F5F5F5',        // Light gray body background
  titleText: '333333',     // Dark title text
  sectionTitle: '1A5276',  // Dark blue section title
  boxBg: 'EBF5FB',         // Light blue commentary box background
  boxBorder: 'AED6F1',     // Commentary box border
  googleBlue: '4285F4',
  googleRed: 'EA4335',
  googleYellow: 'FBBC05',
  googleGreen: '34A853',
};

// Slide dimensions (A4 portrait in inches)
const SLIDE_W = 7.5;
const SLIDE_H = 10.6;

export class ReportGenerator {
  private pptx: PptxGenJS;

  constructor() {
    this.pptx = new PptxGenJS();
    this.pptx.defineLayout({ name: 'A4_PORTRAIT', width: SLIDE_W, height: SLIDE_H });
    this.pptx.layout = 'A4_PORTRAIT';
  }

  private addCoverSlide(storeName: string, month: number, year: number): void {
    const slide = this.pptx.addSlide();
    slide.background = { color: 'F2F2F2' };

    // Google dots decoration
    const dots = [
      { x: 1.2, color: COLORS.googleBlue },
      { x: 1.8, color: COLORS.googleRed },
      { x: 2.4, color: COLORS.googleYellow },
      { x: 3.0, color: COLORS.googleGreen },
    ];
    dots.forEach(dot => {
      slide.addShape(this.pptx.ShapeType.ellipse, {
        x: dot.x, y: 3.2, w: 0.45, h: 0.45,
        fill: { color: dot.color },
        line: { color: dot.color },
      });
    });

    // Main title
    slide.addText(`${month}月度MEO対策 月次レポート`, {
      x: 0.5, y: 4.0, w: SLIDE_W - 1.0, h: 0.7,
      fontSize: 28, bold: true, color: COLORS.titleText,
      align: 'center', fontFace: 'メイリオ',
    });

    // Subtitle
    slide.addText('Googleマップ上での表示・行動分析', {
      x: 0.5, y: 4.75, w: SLIDE_W - 1.0, h: 0.4,
      fontSize: 13, color: '666666',
      align: 'center', fontFace: 'メイリオ',
    });

    // Store name
    slide.addText(`（${storeName}）様`, {
      x: 0.5, y: 5.6, w: SLIDE_W - 1.0, h: 0.6,
      fontSize: 22, bold: true, color: COLORS.titleText,
      align: 'center', fontFace: 'メイリオ',
    });
  }

  private addContentSlide(slideData: SlideData, month: number): void {
    const slide = this.pptx.addSlide();
    slide.background = { color: 'F2F2F2' };

    // Header bar
    slide.addShape(this.pptx.ShapeType.rect, {
      x: 0, y: 0, w: SLIDE_W, h: 0.65,
      fill: { color: COLORS.headerBg },
      line: { color: COLORS.headerBg },
    });

    // Header title
    slide.addText(slideData.title, {
      x: 0.2, y: 0.05, w: SLIDE_W - 0.4, h: 0.55,
      fontSize: 18, bold: true, color: COLORS.headerText,
      align: 'left', fontFace: 'メイリオ',
    });

    // Screenshot area
    const imageAreaY = 0.75;
    const imageAreaH = slideData.imagePath ? 4.8 : 0;

    if (slideData.imagePath && fs.existsSync(slideData.imagePath)) {
      // White background for image
      slide.addShape(this.pptx.ShapeType.rect, {
        x: 0.15, y: imageAreaY, w: SLIDE_W - 0.3, h: imageAreaH,
        fill: { color: 'FFFFFF' },
        line: { color: 'DDDDDD', width: 1 },
      });

      // Insert screenshot
      slide.addImage({
        path: slideData.imagePath,
        x: 0.2, y: imageAreaY + 0.05,
        w: SLIDE_W - 0.4, h: imageAreaH - 0.1,
        sizing: { type: 'contain', w: SLIDE_W - 0.4, h: imageAreaH - 0.1 },
      });
    }

    // Commentary box
    const boxY = imageAreaY + imageAreaH + 0.15;
    const boxH = SLIDE_H - boxY - 0.2;

    slide.addShape(this.pptx.ShapeType.roundRect, {
      x: 0.15, y: boxY, w: SLIDE_W - 0.3, h: boxH,
      fill: { color: 'FFFFFF' },
      line: { color: 'CCCCCC', width: 1 },
      rectRadius: 0.08,
    });

    // Commentary text
    const commentText = [
      { text: '【現状】\n', options: { bold: true, color: '1A5276', fontSize: 11 } },
      { text: slideData.currentStatus + '\n\n', options: { bold: false, color: '333333', fontSize: 11 } },
      { text: '【分析】\n', options: { bold: true, color: '1A5276', fontSize: 11 } },
      { text: slideData.analysis, options: { bold: false, color: '333333', fontSize: 11 } },
    ];

    slide.addText(commentText, {
      x: 0.3, y: boxY + 0.12, w: SLIDE_W - 0.6, h: boxH - 0.25,
      fontFace: 'メイリオ',
      valign: 'top',
      wrap: true,
    });
  }

  async generateReport(
    input: ReportInput,
    slides: {
      keyword?: SlideData;
      views?: SlideData;
      interactions?: SlideData;
      userActions?: SlideData;
    },
    outputPath: string
  ): Promise<void> {
    // Slide 1: Cover
    this.addCoverSlide(input.storeName, input.month, input.year);

    // Slide 2: Keyword ranking
    if (slides.keyword) {
      this.addContentSlide(slides.keyword, input.month);
    }

    // Slide 3: Views
    if (slides.views) {
      this.addContentSlide(slides.views, input.month);
    }

    // Slide 4: Interactions
    if (slides.interactions) {
      this.addContentSlide(slides.interactions, input.month);
    }

    // Slide 5: User actions
    if (slides.userActions) {
      this.addContentSlide(slides.userActions, input.month);
    }

    await this.pptx.writeFile({ fileName: outputPath });
    console.log(`✅ レポートを出力しました: ${outputPath}`);
  }
}
