"""Cấu hình đọc từ biến môi trường hoặc file .env. Khoá và token không nằm trong cơ sở dữ liệu."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class CauHinh(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://bantin:bantin@127.0.0.1:54320/bantin"
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
