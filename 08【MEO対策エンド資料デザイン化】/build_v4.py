"""
MEO対策エンド資料 - Complete Rebuild v4
参考資料カラー x テキスト流用 x 完全新規デザイン
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from pptx.oxml import parse_xml

OUTPUT = r'c:/Users/shira_k13727w/OneDrive/Desktop/クロード保管用/08【MEO対策エンド資料デザイン化】/MEO対策エンド資料_v4.pptx'

# ============================================================
# DESIGN SYSTEM  (参考資料の色をベースに)
# ============================================================
T_DK  = RGBColor(0x00, 0x5E, 0x6E)   # ダークティール
T_MD  = RGBColor(0x00, 0x9A, 0x9A)   # ミッドティール
T_LT  = RGBColor(0x00, 0xC4, 0xCC)   # ライトティール
T_XL  = RGBColor(0x3D, 0xD9, 0xE0)   # エクストラライト
YLW   = RGBColor(0xF5, 0xC0, 0x00)   # イエロー
ORG   = RGBColor(0xFF, 0x88, 0x00)   # オレンジ
NVY   = RGBColor(0x0A, 0x18, 0x2C)   # ネイビー
WHT   = RGBColor(0xFF, 0xFF, 0xFF)
OWHT  = RGBColor(0xF0, 0xF6, 0xF9)   # オフホワイト
TXT   = RGBColor(0x12, 0x22, 0x34)   # ダークテキスト
TXMD  = RGBColor(0x44, 0x58, 0x6C)   # ミッドテキスト
LGR   = RGBColor(0xC4, 0xD8, 0xE4)   # ライトグレー

H_DK  = '005E6E'
H_MD  = '009A9A'
H_LT  = '00C4CC'
H_XL  = '3DD9E0'
H_NVY = '0A182C'

# ============================================================
# SLIDE SETUP
# ============================================================
prs = Presentation()
prs.slide_width  = Inches(13.33)
prs.slide_height = Inches(7.5)
BL = prs.slide_layouts[6]   # blank

W = prs.slide_width
H = prs.slide_height

def ns(): return prs.slides.add_slide(BL)

# ============================================================
# PRIMITIVES
# ============================================================
def bg_solid(s, c):
    f = s.background.fill; f.solid(); f.fore_color.rgb = c

def bg_grad(s, h1, h2, ang=0):
    bg = s.background
    bgPr = bg._element.find(qn('p:bgPr'))
    if bgPr is None:
        bgPr = parse_xml('<p:bgPr xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>')
        bg._element.append(bgPr)
    for c in list(bgPr): bgPr.remove(c)
    bgPr.append(parse_xml(
        f'<a:gradFill xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        f'<a:gsLst><a:gs pos="0"><a:srgbClr val="{h1}"/></a:gs>'
        f'<a:gs pos="100000"><a:srgbClr val="{h2}"/></a:gs></a:gsLst>'
        f'<a:lin ang="{ang}" scaled="0"/></a:gradFill>'
    ))

def _push_back(s, el):
    t = s.shapes._spTree; t.remove(el); t.insert(2, el)

def box(s, l, t, w, h, c, back=True, rnd=False):
    sh = s.shapes.add_shape(5 if rnd else 1, int(l), int(t), int(w), int(h))
    sh.fill.solid(); sh.fill.fore_color.rgb = c
    sh.line.fill.background()
    if back: _push_back(s, sh._element)
    return sh

def gbox(s, l, t, w, h, h1, h2, ang=0, back=True):
    sh = s.shapes.add_shape(1, int(l), int(t), int(w), int(h))
    sh.line.fill.background()
    sp = sh._element
    spPr = sp.find(qn('p:spPr'))
    for c in list(spPr):
        if any(c.tag.endswith(x) for x in ['solidFill','gradFill','noFill','blipFill','pattFill']):
            spPr.remove(c)
    spPr.insert(0, parse_xml(
        f'<a:gradFill xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        f'<a:gsLst><a:gs pos="0"><a:srgbClr val="{h1}"/></a:gs>'
        f'<a:gs pos="100000"><a:srgbClr val="{h2}"/></a:gs></a:gsLst>'
        f'<a:lin ang="{ang}" scaled="0"/></a:gradFill>'
    ))
    if back: _push_back(s, sp)
    return sh

def oval(s, l, t, w, h, c, back=False):
    sh = s.shapes.add_shape(9, int(l), int(t), int(w), int(h))
    sh.fill.solid(); sh.fill.fore_color.rgb = c
    sh.line.fill.background()
    if back: _push_back(s, sh._element)
    return sh

def tb(s, l, t, w, h, text, sz, c, bold=False, align=PP_ALIGN.LEFT, wrap=True):
    tx = s.shapes.add_textbox(int(l), int(t), int(w), int(h))
    tf = tx.text_frame; tf.word_wrap = wrap
    lines = str(text).split('\n')
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        r = p.add_run(); r.text = ln
        r.font.size = Pt(sz); r.font.bold = bold; r.font.color.rgb = c
    return tx

def shape_text(sh, text, sz, c, bold=False, align=PP_ALIGN.CENTER):
    tf = sh.text_frame; tf.word_wrap = True
    tf.paragraphs[0].alignment = align
    r = tf.paragraphs[0].add_run()
    r.text = text; r.font.size = Pt(sz)
    r.font.bold = bold; r.font.color.rgb = c

# ============================================================
# LAYOUT CONSTANTS
# ============================================================
MR   = Inches(0.55)          # 左マージン
HDR  = Inches(1.45)          # ヘッダー高さ
YL_H = Inches(0.055)         # イエローライン高さ
SB_W = Inches(0.07)          # サイドバー幅
BOT  = Inches(0.07)          # ボトムライン高さ
BODY_T = HDR + YL_H          # ボディ開始Y

def std_header(s, title):
    """標準ヘッダー帯（グラデーション＋イエローライン）"""
    gbox(s, 0, 0, W, HDR, H_DK, H_MD, ang=0)
    box(s, 0, HDR, W, YL_H, YLW)
    box(s, 0, BODY_T, SB_W, H - BODY_T - BOT, T_MD)
    box(s, 0, H - BOT, W, BOT, T_MD)
    tb(s, MR, Inches(0.28), W - MR - Inches(0.3), HDR - Inches(0.28),
       title, 28, WHT, bold=True)

# ============================================================
# SLIDE 01: COVER
# ============================================================
def make_cover():
    s = ns()
    bg_solid(s, NVY)
    # Z-order: back=False で追加順に積み上げ、gboxを最後にback=Trueで最背面へ
    # 左ティールアクセントバー
    box(s, 0, 0, Inches(0.12), H, T_MD, back=False)
    # 下部ホワイトパネル
    box(s, 0, H*0.72, W, H*0.28, WHT, back=False)
    # イエローセパレーター
    box(s, 0, H*0.70, W, Inches(0.065), YLW, back=False)
    # 右上装飾サークル（テキストより背面）
    oval(s, W*0.66, -Inches(1.0), Inches(4.5), Inches(4.5), T_XL)
    # テキスト
    tb(s, Inches(0.55), H*0.07, W*0.62, H*0.47,
       'MEO対策で\n集客力を最大化する', 50, WHT, bold=True)
    tb(s, Inches(0.55), H*0.52, W*0.62, H*0.16,
       'Googleマップ集客で、売上が上がる、選ばれるお店に', 20, YLW, bold=True)
    tb(s, Inches(0.55), H*0.745, W*0.58, H*0.08,
       'MEO対策 / Googleビジネスプロフィール最適化', 13, TXMD)
    tb(s, Inches(0.55), H*0.835, W*0.58, H*0.10,
       '検索上位獲得で、見込み客を自動集客', 16, TXT, bold=True)
    # 右グラデーションパネル — 最後にback=Trueで最背面（index 2）へ
    gbox(s, W*0.42, 0, W*0.58, H, H_MD, H_XL, ang=5400000)
    print('  slide 01: Cover ✓')
    return s

# ============================================================
# SLIDE 02: SECTION — Googleマップ戦略
# ============================================================
def make_section_01():
    s = ns()
    bg_solid(s, NVY)
    box(s, 0, 0, Inches(0.45), H, T_MD)
    box(s, W*0.62, 0, W*0.38, H, RGBColor(0x0E, 0x22, 0x38))
    box(s, Inches(0.45), H*0.50, W - Inches(0.45), Inches(0.05), YLW)
    # セクション番号
    tb(s, W*0.63, H*0.08, W*0.35, H*0.55, '01', 100, T_MD, bold=True, align=PP_ALIGN.CENTER)
    # 説明テキスト
    tb(s, Inches(0.65), H*0.18, W*0.55, H*0.20,
       '検索のメインがスマートフォンの今\n店舗集客の最短は', 18, T_XL)
    # メイン見出し
    tb(s, Inches(0.65), H*0.40, W*0.55, H*0.45,
       'Googleマップ戦略\nで勝つこと', 40, WHT, bold=True)
    print('  slide 02: Section ✓')
    return s

# ============================================================
# SLIDE 03: 今、MEO対策が必要な理由（カスタマージャーニー）
# ============================================================
def make_customer_journey():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, '今、MEO対策が必要な理由 ─ お客様はこうしてお店を選んでいます')
    # 4ステップ
    steps = [('01\n検索', 'スマートフォンで\n地域＋業種を検索'),
             ('02\n比較', '写真や★評価で\n複数店舗を比較'),
             ('03\n決定', '口コミを読んで\n来店店舗を決定'),
             ('04\n行動', 'ルート検索・電話で\n来店行動')]
    col_w = (W - MR*2 - SB_W) / 4
    base_l = MR + SB_W + Inches(0.15)
    base_t = BODY_T + Inches(0.25)
    for i, (step, desc) in enumerate(steps):
        cx = base_l + col_w * i
        # カード背景
        c_bg = T_DK if i % 2 == 0 else T_MD
        box(s, cx, base_t, col_w - Inches(0.18), H - BODY_T - BOT - Inches(0.45),
            c_bg, rnd=True)
        # 番号＋ラベル
        tb(s, cx + Inches(0.1), base_t + Inches(0.15), col_w - Inches(0.35),
           Inches(1.1), step, 22, YLW, bold=True, align=PP_ALIGN.CENTER)
        # 説明
        tb(s, cx + Inches(0.1), base_t + Inches(1.3), col_w - Inches(0.35),
           Inches(1.4), desc, 15, WHT, align=PP_ALIGN.CENTER)
        # 矢印 (最後以外)
        if i < 3:
            box(s, cx + col_w - Inches(0.15), base_t + Inches(1.0),
                Inches(0.15), Inches(0.4), YLW)
    # フッターメッセージ
    box(s, MR + SB_W, H - Inches(0.62), W - MR*2, Inches(0.45), T_DK, rnd=True)
    tb(s, MR + SB_W + Inches(0.2), H - Inches(0.60), W - MR*2 - Inches(0.4),
       Inches(0.42), 'これら全て、Googleマップだけで完結します！', 18, YLW, bold=True,
       align=PP_ALIGN.CENTER)
    print('  slide 03: Customer Journey ✓')
    return s

# ============================================================
# SLIDE 04: 検索結果で最も目立つ場所（スプリットレイアウト）
# ============================================================
def make_map_prominence():
    s = ns()
    bg_solid(s, OWHT)
    # 左ティールパネル (40%)
    gbox(s, 0, 0, W*0.40, H, H_DK, H_MD, ang=5400000)
    # イエロー縦ライン
    box(s, W*0.40, 0, Inches(0.06), H, YLW)
    # 右パネル背景
    box(s, W*0.40 + Inches(0.06), 0, W*0.60, H, OWHT)
    # 左：タイトル
    tb(s, Inches(0.35), Inches(0.3), W*0.38, Inches(1.8),
       '検索結果で\n最も目立つ場所', 34, WHT, bold=True)
    tb(s, Inches(0.35), Inches(2.2), W*0.38, Inches(0.6),
       'それが、Googleマップです', 17, YLW, bold=True)
    # 左：説明
    tb(s, Inches(0.35), Inches(3.0), W*0.38, Inches(3.5),
       '検索画面の上から順に\n\n  ① 広告枠（リスティング）\n  ② 地図枠＝ローカルパック\n  ③ 自然検索枠\n\nGoogleマップは最上位の\n"目立つゾーン"を占有します', 14, WHT)
    # 右：キーメッセージ
    tb(s, W*0.43, Inches(1.2), W*0.53, Inches(1.2),
       '最も目に入りやすい場所に\nあなたの店舗を', 24, TXT, bold=True)
    # 右：3ゾーン視覚化
    zones = [('① リスティング広告', YLW, Inches(0.06)),
             ('② ローカルパック  ← ここ！', T_MD, Inches(0.18)),
             ('③ 自然検索', LGR, Inches(0.06))]
    zt = Inches(2.8)
    for label, c, thick in zones:
        box(s, W*0.43, zt, W*0.5, thick + Inches(0.44), c, rnd=True)
        tb(s, W*0.45, zt + Inches(0.08), W*0.47, Inches(0.35), label,
           13 if '←' not in label else 15,
           WHT if c != LGR else TXT, bold='←' in label)
        zt += thick + Inches(0.55)
    # 右下：補足
    tb(s, W*0.43, H - Inches(1.1), W*0.53, Inches(0.9),
       'ローカルパックのクリック率は広告枠の\n約2〜3倍。最も費用対効果が高い集客手段です。',
       13, TXMD)
    print('  slide 04: Map Prominence ✓')
    return s

# ============================================================
# SLIDE 05: Googleマップが売上に直結する理由（3カラム）
# ============================================================
def make_revenue_driver():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, 'Googleマップが売上に直結する理由')
    cols = [
        ('圧倒的\nビュー数', '上位表示されるだけで\n月数万〜数十万回の\n表示機会を獲得できます', T_DK, '01'),
        ('来店意欲\nの向上', '写真・口コミで信頼感UP\n初めてのお客様も\n安心して来店できます', T_MD, '02'),
        ('売上\n拡大', 'ルート検索・電話・予約\n来店行動の全てがMAP\n一つで完結します', T_LT, '03'),
    ]
    col_w = (W - MR - SB_W - Inches(0.3)) / 3
    base_l = MR + SB_W + Inches(0.15)
    for i, (hdg, desc, c, num) in enumerate(cols):
        cx = base_l + col_w * i
        box(s, cx, BODY_T + Inches(0.2), col_w - Inches(0.2),
            H - BODY_T - BOT - Inches(0.6), c, rnd=True)
        # 番号
        tb(s, cx + Inches(0.15), BODY_T + Inches(0.3), col_w - Inches(0.4),
           Inches(0.5), num, 28, YLW, bold=True)
        # 見出し
        tb(s, cx + Inches(0.15), BODY_T + Inches(0.8), col_w - Inches(0.35),
           Inches(1.2), hdg, 24, WHT, bold=True)
        # 説明
        tb(s, cx + Inches(0.15), BODY_T + Inches(2.1), col_w - Inches(0.35),
           Inches(2.5), desc, 14, WHT)
    # フッター
    tb(s, MR + SB_W, H - Inches(0.55), W - MR*2, Inches(0.45),
       '上位表示が、直接的な利益に繋がる体験をご実感ください！', 16, T_MD,
       bold=True, align=PP_ALIGN.CENTER)
    print('  slide 05: Revenue Driver ✓')
    return s

# ============================================================
# SLIDE 06: Googleマップ経由で増える行動（4ボックス）
# ============================================================
def make_map_actions():
    s = ns()
    bg_solid(s, T_DK)
    box(s, 0, 0, W, Inches(0.07), YLW)
    box(s, 0, H - Inches(0.07), W, Inches(0.07), YLW)
    tb(s, MR, Inches(0.2), W - MR*2, Inches(0.9),
       'Googleマップ経由で増える行動', 34, WHT, bold=True, align=PP_ALIGN.CENTER)
    tb(s, MR, Inches(1.05), W - MR*2, Inches(0.5),
       'ユーザーはGoogleマップで「見つけて → 確認して → 来店する」', 16, YLW,
       align=PP_ALIGN.CENTER)
    actions = [
        ('🔍', '店舗をみつける', '「近くの○○」で検索\n地図上に表示される'),
        ('📷', '写真・口コミを見る', '雰囲気・評判を確認\n来店判断に直結'),
        ('🗺', 'ルート検索', 'ワンタップで経路案内\n来店率が大幅UP'),
        ('🌐', 'ウェブサイトを見る', 'メニュー・予約ページへ\nシームレスに誘導'),
    ]
    col_w = (W - MR*2) / 4
    for i, (icon, title, desc) in enumerate(actions):
        cx = MR + col_w * i
        box(s, cx + Inches(0.1), Inches(1.75), col_w - Inches(0.2),
            H - Inches(2.2), WHT, rnd=True)
        tb(s, cx + Inches(0.2), Inches(1.9), col_w - Inches(0.4), Inches(0.7),
           icon, 30, T_MD, align=PP_ALIGN.CENTER)
        tb(s, cx + Inches(0.15), Inches(2.65), col_w - Inches(0.3), Inches(0.7),
           title, 16, TXT, bold=True, align=PP_ALIGN.CENTER)
        tb(s, cx + Inches(0.15), Inches(3.45), col_w - Inches(0.3), Inches(2.5),
           desc, 13, TXMD, align=PP_ALIGN.CENTER)
    print('  slide 06: Map Actions ✓')
    return s

# ============================================================
# SLIDE 07: 選ばれる店舗と選ばれない店舗の差
# ============================================================
def make_comparison():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, '選ばれる店舗と選ばれない店舗の差')
    half = (W - SB_W - Inches(0.35)) / 2
    base_l = SB_W + Inches(0.2)
    # 左：選ばれない
    box(s, base_l, BODY_T + Inches(0.2), half - Inches(0.15),
        H - BODY_T - BOT - Inches(0.55), LGR, rnd=True)
    tb(s, base_l + Inches(0.2), BODY_T + Inches(0.3), half - Inches(0.5),
       Inches(0.6), '選ばれない店舗', 20, TXMD, bold=True)
    bad = ['写真がない / 少ない', '住所・電話番号が不正確', '口コミゼロ or 放置',
           '情報更新が止まっている', '営業時間が不明確']
    for i, t in enumerate(bad):
        tb(s, base_l + Inches(0.25), BODY_T + Inches(1.05) + Inches(0.55)*i,
           half - Inches(0.5), Inches(0.5), f'✕  {t}', 14, TXT)
    tb(s, base_l + Inches(0.15), H - Inches(0.85), half - Inches(0.3), Inches(0.55),
       '機会損失 — 見込み客を競合に奪われる', 13, TXMD, bold=True)
    # 右：選ばれる
    rx = base_l + half + Inches(0.15)
    box(s, rx, BODY_T + Inches(0.2), half - Inches(0.15),
        H - BODY_T - BOT - Inches(0.55), T_MD, rnd=True)
    tb(s, rx + Inches(0.2), BODY_T + Inches(0.3), half - Inches(0.5),
       Inches(0.6), '選ばれる店舗', 20, WHT, bold=True)
    good = ['魅力的な写真が豊富', '情報が正確で最新', '高評価口コミが多い',
            '定期的に情報更新', 'オーナー返信あり']
    for i, t in enumerate(good):
        tb(s, rx + Inches(0.25), BODY_T + Inches(1.05) + Inches(0.55)*i,
           half - Inches(0.5), Inches(0.5), f'◎  {t}', 14, WHT)
    tb(s, rx + Inches(0.15), H - Inches(0.85), half - Inches(0.3), Inches(0.55),
       '集客チャンス — 選ばれ続ける店舗へ', 13, YLW, bold=True)
    print('  slide 07: Comparison ✓')
    return s

# ============================================================
# SLIDE 08: 上位表示されると何が変わるのか
# ============================================================
def make_what_changes():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, '上位表示されると何が変わるのか')
    steps = [
        ('圏外', '見つけてもらえない\n存在しないも同然', LGR, TXT),
        ('上位表示', '検索で発見される\n月間ビュー数が激増', T_MD, WHT),
        ('信頼獲得', '口コミ・写真で\n来店意欲が高まる', T_DK, WHT),
        ('売上UP', '電話・来店・予約\nアクション数が倍増', YLW, TXT),
    ]
    sw = (W - MR*2 - SB_W) / 4
    base_l = MR + SB_W + Inches(0.1)
    base_t = BODY_T + Inches(0.3)
    bh = H - BODY_T - BOT - Inches(1.1)
    for i, (hdg, desc, bgc, tc) in enumerate(steps):
        cx = base_l + sw * i
        box(s, cx, base_t + sw*0.1*i, sw - Inches(0.12), bh - sw*0.1*i, bgc, rnd=True)
        tb(s, cx + Inches(0.12), base_t + sw*0.1*i + Inches(0.2),
           sw - Inches(0.28), Inches(0.65), hdg, 18, tc, bold=True, align=PP_ALIGN.CENTER)
        tb(s, cx + Inches(0.12), base_t + sw*0.1*i + Inches(0.95),
           sw - Inches(0.28), Inches(2.5), desc, 13, tc, align=PP_ALIGN.CENTER)
        if i < 3:
            tb(s, cx + sw - Inches(0.25), base_t + bh*0.4, Inches(0.3), Inches(0.5),
               '▶', 18, YLW, bold=True)
    tb(s, MR + SB_W, H - Inches(0.58), W - MR*2, Inches(0.45),
       'どれだけプロフィールを整えても、見つからなければ効果は得られません',
       15, TXMD, bold=True, align=PP_ALIGN.CENTER)
    print('  slide 08: What Changes ✓')
    return s

# ============================================================
# SLIDE 09: Googleが店舗を評価する3つの要素
# ============================================================
def make_three_factors():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, 'Googleが店舗を評価する3つの要素')
    factors = [
        ('関連性', 'Relevance', '検索キーワードと\nプロフィール情報の\n一致度・完全性', T_DK),
        ('距離', 'Distance', 'ユーザーの現在地と\n店舗の物理的距離\n（エリア設定も有効）', T_MD),
        ('知名度', 'Prominence', '口コミ数・評価点\nWeb上での言及度\nブランド認知度', T_LT),
    ]
    ow = (W - MR*2 - SB_W - Inches(0.4)) / 3
    base_l = MR + SB_W + Inches(0.2)
    ot = BODY_T + Inches(0.3)
    oh = H - BODY_T - BOT - Inches(1.2)
    for i, (jn, en, desc, c) in enumerate(factors):
        cx = base_l + ow * i
        # 円形シェイプ
        o = oval(s, cx + ow*0.1, ot, ow*0.8, oh * 0.75, c)
        shape_text(o, '', 1, WHT)
        # テキスト
        tb(s, cx + Inches(0.1), ot + oh*0.05, ow*0.8, Inches(0.55),
           jn, 26, WHT, bold=True, align=PP_ALIGN.CENTER)
        tb(s, cx + Inches(0.1), ot + oh*0.25, ow*0.8, Inches(0.4),
           en, 12, YLW, align=PP_ALIGN.CENTER)
        tb(s, cx + Inches(0.1), ot + oh*0.38, ow*0.8, Inches(1.8),
           desc, 13, WHT, align=PP_ALIGN.CENTER)
    tb(s, MR + SB_W, H - Inches(0.68), W - MR*2, Inches(0.55),
       'Googleのアルゴリズムは日々変化します。専門知識なしでMEO対策を継続するのは困難な時代です。',
       13, TXMD, align=PP_ALIGN.CENTER)
    print('  slide 09: Three Factors ✓')
    return s

# ============================================================
# SLIDE 10: 距離とエリアの考え方
# ============================================================
def make_distance_area():
    s = ns()
    bg_solid(s, OWHT)
    # 左ティールパネル (38%)
    gbox(s, 0, 0, W*0.38, H, H_MD, H_DK, ang=5400000)
    box(s, W*0.38, 0, Inches(0.06), H, YLW)
    tb(s, Inches(0.3), Inches(0.3), W*0.35, Inches(2.0),
       '距離と\nエリアの\n考え方', 32, WHT, bold=True)
    tb(s, Inches(0.3), Inches(2.6), W*0.35, Inches(1.5),
       'Googleは距離だけでなく\n関連性・知名度も\n総合的に判断します', 14, YLW)
    # 右パネル
    rx = W*0.38 + Inches(0.25)
    rw = W - W*0.38 - Inches(0.5)
    tb(s, rx, Inches(0.4), rw, Inches(0.8),
       '距離だけではない！エリア戦略がカギ', 22, TXT, bold=True)
    points = [
        ('📍 地域キーワード対策',
         '「新宿 カフェ」「渋谷 ランチ」など地名を含むキーワードで\n上位表示を狙うことが効果的です。'),
        ('🎯 エリア設定の最適化',
         '店舗から一定距離のユーザーに表示されやすくするため\nサービスエリアの正確な設定が重要です。'),
        ('📊 検索意図との一致',
         '「近くの○○」「今すぐ行ける○○」など\n来店意欲の高いキーワードへの対応が成果を左右します。'),
    ]
    for i, (hdg, body) in enumerate(points):
        t_start = Inches(1.4) + Inches(1.85)*i
        box(s, rx, t_start, rw, Inches(1.7), OWHT, rnd=True)
        box(s, rx, t_start, Inches(0.07), Inches(1.7), T_MD)
        tb(s, rx + Inches(0.2), t_start + Inches(0.1), rw - Inches(0.3),
           Inches(0.5), hdg, 15, TXT, bold=True)
        tb(s, rx + Inches(0.2), t_start + Inches(0.65), rw - Inches(0.3),
           Inches(1.0), body, 12, TXMD)
    print('  slide 10: Distance Area ✓')
    return s

# ============================================================
# SLIDE 11: 知名度・口コミの影響
# ============================================================
def make_review_impact():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, '知名度・口コミの影響')
    items = [
        ('口コミの数', '多くのポジティブな口コミは\n信頼性を高め、新規顧客を\n引きつけます。', T_DK),
        ('口コミの質', '具体的な高評価は順位だけ\nでなく来店意欲を直接\n高めます。', T_MD),
        ('オーナー返信', '返信はGoogleとユーザー\n双方からの評価対象。\n誠実な対応が武器になります。', T_LT),
        ('知名度UP', 'Web上での言及・被リンク・\nSNSでの認知度も\nアルゴリズムが参照します。', YLW),
    ]
    iw = (W - MR - SB_W - Inches(0.5)) / 4
    base_l = MR + SB_W + Inches(0.2)
    for i, (hdg, desc, c) in enumerate(items):
        cx = base_l + iw * i
        box(s, cx, BODY_T + Inches(0.25), iw - Inches(0.18),
            H - BODY_T - BOT - Inches(0.65), c, rnd=True)
        tb(s, cx + Inches(0.12), BODY_T + Inches(0.4), iw - Inches(0.3),
           Inches(0.8), hdg, 17, WHT if c != YLW else TXT, bold=True, align=PP_ALIGN.CENTER)
        tb(s, cx + Inches(0.12), BODY_T + Inches(1.3), iw - Inches(0.3),
           Inches(2.8), desc, 13, WHT if c != YLW else TXT, align=PP_ALIGN.CENTER)
    print('  slide 11: Review Impact ✓')
    return s

# ============================================================
# SLIDE 12: 選ばれる店舗の共通点
# ============================================================
def make_common_traits():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, '選ばれる店舗の共通点')
    traits = [
        ('情報が正確で充実',
         '営業時間・住所・電話番号・ウェブサイトなど\n必要な情報が最新かつ正確に整備されている', T_DK),
        ('写真が魅力的で豊富',
         '店舗外観・内観・商品・サービス・スタッフなど\n来店意欲を高める写真が多数掲載されている', T_MD),
        ('高評価の口コミが多い',
         'お客様からのポジティブな口コミが蓄積され\nオーナーが丁寧に返信している', T_LT),
        ('定期的に情報更新',
         '新商品・イベント・キャンペーンなど\n最新情報を定期的に発信し続けている', YLW),
    ]
    cw = (W - MR - SB_W - Inches(0.5)) / 2
    base_l = MR + SB_W + Inches(0.2)
    positions = [(0, 0), (1, 0), (0, 1), (1, 1)]
    rh = (H - BODY_T - BOT - Inches(0.7)) / 2
    for i, (hdg, desc, c) in enumerate(traits):
        col, row = positions[i]
        cx = base_l + cw * col
        cy = BODY_T + Inches(0.2) + rh * row
        box(s, cx, cy, cw - Inches(0.2), rh - Inches(0.15), c, rnd=True)
        box(s, cx, cy, Inches(0.08), rh - Inches(0.15), NVY)
        tb(s, cx + Inches(0.2), cy + Inches(0.15), cw - Inches(0.4),
           Inches(0.65), hdg, 17, WHT if c != YLW else TXT, bold=True)
        tb(s, cx + Inches(0.2), cy + Inches(0.85), cw - Inches(0.4),
           rh - Inches(1.1), desc, 13, WHT if c != YLW else TXT)
    tb(s, MR + SB_W, H - Inches(0.55), W - MR*2, Inches(0.42),
       'これらの要素を弊社MEO対策でまるっと解決できます！', 16, T_MD,
       bold=True, align=PP_ALIGN.CENTER)
    print('  slide 12: Common Traits ✓')
    return s

# ============================================================
# SLIDE 13: 口コミが来店を後押しする理由
# ============================================================
def make_review_psychology():
    s = ns()
    bg_solid(s, T_DK)
    box(s, 0, 0, W, Inches(0.07), YLW)
    box(s, 0, H - Inches(0.07), W, Inches(0.07), YLW)
    tb(s, MR, Inches(0.18), W - MR*2, Inches(0.9),
       '口コミが来店を後押しする理由', 32, WHT, bold=True, align=PP_ALIGN.CENTER)
    tb(s, MR, Inches(1.1), W - MR*2, Inches(0.6),
       '多くの高評価な口コミが、お客様の「失敗しない」という安心感を生み出します',
       16, YLW, align=PP_ALIGN.CENTER)
    reasons = [
        ('安心感', '「みんなが良いと言っている」\n事実が不安を取り除き\n来店へのハードルを下げます'),
        ('信頼性', '実際の体験談は広告より\n信頼される。星評価が\n高いほど選ばれやすい'),
        ('社会的証明', '多くの人が選んでいる実績が\n「自分も行くべきだ」という\n心理を生み出します'),
    ]
    rw = (W - MR*2) / 3
    for i, (hdg, desc) in enumerate(reasons):
        cx = MR + rw * i
        box(s, cx + Inches(0.15), Inches(1.95), rw - Inches(0.3),
            H - Inches(2.5), WHT, rnd=True)
        tb(s, cx + Inches(0.25), Inches(2.1), rw - Inches(0.5),
           Inches(0.7), hdg, 22, T_DK, bold=True, align=PP_ALIGN.CENTER)
        tb(s, cx + Inches(0.25), Inches(2.9), rw - Inches(0.5),
           H - Inches(3.5), desc, 14, TXT, align=PP_ALIGN.CENTER)
    print('  slide 13: Review Psychology ✓')
    return s

# ============================================================
# SLIDE 14: AIを活用した口コミ返信
# ============================================================
def make_ai_review():
    s = ns()
    bg_solid(s, OWHT)
    # 左パネル
    gbox(s, 0, 0, W*0.42, H, H_DK, H_MD, ang=5400000)
    box(s, W*0.42, 0, Inches(0.06), H, YLW)
    tb(s, Inches(0.3), Inches(0.35), W*0.38, Inches(1.0),
       'AIを活用した\n口コミ返信', 30, WHT, bold=True)
    tb(s, Inches(0.3), Inches(1.5), W*0.38, Inches(0.7),
       '口コミの返信文章に\n迷ったことはありませんか？', 15, YLW)
    box(s, Inches(0.3), Inches(2.4), W*0.35, Inches(0.07), WHT)
    tb(s, Inches(0.3), Inches(2.6), W*0.38, Inches(3.5),
       'ボタン一つで楽々文書作成・返信！\n\nAIが口コミ内容を深く理解し\n1人1人に最適な文章で返信。\n\n返信の手間を大幅削減し\nオーナー様は本業に集中できます', 14, WHT)
    # 右パネル
    rx = W*0.42 + Inches(0.3)
    rw = W - W*0.42 - Inches(0.5)
    feats = [
        ('🤖 AI生成返信', 'ボタン1つで返信文章を自動生成\n口調・絵文字も自由にカスタマイズ可能'),
        ('⚡ スピード対応', '新着口コミをLINE通知で即キャッチ\n見逃しゼロで迅速な対応が可能に'),
        ('📊 分析レポート', '口コミの傾向・評価推移を自動分析\n改善すべきポイントが一目でわかる'),
    ]
    for i, (hdg, desc) in enumerate(feats):
        t = Inches(0.5) + Inches(2.1)*i
        box(s, rx, t, rw, Inches(1.85), T_DK if i % 2 == 0 else T_MD, rnd=True)
        tb(s, rx + Inches(0.2), t + Inches(0.15), rw - Inches(0.35),
           Inches(0.6), hdg, 17, YLW, bold=True)
        tb(s, rx + Inches(0.2), t + Inches(0.8), rw - Inches(0.35),
           Inches(0.9), desc, 13, WHT)
    print('  slide 14: AI Review ✓')
    return s

# ============================================================
# SLIDE 15: 投稿は一気に準備できます
# ============================================================
def make_batch_post():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, '投稿は一気に準備できます')
    box(s, MR + SB_W, BODY_T + Inches(0.2), W - MR*2, Inches(0.7), T_DK, rnd=True)
    tb(s, MR + SB_W + Inches(0.3), BODY_T + Inches(0.3), W - MR*2 - Inches(0.6),
       Inches(0.5), '"SNSの更新がなかなか続かない" — そんなオーナー様へ',
       16, WHT, bold=True)
    feats = [
        ('AIで最適投稿を作成',
         '店舗情報・季節・イベントを踏まえた\n投稿文をAIが自動生成します。\n忙しいオーナー様の手間を大幅削減。'),
        ('1ヶ月分を一括予約',
         '投稿スケジュール機能を使えば\n一度に1ヶ月分の投稿を予約投稿可能。\nまとめて準備して後は自動更新。'),
        ('写真・絵文字も自由',
         '口調・絵文字・写真の組み合わせを\n自由にカスタマイズ。\n店舗の個性を出した投稿が可能です。'),
    ]
    fw = (W - MR - SB_W - Inches(0.5)) / 3
    for i, (hdg, desc) in enumerate(feats):
        cx = MR + SB_W + Inches(0.15) + fw * i
        box(s, cx, BODY_T + Inches(1.15), fw - Inches(0.2),
            H - BODY_T - BOT - Inches(1.5), T_MD if i == 1 else OWHT, rnd=True)
        border_c = T_DK if i != 1 else T_LT
        box(s, cx, BODY_T + Inches(1.15), Inches(0.07),
            H - BODY_T - BOT - Inches(1.5), border_c)
        tb(s, cx + Inches(0.2), BODY_T + Inches(1.3), fw - Inches(0.35),
           Inches(0.7), hdg, 16, WHT if i == 1 else TXT, bold=True)
        tb(s, cx + Inches(0.2), BODY_T + Inches(2.1), fw - Inches(0.35),
           Inches(2.5), desc, 13, WHT if i == 1 else TXMD)
    tb(s, MR + SB_W, H - Inches(0.55), W - MR*2, Inches(0.42),
       '弊社のMEO対策は、オーナー様の手間を最大限お手伝いします。',
       15, T_MD, bold=True, align=PP_ALIGN.CENTER)
    print('  slide 15: Batch Post ✓')
    return s

# ============================================================
# SLIDE 16: 継続運用が成果を生む理由
# ============================================================
def make_continuous():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, '継続運用が成果を生む理由')
    tb(s, MR + SB_W + Inches(0.1), BODY_T + Inches(0.15), W - MR*2, Inches(0.55),
       'MEO対策は早期導入・継続的な育成が成功のカギです', 17, TXT, bold=True)
    steps = [
        ('STEP 1\n初期設定', 'プロフィールの\n完全最適化\nキーワード戦略策定', T_DK),
        ('STEP 2\n日々の運用', '投稿・口コミ返信\n写真更新・情報管理\nLINE通知で即対応', T_MD),
        ('STEP 3\n継続的更新', 'キャンペーン・\nイベント情報発信\nアルゴリズム対応', T_LT),
        ('STEP 4\n上位継続', '月次レポート確認\n前年比グラフで成果\nPDCAで改善継続', YLW),
    ]
    sw = (W - MR - SB_W - Inches(0.5)) / 4
    base_l = MR + SB_W + Inches(0.15)
    bh = H - BODY_T - BOT - Inches(1.25)
    for i, (hdg, desc, c) in enumerate(steps):
        cx = base_l + sw * i
        box(s, cx, BODY_T + Inches(0.85), sw - Inches(0.15), bh, c, rnd=True)
        tb(s, cx + Inches(0.1), BODY_T + Inches(1.0), sw - Inches(0.25),
           Inches(0.9), hdg, 16, WHT if c != YLW else TXT, bold=True, align=PP_ALIGN.CENTER)
        tb(s, cx + Inches(0.1), BODY_T + Inches(2.0), sw - Inches(0.25),
           bh - Inches(1.2), desc, 13, WHT if c != YLW else TXT, align=PP_ALIGN.CENTER)
        if i < 3:
            tb(s, cx + sw - Inches(0.22), BODY_T + Inches(1.8), Inches(0.25), Inches(0.4),
               '▶', 16, YLW if c != YLW else T_MD, bold=True)
    tb(s, MR + SB_W, H - Inches(0.55), W - MR*2, Inches(0.42),
       '手間なく継続できる仕組みで、確実に成果を積み上げます',
       15, T_MD, bold=True, align=PP_ALIGN.CENTER)
    print('  slide 16: Continuous ✓')
    return s

# ============================================================
# SLIDE 17: 目に見える、閲覧数の増加
# ============================================================
def make_metrics():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, '目に見える、閲覧数の増加 ─ 成長するMEO対策')
    tb(s, MR + SB_W + Inches(0.1), BODY_T + Inches(0.15), W - MR*2, Inches(0.55),
       'キーワードが上位でも、閲覧数が増えなければ意味がありません', 15, TXMD)
    # グラフ風ビジュアル
    base_l = MR + SB_W + Inches(0.2)
    bw = W - base_l - MR
    bars = [('1月', 0.2), ('2月', 0.3), ('3月', 0.45), ('4月', 0.5), ('5月', 0.62),
            ('6月', 0.7), ('7月', 0.78), ('8月', 0.82), ('9月', 0.88), ('10月', 0.92),
            ('11月', 0.95), ('12月', 1.0)]
    bar_w = bw / len(bars) - Inches(0.08)
    max_h = H - BODY_T - BOT - Inches(1.9)
    base_t = H - BOT - Inches(0.6)
    for i, (month, ratio) in enumerate(bars):
        bx = base_l + (bw / len(bars)) * i
        bh = max_h * ratio
        by = base_t - bh
        c = T_DK if i < 6 else T_MD
        box(s, bx, by, bar_w, bh, c)
        tb(s, bx, base_t + Inches(0.05), bar_w + Inches(0.05), Inches(0.4),
           month, 10, TXMD, align=PP_ALIGN.CENTER)
    # 前年比ライン（シンプルな表示）
    box(s, base_l, base_t - max_h*0.45, bw, Inches(0.03), YLW)
    tb(s, base_l + bw*0.7, base_t - max_h*0.48, Inches(1.5), Inches(0.4),
       '前年比', 11, YLW, bold=True)
    # サマリー
    box(s, MR + SB_W, BODY_T + Inches(0.75), Inches(3.5), Inches(1.0), T_DK, rnd=True)
    tb(s, MR + SB_W + Inches(0.15), BODY_T + Inches(0.82), Inches(3.2), Inches(0.85),
       '毎月の閲覧数をグラフ化\n前年と比較して成長を可視化', 13, WHT, bold=True)
    print('  slide 17: Metrics ✓')
    return s

# ============================================================
# SLIDE 18: 検索順位の上昇イメージ
# ============================================================
def make_ranking():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, '検索順位の上昇イメージ')
    tb(s, MR + SB_W + Inches(0.1), BODY_T + Inches(0.15), W - MR*2, Inches(0.55),
       'MEO対策で、段階的に上位表示を実現していきましょう！', 15, T_MD, bold=True)
    stages = [
        ('対策前', '20位以下\n（圏外）', LGR, TXT, 0.2),
        ('0.5ヶ月後', '8位', T_LT, TXT, 0.5),
        ('1ヶ月後', '2位\n（TOP3入り）', YLW, TXT, 1.0),
    ]
    sw = (W - MR*2 - SB_W) / 3
    base_l = MR + SB_W + Inches(0.1)
    max_h = H - BODY_T - BOT - Inches(1.6)
    base_t = H - BOT - Inches(0.4)
    for i, (period, rank, c, tc, ratio) in enumerate(stages):
        cx = base_l + sw * i
        bh = max_h * ratio
        by = base_t - bh
        box(s, cx + sw*0.1, by, sw*0.8, bh, c)
        tb(s, cx + sw*0.05, by - Inches(0.7), sw*0.9, Inches(0.6),
           rank, 20, TXT, bold=True, align=PP_ALIGN.CENTER)
        tb(s, cx + sw*0.05, base_t + Inches(0.05), sw*0.9, Inches(0.45),
           period, 13, TXMD, align=PP_ALIGN.CENTER)
    # 矢印
    tb(s, MR + SB_W + sw*0.85, BODY_T + max_h*0.3 + Inches(0.85),
       Inches(0.4), Inches(0.5), '▶', 20, YLW, bold=True)
    tb(s, MR + SB_W + sw*1.85, BODY_T + max_h*0.1 + Inches(0.85),
       Inches(0.4), Inches(0.5), '▶', 20, YLW, bold=True)
    print('  slide 18: Ranking ✓')
    return s

# ============================================================
# SLIDE 19: 電話・ルート検索・来店数の変化
# ============================================================
def make_action_change():
    s = ns()
    bg_solid(s, T_DK)
    box(s, 0, 0, W, Inches(0.07), YLW)
    box(s, 0, H - Inches(0.07), W, Inches(0.07), YLW)
    tb(s, MR, Inches(0.2), W - MR*2, Inches(0.85),
       '電話・ルート検索・来店数の変化', 32, WHT, bold=True, align=PP_ALIGN.CENTER)
    tb(s, MR, Inches(1.1), W - MR*2, Inches(0.55),
       '信頼できる店舗になることで、お客様からのアクションが劇的に増加します',
       16, YLW, align=PP_ALIGN.CENTER)
    metrics = [
        ('📞', '電話問い合わせ', '上位表示で\nタップして通話が急増', '+180%'),
        ('🗺', 'ルート検索', '来店意欲の高い\nユーザーがルート案内開始', '+220%'),
        ('👥', '来店客数', '口コミ・写真が\n来店の後押しに', '+150%'),
        ('🌐', 'WEBサイト誘導', 'プロフィールからの\nクリックが増加', '+130%'),
    ]
    mw = (W - MR*2) / 4
    for i, (icon, title, desc, pct) in enumerate(metrics):
        cx = MR + mw * i
        box(s, cx + Inches(0.12), Inches(1.9), mw - Inches(0.24),
            H - Inches(2.4), WHT, rnd=True)
        tb(s, cx + Inches(0.22), Inches(2.0), mw - Inches(0.44), Inches(0.6),
           icon, 28, T_MD, align=PP_ALIGN.CENTER)
        tb(s, cx + Inches(0.22), Inches(2.65), mw - Inches(0.44), Inches(0.55),
           title, 14, TXT, bold=True, align=PP_ALIGN.CENTER)
        tb(s, cx + Inches(0.22), Inches(3.25), mw - Inches(0.44), Inches(1.0),
           desc, 12, TXMD, align=PP_ALIGN.CENTER)
        tb(s, cx + Inches(0.22), Inches(4.3), mw - Inches(0.44), Inches(0.8),
           pct, 28, ORG, bold=True, align=PP_ALIGN.CENTER)
        tb(s, cx + Inches(0.22), Inches(5.1), mw - Inches(0.44), Inches(0.35),
           '平均増加率（参考値）', 10, TXMD, align=PP_ALIGN.CENTER)
    print('  slide 19: Action Change ✓')
    return s

# ============================================================
# SLIDE 20: グラフで分かる、1年間の成長
# ============================================================
def make_year_growth():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, 'グラフで分かる、1年間の成長')
    tb(s, MR + SB_W + Inches(0.1), BODY_T + Inches(0.15), W*0.55, Inches(0.55),
       '3年以上伸び続けているのか？MEO対策の効果が出ているのか？', 14, TXMD)
    # 左：成長説明
    box(s, MR + SB_W + Inches(0.1), BODY_T + Inches(0.85),
        W*0.42, H - BODY_T - BOT - Inches(1.2), T_DK, rnd=True)
    tb(s, MR + SB_W + Inches(0.3), BODY_T + Inches(1.0), W*0.38, Inches(0.7),
       '成長するMEO対策', 20, YLW, bold=True)
    tb(s, MR + SB_W + Inches(0.3), BODY_T + Inches(1.8), W*0.38, Inches(3.5),
       '毎月の閲覧数をグラフ化し、\n前年と比較することで成長を可視化。\n\nオーナー様の「本当に効果があるのか？」\nという不安に、データで答えます。\n\n弊社MEO対策に自信があるからこそ、\n積み重なった実績をお見せできます。', 13, WHT)
    # 右：グラフ的ビジュアル
    rx = MR + SB_W + W*0.47
    rw = W - rx - MR
    months = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月']
    cy_vals = [0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.72, 0.78, 0.85, 0.92, 1.0]
    py_vals = [0.25, 0.28, 0.32, 0.35, 0.38, 0.40, 0.43, 0.45, 0.48, 0.50, 0.53, 0.55]
    max_h = H - BODY_T - BOT - Inches(1.7)
    base_t_bar = H - BOT - Inches(0.45)
    bw_each = rw / 12 - Inches(0.05)
    for i, (month, cy, py) in enumerate(zip(months, cy_vals, py_vals)):
        bx = rx + (rw / 12) * i
        # 今年
        h1 = max_h * cy
        box(s, bx, base_t_bar - h1, bw_each * 0.55, h1, T_MD)
        # 前年
        h2 = max_h * py
        box(s, bx + bw_each * 0.6, base_t_bar - h2, bw_each * 0.4, h2, LGR)
        tb(s, bx, base_t_bar + Inches(0.04), bw_each + Inches(0.08), Inches(0.35),
           month, 9, TXMD, align=PP_ALIGN.CENTER)
    # 凡例
    box(s, rx, BODY_T + Inches(0.75), Inches(0.25), Inches(0.25), T_MD)
    tb(s, rx + Inches(0.3), BODY_T + Inches(0.75), Inches(1.0), Inches(0.28), '今年', 11, TXT)
    box(s, rx + Inches(1.5), BODY_T + Inches(0.75), Inches(0.25), Inches(0.25), LGR)
    tb(s, rx + Inches(1.8), BODY_T + Inches(0.75), Inches(1.0), Inches(0.28), '前年', 11, TXT)
    print('  slide 20: Year Growth ✓')
    return s

# ============================================================
# SLIDE 21: 導入前後の比較イメージ
# ============================================================
def make_before_after():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, '導入前後の比較イメージ')
    hw = (W - MR - SB_W - Inches(0.4)) / 2
    base_l = MR + SB_W + Inches(0.15)
    bh = H - BODY_T - BOT - Inches(0.4)
    # BEFORE
    box(s, base_l, BODY_T + Inches(0.2), hw - Inches(0.15), bh, LGR, rnd=True)
    tb(s, base_l + Inches(0.2), BODY_T + Inches(0.3), hw - Inches(0.4),
       Inches(0.65), 'BEFORE', 26, TXMD, bold=True)
    box(s, base_l + Inches(0.2), BODY_T + Inches(1.0), hw - Inches(0.4),
       Inches(0.05), TXMD)
    befores = ['Googleマップを知らない客しか来ない',
               '口コミがなく新規客が来店しない',
               '競合店に検索で負けている',
               '写真が少なく魅力が伝わらない',
               '情報が古いまま放置されている']
    for i, t in enumerate(befores):
        tb(s, base_l + Inches(0.25), BODY_T + Inches(1.2) + Inches(0.62)*i,
           hw - Inches(0.5), Inches(0.55), f'✕  {t}', 13, TXMD)
    # AFTER
    rx = base_l + hw + Inches(0.2)
    box(s, rx, BODY_T + Inches(0.2), hw - Inches(0.15), bh, T_MD, rnd=True)
    tb(s, rx + Inches(0.2), BODY_T + Inches(0.3), hw - Inches(0.4),
       Inches(0.65), 'AFTER', 26, YLW, bold=True)
    box(s, rx + Inches(0.2), BODY_T + Inches(1.0), hw - Inches(0.4),
       Inches(0.05), YLW)
    afters = ['Googleマップを見て来ました！の声が増加',
              '高評価口コミで新規客が続々来店',
              '検索TOP3に入り競合に差をつける',
              '魅力的な写真で来店意欲が高まる',
              '最新情報で信頼感が格段に向上']
    for i, t in enumerate(afters):
        tb(s, rx + Inches(0.25), BODY_T + Inches(1.2) + Inches(0.62)*i,
           hw - Inches(0.5), Inches(0.55), f'◎  {t}', 13, WHT)
    print('  slide 21: Before/After ✓')
    return s

# ============================================================
# SLIDE 22: なぜ安い業者では駄目なのか
# ============================================================
def make_why_not_cheap():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, 'なぜ安い業者では駄目なのか')
    reasons = [
        ('アルゴリズムは常に変化する',
         'Googleのアルゴリズムは頻繁に更新されます。\n安価な業者は最新動向への対応が遅く、\n一時的な効果しか得られないことがほとんどです。',
         '時間だけを費やして成果が出ない'),
        ('本業との両立が困難',
         '継続的なMEO運用には専門知識と\n毎日の管理工数が必要です。\n自社対応では本業に支障が出てしまいます。',
         '結果、途中でやめてしまう'),
        ('継続的な知見・実績が必要',
         '成功するMEO対策は経験と\n蓄積データに基づく戦略が不可欠です。\n低コストでは必要なサポートが得られません。',
         '投資対効果が大幅に下がる'),
    ]
    rw = (W - MR - SB_W - Inches(0.5)) / 3
    base_l = MR + SB_W + Inches(0.15)
    for i, (hdg, body, warn) in enumerate(reasons):
        cx = base_l + rw * i
        box(s, cx, BODY_T + Inches(0.2), rw - Inches(0.18),
            H - BODY_T - BOT - Inches(0.55), OWHT, rnd=True)
        box(s, cx, BODY_T + Inches(0.2), Inches(0.08),
            H - BODY_T - BOT - Inches(0.55), T_DK)
        tb(s, cx + Inches(0.2), BODY_T + Inches(0.35), rw - Inches(0.38),
           Inches(0.75), hdg, 15, TXT, bold=True)
        tb(s, cx + Inches(0.2), BODY_T + Inches(1.15), rw - Inches(0.38),
           Inches(2.5), body, 13, TXMD)
        box(s, cx + Inches(0.1), H - BOT - Inches(1.25), rw - Inches(0.3), Inches(0.7), T_DK, rnd=True)
        tb(s, cx + Inches(0.2), H - BOT - Inches(1.18), rw - Inches(0.38),
           Inches(0.55), warn, 12, WHT, bold=True, align=PP_ALIGN.CENTER)
    print('  slide 22: Why Not Cheap ✓')
    return s

# ============================================================
# SLIDE 23: プランで得られるメリット
# ============================================================
def make_plan_benefits():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, 'プランで得られるメリット')
    items = [
        ('最新ノウハウの活用', 'Googleのアルゴリズム変更に即時対応\n常に最適な戦略で運用を継続します'),
        ('効率的な戦略立案', 'ビジネスに最適化されたMEO戦略\nPDCAサイクルで継続的に改善します'),
        ('AI機能で時間を節約', '口コミ返信・投稿作成をAIが自動化\n管理工数を大幅に削減できます'),
        ('透明性の高い管理', '月次レポート・グラフで成果を可視化\n何をやっているか全てわかります'),
        ('継続的なサポート', 'ご要望・疑問に迅速に対応\nLINE通知で常に最新状況を共有'),
    ]
    iw = (W - MR - SB_W - Inches(0.5)) / 3
    base_l = MR + SB_W + Inches(0.15)
    positions = [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1)]
    rh = (H - BODY_T - BOT - Inches(0.45)) / 2
    for i, (hdg, desc) in enumerate(items):
        col, row = positions[i]
        cx = base_l + iw * col
        cy = BODY_T + Inches(0.2) + rh * row
        box(s, cx, cy, iw - Inches(0.18), rh - Inches(0.12), T_MD if col==1 else T_DK, rnd=True)
        tb(s, cx + Inches(0.18), cy + Inches(0.15), iw - Inches(0.38),
           Inches(0.65), f'{i+1:02d}  {hdg}', 15, YLW, bold=True)
        tb(s, cx + Inches(0.18), cy + Inches(0.85), iw - Inches(0.38),
           rh - Inches(1.1), desc, 13, WHT)
    # 最後の1個（右下）
    cx2 = base_l + iw * 2
    cy2 = BODY_T + Inches(0.2) + rh
    box(s, cx2, cy2, iw - Inches(0.18), rh - Inches(0.12), T_LT, rnd=True)
    tb(s, cx2 + Inches(0.18), cy2 + Inches(0.15), iw - Inches(0.38),
       Inches(0.65), '05  継続的なサポート', 15, TXT, bold=True)
    tb(s, cx2 + Inches(0.18), cy2 + Inches(0.85), iw - Inches(0.38),
       rh - Inches(1.1), 'ご要望・疑問に迅速に対応\nLINE通知で常に最新状況を共有', 13, TXT)
    print('  slide 23: Plan Benefits ✓')
    return s

# ============================================================
# SLIDE 24: MEO対策で得られる成果
# ============================================================
def make_outcomes():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, 'MEO対策で得られる成果')
    outcomes = [
        ('集客力の向上', '来店意欲のあるユーザーに\nリーチし、新規顧客を\n継続的に獲得します', T_DK),
        ('業務の効率化', '煩雑な店舗管理を弊社が代行\n本業に集中できる\n環境を実現します', T_MD),
        ('ブランド価値の向上', '高評価と口コミが蓄積され\n顧客からの信頼と\nブランド力が高まります', T_LT),
        ('コスト削減', '継続的なMEO効果で\n広告依存度を軽減し\n費用対効果が向上します', YLW),
    ]
    ow = (W - MR - SB_W - Inches(0.5)) / 2
    rh = (H - BODY_T - BOT - Inches(0.4)) / 2
    base_l = MR + SB_W + Inches(0.15)
    pos = [(0,0),(1,0),(0,1),(1,1)]
    for i, ((col, row), (hdg, desc, c)) in enumerate(zip(pos, outcomes)):
        cx = base_l + ow * col
        cy = BODY_T + Inches(0.2) + rh * row
        box(s, cx, cy, ow - Inches(0.2), rh - Inches(0.15), c, rnd=True)
        tb(s, cx + Inches(0.2), cy + Inches(0.18), ow - Inches(0.42),
           Inches(0.65), f'0{i+1}  {hdg}', 18, WHT if c != YLW else TXT, bold=True)
        tb(s, cx + Inches(0.2), cy + Inches(0.9), ow - Inches(0.42),
           rh - Inches(1.1), desc, 14, WHT if c != YLW else TXT)
    print('  slide 24: Outcomes ✓')
    return s

# ============================================================
# SLIDE 25: 他社MEOとの圧倒的な違い（比較表）
# ============================================================
def make_comparison_table():
    s = ns()
    bg_solid(s, OWHT)
    std_header(s, '他社MEOとの圧倒的な違い')
    rows = [
        ('比較項目', '他社MEO対策', '当社MEO対策', True),
        ('可視化・透明性', '✕  不透明・レポート提出のみ', '◎  完全可視化（カレンダー・グラフ）', False),
        ('戦略性・運用', '△  作業重視（投稿代行がメイン）', '◎  AIで投稿し放題・キーワード戦略', False),
        ('AIの精度', '△  簡易な文章のみ', '◎  絵文字・口調など自由に選択可', False),
        ('投稿予約機能', '✕  予約機能なし', '◎  あり。1ヶ月分の投稿予約も可', False),
        ('LINE通知機能', '✕  通知機能なし', '◎  あり。新着口コミにすぐ対応可', False),
    ]
    table_l = MR + SB_W + Inches(0.15)
    table_w = W - table_l - MR
    col1 = table_w * 0.25
    col2 = table_w * 0.375
    col3 = table_w * 0.375
    row_h = (H - BODY_T - BOT - Inches(0.3)) / len(rows)
    for i, (item, other, ours, is_hdr) in enumerate(rows):
        ry = BODY_T + Inches(0.15) + row_h * i
        bg = T_DK if is_hdr else (OWHT if i % 2 == 0 else LGR)
        box(s, table_l, ry, col1, row_h - Inches(0.03),
            T_DK if is_hdr else (T_XL if False else OWHT), rnd=False)
        box(s, table_l + col1, ry, col2, row_h - Inches(0.03),
            T_DK if is_hdr else RGBColor(0xFF,0xF0,0xF0), rnd=False)
        box(s, table_l + col1 + col2, ry, col3, row_h - Inches(0.03),
            T_DK if is_hdr else RGBColor(0xE8,0xF8,0xF0), rnd=False)
        for j, (text, cx, cw) in enumerate([
            (item, table_l, col1),
            (other, table_l + col1, col2),
            (ours, table_l + col1 + col2, col3),
        ]):
            tc = WHT if is_hdr else (YLW if j == 2 and not is_hdr else TXT)
            tb(s, cx + Inches(0.1), ry + Inches(0.07), cw - Inches(0.2),
               row_h - Inches(0.15), text, 13 if not is_hdr else 14,
               tc, bold=is_hdr or j == 2)
    print('  slide 25: Comparison Table ✓')
    return s

# ============================================================
# SLIDE 26: まとめ / CTA
# ============================================================
def make_cta():
    s = ns()
    bg_grad(s, H_DK, H_MD, ang=0)
    box(s, 0, 0, W, Inches(0.07), YLW)
    box(s, 0, H - Inches(0.07), W, Inches(0.07), YLW)
    box(s, 0, 0, Inches(0.1), H, NVY)
    tb(s, MR, Inches(0.25), W - MR*2, Inches(1.0),
       'なぜ今、MEO対策なのか', 28, YLW, bold=True, align=PP_ALIGN.CENTER)
    box(s, MR, Inches(1.3), W - MR*2, Inches(0.06), WHT)
    points = [
        '✓  スマートフォン検索の約78%がGoogleを使用',
        '✓  「近くの○○」検索は年々増加し続けている',
        '✓  Googleマップ上位表示 = 24時間365日自動集客',
        '✓  競合他社がMEO対策を始める前に先行優位を確立',
    ]
    for i, p in enumerate(points):
        tb(s, MR + Inches(1.0), Inches(1.6) + Inches(0.75)*i, W - MR*2 - Inches(1.0),
           Inches(0.65), p, 17, WHT, bold=(i==3))
    box(s, MR*2, H*0.70, W - MR*4, H*0.22, WHT, rnd=True)
    tb(s, MR*2 + Inches(0.3), H*0.72, W - MR*4 - Inches(0.6), H*0.18,
       '今すぐ無料相談 — 貴店に最適なMEO戦略をご提案します',
       22, T_DK, bold=True, align=PP_ALIGN.CENTER)
    print('  slide 26: CTA ✓')
    return s

# ============================================================
# SLIDE 27: 最後のスライド
# ============================================================
def make_closing():
    s = ns()
    bg_solid(s, NVY)
    box(s, 0, 0, Inches(0.45), H, T_MD)
    box(s, 0, H - Inches(0.07), W, Inches(0.07), YLW)
    box(s, 0, 0, W, Inches(0.07), YLW)
    tb(s, Inches(0.7), Inches(1.0), W - Inches(1.2), Inches(1.2),
       'ご清聴ありがとうございました', 32, WHT, bold=True)
    box(s, Inches(0.7), Inches(2.4), W*0.4, Inches(0.05), T_LT)
    tb(s, Inches(0.7), Inches(2.6), W*0.6, Inches(0.7),
       'MEO対策で、あなたのお店を\nGoogleマップのTOPへ', 20, T_XL)
    tb(s, Inches(0.7), Inches(3.6), W*0.5, Inches(0.6),
       '📍 Googleビジネスプロフィール最適化', 14, YLW)
    tb(s, Inches(0.7), Inches(4.2), W*0.5, Inches(0.6),
       '🤖 AI口コミ返信・投稿自動化', 14, YLW)
    tb(s, Inches(0.7), Inches(4.8), W*0.5, Inches(0.6),
       '📊 月次レポート・前年比グラフ', 14, YLW)
    tb(s, Inches(0.7), Inches(5.4), W*0.5, Inches(0.6),
       '🔔 LINE通知で即時対応サポート', 14, YLW)
    print('  slide 27: Closing ✓')
    return s

# ============================================================
# BUILD ALL SLIDES
# ============================================================
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
