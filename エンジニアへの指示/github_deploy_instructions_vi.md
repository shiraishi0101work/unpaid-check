# Hướng dẫn thiết lập GitHub & Deploy — 3 dự án LP

---

## Tổng quan

Chúng tôi sẽ vận hành 3 website LP theo quy trình sau:

| Bước | Bên thực hiện | Nội dung |
|------|--------------|----------|
| 1 | **Việt Nam** | Tạo 3 GitHub repository |
| 2 | **Nhật Bản** | Push code lên từng repository |
| 3 | **Việt Nam** | Upload code lên server, cấu hình Web server |
| 4 | **Nhật Bản** | Cung cấp tên miền muốn sử dụng |
| 5 | **Việt Nam** | Hỗ trợ mua tên miền & cấu hình DNS |

---

## 3 Dự án

| # | Tên dự án | Trạng thái | GitHub Repository |
|---|-----------|-----------|-------------------|
| 1 | AI営業リストマスターLP | ✅ Đã có code | Đã tạo sẵn: `ai-list-master-lp` |
| 2 | AIアドマスター | 🔜 Sẽ tạo mới | Cần tạo mới |
| 3 | AI求人マスター | 🔜 Sẽ tạo mới | Cần tạo mới |

---

## STEP 1 — Tạo GitHub Repository (Việt Nam thực hiện)

Tạo **3 repository** trên GitHub với các thiết lập sau:

### Repository 1（đã tồn tại）
- Tên: `ai-list-master-lp`
- URL hiện tại: https://shiraishi0101work.github.io/ai-list-master-lp/

### Repository 2（tạo mới）
- Tên đề xuất: `ai-ad-master-lp`
- Visibility: **Private**（hoặc Public nếu có yêu cầu khác）
- Không cần khởi tạo README

### Repository 3（tạo mới）
- Tên đề xuất: `ai-job-master-lp`
- Visibility: **Private**（hoặc Public nếu có yêu cầu khác）
- Không cần khởi tạo README

> Sau khi tạo xong, vui lòng cung cấp URL của từng repository cho bên Nhật Bản.

---

## STEP 2 — Push code (Nhật Bản thực hiện)

Bên Nhật Bản sẽ push code lên từng repository.  
Bên Việt Nam không cần làm gì ở bước này.

---

## STEP 3 — Deploy lên Server (Việt Nam thực hiện)

Sau khi bên Nhật Bản push code, thực hiện các bước sau cho **từng dự án**:

### 3-1. Clone hoặc Pull code từ GitHub

```bash
# Lần đầu tiên
git clone https://github.com/[tên tài khoản]/[tên repo].git /var/www/[tên dự án]

# Từ lần thứ 2 trở đi (khi có cập nhật)
cd /var/www/[tên dự án]
git pull origin main
```

### 3-2. Cấu hình Web server (Nginx)

Tạo file cấu hình cho từng dự án:

```nginx
server {
    listen 80;
    server_name [tên miền sẽ được cung cấp sau];

    root /var/www/[tên dự án];
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }
}
```

### 3-3. Reload Nginx

```bash
nginx -t
systemctl reload nginx
```

### 3-4. SSL設定（HTTPS化）

```bash
certbot --nginx -d [tên miền]
```

---

## STEP 4 — Cung cấp tên miền (Nhật Bản thực hiện)

Bên Nhật Bản sẽ cung cấp tên miền muốn sử dụng cho từng dự án.  
Bên Việt Nam không cần làm gì ở bước này.

---

## STEP 5 — Mua tên miền & cấu hình DNS (Việt Nam hỗ trợ)

Sau khi nhận được tên miền từ bên Nhật Bản:

1. Hỗ trợ mua tên miền（nếu cần）
2. Cấu hình DNS: trỏ tên miền về IP của server
3. Xác nhận với bên Nhật Bản sau khi hoàn tất

---

## Liên hệ

Nếu có câu hỏi hoặc vấn đề phát sinh, vui lòng liên hệ bên Nhật Bản.

---

*Tài liệu này được tạo ngày 2026-04-28*
