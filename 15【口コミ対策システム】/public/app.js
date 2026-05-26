// ======= 地図初期化 =======
const map = L.map('map', {
  center: [35.6812, 139.7671],
  zoom: 11,
  zoomControl: true
});

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19
}).addTo(map);

// ======= 状態 =======
let selectedLat = null;
let selectedLon = null;
let selectedName = '選択した地点';
let marker = null;
let isConnected = false;

// ======= DOM =======
const btnScan = document.getElementById('btn-scan');
const btnConnect = document.getElementById('btn-connect');
const btnApply = document.getElementById('btn-apply');
const btnReset = document.getElementById('btn-reset');
const btnSearch = document.getElementById('btn-search');
const deviceSelect = document.getElementById('device-select');
const connStatus = document.getElementById('conn-status');
const pinInfo = document.getElementById('pin-info');
const pinName = document.getElementById('pin-name');
const pinCoords = document.getElementById('pin-coords');
const searchInput = document.getElementById('search-input');
const searchResults = document.getElementById('search-results');
const currentLocationCard = document.getElementById('current-location-card');
const currentLocationInfo = document.getElementById('current-location-info');

// ======= トースト =======
let toastTimer = null;
function showToast(msg, type = 'info') {
  const toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.className = `toast ${type} show`;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 3500);
}

// ======= ピン表示 =======
function setPin(lat, lon, name) {
  selectedLat = lat;
  selectedLon = lon;
  selectedName = name || '選択した地点';

  if (marker) map.removeLayer(marker);

  const icon = L.divIcon({
    className: '',
    html: `<div style="
      width:18px;height:18px;
      background:#ef4444;
      border:3px solid #fff;
      border-radius:50% 50% 50% 0;
      transform:rotate(-45deg);
      box-shadow:0 2px 8px rgba(0,0,0,0.5);
    "></div>`,
    iconSize: [18, 18],
    iconAnchor: [9, 18]
  });

  marker = L.marker([lat, lon], { icon }).addTo(map);

  pinName.textContent = selectedName;
  pinCoords.textContent = `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
  pinInfo.style.display = 'flex';

  // プリセットのアクティブ状態更新
  document.querySelectorAll('.preset-btn').forEach(b => {
    const bLat = parseFloat(b.dataset.lat);
    const bLon = parseFloat(b.dataset.lon);
    b.classList.toggle('active', Math.abs(bLat - lat) < 0.001 && Math.abs(bLon - lon) < 0.001);
  });
}

// ======= 地図クリック =======
map.on('click', async (e) => {
  const { lat, lng } = e.latlng;
  setPin(lat, lng, '選択した地点');

  // 逆ジオコーディング（Nominatim）
  try {
    const r = await fetch(
      `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json&accept-language=ja`
    );
    const data = await r.json();
    if (data && data.display_name) {
      const parts = data.display_name.split(',');
      const shortName = parts.slice(0, 3).join('').trim();
      setPin(lat, lng, shortName || '選択した地点');
    }
  } catch {}
});

// ======= デバイス検出 =======
btnScan.addEventListener('click', async () => {
  btnScan.disabled = true;
  btnScan.textContent = '検出中...';

  try {
    const r = await fetch('/api/devices');
    const data = await r.json();

    if (data.error) {
      showToast(data.error, 'error');
      return;
    }

    if (data.devices.length === 0) {
      showToast('デバイスが見つかりません。USBデバッグが有効か確認してください。', 'error');
      return;
    }

    deviceSelect.innerHTML = '<option value="">-- デバイスを選択 --</option>' +
      data.devices.map(d => `<option value="${d.id}">${d.id}</option>`).join('');
    deviceSelect.style.display = 'block';
    btnConnect.style.display = 'block';

    showToast(`${data.devices.length}台のデバイスを検出しました`, 'success');
  } catch (e) {
    showToast('エラー: ' + e.message, 'error');
  } finally {
    btnScan.disabled = false;
    btnScan.textContent = 'デバイスを検出';
  }
});

// ======= Chrome接続 =======
btnConnect.addEventListener('click', async () => {
  const deviceId = deviceSelect.value;
  if (!deviceId) { showToast('デバイスを選択してください', 'error'); return; }

  btnConnect.disabled = true;
  btnConnect.textContent = '接続中...';
  setStatusBadge('connecting');

  try {
    const r = await fetch('/api/connect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ deviceId })
    });
    const data = await r.json();

    if (data.success) {
      isConnected = true;
      setStatusBadge('connected', deviceId);
      showToast(`接続成功（${data.socket}）`, 'success');
      btnConnect.textContent = '再接続';
    } else {
      isConnected = false;
      setStatusBadge('error');
      showToast(data.error, 'error');
    }
  } catch (e) {
    showToast('接続エラー: ' + e.message, 'error');
    setStatusBadge('error');
  } finally {
    btnConnect.disabled = false;
    if (!isConnected) btnConnect.textContent = 'Chromeに接続';
  }
});

// ======= 位置適用 =======
btnApply.addEventListener('click', async () => {
  if (!isConnected) {
    showToast('先にデバイスに接続してください', 'error');
    return;
  }
  if (selectedLat === null) {
    showToast('地図上の場所をクリックしてください', 'error');
    return;
  }

  btnApply.disabled = true;
  btnApply.textContent = '適用中...';

  try {
    const r = await fetch('/api/set-location', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lat: selectedLat, lon: selectedLon, name: selectedName })
    });
    const data = await r.json();

    if (data.success) {
      showToast(`✓ 位置情報を適用しました（${data.tabCount}タブ）`, 'success');
      updateCurrentLocation(selectedLat, selectedLon, selectedName);
    } else {
      showToast(data.error, 'error');
    }
  } catch (e) {
    showToast('エラー: ' + e.message, 'error');
  } finally {
    btnApply.disabled = false;
    btnApply.textContent = 'この場所を適用';
  }
});

// ======= 位置リセット =======
btnReset.addEventListener('click', async () => {
  btnReset.disabled = true;
  try {
    const r = await fetch('/api/reset-location', { method: 'POST' });
    const data = await r.json();
    if (data.success) {
      showToast('位置情報をリセットしました', 'info');
      currentLocationCard.style.display = 'none';
    } else {
      showToast(data.error, 'error');
    }
  } catch (e) {
    showToast('エラー: ' + e.message, 'error');
  } finally {
    btnReset.disabled = false;
  }
});

// ======= 住所検索（Nominatim） =======
btnSearch.addEventListener('click', doSearch);
searchInput.addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });

async function doSearch() {
  const q = searchInput.value.trim();
  if (!q) return;

  btnSearch.disabled = true;
  btnSearch.textContent = '...';
  searchResults.innerHTML = '<div style="color:#64748b;font-size:12px;padding:4px">検索中...</div>';

  try {
    const r = await fetch(
      `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(q)}&format=json&limit=6&accept-language=ja&countrycodes=jp`
    );
    const items = await r.json();

    if (items.length === 0) {
      searchResults.innerHTML = '<div style="color:#64748b;font-size:12px;padding:4px">見つかりませんでした</div>';
      return;
    }

    searchResults.innerHTML = items.map((item, i) =>
      `<div class="search-result-item" data-lat="${item.lat}" data-lon="${item.lon}" data-name="${item.display_name.split(',').slice(0,3).join('')}">
        ${item.display_name.split(',').slice(0, 3).join('、')}
      </div>`
    ).join('');

    searchResults.querySelectorAll('.search-result-item').forEach(el => {
      el.addEventListener('click', () => {
        const lat = parseFloat(el.dataset.lat);
        const lon = parseFloat(el.dataset.lon);
        const name = el.dataset.name;
        setPin(lat, lon, name);
        map.setView([lat, lon], 15);
        searchResults.innerHTML = '';
      });
    });
  } catch (e) {
    searchResults.innerHTML = '<div style="color:#f87171;font-size:12px;padding:4px">検索エラー</div>';
  } finally {
    btnSearch.disabled = false;
    btnSearch.textContent = '検索';
  }
}

// ======= プリセットボタン =======
document.querySelectorAll('.preset-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const lat = parseFloat(btn.dataset.lat);
    const lon = parseFloat(btn.dataset.lon);
    const name = btn.dataset.name;
    setPin(lat, lon, name);
    map.setView([lat, lon], 13);
  });
});

// ======= ヘルパー =======
function setStatusBadge(state, deviceId) {
  const badge = document.getElementById('conn-status');
  if (state === 'connected') {
    badge.textContent = `接続中: ${deviceId}`;
    badge.className = 'status-badge status-connected';
  } else if (state === 'error') {
    badge.textContent = '接続失敗';
    badge.className = 'status-badge status-error';
  } else if (state === 'connecting') {
    badge.textContent = '接続中...';
    badge.className = 'status-badge status-disconnected';
  } else {
    badge.textContent = '未接続';
    badge.className = 'status-badge status-disconnected';
  }
}

function updateCurrentLocation(lat, lon, name) {
  currentLocationCard.style.display = 'flex';
  currentLocationInfo.innerHTML =
    `<b>${name}</b><br>` +
    `緯度: ${lat.toFixed(5)}<br>` +
    `経度: ${lon.toFixed(5)}`;
}

// ======= 初期ステータス確認 =======
(async () => {
  try {
    const r = await fetch('/api/status');
    const data = await r.json();
    if (data.connected) {
      isConnected = true;
      setStatusBadge('connected', data.deviceId);
      if (data.lat && data.lon) {
        updateCurrentLocation(data.lat, data.lon, data.locationName || '適用中');
        setPin(data.lat, data.lon, data.locationName || '適用中');
        map.setView([data.lat, data.lon], 13);
      }
    }
  } catch {}
})();
