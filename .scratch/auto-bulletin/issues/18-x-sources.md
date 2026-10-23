# 18: Nguồn X

**What to build:** Chủ hệ thống theo dõi các tài khoản X họ tin. Trên trang quản lí họ nạp cookies của một phiên đăng nhập X và cấu hình proxy, rồi thêm tài khoản X làm **Nguồn**. Bài đăng gốc và chuỗi bài của các tài khoản đó thành **Bài gốc**. Việc thu thập dùng Playwright. Khi X chặn hoặc phiên hết hạn, các **Kỳ** bỏ qua X, vẫn ra **Bản tin** từ các **Nguồn** khác, và bot nhắn riêng cho chủ hệ thống để nạp lại.

Việc đầu tiên của ticket là thử xem Playwright có lấy được bài của một tài khoản từ IP của server qua proxy không. Nếu không, dừng và báo lại trước khi làm phần còn lại.

Điều khoản của X cấm thu thập tự động; chủ hệ thống đã biết và chấp nhận rủi ro tài khoản bị hạn chế. Bộ thu thập phải thay được bằng cách khác mà không đụng tới phần còn lại.

**Blocked by:** 09, 11

**Status:** ready-for-agent

- [ ] Kết quả thử từ IP server qua proxy được ghi lại trước khi làm tiếp
- [ ] Nạp và thay được cookies phiên đăng nhập X trên trang quản lí; cookies được mã hoá khi lưu và không bao giờ hiện lại đầy đủ
- [ ] Cấu hình được proxy cho việc thu thập X trên trang quản lí
- [ ] Thêm được **Nguồn** loại tài khoản X bằng tên tài khoản và bấm thử được
- [ ] Chỉ bài đăng gốc và chuỗi bài của chính tài khoản đó thành **Bài gốc**; trả lời và đăng lại bị bỏ
- [ ] Một chuỗi bài thành một **Bài gốc**, không phải nhiều
- [ ] Ảnh của **Tin** có **Bài gốc chính** là bài X là ảnh chụp bài đăng đó
- [ ] Khi bị chặn hoặc hết phiên: **Nguồn** X được ghi là lỗi, **Kỳ** vẫn chạy, và chủ hệ thống nhận đúng một tin nhắn riêng cho mỗi lần sự cố, không lặp lại mỗi lần thu thập
- [ ] Tốc độ thu thập có giới hạn cấu hình được
- [ ] Bộ thu thập có test bằng phản hồi đã ghi lại, gồm trường hợp bị chặn và hết phiên
