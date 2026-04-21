# Hệ thống kiểm tra chưa thanh toán — Hướng dẫn cập nhật (2026-04-21)

## Nội dung cập nhật

- Sửa phương thức xác thực OAuth MF Cloud Invoice (khắc phục lỗi 401)

---

## Các bước thực hiện

### BƯỚC 1: Cập nhật file auth.py

```bash
sudo nano /opt/unpaid_check/auth.py
```

Sau khi mở file, tìm hàm `_refresh` (khoảng dòng 103) và thay thế như sau:

**Trước khi thay đổi：**
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

**Sau khi thay đổi：**
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

Tiếp theo, tìm hàm `handle_callback` (khoảng dòng 137) và thay thế phần bên dưới:

**Trước khi thay đổi：**
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

**Sau khi thay đổi：**
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

Sau khi chỉnh sửa, nhấn `Ctrl+X` → `Y` → `Enter` để lưu.

---

### BƯỚC 2: Khởi động lại dịch vụ

```bash
sudo systemctl restart unpaid_check
sudo systemctl status unpaid_check
```

Nếu hiển thị「active (running)」là hoàn thành.

---

### BƯỚC 3: Xác nhận hoạt động

Truy cập `https://check.coaris-ai.com/oauth/start/invoice` trên trình duyệt và hoàn tất xác thực OAuth với MF Cloud Invoice.

Sau khi xác thực, nếu dashboard hiển thị là hoàn thành.

---

## Danh sách file đã thay đổi

| File | Nội dung thay đổi |
|------|------------------|
| `auth.py` | Thay đổi phương thức lấy token OAuth từ Basic Auth sang POST Body |

---

**Hoàn thành. Nếu có thắc mắc, vui lòng liên hệ bên yêu cầu.**
