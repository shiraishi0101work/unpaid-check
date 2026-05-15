"""
デザイン文字生成システム - ステッカースタイル文字画像ジェネレーター
スタイル: 太い黒アウトライン + 白い外枠 + カラー塗り + グロスハイライト + ドロップシャドウ
"""

import os
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter


# ============================================================
# フォント設定
# ============================================================
# 可変フォント（weight=900 で最太にする）を最優先
VARIABLE_FONT = r"C:\Windows\Fonts\NotoSansJP-VF.ttf"

FALLBACK_FONTS = [
    r"C:\Windows\Fonts\BIZ-UDGothicB.ttc",
    r"C:\Windows\Fonts\YuGothB.ttc",
    r"C:\Windows\Fonts\meiryob.ttc",
    r"C:\Windows\Fonts\msgothic.ttc",
]


def load_font(font_size: int, font_path: str = None) -> ImageFont.FreeTypeFont:
    """フォントをロードする。可変フォントは weight=900 に設定。"""
    path = font_path

    # パス未指定 → 自動選択
    if path is None:
        if os.path.exists(VARIABLE_FONT):
            path = VARIABLE_FONT
        else:
            path = next((p for p in FALLBACK_FONTS if os.path.exists(p)), None)

    if path is None:
        raise FileNotFoundError("利用可能な日本語フォントが見つかりません")

    font = ImageFont.truetype(path, font_size)

    # 可変フォントなら weight=900（Black）に設定
    if path == VARIABLE_FONT:
        try:
            font.set_variation_by_axes([900])
        except Exception:
            pass  # 非対応バージョンは無視

    return font


def hex_to_rgba(hex_color: str, alpha: int = 255) -> tuple:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return (r, g, b, alpha)


def draw_4point_star(draw: ImageDraw.Draw, cx: float, cy: float,
                     outer_r: float, inner_r: float, color: tuple):
    """4角星（キラキラ）を描画"""
    points = []
    for i in range(8):
        angle = math.pi * i / 4 - math.pi / 2
        r = outer_r if i % 2 == 0 else inner_r
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(points, fill=color)


def generate_sticker(
    text: str,
    color_hex: str = "#FF88BB",
    font_size: int = 200,
    font_path: str = None,
) -> Image.Image:
    """
    ステッカースタイルの文字画像を生成する

    Args:
        text:       生成するテキスト
        color_hex:  塗りの色（例: "#FF88BB"）
        font_size:  フォントサイズ（デフォルト 200px）
        font_path:  フォントファイルのパス（None の場合は自動検出）

    Returns:
        RGBA モードの PIL Image（背景透過）
    """
    if not text or not text.strip():
        raise ValueError("テキストを入力してください")

    if font_path is None:
        font_path = find_font()

    fill_rgba   = hex_to_rgba(color_hex)
    shadow_rgba = (140, 150, 200, 170)

    # ストローク幅（フォントサイズに比例）
    outer_stroke = max(10, font_size // 9)    # 白い外枠
    inner_stroke = max(6,  font_size // 14)   # 黒いアウトライン
    combined     = outer_stroke + inner_stroke

    shadow_dx = max(6, font_size // 22)
    shadow_dy = max(7, font_size // 18)
    padding   = combined * 3 + shadow_dx + shadow_dy

    # ---- フォントロード & テキスト計測 ----
    font = ImageFont.truetype(font_path, font_size)

    tmp_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = tmp_draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    offset_x = -bbox[0]
    offset_y = -bbox[1]

    canvas_w = text_w + padding * 2 + shadow_dx
    canvas_h = text_h + padding * 2 + shadow_dy

    tx = padding + offset_x   # テキスト描画 X
    ty = padding + offset_y   # テキスト描画 Y

    # ======================================================
    # 1. ドロップシャドウ
    # ======================================================
    shadow_img  = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_img)
    shadow_draw.text(
        (tx + shadow_dx, ty + shadow_dy), text, font=font,
        fill=shadow_rgba,
        stroke_width=combined,
        stroke_fill=shadow_rgba,
    )
    blur_r = max(4, font_size // 30)
    shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(blur_r))

    # ======================================================
    # 2. 白い外枠レイヤー
    # ======================================================
    white_img  = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    white_draw = ImageDraw.Draw(white_img)
    white_draw.text(
        (tx, ty), text, font=font,
        fill=(255, 255, 255, 255),
        stroke_width=combined,
        stroke_fill=(255, 255, 255, 255),
    )

    # ======================================================
    # 3. 黒いアウトラインレイヤー
    # ======================================================
    black_img  = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    black_draw = ImageDraw.Draw(black_img)
    black_draw.text(
        (tx, ty), text, font=font,
        fill=(25, 25, 25, 255),
        stroke_width=inner_stroke,
        stroke_fill=(25, 25, 25, 255),
    )

    # ======================================================
    # 4. カラー塗りレイヤー
    # ======================================================
    fill_img  = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    fill_draw = ImageDraw.Draw(fill_img)
    fill_draw.text((tx, ty), text, font=font, fill=fill_rgba)

    # ======================================================
    # 5. グロスハイライト（文字の輪郭内のみ）
    # ======================================================
    # テキストマスク（ストロークなし、文字形状のみ）
    text_mask = Image.new("L", (canvas_w, canvas_h), 0)
    mask_draw = ImageDraw.Draw(text_mask)
    mask_draw.text((tx, ty), text, font=font, fill=255)

    gloss_img  = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    gloss_draw = ImageDraw.Draw(gloss_img)

    # 上部 38% を半透明ホワイトで塗る
    gloss_top    = ty
    gloss_bottom = ty + int(text_h * 0.38)
    gloss_draw.rectangle(
        [tx, gloss_top, tx + text_w, gloss_bottom],
        fill=(255, 255, 255, 105),
    )

    # 4角星（キラキラ）
    star_cx = tx + int(text_h * 0.13)
    star_cy = ty + int(text_h * 0.13)
    star_r  = max(8, int(text_h * 0.14))
    draw_4point_star(gloss_draw, star_cx, star_cy, star_r, star_r * 0.33,
                     (255, 255, 255, 235))

    # 小さいドット ×2
    dot_r = max(3, int(star_r * 0.28))
    gloss_draw.ellipse([
        star_cx + star_r * 1.05 - dot_r, star_cy + star_r * 0.5 - dot_r,
        star_cx + star_r * 1.05 + dot_r, star_cy + star_r * 0.5 + dot_r,
    ], fill=(255, 255, 255, 200))
    gloss_draw.ellipse([
        star_cx + star_r * 1.6 - dot_r * 0.7, star_cy - dot_r * 0.7,
        star_cx + star_r * 1.6 + dot_r * 0.7, star_cy + dot_r * 0.7,
    ], fill=(255, 255, 255, 170))

    # テキストマスクでクリッピング
    transparent = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    gloss_img   = Image.composite(gloss_img, transparent, text_mask)

    # ======================================================
    # 6. 合成（下から: シャドウ → 白枠 → 黒枠 → 塗り → グロス）
    # ======================================================
    result = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    result = Image.alpha_composite(result, shadow_img)
    result = Image.alpha_composite(result, white_img)
    result = Image.alpha_composite(result, black_img)
    result = Image.alpha_composite(result, fill_img)
    result = Image.alpha_composite(result, gloss_img)

    # 不要な余白をトリミング
    bbox = result.getbbox()
    if bbox:
        margin = max(4, combined // 2)
        x0 = max(0, bbox[0] - margin)
        y0 = max(0, bbox[1] - margin)
        x1 = min(canvas_w, bbox[2] + margin)
        y1 = min(canvas_h, bbox[3] + margin)
        result = result.crop((x0, y0, x1, y1))

    return result
