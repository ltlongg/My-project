# 27: Xoá dữ liệu cũ

**What to build:** Ổ đĩa của server không đầy dần theo thời gian. **Bài gốc** và ảnh chụp cũ hơn 90 ngày được tự động xoá. Những gì chủ hệ thống cần tra lại được giữ vĩnh viễn: **Bản tin**, **Tin** đã phát cùng ảnh và nội dung đúng như đã gửi, **Phản hồi**, và mọi phiên bản **Hướng dẫn**.

**Blocked by:** 08

**Status:** ready-for-agent

- [ ] **Bài gốc** cũ hơn 90 ngày mà không thuộc **Tin** đã phát nào bị xoá, gồm cả toàn văn
- [ ] Ảnh chụp cũ hơn 90 ngày không gắn với **Tin** đã phát nào bị xoá khỏi ổ đĩa
- [ ] **Tin** đã phát giữ nguyên tiêu đề, tóm tắt, ảnh và link sau khi dọn; trang **Bản tin** cũ vẫn hiện đủ
- [ ] **Bản tin**, **Phản hồi** và các phiên bản **Hướng dẫn** không bao giờ bị xoá
- [ ] Quy tắc không phát lại vẫn đúng sau khi dọn: một sự kiện đã phát không quay lại chỉ vì **Bài gốc** của nó đã bị xoá
- [ ] Việc dọn chạy định kỳ, ngoài giờ phát, và ghi lại đã xoá bao nhiêu
- [ ] Số ngày giữ cấu hình được
- [ ] Test với đồng hồ giả phủ: đúng thứ bị xoá, đúng thứ được giữ
