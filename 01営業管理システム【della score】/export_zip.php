<?php
/**
 * コアリス システム連携エクスポート
 * DellaScore + イワタアシスト のデータをZIPで出力
 * 他システム・AI連携用
 */

$DS_DB = __DIR__ . '/della_score.db';
$IW_DB = __DIR__ . '/../02仕入れ管理【イワタアシスト】/iwata_assist.db';
$EXPORT_DATE = date('Ymd_His');

// ── DB読み込みヘルパー ──────────────────────
function storeGet($dbPath, $key) {
    try {
        $db = new PDO('sqlite:' . $dbPath);
        $st = $db->prepare('SELECT value FROM store WHERE key=?');
        $st->execute([$key]);
        $r = $st->fetch();
        return $r ? (json_decode($r['value'], true) ?: []) : [];
    } catch (Exception $e) { return []; }
}
function dbAll($dbPath, $sql) {
    try {
        $db = new PDO('sqlite:' . $dbPath);
        return $db->query($sql)->fetchAll(PDO::FETCH_ASSOC);
    } catch (Exception $e) { return []; }
}

// ── DellaScore データ取得 ──────────────────────
$prospects = array_map(fn($p) => [
    'id'       => $p['id'],
    'client'   => $p['client'],
    'name'     => $p['name'] ?? '',
    'amount'   => (int)($p['amount'] ?? 0),
    'cost'     => (int)($p['cost'] ?? 0),
    'issued'   => $p['issued'] ?? '',
    'deadline' => $p['deadline'] ?? '',
    'status'   => $p['status'] ?? '',
    'owner'    => $p['owner'] ?? '',
    'memo'     => $p['memo'] ?? '',
], storeGet($DS_DB, 'prospects'));

$invoices = array_map(fn($i) => [
    'id'             => $i['id'],
    'billing_number' => $i['billing_number'] ?? '',
    'client'         => $i['client'],
    'name'           => $i['name'] ?? '',
    'amount'         => (int)($i['amount'] ?? 0),
    'tax'            => (int)($i['tax'] ?? 0),
    'issued'         => $i['issued'] ?? '',
    'due'            => $i['due'] ?? '',
    'status'         => $i['status'] ?? '',
    'owner'          => $i['owner'] ?? '',
], storeGet($DS_DB, 'invoices'));

$orders = array_map(fn($o) => [
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
], storeGet($DS_DB, 'orders'));

$purchases = array_map(fn($p) => [
    'id'       => $p['id'],
    'supplier' => $p['supplier'],
    'desc'     => $p['desc'] ?? '',
    'amount'   => (int)($p['amount'] ?? 0),
    'tax'      => (int)($p['tax'] ?? 0),
    'issued'   => $p['issued'] ?? '',
    'due'      => $p['due'] ?? '',
    'status'   => $p['status'] ?? '',
    'owner'    => $p['owner'] ?? '',
], storeGet($DS_DB, 'purchases'));

$clients = array_map(fn($c) => [
    'name'    => $c['name'],
    'tel'     => $c['tel'] ?? '',
    'email'   => $c['email'] ?? '',
    'address' => $c['address'] ?? '',
    'memo'    => $c['memo'] ?? '',
    'owners'  => $c['owners'] ?? [],
], storeGet($DS_DB, 'clients'));

// ── イワタアシスト データ取得 ──────────────────────
$iw_orders = array_map(fn($o) => [
    'id'     => $o['id'],
    'date'   => $o['date'],
    'name'   => $o['name'],
    'shop'   => $o['shop'],
    'brand'  => $o['brand'] ?? '',
    'qty'    => (int)($o['qty'] ?? 1),
    'price'  => (int)($o['price'] ?? 0),
    'client' => $o['client'] ?? '',
    'status' => $o['status'] ?? '',
    'memo'   => $o['memo'] ?? '',
], dbAll($IW_DB, 'SELECT * FROM orders ORDER BY date DESC'));

// ── 件数集計 ──────────────────────────────────
$counts = [
    'prospects' => count($prospects),
    'invoices'  => count($invoices),
    'orders'    => count($orders),
    'purchases' => count($purchases),
    'clients'   => count($clients),
    'iw_orders' => count($iw_orders),
];
$total = array_sum($counts);
$genAt = date('Y-m-d H:i:s');

// ── スキーマ定義 ──────────────────────────────────
$schema = [
    'generated_at' => $genAt,
    'systems' => [
        'della_score' => [
            'description' => '営業管理システム。見込み→受注→請求書の商談フローを管理。',
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
                        'status' => '発注済 / 入荷済 等 (string)',
                        'memo'   => '備考 (string)',
                    ],
                ],
            ],
        ],
    ],
    'integration_notes' => [
        '取引先の名寄せ'   => 'della_score/clients.name ↔ iwata_assist/orders.client で名寄せ可能（表記ゆれ注意）',
        '担当者'           => '各テーブルの owner フィールドに担当者名。della_score/clients.owners に担当者一覧あり',
        '金額の扱い'       => '全て税抜金額。消費税は tax フィールドに別途格納',
        '日付フォーマット' => '全て YYYY-MM-DD 形式',
        '見込み→受注のフロー' => 'prospects.status=ordered の案件に対応する orders レコードが存在する',
    ],
];

$readme = <<<MD
# コアリス システム連携エクスポート

生成日時: {$genAt}

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
- **担当者管理**: 各データの `owner` フィールド（della_score/clients.owners も参照）
- **金額**: すべて税抜。消費税は `tax` フィールドに別格納
- **日付**: すべて `YYYY-MM-DD` 形式
- **見込み→受注フロー**: prospects.status=ordered の案件に対応する orders レコードが存在

## フィールド定義

詳細は `schema.json` を参照してください。

## AIへの渡し方（推奨）

1. このZIPを解凍する
2. `schema.json` と対象の `.json` ファイルをAIにアップロード
3. 「このデータを使って〇〇を作って」と指示する
MD;

// ── 一時フォルダに書き出し ──────────────────────
$tmpDir = sys_get_temp_dir() . '/corelis_export_' . $EXPORT_DATE;
$dsDir  = $tmpDir . '/della_score';
$iwDir  = $tmpDir . '/iwata_assist';
mkdir($dsDir, 0777, true);
mkdir($iwDir, 0777, true);

$opts = JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT;
file_put_contents($dsDir . '/prospects.json', json_encode($prospects, $opts));
file_put_contents($dsDir . '/invoices.json',  json_encode($invoices,  $opts));
file_put_contents($dsDir . '/orders.json',    json_encode($orders,    $opts));
file_put_contents($dsDir . '/purchases.json', json_encode($purchases, $opts));
file_put_contents($dsDir . '/clients.json',   json_encode($clients,   $opts));
file_put_contents($iwDir  . '/orders.json',   json_encode($iw_orders, $opts));
file_put_contents($tmpDir . '/schema.json',   json_encode($schema,    $opts));
file_put_contents($tmpDir . '/README.md',     $readme);

// ── PowerShellでZIP化（ZipArchive非依存） ──────────────────────
$zipPath = sys_get_temp_dir() . '/corelis_export_' . $EXPORT_DATE . '.zip';
$tmpDirWin = str_replace('/', '\\', $tmpDir);
$zipPathWin = str_replace('/', '\\', $zipPath);
$cmd = "powershell -NoProfile -Command \"Compress-Archive -Path '{$tmpDirWin}\\*' -DestinationPath '{$zipPathWin}' -Force\" 2>&1";
exec($cmd, $out, $ret);

// 一時フォルダ削除
function rmdir_r($dir) {
    foreach (glob($dir . '/*') as $f) is_dir($f) ? rmdir_r($f) : unlink($f);
    rmdir($dir);
}
rmdir_r($tmpDir);

if ($ret !== 0 || !file_exists($zipPath)) {
    header('Content-Type: text/plain; charset=utf-8');
    echo "ZIPの生成に失敗しました。\n";
    echo implode("\n", $out);
    exit;
}

// ── ダウンロード出力 ──────────────────────────────
$filename = 'corelis_export_' . $EXPORT_DATE . '.zip';
header('Content-Type: application/zip');
header('Content-Disposition: attachment; filename="' . $filename . '"');
header('Content-Length: ' . filesize($zipPath));
header('Cache-Control: no-cache, must-revalidate');
readfile($zipPath);
unlink($zipPath);
exit;
