# 06: Gom Tin và không phát lại

**What to build:** Người đọc không thấy một chuyện hai lần. Các **Bài gốc** cùng nói về một sự kiện được gom thành một ứng viên **Tin** trước khi tới **Biên tập**, và **Biên tập** chọn một **Bài gốc chính** trong số đó, ưu tiên nơi đưa tin đầu tiên hoặc nguồn gốc nhất. Ứng viên trùng với một **Tin** đã phát của cùng **Chuyên mục** bị loại, trừ khi có diễn biến mới đáng kể; khi đó nó được phát với nhãn "Cập nhật".

**Blocked by:** 04

**Status:** ready-for-agent

- [ ] Nhiều **Bài gốc** về cùng một sự kiện, kể cả khác ngôn ngữ, thành một ứng viên **Tin**
- [ ] Một **Tin** có nhiều **Bài gốc** và đúng một **Bài gốc chính**
- [ ] Ứng viên trùng với **Tin** đã phát của cùng **Chuyên mục** không xuất hiện lại
- [ ] Ứng viên có diễn biến mới so với **Tin** đã phát được phát với nhãn "Cập nhật" và liên kết với **Tin** trước
- [ ] **Tin** của **Kỳ** xem trước hoặc **Kỳ** không phát không được tính là đã phát
- [ ] Việc so độ giống nghĩa dùng vector nhúng theo lựa chọn ở ticket 02, lưu trong Postgres
- [ ] Test tại điểm "Chạy Kỳ" phủ: gom, không gom nhầm hai sự kiện khác nhau cùng chủ đề, không phát lại, và "Cập nhật"
