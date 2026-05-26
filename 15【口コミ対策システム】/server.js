const express = require('express');
const { exec } = require('child_process');
const CDP = require('chrome-remote-interface');
const http = require('http');
const path = require('path');
const util = require('util');
const execAsync = util.promisify(exec);

// ADBのパス（wingetインストール先 or PATH上のadb）
const ADB = process.env.ADB_PATH ||
  'C:\\Users\\shira_k13727w\\AppData\\Local\\Microsoft\\WinGet\\Packages\\Google.PlatformTools_Microsoft.Winget.Source_8wekyb3d8bbwe\\platform-tools\\adb.exe';

const app = express();
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

const PORT = 3000;

// Chrome ソケット名の候補（バージョン違い対応）
const CHROME_SOCKETS = [
  'chrome_devtools_remote',
  'chrome_beta_devtools_remote',
  'chrome_dev_devtools_remote',
  'chrome_canary_devtools_remote',
  'webview_devtools_remote'
];

let state = {
  connected: false,
  deviceId: null,
  socket: null,
  lat: null,
  lon: null,
  locationName: null
};

// ---- ADB デバイス一覧 ----
app.get('/api/devices', async (req, res) => {
  try {
    const { stdout } = await execAsync(`${ADB} devices`);
    const lines = stdout.split('\n').slice(1);
    const devices = lines
      .filter(l => l.trim() && l.includes('\t'))
      .map(l => {
        const parts = l.split('\t');
        return { id: parts[0].trim(), status: parts[1].trim() };
      })
      .filter(d => d.status === 'device');
    res.json({ devices });
  } catch {
    res.json({ error: 'ADB が見つかりません。Android SDK Platform Tools をインストールしてください。', devices: [] });
  }
});

// HTTP で /json/version を取得（CDPを開かずに確認）
function checkChromeHttp(port) {
  return new Promise((resolve, reject) => {
    const req = http.get(`http://127.0.0.1:${port}/json/version`, { timeout: 3000 }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); } catch { reject(new Error('parse error')); }
      });
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
  });
}

// ---- デバイス接続 ----
app.post('/api/connect', async (req, res) => {
  const { deviceId } = req.body;
  if (!deviceId) return res.status(400).json({ error: 'deviceId が必要です' });

  // 既存のフォワードを削除
  try { await execAsync(`${ADB} -s ${deviceId} forward --remove tcp:9222`); } catch {}

  for (const socket of CHROME_SOCKETS) {
    try {
      await execAsync(`${ADB} -s ${deviceId} forward tcp:9222 localabstract:${socket}`);

      // CDPを開かずHTTPだけで確認（Chromeがクラッシュしない）
      const info = await checkChromeHttp(9222);

      state.connected = true;
      state.deviceId = deviceId;
      state.socket = socket;

      return res.json({ success: true, socket, browser: info.Browser || '' });
    } catch {
      try { await execAsync(`${ADB} -s ${deviceId} forward --remove tcp:9222`); } catch {}
    }
  }

  res.json({ error: 'Chrome に接続できませんでした。\nデバイスで Chrome を開いてからもう一度お試しください。' });
});

// ---- 位置情報をセット ----
app.post('/api/set-location', async (req, res) => {
  const { lat, lon, name } = req.body;

  if (!state.connected) {
    return res.json({ error: '先にデバイスに接続してください' });
  }

  const latitude = parseFloat(lat);
  const longitude = parseFloat(lon);

  if (isNaN(latitude) || isNaN(longitude)) {
    return res.status(400).json({ error: '緯度・経度が不正です' });
  }

  try {
    const targets = await CDP.List({ port: 9222 });
    const pages = targets.filter(t => t.type === 'page');

    if (pages.length === 0) {
      return res.json({ error: 'Chrome のタブが見つかりません。Chrome で何かページを開いてください。' });
    }

    let successCount = 0;
    for (const page of pages) {
      const client = await CDP({ target: page.id, port: 9222 });
      try {
        await client.Emulation.setGeolocationOverride({ latitude, longitude, accuracy: 10 });
        successCount++;
      } catch (e) {
        console.error(`Tab ${page.id}: ${e.message}`);
      } finally {
        await client.close();
      }
    }

    state.lat = latitude;
    state.lon = longitude;
    state.locationName = name || null;

    res.json({ success: true, lat: latitude, lon: longitude, tabCount: successCount });
  } catch (err) {
    res.json({ error: `位置情報の設定に失敗しました: ${err.message}` });
  }
});

// ---- 位置情報をリセット ----
app.post('/api/reset-location', async (req, res) => {
  if (!state.connected) return res.json({ error: '接続されていません' });

  try {
    const targets = await CDP.List({ port: 9222 });
    const pages = targets.filter(t => t.type === 'page');

    for (const page of pages) {
      const client = await CDP({ target: page.id, port: 9222 });
      try {
        await client.Emulation.clearGeolocationOverride();
      } catch {}
      finally { await client.close(); }
    }

    state.lat = null;
    state.lon = null;
    state.locationName = null;

    res.json({ success: true });
  } catch (err) {
    res.json({ error: err.message });
  }
});

// ---- 住所検索プロキシ（国土地理院API → Nominatimフォールバック）----
app.get('/api/search', async (req, res) => {
  const q = req.query.q;
  if (!q) return res.json([]);

  try {
    // 国土地理院（番地レベルまで対応・日本専用）
    const gsiUrl = `https://msearch.gsi.go.jp/address-search/AddressSearch?q=${encodeURIComponent(q)}`;
    const { stdout: gsiOut } = await execAsync(`curl -s "${gsiUrl}" -H "User-Agent: MEO-LocationChecker/1.0"`);
    const gsiData = JSON.parse(gsiOut);

    if (gsiData && gsiData.length > 0) {
      const results = gsiData.slice(0, 6).map(item => ({
        display_name: item.properties.title,
        lat: String(item.geometry.coordinates[1]),
        lon: String(item.geometry.coordinates[0])
      }));
      return res.json(results);
    }
  } catch {}

  // フォールバック: Nominatim
  try {
    const nomUrl = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(q)}&format=json&limit=6&accept-language=ja&countrycodes=jp`;
    const { stdout } = await execAsync(`curl -s "${nomUrl}" -H "User-Agent: MEO-LocationChecker/1.0"`);
    res.json(JSON.parse(stdout));
  } catch {
    res.json([]);
  }
});

// ---- 切断 ----
app.post('/api/disconnect', async (req, res) => {
  if (state.deviceId) {
    try { await execAsync(`${ADB} -s ${state.deviceId} forward --remove tcp:9222`); } catch {}
  }
  state = { connected: false, deviceId: null, socket: null, lat: null, lon: null, locationName: null };
  res.json({ success: true });
});

// ---- ステータス ----
app.get('/api/status', (req, res) => res.json(state));

app.listen(PORT, () => {
  console.log(`\n✅ MEO位置情報チェッカー 起動完了`);
  console.log(`🌐 http://localhost:${PORT}\n`);
});
