<?php
// PowerPoint (PPTX) エクスポート - ライブラリ不要で生成

$db = new PDO('sqlite:' . __DIR__ . '/manual.db');
$db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

$sections = $db->query("SELECT * FROM sections ORDER BY order_num ASC, id ASC")->fetchAll(PDO::FETCH_ASSOC);

// EMU変換 (1cm = 360000 EMU, 1pt = 12700 EMU)
// スライドサイズ: 25.4cm x 19.05cm (widescreen 16:10 近似 → 標準 10in x 7.5in)
$slideW = 9144000; // 10inch
$slideH = 6858000; // 7.5inch

// ────── ヘルパー ──────
function esc($s) { return htmlspecialchars($s ?? '', ENT_XML1, 'UTF-8'); }

function rgb($hex) {
    $hex = ltrim($hex, '#');
    return strtoupper($hex);
}

function makeSlide($idx, $section, $slideW, $slideH, $hasImage, $imgRId) {
    $title   = esc($section['title'] ?? '');
    $content = esc($section['content'] ?? '');
    $slideNum = $idx + 1;

    // コンテンツエリアのレイアウト
    if ($hasImage) {
        // 左: テキスト, 右: 画像
        $txtX = 457200; $txtY = 685800;
        $txtW = 4572000; $txtH = 5486400;
        $imgX = 5257200; $imgY = 685800;
        $imgW = 3429000; $imgH = 4572000;
    } else {
        $txtX = 457200; $txtY = 685800;
        $txtW = 8229600; $txtH = 5486400;
    }

    $imgXml = '';
    if ($hasImage) {
        $imgXml = <<<XML
    <p:sp>
      <p:nvSpPr>
        <p:cNvPr id="5" name="Placeholder 5"/>
        <p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>
        <p:nvPr/>
      </p:nvSpPr>
    </p:sp>
XML;
        // 画像はpicで描画
        $imgXml = <<<XML
  <p:pic>
    <p:nvPicPr>
      <p:cNvPr id="6" name="image{$idx}"/>
      <p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr>
      <p:nvPr/>
    </p:nvPicPr>
    <p:blipFill>
      <a:blip r:embed="{$imgRId}"/>
      <a:stretch><a:fillRect/></a:stretch>
    </p:blipFill>
    <p:spPr>
      <a:xfrm><a:off x="{$imgX}" y="{$imgY}"/><a:ext cx="{$imgW}" cy="{$imgH}"/></a:xfrm>
      <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
    </p:spPr>
  </p:pic>
XML;
    }

    // コンテンツを行分割してパラグラフに
    $lines = explode("\n", $section['content'] ?? '');
    $paras = '';
    foreach ($lines as $line) {
        $line = esc(trim($line));
        if ($line === '') {
            $paras .= '<a:p><a:endParaRPr lang="ja-JP" sz="1800"/></a:p>';
        } else {
            $paras .= <<<XML
<a:p><a:r><a:rPr lang="ja-JP" sz="1800" dirty="0"/><a:t>{$line}</a:t></a:r></a:p>
XML;
        }
    }
    if (!$paras) $paras = '<a:p><a:endParaRPr lang="ja-JP" sz="1800"/></a:p>';

    return <<<XML
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
       xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
       xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr>
        <p:cNvPr id="1" name=""/>
        <p:cNvGrpSpPr/>
        <p:nvPr/>
      </p:nvGrpSpPr>
      <p:grpSpPr>
        <a:xfrm><a:off x="0" y="0"/><a:ext cx="{$slideW}" cy="{$slideH}"/>
          <a:chOff x="0" y="0"/><a:chExt cx="{$slideW}" cy="{$slideH}"/>
        </a:xfrm>
      </p:grpSpPr>
      <!-- 背景 -->
      <p:sp>
        <p:nvSpPr><p:cNvPr id="2" name="bg"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr/></p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="0" y="0"/><a:ext cx="{$slideW}" cy="{$slideH}"/></a:xfrm>
          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
          <a:solidFill><a:srgbClr val="F8F9FA"/></a:solidFill>
          <a:ln><a:noFill/></a:ln>
        </p:spPr>
        <p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody>
      </p:sp>
      <!-- タイトルバー -->
      <p:sp>
        <p:nvSpPr><p:cNvPr id="3" name="titlebar"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr/></p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="0" y="0"/><a:ext cx="{$slideW}" cy="571500"/></a:xfrm>
          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
          <a:solidFill><a:srgbClr val="1A1A2E"/></a:solidFill>
          <a:ln><a:noFill/></a:ln>
        </p:spPr>
        <p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody>
      </p:sp>
      <!-- タイトルテキスト -->
      <p:sp>
        <p:nvSpPr><p:cNvPr id="4" name="title"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr/></p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="228600" y="57150"/><a:ext cx="8686800" cy="457200"/></a:xfrm>
          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
          <a:noFill/>
        </p:spPr>
        <p:txBody>
          <a:bodyPr anchor="ctr"/>
          <a:lstStyle/>
          <a:p><a:r><a:rPr lang="ja-JP" sz="2400" b="1" dirty="0"><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill></a:rPr><a:t>{$title}</a:t></a:r></a:p>
        </p:txBody>
      </p:sp>
      <!-- コンテンツ -->
      <p:sp>
        <p:nvSpPr><p:cNvPr id="5" name="content"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr/></p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="{$txtX}" y="{$txtY}"/><a:ext cx="{$txtW}" cy="{$txtH}"/></a:xfrm>
          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
          <a:noFill/>
        </p:spPr>
        <p:txBody>
          <a:bodyPr wrap="square"/>
          <a:lstStyle/>
          {$paras}
        </p:txBody>
      </p:sp>
      {$imgXml}
      <!-- スライド番号 -->
      <p:sp>
        <p:nvSpPr><p:cNvPr id="9" name="num"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr/></p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="8229600" y="6400800"/><a:ext cx="914400" cy="457200"/></a:xfrm>
          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
          <a:noFill/>
        </p:spPr>
        <p:txBody>
          <a:bodyPr anchor="ctr"/>
          <a:lstStyle/>
          <a:p><a:pPr algn="r"/><a:r><a:rPr lang="ja-JP" sz="1200" dirty="0"><a:solidFill><a:srgbClr val="888888"/></a:solidFill></a:rPr><a:t>{$slideNum}</a:t></a:r></a:p>
        </p:txBody>
      </p:sp>
    </p:spTree>
  </p:cSld>
</p:sld>
XML;
}

// ────── PPTX構築 ──────
$tmpDir = sys_get_temp_dir() . '/pptx_' . uniqid();
mkdir($tmpDir);
mkdir($tmpDir . '/_rels');
mkdir($tmpDir . '/ppt');
mkdir($tmpDir . '/ppt/slides');
mkdir($tmpDir . '/ppt/slides/_rels');
mkdir($tmpDir . '/ppt/slideLayouts');
mkdir($tmpDir . '/ppt/slideLayouts/_rels');
mkdir($tmpDir . '/ppt/slideMasters');
mkdir($tmpDir . '/ppt/slideMasters/_rels');
mkdir($tmpDir . '/ppt/media');
mkdir($tmpDir . '/docProps');

// [Content_Types].xml
$slideTypes = '';
for ($i = 0; $i < count($sections); $i++) {
    $n = $i + 1;
    $slideTypes .= "<Override PartName=\"/ppt/slides/slide{$n}.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.presentationml.slide+xml\"/>\n";
}

file_put_contents($tmpDir . '/[Content_Types].xml', <<<XML
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="jpeg" ContentType="image/jpeg"/>
  <Default Extension="jpg" ContentType="image/jpeg"/>
  <Default Extension="png" ContentType="image/png"/>
  <Default Extension="gif" ContentType="image/gif"/>
  <Default Extension="webp" ContentType="image/webp"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
  <Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
  {$slideTypes}
</Types>
XML);

// _rels/.rels
file_put_contents($tmpDir . '/_rels/.rels', <<<XML
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
</Relationships>
XML);

// slideMaster1.xml (最小限)
file_put_contents($tmpDir . '/ppt/slideMasters/slideMaster1.xml', <<<XML
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
             xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
             xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree>
    <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
    <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
  </p:spTree></p:cSld>
  <p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
  <p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
  <p:txStyles>
    <p:titleStyle><a:lvl1pPr><a:defRPr lang="ja-JP"/></a:lvl1pPr></p:titleStyle>
    <p:bodyStyle><a:lvl1pPr><a:defRPr lang="ja-JP"/></a:lvl1pPr></p:bodyStyle>
    <p:otherStyle><a:lvl1pPr><a:defRPr lang="ja-JP"/></a:lvl1pPr></p:otherStyle>
  </p:txStyles>
</p:sldMaster>
XML);

file_put_contents($tmpDir . '/ppt/slideMasters/_rels/slideMaster1.xml.rels', <<<XML
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
</Relationships>
XML);

// slideLayout1.xml
file_put_contents($tmpDir . '/ppt/slideLayouts/slideLayout1.xml', <<<XML
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
             xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
             xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank">
  <p:cSld name="blank"><p:spTree>
    <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
    <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
  </p:spTree></p:cSld>
</p:sldLayout>
XML);

file_put_contents($tmpDir . '/ppt/slideLayouts/_rels/slideLayout1.xml.rels', <<<XML
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
</Relationships>
XML);

// 各スライド生成
$slideRels = '';
for ($i = 0; $i < count($sections); $i++) {
    $n = $i + 1;
    $section = $sections[$i];
    $imgPath = $section['image_path'] ? __DIR__ . '/' . $section['image_path'] : '';
    $hasImage = $imgPath && file_exists($imgPath);
    $imgRId = '';

    $relsXml = <<<XML
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
XML;

    if ($hasImage) {
        $imgRId = 'rId2';
        $ext = strtolower(pathinfo($imgPath, PATHINFO_EXTENSION));
        $mediaName = "image{$n}.{$ext}";
        copy($imgPath, $tmpDir . '/ppt/media/' . $mediaName);
        $relsXml .= "\n  <Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/image\" Target=\"../media/{$mediaName}\"/>";
    }
    $relsXml .= "\n</Relationships>";

    file_put_contents($tmpDir . "/ppt/slides/_rels/slide{$n}.xml.rels", $relsXml);
    file_put_contents($tmpDir . "/ppt/slides/slide{$n}.xml", makeSlide($i, $section, $slideW, $slideH, $hasImage, $imgRId));

    $slideRels .= "  <Relationship Id=\"rId" . ($n + 2) . "\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide\" Target=\"slides/slide{$n}.xml\"/>\n";
}

// presentation.xml
$slideIdList = '';
for ($i = 0; $i < count($sections); $i++) {
    $n = $i + 1;
    $id = 256 + $i;
    $rid = $n + 2;
    $slideIdList .= "    <p:sldId id=\"{$id}\" r:id=\"rId{$rid}\"/>\n";
}

file_put_contents($tmpDir . '/ppt/presentation.xml', <<<XML
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
                xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
                xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                saveSubsetFonts="1">
  <p:sldMasterIdLst>
    <p:sldMasterId id="2147483648" r:id="rId1"/>
  </p:sldMasterIdLst>
  <p:sldSz cx="{$slideW}" cy="{$slideH}" type="screen4x3"/>
  <p:notesSz cx="6858000" cy="9144000"/>
  <p:sldIdLst>
{$slideIdList}  </p:sldIdLst>
</p:presentation>
XML);

file_put_contents($tmpDir . '/ppt/_rels/presentation.xml.rels', <<<XML
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>
{$slideRels}</Relationships>
XML);

// ZIP化してPPTXとして出力
$pptxFile = sys_get_temp_dir() . '/AIブログマスター仕様説明書_' . date('Ymd_His') . '.pptx';

// ZipArchiveで作成
$zip = new ZipArchive();
$zip->open($pptxFile, ZipArchive::CREATE | ZipArchive::OVERWRITE);

$files = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($tmpDir));
foreach ($files as $file) {
    if ($file->isDir()) continue;
    $filePath = $file->getRealPath();
    $relativePath = substr($filePath, strlen($tmpDir) + 1);
    $relativePath = str_replace('\\', '/', $relativePath);
    $zip->addFile($filePath, $relativePath);
}
$zip->close();

// 一時ディレクトリ削除
array_map('unlink', glob($tmpDir . '/ppt/media/*'));
array_map('unlink', glob($tmpDir . '/ppt/slides/_rels/*'));
array_map('unlink', glob($tmpDir . '/ppt/slides/*'));
array_map('unlink', glob($tmpDir . '/ppt/slideLayouts/_rels/*'));
array_map('unlink', glob($tmpDir . '/ppt/slideLayouts/*'));
array_map('unlink', glob($tmpDir . '/ppt/slideMasters/_rels/*'));
array_map('unlink', glob($tmpDir . '/ppt/slideMasters/*'));
array_map('unlink', glob($tmpDir . '/ppt/_rels/*'));
array_map('unlink', glob($tmpDir . '/ppt/*'));
array_map('unlink', glob($tmpDir . '/_rels/*'));
array_map('unlink', glob($tmpDir . '/*'));
@rmdir($tmpDir . '/ppt/media');
@rmdir($tmpDir . '/ppt/slides/_rels');
@rmdir($tmpDir . '/ppt/slides');
@rmdir($tmpDir . '/ppt/slideLayouts/_rels');
@rmdir($tmpDir . '/ppt/slideLayouts');
@rmdir($tmpDir . '/ppt/slideMasters/_rels');
@rmdir($tmpDir . '/ppt/slideMasters');
@rmdir($tmpDir . '/ppt/_rels');
@rmdir($tmpDir . '/ppt/theme');
@rmdir($tmpDir . '/ppt');
@rmdir($tmpDir . '/_rels');
@rmdir($tmpDir . '/docProps');
@rmdir($tmpDir);

// ダウンロード
$filename = 'AIブログマスター仕様説明書_' . date('Ymd_His') . '.pptx';
header('Content-Type: application/vnd.openxmlformats-officedocument.presentationml.presentation');
header('Content-Disposition: attachment; filename="' . rawurlencode($filename) . '"');
header('Content-Length: ' . filesize($pptxFile));
readfile($pptxFile);
unlink($pptxFile);
