"""Cấu hình đọc từ biến môi trường hoặc file .env. Khoá và token không nằm trong cơ sở dữ liệu."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class CauHinh(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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
    # Công cụ tìm kiếm web của Biên tập.
    cong_cu_tim_kiem: Literal["tavily", "brave"] = "tavily"
    tavily_api_key: str | None = None
    brave_api_key: str | None = None
