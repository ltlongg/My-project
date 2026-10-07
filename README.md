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
cp .env.example .env           # rồi điền TELEGRAM_BOT_TOKEN và TELEGRAM_CHAT_ID
uv run bantin khoi-tao         # tạo bảng và nạp Chuyên mục công nghệ, một Nguồn RSS, Kênh đăng
```

## Chạy một Kỳ

```sh
uv run bantin chay-ky cong-nghe
```

Lệnh in ra kết quả của **Kỳ** (đã phát, không phát hoặc hỏng kèm lí do) và các **Tin** trong
**Bản tin**. Mã thoát khác 0 khi **Kỳ** hỏng.

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

- `src/bantin/chay_ky.py`: lối vào duy nhất "chạy một **Kỳ** cho **Chuyên mục** này tại thời điểm này".
- `src/bantin/thu_thap/`: giao diện chung của bộ thu thập và bộ thu thập RSS.
- `src/bantin/phat_hanh/`: giao diện chung của bộ phát và bộ phát Telegram.
- `src/bantin/mo_hinh.py`, `src/bantin/migrations/`: các bảng và migration (Alembic).
- `tests/conftest.py`: khuôn test tại điểm "Chạy Kỳ" (**Nguồn** giả, **Kênh đăng** giả, đồng hồ giả).
- `tests/du_lieu/`: phản hồi mẫu cho test của từng bộ nối ra bên ngoài.
