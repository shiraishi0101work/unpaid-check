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
$sections = $db->query("SELECT * FROM sections ORDER BY order_num ASC, id ASC")->fetchAll(PDO::FETCH_ASSOC);
$lastUpdated = $db->query("SELECT MAX(updated_at) FROM sections")->fetchColumn();
$sectionsJson = json_encode($sections, JSON_UNESCAPED_UNICODE);

// セクションごとのアイコン（順番に対応）
$icons = ['🖥️','🤖','👤','✏️','👁️','📚','📊','🔧','📋','⚙️','💡','📌','🔔','🎯','📝'];
$colors = ['#2563eb','#7c3aed','#059669','#d97706','#dc2626','#0891b2','#9333ea','#16a34a','#ea580c','#0284c7'];
?>
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AIブログマスター ご利用ガイド</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;}
body{font-family:'Hiragino Kaku Gothic ProN','Yu Gothic',sans-serif;background:#f0f4ff;color:#1e293b;min-height:100vh;display:flex;flex-direction:column;}

/* ─── ヘッダー ─── */
header{background:linear-gradient(135deg,#1e293b,#0f172a);color:#fff;height:60px;display:flex;align-items:center;justify-content:space-between;padding:0 24px;box-shadow:0 2px 12px rgba(0,0,0,.3);position:sticky;top:0;z-index:100;flex-shrink:0;}
.logo{display:flex;align-items:center;gap:10px;cursor:pointer;text-decoration:none;color:#fff;}
.logo-badge{background:linear-gradient(135deg,#2563eb,#0ea5e9);padding:5px 10px;border-radius:8px;font-size:.75rem;font-weight:800;letter-spacing:.5px;}
.logo-text{font-size:1rem;font-weight:700;}
.logo-sub{font-size:.75rem;color:#94a3b8;margin-left:6px;}
.header-right{display:flex;gap:10px;align-items:center;}
.btn{display:inline-flex;align-items:center;gap:6px;padding:8px 16px;border-radius:8px;border:none;cursor:pointer;font-size:.82rem;font-weight:600;transition:all .18s;text-decoration:none;white-space:nowrap;}
.btn-pdf{background:linear-gradient(135deg,#2563eb,#1d4ed8);color:#fff;}
.btn-pdf:hover{background:linear-gradient(135deg,#1d4ed8,#1e40af);transform:translateY(-1px);box-shadow:0 4px 12px rgba(37,99,235,.4);}
.btn-print{background:rgba(255,255,255,.12);color:#fff;border:1px solid rgba(255,255,255,.25);}
.btn-print:hover{background:rgba(255,255,255,.2);}
.btn-admin{background:rgba(255,255,255,.08);color:#94a3b8;border:1px solid rgba(255,255,255,.12);font-size:.75rem;padding:6px 12px;}
.btn-admin:hover{color:#fff;border-color:rgba(255,255,255,.3);}

/* ─── レイアウト ─── */
.layout{display:flex;flex:1;overflow:hidden;height:calc(100vh - 60px);}

/* ─── サイドバー ─── */
.sidebar{width:250px;flex-shrink:0;background:#1e293b;color:#94a3b8;display:flex;flex-direction:column;overflow-y:auto;overflow-x:hidden;}
.sidebar-home{padding:16px;border-bottom:1px solid rgba(255,255,255,.06);}
.sidebar-home-btn{display:flex;align-items:center;gap:8px;padding:10px 12px;border-radius:8px;cursor:pointer;transition:all .15s;color:#94a3b8;font-size:.85rem;font-weight:600;}
.sidebar-home-btn:hover,.sidebar-home-btn.active{background:rgba(37,99,235,.25);color:#60a5fa;}
.sidebar-title{padding:12px 16px 6px;font-size:.65rem;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:1px;}
.sidebar-item{display:flex;align-items:center;gap:10px;padding:10px 16px;cursor:pointer;transition:all .15s;border-left:3px solid transparent;font-size:.82rem;}
.sidebar-item:hover{background:rgba(255,255,255,.05);color:#e2e8f0;}
.sidebar-item.active{background:rgba(37,99,235,.2);border-left-color:#2563eb;color:#60a5fa;}
.sidebar-item-icon{width:28px;height:28px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:.9rem;flex-shrink:0;}
.sidebar-item-num{font-size:.65rem;font-weight:700;color:#475569;margin-left:auto;flex-shrink:0;}
.sidebar-footer{padding:16px;border-top:1px solid rgba(255,255,255,.06);margin-top:auto;}
.sidebar-footer-text{font-size:.7rem;color:#475569;text-align:center;line-height:1.6;}

/* ─── メインエリア ─── */
.main{flex:1;overflow-y:auto;display:flex;flex-direction:column;}

/* ─── ホームビュー ─── */
.hero{background:linear-gradient(135deg,#1e293b 0%,#1e40af 50%,#0ea5e9 100%);color:#fff;padding:48px 48px 40px;position:relative;overflow:hidden;}
.hero::before{content:'';position:absolute;top:-50%;right:-10%;width:500px;height:500px;background:radial-gradient(circle,rgba(255,255,255,.05) 0%,transparent 70%);pointer-events:none;}
.hero-badge{display:inline-flex;align-items:center;gap:6px;background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.2);padding:4px 12px;border-radius:20px;font-size:.72rem;font-weight:600;margin-bottom:16px;}
.hero h1{font-size:1.9rem;font-weight:800;margin-bottom:8px;line-height:1.3;}
.hero p{font-size:.88rem;color:rgba(255,255,255,.7);margin-bottom:20px;line-height:1.7;}
.hero-meta{display:flex;gap:16px;flex-wrap:wrap;}
.hero-meta-item{display:flex;align-items:center;gap:6px;background:rgba(255,255,255,.1);padding:6px 14px;border-radius:20px;font-size:.75rem;}

/* カードグリッド */
.cards-section{padding:32px 32px 40px;}
.cards-section-title{font-size:.75rem;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:1px;margin-bottom:20px;display:flex;align-items:center;gap:8px;}
.cards-section-title::after{content:'';flex:1;height:1px;background:#e2e8f0;}
.card-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:20px;}
.card{background:#fff;border-radius:16px;box-shadow:0 2px 12px rgba(0,0,0,.06);overflow:hidden;cursor:pointer;transition:all .2s;border:1px solid #e8edf5;}
.card:hover{transform:translateY(-4px);box-shadow:0 8px 32px rgba(0,0,0,.12);border-color:#2563eb;}
.card-header{height:80px;display:flex;align-items:center;padding:0 20px;gap:14px;position:relative;overflow:hidden;}
.card-header::after{content:'';position:absolute;right:-20px;top:50%;transform:translateY(-50%);width:100px;height:100px;border-radius:50%;background:rgba(255,255,255,.1);}
.card-icon{width:44px;height:44px;background:rgba(255,255,255,.2);border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:1.3rem;flex-shrink:0;backdrop-filter:blur(4px);}
.card-num{font-size:.65rem;font-weight:800;color:rgba(255,255,255,.6);letter-spacing:1px;}
.card-header-title{font-size:1rem;font-weight:700;color:#fff;line-height:1.3;}
.card-body{padding:18px 20px 20px;}
.card-desc{font-size:.82rem;color:#64748b;line-height:1.7;margin-bottom:14px;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;}
.card-footer{display:flex;align-items:center;justify-content:space-between;}
.card-updated{font-size:.7rem;color:#94a3b8;}
.card-link{font-size:.78rem;font-weight:700;color:#2563eb;display:flex;align-items:center;gap:4px;}
.card:hover .card-link{gap:8px;}

/* ─── 詳細ビュー ─── */
.detail-view{padding:32px 40px;max-width:880px;}
.breadcrumb{display:flex;align-items:center;gap:8px;font-size:.75rem;color:#94a3b8;margin-bottom:24px;}
.breadcrumb a{color:#2563eb;cursor:pointer;text-decoration:none;}
.breadcrumb a:hover{text-decoration:underline;}
.breadcrumb-sep{color:#cbd5e1;}
.detail-header{display:flex;align-items:flex-start;gap:16px;margin-bottom:28px;padding-bottom:24px;border-bottom:1px solid #e2e8f0;}
.detail-icon{width:56px;height:56px;border-radius:14px;display:flex;align-items:center;justify-content:center;font-size:1.6rem;flex-shrink:0;}
.detail-title-wrap{}
.detail-num{font-size:.65rem;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;}
.detail-title{font-size:1.6rem;font-weight:800;color:#1e293b;line-height:1.3;}
.detail-updated{font-size:.72rem;color:#94a3b8;margin-top:6px;}
.detail-content{font-size:.9rem;line-height:1.9;color:#374151;white-space:pre-wrap;}
.detail-content-box{background:#fff;border-radius:12px;padding:28px;box-shadow:0 2px 12px rgba(0,0,0,.05);border:1px solid #e8edf5;margin-bottom:24px;}
.detail-image{margin-top:24px;border-radius:12px;overflow:hidden;border:1px solid #e2e8f0;background:#fafafa;}
.detail-image img{width:100%;height:auto;display:block;}

/* ナビゲーション */
.detail-nav{display:flex;justify-content:space-between;gap:12px;margin-top:32px;padding-top:24px;border-top:1px solid #e2e8f0;}
.nav-btn{display:flex;align-items:center;gap:10px;padding:12px 20px;background:#fff;border:1px solid #e2e8f0;border-radius:10px;cursor:pointer;font-size:.82rem;font-weight:600;color:#475569;transition:all .18s;text-decoration:none;max-width:45%;}
.nav-btn:hover{border-color:#2563eb;color:#2563eb;background:#f0f4ff;}
.nav-btn.nav-prev .nav-text{text-align:left;}
.nav-btn.nav-next{margin-left:auto;}
.nav-btn.nav-next .nav-text{text-align:right;}
.nav-label{font-size:.65rem;color:#94a3b8;display:block;margin-bottom:2px;}
.nav-title{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:200px;}

/* 空状態 */
.empty-state{padding:80px 40px;text-align:center;color:#94a3b8;}
.empty-state-icon{font-size:3rem;margin-bottom:16px;}
.empty-state p{font-size:.9rem;line-height:1.8;}
.empty-state a{color:#2563eb;cursor:pointer;font-weight:600;}

/* ─── 印刷スタイル ─── */
@media print{
  .sidebar,.header-right,.detail-nav,header .btn-admin,header .btn-print{display:none!important;}
  .layout{height:auto!important;overflow:visible!important;}
  .main{overflow:visible!important;}
  body{background:#fff;}
  .detail-content-box{box-shadow:none;border:1px solid #ddd;}
  .card{break-inside:avoid;box-shadow:none;border:1px solid #ddd;}
}

/* スクロールバー */
::-webkit-scrollbar{width:5px;height:5px;}
::-webkit-scrollbar-track{background:transparent;}
::-webkit-scrollbar-thumb{background:#cbd5e1;border-radius:3px;}
</style>
</head>
<body>

<header>
  <a class="logo" onclick="showHome()" href="javascript:void(0)">
    <span class="logo-badge">AI-Blog</span>
    <span class="logo-text">AIブログマスター</span>
    <span class="logo-sub">ご利用ガイド</span>
  </a>
  <div class="header-right">
    <?php if(file_exists(__DIR__.'/guide.pdf')): ?>
    <a href="guide.pdf" download="AIブログマスター_ご利用ガイド.pdf" class="btn btn-pdf">⬇ PDF ダウンロード</a>
    <?php endif; ?>
    <button class="btn btn-print" onclick="window.print()">🖨 印刷</button>
    <a href="admin.php" class="btn btn-admin">⚙ 管理者</a>
  </div>
</header>

<div class="layout">

  <!-- ─── 左サイドバー ─── -->
  <aside class="sidebar">
    <div class="sidebar-home">
      <div class="sidebar-home-btn active" id="sidebar-home-btn" onclick="showHome()">
        🏠 ホーム（目次）
      </div>
    </div>
    <div class="sidebar-title">セクション</div>
    <div id="sidebar-nav"></div>
    <div class="sidebar-footer">
      <div class="sidebar-footer-text">
        <?php if($lastUpdated): ?>
        最終更新<br><?= date('Y年n月j日', strtotime($lastUpdated)) ?>
        <?php endif; ?>
      </div>
    </div>
  </aside>

  <!-- ─── メインコンテンツ ─── -->
  <main class="main" id="main">

    <!-- ホームビュー -->
    <div id="view-home">
      <div class="hero">
        <div class="hero-badge">📘 AIブログマスター</div>
        <h1>ご利用ガイド</h1>
        <p>AIを使ったWordPress自動投稿ツールの使い方をわかりやすく解説します。<br>各セクションをクリックして詳細をご確認ください。</p>
        <div class="hero-meta">
          <div class="hero-meta-item">📄 全 <?= count($sections) ?> セクション</div>
          <?php if($lastUpdated): ?>
          <div class="hero-meta-item">🕐 最終更新 <?= date('Y年n月j日', strtotime($lastUpdated)) ?></div>
          <?php endif; ?>
          <?php if(file_exists(__DIR__.'/guide.pdf')): ?>
          <div class="hero-meta-item">📥 PDFダウンロード対応</div>
          <?php endif; ?>
        </div>
      </div>

      <div class="cards-section">
        <?php if(empty($sections)): ?>
        <div class="empty-state">
          <div class="empty-state-icon">📭</div>
          <p>まだコンテンツがありません。<br>
          <a href="seed.php" target="_blank">初期データを投入する</a>か、
          <a href="admin.php">管理者ページ</a>からセクションを追加してください。</p>
        </div>
        <?php else: ?>
        <div class="cards-section-title">セクション一覧</div>
        <div class="card-grid" id="card-grid"></div>
        <?php endif; ?>
      </div>
    </div>

    <!-- 詳細ビュー -->
    <div id="view-detail" style="display:none;">
      <div class="detail-view" id="detail-content"></div>
    </div>

  </main>
</div>

<script>
const sections = <?= $sectionsJson ?>;
const icons    = <?= json_encode($icons) ?>;
const colors   = <?= json_encode($colors) ?>;

function getColor(i){ return colors[i % colors.length]; }
function getIcon(i){ return icons[i % icons.length]; }

// ─── サイドバー生成 ───
function renderSidebar(activeId){
  const nav = document.getElementById('sidebar-nav');
  nav.innerHTML = sections.map((s, i) => `
    <div class="sidebar-item${activeId===s.id?' active':''}" onclick="showSection(${s.id})">
      <div class="sidebar-item-icon" style="background:${getColor(i)}22;color:${getColor(i)}">${getIcon(i)}</div>
      <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${esc(s.title)}</span>
      <span class="sidebar-item-num">${i+1}</span>
    </div>`).join('');
}

// ─── カードグリッド生成 ───
function renderCards(){
  const grid = document.getElementById('card-grid');
  if(!grid) return;
  grid.innerHTML = sections.map((s, i) => {
    const desc = s.content.replace(/■.*\n?/g,'').replace(/・/g,'').replace(/\n+/g,' ').substring(0,80).trim() + '…';
    const updated = s.updated_at ? s.updated_at.substring(0,10) : '';
    return `
    <div class="card" onclick="showSection(${s.id})">
      <div class="card-header" style="background:linear-gradient(135deg,${getColor(i)},${getColor(i)}bb)">
        <div class="card-icon">${getIcon(i)}</div>
        <div>
          <div class="card-num">SECTION ${i+1}</div>
          <div class="card-header-title">${esc(s.title)}</div>
        </div>
      </div>
      <div class="card-body">
        <div class="card-desc">${esc(desc)}</div>
        <div class="card-footer">
          <span class="card-updated">${updated ? updated+' 更新' : ''}</span>
          <span class="card-link">詳細を見る →</span>
        </div>
      </div>
    </div>`;
  }).join('');
}

// ─── ホーム表示 ───
function showHome(){
  document.getElementById('view-home').style.display   = 'block';
  document.getElementById('view-detail').style.display = 'none';
  document.getElementById('sidebar-home-btn').classList.add('active');
  renderSidebar(null);
  document.getElementById('main').scrollTop = 0;
}

// ─── セクション詳細表示 ───
function showSection(id){
  const idx = sections.findIndex(s => s.id === id);
  if(idx < 0) return;
  const s    = sections[idx];
  const prev = sections[idx-1] || null;
  const next = sections[idx+1] || null;
  const color = getColor(idx);
  const icon  = getIcon(idx);

  const formattedContent = esc(s.content)
    .replace(/■\s(.+)/g, '<strong style="color:#1e293b;font-size:.95rem;">■ $1</strong>')
    .replace(/①|②|③|④|⑤|⑥|⑦|⑧|⑨|⑩/g, m => `<span style="background:${color};color:#fff;border-radius:50%;width:20px;height:20px;display:inline-flex;align-items:center;justify-content:center;font-size:.7rem;font-weight:700;margin-right:4px">${m}</span>`);

  const imgHtml = s.image_path
    ? `<div class="detail-image"><img src="${esc(s.image_path)}" alt="${esc(s.title)}"></div>` : '';

  const prevHtml = prev
    ? `<div class="nav-btn nav-prev" onclick="showSection(${prev.id})">
        ← <div class="nav-text"><span class="nav-label">前のセクション</span><span class="nav-title">${esc(prev.title)}</span></div>
       </div>` : '<div></div>';
  const nextHtml = next
    ? `<div class="nav-btn nav-next" onclick="showSection(${next.id})">
        <div class="nav-text"><span class="nav-label">次のセクション</span><span class="nav-title">${esc(next.title)}</span></div> →
       </div>` : '<div></div>';

  document.getElementById('detail-content').innerHTML = `
    <div class="breadcrumb">
      <a onclick="showHome()">🏠 ホーム</a>
      <span class="breadcrumb-sep">›</span>
      <span>${esc(s.title)}</span>
    </div>
    <div class="detail-header">
      <div class="detail-icon" style="background:${color}22;color:${color}">${icon}</div>
      <div class="detail-title-wrap">
        <div class="detail-num">SECTION ${idx+1} / ${sections.length}</div>
        <div class="detail-title">${esc(s.title)}</div>
        <div class="detail-updated">最終更新：${(s.updated_at||'').substring(0,16)}</div>
      </div>
    </div>
    <div class="detail-content-box">
      <div class="detail-content">${formattedContent}</div>
      ${imgHtml}
    </div>
    <div class="detail-nav">${prevHtml}${nextHtml}</div>`;

  document.getElementById('view-home').style.display   = 'none';
  document.getElementById('view-detail').style.display = 'block';
  document.getElementById('sidebar-home-btn').classList.remove('active');
  renderSidebar(id);
  document.getElementById('main').scrollTop = 0;
}

function esc(s){
  return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// 初期化
renderSidebar(null);
renderCards();
</script>
</body>
</html>
