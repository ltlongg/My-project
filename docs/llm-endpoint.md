# Endpoint LLM: làm được gì và dùng model nào

Kết quả của `uv run bulletin probe-llm` ngày 2026-10-08 (ticket 02). Chạy lại lệnh mỗi khi đổi model hoặc đổi endpoint, rồi cập nhật ghi chú này.

Endpoint là một proxy chạy trên máy phát triển (`http://localhost:20128/v1`), đứng trước hai nhà cung cấp: `cx/` là Codex qua một tài khoản ChatGPT, `ds/` là DeepSeek.

## Kết luận

- **Tool calling chạy được qua endpoint**, cả một lượt lẫn nhiều lượt liên tiếp, trên mọi model còn sống. Vòng agent không cần gọi thẳng Gemini hay Anthropic.
- **Endpoint không tạo được vector nhúng.** Gom **Tin** phải dùng một model nhúng tự chạy (xem cuối ghi chú).
- **Kết quả có cấu trúc**: đừng dùng `response_format` kiểu `json_schema`, vì nhóm `ds/` từ chối. Hai cách chạy được trên mọi model: yêu cầu JSON trong prompt rồi kiểm tra bằng code, hoặc ép qua tool calling.

## Từng nhóm model

| Model | Gọi thường | Công cụ một lượt | Công cụ nhiều lượt | JSON theo schema | JSON theo prompt | Viết tiếng Việt |
| --- | --- | --- | --- | --- | --- | --- |
| `cx/gpt-5.5`, `cx/gpt-5.6-luna`, `cx/gpt-5.6-sol`, `cx/gpt-5.6-terra` | đạt | đạt | đạt | đạt | đạt | đạt |
| `ds/deepseek-chat`, `ds/deepseek-reasoner`, `ds/deepseek-v4-flash`, `ds/deepseek-v4-pro`, `ds/deepseek-v4-pro-max`, `ds/deepseek-v4-pro-none` | đạt | đạt | đạt | KHÔNG | đạt | đạt |
| `cx/gpt-5.3-codex-spark`, `cx/gpt-5.4`, `cx/gpt-5.4-mini` | KHÔNG | – | – | – | – | – |

- Mỗi model `cx/` có thêm một bản `-review`; kết quả giống hệt bản thường.
- Ba model `cx/` ở dòng cuối bị từ chối: "not supported when using Codex with a ChatGPT account".
- "Công cụ nhiều lượt" đòi model tìm, đọc đúng **Bài gốc**, rồi trả lời bằng một con số chỉ có trong toàn văn.
- "Viết tiếng Việt" chỉ được máy soát phần soát được: có phải tiếng Việt, có giữ tên riêng và con số. Câu chữ thì đọc bản tóm tắt mà lệnh in ra. Trong các lần chạy, `ds/deepseek-reasoner` để nguyên cả cụm tiếng Anh thường dùng ("volume shipments", "2-nanometer process").
- Thời gian cho cả bảy phép thử: nhóm `cx/` 19–32 giây; `ds/deepseek-chat` khoảng 9 giây, `ds/deepseek-v4-pro` khoảng 50 giây.

## Model cho từng vai trò

Bộ thử chỉ cho biết model **làm được gì**, không so được model nào viết hay hơn. Lựa chọn dưới đây dựa trên khả năng và tốc độ; chất lượng để bộ đánh giá agent (ticket 15) xét lại.

| Vai trò | Model | Vì sao |
| --- | --- | --- |
| Sơ tuyển | `ds/deepseek-chat` | Nhanh nhất, và việc chấm điểm phải gọi nhiều lần |
| **Biên tập** | `cx/gpt-5.6-luna` | Model mặc định chủ hệ thống đã chọn (`MODEL`); đạt mọi phép thử, bản tóm tắt tiếng Việt sạch |
| **Kiểm chứng** | `ds/deepseek-v4-pro` | Khác nhà cung cấp với **Biên tập**, để người soát không mắc cùng lỗi với người viết |
| Cải tiến | `cx/gpt-5.6-luna` | Chưa có căn cứ để chọn khác **Biên tập** |

Mỗi vai trò có một biến riêng, trống thì dùng `MODEL`. Ticket 04 đã thêm `EDITOR_MODEL`, ticket 05 thêm `VERIFIER_MODEL`; `SHORTLIST_MODEL` và `IMPROVER_MODEL` được thêm khi vai trò đó có code.

## Điều code phải tính tới

- **Một lời gọi bị từ chối khoá cả model khoảng 30 giây.** Sau khi nhà cung cấp trả lỗi, proxy trả lại đúng lỗi đó cho mọi lời gọi tới cùng model gốc, kèm đầu `retry-after`. Nhiều tên dùng chung một model gốc (`ds/deepseek-chat`, `-reasoner` và `-v4-flash`; ba bản `ds/deepseek-v4-pro*`), nên chúng bị khoá cùng nhau. Vì vậy: gặp `retry-after` thì chờ rồi gọi lại, và đừng gửi thứ model không nhận.
- **Gọi không stream tới nhóm `ds/` trả thân sai chuẩn**: JSON nối thêm `data: [DONE]`, kiểu `text/event-stream`. `ChatOpenAI` của `langchain-openai` đọc được cả hai chế độ (đã thử gọi thường, tool calling và `with_structured_output(method="function_calling")` trên `cx/gpt-5.6-luna` và `ds/deepseek-chat`), nhưng một client HTTP tự viết phải dùng stream.
- **Nhóm `cx/` tự chèn khoảng 2.500 token vào mỗi lời gọi**: một câu hỏi mười token được tính 2.502 token. Nhiều khả năng đó là hướng dẫn hệ thống của Codex; chưa tìm được cách xem hay tắt nó.
- **Giới hạn tốc độ và hết hạn mức chưa tái hiện được**: 10 lời gọi cùng lúc tới `cx/gpt-5.5` và 12 tới `ds/deepseek-chat` đều thành công. Điều đã biết là hình dạng lỗi của proxy: mã HTTP của nhà cung cấp, thân `{"error": {"message": "[nhà cung cấp/model] [mã]: <lỗi gốc> (reset after Ns)"}}` và đầu `retry-after`. Suy đoán, chưa kiểm chứng: lỗi 429 cũng mang hình dạng này.
- Khoá sai trả `401 Invalid API key`; model không tồn tại trả `404 No active credentials for provider`.
- Endpoint ở `localhost` chỉ dùng được trên máy này; ticket 16 cần một địa chỉ mà server tới được.
- Rủi ro đã ghi trong spec nay là thật: nhóm `cx/` chạy trên một gói thuê bao ChatGPT, không phải khoá API trả theo lượng dùng.

## Model nhúng tự chạy

Chọn `BAAI/bge-m3`: đa ngôn ngữ (có tiếng Việt), vector 1.024 chiều, giấy phép MIT, chạy được trên CPU với vài trăm **Bài gốc** mỗi ngày. Nếu server thiếu RAM thì lùi về `intfloat/multilingual-e5-small` (384 chiều). Lựa chọn dựa trên đặc tính đã công bố của hai model. Ticket 06 đã chạy thử `bge-m3` trên RSS thật và giữ lựa chọn này; số đo, ngưỡng gom và tài nguyên cần có ở `docs/clustering.md`.
