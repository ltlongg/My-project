# 19: Chuyển audio thành chữ

**What to build:** Hệ thống biến một file audio thành văn bản bằng model tự chạy trên server, không gọi dịch vụ ngoài. Một giao diện duy nhất "đưa audio và ngôn ngữ, nhận văn bản", phía sau là hai model: Zipformer của hynt cho tiếng Việt và Phonon-2 của FermionResearch cho tiếng Anh. Ticket này đứng riêng được: xong là thử được bằng một file audio bất kì, chưa cần YouTube.

Zipformer có ba biến thể (30M, 30M streaming, 150M); chọn một sau khi đo trên vài mẫu tiếng Việt thật và ghi lại lí do. Giấy phép của Zipformer là CC BY-NC-ND 4.0, chỉ dùng phi thương mại.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Một lệnh nhận file audio và ngôn ngữ, in ra văn bản
- [ ] Audio tiếng Việt đi qua Zipformer, tiếng Anh đi qua Phonon-2; ngôn ngữ khác trả về lỗi rõ ràng
- [ ] Cả hai model chạy bằng CPU trong Docker trên Linux, không cần GPU
- [ ] Audio dài 90 phút được xử lí xong mà không hết bộ nhớ; thời gian xử lí trên máy thử được ghi lại
- [ ] Biến thể Zipformer được chọn, kèm số đo và lí do, ghi thành ghi chú ngắn trong repo
- [ ] File hỏng hoặc không có tiếng nói trả về lỗi rõ ràng, không treo
- [ ] Model được tải một lần và giữ lại giữa các lần dựng
- [ ] Có test với hai đoạn audio ngắn mẫu, một tiếng Việt và một tiếng Anh, khẳng định văn bản trả về chứa các từ khoá mong đợi
