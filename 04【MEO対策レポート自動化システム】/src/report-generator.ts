import PptxGenJS from 'pptxgenjs';
import * as fs from 'fs';
import * as path from 'path';
import { imageSize } from 'image-size';
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

  // 画像のアスペクト比を保ったまま指定エリアに収まるサイズを計算（引き延ばしなし）
  private containImage(
    imagePath: string, maxW: number, maxH: number
  ): { w: number; h: number; offsetX: number; offsetY: number } {
    try {
      const dims = imageSize(imagePath);
      const pw = dims.width ?? 0;
      const ph = dims.height ?? 0;
      if (!pw || !ph) return { w: maxW, h: maxH, offsetX: 0, offsetY: 0 };
      const ratio = pw / ph;
      const containerRatio = maxW / maxH;
      let w: number, h: number;
      if (ratio > containerRatio) {
        w = maxW;
        h = maxW / ratio;
      } else {
        h = maxH;
        w = maxH * ratio;
      }
      return { w, h, offsetX: (maxW - w) / 2, offsetY: (maxH - h) / 2 };
    } catch {
      return { w: maxW, h: maxH, offsetX: 0, offsetY: 0 };
    }
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
    slide.addText('Googleマップ上での表示・行動分析ご報告', {
      x: 0.5, y: 4.75, w: SLIDE_W - 1.0, h: 0.4,
      fontSize: 13, color: '666666',
      align: 'center', fontFace: 'メイリオ',
    });

    // Store name
    slide.addText(`${storeName} 様`, {
      x: 0.5, y: 5.6, w: SLIDE_W - 1.0, h: 0.6,
      fontSize: 22, bold: true, color: COLORS.titleText,
      align: 'center', fontFace: 'メイリオ',
    });
  }

  private addContentSlide(slideData: SlideData, month: number, showCommentary = true): void {
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

    // Screenshot area（画像あり・なし両方で枠を表示）
    const imageAreaY = 0.75;
    const imageAreaH = showCommentary ? 4.8 : SLIDE_H - imageAreaY - 0.2;

    // 画像枠（常に表示）
    slide.addShape(this.pptx.ShapeType.rect, {
      x: 0.15, y: imageAreaY, w: SLIDE_W - 0.3, h: imageAreaH,
      fill: { color: 'FFFFFF' },
      line: { color: 'DDDDDD', width: 1 },
    });

    // 画像を挿入（ある場合のみ・元サイズ維持で引き延ばさない）
    if (slideData.imagePath && fs.existsSync(slideData.imagePath)) {
      slide.addImage({
        path: slideData.imagePath,
        x: 0.2, y: imageAreaY + 0.05,
        w: SLIDE_W - 0.4, h: imageAreaH - 0.1,
        sizing: { type: 'contain', w: SLIDE_W - 0.4, h: imageAreaH - 0.1 },
      });
    }

    if (!showCommentary) return;

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

  // 複数キーワード画像を1スライドに横並び配置
  private addKeywordsSlide(keywordSlides: SlideData[], month: number): void {
    const slide = this.pptx.addSlide();
    slide.background = { color: 'F2F2F2' };

    // Header
    slide.addShape(this.pptx.ShapeType.rect, {
      x: 0, y: 0, w: SLIDE_W, h: 0.65,
      fill: { color: COLORS.headerBg },
      line: { color: COLORS.headerBg },
    });
    slide.addText(keywordSlides[0]!.title, {
      x: 0.2, y: 0.05, w: SLIDE_W - 0.4, h: 0.55,
      fontSize: 18, bold: true, color: COLORS.headerText,
      align: 'left', fontFace: 'メイリオ',
    });

    const imageAreaY = 0.75;
    const n = keywordSlides.length;
    const gap = 0.05;
    const totalW = SLIDE_W - 0.3;
    const perW = (totalW - gap * (n - 1)) / n;

    // 画像枠のみ（手動差し込み用プレースホルダー）
    const placeholderH = SLIDE_H - imageAreaY - 5.4; // コメントボックスの上まで
    for (let i = 0; i < n; i++) {
      const x = 0.15 + i * (perW + gap);
      // 枠線付き白背景
      slide.addShape(this.pptx.ShapeType.rect, {
        x, y: imageAreaY, w: perW, h: placeholderH,
        fill: { color: 'FFFFFF' },
        line: { color: 'AAAAAA', width: 1 },
      });
      // ラベル
      slide.addText(`スクリーンショット ${i + 1}`, {
        x, y: imageAreaY + placeholderH / 2 - 0.2, w: perW, h: 0.4,
        fontSize: 10, color: 'AAAAAA',
        align: 'center', fontFace: 'メイリオ',
      });
    }

    // コメントボックス（スライド下部固定。画像と重なってもOK）
    const first = keywordSlides[0]!;
    if (first.currentStatus || first.analysis) {
      const boxY = SLIDE_H - 5.2;
      const boxH = 5.0;
      slide.addShape(this.pptx.ShapeType.roundRect, {
        x: 0.15, y: boxY, w: SLIDE_W - 0.3, h: boxH,
        fill: { color: 'FFFFFF' },
        line: { color: 'CCCCCC', width: 1 },
        rectRadius: 0.08,
      });
      const commentText = [
        { text: '【現状】\n', options: { bold: true, color: '1A5276', fontSize: 11 } },
        { text: first.currentStatus + '\n\n', options: { bold: false, color: '333333', fontSize: 11 } },
        { text: '【分析】\n', options: { bold: true, color: '1A5276', fontSize: 11 } },
        { text: first.analysis, options: { bold: false, color: '333333', fontSize: 11 } },
      ];
      slide.addText(commentText, {
        x: 0.3, y: boxY + 0.12, w: SLIDE_W - 0.6, h: boxH - 0.25,
        fontFace: 'メイリオ', valign: 'top', wrap: true,
      });
    }
  }

  async generateReport(
    input: ReportInput,
    slides: {
      keywords?: SlideData[];
      keyword?: SlideData;
      views?: SlideData;
      interactions?: SlideData;
      userActions?: SlideData;
    },
    outputPath: string
  ): Promise<void> {
    // Slide 1: Cover
    this.addCoverSlide(input.storeName, input.month, input.year);

    // Keyword slides（複数枚→1スライドに横並び、1枚→通常スライド）
    const keywordSlides = slides.keywords ?? (slides.keyword ? [slides.keyword] : []);
    if (keywordSlides.length > 1) {
      this.addKeywordsSlide(keywordSlides, input.month);
    } else if (keywordSlides.length === 1) {
      this.addContentSlide(keywordSlides[0]!, input.month, true);
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
