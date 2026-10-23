# 15: Bộ đánh giá agent

**What to build:** Biết được hai agent làm việc tốt đến đâu bằng con số, thay vì đọc **Bản tin** rồi cảm nhận. Một lệnh chạy **Biên tập** và **Kiểm chứng** với LLM thật trên một tập **Bài gốc** mẫu cố định và in ra báo cáo. Bộ này không chặn build; chạy lại mỗi khi đổi model hoặc **Hướng dẫn** mặc định.

**Blocked by:** 05

**Status:** ready-for-agent

- [ ] Có một tập **Bài gốc** mẫu cố định, gồm bài tiếng Anh và tiếng Việt, trong và ngoài phạm vi **Chuyên mục**
- [ ] Có một tập **Tin** viết sẵn, một phần cố ý sai (số liệu sai, tên sai, tiêu đề nói quá, chi tiết không có trong **Bài gốc**), để đo **Kiểm chứng** bắt được bao nhiêu và bắt nhầm bao nhiêu
- [ ] Báo cáo cho biết **Biên tập** có chọn **Tin** ngoài phạm vi không, và tóm tắt có giữ đúng nghĩa bản gốc không
- [ ] Báo cáo ghi model, phiên bản **Hướng dẫn** và ngày chạy, để so giữa các lần
- [ ] Chạy bằng một lệnh, tách khỏi bộ test thường; bộ test thường không gọi LLM thật
- [ ] Kết quả lần chạy đầu được lưu lại làm mốc so sánh
