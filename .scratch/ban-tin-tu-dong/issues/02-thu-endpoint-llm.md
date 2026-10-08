# 02: Thử endpoint LLM

**What to build:** Biết chắc endpoint LLM của chủ hệ thống làm được gì trước khi vòng agent dựa vào nó. Chạy một bộ thử nhỏ với từng model định dùng và ghi kết quả lại, kèm lựa chọn model cho từng vai trò (sơ tuyển, **Biên tập**, **Kiểm chứng**, cải tiến). Nếu tool calling không chạy qua endpoint, quyết định gọi thẳng Gemini hoặc Anthropic cho vòng agent.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Với mỗi model ứng viên, có kết quả đạt hoặc không đạt cho: gọi thường, tool calling một lượt, tool calling nhiều lượt liên tiếp, kết quả có cấu trúc, và viết tiếng Việt từ văn bản tiếng Anh
- [ ] Biết endpoint có tạo được vector nhúng không; nếu không, đã chọn một model nhúng tự chạy
- [ ] Biết endpoint trả gì khi bị giới hạn tốc độ hoặc hết hạn mức
- [ ] Kết quả và lựa chọn model cho từng vai trò được ghi thành một ghi chú ngắn trong repo
- [ ] Nếu kết quả buộc phải đổi một quyết định trong spec, phần "Cần thử trước khi dựa vào" của spec được cập nhật
- [ ] Bộ thử chạy lại được bằng một lệnh, để dùng khi đổi model
