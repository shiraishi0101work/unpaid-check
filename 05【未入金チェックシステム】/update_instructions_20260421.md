# 未入金チェックシステム — アップデート手順書（2026-04-21）

## 更新内容

- MFクラウド請求書のOAuth認証方式を修正（401エラー対策）

---

## 作業手順

### STEP 1: auth.py を更新する

```bash
sudo nano /opt/unpaid_check/auth.py
```

ファイルを開いたら、`_refresh` 関数（103行目付近）を以下に書き換えてください：

**変更前：**
```python
def _refresh(service_name: str, token_data: dict, company_id: str = "") -> dict:
    svc     = _svc(service_name)
    headers = _basic_auth_header(svc["client_id"], svc["client_secret"])
    resp    = requests.post(svc["token_url"], headers=headers, data={
        "grant_type":    "refresh_token",
        "refresh_token": token_data["refresh_token"],
    })
    resp.raise_for_status()
    new_token = resp.json()
    save_token(service_name, new_token, company_id)
    return new_token
```

**変更後：**
```python
def _refresh(service_name: str, token_data: dict, company_id: str = "") -> dict:
    svc  = _svc(service_name)
    resp = requests.post(svc["token_url"], data={
        "grant_type":    "refresh_token",
        "refresh_token": token_data["refresh_token"],
        "client_id":     svc["client_id"],
        "client_secret": svc["client_secret"],
    })
    resp.raise_for_status()
    new_token = resp.json()
    save_token(service_name, new_token, company_id)
    return new_token
```

---

次に、`handle_callback` 関数（137行目付近）を以下に書き換えてください：

**変更前：**
```python
    svc     = _svc(service_name)
    headers = _basic_auth_header(svc["client_id"], svc["client_secret"])
    resp    = requests.post(svc["token_url"], headers=headers, data={
        "grant_type":   "authorization_code",
        "code":          code,
        "redirect_uri":  svc["redirect_uri"],
    })
    resp.raise_for_status()
    save_token(service_name, resp.json(), company_id)
    return True, company_id
```

**変更後：**
```python
    svc  = _svc(service_name)
    resp = requests.post(svc["token_url"], data={
        "grant_type":    "authorization_code",
        "code":           code,
        "redirect_uri":   svc["redirect_uri"],
        "client_id":      svc["client_id"],
        "client_secret":  svc["client_secret"],
    })
    resp.raise_for_status()
    save_token(service_name, resp.json(), company_id)
    return True, company_id
```

編集後、`Ctrl+X` → `Y` → `Enter` で保存してください。

---

### STEP 2: サービスを再起動

```bash
sudo systemctl restart unpaid_check
sudo systemctl status unpaid_check
```

「active (running)」と表示されれば完了です。

---

### STEP 3: 動作確認

ブラウザで `https://check.coaris-ai.com/oauth/start/invoice` にアクセスし、MFクラウド請求書のOAuth認証を完了してください。

認証後、ダッシュボードが表示されれば完了です。

---

## 変更ファイル一覧

| ファイル | 変更内容 |
|----------|---------|
| `auth.py` | OAuthトークン取得方式をBasic認証からPOST Body方式に変更 |

---

**以上で完了です。不明点は依頼元にご連絡ください。**
