# 05: Kiểm chứng và vòng viết lại

**What to build:** Không **Tin** nào được phát khi chưa qua agent **Kiểm chứng**. **Kiểm chứng** đối chiếu tiêu đề và tóm tắt của từng **Tin** với toàn văn **Bài gốc** của nó, và trả về đạt hoặc không đạt kèm lí do cụ thể. **Tin** không đạt quay lại **Biên tập** để viết lại, tối đa hai lần, rồi bị bỏ khỏi **Bản tin**. Vì không có người duyệt, đây là chốt chặn duy nhất (ADR 0001).

**Blocked by:** 04

**Status:** ready-for-agent

- [ ] **Kiểm chứng** bắt các sai lệch về số liệu, tên, ngày tháng, và tiêu đề nói quá so với **Bài gốc**
- [ ] **Tin** không đạt được viết lại với lí do của **Kiểm chứng** làm đầu vào; sau hai lần viết lại vẫn không đạt thì bị bỏ
- [ ] Mỗi lượt **Kiểm chứng**, lí do, và bản viết lại tương ứng được lưu theo **Tin**
- [ ] **Tin** bị bỏ được lưu kèm lí do, không biến mất
- [ ] Sau **Kiểm chứng** còn dưới ba **Tin** thì **Bản tin** không được phát và **Kỳ** được ghi là hỏng
- [ ] **Hướng dẫn** của **Kiểm chứng** là một bản chung cho mọi **Chuyên mục**, đọc từ dữ liệu; **Kỳ** ghi lại phiên bản đã dùng
- [ ] **Kiểm chứng** dùng cấu hình model riêng, độc lập với **Biên tập**
- [ ] Test tại điểm "Chạy Kỳ" phủ: đạt ngay, đạt sau khi viết lại, bị bỏ sau hai lần, và không phát vì dưới ba **Tin**
