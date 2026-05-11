"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.ReportGenerator = void 0;
const pptxgenjs_1 = __importDefault(require("pptxgenjs"));
const fs = __importStar(require("fs"));
const image_size_1 = require("image-size");
// Color constants matching the template
const COLORS = {
    headerBg: '3D8FD4', // Blue header background
    headerText: 'FFFFFF', // White header text
    bodyBg: 'F5F5F5', // Light gray body background
    titleText: '333333', // Dark title text
    sectionTitle: '1A5276', // Dark blue section title
    boxBg: 'EBF5FB', // Light blue commentary box background
    boxBorder: 'AED6F1', // Commentary box border
    googleBlue: '4285F4',
    googleRed: 'EA4335',
    googleYellow: 'FBBC05',
    googleGreen: '34A853',
};
// Slide dimensions (A4 portrait in inches)
const SLIDE_W = 7.5;
const SLIDE_H = 10.6;
class ReportGenerator {
    constructor() {
        this.pptx = new pptxgenjs_1.default();
        this.pptx.defineLayout({ name: 'A4_PORTRAIT', width: SLIDE_W, height: SLIDE_H });
        this.pptx.layout = 'A4_PORTRAIT';
    }
    // 画像のアスペクト比を保ったまま指定エリアに収まるサイズを計算（引き延ばしなし）
    containImage(imagePath, maxW, maxH) {
        try {
            const dims = (0, image_size_1.imageSize)(imagePath);
            const pw = dims.width ?? 0;
            const ph = dims.height ?? 0;
            if (!pw || !ph)
                return { w: maxW, h: maxH, offsetX: 0, offsetY: 0 };
            const ratio = pw / ph;
            const containerRatio = maxW / maxH;
            let w, h;
            if (ratio > containerRatio) {
                w = maxW;
                h = maxW / ratio;
            }
            else {
                h = maxH;
                w = maxH * ratio;
            }
            return { w, h, offsetX: (maxW - w) / 2, offsetY: (maxH - h) / 2 };
        }
        catch {
            return { w: maxW, h: maxH, offsetX: 0, offsetY: 0 };
        }
    }
    addCoverSlide(storeName, month, year) {
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
    addContentSlide(slideData, month, showCommentary = true) {
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
        // 画像を挿入（ある場合のみ・アスペクト比を保ってエリアに収める）
        if (slideData.imagePath && fs.existsSync(slideData.imagePath)) {
            const maxW = SLIDE_W - 0.4;
            const maxH = imageAreaH - 0.1;
            const { w, h, offsetX, offsetY } = this.containImage(slideData.imagePath, maxW, maxH);
            slide.addImage({
                path: slideData.imagePath,
                x: 0.2 + offsetX,
                y: imageAreaY + 0.05 + offsetY,
                w,
                h,
            });
        }
        if (!showCommentary)
            return;
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
    addKeywordsSlide(keywordSlides, month) {
        const slide = this.pptx.addSlide();
        slide.background = { color: 'F2F2F2' };
        // Header
        slide.addShape(this.pptx.ShapeType.rect, {
            x: 0, y: 0, w: SLIDE_W, h: 0.65,
            fill: { color: COLORS.headerBg },
            line: { color: COLORS.headerBg },
        });
        slide.addText(keywordSlides[0].title, {
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
        const first = keywordSlides[0];
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
    // 複数ユーザー行動画像を2×2グリッドで配置
    addUserActionsGridSlide(userActSlides) {
        const slide = this.pptx.addSlide();
        slide.background = { color: 'F2F2F2' };
        // Header
        slide.addShape(this.pptx.ShapeType.rect, {
            x: 0, y: 0, w: SLIDE_W, h: 0.65,
            fill: { color: COLORS.headerBg },
            line: { color: COLORS.headerBg },
        });
        slide.addText(userActSlides[0].title, {
            x: 0.2, y: 0.05, w: SLIDE_W - 0.4, h: 0.55,
            fontSize: 18, bold: true, color: COLORS.headerText,
            align: 'left', fontFace: 'メイリオ',
        });
        const imageAreaY = 0.75;
        const gap = 0.08;
        const totalW = SLIDE_W - 0.3;
        const boxY = SLIDE_H - 5.2;
        const imageAreaH = boxY - imageAreaY - 0.1;
        const cols = 2;
        const rows = 2;
        const cellW = (totalW - gap * (cols - 1)) / cols;
        const cellH = (imageAreaH - gap * (rows - 1)) / rows;
        for (let i = 0; i < Math.min(userActSlides.length, 4); i++) {
            const col = i % cols;
            const row = Math.floor(i / cols);
            const x = 0.15 + col * (cellW + gap);
            const y = imageAreaY + row * (cellH + gap);
            slide.addShape(this.pptx.ShapeType.rect, {
                x, y, w: cellW, h: cellH,
                fill: { color: 'FFFFFF' },
                line: { color: 'AAAAAA', width: 1 },
            });
            const s = userActSlides[i];
            if (s.imagePath && fs.existsSync(s.imagePath)) {
                const { w, h, offsetX, offsetY } = this.containImage(s.imagePath, cellW - 0.06, cellH - 0.06);
                slide.addImage({
                    path: s.imagePath,
                    x: x + 0.03 + offsetX,
                    y: y + 0.03 + offsetY,
                    w, h,
                });
            }
            else {
                slide.addText(`スクリーンショット ${i + 1}`, {
                    x, y: y + cellH / 2 - 0.2, w: cellW, h: 0.4,
                    fontSize: 10, color: 'AAAAAA',
                    align: 'center', fontFace: 'メイリオ',
                });
            }
        }
        const first = userActSlides[0];
        if (first.currentStatus || first.analysis) {
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
    async generateReport(input, slides, outputPath) {
        // Slide 1: Cover
        this.addCoverSlide(input.storeName, input.month, input.year);
        // Keyword slides（複数枚→1スライドに横並び、1枚→通常スライド）
        const keywordSlides = slides.keywords ?? (slides.keyword ? [slides.keyword] : []);
        if (keywordSlides.length > 1) {
            this.addKeywordsSlide(keywordSlides, input.month);
        }
        else if (keywordSlides.length === 1) {
            this.addContentSlide(keywordSlides[0], input.month, true);
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
exports.ReportGenerator = ReportGenerator;
//# sourceMappingURL=report-generator.js.map