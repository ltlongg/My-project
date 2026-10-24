"""Cấu hình đọc từ biến môi trường hoặc file .env. Khoá và token không nằm trong cơ sở dữ liệu."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Biến để trống, như trong .env.example, thì coi như chưa đặt và dùng giá trị mặc định.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    database_url: str = "postgresql+psycopg://bulletin:bulletin@127.0.0.1:54320/bulletin"
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    # Mã người dùng Telegram của chủ hệ thống: bot nhắn riêng tới đây.
    telegram_owner_id: str | None = None
    # Endpoint LLM tương thích OpenAI.
    openai_base_url: str | None = None
    openai_api_key: str | None = None
    # Model mặc định, và model riêng của từng vai trò; để trống thì dùng model mặc định.
    model: str | None = None
    shortlist_model: str | None = None
    editor_model: str | None = None
    verifier_model: str | None = None
    # Dịch vụ tạo vector nhúng để gom Tin: một endpoint tương thích OpenAI, mặc định là Jina.
    # Endpoint LLM ở trên không tạo được vector nhúng.
    embedding_base_url: str = "https://api.jina.ai/v1"
    embedding_api_key: str | None = None
    embedding_model: str = "jina-embeddings-v5-text-small"
    # Công cụ tìm kiếm web của Biên tập.
    search_provider: Literal["tavily", "brave"] = "tavily"
    tavily_api_key: str | None = None
    brave_api_key: str | None = None
    # Chromium để chụp ảnh Bài gốc: địa chỉ WebSocket của một Playwright server, như dịch vụ
    # browser trong compose.yaml. Để trống thì tự mở Chromium cài bằng `playwright install`.
    browser_url: str | None = None
