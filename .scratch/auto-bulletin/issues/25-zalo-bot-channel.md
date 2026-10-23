# 25: Kênh đăng Zalo Bot

**What to build:** Chủ hệ thống nhận **Bản tin** trong cuộc trò chuyện Zalo riêng với một Zalo Bot. Họ thêm **Kênh đăng** loại Zalo trên trang quản lí, gắn vào **Chuyên mục**, và **Bản tin** tới Zalo cùng lúc với Telegram, cùng nội dung, định dạng theo giới hạn của Zalo.

Việc đầu tiên của ticket là thử xem Zalo Bot có chủ động gửi tin cho một người dùng được không, tức không cần người đó vừa nhắn trước. Tài liệu chính thức chưa xác nhận điều này. Nếu không được, ghi kết quả, đóng ticket, và chuyển Zalo sang phần ngoài phạm vi trong spec.

Chỉ dùng Zalo Bot Platform chính thức. Không dùng thư viện điều khiển tài khoản Zalo cá nhân, và không đăng vào nhóm Zalo.

**Blocked by:** 08, 11

**Status:** ready-for-agent

- [ ] Kết quả thử gửi tin chủ động được ghi lại trước khi làm tiếp
- [ ] Thêm được **Kênh đăng** loại Zalo trên trang quản lí và gửi tin thử được
- [ ] **Bản tin** tới Zalo gồm tin nhắn mở đầu, rồi mỗi **Tin** một ảnh và phần chữ gồm tiêu đề, tóm tắt, link
- [ ] Không tin nhắn nào vượt 2.000 ký tự
- [ ] Nội dung **Tin** giống hệt bản Telegram; chỉ định dạng khác
- [ ] Zalo lỗi không chặn và không làm trễ việc phát tới Telegram; lỗi được ghi theo **Kênh đăng** trong **Kỳ**
- [ ] Bộ phát Zalo có test bằng phản hồi đã ghi lại, gồm trường hợp vượt hạn mức
