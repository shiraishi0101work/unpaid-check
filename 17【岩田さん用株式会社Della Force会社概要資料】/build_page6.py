from PIL import Image, ImageDraw, ImageFont
import numpy as np

orig       = r"C:\Users\shira_k13727w\OneDrive\Desktop\クロード保管用\17【岩田さん用株式会社Della Force会社概要資料】\page6_original.png"
out_img    = r"C:\Users\shira_k13727w\OneDrive\Desktop\クロード保管用\17【岩田さん用株式会社Della Force会社概要資料】\page6_with_pos.png"
coaris_logo= r"C:\Users\shira_k13727w\OneDrive\DF\全体\COARIS\ロゴ横.png"

img = Image.open(orig).convert("RGB")
arr = np.array(img, dtype=np.float32)
W, H = img.size   # 3840 x 2160

# ─── 1. 背景グラデーション再構築 ───
BG_Y0, BG_Y1 = 1035, 1820
left_bg  = arr[BG_Y0:BG_Y1,  20:100, :].mean(axis=1)
right_bg = arr[BG_Y0:BG_Y1, 3740:3820, :].mean(axis=1)
zone_h = BG_Y1 - BG_Y0
xs = np.linspace(0, 1, W)
bg_zone = np.zeros((zone_h, W, 3), dtype=np.float32)
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

result = Image.fromarray(result_arr.astype(np.uint8))

# ─── 2. レイアウト ───
MARGIN = 200
GAP    = 80
IW     = (W - 2*MARGIN - 3*GAP) // 4   # 820
IH     = 600
LOGO_ZONE_Y = BG_Y0 + (zone_h - IH) // 2
print(f"item={IW}x{IH}, y={LOGO_ZONE_Y}")

def item_x(i): return MARGIN + i*(IW+GAP)

def slot_bg(i):
    x0 = item_x(i)
    patch = bg_zone[LOGO_ZONE_Y-BG_Y0:LOGO_ZONE_Y-BG_Y0+IH, x0:x0+IW]
    return tuple(patch.mean(axis=(0,1)).astype(int))

# ─── 3. フォント ───
def FB(s):  return ImageFont.truetype(r"C:\Windows\Fonts\YuGothB.ttc", s)
def FM(s):  return ImageFont.truetype(r"C:\Windows\Fonts\YuGothM.ttc", s)
def FME(s): return ImageFont.truetype(r"C:\Windows\Fonts\meiryo.ttc",  s)

# ─── 4. 共通ラベル描画 ───
def draw_labels(d, cx, icon_bottom, small_label, main_label, main_color, en_label):
    ty = icon_bottom + 14
    if small_label:
        d.text((cx, ty), small_label, font=FME(26), fill=(110,125,150), anchor="mt")
        ty += 36
    d.text((cx, ty), main_label, font=FB(44), fill=main_color, anchor="mt")
    sy = ty + 62
    d.line([(cx-IW//3, sy),(cx+IW//3, sy)], fill=(200,215,235), width=2)
    d.text((cx, sy+15), en_label, font=FB(27), fill=(40,45,60), anchor="mt")

# ─── 5. OCTON ───
def make_octon():
    bg = slot_bg(0)
    im = Image.new("RGB", (IW, IH), bg)
    d  = ImageDraw.Draw(im)
    cx = IW//2
    ORANGE = (235, 115, 30)
    DARK   = (50, 50, 50)
    TOP = int(IH*0.02)
    IS  = int(IH*0.50)

    # 書類スタック（下から）
    sh = int(IS*0.44); sw = int(IS*0.58)
    sy = TOP + int(IS*0.52)
    for i in range(4, -1, -1):
        oy = sy + i*int(IS*0.042)
        d.rounded_rectangle([cx-sw//2, oy, cx+sw//2, oy+sh],
                             radius=6, fill=(255,255,255), outline=DARK, width=3)

    # タコ胴体
    bx, by = cx, TOP + int(IS*0.30)
    br = int(IS*0.24)
    d.ellipse([bx-br, by-br, bx+br, by+br], fill=ORANGE)
    # 目
    for ex in [-int(br*0.38), int(br*0.38)]:
        er = int(br*0.18)
        ey = by - int(br*0.12)
        d.ellipse([bx+ex-er, ey-er, bx+ex+er, ey+er], fill="white")
        d.ellipse([bx+ex-er//2, ey-er//2, bx+ex+er//2, ey+er//2], fill=DARK)
    # 口（笑顔）
    d.arc([bx-int(br*0.3), by+int(br*0.1), bx+int(br*0.3), by+int(br*0.4)],
          start=10, end=170, fill=DARK, width=4)
    # 脚
    for j, (lx_r, angle) in enumerate([(-0.9,-20),(-0.45,-8),(0,0),(0.45,8),(0.9,20)]):
        x1 = int(bx + lx_r*br)
        y1 = int(by + br*0.75)
        x2 = x1 + int(angle*1.2)
        y2 = y1 + int(IS*0.15)
        d.line([(x1,y1),(x2,y2)], fill=ORANGE, width=max(4,int(br*0.26)))

    draw_labels(d, cx, TOP+IS,
                "書類回収 AI BOT", "オクトン", (30,150,220),
                "OCTON（OCR x AI書類回収）")
    return im

# ─── 6. COARIS ───
def make_coaris():
    bg = slot_bg(1)
    im = Image.new("RGB", (IW, IH), bg)
    d  = ImageDraw.Draw(im)
    cx = IW//2

    # ロゴ四角.pngのアイコン部分（上60%）だけ切り取って使う
    coaris_sq = Image.open(r"C:\Users\shira_k13727w\OneDrive\DF\全体\COARIS\ロゴ四角.png").convert("RGBA")
    # アイコン部分: 上65%を切り取り
    icon_crop_h = int(coaris_sq.height * 0.60)
    icon_only   = coaris_sq.crop((0, 0, coaris_sq.width, icon_crop_h))
    iw = int(IW * 0.52)
    ih = int(icon_only.height * iw / icon_only.width)
    icon_r = icon_only.resize((iw, ih), Image.LANCZOS)
    logo_top = int(IH * 0.04)
    im.paste(icon_r, ((IW-iw)//2, logo_top), icon_r)
    icon_bottom = logo_top + ih

    # "COARIS AI+" テキスト（オリジナル資料に合わせて）
    NAVY = (25, 40, 100)
    CYAN = (0, 180, 220)
    ty = icon_bottom + 8
    d.text((cx, ty), "COARIS AI", font=FB(46), fill=NAVY, anchor="mt")
    # "+" を右に cyan で追加
    bbox = d.textbbox((0,0), "COARIS AI", font=FB(46))
    txt_w = bbox[2] - bbox[0]
    plus_x = cx + txt_w//2 + 4
    d.text((plus_x, ty+4), "+", font=FB(36), fill=CYAN, anchor="lt")
    # サブテキスト
    d.text((cx, ty+54), "\u696d\u52d9\u88dc\u52a9AI\u30af\u30e9\u30a6\u30c9",
           font=FME(24), fill=(80,90,110), anchor="mt")
    sep_y = ty + 54 + 36
    d.line([(cx-IW//3, sep_y),(cx+IW//3, sep_y)], fill=(200,215,235), width=2)
    d.text((cx, sep_y+15), "COARIS AI\uff08\u793e\u5185AI\u57fa\u76e4\uff09",
           font=FB(27), fill=(40,45,60), anchor="mt")
    return im

# ─── 7. ShogunOS ───
def make_shogun():
    bg = slot_bg(2)
    im = Image.new("RGB", (IW, IH), bg)
    d  = ImageDraw.Draw(im)
    cx = IW//2
    BLK = (15, 15, 20)
    TOP = int(IH*0.02)
    SC  = int(IH*0.40)   # scale

    # 上部アーチ（兜）
    ax = cx; ay = TOP + int(SC*0.05)
    aw = int(SC*0.90)
    d.arc([ax-aw, ay, ax+aw, ay+int(SC*1.1)],
          start=205, end=335, fill=BLK, width=int(SC*0.17))

    # 左右の角飾り
    mid_y = TOP + int(SC*0.55)
    for side in [-1, 1]:
        px = ax + side*aw
        py = ay + int(SC*0.55)
        d.line([(px, py),(px + side*int(SC*0.28), py - int(SC*0.28))],
               fill=BLK, width=int(SC*0.16))

    # 額の三角紋
    tri = [(ax, ay+int(SC*0.12)),
           (ax-int(SC*0.28), mid_y),
           (ax+int(SC*0.28), mid_y)]
    d.polygon(tri, fill=BLK)

    # 胴部メインブロック
    bw = int(SC*1.55); bh = int(SC*0.55)
    bx0 = ax-bw//2; by0 = mid_y
    d.rounded_rectangle([bx0, by0, bx0+bw, by0+bh], radius=5, fill=BLK)
    # 横ライン2本
    for k in [1,2]:
        ly = by0 + k*bh//3
        d.line([(bx0+8,ly),(bx0+bw-8,ly)], fill=(55,55,62), width=3)
    # 縦ライン（中央）
    d.line([(ax, by0+6),(ax, by0+bh-6)], fill=(55,55,62), width=4)

    # 下段左右ウイング
    pw = int(SC*0.58); ph = int(SC*0.24)
    py0 = by0 + bh + 5
    for side in [-1, 1]:
        px0 = ax + (6 if side>0 else -6-pw)
        d.rounded_rectangle([px0, py0, px0+pw, py0+ph], radius=4, fill=BLK)

    icon_bottom = py0 + ph
    draw_labels(d, cx, icon_bottom,
                None, "SHOGUN OS", BLK,
                "ShogunOS\uff08AI \u00d7 \u7d44\u7e54OS\uff09")
    return im

# ─── 8. POS ───
def make_pos():
    BLUE  = (30, 64, 175)
    LBLUE = (147, 197, 253)
    GREEN = (34, 197, 94)
    bg = slot_bg(3)
    im = Image.new("RGB", (IW, IH), bg)
    d  = ImageDraw.Draw(im)
    cx = IW//2
    TOP = int(IH*0.02)
    IS  = int(IH*0.50)

    TW = int(IS*0.82); TH = int(IS*0.65)
    TX0=cx-TW//2; TY0=TOP; TX1=cx+TW//2; TY1=TY0+TH
    d.rounded_rectangle([TX0,TY0,TX1,TY1], radius=20, fill=BLUE)
    SM=13
    d.rectangle([TX0+SM,TY0+SM,TX1-SM,TY1-SM], fill=LBLUE)
    for k,p in enumerate([0.22,0.38,0.54,0.70]):
        ly=TY0+SM+int((TH-2*SM)*p)
        lw=int((TW-2*SM)*(0.70-k*0.09))
        d.rectangle([TX0+SM+12,ly,TX0+SM+12+lw,ly+7], fill=BLUE)
    d.text((TX1-SM-55,TY0+SM+7),"\\xa5",font=FB(32),fill=BLUE)
    SW=16
    d.rectangle([cx-SW,TY1,cx+SW,TY1+int(IS*0.15)],fill=BLUE)
    BW=int(IS*0.44); BY2=TY1+int(IS*0.15)
    d.rounded_rectangle([cx-BW,BY2,cx+BW,BY2+int(IS*0.09)],radius=8,fill=BLUE)
    CR=int(IS*0.15); CCX=TX1+7; CCY=TY1+7
    d.ellipse([CCX-CR,CCY-CR,CCX+CR,CCY+CR],fill=GREEN)
    d.line([(CCX-int(CR*.55),CCY+int(CR*.05)),
            (CCX-int(CR*.10),CCY+int(CR*.45)),
            (CCX+int(CR*.56),CCY-int(CR*.40))],fill="white",width=7)

    draw_labels(d, cx, TOP+IS,
                "POS System", "POSシステム開発", BLUE,
                "POS System Development")
    return im

# ─── 9. 貼り付け ───
for i, make_fn in enumerate([make_octon, make_coaris, make_shogun, make_pos]):
    item_img = make_fn()
    result.paste(item_img, (item_x(i), LOGO_ZONE_Y))

result.save(out_img, quality=97)
print("Done:", out_img)
