# 24: Đề xuất cải tiến hằng tuần

**What to build:** Hệ thống tự tốt lên mà chủ hệ thống vẫn nắm quyền quyết định. Mỗi tuần một agent đọc **Phản hồi** và các **Bản tin** của tuần rồi soạn một **Đề xuất cải tiến**: sửa gì trong **Hướng dẫn** của **Chuyên mục** nào, thêm hoặc bỏ **Nguồn** nào, dựa trên **Phản hồi** nào. Bot báo cho chủ hệ thống khi có đề xuất. Trên trang quản lí họ xem đề xuất dạng so sánh trước và sau rồi bấm đồng ý hoặc từ chối. Agent không bao giờ tự sửa **Hướng dẫn** (ADR 0001).

**Blocked by:** 22, 23

**Status:** ready-for-agent

- [ ] Mỗi tuần mỗi **Chuyên mục** có nhiều nhất một **Đề xuất cải tiến**; tuần không đủ **Phản hồi** thì không có đề xuất
- [ ] Đề xuất nêu thay đổi cụ thể và dẫn tới những **Phản hồi** làm căn cứ
- [ ] Chỉ **Phản hồi** của chủ hệ thống làm căn cứ sửa **Hướng dẫn**; **Phản hồi** của thành viên chỉ được nêu để tham khảo
- [ ] Lời nhắn chữ của chủ hệ thống được ưu tiên hơn 👍/👎
- [ ] Đề xuất về **Hướng dẫn** hiện dạng so sánh trước và sau
- [ ] Đề xuất có thể gồm thêm **Nguồn** mà **Biên tập** gặp khi tìm kiếm, hoặc tắt **Nguồn** hay bị 👎
- [ ] Đồng ý tạo một phiên bản **Hướng dẫn** mới có hiệu lực, ghi nguồn gốc là đề xuất này; thay đổi **Nguồn** được áp dụng
- [ ] Từ chối không đổi gì, và lí do từ chối (nếu có) được dùng cho đề xuất tuần sau
- [ ] Không có đường nào để một **Hướng dẫn** đổi mà không qua sửa tay, quay lui, hoặc đồng ý một đề xuất
- [ ] Bot nhắn riêng cho chủ hệ thống khi có đề xuất mới, kèm link tới trang quản lí
- [ ] Test tại API phủ đồng ý và từ chối; việc soạn đề xuất có test với LLM trả lời theo kịch bản
