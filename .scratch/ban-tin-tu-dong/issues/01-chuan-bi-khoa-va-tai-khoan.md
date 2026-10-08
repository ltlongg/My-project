# 01: Chuẩn bị khoá và tài khoản

**What to build:** Chủ hệ thống có sẵn mọi khoá và tài khoản mà lát cắt đầu cần, đặt trong một file cấu hình môi trường không được đưa vào git, để các ticket sau chạy được với dịch vụ thật. Đây là các bước chỉ con người làm được; dùng `/wizard` để dựng một kịch bản dẫn từng bước.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] Có một bot Telegram và token của nó
- [x] Có một nhóm Telegram thử, bot đã được thêm vào và có quyền gửi tin; biết mã của nhóm
- [x] Biết mã người dùng Telegram của chủ hệ thống, để bot nhắn riêng và nhận diện **Phản hồi** của chủ
- [x] Có địa chỉ và khoá của endpoint LLM tương thích OpenAI, và danh sách model dùng được
- [x] Có khoá Tavily (hoặc Brave)
- [x] Có khoá Langfuse bản cloud
- [x] Tất cả nằm trong file cấu hình môi trường; file này bị git bỏ qua, và có một file mẫu liệt kê tên các biến mà không có giá trị

## Comments

**2026-10-08, agent.** Đã dựng kịch bản `scripts/setup-keys.sh` (chạy bằng Git Bash: `bash scripts/setup-keys.sh`) dẫn sáu bước: token bot, nhóm thử, mã người dùng của chủ, endpoint LLM, Tavily, Langfuse. Nó tự tìm mã nhóm và mã người dùng qua `getUpdates`, kiểm tra từng giá trị với dịch vụ thật và ghi vào `.env`. `.env.example` giờ liệt kê đủ tên biến; `.env` đã bị git bỏ qua.

Đã kiểm tra `.env` hiện có bằng các lời gọi chỉ đọc:

- `TELEGRAM_BOT_TOKEN`: đúng, Telegram nhận.
- `TELEGRAM_CHAT_ID`: sai. Giá trị đang điền là mã của chính con bot (phần số đứng trước dấu hai chấm trong token), không phải mã nhóm. Bot chưa thấy nhóm nào: `getUpdates` trả về rỗng.
- `OPENAI_BASE_URL` và `OPENAI_API_KEY`: đúng, `GET /models` trả về 20 model (nhóm `cx/gpt-5.*` và `ds/deepseek-*`). Địa chỉ là `localhost`, nên chỉ dùng được trên máy phát triển; ticket 16 cần một địa chỉ mà server tới được.
- `TELEGRAM_OWNER_ID`, `TAVILY_API_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL`: chưa có.

Tên biến: giữ `OPENAI_BASE_URL` và `OPENAI_API_KEY` như chủ hệ thống đã đặt. `.env` còn có `GUARDRAILS_MODEL`, không ứng với vai trò nào trong spec; tên biến model cho từng vai trò để ticket 02 quyết định.

Còn lại cho chủ hệ thống: chạy kịch bản, nhấn Enter ở bước 1 và 4 để giữ giá trị đã có, làm các bước 2, 3, 5, 6.

**2026-10-08, agent (lần hai).** Chủ hệ thống đã điền đủ. Kiểm tra lại bằng lời gọi chỉ đọc, tất cả đạt:

- Bot: Telegram nhận token.
- Nhóm thử: là một nhóm thường (`group`), bot là thành viên, quyền mặc định của thành viên cho phép gửi tin. Chủ hệ thống là người tạo nhóm.
- `TELEGRAM_OWNER_ID`: một tài khoản cá nhân đã từng nhắn bot, nên bot nhắn riêng được.
- Endpoint LLM: `GET /models` trả về 20 model.
- Tavily: `GET /usage` trả về 200. Có thêm `BRAVE_API_KEY` để thay thế, chưa kiểm tra.
- Langfuse: vùng Nhật (`https://jp.cloud.langfuse.com`), cặp khoá được nhận.

Chưa gửi tin nhắn thật nào vào nhóm; đó là tiêu chí còn lại của ticket 03. `.env` còn có `MODEL` (hiện là `cx/gpt-5.6-luna`), coi như model mặc định; model cho từng vai trò do ticket 02 chọn.
