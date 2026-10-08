# 12: Theo dõi Kỳ và Tin

**What to build:** Khi một **Tin** sai hoặc một **Bản tin** không ra, chủ hệ thống tự tìm được nguyên nhân trên trang quản lí. Họ xem danh sách **Kỳ** và kết quả từng cái; mở một **Bản tin** và thấy đúng những gì đã gửi; với từng **Tin** thấy các **Bài gốc**, **Bài gốc chính**, điểm, lí do **Biên tập** chọn, từng lượt **Kiểm chứng**; thấy cả những **Tin** không được chọn hoặc bị loại kèm lí do; và mở được vết chi tiết các lần gọi LLM trên Langfuse.

**Blocked by:** 05, 10

**Status:** ready-for-agent

- [ ] Danh sách **Kỳ** lọc được theo **Chuyên mục** và kết quả (đã phát, không phát, hỏng), có lí do khi hỏng
- [ ] Trang một **Bản tin** hiện từng **Tin** đúng như đã gửi, gồm ảnh
- [ ] Trang một **Tin** hiện mọi **Bài gốc** của nó, **Bài gốc chính**, điểm và lí do chọn
- [ ] Trang một **Tin** hiện từng lượt **Kiểm chứng**: kết luận, lí do, và bản viết lại sau đó
- [ ] Trang một **Kỳ** hiện các ứng viên không được chọn và các **Tin** bị **Kiểm chứng** bỏ, kèm lí do
- [ ] Mọi lần gọi LLM và công cụ của agent được ghi vết lên Langfuse; từ một **Tin** mở được đúng vết của nó
- [ ] Trang quản lí vẫn hiện đủ các mục trên khi Langfuse không truy cập được
- [ ] Chi phí và số lần gọi LLM hiện theo **Kỳ** và theo ngày
- [ ] Tìm được **Tin** đã phát theo từ khoá
- [ ] Test gọi API thật phủ danh sách, chi tiết, lọc và tìm kiếm
