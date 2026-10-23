# 09: Lịch, thử lại và thông báo riêng

**What to build:** Hệ thống tự chạy không cần ai bấm. Việc thu thập **Bài gốc** chạy định kỳ trong ngày; **Kỳ** của mỗi **Chuyên mục** tự chạy đúng giờ phát của nó theo giờ Việt Nam. **Kỳ** hỏng được thử lại sau 30 phút, tối đa ba lần. Khi một **Kỳ** hỏng hẳn hoặc không phát, bot nhắn riêng cho chủ hệ thống kèm lí do. Một **Nguồn** hỏng không làm hỏng **Kỳ**.

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] **Kỳ** của một **Chuyên mục** tự chạy đúng giờ phát đã khai, theo múi giờ Asia/Ho_Chi_Minh
- [ ] Việc thu thập chạy định kỳ, tách khỏi **Kỳ**; **Kỳ** dùng những **Bài gốc** đã thu thập
- [ ] **Kỳ** hỏng được thử lại sau 30 phút, tối đa ba lần, rồi dừng
- [ ] Một **Bản tin** không bao giờ được phát hai lần cho cùng một **Kỳ**, kể cả khi thử lại hoặc khởi động lại giữa chừng
- [ ] Chủ hệ thống nhận tin nhắn riêng khi **Kỳ** hỏng hẳn hoặc không phát, có tên **Chuyên mục** và lí do
- [ ] Lỗi của một **Nguồn** được ghi lại theo **Nguồn** và **Kỳ** vẫn chạy với các **Nguồn** còn lại
- [ ] **Chuyên mục** đang tạm dừng không chạy **Kỳ**
- [ ] Khởi động lại dịch vụ không làm mất lịch và không chạy bù hàng loạt các **Kỳ** đã lỡ
- [ ] Test tại điểm "Chạy Kỳ" với đồng hồ giả phủ: đúng giờ, thử lại, dừng sau ba lần, thông báo, và **Nguồn** hỏng
