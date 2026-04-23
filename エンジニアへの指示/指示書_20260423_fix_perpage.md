# TÀI LIỆU HƯỚNG DẪN TRIỂN KHAI

**Ngày:** 2026-04-23  
**Hệ thống:** https://check.coaris-ai.com/login  
**Nội dung:** Sửa lỗi 400 Bad Request khi nhấn nút「まとめて再確認（MF会計）」

---

## Nguyên nhân lỗi

Khi nhấn nút「まとめて再確認（MF会計）」, hệ thống gửi request đến MF Cloud Kế toán với `per_page=10000`, vượt quá giới hạn tối đa của API (100). API trả về lỗi 400 Bad Request.

**Lỗi hiển thị:**
```
エラー: MFクラウド会計APIエラー: 400 Client Error: Bad Request for url:
https://api-accounting.moneyforward.com/api/v3/journals?...per_page=10000...
```

---

## File cần thay thế (1 file)

File đính kèm: `update_20260423_fix_perpage.zip`

| Tên file | Vị trí trên server |
|----------|-------------------|
| `mf_accounting.py` | Thư mục gốc của ứng dụng |

**Thay đổi:** Dòng 51: `"per_page": 10000` → `"per_page": 100`

---

## Quy trình thực hiện

```
1. Backup file hiện tại:
   mf_accounting.py → mf_accounting.py.bak_20260423

2. Giải nén update_20260423_fix_perpage.zip

3. Upload ghi đè mf_accounting.py lên server

4. Restart ứng dụng Flask

5. Kiểm tra: Đăng nhập bằng kimanet@gmail.com
   → Nhấn「まとめて再確認（MF会計）」
   → Không còn lỗi 400
```

---

## Lưu ý

- Chỉ thay thế `mf_accounting.py`, không cần thay đổi file khác
- **Tuyệt đối không ghi đè file `.env`**
- **Tuyệt đối không chạm vào thư mục `data/`**

---

**Thời gian dự kiến hoàn thành: 5〜10 phút**
