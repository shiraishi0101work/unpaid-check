# Hệ thống Kiểm tra Công nợ Chưa Thu — Hướng dẫn Triển khai Server

> **Dành cho Kỹ sư**  
> Đây là ứng dụng web được xây dựng bằng Python (Flask).  
> Làm theo đúng các bước dưới đây, bạn có thể tải lên server và khởi chạy hệ thống.  
> Không cần hiểu nội dung code. Chỉ cần thực hiện theo từng bước.

---

## ■ Kết quả sau khi hoàn thành

- Truy cập `https://【tên miền đã cài đặt】/` sẽ hiển thị màn hình đăng nhập
- Sau khi đăng nhập, có thể kiểm tra dữ liệu công nợ chưa thu của từng công ty
- Tài khoản quản trị viên có thể xem tổng hợp dữ liệu của tất cả công ty

---

## ■ Yêu cầu Server

| Mục | Yêu cầu |
|-----|---------|
| OS | Ubuntu 20.04 / 22.04 (khuyến nghị) |
| Python | **3.11 trở lên** (khuyến nghị 3.12) |
| RAM | 1GB trở lên |
| Ổ cứng | 5GB trở lên |
| Port mở | 80 (HTTP), 443 (HTTPS) |

---

## ■ STEP 1: Giải nén file lên server

Chuyển file `unpaid_check_system.zip` lên server và giải nén.

```bash
mkdir -p /opt/unpaid_check
cd /opt/unpaid_check
unzip unpaid_check_system.zip
```

---

## ■ STEP 2: Cài đặt các package Python

```bash
cd /opt/unpaid_check

# Tạo môi trường ảo
python3 -m venv venv
source venv/bin/activate

# Cài đặt các package cần thiết
pip install -r requirements.txt
```

---

## ■ STEP 3: Tạo file cấu hình (.env)

```bash
cp .env.example .env
nano .env
```

Sau khi mở file `.env`, dán nội dung sau vào (chỉ thay đổi phần 【tên miền】):

```
MF_INVOICE_CLIENT_ID=239946377590530
MF_INVOICE_CLIENT_SECRET=4VCKMJWJq3tZvbxMs3JDbOygt9ImXJdfJ6QCDPEMPAjHEkva_Xxi5VtQZYMhK8Z4-5RIHJwbcs315ZzWFWaf6A
MF_INVOICE_REDIRECT_URI=https://【tên miền】/oauth/callback/invoice

PORT=5000
FLASK_DEBUG=false
FLASK_SECRET_KEY=（Dán chuỗi được tạo bằng lệnh dưới đây）

SCHEDULE_ENABLED=false
SCHEDULE_CRON=0 9 * * 1-5
```

**Tạo FLASK_SECRET_KEY (bắt buộc thực hiện):**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```
Dán chuỗi ký tự được xuất ra vào sau `FLASK_SECRET_KEY=`.

---

## ■ STEP 4: Tạo file thông tin tài khoản

Tạo file `data/auth.json` với nội dung sau.  
File này chứa thông tin tài khoản đăng nhập.

```bash
mkdir -p data
cat > data/auth.json << 'EOF'
{
  "companies": [
    {
      "id": "c_admin",
      "email": "kanri@coaris.co.jp",
      "password_hash": "scrypt:32768:8:1$mmQhdYz33EcBhjat$01c0e4a5243fec2e0bbcefa15a9a28951b475eb98f4d5e1371b23ccec975e51f79fd19f81c86332f26dc79ad1eb6429a30f5898dc37f5eb261bde2ca25089306",
      "is_admin": true,
      "created_at": "2026-04-20T00:00:00.000000"
    },
    {
      "id": "c_main",
      "email": "info@dellaforce.com",
      "password_hash": "scrypt:32768:8:1$l11Sp8prejehCuP8$7b232c193464595cf7d5fe43f5e3d240080d9c7849af45eb9072ea384a3c09a444b5674bcb18ad7d555a014374df74243bbc576d9cf85347a89d8c7b7cdaa9f8",
      "is_admin": false,
      "created_at": "2026-04-20T13:08:47.381802"
    },
    {
      "id": "c_c85279d3",
      "email": "kimanet@gmail.com",
      "password_hash": "scrypt:32768:8:1$TI8cUErIHlieEGgg$877236186dc46d78e8771412be94d256517e3e9faf2e25ba8fac2c2a5253362c623fe848ea64d7cf2be895ee79e5e0bffdf76d5447a536040f2f038744e8dabe",
      "is_admin": false,
      "created_at": "2026-04-20T13:30:11.083328"
    }
  ]
}
EOF
```

---

## ■ STEP 5: Tạo các thư mục cần thiết

```bash
mkdir -p data tokens output
```

---

## ■ STEP 6: Kiểm tra hoạt động (khởi động tạm thời)

```bash
source venv/bin/activate
python app.py
```

Truy cập `http://【IP server】:5000` trên trình duyệt.  
Nếu màn hình đăng nhập hiển thị thì thành công. Sau khi kiểm tra, nhấn `Ctrl+C` để dừng.

---

## ■ STEP 7: Chạy production (gunicorn + systemd)

### Tạo file service systemd

```bash
nano /etc/systemd/system/unpaid_check.service
```

Dán nội dung sau:

```ini
[Unit]
Description=Unpaid Check System
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/unpaid_check
Environment="PATH=/opt/unpaid_check/venv/bin"
ExecStart=/opt/unpaid_check/venv/bin/gunicorn -w 2 -b 0.0.0.0:5000 app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Kích hoạt và khởi động service

```bash
systemctl daemon-reload
systemctl enable unpaid_check
systemctl start unpaid_check
systemctl status unpaid_check
```

Nếu hiển thị "active (running)" thì bình thường.

---

## ■ STEP 8: Cấu hình nginx + HTTPS

### Tạo file cấu hình nginx

```bash
nano /etc/nginx/sites-available/unpaid_check
```

Dán nội dung sau (thay 【tên miền】 bằng tên miền thực tế):

```nginx
server {
    listen 80;
    server_name 【tên miền】;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
ln -s /etc/nginx/sites-available/unpaid_check /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

### Cài đặt HTTPS (Let's Encrypt)

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d 【tên miền】
```

Làm theo hướng dẫn để hoàn tất việc cài đặt HTTPS.

---

## ■ STEP 9: Cập nhật cài đặt OAuth của MF Cloud Invoice

**Nếu bỏ qua bước này, tính năng kết nối MF sẽ không hoạt động.**

1. Đăng nhập vào MF Cloud Invoice Developer Console  
   → https://invoice.moneyforward.com/developer

2. Mở OAuth app tương ứng (CLIENT_ID: `239946377590530`)

3. Thay đổi Redirect URI thành:
   ```
   https://【tên miền】/oauth/callback/invoice
   ```

4. Lưu lại

---

## ■ STEP 10: Xác thực lại kết nối MF Cloud

Sau khi chuyển server, mỗi tài khoản công ty cần xác thực lại với MF Cloud.  
(Token không được đưa vào ZIP vì lý do bảo mật)

Đăng nhập bằng tài khoản từng công ty, vào màn hình cài đặt và nhấn nút **「MFクラウド請求書 連携」** (Kết nối MF Cloud Invoice) để xác thực.

---

## ■ Danh sách tài khoản đăng nhập

| Loại | Email | Mật khẩu | Quyền hạn |
|------|-------|----------|-----------|
| Quản trị viên | kanri@coaris.co.jp | kanri@1111 | Xem tất cả công ty |
| Thông thường (Della Force) | info@dellaforce.com | （giữ nguyên mật khẩu cũ） | Chỉ xem công ty mình |
| Thông thường | kimanet@gmail.com | （giữ nguyên mật khẩu cũ） | Chỉ xem công ty mình |

> Mật khẩu của `info@dellaforce.com` và `kimanet@gmail.com` không thay đổi,  
> có thể đăng nhập bằng mật khẩu hiện tại.

---

## ■ Xử lý sự cố

| Triệu chứng | Nơi kiểm tra |
|-------------|-------------|
| Không khởi động được | Kiểm tra thiếu sót trong `.env`, kiểm tra phiên bản Python |
| Không kết nối được MF | Kiểm tra Redirect URI có khớp với cài đặt ở STEP 9 không |
| Lỗi 500 | Kiểm tra log bằng `journalctl -u unpaid_check -f` |
| Không hiển thị trang | Kiểm tra `systemctl status unpaid_check` và `systemctl status nginx` |

---

## ■ Danh sách file đính kèm

| File | Nội dung |
|------|---------|
| `unpaid_check_system.zip` | Toàn bộ source code hệ thống |
| `[Engineer] Server Deployment Guide (Vietnamese).md / .html` | Tài liệu hướng dẫn này |

---

**Sau khi hoàn thành, hãy truy cập `https://【tên miền】` và xác nhận có thể đăng nhập được.**  
**Nếu có vấn đề không rõ, vui lòng liên hệ với bên yêu cầu.**
