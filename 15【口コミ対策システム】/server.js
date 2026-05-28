const express = require('express');
const { exec } = require('child_process');
const CDP = require('chrome-remote-interface');
const http = require('http');
const WebSocket = require('ws');
const path = require('path');
const util = require('util');
const execAsync = util.promisify(exec);

// 生WebSocketで1コマンドだけ送る（Chromeへの負荷最小）
function sendCDPCommand(wsUrl, method, params = {}) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    const timer = setTimeout(() => { ws.terminate(); reject(new Error('timeout')); }, 5000);

    ws.on('open', () => {
      ws.send(JSON.stringify({ id: 1, method, params }));
    });
    ws.on('message', (data) => {
      clearTimeout(timer);
      ws.close();
      resolve(JSON.parse(data));
    });
    ws.on('error', (e) => { clearTimeout(timer); reject(e); });
  });
}

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
  locationName: null,
  keepAliveTimer: null
};

// ---- デバイス全体のモック位置情報をセット ----
async function setDeviceLocation(deviceId, lat, lon) {
  const ts = Date.now();
  await execAsync(`${ADB} -s ${deviceId} shell appops set android.uid.shell android:mock_location allow`);
  await execAsync(`${ADB} -s ${deviceId} shell cmd location set-test-provider-enabled gps true`);
  await execAsync(`${ADB} -s ${deviceId} shell cmd location set-test-provider-location gps ${lat} ${lon} 0 1 0 0 ${ts}`);
}

// ---- デバイスのモック位置情報をリセット ----
async function resetDeviceLocation(deviceId) {
  try {
    await execAsync(`${ADB} -s ${deviceId} shell cmd location set-test-provider-enabled gps false`);
  } catch {}
}

// ---- keepAlive停止 ----
function stopKeepAlive() {
  if (state.keepAliveTimer) {
    clearInterval(state.keepAliveTimer);
    state.keepAliveTimer = null;
  }
}

// ---- keepAlive開始（30秒ごとに座標を再送） ----
function startKeepAlive(deviceId, lat, lon) {
  stopKeepAlive();
  state.keepAliveTimer = setInterval(async () => {
    if (!state.connected || state.lat === null) return;
    try {
      await setDeviceLocation(deviceId, lat, lon);
    } catch {}
  }, 30000);
}

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
    // HTTP でタブ一覧取得（WebSocket不使用）
    const targets = await CDP.List({ port: 9222 });
    const pages = targets.filter(t => t.type === 'page' && t.webSocketDebuggerUrl);

    if (pages.length === 0) {
      return res.json({ error: 'Chrome のタブが見つかりません。Chrome で何かページを開いてください。' });
    }

    // 最初の1タブにだけ送る（最小負荷）
    const wsUrl = pages[0].webSocketDebuggerUrl.replace('ws://localhost', 'ws://127.0.0.1');
    console.log('Connecting to:', wsUrl);

    await sendCDPCommand(wsUrl, 'Emulation.setGeolocationOverride',
      { latitude, longitude, accuracy: 10 });

    state.lat = latitude;
    state.lon = longitude;
    state.locationName = name || null;

    // デバイス全体にもモック位置情報をセット
    let deviceSuccess = false;
    try {
      await setDeviceLocation(state.deviceId, latitude, longitude);
      deviceSuccess = true;
      startKeepAlive(state.deviceId, latitude, longitude);
    } catch (err) {
      console.warn('デバイスGPS設定失敗（Chromeのみ適用）:', err.message);
    }

    res.json({ success: true, lat: latitude, lon: longitude, tabCount: 1, deviceGps: deviceSuccess });
  } catch (err) {
    res.json({ error: `位置情報の設定に失敗しました: ${err.message}` });
  }
});

// ---- 位置情報をリセット ----
app.post('/api/reset-location', async (req, res) => {
  if (!state.connected) return res.json({ error: '接続されていません' });

  stopKeepAlive();

  // Chromeリセット
  try {
    const client = await CDP({ port: 9222 });
    try {
      const { targetInfos } = await client.Target.getTargets();
      const pages = targetInfos.filter(t => t.type === 'page');
      for (const target of pages) {
        try {
          const { sessionId } = await client.Target.attachToTarget({ targetId: target.targetId, flatten: true });
          await client.send('Emulation.clearGeolocationOverride', {}, sessionId);
          await client.Target.detachFromTarget({ sessionId });
        } catch {}
      }
    } finally {
      await client.close();
    }
  } catch (err) {
    console.warn('Chrome GPSリセット失敗:', err.message);
  }

  // デバイスリセット
  await resetDeviceLocation(state.deviceId);

  state.lat = null;
  state.lon = null;
  state.locationName = null;

  res.json({ success: true });
});

// 全角数字・ハイフン → 半角に正規化
function normalizeAddress(q) {
  return q
    .replace(/[０-９]/g, c => String.fromCharCode(c.charCodeAt(0) - 0xFEE0))
    .replace(/[‐－―]/g, '-')
    .replace(/　/g, ' ');
}

// 国土地理院API検索
async function searchGSI(q) {
  const url = `https://msearch.gsi.go.jp/address-search/AddressSearch?q=${encodeURIComponent(q)}`;
  const { stdout } = await execAsync(`curl -s "${url}" -H "User-Agent: MEO-LocationChecker/1.0"`);
  const data = JSON.parse(stdout);
  if (!data || data.length === 0) return [];
  return data.slice(0, 6).map(item => ({
    display_name: item.properties.title,
    lat: String(item.geometry.coordinates[1]),
    lon: String(item.geometry.coordinates[0])
  }));
}

// ---- 住所検索プロキシ（国土地理院API → Nominatimフォールバック）----
app.get('/api/search', async (req, res) => {
  const q = req.query.q;
  if (!q) return res.json([]);

  // 1. 入力そのまま
  try {
    const results = await searchGSI(q);
    if (results.length > 0) return res.json(results);
  } catch {}

  // 2. 全角→半角に正規化して再検索
  const normalized = normalizeAddress(q);
  if (normalized !== q) {
    try {
      const results = await searchGSI(normalized);
      if (results.length > 0) return res.json(results);
    } catch {}
  }

  // 3. フォールバック: Nominatim
  try {
    const nomUrl = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(normalized)}&format=json&limit=6&accept-language=ja&countrycodes=jp`;
    const { stdout } = await execAsync(`curl -s "${nomUrl}" -H "User-Agent: MEO-LocationChecker/1.0"`);
    const data = JSON.parse(stdout);
    if (data.length > 0) return res.json(data);
  } catch {}

  // 4. 番地を除いた住所で再検索（最終手段）
  const withoutNumber = normalized.replace(/\d+[-－]\d+[-－]?\d*$/, '').replace(/\d+$/, '').trim();
  if (withoutNumber && withoutNumber !== normalized) {
    try {
      const results = await searchGSI(withoutNumber);
      if (results.length > 0) return res.json(results.map(r => ({ ...r, display_name: r.display_name + '（近辺）' })));
    } catch {}
  }

  res.json([]);
});

// ---- 切断 ----
app.post('/api/disconnect', async (req, res) => {
  stopKeepAlive();
  if (state.deviceId) {
    await resetDeviceLocation(state.deviceId);
    try { await execAsync(`${ADB} -s ${state.deviceId} forward --remove tcp:9222`); } catch {}
  }
  state = { connected: false, deviceId: null, socket: null, lat: null, lon: null, locationName: null, keepAliveTimer: null };
  res.json({ success: true });
});

// ---- ステータス ----
app.get('/api/status', (req, res) => res.json(state));

app.listen(PORT, () => {
  console.log(`\n✅ MEO位置情報チェッカー 起動完了`);
  console.log(`🌐 http://localhost:${PORT}\n`);
});
