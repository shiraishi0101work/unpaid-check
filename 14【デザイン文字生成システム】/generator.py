"""
デザイン文字生成システム - ステッカースタイル文字画像ジェネレーター
"""

import os
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

_HERE = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# フォントカタログ
# ============================================================
FONT_CATALOG = [
    {
        "id":       "lanovepop",
        "label":    "ラノベPOP V2（かわいい太ポップ）",
        "path":     os.path.join(_HERE, "LightNovelPOPv2.otf"),
        "weight":   None,
        "variable": False,
    },
    {
        "id":       "tanuki",
        "label":    "たぬき油性マジック（手書きポップ）",
        "path":     os.path.join(_HERE, "TanukiMagic.ttf"),
        "weight":   None,
        "variable": False,
    },
    {
        "id":       "noto_black",
        "label":    "Noto Sans JP（極太ゴシック・ウェイト調整可）",
        "path":     r"C:\Windows\Fonts\NotoSansJP-VF.ttf",
        "weight":   900,
        "variable": True,
    },
    {
        "id":       "biz_ud",
        "label":    "BIZ UD Gothic Bold（太めゴシック）",
        "path":     r"C:\Windows\Fonts\BIZ-UDGothicB.ttc",
        "weight":   None,
        "variable": False,
    },
    {
        "id":       "yugoth",
        "label":    "Yu Gothic Bold（游ゴシック太字）",
        "path":     r"C:\Windows\Fonts\YuGothB.ttc",
        "weight":   None,
        "variable": False,
    },
    {
        "id":       "meiryo",
        "label":    "Meiryo Bold（メイリオ太字）",
        "path":     r"C:\Windows\Fonts\meiryob.ttc",
        "weight":   None,
        "variable": False,
    },
]
FONT_CATALOG = [f for f in FONT_CATALOG if os.path.exists(f["path"])]


def get_available_fonts():
    return [{"id": f["id"], "label": f["label"], "variable": f["variable"]}
            for f in FONT_CATALOG]


def _resolve_font_entry(font_id):
    for f in FONT_CATALOG:
        if f["id"] == font_id:
            return f
    return FONT_CATALOG[0]


def load_font(font_size, font_id=None, font_weight=None):
    entry  = _resolve_font_entry(font_id) if font_id else FONT_CATALOG[0]
    font   = ImageFont.truetype(entry["path"], font_size)
    weight = font_weight if font_weight is not None else entry["weight"]
    if weight is not None:
        try:
            font.set_variation_by_axes([int(weight)])
        except Exception:
            pass
    return font


# ============================================================
# カラーユーティリティ
# ============================================================
def hex_to_rgba(hex_color, alpha=255):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i+2], 16) for i in (0, 2, 4))
    return (r, g, b, alpha)


def lighten_rgba(rgba, factor=0.45):
    r, g, b, a = rgba
    return (int(r+(255-r)*factor), int(g+(255-g)*factor), int(b+(255-b)*factor), a)


def _lerp_color(c1, c2, t):
    return tuple(max(0, min(255, int(c1[i] + (c2[i]-c1[i])*t))) for i in range(4))


# ============================================================
# テキスト計測 & レンダリング（字間対応）
# ============================================================
_TMP_DRAW = ImageDraw.Draw(Image.new("RGBA", (1, 1)))

def _measure(text, font, letter_spacing):
    if not text:
        return 0, 0, 0, 0
    full_bb  = _TMP_DRAW.textbbox((0, 0), text, font=font)
    text_h   = full_bb[3] - full_bb[1]
    offset_y = -full_bb[1]
    if letter_spacing == 0:
        return full_bb[2] - full_bb[0], text_h, -full_bb[0], offset_y
    total_w  = 0
    offset_x = 0
    for i, ch in enumerate(text):
        cb = _TMP_DRAW.textbbox((0, 0), ch, font=font)
        if i == 0:
            offset_x = -cb[0]
        total_w += cb[2] - cb[0]
        if i < len(text) - 1:
            total_w += letter_spacing
    return total_w, text_h, offset_x, offset_y


def _render_text(canvas_size, text, font, tx, ty,
                 fill_color, stroke_width=0, stroke_fill=None,
                 letter_spacing=0):
    img  = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    sf   = stroke_fill or fill_color
    if letter_spacing == 0:
        draw.text((tx, ty), text, font=font, fill=fill_color,
                  stroke_width=stroke_width, stroke_fill=sf)
        return img
    x = tx
    for i, ch in enumerate(text):
        draw.text((x, ty), ch, font=font, fill=fill_color,
                  stroke_width=stroke_width, stroke_fill=sf)
        cb = _TMP_DRAW.textbbox((0, 0), ch, font=font)
        x += (cb[2] - cb[0]) + letter_spacing
    return img


# ============================================================
# グラデーション生成
# ============================================================
def _create_gradient(w, h, c1, c2, mode):
    img  = Image.new("RGBA", (w, h))
    draw = ImageDraw.Draw(img)

    if mode == "top_bottom":
        for y in range(h):
            draw.line([(0, y), (w-1, y)], fill=_lerp_color(c1, c2, y/max(1, h-1)))

    elif mode == "left_right":
        for x in range(w):
            draw.line([(x, 0), (x, h-1)], fill=_lerp_color(c1, c2, x/max(1, w-1)))

    elif mode == "diagonal":
        # 縦グラデ画像を -45° 回転して切り抜き
        diag = int(math.sqrt(w*w + h*h)) + 4
        tmp  = Image.new("RGBA", (diag, diag))
        td   = ImageDraw.Draw(tmp)
        for y in range(diag):
            td.line([(0, y), (diag-1, y)], fill=_lerp_color(c1, c2, y/max(1, diag-1)))
        tmp  = tmp.rotate(-45, expand=False, resample=Image.BICUBIC)
        cx, cy = tmp.size[0]//2, tmp.size[1]//2
        img  = tmp.crop((cx-w//2, cy-h//2, cx-w//2+w, cy-h//2+h))
        if img.size != (w, h):
            img = img.resize((w, h), Image.LANCZOS)

    return img


# ============================================================
# 4角星（グロス用）
# ============================================================
def _draw_star(draw, cx, cy, r_outer, r_inner, color):
    pts = []
    for i in range(8):
        ang = math.pi * i / 4 - math.pi / 2
        r   = r_outer if i % 2 == 0 else r_inner
        pts.append((cx + r*math.cos(ang), cy + r*math.sin(ang)))
    draw.polygon(pts, fill=color)


# ============================================================
# 後処理：横幅スケール・斜体
# ============================================================
def _apply_x_scale(img, pct):
    if pct == 100:
        return img
    w, h  = img.size
    new_w = max(1, int(w * pct / 100))
    return img.resize((new_w, h), Image.LANCZOS)


def _apply_slant(img, deg):
    if deg == 0:
        return img
    shear  = math.tan(math.radians(deg))
    w, h   = img.size
    extra  = abs(int(h * shear))
    new_w  = w + extra
    if deg > 0:
        matrix = (1, shear, -extra, 0, 1, 0)
    else:
        matrix = (1, shear, 0, 0, 1, 0)
    return img.transform((new_w, h), Image.AFFINE, matrix, Image.BICUBIC)


# ============================================================
# メイン生成関数
# ============================================================
def generate_sticker(
    text,
    # 塗り
    color_hex        = "#FF88BB",
    font_size        = 200,
    font_id          = None,
    # 外縁
    border_mode      = "double",   # "none" | "single" | "double"
    border_color1    = "#1a1a1a",
    border_color2    = "#ffffff",
    border_size      = 5,          # 1-10
    # 文字スタイル
    letter_spacing   = 0,          # px（-20〜150）
    x_scale          = 100,        # 横幅 %（50〜200）
    slant            = 0,          # 斜体角度（-30〜30）
    fake_bold        = 0,          # 疑似太字（0〜8）
    font_weight      = None,       # ウェイト（可変フォントのみ有効、100〜900）
    # エフェクト
    gloss            = True,       # 艶あり/なし
    gloss_intensity  = 60,         # 艶の強さ（0〜100）
    gradient_mode     = "none",     # "none"|"top_bottom"|"left_right"|"diagonal"
    gradient_color2   = None,       # グラデ第2色（None=塗り色を明るくして自動生成）
    gradient_strength = 100,        # グラデーション強度 0-100
):
    if not text or not text.strip():
        raise ValueError("テキストを入力してください")

    border_size     = max(1, min(10, int(border_size)))
    size_factor     = border_size / 5.0
    gloss_intensity = max(0, min(100, int(gloss_intensity)))
    fake_bold       = max(0, min(8,  int(fake_bold)))
    x_scale         = max(50, min(200, int(x_scale)))
    slant           = max(-30, min(30, int(slant)))

    fill_rgba    = hex_to_rgba(color_hex)
    color1_rgba  = hex_to_rgba(border_color1)
    color2_rgba  = hex_to_rgba(border_color2)

    # ストローク幅
    inner_stroke = max(2, int((font_size / 14) * size_factor))
    outer_stroke = max(3, int((font_size / 9)  * size_factor))
    combined     = inner_stroke + outer_stroke

    if border_mode == "none":
        eff_combined = 0
    elif border_mode == "single":
        eff_combined = inner_stroke
    else:
        eff_combined = combined

    padding  = eff_combined * 3 + 10

    # ---- フォントロード & 計測 ----
    font = load_font(font_size, font_id, font_weight)
    text_w, text_h, offset_x, offset_y = _measure(text, font, letter_spacing)

    canvas_w = text_w + padding * 2
    canvas_h = text_h + padding * 2
    tx = padding + offset_x
    ty = padding + offset_y

    result = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

    # ---- 外側ふち（double） ----
    if border_mode == "double":
        layer = _render_text(
            (canvas_w, canvas_h), text, font, tx, ty,
            color2_rgba, combined, color2_rgba, letter_spacing
        )
        result = Image.alpha_composite(result, layer)

    # ---- 内側ふち（single / double） ----
    if border_mode in ("single", "double"):
        layer = _render_text(
            (canvas_w, canvas_h), text, font, tx, ty,
            color1_rgba, inner_stroke, color1_rgba, letter_spacing
        )
        result = Image.alpha_composite(result, layer)

    # ---- 塗り（グラデ or フラット） ----
    # テキストマスク
    text_mask = Image.new("L", (canvas_w, canvas_h), 0)
    _render_text((canvas_w, canvas_h), text, font, tx, ty,
                 255, 0, None, letter_spacing
                 )
    # マスク専用レンダリング
    mask_layer = Image.new("L", (canvas_w, canvas_h), 0)
    mask_draw  = ImageDraw.Draw(mask_layer)
    if letter_spacing == 0:
        mask_draw.text((tx, ty), text, font=font, fill=255)
    else:
        x = tx
        for i, ch in enumerate(text):
            mask_draw.text((x, ty), ch, font=font, fill=255)
            cb = _TMP_DRAW.textbbox((0, 0), ch, font=font)
            x += (cb[2]-cb[0]) + letter_spacing
    text_mask = mask_layer

    if gradient_mode != "none":
        gc2_base = hex_to_rgba(gradient_color2) if gradient_color2 else lighten_rgba(fill_rgba, 0.45)
        # 強度で第2色を fill_rgba との間で補間（0%=単色、100%=フル）
        t = max(0, min(100, int(gradient_strength))) / 100.0
        gc2 = tuple(int(fill_rgba[i] + (gc2_base[i] - fill_rgba[i]) * t) for i in range(4))
        grad_img = _create_gradient(canvas_w, canvas_h, fill_rgba, gc2, gradient_mode)
        # fake_bold ストロークを考慮したマスク
        if fake_bold > 0:
            fb_mask = Image.new("L", (canvas_w, canvas_h), 0)
            fb_draw = ImageDraw.Draw(fb_mask)
            if letter_spacing == 0:
                fb_draw.text((tx, ty), text, font=font, fill=255,
                             stroke_width=fake_bold, stroke_fill=255)
            else:
                x = tx
                for i, ch in enumerate(text):
                    fb_draw.text((x, ty), ch, font=font, fill=255,
                                 stroke_width=fake_bold, stroke_fill=255)
                    cb = _TMP_DRAW.textbbox((0, 0), ch, font=font)
                    x += (cb[2]-cb[0]) + letter_spacing
            fill_mask = fb_mask
        else:
            fill_mask = text_mask
        fill_layer = Image.composite(grad_img, Image.new("RGBA", (canvas_w, canvas_h), (0,0,0,0)), fill_mask)
    else:
        fill_layer = _render_text(
            (canvas_w, canvas_h), text, font, tx, ty,
            fill_rgba, fake_bold, fill_rgba, letter_spacing
        )

    result = Image.alpha_composite(result, fill_layer)

    # ---- グロス ----
    if gloss and gloss_intensity > 0:
        alpha   = int(gloss_intensity * 1.5)   # 0-150 範囲に拡張
        gl_img  = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        gl_draw = ImageDraw.Draw(gl_img)

        # 上部ハイライト帯（文字の上40%に白いグロー）
        top_h = ty + int(text_h * 0.42)
        gl_draw.rectangle([tx, ty, tx + text_w, top_h],
                           fill=(255, 255, 255, min(255, int(alpha * 0.75))))

        # ぼかしてなめらかなグロー（強めにぼかしてトゲ完全除去）
        blur_r = max(6, font_size // 20)
        gl_img = gl_img.filter(ImageFilter.GaussianBlur(radius=blur_r))
        transp = Image.new("RGBA", (canvas_w, canvas_h), (0,0,0,0))
        gl_img = Image.composite(gl_img, transp, text_mask)
        result = Image.alpha_composite(result, gl_img)

    # ---- 余白トリミング ----
    bbox = result.getbbox()
    if bbox:
        margin = max(4, eff_combined // 2 + 2)
        x0 = max(0, bbox[0]-margin)
        y0 = max(0, bbox[1]-margin)
        x1 = min(canvas_w, bbox[2]+margin)
        y1 = min(canvas_h, bbox[3]+margin)
        result = result.crop((x0, y0, x1, y1))

    # ---- 横幅スケール → 斜体（後処理） ----
    result = _apply_x_scale(result, x_scale)
    result = _apply_slant(result, slant)

    return result
