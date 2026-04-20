# Hệ thống Kiểm tra Công nợ — Hướng dẫn Cập nhật (2026-04-20)

## Nội dung cập nhật

- Sửa lỗi hiển thị trùng lặp trong lịch sử hàng tháng
- Thêm tính năng xóa và chỉnh sửa lịch sử hàng tháng

---

## Các bước thực hiện

### STEP 1: Chuyển file lên server

Chuyển file `unpaid_check_update_20260420.zip` lên server và giải nén.

```bash
cd /opt/unpaid_check
unzip -o unpaid_check_update_20260420.zip
```

> Tùy chọn `-o` sẽ ghi đè file cũ mà không cần xác nhận.

---

### STEP 2: Khởi động lại service

```bash
systemctl restart unpaid_check
systemctl status unpaid_check
```

Nếu hiển thị "active (running)" thì hoàn thành.

---

### STEP 3: Kiểm tra hoạt động

Truy cập `https://【tên miền】/history` trên trình duyệt và xác nhận:

- Trên mỗi thẻ danh sách lịch sử có nút thùng rác (xóa cả tháng)
- Trong trang chi tiết, mỗi hàng có nút bút chì (chỉnh sửa) và thùng rác (xóa hàng)
- Nút "この確定を削除"（Xóa xác nhận này）xuất hiện ở góc trên phải trang chi tiết

---

## Danh sách file thay đổi

| File | Nội dung thay đổi |
|------|------------------|
| `app.py` | Sửa logic loại bỏ trùng lặp, thêm API xóa |
| `templates/history.html` | Thêm toàn bộ UI xóa và chỉnh sửa |

---

**Hoàn thành. Nếu có vấn đề, vui lòng liên hệ với bên yêu cầu.**
