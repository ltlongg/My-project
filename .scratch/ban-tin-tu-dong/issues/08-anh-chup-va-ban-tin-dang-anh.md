# 08: Ảnh chụp và Bản tin dạng ảnh

**What to build:** **Bản tin** trên Telegram có hình dạng cuối cùng: một tin nhắn mở đầu nêu tên **Chuyên mục** và ngày, rồi mỗi **Tin** là một tin nhắn ảnh chụp **Bài gốc chính** kèm chú thích gồm tiêu đề, tóm tắt và link. Ảnh được chụp bằng Playwright; không chụp được thì dùng ảnh đại diện của bài; không có cả hai thì **Tin** vẫn được phát, không ảnh.

**Blocked by:** 04

**Status:** ready-for-agent

- [ ] Có một module "nhận địa chỉ, trả về ảnh" theo thứ tự: ảnh chụp trang, ảnh đại diện, không ảnh
- [ ] Ảnh chụp thấy được tiêu đề và phần đầu bài, không bị bảng cookie che ở các trang phổ biến trong danh sách **Nguồn**
- [ ] Trang chặn trình duyệt tự động, quá thời gian hoặc có tường phí thì rơi xuống ảnh đại diện, không làm hỏng **Kỳ**
- [ ] **Bản tin** mở đầu bằng một tin nhắn nêu tên **Chuyên mục** và ngày
- [ ] Mỗi **Tin** là một tin nhắn riêng; chú thích không vượt 1.024 ký tự
- [ ] **Tin** "Cập nhật" hiện nhãn đó trong chú thích
- [ ] Ảnh và nội dung đúng như đã gửi được lưu theo **Tin**, để xem lại sau
- [ ] Bộ phát Telegram có test bằng dữ liệu đã ghi lại cho: có ảnh, không ảnh, chú thích sát giới hạn, và Telegram trả lỗi
