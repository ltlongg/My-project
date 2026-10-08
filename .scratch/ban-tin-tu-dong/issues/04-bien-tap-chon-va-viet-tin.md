# 04: Biên tập chọn và viết Tin tiếng Việt

**What to build:** **Bản tin** không còn là danh sách tiêu đề gốc. Agent **Biên tập** đọc các ứng viên của **Kỳ**, chọn 5–7 **Tin** đáng đọc nhất theo **Hướng dẫn** của **Chuyên mục**, và viết cho mỗi **Tin** một tiêu đề và một tóm tắt 4–6 câu bằng tiếng Việt từ toàn văn **Bài gốc**, kèm lí do chọn. Ở ticket này mỗi **Bài gốc** là một ứng viên **Tin**; việc gom và sơ tuyển đến sau.

Vòng agent viết bằng LangGraph theo ADR 0001; model theo kết quả ticket 02.

**Blocked by:** 02, 03

**Status:** ready-for-agent

- [ ] Toàn văn của một **Bài gốc** loại bài báo được trích ra và lưu lại
- [ ] **Biên tập** có công cụ đọc toàn văn một **Bài gốc** và công cụ tìm kiếm web; công cụ tìm kiếm thay được giữa Tavily và Brave
- [ ] Mỗi **Tin** được chọn có tiêu đề, tóm tắt tiếng Việt, **Bài gốc chính** và lí do chọn, tất cả được lưu
- [ ] Tên riêng và thuật ngữ chuyên ngành quen dùng được giữ nguyên tiếng Anh
- [ ] Tiêu đề, tóm tắt và link của một **Tin** vừa trong 1.024 ký tự
- [ ] **Tin** chỉ dẫn tới **Bài gốc** từ **Nguồn** đã khai; kết quả tìm kiếm web không trở thành **Tin**
- [ ] **Hướng dẫn** của **Biên tập** được đọc từ dữ liệu theo **Chuyên mục**, không viết cứng trong code; **Kỳ** ghi lại phiên bản đã dùng
- [ ] Kết quả có cấu trúc từ LLM được kiểm tra bằng code; kết quả hỏng được xử lí như một lỗi của **Kỳ**, không phát ra ngoài
- [ ] Trạng thái của vòng agent được lưu để một **Kỳ** bị gián đoạn chạy tiếp được
- [ ] Test tại điểm "Chạy Kỳ" với LLM trả lời theo kịch bản phủ các hành vi trên
