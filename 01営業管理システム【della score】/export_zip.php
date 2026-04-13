<?php
/**
 * コアリス システム連携エクスポート
 * DellaScore + イワタアシスト のデータをZIPで出力
 * 他システム・AI連携用
 */

// ── パス設定 ──────────────────────────────
$DS_DB   = __DIR__ . '/della_score.db';
$IW_DB   = __DIR__ . '/../02仕入れ管理【イワタアシスト】/iwata_assist.db';
$EXPORT_DATE = date('Ymd_His');

// ── DB読み込みヘルパー ──────────────────────
function dbGet($dbPath, $sql, $params = []) {
    try {
        $db = new PDO('sqlite:' . $dbPath);
        $db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        $st = $db->prepare($sql);
        $st->execute($params);
        return $st->fetchAll(PDO::FETCH_ASSOC);
    } catch (Exception $e) {
        return ['_error' => $e->getMessage()];
    }
}
function storeGet($dbPath, $key) {
    $r = dbGet($dbPath, 'SELECT value FROM store WHERE key=?', [$key]);
    if (isset($r[0]['value'])) return json_decode($r[0]['value'], true) ?: [];
    return [];
}

// ── DellaScore データ取得 ──────────────────────
$ds = [];

// 見込み（商談管理）
$ds['prospects'] = array_map(function($p) {
    return [
        'id'        => $p['id'],
        'client'    => $p['client'],      // 取引先名
        'name'      => $p['name'],        // 案件名
        'amount'    => (int)($p['amount'] ?? 0),    // 金額（税抜）
        'cost'      => (int)($p['cost'] ?? 0),      // 仕入れ原価
        'issued'    => $p['issued'] ?? '',           // 見積日
        'deadline'  => $p['deadline'] ?? '',         // 有効期限
        'status'    => $p['status'] ?? '',           // prospect/ordered/canceled
        'owner'     => $p['owner'] ?? '',            // 担当者
        'memo'      => $p['memo'] ?? '',
    ];
}, storeGet($DS_DB, 'prospects'));

// 請求書（売上）
$ds['invoices'] = array_map(function($i) {
    return [
        'id'             => $i['id'],
        'billing_number' => $i['billing_number'] ?? '',
        'client'         => $i['client'],
        'name'           => $i['name'] ?? '',      // 案件名
        'amount'         => (int)($i['amount'] ?? 0),
        'tax'            => (int)($i['tax'] ?? 0),
        'issued'         => $i['issued'] ?? '',    // 請求日
        'due'            => $i['due'] ?? '',       // 支払期限
        'status'         => $i['status'] ?? '',    // paid/unpaid
        'owner'          => $i['owner'] ?? '',
    ];
}, storeGet($DS_DB, 'invoices'));

// 受注
$ds['orders'] = array_map(function($o) {
    return [
        'id'              => $o['id'],
        'client'          => $o['client'],
        'name'            => $o['name'] ?? '',
        'amount'          => (int)($o['amount'] ?? 0),
        'tax'             => (int)($o['tax'] ?? 0),
        'date'            => $o['date'] ?? '',
        'delivery'        => $o['delivery'] ?? '',
        'collectionMonth' => $o['collectionMonth'] ?? '',
        'payment'         => $o['payment'] ?? '',
        'owner'           => $o['owner'] ?? '',
    ];
}, storeGet($DS_DB, 'orders'));

// 仕入れ請求書
$ds['purchases'] = array_map(function($p) {
    return [
        'id'       => $p['id'],
        'supplier' => $p['supplier'],
        'desc'     => $p['desc'] ?? '',
        'amount'   => (int)($p['amount'] ?? 0),
        'tax'      => (int)($p['tax'] ?? 0),
        'issued'   => $p['issued'] ?? '',
        'due'      => $p['due'] ?? '',
        'status'   => $p['status'] ?? '',   // paid/unpaid
        'owner'    => $p['owner'] ?? '',
    ];
}, storeGet($DS_DB, 'purchases'));

// 取引先
$ds['clients'] = array_map(function($c) {
    return [
        'name'    => $c['name'],
        'tel'     => $c['tel'] ?? '',
        'email'   => $c['email'] ?? '',
        'address' => $c['address'] ?? '',
        'memo'    => $c['memo'] ?? '',
        'owners'  => $c['owners'] ?? [],
    ];
}, storeGet($DS_DB, 'clients'));

// ── イワタアシスト データ取得 ──────────────────────
$iw = [];

$iw['orders'] = array_map(function($o) {
    return [
        'id'     => $o['id'],
        'date'   => $o['date'],          // 発注日
        'name'   => $o['name'],          // 商品名
        'shop'   => $o['shop'],          // 購入先
        'brand'  => $o['brand'] ?? '',
        'qty'    => (int)($o['qty'] ?? 1),
        'price'  => (int)($o['price'] ?? 0),
        'client' => $o['client'] ?? '',  // 使用先（取引先）
        'status' => $o['status'] ?? '',  // 発注済/入荷済 等
        'memo'   => $o['memo'] ?? '',
    ];
}, dbGet($IW_DB, 'SELECT * FROM orders ORDER BY date DESC'));

// ── スキーマ定義（他システム連携用ガイド） ──────────────────────
$schema = [
    'generated_at' => date('Y-m-d H:i:s'),
    'systems' => [
        'della_score' => [
            'description' => '営業管理システム。見込み→受注→請求書の一連の商談フローを管理。',
            'tables' => [
                'prospects' => [
                    'description' => '見込み案件・商談管理',
                    'fields' => [
                        'id'       => 'ユニークID (string)',
                        'client'   => '取引先名 (string)',
                        'name'     => '案件名 (string)',
                        'amount'   => '金額・税抜 (integer)',
                        'cost'     => '仕入れ原価・税抜 (integer)',
                        'issued'   => '見積日 YYYY-MM-DD (string)',
                        'deadline' => '有効期限 YYYY-MM-DD (string)',
                        'status'   => 'prospect=商談中 / ordered=受注済 / canceled=失注',
                        'owner'    => '担当者名 (string)',
                        'memo'     => '備考 (string)',
                    ],
                ],
                'invoices' => [
                    'description' => '売上請求書',
                    'fields' => [
                        'id'             => 'ユニークID (string)',
                        'billing_number' => '請求書番号 (string)',
                        'client'         => '請求先名 (string)',
                        'name'           => '案件名 (string)',
                        'amount'         => '金額・税抜 (integer)',
                        'tax'            => '消費税額 (integer)',
                        'issued'         => '請求日 YYYY-MM-DD (string)',
                        'due'            => '支払期限 YYYY-MM-DD (string)',
                        'status'         => 'paid=入金済 / unpaid=未入金',
                        'owner'          => '担当者名 (string)',
                    ],
                ],
                'orders' => [
                    'description' => '受注管理',
                    'fields' => [
                        'id'              => 'ユニークID (string)',
                        'client'          => '取引先名 (string)',
                        'name'            => '案件名 (string)',
                        'amount'          => '金額・税抜 (integer)',
                        'tax'             => '消費税額 (integer)',
                        'date'            => '受注日 YYYY-MM-DD (string)',
                        'delivery'        => '納品日 YYYY-MM-DD (string)',
                        'collectionMonth' => '回収予定月 YYYY-MM (string)',
                        'payment'         => '支払い条件 (string)',
                        'owner'           => '担当者名 (string)',
                    ],
                ],
                'purchases' => [
                    'description' => '仕入れ請求書',
                    'fields' => [
                        'id'       => 'ユニークID (string)',
                        'supplier' => '仕入れ先名 (string)',
                        'desc'     => '内容 (string)',
                        'amount'   => '金額・税抜 (integer)',
                        'tax'      => '消費税額 (integer)',
                        'issued'   => '請求日 YYYY-MM-DD (string)',
                        'due'      => '支払期限 YYYY-MM-DD (string)',
                        'status'   => 'paid=支払済 / unpaid=未払い',
                        'owner'    => '担当者名 (string)',
                    ],
                ],
                'clients' => [
                    'description' => '取引先マスタ',
                    'fields' => [
                        'name'    => '取引先名 (string) ※主キー相当',
                        'tel'     => '電話番号 (string)',
                        'email'   => 'メールアドレス (string)',
                        'address' => '住所 (string)',
                        'memo'    => '備考 (string)',
                        'owners'  => '担当者リスト (string[])',
                    ],
                ],
            ],
        ],
        'iwata_assist' => [
            'description' => '仕入れ発注管理システム。商品の発注・入荷状況を管理。',
            'tables' => [
                'orders' => [
                    'description' => '仕入れ発注履歴',
                    'fields' => [
                        'id'     => 'ID (integer)',
                        'date'   => '発注日 YYYY-MM-DD (string)',
                        'name'   => '商品名 (string)',
                        'shop'   => '購入先店舗 (string)',
                        'brand'  => 'ブランド (string)',
                        'qty'    => '数量 (integer)',
                        'price'  => '単価 (integer)',
                        'client' => '使用先・取引先 (string)',
                        'status' => '発注済 / 入荷済 等',
                        'memo'   => '備考 (string)',
                    ],
                ],
            ],
        ],
    ],
    'integration_notes' => [
        '取引先の名寄せ' => 'della_score.clients.name ↔ iwata_assist.orders.client で名寄せ可能（表記ゆれ注意）',
        '担当者' => '各テーブルの owner フィールドに担当者名が入る。della_score.clients.owners に紐づく担当者一覧あり',
        '金額の扱い' => '全て税抜金額。消費税はtaxフィールドに別途格納',
        '日付フォーマット' => '全て YYYY-MM-DD 形式',
    ],
];

// ── ZIP生成 ──────────────────────────────────
$zipPath = sys_get_temp_dir() . '/corelis_export_' . $EXPORT_DATE . '.zip';
$zip = new ZipArchive();
if ($zip->open($zipPath, ZipArchive::CREATE | ZipArchive::OVERWRITE) !== true) {
    die('ZIPファイルの作成に失敗しました');
}

$opts = JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT;

// DellaScore
$zip->addFromString('della_score/prospects.json',  json_encode($ds['prospects'], $opts));
$zip->addFromString('della_score/invoices.json',   json_encode($ds['invoices'],  $opts));
$zip->addFromString('della_score/orders.json',     json_encode($ds['orders'],    $opts));
$zip->addFromString('della_score/purchases.json',  json_encode($ds['purchases'], $opts));
$zip->addFromString('della_score/clients.json',    json_encode($ds['clients'],   $opts));

// イワタアシスト
$zip->addFromString('iwata_assist/orders.json', json_encode($iw['orders'], $opts));

// スキーマ・README
$zip->addFromString('schema.json', json_encode($schema, $opts));
$zip->addFromString('README.md', <<<MD
# コアリス システム連携エクスポート

生成日時: {$schema['generated_at']}

## 含まれるデータ

### della_score/
| ファイル | 内容 | 件数 |
|---|---|---|
| prospects.json | 見込み・商談管理 | {$counts['prospects']}件 |
| invoices.json | 売上請求書 | {$counts['invoices']}件 |
| orders.json | 受注管理 | {$counts['orders']}件 |
| purchases.json | 仕入れ請求書 | {$counts['purchases']}件 |
| clients.json | 取引先マスタ | {$counts['clients']}件 |

### iwata_assist/
| ファイル | 内容 | 件数 |
|---|---|---|
| orders.json | 仕入れ発注履歴 | {$counts['iw_orders']}件 |

## 連携ポイント

- **取引先の名寄せ**: `della_score/clients.name` ↔ `iwata_assist/orders.client`
- **担当者管理**: 各データの `owner` フィールド
- **金額**: すべて税抜。消費税は `tax` フィールドに別格納
- **日付**: すべて `YYYY-MM-DD` 形式

## フィールド定義

詳細は `schema.json` を参照してください。
MD
);

$zip->close();

// 件数を README に埋め込むために再計算して上書き
$counts = [
    'prospects' => count($ds['prospects']),
    'invoices'  => count($ds['invoices']),
    'orders'    => count($ds['orders']),
    'purchases' => count($ds['purchases']),
    'clients'   => count($ds['clients']),
    'iw_orders' => count($iw['orders']),
];
$total = array_sum($counts);

// READMEを件数込みで再生成してZIPを再度開いて更新
$zip->open($zipPath, ZipArchive::CREATE);
$zip->addFromString('README.md', <<<MD
# コアリス システム連携エクスポート

生成日時: {$schema['generated_at']}

## 含まれるデータ（合計 {$total} 件）

### della_score/
| ファイル | 内容 | 件数 |
|---|---|---|
| prospects.json | 見込み・商談管理 | {$counts['prospects']} 件 |
| invoices.json | 売上請求書 | {$counts['invoices']} 件 |
| orders.json | 受注管理 | {$counts['orders']} 件 |
| purchases.json | 仕入れ請求書 | {$counts['purchases']} 件 |
| clients.json | 取引先マスタ | {$counts['clients']} 件 |

### iwata_assist/
| ファイル | 内容 | 件数 |
|---|---|---|
| orders.json | 仕入れ発注履歴 | {$counts['iw_orders']} 件 |

## 連携ポイント

- **取引先の名寄せ**: `della_score/clients.name` ↔ `iwata_assist/orders.client`
- **担当者管理**: 各データの `owner` フィールド
- **金額**: すべて税抜。消費税は `tax` フィールドに別格納
- **日付**: すべて `YYYY-MM-DD` 形式

## フィールド定義

詳細は `schema.json` を参照してください。
MD
);
$zip->close();

// ── ダウンロード出力 ──────────────────────────────
$filename = 'corelis_export_' . $EXPORT_DATE . '.zip';
header('Content-Type: application/zip');
header('Content-Disposition: attachment; filename="' . $filename . '"');
header('Content-Length: ' . filesize($zipPath));
header('Cache-Control: no-cache, must-revalidate');
readfile($zipPath);
unlink($zipPath);
exit;
