const path = require('path');
const fs = require('fs');
const pdfjsLib = require('pdfjs-dist/legacy/build/pdf.js');
const pkgDir = path.dirname(require.resolve('pdfjs-dist/package.json'));
const cmapUrl = path.join(pkgDir, 'cmaps') + path.sep;

const filePath = 'C:/Users/shira_k13727w/OneDrive/DF/アライアンス関連/請求書・売上/アライアンス事業部請求書/2026年度/1月/AIブログ（請求書）/☆●OneChat株式会社御中【1月度AIブログマスターご請求】.pdf';
const buffer = fs.readFileSync(filePath);

pdfjsLib.getDocument({ data: new Uint8Array(buffer), cMapUrl, cMapPacked: true, disableWorker: true }).promise
  .then(async doc => {
    let text = '';
    for (let i = 1; i <= doc.numPages; i++) {
      const page = await doc.getPage(i);
      const content = await page.getTextContent();
      text += content.items.map(x => x.str).join('') + '\n';
    }
    console.log('=== 先頭600文字 ===');
    console.log(JSON.stringify(text.slice(0, 600)));
    const m = text.match(/([^\n\r]{2,40})\s*(?:御中|様)/);
    console.log('=== 御中/様マッチ ===', m ? JSON.stringify(m[1]) : '未検出');
    console.log('=== OneChat含む行 ===');
    text.split('\n').filter(l => l.includes('OneChat') || l.includes('御中') || l.includes('様')).forEach(l => console.log(JSON.stringify(l)));
  })
  .catch(e => console.error(e.message));
