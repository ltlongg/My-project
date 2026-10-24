# Bản tin tự động

Hệ thống cá nhân thu thập tin tức, chọn lọc, tóm tắt sang tiếng Việt và phát thành bản tin định kỳ.
Thuật ngữ ở [CONTEXT.md](CONTEXT.md); spec và ticket ở `.scratch/auto-bulletin/`.

Hiện có: một lệnh chạy một **Kỳ** cho một **Chuyên mục**, và Lịch chạy các **Kỳ** đó đúng giờ
phát mà không cần ai bấm. Một **Kỳ** lấy **Bài gốc** từ **Nguồn** RSS, gom
những **Bài gốc** cùng nói về một sự kiện thành một ứng viên **Tin** và đánh dấu ứng viên trùng với
**Tin** đã phát, để agent **Biên tập** đọc toàn văn, chọn và viết các **Tin** bằng tiếng Việt theo **Hướng dẫn** của
**Chuyên mục**, để agent **Kiểm chứng** đối chiếu từng **Tin** với **Bài gốc** (**Tin** không đạt được
viết lại tối đa hai lần rồi bị bỏ), chụp ảnh **Bài gốc chính** của từng **Tin**, rồi gửi **Bản tin**
vào **Kênh đăng** Telegram: một tin nhắn mở đầu nêu tên **Chuyên mục** và ngày, rồi mỗi **Tin** một
tin nhắn ảnh. Còn dưới ba **Tin** qua **Kiểm chứng** thì **Bản tin** không được phát.

## Dựng môi trường

Cần [Docker](https://docs.docker.com/get-docker/) và [uv](https://docs.astral.sh/uv/).

```sh
docker compose up -d --wait    # Postgres ở 127.0.0.1:54320, Chromium ở ws://127.0.0.1:3000/
uv sync
bash scripts/setup-keys.sh     # dẫn từng bước lấy khoá và tài khoản, ghi vào .env
uv run siftly init           # tạo bảng, nạp Chuyên mục công nghệ, Nguồn RSS, Hướng dẫn, Kênh đăng
```

`scripts/setup-keys.sh` chạy bằng Git Bash trên Windows và chạy lại được: giá trị đã có được giữ khi
nhấn Enter. Muốn điền tay thì sao chép `.env.example` thành `.env`.

Chromium để chụp ảnh chạy trong dịch vụ `browser` của `compose.yaml` (ảnh Playwright khoảng 3,5 GB),
và ứng dụng kết nối tới nó qua `BROWSER_URL`. Muốn dùng Chromium cài trên máy thì để trống
`BROWSER_URL` và chạy `uv run playwright install --with-deps chromium` (trên Linux cần quyền sudo để
cài thư viện hệ thống).

## Chạy một Kỳ

```sh
uv run siftly run tech
```

Lệnh in ra kết quả của **Kỳ** (đã phát, không phát hoặc hỏng kèm lí do) và các **Tin** trong
**Bản tin**. Mã thoát khác 0 khi **Kỳ** hỏng.

**Biên tập** và **Kiểm chứng** gọi endpoint LLM (`OPENAI_BASE_URL`, `OPENAI_API_KEY`) bằng model ở
`EDITOR_MODEL` và `VERIFIER_MODEL`, để trống thì dùng `MODEL`. Nên đặt hai model của hai nhà
cung cấp khác nhau (xem [docs/llm-endpoint.md](docs/llm-endpoint.md)). Công cụ tìm kiếm web của
**Biên tập** là Tavily; đặt `SEARCH_PROVIDER=brave` để đổi sang Brave. Vector nhúng để gom **Tin**
lấy từ một endpoint `/embeddings` tương thích OpenAI (hiện dùng Jina), vì endpoint LLM không tạo được vector
nhúng; cấu hình bằng `EMBEDDING_BASE_URL`, `EMBEDDING_API_KEY` và `EMBEDDING_MODEL`.

Trước **Biên tập**, bước sơ tuyển chấm điểm mọi ứng viên **Tin** và chỉ chuyển tối đa 30 ứng viên
điểm cao nhất (cột `sections.shortlist_size`). Mức phù hợp với phạm vi **Chuyên mục** do một model
nhỏ chấm, cấu hình bằng `SHORTLIST_MODEL`, để trống thì dùng `MODEL`.

Sau **Kiểm chứng**, mỗi **Tin** sắp phát được chụp ảnh **Bài gốc chính** bằng Chromium, ở khung cỡ
điện thoại, cuộn tới tiêu đề bài, đã gỡ bảng hỏi cookie và ẩn header dính. Trang trả mã lỗi, chặn
trình duyệt tự động, có tường phí hoặc mở quá 20 giây thì dùng ảnh đại diện của bài (`og:image`);
không có cả hai thì **Tin** vẫn được phát, không ảnh. Ảnh đã gửi được lưu theo **Tin** ở bảng
`story_images`, kèm lí do khi phải dùng cách kém hơn.

Trạng thái của **Biên tập** và các kết luận của **Kiểm chứng** được lưu sau từng bước. **Kỳ** bị dừng giữa chừng (mất điện, tắt tiến
trình) thì chạy tiếp từ bước đang dở, không đọc lại những **Bài gốc** đã đọc:

```sh
uv run siftly run tech --resume
```

## Chạy Lịch

```sh
uv run siftly serve
```

Lệnh chạy mãi cho tới khi bị dừng. Mỗi phút nó xét việc đã tới giờ:

- Thu thập **Bài gốc** của mọi **Nguồn** mỗi giờ một lần, để **Bài gốc** đã trôi khỏi RSS feed
  trước giờ phát vẫn vào được **Kỳ**. Lỗi được ghi theo **Nguồn** (cột `sources.last_error`).
- Chạy **Kỳ** của mỗi **Chuyên mục** vào giờ phát theo giờ Việt Nam (cột `sections.publish_time`;
  công nghệ là 8:00). **Chuyên mục** có `sections.is_paused` thì bị bỏ qua hoàn toàn.
- **Kỳ** hỏng được thử lại sau 30 phút, tối đa ba lần, dùng lại những bước đã xong: **Bản tin** đã
  dựng không bị viết lại, và **Kênh đăng** đã nhận tin nhắn nào thì không nhận lại tin nhắn đó.
- **Kỳ** hỏng hẳn hoặc không phát thì bot nhắn riêng cho chủ hệ thống kèm lí do, tới
  `TELEGRAM_OWNER_ID`. Bot chỉ nhắn được cho người đã mở cuộc trò chuyện với nó và bấm Start.

Khởi động lại thì Lịch làm tiếp từ những gì đã lưu: **Kỳ** bị gián đoạn được chạy tiếp, **Kỳ**
lỡ giờ phát được chạy muộn. Quá giờ phát ba tiếng thì thôi: không bắt đầu, không chạy tiếp, không
thử lại, và chỉ **Kỳ** gần nhất của mỗi **Chuyên mục** được xét, nên không chạy bù hàng loạt.
Lệnh `siftly run` và Lịch không cùng chạy một **Chuyên mục** được: bên đến sau bị từ chối.

## Thử endpoint LLM

```sh
uv run siftly probe-llm                      # mọi model của endpoint, mất chừng mười phút
uv run siftly probe-llm cx/gpt-5.5 ds/deepseek-chat
```

Lệnh gọi endpoint thật và in một báo cáo markdown: từng model có gọi thường, gọi công cụ, trả kết quả
có cấu trúc và viết tiếng Việt được không. Chạy lại mỗi khi đổi model; kết quả lần gần nhất và model
chọn cho từng vai trò nằm ở [docs/llm-endpoint.md](docs/llm-endpoint.md).

## Test

```sh
docker compose up -d --wait && uv run pytest
```

Test dùng Postgres thật, trong cơ sở dữ liệu riêng `bulletin_test` (tự tạo, bị xoá sạch mỗi lần chạy),
và không gọi mạng. Đổi nơi test trỏ tới bằng biến `TEST_DATABASE_URL`. Test chụp ảnh dùng Chromium
thật ở `BROWSER_URL` (hoặc Chromium đã cài khi để trống), với các trang mẫu ở
`tests/fixtures/pages/` được trả từ Python.

```sh
uv run mypy          # kiểm tra kiểu
uv run ruff check    # lint
uv run ruff format   # định dạng
```

## Bố cục

- `src/siftly/runner.py`: lối vào duy nhất "chạy một **Kỳ** cho **Chuyên mục** này tại thời điểm này".
- `src/siftly/scheduler.py`: Lịch: thu thập định kỳ, chạy **Kỳ** đúng giờ phát, thử lại và
  nhắn riêng khi hỏng.
- `src/siftly/notifications.py`: thông báo riêng cho chủ hệ thống qua bot Telegram.
- `src/siftly/collectors/`: giao diện chung của bộ thu thập và bộ thu thập RSS.
- `src/siftly/clustering.py`: gom **Bài gốc** cùng sự kiện thành ứng viên **Tin**, đối chiếu với
  **Tin** đã phát.
- `src/siftly/embeddings/`: giao diện chung của bộ nhúng và bộ nhúng qua endpoint `/embeddings`.
- `src/siftly/extractors/`: giao diện chung của bộ lấy nội dung và bộ trích thân bài báo.
- `src/siftly/agents/`: vòng agent viết bằng LangGraph: **Biên tập**, và **Kiểm chứng** xét
  từng **Tin** nó nộp.
- `src/siftly/search/`: giao diện chung của bộ tìm kiếm web, với Tavily và Brave.
- `src/siftly/images/`: chụp ảnh **Bài gốc chính**: ảnh chụp trang bằng Playwright, rồi ảnh đại
  diện, rồi không ảnh.
- `src/siftly/publishers/`: giao diện chung của bộ phát và bộ phát Telegram.
- `src/siftly/llm_probe.py`: bộ thử endpoint LLM.
- `src/siftly/models.py`, `src/siftly/migrations/`: các bảng và migration (Alembic).
- `tests/conftest.py`: khuôn test tại điểm "Chạy Kỳ" (**Nguồn** giả, **Kênh đăng** giả, LLM trả lời
  theo kịch bản, bộ nhúng giả, bộ chụp ảnh giả, thông báo riêng giả, đồng hồ giả).
- `tests/fixtures/`: phản hồi mẫu cho test của từng bộ nối ra bên ngoài.
