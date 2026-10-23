# 02: Thử endpoint LLM

**What to build:** Biết chắc endpoint LLM của chủ hệ thống làm được gì trước khi vòng agent dựa vào nó. Chạy một bộ thử nhỏ với từng model định dùng và ghi kết quả lại, kèm lựa chọn model cho từng vai trò (sơ tuyển, **Biên tập**, **Kiểm chứng**, cải tiến). Nếu tool calling không chạy qua endpoint, quyết định gọi thẳng Gemini hoặc Anthropic cho vòng agent.

**Blocked by:** 01

**Status:** done

- [x] Với mỗi model ứng viên, có kết quả đạt hoặc không đạt cho: gọi thường, tool calling một lượt, tool calling nhiều lượt liên tiếp, kết quả có cấu trúc, và viết tiếng Việt từ văn bản tiếng Anh
- [x] Biết endpoint có tạo được vector nhúng không; nếu không, đã chọn một model nhúng tự chạy
- [x] Biết endpoint trả gì khi bị giới hạn tốc độ hoặc hết hạn mức
- [x] Kết quả và lựa chọn model cho từng vai trò được ghi thành một ghi chú ngắn trong repo
- [x] Nếu kết quả buộc phải đổi một quyết định trong spec, phần "Cần thử trước khi dựa vào" của spec được cập nhật
- [x] Bộ thử chạy lại được bằng một lệnh, để dùng khi đổi model

## Comments

**2026-10-08, agent.** Bộ thử là `uv run bulletin probe-llm` (`src/bulletin/llm_probe.py`, test ở `tests/test_llm_probe.py` bằng một endpoint giả). Đã chạy trên cả 20 model; kết quả, model cho từng vai trò và những điều code phải tính tới nằm ở `docs/llm-endpoint.md`.

Tóm tắt: 14 model sống, cả 14 đều tool calling được một lượt và nhiều lượt, nên vòng agent đi qua endpoint. Sáu model `cx/` đời cũ không dùng được với tài khoản này. Nhóm `ds/` từ chối `response_format` kiểu `json_schema`. Endpoint không tạo được vector nhúng; chọn `BAAI/bge-m3` tự chạy. Spec đã cập nhật hai mục tương ứng.

Chuyển sang `ready-for-human` vì hai việc cần chủ hệ thống:

- Tiêu chí về giới hạn tốc độ chưa đạt. 10 và 12 lời gọi cùng lúc không làm endpoint từ chối, và agent không cố vắt cạn hạn mức của một gói thuê bao. Mới biết hình dạng lỗi chung của proxy (mã của nhà cung cấp, thông điệp bọc lại, đầu `retry-after`) và việc nó khoá cả model khoảng 30 giây sau mỗi lần từ chối. Chủ hệ thống quyết định: chấp nhận mức hiểu biết này, hoặc cho biết trang quản lí của proxy báo gì khi hết hạn mức.
- Lựa chọn model cho từng vai trò dựa trên khả năng và tốc độ, không phải chất lượng. Cần chủ hệ thống xem qua, nhất là việc dùng `ds/deepseek-v4-pro` cho **Kiểm chứng**.

Chưa thử `BRAVE_API_KEY`, và chưa chạy thử model nhúng nào.

**2026-10-08, chủ hệ thống.** Đồng ý với bảng model cho từng vai trò, và chấp nhận mức hiểu biết hiện có về giới hạn tốc độ (hình dạng lỗi của proxy và việc khoá model theo `retry-after`) dù chưa thấy lỗi hết hạn mức thật. Đóng ticket.
