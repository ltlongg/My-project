# 21: Chuyên mục tài chính và thời sự

**What to build:** Chủ hệ thống nhận đủ ba **Bản tin** mỗi ngày. Thêm hai **Chuyên mục** có sẵn **Hướng dẫn** và **Nguồn** RSS khởi đầu riêng: tài chính phát lúc 12:00, thời sự phát lúc 20:00. Ba **Chuyên mục** chạy độc lập: **Kỳ** của cái này không ảnh hưởng cái kia, **Tin** đã phát ở **Chuyên mục** này không chặn **Chuyên mục** khác, và một **Nguồn** dùng chung chỉ được thu thập một lần.

Phạm vi tài chính: kinh tế vĩ mô Việt Nam và thế giới, tin về doanh nghiệp lớn (kết quả kinh doanh, sáp nhập, biến động lớn); không crypto, không bảng giá, không khuyến nghị mua bán. Phạm vi thời sự: trong nước và thế giới.

**Blocked by:** 11, 14

**Status:** ready-for-agent

- [ ] Dữ liệu khởi tạo tạo ra **Chuyên mục** tài chính (12:00) và thời sự (20:00), mỗi cái 5–7 **Tin**
- [ ] Mỗi **Chuyên mục** có **Hướng dẫn** riêng cho **Biên tập** nêu đúng phạm vi ở trên
- [ ] Mỗi **Chuyên mục** có khoảng 8–12 **Nguồn** RSS, cả tiếng Việt và tiếng Anh, từng địa chỉ đã được gọi thử
- [ ] Một **Nguồn** gắn vào cả tài chính lẫn thời sự chỉ được thu thập một lần và góp ứng viên cho cả hai
- [ ] Một sự kiện được phát ở tài chính vẫn có thể được phát ở thời sự; quy tắc không phát lại chỉ áp dụng trong một **Chuyên mục**
- [ ] Một **Kỳ** hỏng ở một **Chuyên mục** không làm trễ hay hỏng **Kỳ** của **Chuyên mục** khác
- [ ] Tin crypto, bảng giá và khuyến nghị mua bán không xuất hiện trong **Bản tin** tài chính
- [ ] Một **Kỳ** xem trước với LLM thật cho mỗi **Chuyên mục** mới ra **Bản tin** đúng phạm vi; kết quả được đính kèm khi đóng ticket
