# Bản tin tự động

Hệ thống cá nhân thu thập tin tức, chọn lọc, tóm tắt sang tiếng Việt và phát thành bản tin định kỳ.
Thuật ngữ ở [CONTEXT.md](CONTEXT.md); spec và ticket ở `.scratch/ban-tin-tu-dong/`.

Hiện có: một lệnh chạy một **Kỳ** cho một **Chuyên mục**, lấy **Bài gốc** từ **Nguồn** RSS, lưu vào
Postgres và gửi một **Bản tin** thô (tiêu đề gốc kèm link) vào **Kênh đăng** Telegram.

## Dựng môi trường

Cần [Docker](https://docs.docker.com/get-docker/) và [uv](https://docs.astral.sh/uv/).

```sh
docker compose up -d --wait    # Postgres ở 127.0.0.1:54320
uv sync
bash scripts/setup-keys.sh     # dẫn từng bước lấy khoá và tài khoản, ghi vào .env
uv run bulletin khoi-tao       # tạo bảng và nạp Chuyên mục công nghệ, một Nguồn RSS, Kênh đăng
```

`scripts/setup-keys.sh` chạy bằng Git Bash trên Windows và chạy lại được: giá trị đã có được giữ khi
nhấn Enter. Muốn điền tay thì sao chép `.env.example` thành `.env`.

## Chạy một Kỳ

```sh
uv run bulletin chay-ky cong-nghe
```

Lệnh in ra kết quả của **Kỳ** (đã phát, không phát hoặc hỏng kèm lí do) và các **Tin** trong
**Bản tin**. Mã thoát khác 0 khi **Kỳ** hỏng.

## Thử endpoint LLM

```sh
uv run bulletin thu-llm                        # mọi model của endpoint, mất chừng mười phút
uv run bulletin thu-llm cx/gpt-5.5 ds/deepseek-chat
```

Lệnh gọi endpoint thật và in một báo cáo markdown: từng model có gọi thường, gọi công cụ, trả kết quả
có cấu trúc và viết tiếng Việt được không. Chạy lại mỗi khi đổi model; kết quả lần gần nhất và model
chọn cho từng vai trò nằm ở [docs/llm-endpoint.md](docs/llm-endpoint.md).

## Test

```sh
docker compose up -d --wait && uv run pytest
```

Test dùng Postgres thật, trong cơ sở dữ liệu riêng `bantin_test` (tự tạo, bị xoá sạch mỗi lần chạy),
và không gọi mạng. Đổi nơi test trỏ tới bằng biến `TEST_DATABASE_URL`.

```sh
uv run mypy          # kiểm tra kiểu
uv run ruff check    # lint
uv run ruff format   # định dạng
```

## Bố cục

- `src/bulletin/chay_ky.py`: lối vào duy nhất "chạy một **Kỳ** cho **Chuyên mục** này tại thời điểm này".
- `src/bulletin/collectors/`: giao diện chung của bộ thu thập và bộ thu thập RSS.
- `src/bulletin/publishers/`: giao diện chung của bộ phát và bộ phát Telegram.
- `src/bulletin/thu_llm.py`: bộ thử endpoint LLM.
- `src/bulletin/mo_hinh.py`, `src/bulletin/migrations/`: các bảng và migration (Alembic).
- `tests/conftest.py`: khuôn test tại điểm "Chạy Kỳ" (**Nguồn** giả, **Kênh đăng** giả, đồng hồ giả).
- `tests/fixtures/`: phản hồi mẫu cho test của từng bộ nối ra bên ngoài.
