<?php
$db = new PDO('sqlite:' . __DIR__ . '/manual.db');
$db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
$db->exec("CREATE TABLE IF NOT EXISTS sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT,
    image_path TEXT,
    order_num INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime'))
)");
$sections      = $db->query("SELECT * FROM sections ORDER BY order_num ASC, id ASC")->fetchAll(PDO::FETCH_ASSOC);
$lastUpdated   = $db->query("SELECT MAX(updated_at) FROM sections")->fetchColumn();
$sectionsJson  = json_encode($sections, JSON_UNESCAPED_UNICODE);
$sectionCount  = count($sections);
?>
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0">
<title>AIブログマスター ご利用ガイド | AI-BlogMaster</title>

<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Zen+Maru+Gothic:wght@700&family=Noto+Sans+JP:wght@400;500;700&display=swap" rel="stylesheet">

<style>
/* ============================================================
   リセット & 基本設定
   ============================================================ */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html { font-size: 62.5%; }

body {
  font-family: 'Noto Sans JP', 'Hiragino Kaku Gothic ProN', 'ヒラギノ角ゴ ProN', sans-serif;
  font-size: 1.5rem;
  color: #4D4D4D;
  background: #dcf4fd;
  min-height: 100vh;
  line-height: 1.8;
}

a { color: inherit; text-decoration: none; }
img { max-width: 100%; display: block; }

/* ============================================================
   サイト全体のラッパー
   ============================================================ */
#guide-wrapper {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

/* ============================================================
   ヘッダー
   ============================================================ */
#guide-header {
  background: #00408b;
  position: sticky;
  top: 0;
  z-index: 200;
  box-shadow: 0 2px 10px rgba(0,0,0,0.25);
}

.guide-header-inner {
  max-width: 134.2rem;
  margin: 0 auto;
  padding: 0 2rem;
  height: 6rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 2rem;
}

.guide-logo {
  display: flex;
  align-items: center;
  gap: 1.2rem;
  cursor: pointer;
}

.guide-logo-mark {
  width: 3.6rem;
  height: 3.6rem;
  background: #fa672b;
  border-radius: 0.8rem;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.guide-logo-mark svg { width: 2rem; height: 2rem; fill: #fff; }

.guide-logo-text {
  font-family: 'Zen Maru Gothic', sans-serif;
  font-size: 1.8rem;
  font-weight: 700;
  color: #fff;
  line-height: 1.2;
}

.guide-logo-sub {
  font-size: 1.1rem;
  color: rgba(255,255,255,0.6);
  font-weight: 400;
  margin-top: 0.2rem;
}

.guide-header-actions {
  display: flex;
  align-items: center;
  gap: 1.2rem;
  flex-shrink: 0;
}

/* ボタン共通 */
.btn {
  display: inline-flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.9rem 1.8rem;
  border-radius: 0.6rem;
  border: none;
  cursor: pointer;
  font-size: 1.3rem;
  font-weight: 700;
  font-family: inherit;
  line-height: 1;
  transition: opacity 0.15s, transform 0.15s;
  white-space: nowrap;
}
.btn:hover { opacity: 0.85; transform: translateY(-1px); }
.btn:active { transform: translateY(0); }

.btn-orange {
  background: #fa672b;
  color: #fff;
}

.btn-ghost {
  background: rgba(255,255,255,0.12);
  color: rgba(255,255,255,0.75);
  border: 1px solid rgba(255,255,255,0.2);
  font-size: 1.2rem;
  padding: 0.7rem 1.4rem;
}

/* ============================================================
   メインレイアウト（サイドバー + コンテンツ）
   ============================================================ */
#guide-body {
  display: flex;
  flex: 1;
  max-width: 134.2rem;
  margin: 0 auto;
  width: 100%;
  padding: 0 2rem;
  gap: 3rem;
  align-items: flex-start;
}

/* ============================================================
   左サイドバー
   ============================================================ */
#guide-sidebar {
  width: 26rem;
  flex-shrink: 0;
  position: sticky;
  top: 6rem;
  max-height: calc(100vh - 6rem);
  overflow-y: auto;
  padding: 2rem 0 4rem;
}

.sidebar-section-label {
  font-size: 1.1rem;
  font-weight: 700;
  color: #00408b;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  padding: 0 1rem 0.8rem;
  border-bottom: 2px solid #00408b;
  margin-bottom: 0.8rem;
}

.sidebar-home-btn {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1.2rem 1.4rem;
  border-radius: 0.6rem;
  cursor: pointer;
  font-size: 1.4rem;
  font-weight: 700;
  color: #00408b;
  transition: background 0.15s;
  margin-bottom: 1.6rem;
}
.sidebar-home-btn:hover { background: rgba(0,64,139,0.08); }
.sidebar-home-btn.active { background: #00408b; color: #fff; }

.sidebar-home-btn svg { width: 1.6rem; height: 1.6rem; flex-shrink: 0; }

.sidebar-nav-item {
  display: flex;
  align-items: center;
  gap: 1.2rem;
  padding: 1.1rem 1.4rem;
  border-radius: 0.6rem;
  cursor: pointer;
  font-size: 1.3rem;
  color: #4D4D4D;
  transition: background 0.15s;
  margin-bottom: 0.2rem;
  border-left: 3px solid transparent;
}
.sidebar-nav-item:hover { background: rgba(0,64,139,0.06); color: #00408b; }
.sidebar-nav-item.active {
  background: rgba(0,64,139,0.08);
  border-left-color: #00408b;
  color: #00408b;
  font-weight: 700;
}

.sidebar-num {
  width: 2.4rem;
  height: 2.4rem;
  border-radius: 50%;
  background: #e0ecf8;
  color: #00408b;
  font-size: 1.1rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.sidebar-nav-item.active .sidebar-num {
  background: #00408b;
  color: #fff;
}

.sidebar-nav-title {
  flex: 1;
  line-height: 1.4;
}

/* ============================================================
   メインコンテンツ
   ============================================================ */
#guide-main {
  flex: 1;
  min-width: 0;
  padding: 3rem 0 6rem;
}

/* ============================================================
   ヒーローエリア（TOPページ）
   ============================================================ */
.guide-hero {
  background: #fff;
  border-radius: 1.2rem;
  overflow: hidden;
  margin-bottom: 3rem;
  box-shadow: 0 2px 16px rgba(0,64,139,0.10);
}

.guide-hero-top {
  background: linear-gradient(135deg, #00408b 0%, #0062d4 100%);
  padding: 4rem 4rem 3.6rem;
  color: #fff;
  position: relative;
  overflow: hidden;
}

.guide-hero-top::after {
  content: '';
  position: absolute;
  right: -6rem;
  top: -6rem;
  width: 28rem;
  height: 28rem;
  border-radius: 50%;
  background: rgba(255,255,255,0.05);
  pointer-events: none;
}

.guide-hero-label {
  display: inline-block;
  background: #fa672b;
  color: #fff;
  font-size: 1.1rem;
  font-weight: 700;
  padding: 0.4rem 1.2rem;
  border-radius: 2rem;
  margin-bottom: 1.4rem;
  letter-spacing: 0.05em;
}

.guide-hero-title {
  font-family: 'Zen Maru Gothic', sans-serif;
  font-size: 3rem;
  font-weight: 700;
  line-height: 1.35;
  margin-bottom: 1.2rem;
}

.guide-hero-desc {
  font-size: 1.4rem;
  color: rgba(255,255,255,0.8);
  line-height: 1.8;
  max-width: 60rem;
}

.guide-hero-bottom {
  padding: 2rem 4rem;
  display: flex;
  align-items: center;
  gap: 3rem;
  background: #f5faff;
  border-top: 1px solid #e0ecf8;
}

.guide-hero-stat {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  font-size: 1.3rem;
  color: #00408b;
  font-weight: 500;
}

.guide-hero-stat-num {
  font-family: 'Zen Maru Gothic', sans-serif;
  font-size: 2.4rem;
  font-weight: 700;
  color: #00408b;
}

.guide-hero-divider {
  width: 1px;
  height: 3rem;
  background: #ccddf0;
}

/* ============================================================
   セクションカードグリッド
   ============================================================ */
.cards-label {
  font-size: 1.2rem;
  font-weight: 700;
  color: #00408b;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  margin-bottom: 1.6rem;
  display: flex;
  align-items: center;
  gap: 1.2rem;
}

.cards-label::after {
  content: '';
  flex: 1;
  height: 1px;
  background: rgba(0,64,139,0.2);
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(28rem, 1fr));
  gap: 2rem;
}

.card {
  background: #fff;
  border-radius: 1.2rem;
  overflow: hidden;
  cursor: pointer;
  box-shadow: 0 2px 12px rgba(0,64,139,0.08);
  border: 1px solid #e0ecf8;
  transition: transform 0.2s, box-shadow 0.2s;
}

.card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 28px rgba(0,64,139,0.16);
  border-color: #00408b;
}

.card-top {
  background: #00408b;
  padding: 2rem 2.2rem 1.8rem;
  display: flex;
  align-items: flex-start;
  gap: 1.4rem;
}

.card-num-badge {
  background: rgba(255,255,255,0.15);
  color: #fff;
  font-size: 1.1rem;
  font-weight: 700;
  padding: 0.4rem 0.9rem;
  border-radius: 0.4rem;
  letter-spacing: 0.05em;
  flex-shrink: 0;
  margin-top: 0.2rem;
}

.card-header-title {
  font-family: 'Zen Maru Gothic', sans-serif;
  font-size: 1.7rem;
  font-weight: 700;
  color: #fff;
  line-height: 1.4;
}

.card-body {
  padding: 1.8rem 2.2rem 2rem;
}

.card-desc {
  font-size: 1.3rem;
  color: #666;
  line-height: 1.75;
  margin-bottom: 1.6rem;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-action {
  display: flex;
  align-items: center;
  justify-content: flex-end;
}

.card-action-link {
  font-size: 1.3rem;
  font-weight: 700;
  color: #00408b;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.card:hover .card-action-link { color: #fa672b; }

.card-action-arrow {
  width: 1.6rem;
  height: 1.6rem;
  transition: transform 0.15s;
}
.card:hover .card-action-arrow { transform: translateX(4px); }

/* ============================================================
   詳細ビュー
   ============================================================ */
.detail-wrap {
  background: #fff;
  border-radius: 1.2rem;
  overflow: hidden;
  box-shadow: 0 2px 16px rgba(0,64,139,0.10);
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  font-size: 1.25rem;
  color: #888;
  padding: 1.8rem 4rem;
  border-bottom: 1px solid #f0f5fa;
  background: #fafcff;
}

.breadcrumb-home {
  color: #00408b;
  cursor: pointer;
  font-weight: 500;
}
.breadcrumb-home:hover { text-decoration: underline; }

.breadcrumb-sep { color: #ccc; }

.detail-header {
  background: linear-gradient(135deg, #00408b 0%, #0062d4 100%);
  padding: 4rem 4rem 3.6rem;
  color: #fff;
  position: relative;
  overflow: hidden;
}

.detail-header::after {
  content: '';
  position: absolute;
  right: -4rem;
  bottom: -4rem;
  width: 20rem;
  height: 20rem;
  border-radius: 50%;
  background: rgba(255,255,255,0.05);
  pointer-events: none;
}

.detail-section-label {
  font-size: 1.15rem;
  font-weight: 700;
  color: rgba(255,255,255,0.6);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  margin-bottom: 1rem;
}

.detail-title {
  font-family: 'Zen Maru Gothic', sans-serif;
  font-size: 2.6rem;
  font-weight: 700;
  line-height: 1.35;
  margin-bottom: 1rem;
}

.detail-updated {
  font-size: 1.2rem;
  color: rgba(255,255,255,0.5);
}

.detail-num-badge {
  position: absolute;
  right: 4rem;
  top: 50%;
  transform: translateY(-50%);
  font-family: 'Zen Maru Gothic', sans-serif;
  font-size: 8rem;
  font-weight: 700;
  color: rgba(255,255,255,0.07);
  line-height: 1;
  user-select: none;
}

/* コンテンツ本文 */
.detail-content-area {
  padding: 4rem;
}

.detail-content {
  font-size: 1.5rem;
  line-height: 2;
  color: #4D4D4D;
  white-space: pre-wrap;
  word-break: break-word;
}

.detail-content .content-heading {
  display: block;
  font-weight: 700;
  color: #00408b;
  font-size: 1.6rem;
  margin-top: 2.8rem;
  margin-bottom: 0.6rem;
  padding-bottom: 0.6rem;
  border-bottom: 2px solid #e0ecf8;
}

.detail-content .content-heading:first-child { margin-top: 0; }

.detail-image {
  margin-top: 3.2rem;
  border-radius: 0.8rem;
  overflow: hidden;
  border: 1px solid #e0ecf8;
}

/* ページナビゲーション */
.detail-nav {
  display: flex;
  justify-content: space-between;
  gap: 2rem;
  padding: 2.4rem 4rem;
  border-top: 1px solid #f0f5fa;
  background: #fafcff;
}

.nav-btn {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1.4rem 2rem;
  background: #fff;
  border: 1px solid #e0ecf8;
  border-radius: 0.8rem;
  cursor: pointer;
  font-size: 1.3rem;
  color: #4D4D4D;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
  max-width: 46%;
  font-family: inherit;
  font-weight: 500;
  text-align: left;
}

.nav-btn:hover {
  border-color: #00408b;
  color: #00408b;
  background: #f0f5fa;
}

.nav-btn-next { margin-left: auto; text-align: right; }

.nav-btn-label {
  display: block;
  font-size: 1.1rem;
  color: #999;
  font-weight: 400;
  margin-bottom: 0.3rem;
}

.nav-btn-title {
  display: block;
  font-weight: 700;
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 24rem;
}

.nav-btn svg {
  width: 2rem;
  height: 2rem;
  flex-shrink: 0;
  color: #ccc;
}

.nav-btn:hover svg { color: #00408b; }

/* ============================================================
   空状態
   ============================================================ */
.empty-state {
  text-align: center;
  padding: 8rem 4rem;
  color: #999;
}

.empty-state p {
  font-size: 1.5rem;
  line-height: 1.8;
  margin-top: 1.6rem;
}

.empty-state a {
  color: #00408b;
  font-weight: 700;
}
.empty-state a:hover { text-decoration: underline; }

/* ============================================================
   スクロールバー
   ============================================================ */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #ccddf0; border-radius: 3px; }

/* ============================================================
   印刷スタイル
   ============================================================ */
@media print {
  #guide-header,
  #guide-sidebar,
  .detail-nav,
  .guide-header-actions,
  .guide-hero-bottom .btn { display: none !important; }

  #guide-body { padding: 0; max-width: 100%; }
  #guide-main { padding: 2rem 0; }
  .detail-wrap { box-shadow: none; border: 1px solid #ddd; }
  body { background: #fff; }
}

/* ============================================================
   レスポンシブ（タブレット以下）
   ============================================================ */
@media all and (max-width: 900px) {
  #guide-sidebar { display: none; }
  #guide-body { padding: 0 1.6rem; gap: 0; }
  .card-grid { grid-template-columns: 1fr; }
  .guide-hero-top { padding: 3rem 2.4rem; }
  .guide-hero-title { font-size: 2.4rem; }
  .guide-hero-bottom { flex-wrap: wrap; padding: 1.6rem 2.4rem; gap: 1.2rem; }
  .detail-header { padding: 3rem 2.4rem; }
  .detail-num-badge { display: none; }
  .detail-content-area { padding: 2.4rem; }
  .breadcrumb { padding: 1.4rem 2.4rem; }
  .detail-nav { padding: 2rem 2.4rem; }
  .guide-header-inner { padding: 0 1.6rem; }
  .guide-logo-text { font-size: 1.6rem; }
}
</style>
</head>
<body>

<div id="guide-wrapper">

  <!-- ヘッダー -->
  <header id="guide-header">
    <div class="guide-header-inner">

      <div class="guide-logo" onclick="showHome()">
        <div class="guide-logo-mark">
          <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
          </svg>
        </div>
        <div>
          <div class="guide-logo-text">AI-BlogMaster</div>
          <div class="guide-logo-sub">ご利用ガイド</div>
        </div>
      </div>

      <div class="guide-header-actions">
        <?php if (file_exists(__DIR__ . '/guide.pdf')): ?>
        <a href="guide.pdf" download="AIブログマスター_ご利用ガイド.pdf" class="btn btn-orange">
          PDF ダウンロード
        </a>
        <?php endif; ?>
        <button class="btn btn-ghost" onclick="window.print()">印刷</button>
        <a href="admin.php" class="btn btn-ghost">管理者</a>
      </div>

    </div>
  </header>

  <!-- メインレイアウト -->
  <div id="guide-body">

    <!-- 左サイドバー -->
    <aside id="guide-sidebar">
      <div class="sidebar-home-btn active" id="sidebar-home-btn" onclick="showHome()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>
          <polyline points="9 22 9 12 15 12 15 22"/>
        </svg>
        ホーム（目次）
      </div>
      <div class="sidebar-section-label">セクション</div>
      <nav id="sidebar-nav"></nav>
    </aside>

    <!-- コンテンツエリア -->
    <main id="guide-main">

      <!-- TOPページ -->
      <div id="view-home">

        <div class="guide-hero">
          <div class="guide-hero-top">
            <div class="guide-hero-label">AI-BlogMaster</div>
            <h1 class="guide-hero-title">ご利用ガイド</h1>
            <p class="guide-hero-desc">
              AIを使ったWordPress自動投稿ツールの使い方を解説します。<br>
              各セクションを選択して詳細をご確認ください。
            </p>
          </div>
          <div class="guide-hero-bottom">
            <div class="guide-hero-stat">
              <span class="guide-hero-stat-num"><?= $sectionCount ?></span>
              <span>セクション</span>
            </div>
            <div class="guide-hero-divider"></div>
            <?php if ($lastUpdated): ?>
            <div class="guide-hero-stat">
              最終更新：<?= date('Y年n月j日', strtotime($lastUpdated)) ?>
            </div>
            <?php endif; ?>
            <?php if (file_exists(__DIR__ . '/guide.pdf')): ?>
            <div class="guide-hero-divider"></div>
            <div class="guide-hero-stat">PDF ダウンロード対応</div>
            <?php endif; ?>
          </div>
        </div>

        <?php if (empty($sections)): ?>
        <div class="empty-state">
          <p>
            まだコンテンツがありません。<br>
            <a href="seed.php" target="_blank">初期データを投入する</a> か、
            <a href="admin.php">管理者ページ</a> からセクションを追加してください。
          </p>
        </div>
        <?php else: ?>
        <div class="cards-label">セクション一覧</div>
        <div class="card-grid" id="card-grid"></div>
        <?php endif; ?>

      </div><!-- /view-home -->

      <!-- 詳細ページ -->
      <div id="view-detail" style="display:none;">
        <div class="detail-wrap" id="detail-content"></div>
      </div>

    </main><!-- /guide-main -->

  </div><!-- /guide-body -->

</div><!-- /guide-wrapper -->

<script>
const sections = <?= $sectionsJson ?>;

/* ─── サイドバー生成 ─── */
function renderSidebar(activeId) {
  const nav = document.getElementById('sidebar-nav');
  const homBtn = document.getElementById('sidebar-home-btn');
  homBtn.classList.toggle('active', activeId === null);

  nav.innerHTML = sections.map((s, i) => `
    <div class="sidebar-nav-item${activeId === s.id ? ' active' : ''}" onclick="showSection(${s.id})">
      <span class="sidebar-num">${i + 1}</span>
      <span class="sidebar-nav-title">${esc(s.title)}</span>
    </div>
  `).join('');
}

/* ─── カードグリッド生成 ─── */
function renderCards() {
  const grid = document.getElementById('card-grid');
  if (!grid) return;

  grid.innerHTML = sections.map((s, i) => {
    const raw  = s.content || '';
    const desc = raw.replace(/■\s?[^\n]*/g, '').replace(/[・①②③④⑤⑥⑦⑧⑨⑩]/g, '').replace(/\n+/g, ' ').trim().substring(0, 90) + '…';
    return `
    <div class="card" onclick="showSection(${s.id})">
      <div class="card-top">
        <span class="card-num-badge">0${i + 1 < 10 ? i + 1 : i + 1}</span>
        <span class="card-header-title">${esc(s.title)}</span>
      </div>
      <div class="card-body">
        <p class="card-desc">${esc(desc)}</p>
        <div class="card-action">
          <span class="card-action-link">
            詳細を見る
            <svg class="card-action-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <line x1="5" y1="12" x2="19" y2="12"/>
              <polyline points="12 5 19 12 12 19"/>
            </svg>
          </span>
        </div>
      </div>
    </div>`;
  }).join('');
}

/* ─── ホーム表示 ─── */
function showHome() {
  document.getElementById('view-home').style.display   = 'block';
  document.getElementById('view-detail').style.display = 'none';
  renderSidebar(null);
  document.getElementById('guide-main').scrollTop = 0;
  window.scrollTo(0, 0);
}

/* ─── セクション詳細表示 ─── */
function showSection(id) {
  const idx  = sections.findIndex(s => s.id === id);
  if (idx < 0) return;
  const s    = sections[idx];
  const prev = sections[idx - 1] || null;
  const next = sections[idx + 1] || null;

  /* 本文フォーマット：■ 見出しを強調 */
  const formatted = esc(s.content || '')
    .replace(/■\s?([^\n]+)/g, '<span class="content-heading">■ $1</span>');

  const imgHtml = s.image_path
    ? `<div class="detail-image"><img src="${esc(s.image_path)}" alt="${esc(s.title)}"></div>` : '';

  const prevHtml = prev ? `
    <button class="nav-btn" onclick="showSection(${prev.id})">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="19" y1="12" x2="5" y2="12"/>
        <polyline points="12 19 5 12 12 5"/>
      </svg>
      <div>
        <span class="nav-btn-label">前のセクション</span>
        <span class="nav-btn-title">${esc(prev.title)}</span>
      </div>
    </button>` : '<div></div>';

  const nextHtml = next ? `
    <button class="nav-btn nav-btn-next" onclick="showSection(${next.id})">
      <div>
        <span class="nav-btn-label">次のセクション</span>
        <span class="nav-btn-title">${esc(next.title)}</span>
      </div>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="5" y1="12" x2="19" y2="12"/>
        <polyline points="12 5 19 12 12 19"/>
      </svg>
    </button>` : '<div></div>';

  document.getElementById('detail-content').innerHTML = `
    <div class="breadcrumb">
      <span class="breadcrumb-home" onclick="showHome()">ホーム</span>
      <span class="breadcrumb-sep">›</span>
      <span>${esc(s.title)}</span>
    </div>
    <div class="detail-header">
      <div class="detail-section-label">SECTION ${idx + 1} / ${sections.length}</div>
      <h2 class="detail-title">${esc(s.title)}</h2>
      <div class="detail-updated">最終更新：${(s.updated_at || '').substring(0, 16)}</div>
      <div class="detail-num-badge">${idx + 1}</div>
    </div>
    <div class="detail-content-area">
      <div class="detail-content">${formatted}</div>
      ${imgHtml}
    </div>
    <div class="detail-nav">${prevHtml}${nextHtml}</div>`;

  document.getElementById('view-home').style.display   = 'none';
  document.getElementById('view-detail').style.display = 'block';
  renderSidebar(id);
  window.scrollTo(0, 0);
}

function esc(s) {
  return (s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

/* 初期化 */
renderSidebar(null);
renderCards();
</script>
</body>
</html>
