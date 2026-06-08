from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

orig    = r"C:\Users\shira_k13727w\OneDrive\Desktop\クロード保管用\17【岩田さん用株式会社Della Force会社概要資料】\page6_original.png"
out_img = r"C:\Users\shira_k13727w\OneDrive\Desktop\クロード保管用\17【岩田さん用株式会社Della Force会社概要資料】\page6_with_pos.png"

img = Image.open(orig).convert("RGB")
arr = np.array(img, dtype=np.float32)
W, H = img.size   # 3840 x 2160

# ─── 1. 背景グラデーション再構築 ───
BG_Y0, BG_Y1 = 1035, 1820
left_bg  = arr[BG_Y0:BG_Y1,  20:100, :].mean(axis=1)
right_bg = arr[BG_Y0:BG_Y1, 3740:3820, :].mean(axis=1)
zone_h   = BG_Y1 - BG_Y0
xs       = np.linspace(0, 1, W)
bg_zone  = np.zeros((zone_h, W, 3), dtype=np.float32)
for c in range(3):
    bg_zone[:, :, c] = left_bg[:, c:c+1] * (1-xs) + right_bg[:, c:c+1] * xs

result_arr = arr.copy()
result_arr[BG_Y0:BG_Y1] = np.clip(bg_zone, 0, 255)

# フェードブレンド（境界を自然に）
FADE = 25
for dy in range(FADE):
    alpha = dy / FADE
    for y in [BG_Y0+dy, BG_Y1-1-dy]:
        result_arr[y] = arr[y] * (1-alpha) + result_arr[y] * alpha

# ─── 2. レイアウト: 4列均等 ───
MARGIN      = 200
GAP         = 80
IW          = (W - 2*MARGIN - 3*GAP) // 4   # 800
IH          = 600
LOGO_ZONE_Y = BG_Y0 + (zone_h - IH) // 2   # 1127

def item_x0(i): return MARGIN + i*(IW+GAP)
def item_cx(i): return item_x0(i) + IW//2
# item_x0: [200, 1080, 1960, 2840]
# item_cx: [600, 1480, 2360, 3240]

print(f"IW={IW}, IH={IH}, LOGO_ZONE_Y={LOGO_ZONE_Y}")
print(f"Column centers: {[item_cx(i) for i in range(4)]}")

# ─── 3. オリジナル画像からロゴをマスク合成 ───
# オリジナル底部のロゴ位置（解析済み）:
#   OCTON  : content x=911-1503, center x=1207
#   SHOGUN : content x=2304-2936, center x=2620
# クロップ範囲: y=BG_Y0〜y=BG_Y0+739（コンテンツ縦範囲）→IHにスケール

CROP_Y0 = BG_Y0         # 1035
CROP_Y1 = BG_Y0 + 739   # 1774（元ロゴの縦範囲）

def paste_original_logo(result_arr, slot_i, orig_cx, threshold=18):
    """元画像からロゴを切り抜き、グラデーション背景を透過させてスロットに合成"""
    # 水平クロップ（IW幅、orig_cx中心）
    cx0 = max(0, orig_cx - IW//2)
    cx1 = min(W, cx0 + IW)
    actual_w = cx1 - cx0

    orig_crop = arr[CROP_Y0:CROP_Y1, cx0:cx1]            # shape: (739, IW, 3)
    bg_at     = bg_zone[CROP_Y0-BG_Y0:CROP_Y1-BG_Y0, cx0:cx1]  # same shape

    # ロゴ領域マスク（グラデーションとの差分）
    diff = np.abs(orig_crop.astype(np.float32) - bg_at).max(axis=2)
    mask_raw = (diff > threshold).astype(np.uint8) * 255

    # 幅が足りない場合は中央配置でパディング
    if actual_w < IW:
        pad_l = (IW - actual_w) // 2
        orig_pad = np.zeros((CROP_Y1-CROP_Y0, IW, 3), dtype=np.uint8)
        mask_pad = np.zeros((CROP_Y1-CROP_Y0, IW),    dtype=np.uint8)
        orig_pad[:, pad_l:pad_l+actual_w] = orig_crop
        mask_pad[:, pad_l:pad_l+actual_w] = mask_raw
        orig_crop = orig_pad
        mask_raw  = mask_pad

    # スケール: (IW, 739) → (IW, IH=600)
    orig_img = Image.fromarray(orig_crop.astype(np.uint8)).resize((IW, IH), Image.LANCZOS)
    mask_img = Image.fromarray(mask_raw).resize((IW, IH), Image.LANCZOS)
    mask_img = mask_img.filter(ImageFilter.GaussianBlur(1))

    orig_f = np.array(orig_img, dtype=np.float32)
    mask_f = np.array(mask_img, dtype=np.float32)[:, :, np.newaxis] / 255.0

    # スロットに合成（ロゴ部分のみ上書き、背景は新グラデーション）
    dx0 = item_x0(slot_i)
    dy0 = LOGO_ZONE_Y
    dest = result_arr[dy0:dy0+IH, dx0:dx0+IW].astype(np.float32)
    blended = dest * (1 - mask_f) + orig_f * mask_f
    result_arr[dy0:dy0+IH, dx0:dx0+IW] = np.clip(blended, 0, 255)

# OCTON（スロット0）
paste_original_logo(result_arr, slot_i=0, orig_cx=1207)
print("OCTON pasted")

# SHOGUN（スロット2）
paste_original_logo(result_arr, slot_i=2, orig_cx=2620)
print("SHOGUN pasted")

# PIL描画用に変換
result = Image.fromarray(result_arr.astype(np.uint8))
d = ImageDraw.Draw(result)

def FB(s):  return ImageFont.truetype(r"C:\Windows\Fonts\YuGothB.ttc", s)
def FME(s): return ImageFont.truetype(r"C:\Windows\Fonts\meiryo.ttc",  s)

# ─── 4. COARIS（スロット1）: グラデーション上に直接描画 ───
coaris_sq   = Image.open(r"C:\Users\shira_k13727w\OneDrive\DF\全体\COARIS\ロゴ四角.png").convert("RGBA")
icon_crop_h = int(coaris_sq.height * 0.60)
icon_only   = coaris_sq.crop((0, 0, coaris_sq.width, icon_crop_h))
iw_c        = int(IW * 0.52)
ih_c        = int(icon_only.height * iw_c / icon_only.width)
icon_r      = icon_only.resize((iw_c, ih_c), Image.LANCZOS)

logo_top = LOGO_ZONE_Y + int(IH * 0.04)
paste_x  = item_x0(1) + (IW - iw_c) // 2
result.paste(icon_r, (paste_x, logo_top), icon_r)
icon_bottom_c = logo_top + ih_c

cx1  = item_cx(1)
NAVY = (25, 40, 100)
CYAN = (0, 180, 220)
ty   = icon_bottom_c + 8
d.text((cx1, ty), "COARIS AI", font=FB(46), fill=NAVY, anchor="mt")
bbox  = d.textbbox((0, 0), "COARIS AI", font=FB(46))
txt_w = bbox[2] - bbox[0]
d.text((cx1 + txt_w//2 + 4, ty+4), "+", font=FB(36), fill=CYAN, anchor="lt")
d.text((cx1, ty+54), "業務補助AIクラウド", font=FME(24), fill=(80, 90, 110), anchor="mt")
sep_y = ty + 54 + 36
d.line([(cx1-IW//3, sep_y), (cx1+IW//3, sep_y)], fill=(200, 215, 235), width=2)
d.text((cx1, sep_y+15), "COARIS AI（社内AI基盤）", font=FB(27), fill=(40, 45, 60), anchor="mt")

# ─── 5. POS（スロット3）: グラデーション上に直接描画 ───
cx3   = item_cx(3)
BLUE  = (30, 64, 175)
LBLUE = (147, 197, 253)
GREEN = (34, 197, 94)

TOP = LOGO_ZONE_Y + int(IH * 0.02)
IS  = int(IH * 0.50)   # 300

TW = int(IS * 0.82); TH = int(IS * 0.65)
TX0 = cx3 - TW//2; TY0 = TOP; TX1 = cx3 + TW//2; TY1 = TY0 + TH
d.rounded_rectangle([TX0, TY0, TX1, TY1], radius=20, fill=BLUE)
SM = 13
d.rectangle([TX0+SM, TY0+SM, TX1-SM, TY1-SM], fill=LBLUE)
for k, p in enumerate([0.22, 0.38, 0.54, 0.70]):
    ly = TY0+SM + int((TH-2*SM)*p)
    lw = int((TW-2*SM)*(0.70-k*0.09))
    d.rectangle([TX0+SM+12, ly, TX0+SM+12+lw, ly+7], fill=BLUE)
SW = 16
d.rectangle([cx3-SW, TY1, cx3+SW, TY1+int(IS*0.15)], fill=BLUE)
BW = int(IS*0.44); BY2 = TY1+int(IS*0.15)
d.rounded_rectangle([cx3-BW, BY2, cx3+BW, BY2+int(IS*0.09)], radius=8, fill=BLUE)
CR = int(IS*0.15); CCX = TX1+7; CCY = TY1+7
d.ellipse([CCX-CR, CCY-CR, CCX+CR, CCY+CR], fill=GREEN)
d.line([(CCX-int(CR*.55), CCY+int(CR*.05)),
        (CCX-int(CR*.10), CCY+int(CR*.45)),
        (CCX+int(CR*.56), CCY-int(CR*.40))], fill="white", width=7)

# POSラベル
icon_bottom_p = TOP + IS
ty3 = icon_bottom_p + 14
d.text((cx3, ty3), "POS System", font=FME(26), fill=(110, 125, 150), anchor="mt")
ty3 += 36
d.text((cx3, ty3), "POSシステム開発", font=FB(44), fill=BLUE, anchor="mt")
sy3 = ty3 + 62
d.line([(cx3-IW//3, sy3), (cx3+IW//3, sy3)], fill=(200, 215, 235), width=2)
d.text((cx3, sy3+15), "POS System Development", font=FB(27), fill=(40, 45, 60), anchor="mt")

result.save(out_img, quality=97)
print("Done:", out_img)
