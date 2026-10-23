# 16: Triển khai lên server

**What to build:** Lát cắt đầu chạy thật. Hệ thống chạy trên server Linux của chủ hệ thống bằng Docker Compose, trang quản lí mở được qua HTTPS trên tên miền của họ, và **Bản tin** công nghệ tới nhóm Telegram thật lúc 8:00 mỗi sáng mà không cần ai bấm.

Các bước cần quyền trên server và tên miền là việc của chủ hệ thống; dùng `/wizard` để dẫn từng bước.

**Blocked by:** 08, 09, 11

**Status:** ready-for-agent

- [ ] Một lệnh dựng toàn bộ hệ thống trên server từ repo và file cấu hình môi trường
- [ ] Trang quản lí chỉ truy cập được qua HTTPS trên tên miền; chứng chỉ tự gia hạn
- [ ] Cơ sở dữ liệu và ảnh chụp nằm trên ổ lưu bền, còn nguyên sau khi dựng lại
- [ ] Dịch vụ tự chạy lại sau khi server khởi động lại
- [ ] Cơ sở dữ liệu được sao lưu định kỳ, và có hướng dẫn khôi phục đã thử
- [ ] Khoá và token chỉ nằm trong cấu hình môi trường trên server, không nằm trong repo hay ảnh Docker
- [ ] Có hướng dẫn ngắn cho việc cập nhật phiên bản mới và xem log
- [ ] **Bản tin** công nghệ tới nhóm thật đúng 8:00 trong ba ngày liên tiếp
