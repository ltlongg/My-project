# Bản tin tự động

Hệ thống cá nhân thu thập tin tức, chọn lọc, tóm tắt sang tiếng Việt và phát thành bản tin định kỳ.
Thuật ngữ ở [CONTEXT.md](CONTEXT.md); spec và ticket ở `.scratch/auto-bulletin/`.

Hiện có: một lệnh chạy một **Kỳ** cho một **Chuyên mục**. Nó lấy **Bài gốc** từ **Nguồn** RSS, gom
những **Bài gốc** cùng nói về một sự kiện thành một ứng viên **Tin** và đánh dấu ứng viên trùng với
**Tin** đã phát, để agent **Biên tập** đọc toàn văn, chọn và viết các **Tin** bằng tiếng Việt theo **Hướng dẫn** của
**Chuyên mục**, để agent **Kiểm chứng** đối chiếu từng **Tin** với **Bài gốc** (**Tin** không đạt được
viết lại tối đa hai lần rồi bị bỏ), rồi gửi **Bản tin** vào **Kênh đăng** Telegram. Còn dưới ba
**Tin** qua **Kiểm chứng** thì **Bản tin** không được phát.

## Dựng môi trường

Cần [Docker](https://docs.docker.com/get-docker/) và [uv](https://docs.astral.sh/uv/).

```sh
docker compose up -d --wait    # Postgres ở 127.0.0.1:54320, model nhúng ở 127.0.0.1:54321
uv sync
bash scripts/setup-keys.sh     # dẫn từng bước lấy khoá và tài khoản, ghi vào .env
uv run bulletin init           # tạo bảng, nạp Chuyên mục công nghệ, Nguồn RSS, Hướng dẫn, Kênh đăng
```

Lần đầu, dịch vụ `embeddings` tải khoảng 2,3 GB model `BAAI/bge-m3`; khi chạy nó cần khoảng 3,2 GB RAM
trong Docker (xem [docs/clustering.md](docs/clustering.md)).

`scripts/setup-keys.sh` chạy bằng Git Bash trên Windows và chạy lại được: giá trị đã có được giữ khi
nhấn Enter. Muốn điền tay thì sao chép `.env.example` thành `.env`.

## Chạy một Kỳ

```sh
uv run bulletin run tech
```

Lệnh in ra kết quả của **Kỳ** (đã phát, không phát hoặc hỏng kèm lí do) và các **Tin** trong
**Bản tin**. Mã thoát khác 0 khi **Kỳ** hỏng.

**Biên tập** và **Kiểm chứng** gọi endpoint LLM (`OPENAI_BASE_URL`, `OPENAI_API_KEY`) bằng model ở
`EDITOR_MODEL` và `VERIFIER_MODEL`, để trống thì dùng `MODEL`. Nên đặt hai model của hai nhà
cung cấp khác nhau (xem [docs/llm-endpoint.md](docs/llm-endpoint.md)). Công cụ tìm kiếm web của
**Biên tập** là Tavily; đặt `SEARCH_PROVIDER=brave` để đổi sang Brave. Vector nhúng để gom **Tin**
lấy từ dịch vụ `embeddings` trong `compose.yaml`, vì endpoint LLM không tạo được vector nhúng; đổi bằng
`EMBEDDING_BASE_URL` và `EMBEDDING_MODEL`.

Trạng thái của **Biên tập** và các kết luận của **Kiểm chứng** được lưu sau từng bước. **Kỳ** bị dừng giữa chừng (mất điện, tắt tiến
trình) thì chạy tiếp từ bước đang dở, không đọc lại những **Bài gốc** đã đọc:

```sh
uv run bulletin run tech --resume
```

## Thử endpoint LLM

```sh
uv run bulletin probe-llm                      # mọi model của endpoint, mất chừng mười phút
uv run bulletin probe-llm cx/gpt-5.5 ds/deepseek-chat
```

Lệnh gọi endpoint thật và in một báo cáo markdown: từng model có gọi thường, gọi công cụ, trả kết quả
có cấu trúc và viết tiếng Việt được không. Chạy lại mỗi khi đổi model; kết quả lần gần nhất và model
chọn cho từng vai trò nằm ở [docs/llm-endpoint.md](docs/llm-endpoint.md).

## Test

```sh
docker compose up -d --wait && uv run pytest
```

Test dùng Postgres thật, trong cơ sở dữ liệu riêng `bulletin_test` (tự tạo, bị xoá sạch mỗi lần chạy),
và không gọi mạng. Đổi nơi test trỏ tới bằng biến `TEST_DATABASE_URL`.

```sh
uv run mypy          # kiểm tra kiểu
uv run ruff check    # lint
uv run ruff format   # định dạng
```

## Bố cục

- `src/bulletin/runner.py`: lối vào duy nhất "chạy một **Kỳ** cho **Chuyên mục** này tại thời điểm này".
- `src/bulletin/collectors/`: giao diện chung của bộ thu thập và bộ thu thập RSS.
- `src/bulletin/clustering.py`: gom **Bài gốc** cùng sự kiện thành ứng viên **Tin**, đối chiếu với
  **Tin** đã phát.
- `src/bulletin/embeddings/`: giao diện chung của bộ nhúng và bộ nhúng qua endpoint `/embeddings`.
- `src/bulletin/extractors/`: giao diện chung của bộ lấy nội dung và bộ trích thân bài báo.
- `src/bulletin/agents/`: vòng agent viết bằng LangGraph: **Biên tập**, và **Kiểm chứng** xét
  từng **Tin** nó nộp.
- `src/bulletin/search/`: giao diện chung của bộ tìm kiếm web, với Tavily và Brave.
- `src/bulletin/publishers/`: giao diện chung của bộ phát và bộ phát Telegram.
- `src/bulletin/llm_probe.py`: bộ thử endpoint LLM.
- `src/bulletin/models.py`, `src/bulletin/migrations/`: các bảng và migration (Alembic).
- `tests/conftest.py`: khuôn test tại điểm "Chạy Kỳ" (**Nguồn** giả, **Kênh đăng** giả, LLM trả lời
  theo kịch bản, bộ nhúng giả, đồng hồ giả).
- `tests/fixtures/`: phản hồi mẫu cho test của từng bộ nối ra bên ngoài.
