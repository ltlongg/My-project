# 01: Chuẩn bị khoá và tài khoản

**What to build:** Chủ hệ thống có sẵn mọi khoá và tài khoản mà lát cắt đầu cần, đặt trong một file cấu hình môi trường không được đưa vào git, để các ticket sau chạy được với dịch vụ thật. Đây là các bước chỉ con người làm được; dùng `/wizard` để dựng một kịch bản dẫn từng bước.

**Blocked by:** None (can start immediately)

**Status:** ready-for-human

- [ ] Có một bot Telegram và token của nó
- [ ] Có một nhóm Telegram thử, bot đã được thêm vào và có quyền gửi tin; biết mã của nhóm
- [ ] Biết mã người dùng Telegram của chủ hệ thống, để bot nhắn riêng và nhận diện **Phản hồi** của chủ
- [ ] Có địa chỉ và khoá của endpoint LLM tương thích OpenAI, và danh sách model dùng được
- [ ] Có khoá Tavily (hoặc Brave)
- [ ] Có khoá Langfuse bản cloud
- [ ] Tất cả nằm trong file cấu hình môi trường; file này bị git bỏ qua, và có một file mẫu liệt kê tên các biến mà không có giá trị
