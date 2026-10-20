"""Cấu hình đọc từ biến môi trường hoặc file .env. Khoá và token không nằm trong cơ sở dữ liệu."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class CauHinh(BaseSettings):
    # Biến để trống, như trong .env.example, thì coi như chưa đặt và dùng giá trị mặc định.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    database_url: str = "postgresql+psycopg://bantin:bantin@127.0.0.1:54320/bantin"
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    # Endpoint LLM tương thích OpenAI.
    openai_base_url: str | None = None
    openai_api_key: str | None = None
    # Model mặc định, và model riêng của từng vai trò; để trống thì dùng model mặc định.
    model: str | None = None
    model_bien_tap: str | None = None
    model_kiem_chung: str | None = None
    # Dịch vụ tạo vector nhúng để gom Tin: một endpoint tương thích OpenAI, mặc định là Text
    # Embeddings Inference trong compose.yaml. Endpoint LLM ở trên không tạo được vector nhúng.
    nhung_base_url: str = "http://127.0.0.1:54321/v1"
    nhung_api_key: str | None = None
    model_nhung: str = "BAAI/bge-m3"
    # Công cụ tìm kiếm web của Biên tập.
    cong_cu_tim_kiem: Literal["tavily", "brave"] = "tavily"
    tavily_api_key: str | None = None
    brave_api_key: str | None = None
