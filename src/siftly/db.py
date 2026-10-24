"""Kết nối Postgres và nâng cấp lược đồ."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from langgraph.checkpoint.postgres import PostgresSaver
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
# Các bảng LangGraph tự tạo để lưu trạng thái của vòng agent; chúng nằm ngoài Alembic.
CHECKPOINT_TABLES = ("checkpoints", "checkpoint_blobs", "checkpoint_writes")


def make_engine(database_url: str) -> Engine:
    return create_engine(database_url)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Trả về hàm mở phiên làm việc với cơ sở dữ liệu."""
    return sessionmaker(engine, expire_on_commit=False)


@contextmanager
def open_checkpointer(engine: Engine) -> Iterator[PostgresSaver]:
    """Mở nơi lưu trạng thái của vòng agent, trong cùng cơ sở dữ liệu với phần còn lại."""
    url = engine.url.set(drivername="postgresql").render_as_string(hide_password=False)
    with PostgresSaver.from_conn_string(url) as checkpointer:
        yield checkpointer


def _config() -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    return config


def is_up_to_date(engine: Engine) -> bool:
    """Lược đồ đã ở phiên bản mới nhất chưa."""
    with engine.connect() as connection:
        current = MigrationContext.configure(connection).get_current_heads()
    return set(current) == set(ScriptDirectory.from_config(_config()).get_heads())


def upgrade(engine: Engine) -> None:
    """Đưa lược đồ lên phiên bản mới nhất."""
    config = _config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    with open_checkpointer(engine) as checkpointer:
        checkpointer.setup()
