"""
MEO対策エンド資料 - Premium Redesign v5
大型数値・グラデーションカード・バッジ・ウォーターマーク・微斜めセパレーター
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from pptx.oxml import parse_xml

OUTPUT = r'c:/Users/shira_k13727w/OneDrive/Desktop/クロード保管用/08【MEO対策エンド資料デザイン化】/MEO対策エンド資料_v5.pptx'

# ── プレースホルダー（後で差し替え）──────────────────────────
SVC_NAME = 'MEO対策サービス'   # ← サービス正式名称に変更
COMPANY  = '株式会社〇〇'      # ← 会社名に変更
CONTACT  = 'TEL: 000-0000-0000 / LINE: @xxxxx'  # ← 連絡先に変更

# ================================================================
# DESIGN SYSTEM
# ================================================================
T_DK  = RGBColor(0x00, 0x5E, 0x6E)
T_MD  = RGBColor(0x00, 0x9A, 0x9A)
T_LT  = RGBColor(0x00, 0xC4, 0xCC)
T_XL  = RGBColor(0x3D, 0xD9, 0xE0)
T_WM  = RGBColor(0xD8, 0xF0, 0xEF)   # ウォーターマーク用超薄ティール
YLW   = RGBColor(0xF5, 0xC0, 0x00)
ORG   = RGBColor(0xFF, 0x88, 0x00)
NVY   = RGBColor(0x0A, 0x18, 0x2C)
WHT   = RGBColor(0xFF, 0xFF, 0xFF)
OWHT  = RGBColor(0xF0, 0xF6, 0xF9)
TXT   = RGBColor(0x12, 0x22, 0x34)
TXMD  = RGBColor(0x44, 0x58, 0x6C)
LGR   = RGBColor(0xC8, 0xD8, 0xE6)
LGRD  = RGBColor(0xA8, 0xBC, 0xCC)   # ダークグレー
DWM   = RGBColor(0x00, 0x4A, 0x58)   # ダーク背景用ウォーターマーク

H_DK  = '005E6E'
H_MD  = '009A9A'
H_LT  = '00C4CC'
H_XL  = '3DD9E0'
H_NVY = '0A182C'
H_NY2 = '0E2238'

# ================================================================
# SETUP
# ================================================================
prs = Presentation()
prs.slide_width  = Inches(13.33)
prs.slide_height = Inches(7.5)
BL = prs.slide_layouts[6]
W  = prs.slide_width
H  = prs.slide_height

def ns(): return prs.slides.add_slide(BL)

# ================================================================
# PRIMITIVES
# ================================================================
def bg_solid(s, c):
    f = s.background.fill; f.solid(); f.fore_color.rgb = c

def _push_back(s, el):
    t = s.shapes._spTree; t.remove(el); t.insert(2, el)

def box(s, l, t, w, h, c, back=True, rnd=False):
    sh = s.shapes.add_shape(5 if rnd else 1, int(l), int(t), int(w), int(h))
    sh.fill.solid(); sh.fill.fore_color.rgb = c
    sh.line.fill.background()
    if back: _push_back(s, sh._element)
    return sh

def _inject_grad(sh, h1, h2, ang):
    sp = sh._element
    spPr = sp.find(qn('p:spPr'))
    for c in list(spPr):
        if any(c.tag.endswith(x) for x in
               ['solidFill','gradFill','noFill','blipFill','pattFill']):
            spPr.remove(c)
    spPr.insert(0, parse_xml(
        f'<a:gradFill xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        f'<a:gsLst>'
        f'<a:gs pos="0"><a:srgbClr val="{h1}"/></a:gs>'
        f'<a:gs pos="100000"><a:srgbClr val="{h2}"/></a:gs>'
        f'</a:gsLst>'
        f'<a:lin ang="{ang}" scaled="0"/>'
        f'</a:gradFill>'
    ))

def gbox(s, l, t, w, h, h1, h2, ang=0, back=True):
    sh = s.shapes.add_shape(1, int(l), int(t), int(w), int(h))
    sh.line.fill.background()
    _inject_grad(sh, h1, h2, ang)
    if back: _push_back(s, sh._element)
    return sh

def gbox_rnd(s, l, t, w, h, h1, h2, ang=0, back=False):
    """ソリッドカード（h1色で塗りつぶし）"""
    r = int(h1[0:2], 16); g = int(h1[2:4], 16); b = int(h1[4:6], 16)
    return box(s, l, t, w, h, RGBColor(r, g, b), back=back)

def oval(s, l, t, w, h, c, back=False):
    sh = s.shapes.add_shape(9, int(l), int(t), int(w), int(h))
    sh.fill.solid(); sh.fill.fore_color.rgb = c
    sh.line.fill.background()
    if back: _push_back(s, sh._element)
    return sh

def tb(s, l, t, w, h, text, sz, c, bold=False,
       align=PP_ALIGN.LEFT, wrap=True):
    tx = s.shapes.add_textbox(int(l), int(t), int(w), int(h))
    tf = tx.text_frame; tf.word_wrap = wrap
    for i, ln in enumerate(str(text).split('\n')):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        r = p.add_run(); r.text = ln
        r.font.size = Pt(sz); r.font.bold = bold
        r.font.color.rgb = c
    return tx

# ================================================================
# V5 HELPERS
# ================================================================
def badge(s, l, t, text, c=T_MD):
    """プレミアムバッジ（ヘッダー上端に浮かせる）"""
    bw = Inches(1.9); bh = Inches(0.38)
    bx = s.shapes.add_shape(5, int(l), int(t), int(bw), int(bh))
    bx.fill.solid(); bx.fill.fore_color.rgb = c
    bx.line.fill.background()
    tf = bx.text_frame; tf.word_wrap = False
    tf.paragraphs[0].alignment = PP_ALIGN.CENTER
    r = tf.paragraphs[0].add_run()
    r.text = text; r.font.size = Pt(11); r.font.bold = True
    r.font.color.rgb = TXT if c == YLW else WHT

def wm(s, text, sz=130, xr=0.40, yr=0.14, dark=False):
    """背景ウォーターマーク（最背面）"""
    c = DWM if dark else T_WM
    tx = s.shapes.add_textbox(int(W * xr), int(H * yr),
                               int(W * 0.60), int(H * 0.72))
    tf = tx.text_frame
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.RIGHT
    r = p.add_run(); r.text = text
    r.font.size = Pt(sz); r.font.bold = True; r.font.color.rgb = c
    el = tx._element
    s.shapes._spTree.remove(el)
    s.shapes._spTree.insert(2, el)

def numblock(s, l, t, w, h, num_str, unit_str, label_str,
             nc=YLW, tc=WHT):
    """大型数値ブロック（グラデーション背景）"""
    gbox_rnd(s, l, t, w, h, H_DK, H_MD, ang=5400000, back=False)
    unit_t = t + h - Inches(0.55)
    num_h  = unit_t - t - Inches(0.60)
    avail_in = num_h / 914400
    sz = min(64, max(36, int(avail_in * 52)))
    tb(s, l+Inches(0.12), t+Inches(0.14), w-Inches(0.25), Inches(0.42),
       label_str, 11, RGBColor(0x88, 0xCC, 0xCA), align=PP_ALIGN.CENTER)
    tb(s, l+Inches(0.08), t+Inches(0.54), w-Inches(0.16), num_h,
       num_str, sz, nc, bold=True, align=PP_ALIGN.CENTER)
    tb(s, l+Inches(0.12), unit_t, w-Inches(0.25), Inches(0.48),
       unit_str, 14, tc, align=PP_ALIGN.CENTER)

# ================================================================
# LAYOUT CONSTANTS
# ================================================================
MR     = Inches(0.52)
HDR    = Inches(1.35)
YL_H   = Inches(0.065)
SB_W   = Inches(0.07)
BOT    = Inches(0.07)
BODY_T = HDR + YL_H

def std_header(s, title, bdg='', wm_text=''):
    """V5 強化ヘッダー: NVY→T_DK グラデ + 微斜めゴールドライン"""
    # グラデーションヘッダー帯
    gbox(s, 0, 0, W, HDR, H_NVY, H_DK, ang=5400000, back=False)
    # 微斜めゴールドセパレーター（rotation=-1.2°）
    sep = s.shapes.add_shape(
        1, int(-Inches(0.25)), int(HDR - Inches(0.012)),
        int(W + Inches(0.5)), int(YL_H))
    sep.fill.solid(); sep.fill.fore_color.rgb = YLW
    sep.line.fill.background(); sep.rotation = -1.2
    # サイドバー・ボトムバー
    box(s, 0, BODY_T, SB_W, H - BODY_T - BOT, T_MD, back=False)
    box(s, 0, H - BOT, W, BOT, T_DK, back=False)
    # タイトル（26pt — 長タイトルでもオーバーフローしない）
    tb(s, MR, Inches(0.22), W - MR - Inches(2.4), HDR - Inches(0.15),
       title, 26, WHT, bold=True)
    # バッジ
    if bdg:
        badge(s, W - Inches(2.1), Inches(0.10), bdg)
    # ウォーターマーク
    if wm_text:
        wm(s, wm_text)

# ================================================================
# SLIDE 01: COVER
# ================================================================
def make_cover():
    s = ns()
    bg_solid(s, NVY)
    # 要素を back=False で順番に積み上げ → 最後にgboxをback=Trueで最背面へ

    # 左ティールアクセントバー
    box(s, 0, 0, Inches(0.12), H, T_MD, back=False)
    # ホワイト下部パネル
    box(s, 0, H * 0.70, W, H * 0.30, WHT, back=False)
    # 微斜めゴールドセパレーター
    sep = s.shapes.add_shape(
        1, int(-Inches(0.2)), int(H * 0.695),
        int(W + Inches(0.4)), int(Inches(0.068)))
    sep.fill.solid(); sep.fill.fore_color.rgb = YLW
    sep.line.fill.background(); sep.rotation = -1.0
    # 装飾サークル
    oval(s, W * 0.65, -Inches(1.0), Inches(4.6), Inches(4.6), T_XL)
    # ── テキスト ──
    tb(s, Inches(0.55), H * 0.06, W * 0.60, H * 0.46,
       'MEO対策で\n集客力を最大化する', 52, WHT, bold=True)
    tb(s, Inches(0.55), H * 0.52, W * 0.62, H * 0.15,
       'Googleマップ集客で、売上が上がる、選ばれるお店に',
       19, YLW, bold=True)
    # 下部パネル内テキスト
    tb(s, Inches(0.55), H * 0.735, W * 0.45, Inches(0.45),
       'MEO対策 / Googleビジネスプロフィール最適化', 12, TXMD)
    tb(s, Inches(0.55), H * 0.81, W * 0.45, Inches(0.45),
       '検索上位獲得で、見込み客を自動集客', 15, TXT, bold=True)
    # 右下スタット3点
    stats = [
        ('Google利用率', '78.8%'),
        ('ローカル検索', '5人に4人'),
        ('MAP上位＝', '自動集客'),
    ]
    for i, (lbl, val) in enumerate(stats):
        sy = H * 0.735 + Inches(0.55) * i
        gbox_rnd(s, W * 0.55, sy, W * 0.40, Inches(0.46),
                 H_DK, H_MD, ang=5400000)
        tb(s, W * 0.56, sy + Inches(0.04), W * 0.18, Inches(0.38),
           lbl, 10, RGBColor(0xA0, 0xD6, 0xD4), align=PP_ALIGN.RIGHT)
        tb(s, W * 0.75, sy + Inches(0.04), W * 0.18, Inches(0.38),
           val, 16, YLW, bold=True, align=PP_ALIGN.LEFT)
    # 右グラデパネル（最後にback=Trueで最背面）
    gbox(s, W * 0.42, 0, W * 0.58, H, H_MD, H_XL, ang=5400000)
    # MEO ウォーターマーク（最背面）
    wm(s, 'MEO', sz=160, xr=0.30, yr=0.05)
    print('  slide 01: Cover ✓')
    return s

# ================================================================
# SLIDE 02: SECTION — Googleマップ戦略
# ================================================================
def make_section_01():
    s = ns()
    bg_solid(s, NVY)
    box(s, 0, 0, Inches(0.45), H, T_MD, back=False)
    box(s, W * 0.60, 0, W * 0.40, H,
        RGBColor(0x0E, 0x22, 0x38), back=False)
    # 微斜めゴールドライン（中央やや下）
    sep = s.shapes.add_shape(
        1, int(-Inches(0.2)), int(H * 0.49),
        int(W + Inches(0.4)), int(Inches(0.055)))
    sep.fill.solid(); sep.fill.fore_color.rgb = YLW
    sep.line.fill.background(); sep.rotation = -1.0
    # セクション番号（大）
    tb(s, W * 0.61, H * 0.06, W * 0.37, H * 0.60,
       '01', 110, T_MD, bold=True, align=PP_ALIGN.CENTER)
    # テキスト
    tb(s, Inches(0.65), H * 0.17, W * 0.52, H * 0.22,
       '検索のメインがスマートフォンの今\n店舗集客の最短は', 17, T_XL)
    tb(s, Inches(0.65), H * 0.40, W * 0.52, H * 0.46,
       'Googleマップ戦略\nで勝つこと', 42, WHT, bold=True)
    print('  slide 02: Section ✓')
    return s

# ================================================================
# SLIDE 03: カスタマージャーニー
# ================================================================
def make_customer_journey():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, '今、MEO対策が必要な理由 ─ お客様はこうしてお店を選んでいます',
               'Customer Flow', 'MAP')
    steps = [
        ('01', '検索', 'スマートフォンで\n地域＋業種を検索', H_DK, H_MD),
        ('02', '比較', '写真や★評価で\n複数店舗を比較',    H_MD, H_LT),
        ('03', '決定', '口コミを読んで\n来店店舗を決定',    H_LT, H_XL),
        ('04', '行動', 'ルート検索・電話で\n来店行動',      '009A9A', H_XL),
    ]
    cw = (W - MR * 2 - SB_W - Inches(0.3)) / 4
    bl = MR + SB_W + Inches(0.15)
    ct = BODY_T + Inches(0.28)
    ch = H - BODY_T - BOT - Inches(0.95)
    for i, (num, hdg, desc, g1, g2) in enumerate(steps):
        cx = bl + cw * i
        gbox_rnd(s, cx, ct, cw - Inches(0.15), ch, g1, g2, ang=16200000)
        tb(s, cx + Inches(0.12), ct + Inches(0.12),
           cw - Inches(0.38), Inches(0.5),
           num, 28, YLW, bold=True, align=PP_ALIGN.CENTER)
        tb(s, cx + Inches(0.12), ct + Inches(0.62),
           cw - Inches(0.38), Inches(0.55),
           hdg, 22, WHT, bold=True, align=PP_ALIGN.CENTER)
        tb(s, cx + Inches(0.12), ct + Inches(1.25),
           cw - Inches(0.38), Inches(1.8),
           desc, 13, WHT, align=PP_ALIGN.CENTER)
    tb(s, MR + SB_W, H - Inches(0.72), W - MR * 2, Inches(0.58),
       'これら全て、Googleマップだけで完結します！',
       17, T_DK, bold=True, align=PP_ALIGN.CENTER)
    print('  slide 03: Customer Journey ✓')
    return s

# ================================================================
# SLIDE 04: Googleマップが目立つ場所
# ================================================================
def make_map_prominence():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, '検索結果で最も目立つ場所', 'Google Map', 'TOP')
    # 左ダークパネル
    gbox_rnd(s, MR + SB_W, BODY_T + Inches(0.2),
             W * 0.38, H - BODY_T - BOT - Inches(0.42),
             H_NVY, H_DK, ang=16200000, back=False)
    tb(s, MR + SB_W + Inches(0.25), BODY_T + Inches(0.45),
       W * 0.34, Inches(1.35),
       '検索結果で\n最も目立つ場所', 28, WHT, bold=True)
    tb(s, MR + SB_W + Inches(0.2), BODY_T + Inches(1.95),
       W * 0.35, Inches(0.5),
       'それが、Googleマップです', 17, YLW, bold=True)
    items_l = [
        ('検索画面の上から順に', '① 広告枠（リスティング）'),
        ('', '② 地図枠＝ローカルパック'),
        ('', '③ 自然検索枠'),
    ]
    for j, (sub, main) in enumerate(items_l):
        yt = BODY_T + Inches(2.65) + Inches(0.65) * j
        if sub:
            tb(s, MR + SB_W + Inches(0.2), yt - Inches(0.22),
               W * 0.36, Inches(0.3), sub, 11,
               RGBColor(0x88, 0xCC, 0xCA))
        tb(s, MR + SB_W + Inches(0.2), yt,
           W * 0.36, Inches(0.5), main, 14, WHT)
    # 右側：3つのnumblock
    rx = MR + SB_W + W * 0.42
    rw = W - rx - MR - Inches(0.1)
    nb_h = Inches(1.45)
    nb_data = [
        ('TOP 3', 'に表示', 'ローカルパック'),
        ('2〜3倍', 'クリック率', '広告枠との比較'),
        ('24時間', '自動集客', '表示コスト ¥0'),
    ]
    for k, (num, unit, lbl) in enumerate(nb_data):
        yt = BODY_T + Inches(0.2) + (nb_h + Inches(0.18)) * k
        numblock(s, rx, yt, rw, nb_h, num, unit, lbl)
    print('  slide 04: Map Prominence ✓')
    return s

# ================================================================
# SLIDE 05: 売上に直結する理由
# ================================================================
def make_revenue_driver():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, 'Googleマップが売上に直結する理由', 'Revenue', '¥')
    cols = [
        ('01', '圧倒的\nビュー数', '上位表示されるだけで\n月数万〜数十万回の\n表示機会を獲得できます',
         H_DK, H_MD),
        ('02', '来店意欲\nの向上', '写真・口コミで信頼感UP\n初めてのお客様も\n安心して来店できます',
         H_MD, H_LT),
        ('03', '売上\n拡大', 'ルート検索・電話・予約\n来店行動の全てがMAP\n一つで完結します',
         H_LT, H_XL),
    ]
    cw = (W - MR * 2 - SB_W - Inches(0.4)) / 3
    bl = MR + SB_W + Inches(0.2)
    ct = BODY_T + Inches(0.22)
    ch = H - BODY_T - BOT - Inches(0.95)
    for i, (num, hdg, desc, g1, g2) in enumerate(cols):
        cx = bl + cw * i
        gbox_rnd(s, cx, ct, cw - Inches(0.18), ch, g1, g2, ang=16200000)
        tb(s, cx + Inches(0.12), ct + Inches(0.12),
           cw - Inches(0.3), Inches(0.48),
           num, 30, YLW, bold=True, align=PP_ALIGN.CENTER)
        tb(s, cx + Inches(0.12), ct + Inches(0.65),
           cw - Inches(0.3), Inches(0.8),
           hdg, 24, WHT, bold=True, align=PP_ALIGN.CENTER)
        tb(s, cx + Inches(0.12), ct + Inches(1.55),
           cw - Inches(0.3), Inches(2.2),
           desc, 13, WHT, align=PP_ALIGN.CENTER)
    tb(s, MR + SB_W, H - Inches(0.68), W - MR * 2, Inches(0.55),
       '上位表示が、直接的な利益に繋がる体験をご実感ください！',
       15, T_DK, bold=True, align=PP_ALIGN.CENTER)
    print('  slide 05: Revenue Driver ✓')
    return s

# ================================================================
# SLIDE 06: Googleマップ経由で増える行動
# ================================================================
def make_map_actions():
    s = ns()
    bg_solid(s, T_DK)
    box(s, 0, 0, W, Inches(0.07), YLW, back=False)
    box(s, 0, H - Inches(0.07), W, Inches(0.07), YLW, back=False)
    badge(s, W - Inches(2.1), Inches(0.14), 'User Action', YLW)
    tb(s, MR, Inches(0.18), W - MR * 2, Inches(0.85),
       'Googleマップ経由で増える行動',
       34, WHT, bold=True, align=PP_ALIGN.CENTER)
    tb(s, MR, Inches(1.06), W - MR * 2, Inches(0.52),
       'ユーザーはGoogleマップで「見つけて → 確認して → 来店する」',
       16, YLW, align=PP_ALIGN.CENTER)
    actions = [
        ('🔍', '店舗をみつける', '「近くの○○」で検索\n地図上に表示される'),
        ('📷', '写真・口コミを見る', '雰囲気・評判を確認\n来店判断に直結'),
        ('🗺', 'ルート検索', 'ワンタップで経路案内\n来店率が大幅UP'),
        ('🌐', 'ウェブサイトを見る', 'メニュー・予約ページへ\nシームレスに誘導'),
    ]
    cw = (W - MR * 2) / 4
    for i, (icon, title, desc) in enumerate(actions):
        cx = MR + cw * i
        box(s, cx + Inches(0.1), Inches(1.75),
            cw - Inches(0.2), H - Inches(2.2), WHT, rnd=True, back=False)
        tb(s, cx + Inches(0.2), Inches(1.88), cw - Inches(0.42),
           Inches(0.7), icon, 30, T_MD, align=PP_ALIGN.CENTER)
        tb(s, cx + Inches(0.15), Inches(2.65), cw - Inches(0.3),
           Inches(0.65), title, 16, TXT, bold=True, align=PP_ALIGN.CENTER)
        tb(s, cx + Inches(0.15), Inches(3.42), cw - Inches(0.3),
           Inches(2.5), desc, 13, TXMD, align=PP_ALIGN.CENTER)
    wm(s, 'ACTION', sz=120, xr=0.30, yr=0.10, dark=True)
    print('  slide 06: Map Actions ✓')
    return s

# ================================================================
# SLIDE 07: 選ばれる店舗と選ばれない店舗の差
# ================================================================
def make_comparison():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, '選ばれる店舗と選ばれない店舗の差', 'Compare', 'vs')
    half = (W - SB_W - Inches(0.35)) / 2
    bl   = SB_W + Inches(0.2)
    ct   = BODY_T + Inches(0.18)
    ch   = H - BODY_T - BOT - Inches(0.50)
    # 左：選ばれない（グレーカード）
    box(s, bl, ct, half - Inches(0.15), ch, LGR, rnd=True, back=False)
    tb(s, bl + Inches(0.2), ct + Inches(0.22),
       half - Inches(0.5), Inches(0.58),
       '✕  選ばれない店舗', 20, TXMD, bold=True)
    bads = ['写真がない / 少ない', '住所・電話番号が不正確',
            '口コミゼロ or 放置', '情報更新が止まっている',
            '営業時間が不明確']
    for j, t_ in enumerate(bads):
        tb(s, bl + Inches(0.25),
           ct + Inches(1.0) + Inches(0.58) * j,
           half - Inches(0.5), Inches(0.52),
           f'×  {t_}', 14, TXT)
    tb(s, bl + Inches(0.15), H - Inches(0.75),
       half - Inches(0.3), Inches(0.52),
       '機会損失 — 見込み客を競合に奪われる', 13, LGRD, bold=True)
    # 右：選ばれる（グラデーションカード）
    rx = bl + half + Inches(0.15)
    gbox_rnd(s, rx, ct, half - Inches(0.15), ch, H_DK, H_MD,
             ang=16200000)
    tb(s, rx + Inches(0.2), ct + Inches(0.22),
       half - Inches(0.5), Inches(0.58),
       '◎  選ばれる店舗', 20, WHT, bold=True)
    goods = ['魅力的な写真が豊富', '情報が正確で最新',
             '高評価口コミが多い', '定期的に情報更新',
             'オーナー返信あり']
    for j, t_ in enumerate(goods):
        tb(s, rx + Inches(0.25),
           ct + Inches(1.0) + Inches(0.58) * j,
           half - Inches(0.5), Inches(0.52),
           f'◎  {t_}', 14, WHT)
    tb(s, rx + Inches(0.15), H - Inches(0.75),
       half - Inches(0.3), Inches(0.52),
       '集客チャンス — 選ばれ続ける店舗へ', 13, YLW, bold=True)
    print('  slide 07: Comparison ✓')
    return s

# ================================================================
# SLIDE 08: 上位表示されると何が変わるのか
# ================================================================
def make_what_changes():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, '上位表示されると何が変わるのか', 'Effect', 'UP')
    stages = [
        ('圏外',   '見つけてもらえない\n存在しないも同然', LGR,  TXT),
        ('上位表示', '検索で発見される\n月間ビュー数が激増', None, WHT),
        ('信頼獲得', '口コミ・写真で\n来店意欲が高まる',    None, WHT),
        ('売上UP',  '電話・来店・予約\nアクション数が倍増', YLW, TXT),
    ]
    sw  = (W - MR * 2 - SB_W) / 4
    bl2 = MR + SB_W + Inches(0.1)
    bt  = BODY_T + Inches(0.28)
    bh  = H - BODY_T - BOT - Inches(1.1)
    for i, (hdg, desc, bgc, tc) in enumerate(stages):
        cx = bl2 + sw * i
        drop = sw * 0.1 * i
        if bgc is None:
            gbox_rnd(s, cx, bt + drop, sw - Inches(0.12),
                     bh - drop, H_MD if i == 1 else H_DK,
                     H_LT if i == 1 else H_MD, ang=16200000)
        else:
            box(s, cx, bt + drop, sw - Inches(0.12),
                bh - drop, bgc, rnd=True, back=False)
        tb(s, cx + Inches(0.12), bt + drop + Inches(0.22),
           sw - Inches(0.28), Inches(0.62),
           hdg, 20, tc, bold=True, align=PP_ALIGN.CENTER)
        tb(s, cx + Inches(0.12), bt + drop + Inches(0.92),
           sw - Inches(0.28), Inches(2.2),
           desc, 13, tc, align=PP_ALIGN.CENTER)
        if i < 3:
            tb(s, cx + sw - Inches(0.3), bt + bh * 0.38,
               Inches(0.3), Inches(0.5), '▶', 20, YLW, bold=True)
    tb(s, MR + SB_W, H - Inches(0.60), W - MR * 2, Inches(0.45),
       'どれだけプロフィールを整えても、見つからなければ効果は得られません',
       15, TXMD, bold=True, align=PP_ALIGN.CENTER)
    print('  slide 08: What Changes ✓')
    return s

# ================================================================
# SLIDE 09: Googleが店舗を評価する3つの要素
# ================================================================
def make_three_factors():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, 'Googleが店舗を評価する3つの要素', '3 Factors', '×3')
    factors = [
        ('関連性', 'Relevance',
         '検索キーワードと\nプロフィール情報の\n一致度・完全性', H_DK, H_MD),
        ('距離',   'Distance',
         'ユーザーの現在地と\n店舗の物理的距離\n（エリア設定も有効）', H_MD, H_LT),
        ('知名度', 'Prominence',
         '口コミ数・評価点\nWeb上での言及度\nブランド認知度', H_LT, H_XL),
    ]
    ow   = (W - MR * 2 - SB_W - Inches(0.4)) / 3
    bl2  = MR + SB_W + Inches(0.2)
    ot   = BODY_T + Inches(0.28)
    oh   = H - BODY_T - BOT - Inches(1.0)
    for i, (jn, en, desc, g1, g2) in enumerate(factors):
        cx = bl2 + ow * i
        oval(s, cx + ow * 0.08, ot, ow * 0.84, oh * 0.82,
             T_DK if i == 0 else (T_MD if i == 1 else T_LT))
        tb(s, cx + Inches(0.1), ot + oh * 0.05,
           ow * 0.84, Inches(0.58),
           jn, 26, WHT, bold=True, align=PP_ALIGN.CENTER)
        tb(s, cx + Inches(0.1), ot + oh * 0.26,
           ow * 0.84, Inches(0.38),
           en, 12, YLW, align=PP_ALIGN.CENTER)
        tb(s, cx + Inches(0.1), ot + oh * 0.38,
           ow * 0.84, Inches(1.9),
           desc, 13, WHT, align=PP_ALIGN.CENTER)
    tb(s, MR + SB_W, H - Inches(0.62), W - MR * 2, Inches(0.52),
       'Googleのアルゴリズムは日々変化します。専門知識なしでMEO対策を継続するのは困難な時代です。',
       13, TXMD, align=PP_ALIGN.CENTER)
    print('  slide 09: Three Factors ✓')
    return s

# ================================================================
# SLIDE 10: 距離とエリアの考え方
# ================================================================
def make_distance_area():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, '距離とエリアの考え方', 'Area Strategy', 'GPS')
    # 左：大タイトルパネル
    gbox_rnd(s, MR + SB_W, BODY_T + Inches(0.18),
             W * 0.35, H - BODY_T - BOT - Inches(0.4),
             H_NVY, H_DK, ang=16200000, back=False)
    tb(s, MR + SB_W + Inches(0.22), BODY_T + Inches(0.42),
       W * 0.30, Inches(2.2),
       '距離と\nエリアの\n考え方', 34, WHT, bold=True)
    tb(s, MR + SB_W + Inches(0.18), BODY_T + Inches(2.85),
       W * 0.32, Inches(1.2),
       'Googleは距離だけでなく\n関連性・知名度も\n総合的に判断します',
       13, YLW)
    # 右：3アイテム
    rx  = MR + SB_W + W * 0.38
    rw  = W - rx - MR - Inches(0.1)
    items = [
        ('📍', '地域キーワード対策',
         '「新宿 カフェ」「渋谷 ランチ」など地名を含むキーワードで\n上位表示を狙うことが効果的です。'),
        ('🎯', 'エリア設定の最適化',
         '店舗から一定距離のユーザーに表示されやすくするため\nサービスエリアの正確な設定が重要です。'),
        ('🔍', '検索意図との一致',
         '「近くの○○」「今すぐ行ける○○」など\n来店意欲の高いキーワードへの対応が成果を左右します。'),
    ]
    ih = (H - BODY_T - BOT - Inches(0.58)) / 3
    for j, (icon, title, desc) in enumerate(items):
        yt = BODY_T + Inches(0.18) + ih * j
        box(s, rx, yt + Inches(0.08), Inches(0.055),
            ih - Inches(0.18), T_MD, back=False)
        tb(s, rx + Inches(0.18), yt + Inches(0.1),
           rw - Inches(0.2), Inches(0.52),
           f'{icon}  {title}', 16, TXT, bold=True)
        tb(s, rx + Inches(0.18), yt + Inches(0.68),
           rw - Inches(0.25), ih - Inches(0.85),
           desc, 12, TXMD)
    print('  slide 10: Distance Area ✓')
    return s

# ================================================================
# SLIDE 11: 知名度・口コミの影響
# ================================================================
def make_review_impact():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, '知名度・口コミの影響', 'Review', '★')
    cards = [
        ('口コミの数',  '多くのポジティブな口コミは\n信頼性を高め、新規顧客を\n引きつけます。',
         H_DK, H_MD),
        ('口コミの質',  '具体的な高評価は順位だけで\nなく来店意欲を直接\n高めます。',
         H_MD, H_LT),
        ('オーナー返信', '返信はGoogleとユーザー\n双方からの評価対象。\n誠実な対応が武器になります。',
         H_LT, H_XL),
        ('知名度UP',   'Web上での言及・被リンク・\nSNSでの認知度も\nアルゴリズムが参照します。',
         '009A9A', H_XL),
    ]
    cw = (W - MR * 2 - SB_W - Inches(0.3)) / 4
    bl = MR + SB_W + Inches(0.15)
    ct = BODY_T + Inches(0.22)
    ch = H - BODY_T - BOT - Inches(0.85)
    for i, (hdg, desc, g1, g2) in enumerate(cards):
        cx = bl + cw * i
        gbox_rnd(s, cx, ct, cw - Inches(0.15), ch, g1, g2, ang=16200000)
        tb(s, cx + Inches(0.12), ct + Inches(0.2),
           cw - Inches(0.28), Inches(0.58),
           hdg, 18, WHT, bold=True, align=PP_ALIGN.CENTER)
        tb(s, cx + Inches(0.12), ct + Inches(0.92),
           cw - Inches(0.28), Inches(2.8),
           desc, 13, WHT, align=PP_ALIGN.CENTER)
    print('  slide 11: Review Impact ✓')
    return s

# ================================================================
# SLIDE 12: 上位表示される店舗の共通点
# ================================================================
def make_common_traits():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, '上位表示される店舗の共通点', 'Top Store', 'No.1')
    traits = [
        ('📸', 'プロ品質の写真', '20枚以上・定期更新'),
        ('⭐', '高評価口コミ', '平均4.0以上・50件以上'),
        ('💬', 'オーナー返信', '全ての口コミに返信'),
        ('📝', '最新情報の投稿', '週1回以上のGBP投稿'),
        ('✅', '正確な基本情報', '住所・電話・営業時間'),
        ('🗓', 'Q&A・属性管理', 'キーワードを含めて充実'),
    ]
    cw2 = (W - MR * 2 - SB_W - Inches(0.3)) / 3
    bl  = MR + SB_W + Inches(0.15)
    rows = 2
    rh  = (H - BODY_T - BOT - Inches(0.6)) / rows
    for i, (icon, title, sub) in enumerate(traits):
        col = i % 3; row = i // 3
        cx = bl + cw2 * col
        yt = BODY_T + Inches(0.2) + rh * row
        gbox_rnd(s, cx, yt, cw2 - Inches(0.15), rh - Inches(0.15),
                 H_DK if row == 0 else H_MD, H_MD if row == 0 else H_LT,
                 ang=5400000)
        tb(s, cx + Inches(0.18), yt + Inches(0.18),
           cw2 - Inches(0.35), Inches(0.55),
           f'{icon}  {title}', 16, WHT, bold=True)
        tb(s, cx + Inches(0.18), yt + Inches(0.78),
           cw2 - Inches(0.35), Inches(0.65),
           sub, 13, YLW)
    print('  slide 12: Common Traits ✓')
    return s

# ================================================================
# SLIDE 13: 口コミが来店を後押しする理由
# ================================================================
def make_review_psychology():
    s = ns()
    bg_solid(s, T_DK)
    box(s, 0, 0, W, Inches(0.07), YLW, back=False)
    box(s, 0, H - Inches(0.07), W, Inches(0.07), YLW, back=False)
    badge(s, W - Inches(2.1), Inches(0.14), 'Psychology', YLW)
    tb(s, MR, Inches(0.18), W - MR * 2, Inches(0.75),
       '口コミが来店を後押しする理由', 34, WHT,
       bold=True, align=PP_ALIGN.CENTER)
    tb(s, MR, Inches(0.97), W - MR * 2, Inches(0.48),
       '多くの高評価な口コミが、お客様の「失敗しない」という安心感を生み出します',
       15, YLW, align=PP_ALIGN.CENTER)
    cards13 = [
        ('安心感',    '「みんなが良いと言っている」\n事実が不安を取り除き\n来店へのハードルを下げます。'),
        ('信頼性',    '実際の体験談は広告より\n信頼される、星評価が\n高いほど選ばれやすい。'),
        ('社会的証明', '多くの人が選んでいる実績が\n「自分も行くべきだ」という\n心理を生み出します。'),
    ]
    cw3 = (W - MR * 2) / 3
    ct  = Inches(1.7)
    ch  = H - ct - Inches(0.2)
    for i, (hdg, desc) in enumerate(cards13):
        cx = MR + cw3 * i
        box(s, cx + Inches(0.12), ct, cw3 - Inches(0.24), ch,
            WHT, rnd=True, back=False)
        tb(s, cx + Inches(0.22), ct + Inches(0.22),
           cw3 - Inches(0.45), Inches(0.58),
           hdg, 20, T_MD, bold=True, align=PP_ALIGN.CENTER)
        tb(s, cx + Inches(0.22), ct + Inches(0.92),
           cw3 - Inches(0.45), ch - Inches(1.1),
           desc, 13, TXT, align=PP_ALIGN.CENTER)
    wm(s, 'TRUST', sz=120, xr=0.28, yr=0.08, dark=True)
    print('  slide 13: Review Psychology ✓')
    return s

# ================================================================
# SLIDE 14: AIを活用した口コミ返信
# ================================================================
def make_ai_review():
    s = ns()
    bg_solid(s, OWHT)
    # 左ダークパネル（std_headerなし、独自レイアウト）
    gbox_rnd(s, 0, 0, W * 0.38, H, H_NVY, H_DK, ang=16200000, back=False)
    box(s, 0, H - BOT, W, BOT, T_DK, back=False)
    tb(s, Inches(0.3), Inches(0.35), W * 0.34, Inches(2.0),
       'AIを活用した\n口コミ返信', 30, WHT, bold=True)
    tb(s, Inches(0.3), Inches(2.55), W * 0.34, Inches(0.65),
       '口コミの返信文章に\n迷ったことはありませんか？',
       14, YLW)
    sep14 = s.shapes.add_shape(
        1, int(-Inches(0.2)), int(Inches(2.38)),
        int(W * 0.42), int(Inches(0.055)))
    sep14.fill.solid(); sep14.fill.fore_color.rgb = YLW
    sep14.line.fill.background()
    details = [
        'ボタン1つで返信文章を自動生成',
        'AIが口調を複数提案し、選ぶだけ',
        '返信の手間を削減し、コアに集中',
    ]
    for j, d in enumerate(details):
        tb(s, Inches(0.3), Inches(3.25) + Inches(0.6) * j,
           W * 0.34, Inches(0.52), f'▶ {d}', 12, WHT)
    badge(s, Inches(0.3), Inches(0.12), 'AI Reply', T_MD)
    # 右：3フィーチャーカード
    rx  = W * 0.40
    rw  = W - rx - MR
    feat14 = [
        ('🤖', 'AI生成返信',
         'ボタン1つで返信文章を自動生成\n口調・絵文字も自由にカスタマイズ可能'),
        ('⚡', 'スピード対応',
         '新着口コミをLINE通知で即キャッチ\n見逃しゼロで迅速な対応が可能に'),
        ('📊', '分析レポート',
         '口コミの傾向・評価推移を自動分析\n改善すべきポイントが一目でわかる'),
    ]
    fh = (H - BOT - Inches(0.25)) / 3
    for j, (icon, ftitle, fdesc) in enumerate(feat14):
        yt = Inches(0.12) + fh * j
        gbox_rnd(s, rx, yt + Inches(0.08), rw, fh - Inches(0.16),
                 H_DK, H_MD, ang=5400000)
        tb(s, rx + Inches(0.2), yt + Inches(0.18),
           rw - Inches(0.3), Inches(0.52),
           f'{icon}  {ftitle}', 18, WHT, bold=True)
        tb(s, rx + Inches(0.2), yt + Inches(0.75),
           rw - Inches(0.3), fh - Inches(1.0),
           fdesc, 13, RGBColor(0xC0, 0xE8, 0xE5))
    print('  slide 14: AI Review ✓')
    return s

# ================================================================
# SLIDE 15: 投稿は一気に準備できます
# ================================================================
def make_batch_post():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, '投稿は一気に準備できます', 'Auto Post', 'POST')
    # 上部アクセントバナー
    gbox_rnd(s, MR + SB_W, BODY_T + Inches(0.18),
             W - MR * 2 - SB_W, Inches(0.7),
             H_DK, H_MD, ang=5400000, back=False)
    tb(s, MR + SB_W + Inches(0.25), BODY_T + Inches(0.30),
       W - MR * 2 - SB_W - Inches(0.5), Inches(0.5),
       '"SNSの更新がなかなか続かない" — そんなオーナー様へ',
       15, WHT, bold=True)
    pcards = [
        ('AIで最適投稿を作成',
         '店舗情報・季節・イベントを踏まえた\n投稿文をAIが自動生成します。\n忙しいオーナー様の手間を大幅削減。',
         H_NVY, H_DK),
        ('1ヶ月分を一括予約',
         '投稿スケジュール機能を使えば\n一度に1ヶ月分の投稿を予約投稿可能。\nまとめて準備して後は自動更新。',
         H_DK, H_MD),
        ('写真・絵文字も自由',
         '口調・絵文字・写真の組み合わせを\n自由にカスタマイズ。\n店舗の個性を出した投稿が可能です。',
         H_MD, H_LT),
    ]
    cw4 = (W - MR * 2 - SB_W - Inches(0.3)) / 3
    bl4 = MR + SB_W + Inches(0.15)
    ct4 = BODY_T + Inches(1.05)
    ch4 = H - ct4 - BOT - Inches(0.45)
    for i, (ptitle, pdesc, g1, g2) in enumerate(pcards):
        cx = bl4 + cw4 * i
        gbox_rnd(s, cx, ct4, cw4 - Inches(0.15), ch4, g1, g2,
                 ang=16200000)
        tb(s, cx + Inches(0.15), ct4 + Inches(0.2),
           cw4 - Inches(0.32), Inches(0.6),
           ptitle, 16, WHT, bold=True)
        tb(s, cx + Inches(0.15), ct4 + Inches(0.9),
           cw4 - Inches(0.32), ch4 - Inches(1.1),
           pdesc, 13, WHT)
    tb(s, MR + SB_W, H - Inches(0.58), W - MR * 2, Inches(0.45),
       '弊社のMEO対策は、オーナー様の手間を最大限お手伝いします。',
       14, T_DK, bold=True, align=PP_ALIGN.CENTER)
    print('  slide 15: Batch Post ✓')
    return s

# ================================================================
# SLIDE 16: 継続的な管理が順位を守る
# ================================================================
def make_continuous():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, '継続的な管理が順位を守る', 'Continuous', '∞')
    pts16 = [
        ('月次アクション管理',
         '毎月の投稿計画・口コミ対応・\nプロフィール更新をカレンダーで管理。\n抜け漏れなく継続できます。',
         H_DK, H_MD),
        ('アルゴリズム対応',
         'Googleのアップデートを\n常時モニタリングし、\n最適な設定に随時調整します。',
         H_MD, H_LT),
        ('競合モニタリング',
         '競合店舗の順位・口コミ動向を\n定期チェック。\n差別化戦略を継続的に提案します。',
         H_LT, H_XL),
    ]
    cw5 = (W - MR * 2 - SB_W - Inches(0.3)) / 3
    bl5 = MR + SB_W + Inches(0.15)
    ct5 = BODY_T + Inches(0.25)
    ch5 = H - ct5 - BOT - Inches(0.85)
    for i, (ptitle, pdesc, g1, g2) in enumerate(pts16):
        cx = bl5 + cw5 * i
        gbox_rnd(s, cx, ct5, cw5 - Inches(0.15), ch5, g1, g2,
                 ang=16200000)
        tb(s, cx + Inches(0.15), ct5 + Inches(0.22),
           cw5 - Inches(0.32), Inches(0.62),
           ptitle, 17, WHT, bold=True)
        tb(s, cx + Inches(0.15), ct5 + Inches(0.95),
           cw5 - Inches(0.32), ch5 - Inches(1.1),
           pdesc, 13, WHT)
    tb(s, MR + SB_W, H - Inches(0.65), W - MR * 2, Inches(0.52),
       '一度上がった順位を守るには、継続的な専門知識と管理が不可欠です。',
       14, TXMD, bold=True, align=PP_ALIGN.CENTER)
    print('  slide 16: Continuous ✓')
    return s

# ================================================================
# SLIDE 17: 目に見える、閲覧数の増加
# ================================================================
def make_metrics():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, '目に見える、閲覧数の増加 – 成長するMEO対策', 'Analytics', 'UP')
    tb(s, MR + SB_W + Inches(0.1), BODY_T + Inches(0.18),
       W * 0.58, Inches(0.5),
       'キーワードが上位でも、閲覧数が増えなければ意味がありません', 13, TXMD)
    # 左説明カード
    gbox_rnd(s, MR + SB_W + Inches(0.1), BODY_T + Inches(0.82),
             W * 0.33, H - BODY_T - BOT - Inches(1.22),
             H_DK, H_MD, ang=16200000, back=False)
    tb(s, MR + SB_W + Inches(0.28), BODY_T + Inches(1.0),
       W * 0.28, Inches(0.6), '成長するMEO対策', 18, YLW, bold=True)
    tb(s, MR + SB_W + Inches(0.28), BODY_T + Inches(1.72),
       W * 0.28, Inches(3.0),
       '毎月の閲覧数をグラフ化し、\n前年と比較することで成長を可視化。\n\nオーナー様の「本当に効果があるのか？」\nという不安に、データで答えます。\n\n弊社MEO対策に自信があるからこそ、\n積み重なった実績をお見せできます。',
       12, WHT)
    # 右バーチャート
    rx   = MR + SB_W + W * 0.38
    rw17 = W - rx - MR
    months = ['1月','2月','3月','4月','5月','6月',
              '7月','8月','9月','10月','11月','12月']
    cy_v = [0.40,0.45,0.50,0.55,0.60,0.65,
            0.70,0.72,0.78,0.85,0.92,1.00]
    py_v = [0.25,0.28,0.32,0.35,0.38,0.40,
            0.43,0.45,0.48,0.50,0.53,0.55]
    mh   = H - BODY_T - BOT - Inches(1.5)
    bt17 = H - BOT - Inches(0.42)
    bw   = rw17 / 12 - Inches(0.04)
    for k, (m, cy, py) in enumerate(zip(months, cy_v, py_v)):
        bx = rx + (rw17 / 12) * k
        by_cy = bt17 - mh * cy
        gbox(s, bx, by_cy, bw, mh * cy, H_MD, H_LT,
             ang=16200000, back=False)
        ph = mh * py
        gbox(s, bx, bt17 - ph, bw * 0.45, ph,
             H_NVY, H_DK, ang=16200000, back=False)
        tb(s, bx - Inches(0.08), bt17 + Inches(0.02),
           bw + Inches(0.18), Inches(0.32),
           m, 8, TXMD, align=PP_ALIGN.CENTER)
    # 前年比ライン
    py_line_y = bt17 - mh * 0.48
    box(s, rx, py_line_y, rw17, Inches(0.025), YLW, back=False)
    tb(s, rx + rw17 * 0.62, py_line_y - Inches(0.25),
       Inches(1.0), Inches(0.3), '前年比', 10, YLW)
    print('  slide 17: Metrics ✓')
    return s

# ================================================================
# SLIDE 18: キーワード別の順位チェック
# ================================================================
def make_ranking():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, 'キーワード別の順位チェック', 'Ranking', '#1')
    tb(s, MR + SB_W + Inches(0.1), BODY_T + Inches(0.18),
       W * 0.6, Inches(0.48),
       '検索キーワードごとに順位を可視化し、戦略的にMEO対策を実施します', 13, TXMD)
    keywords = [
        ('1位', '近くの美容院',     '月間2万回検索'),
        ('2位', '渋谷 カフェ',      '月間1,258回検索'),
        ('3位', '新宿 ランチ',      '月間883回検索'),
        ('4位', '池袋 居酒屋',      '月間856回検索'),
        ('5位', '品川 restaurants', '月間792回検索'),
    ]
    rh18 = (H - BODY_T - BOT - Inches(0.85)) / 5
    for j, (rank, kw, vol) in enumerate(keywords):
        yt = BODY_T + Inches(0.75) + rh18 * j
        # ランク数値（numblock風）
        gbox_rnd(s, MR + SB_W + Inches(0.1), yt + Inches(0.06),
                 Inches(0.7), rh18 - Inches(0.12),
                 H_DK, H_MD, ang=5400000)
        tb(s, MR + SB_W + Inches(0.12), yt + Inches(0.1),
           Inches(0.66), rh18 - Inches(0.2),
           rank, 18, YLW, bold=True, align=PP_ALIGN.CENTER)
        # キーワード
        tb(s, MR + SB_W + Inches(1.0), yt + Inches(0.1),
           W * 0.38, rh18 - Inches(0.2),
           kw, 17, TXT, bold=True)
        # 検索ボリューム
        bw18 = (W - MR * 2 - SB_W - Inches(1.0)) * 0.55
        gbox(s, MR + SB_W + Inches(1.0) + W * 0.40,
             yt + rh18 * 0.25, bw18 * (6 - j) / 6,
             rh18 * 0.5, H_MD, H_LT, ang=5400000, back=False)
        tb(s, W - MR - Inches(1.5), yt + Inches(0.08),
           Inches(1.4), rh18 - Inches(0.18),
           vol, 11, TXMD, align=PP_ALIGN.RIGHT)
    print('  slide 18: Ranking ✓')
    return s

# ================================================================
# SLIDE 19: 電話・ルート検索・来店数の変化
# ================================================================
def make_action_change():
    s = ns()
    bg_solid(s, T_DK)
    box(s, 0, 0, W, Inches(0.07), YLW, back=False)
    box(s, 0, H - Inches(0.07), W, Inches(0.07), YLW, back=False)
    badge(s, W - Inches(2.1), Inches(0.14), 'Action UP', YLW)
    tb(s, MR, Inches(0.18), W - MR * 2, Inches(0.82),
       '電話・ルート検索・来店数の変化',
       34, WHT, bold=True, align=PP_ALIGN.CENTER)
    tb(s, MR, Inches(1.06), W - MR * 2, Inches(0.52),
       '信頼できる店舗になることで、お客様からのアクションが劇的に増加します',
       15, YLW, align=PP_ALIGN.CENTER)
    metrics19 = [
        ('📞', '電話問い合わせ', '上位表示で\nタップして通話が急増', '+180%'),
        ('🗺', 'ルート検索',   '来店意欲の高い\nユーザーがルート案内開始', '+220%'),
        ('👥', '来店客数',     '口コミ・写真が\n来店の後押しに', '+150%'),
        ('🌐', 'WEBサイト誘導', 'プロフィールからの\nクリックが増加', '+130%'),
    ]
    mw19 = (W - MR * 2) / 4
    for i, (icon, title, desc, pct) in enumerate(metrics19):
        cx = MR + mw19 * i
        box(s, cx + Inches(0.12), Inches(1.85), mw19 - Inches(0.24),
            H - Inches(2.35), WHT, rnd=True, back=False)
        tb(s, cx + Inches(0.22), Inches(1.96),
           mw19 - Inches(0.44), Inches(0.62),
           icon, 28, T_MD, align=PP_ALIGN.CENTER)
        tb(s, cx + Inches(0.22), Inches(2.62),
           mw19 - Inches(0.44), Inches(0.52),
           title, 14, TXT, bold=True, align=PP_ALIGN.CENTER)
        tb(s, cx + Inches(0.22), Inches(3.22),
           mw19 - Inches(0.44), Inches(0.95),
           desc, 12, TXMD, align=PP_ALIGN.CENTER)
        # 大型パーセント数値（44pt）
        tb(s, cx + Inches(0.15), Inches(4.25),
           mw19 - Inches(0.3), Inches(0.88),
           pct, 44, ORG, bold=True, align=PP_ALIGN.CENTER)
        tb(s, cx + Inches(0.22), Inches(5.12),
           mw19 - Inches(0.44), Inches(0.35),
           '平均増加率（参考値）', 10, TXMD, align=PP_ALIGN.CENTER)
    wm(s, 'UP', sz=130, xr=0.32, yr=0.08, dark=True)
    print('  slide 19: Action Change ✓')
    return s

# ================================================================
# SLIDE 20: グラフで分かる、1年間の成長
# ================================================================
def make_year_growth():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, 'グラフで分かる、1年間の成長', 'Growth', 'GROW')
    tb(s, MR + SB_W + Inches(0.1), BODY_T + Inches(0.15),
       W * 0.55, Inches(0.52),
       '3年以上伸び続けているのか？MEO対策の効果が出ているのか？', 13, TXMD)
    gbox_rnd(s, MR + SB_W + Inches(0.1), BODY_T + Inches(0.85),
             W * 0.40, H - BODY_T - BOT - Inches(1.2),
             H_DK, H_MD, ang=16200000, back=False)
    tb(s, MR + SB_W + Inches(0.28), BODY_T + Inches(1.0),
       W * 0.36, Inches(0.65), '毎月の閲覧数をグラフ化\n前年と比較して成長を可視化',
       17, YLW, bold=True)
    tb(s, MR + SB_W + Inches(0.28), BODY_T + Inches(1.82),
       W * 0.36, Inches(3.5),
       '毎月の閲覧数をグラフ化し、\n前年と比較することで成長を可視化。\n\nオーナー様の「本当に効果があるのか？」\nという不安に、データで答えます。\n\n弊社MEO対策に自信があるからこそ、\n積み重なった実績をお見せできます。',
       12, WHT)
    rx20  = MR + SB_W + W * 0.46
    rw20  = W - rx20 - MR
    months20 = ['1月','2月','3月','4月','5月','6月',
                '7月','8月','9月','10月','11月','12月']
    cy20 = [0.40,0.45,0.50,0.55,0.60,0.65,
            0.70,0.72,0.78,0.85,0.92,1.00]
    mh20 = H - BODY_T - BOT - Inches(1.5)
    bt20 = H - BOT - Inches(0.42)
    bw20 = rw20 / 12 - Inches(0.03)
    for k, (m, cy) in enumerate(zip(months20, cy20)):
        bx = rx20 + (rw20 / 12) * k
        by = bt20 - mh20 * cy
        gbox(s, bx, by, bw20, mh20 * cy, H_MD, H_LT,
             ang=16200000, back=False)
        tb(s, bx - Inches(0.06), bt20 + Inches(0.02),
           bw20 + Inches(0.14), Inches(0.3),
           m, 7, TXMD, align=PP_ALIGN.CENTER)
    print('  slide 20: Year Growth ✓')
    return s

# ================================================================
# SLIDE 21: 導入前後の比較イメージ
# ================================================================
def make_before_after():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, '導入前後の比較イメージ', 'Before / After', '→')
    half21 = (W - SB_W - Inches(0.35)) / 2
    bl21   = SB_W + Inches(0.2)
    ct21   = BODY_T + Inches(0.18)
    ch21   = H - BODY_T - BOT - Inches(0.55)
    # BEFORE（グレー）
    box(s, bl21, ct21, half21 - Inches(0.15), ch21, LGR, rnd=True, back=False)
    tb(s, bl21 + Inches(0.2), ct21 + Inches(0.2),
       half21 - Inches(0.5), Inches(0.62),
       'BEFORE', 24, TXMD, bold=True)
    befores = ['Googleマップを知らない客しか来ない',
               '口コミがなく新規客が来店しない',
               '競合店に検索で負けている',
               '写真が少なく魅力が伝わらない',
               '情報が古いまま放置されている']
    for j, t_ in enumerate(befores):
        tb(s, bl21 + Inches(0.25),
           ct21 + Inches(1.05) + Inches(0.62) * j,
           half21 - Inches(0.5), Inches(0.58),
           f'×  {t_}', 14, TXMD)
    # AFTER（グラデーション）
    rx21 = bl21 + half21 + Inches(0.15)
    gbox_rnd(s, rx21, ct21, half21 - Inches(0.15), ch21,
             H_DK, H_MD, ang=16200000)
    tb(s, rx21 + Inches(0.2), ct21 + Inches(0.2),
       half21 - Inches(0.5), Inches(0.62),
       'AFTER', 24, YLW, bold=True)
    afters = ['Googleマップを見て来ました！の声が増加',
              '高評価口コミで新規客が続々来店',
              '検索TOP3に入り競合に差をつける',
              '魅力的な写真で来店意欲が高まる',
              '最新情報で信頼感が格段に向上']
    for j, t_ in enumerate(afters):
        tb(s, rx21 + Inches(0.25),
           ct21 + Inches(1.05) + Inches(0.62) * j,
           half21 - Inches(0.5), Inches(0.58),
           f'◎  {t_}', 14, WHT)
    print('  slide 21: Before/After ✓')
    return s

# ================================================================
# SLIDE 22: なぜ安い業者では駄目なのか
# ================================================================
def make_why_not_cheap():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, 'なぜ安い業者では駄目なのか', 'Why Premium', 'WHY')
    reasons = [
        ('アルゴリズムは常に変化する',
         'Googleのアルゴリズムは頻繁に更新されます。\n安価な業者は最新動向への対応が遅く、\n一時的な効果しか得られないことがほとんどです。',
         '時間だけ取られ、成果が出ない'),
        ('本業との両立が困難',
         '継続的なMEO運用には専門知識と\n毎日の管理工数が必要です。\n自社対応では本業に支障が出てしまいます。',
         '結果、MEOが止まってしまう'),
        ('継続的な知見・実績が必要',
         '成功するMEO対策は経験と\n蓄積データに基づく戦略が不可欠です。\n低コストでは必要なサポートが得られません。',
         '積み重ねのないMEOに意味はない'),
    ]
    cw22 = (W - MR * 2 - SB_W - Inches(0.3)) / 3
    bl22 = MR + SB_W + Inches(0.15)
    ct22 = BODY_T + Inches(0.22)
    ch22 = H - ct22 - BOT - Inches(0.55)
    for i, (ttl, desc, btm) in enumerate(reasons):
        cx = bl22 + cw22 * i
        gbox_rnd(s, cx, ct22, cw22 - Inches(0.15), ch22,
                 H_DK, H_MD, ang=16200000)
        tb(s, cx + Inches(0.15), ct22 + Inches(0.18),
           cw22 - Inches(0.32), Inches(0.62),
           ttl, 16, WHT, bold=True)
        tb(s, cx + Inches(0.15), ct22 + Inches(0.92),
           cw22 - Inches(0.32), Inches(2.5),
           desc, 12, WHT)
        tb(s, cx + Inches(0.15), ct22 + ch22 - Inches(0.65),
           cw22 - Inches(0.32), Inches(0.58),
           btm, 12, YLW, bold=True)
    print('  slide 22: Why Not Cheap ✓')
    return s

# ================================================================
# SLIDE 23: 弊社MEO対策の特長・メリット
# ================================================================
def make_plan_benefits():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, f'弊社MEO対策の特長・メリット', 'Our Plan', 'PLAN')
    benefits = [
        ('📊', '完全可視化レポート',
         'カレンダー・グラフで\n毎月の成果を数値で報告。\n「効果が見えない」を解消します。'),
        ('🤖', 'AI投稿し放題',
         'AIで投稿文を自動生成。\nキーワード戦略も含めて\n最適な投稿を量産できます。'),
        ('📅', '1ヶ月一括予約',
         '投稿スケジュールを\n一括で予約可能。\n運用の手間を最小化します。'),
        ('🔔', 'LINE即時通知',
         '新着口コミをLINEで即通知。\n見逃しゼロで\n迅速な返信対応が可能に。'),
        ('🔍', 'キーワード戦略',
         '業種＋地域キーワードを\n複数軸で分析し\n上位表示を狙います。'),
        ('💬', 'AI口コミ返信',
         'ボタン1つで返信文を自動生成。\n口調・絵文字も\n自由にカスタマイズ可能。'),
    ]
    cw23 = (W - MR * 2 - SB_W - Inches(0.3)) / 3
    bl23 = MR + SB_W + Inches(0.15)
    rows = 2
    rh23 = (H - BODY_T - BOT - Inches(0.55)) / rows
    for i, (icon, ttl, desc) in enumerate(benefits):
        col = i % 3; row = i // 3
        cx = bl23 + cw23 * col
        yt = BODY_T + Inches(0.18) + rh23 * row
        gbox_rnd(s, cx, yt, cw23 - Inches(0.15), rh23 - Inches(0.15),
                 H_DK if row == 0 else H_MD,
                 H_MD if row == 0 else H_LT,
                 ang=16200000)
        tb(s, cx + Inches(0.18), yt + Inches(0.18),
           cw23 - Inches(0.35), Inches(0.55),
           f'{icon}  {ttl}', 15, WHT, bold=True)
        tb(s, cx + Inches(0.18), yt + Inches(0.82),
           cw23 - Inches(0.35), rh23 - Inches(1.0),
           desc, 12, WHT)
    print('  slide 23: Plan Benefits ✓')
    return s

# ================================================================
# SLIDE 24: MEO対策で期待できる成果
# ================================================================
def make_outcomes():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, 'MEO対策で期待できる成果', 'Outcome', 'GOAL')
    goals = [
        ('TOP 3', '以内表示',        '検索露出',   '地域キーワードで上位獲得'),
        ('3倍',   'のビュー数増加',   '認知拡大',   '月間閲覧数が平均3倍に'),
        ('2倍',   'の来店アクション', '集客強化',   '電話・ルート検索が急増'),
        ('★4.0',  '以上の維持',       '信頼構築',   '口コミ管理で評価を維持'),
    ]
    cw24 = (W - MR * 2 - SB_W - Inches(0.3)) / 2
    bl24 = MR + SB_W + Inches(0.15)
    rows = 2
    rh24 = (H - BODY_T - BOT - Inches(0.45)) / rows
    for i, (num, unit, lbl, desc) in enumerate(goals):
        col = i % 2; row = i // 2
        cx = bl24 + cw24 * col
        yt = BODY_T + Inches(0.18) + rh24 * row
        numblock(s, cx, yt, cw24 - Inches(0.15), rh24 - Inches(0.18),
                 num, unit, lbl)
        tb(s, cx + Inches(0.15), yt + rh24 - Inches(0.72),
           cw24 - Inches(0.35), Inches(0.58),
           desc, 12, RGBColor(0xA0, 0xD6, 0xD4), align=PP_ALIGN.CENTER)
    print('  slide 24: Outcomes ✓')
    return s

# ================================================================
# SLIDE 25: 他社MEOとの圧倒的な違い（比較表）
# ================================================================
def make_comparison_table():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, '他社MEOとの圧倒的な違い', 'Compare', 'VS')
    rows25 = [
        ('比較項目',    '他社MEO対策',                      '当社MEO対策',                       True),
        ('可視化・透明性', '✕  不透明・レポート提出のみ',    '◎  完全可視化（カレンダー・グラフ）', False),
        ('戦略性・運用', '△  作業重視（投稿代行がメイン）',  '◎  AIで投稿し放題・キーワード戦略',  False),
        ('AIの精度',    '△  簡易な文章のみ',                '◎  絵文字・口調など自由に選択可',    False),
        ('投稿予約機能', '✕  予約機能なし',                  '◎  あり。1ヶ月分の投稿予約も可',    False),
        ('LINE通知機能', '✕  通知機能なし',                  '◎  あり。新着口コミにすぐ対応可',   False),
    ]
    tl  = MR + SB_W + Inches(0.15)
    tw  = W - tl - MR
    c1  = tw * 0.25
    c2  = tw * 0.375
    c3  = tw * 0.375
    rh25 = (H - BODY_T - BOT - Inches(0.28)) / len(rows25)
    for i, (item, other, ours, is_hdr) in enumerate(rows25):
        ry = BODY_T + Inches(0.14) + rh25 * i
        if is_hdr:
            gbox(s, tl, ry, c1, rh25 - Inches(0.03),
                 H_NVY, H_DK, ang=5400000, back=False)
            gbox(s, tl + c1, ry, c2, rh25 - Inches(0.03),
                 H_NVY, H_DK, ang=5400000, back=False)
            gbox(s, tl + c1 + c2, ry, c3, rh25 - Inches(0.03),
                 H_DK, H_MD, ang=5400000, back=False)
        else:
            box(s, tl, ry, c1, rh25 - Inches(0.03), OWHT, back=False)
            box(s, tl + c1, ry, c2, rh25 - Inches(0.03),
                RGBColor(0xFF, 0xF2, 0xF0), back=False)
            box(s, tl + c1 + c2, ry, c3, rh25 - Inches(0.03),
                RGBColor(0xE8, 0xF8, 0xF0), back=False)
        for j, (text, cx, cw) in enumerate([
            (item,  tl,          c1),
            (other, tl + c1,     c2),
            (ours,  tl + c1 + c2, c3),
        ]):
            tc25 = (WHT if is_hdr
                    else (YLW if j == 2 else TXT))
            tb(s, cx + Inches(0.1), ry + Inches(0.06),
               cw - Inches(0.2), rh25 - Inches(0.12),
               text, 13 if not is_hdr else 14,
               tc25, bold=(is_hdr or j == 2))
    print('  slide 25: Comparison Table ✓')
    return s

# ================================================================
# SLIDE 26: まとめ / CTA
# ================================================================
def make_cta():
    s = ns()
    bg_solid(s, T_DK)
    box(s, 0, 0, W, Inches(0.07), YLW, back=False)
    box(s, 0, H - Inches(0.07), W, Inches(0.07), YLW, back=False)
    box(s, 0, 0, Inches(0.1), H, NVY, back=False)
    badge(s, W - Inches(2.1), Inches(0.14), SVC_NAME[:12], YLW)
    tb(s, MR, Inches(0.22), W - MR * 2, Inches(0.88),
       'なぜ今、MEO対策なのか',
       32, YLW, bold=True, align=PP_ALIGN.CENTER)
    box(s, MR, Inches(1.15), W - MR * 2, Inches(0.055), WHT, back=False)
    points26 = [
        '✓  スマートフォン検索の約78%がGoogleを使用',
        '✓  「近くの○○」検索は年々増加し続けている',
        '✓  Googleマップ上位表示 = 24時間365日自動集客',
        '✓  競合他社がMEO対策を始める前に先行優位を確立',
    ]
    for i, p in enumerate(points26):
        tb(s, MR + Inches(0.8), Inches(1.42) + Inches(0.72) * i,
           W - MR * 2 - Inches(0.8), Inches(0.65),
           p, 17, WHT, bold=(i == 3))
    # 中央CTAボックス
    gbox_rnd(s, MR * 2, H * 0.695, W - MR * 4, H * 0.22,
             H_NVY, H_DK, ang=5400000)
    tb(s, MR * 2 + Inches(0.3), H * 0.715, W - MR * 4 - Inches(0.6),
       H * 0.09,
       '今すぐ無料相談 — 貴店に最適なMEO戦略をご提案します',
       22, YLW, bold=True, align=PP_ALIGN.CENTER)
    tb(s, MR * 2 + Inches(0.3), H * 0.815, W - MR * 4 - Inches(0.6),
       H * 0.07, CONTACT, 14, WHT, align=PP_ALIGN.CENTER)
    wm(s, 'NOW', sz=120, xr=0.28, yr=0.08, dark=True)
    print('  slide 26: CTA ✓')
    return s

# ================================================================
# SLIDE 27: クロージング
# ================================================================
def make_closing():
    s = ns()
    bg_solid(s, NVY)
    box(s, 0, 0, Inches(0.45), H, T_MD, back=False)
    box(s, 0, H - Inches(0.1), W, Inches(0.1), YLW, back=False)
    box(s, 0, 0, W, Inches(0.07), T_LT, back=False)
    # 微斜めゴールドライン
    sep27 = s.shapes.add_shape(
        1, int(-Inches(0.2)), int(H * 0.38),
        int(W * 0.55 + Inches(0.4)), int(Inches(0.055)))
    sep27.fill.solid(); sep27.fill.fore_color.rgb = YLW
    sep27.line.fill.background(); sep27.rotation = -1.0
    tb(s, Inches(0.65), Inches(0.35), W * 0.60, Inches(1.3),
       'ご清聴ありがとうございました', 36, WHT, bold=True)
    tb(s, Inches(0.65), Inches(2.0), W * 0.52, Inches(0.52),
       f'MEO対策で、あなたのお店を\nGoogleマップのTOPへ', 18, T_XL)
    services27 = [
        '📍  Googleビジネスプロフィール最適化',
        '🤖  AIロコミ返信・投稿自動化',
        '📊  月次レポート・前年比グラフ',
        '🔔  LINE通知で即時対応サポート',
    ]
    for j, sv in enumerate(services27):
        tb(s, Inches(0.65), Inches(3.0) + Inches(0.62) * j,
           W * 0.52, Inches(0.55), sv, 14, T_XL)
    # 連絡先
    gbox_rnd(s, Inches(0.65), H * 0.82, W * 0.52, Inches(0.72),
             H_DK, H_MD, ang=5400000)
    tb(s, Inches(0.85), H * 0.84, W * 0.48, Inches(0.58),
       f'{COMPANY}  |  {CONTACT}', 13, WHT)
    print('  slide 27: Closing ✓')
    return s

# ================================================================
# MAIN
# ================================================================
print('Building slides...')
make_cover()
make_section_01()
make_customer_journey()
make_map_prominence()
make_revenue_driver()
make_map_actions()
make_comparison()
make_what_changes()
make_three_factors()
make_distance_area()
make_review_impact()
make_common_traits()
make_review_psychology()
make_ai_review()
make_batch_post()
make_continuous()
make_metrics()
make_ranking()
make_action_change()
make_year_growth()
make_before_after()
make_why_not_cheap()
make_plan_benefits()
make_outcomes()
make_comparison_table()
make_cta()
make_closing()

prs.save(OUTPUT)
print(f'\n✓ 保存完了: {OUTPUT}')
print(f'  スライド数: {len(prs.slides)}')
