<?php
header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');

$url = $_GET['url'] ?? '';
if (!$url || !filter_var($url, FILTER_VALIDATE_URL)) {
    echo json_encode(['error' => 'invalid url']); exit;
}

// curlでページ取得
$ch = curl_init($url);
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_FOLLOWLOCATION => true,
    CURLOPT_MAXREDIRS      => 5,
    CURLOPT_TIMEOUT        => 15,
    CURLOPT_SSL_VERIFYPEER => false,
    CURLOPT_ENCODING       => '',
    CURLOPT_USERAGENT      => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    CURLOPT_HTTPHEADER     => [
        'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language: ja,en-US;q=0.9,en;q=0.8',
    ],
]);
$html = curl_exec($ch);
$httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);

if (!$html || $httpCode >= 400) {
    echo json_encode(['error' => 'fetch failed', 'code' => $httpCode]); exit;
}

// &yen; → ¥ に変換
$html = str_replace('&yen;', '¥', $html);
// 文字コード変換
if (preg_match('/charset=["\']?(shift.jis|sjis|euc-jp)/i', $html, $m)) {
    $from = stripos($m[1],'euc') !== false ? 'EUC-JP' : 'SJIS-win';
    $conv = @iconv($from, 'UTF-8//IGNORE', $html);
    if ($conv) $html = $conv;
}

$host = strtolower(parse_url($url, PHP_URL_HOST) ?: '');

// --- メタタグ取得（正規表現ベース、DOMDocument不使用） ---
function getMeta($html, $patterns) {
    foreach ($patterns as $pat) {
        if (preg_match($pat, $html, $m)) {
            $v = html_entity_decode(trim($m[1]), ENT_QUOTES, 'UTF-8');
            if ($v) return $v;
        }
    }
    return '';
}

function getPrice($html, $patterns) {
    foreach ($patterns as $pat) {
        if (preg_match($pat, $html, $m)) {
            $p = preg_replace('/[^\d]/', '', $m[1]);
            if ($p && (int)$p > 0) return (int)$p;
        }
    }
    return 0;
}

$name  = '';
$price = 0;
$shop  = '';
$brand = '';
$memo  = '';

// ===== OGP（共通） =====
$ogTitle = getMeta($html, [
    '/property=["\']og:title["\'][^>]*content=["\']([^"\']+)/i',
    '/content=["\']([^"\']{5,})["\'][^>]*property=["\']og:title/i',
    '/<meta[^>]+og:title[^>]+content=["\']([^"\']+)/i',
]);
$ogPrice = getMeta($html, [
    '/property=["\'](?:og|product):price:amount["\'][^>]*content=["\']([^"\']+)/i',
    '/content=["\']([^"\']+)["\'][^>]*property=["\'](?:og|product):price:amount/i',
]);
$ogBrand = getMeta($html, [
    '/property=["\']og:brand["\'][^>]*content=["\']([^"\']+)/i',
    '/itemprop=["\']brand["\'][^>]*content=["\']([^"\']+)/i',
]);
$ogDesc = getMeta($html, [
    '/property=["\']og:description["\'][^>]*content=["\']([^"\']+)/i',
    '/content=["\']([^"\']+)["\'][^>]*property=["\']og:description/i',
    '/name=["\']description["\'][^>]*content=["\']([^"\']+)/i',
]);

// ===== サイト別 =====

if (strpos($host, 'amazon') !== false) {
    $shop  = 'Amazon';
    if (preg_match('/id=["\']productTitle["\'][^>]*>\s*([^<]+)</i', $html, $m)) $name = trim($m[1]);
    $price = getPrice($html, [
        '/class=["\'][^"\']*a-price-whole[^"\']*["\'][^>]*>([\d,]+)/i',
        '/id=["\']priceblock_ourprice["\'][^>]*>[^¥¥]*[¥￥]\s*([\d,]+)/i',
    ]);

} elseif (strpos($host, 'e-trend') !== false) {
    $shop  = 'イートレンド';
    $name  = $ogTitle;
    // ¥数字（カンマ区切り）の最初のものを価格とする
    if (preg_match('/¥\s*([\d,]+)/', $html, $m)) {
        $price = (int)str_replace(',', '', $m[1]);
    }
    // JSON-LDから
    if (!$price && preg_match('/"price"\s*:\s*"?([\d]+)"?/', $html, $m)) {
        $price = (int)$m[1];
    }
    // ブランド：タイトル「e-TREND｜Brand ProductName」の最初の単語
    if (!$brand) {
        if (preg_match('/<title[^>]*>[^|｜]*[|｜]\s*(\S+)/u', $html, $m)) {
            $brand = html_entity_decode($m[1], ENT_QUOTES, 'UTF-8');
        }
    }

} elseif (strpos($host, 'rakuten') !== false) {
    $shop  = '楽天市場';
    $name  = $ogTitle;
    $price = getPrice($html, ['/class=["\'][^"\']*price[^"\']*["\'][^>]*>[^¥¥]*[¥￥]\s*([\d,]+)/i']);

} elseif (strpos($host, 'yahoo') !== false) {
    $shop  = 'Yahoo!ショッピング';
    $name  = $ogTitle;
    $price = getPrice($html, ['/class=["\'][^"\']*price[^"\']*["\'][^>]*>[^¥¥]*[¥￥]\s*([\d,]+)/i']);

} elseif (strpos($host, 'yodobashi') !== false) {
    $shop  = 'ヨドバシカメラ';
    if (preg_match('/class=["\'][^"\']*pName[^"\']*["\'][^>]*>\s*([^<]+)</i', $html, $m)) $name = trim($m[1]);
    $price = getPrice($html, ['/class=["\'][^"\']*(?:selling_price|yprice)[^"\']*["\'][^>]*>[^¥¥]*[¥￥]\s*([\d,]+)/i']);

} elseif (strpos($host, 'monotaro') !== false) {
    $shop  = 'MonotaRO';
    $name  = $ogTitle;
    if (preg_match('/itemprop=["\']price["\'][^>]*content=["\']([^"\']+)/i', $html, $m)) $price = (int)$m[1];

} elseif (strpos($host, 'biccamera') !== false) {
    $shop = 'ビックカメラ';
    $name = $ogTitle;
    $price = getPrice($html, ['/¥\s*([\d,]+)/']);

} elseif (strpos($host, 'joshin') !== false) {
    $shop = 'ジョーシン';
    $name = $ogTitle;
    $price = getPrice($html, ['/¥\s*([\d,]+)/']);
}

// ===== 税込/税抜のサイト別デフォルト =====
// inclusive=税込, exclusive=税抜
$priceTypeMap = [
    'monotaro'   => 'exclusive',  // MonotaROは税抜表示が多い
    'askul'      => 'exclusive',  // ASKULは税抜表示
    'misumi'     => 'exclusive',
    'amazon'     => 'inclusive',
    'rakuten'    => 'inclusive',
    'yahoo'      => 'inclusive',
    'yodobashi'  => 'inclusive',
    'e-trend'    => 'inclusive',
    'biccamera'  => 'inclusive',
    'joshin'     => 'inclusive',
    'edion'      => 'inclusive',
    'sofmap'     => 'inclusive',
    'nojima'     => 'inclusive',
    'yamada'     => 'inclusive',
];
$priceType = 'inclusive'; // デフォルト
foreach ($priceTypeMap as $k => $v) {
    if (strpos($host, $k) !== false) { $priceType = $v; break; }
}

// HTMLの価格周辺テキストで「税抜」「税込」を検出して上書き
if ($price > 0 && preg_match('/¥\s*[\d,]+/', $html, $pm0, PREG_OFFSET_CAPTURE)) {
    $pos  = $pm0[0][1];
    $ctx  = strip_tags(substr($html, max(0, $pos - 300), 600));
    if (preg_match('/税抜|本体価格|\+税|\+ 税|＋税|excluding tax/u', $ctx)) {
        $priceType = 'exclusive';
    } elseif (preg_match('/税込|税込み|込み|including tax/u', $ctx)) {
        $priceType = 'inclusive';
    }
}

// ===== 汎用フォールバック =====
if (!$name) $name = $ogTitle;
if (!$name && preg_match('/<title[^>]*>([^<]+)<\/title>/i', $html, $m)) {
    $name = html_entity_decode(trim($m[1]), ENT_QUOTES, 'UTF-8');
    $name = preg_replace('/\s*[\|\-–｜]\s*.{0,30}$/', '', $name);
}
if (!$price && $ogPrice) $price = (int)preg_replace('/[^\d]/', '', $ogPrice);
if (!$price && preg_match('/"price"\s*:\s*"?([\d]+)"?/', $html, $m)) $price = (int)$m[1];
if (!$price && preg_match('/¥\s*([\d,]+)/', $html, $m)) $price = (int)str_replace(',', '', $m[1]);
// 「数字円」形式の価格（¥表記がないサイト用）
if (!$price) {
    // 「税込」「販売価格」「価格」近辺の 数字円 を優先取得
    $plainText = strip_tags($html);
    if (preg_match('/(?:販売価格|税込(?:価格)?|ご購入価格|割引価格)[^\d]{0,20}([\d,]+)\s*円/u', $plainText, $m)) {
        $price = (int)str_replace(',', '', $m[1]);
        $priceType = 'inclusive';
    } elseif (preg_match('/([\d,]{4,})\s*円(?:\s*（?税込)?）?/u', $plainText, $m)) {
        $price = (int)str_replace(',', '', $m[1]);
    }
}
if (!$brand) $brand = $ogBrand;

// shopが未設定の場合ホストから推測
if (!$shop) {
    $shopMap = [
        'amazon'=>'Amazon','rakuten'=>'楽天市場','yahoo'=>'Yahoo!',
        'yodobashi'=>'ヨドバシカメラ','e-trend'=>'イートレンド',
        'monotaro'=>'MonotaRO','biccamera'=>'ビックカメラ',
        'joshin'=>'ジョーシン','sofmap'=>'ソフマップ',
        'nojima'=>'ノジマ','askul'=>'ASKUL','edion'=>'エディオン',
        'yamada'=>'ヤマダ電機','kakaku'=>'価格.com',
    ];
    foreach ($shopMap as $k => $v) {
        if (strpos($host, $k) !== false) { $shop = $v; break; }
    }
    if (!$shop) $shop = $host;
}

$memo = $ogDesc;
if (strlen($memo) > 120) {
    // UTF-8バイト境界で切る（mbstring不要）
    preg_match('/^.{0,120}/u', $memo, $mm);
    $memo = ($mm[0] ?? substr($memo, 0, 120)) . '…';
}

// rawテキスト（AI補完フォールバック用）
$rawText = strip_tags($html);
$rawText = preg_replace('/\s+/', ' ', $rawText);
preg_match('/^.{0,8000}/u', trim($rawText), $rtm);
$rawText = $rtm[0] ?? substr($rawText, 0, 8000);

// JSON_INVALID_UTF8_IGNOREで不正UTF-8も安全に出力
echo json_encode([
    'name'       => $name,
    'shop'       => $shop,
    'brand'      => $brand,
    'price'      => $price,
    'price_type' => $priceType,  // 'inclusive'=税込, 'exclusive'=税抜
    'memo'       => $memo,
    'raw_text'   => ($name && $price > 0) ? '' : $rawText, // 完全取得済みなら不要
], JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_IGNORE);
