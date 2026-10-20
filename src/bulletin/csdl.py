"""Kết nối Postgres và nâng cấp lược đồ."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from langgraph.checkpoint.postgres import PostgresSaver
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

THU_MUC_MIGRATION = Path(__file__).parent / "migrations"
# Các bảng LangGraph tự tạo để lưu trạng thái của vòng agent; chúng nằm ngoài Alembic.
BANG_TRANG_THAI = ("checkpoints", "checkpoint_blobs", "checkpoint_writes")


def tao_engine(database_url: str) -> Engine:
    return create_engine(database_url)


def tao_mo_phien(engine: Engine) -> sessionmaker[Session]:
    """Trả về hàm mở phiên làm việc với cơ sở dữ liệu."""
    return sessionmaker(engine, expire_on_commit=False)


@contextmanager
def mo_kho_trang_thai(engine: Engine) -> Iterator[PostgresSaver]:
    """Mở nơi lưu trạng thái của vòng agent, trong cùng cơ sở dữ liệu với phần còn lại."""
    dia_chi = engine.url.set(drivername="postgresql").render_as_string(hide_password=False)
    with PostgresSaver.from_conn_string(dia_chi) as kho:
        yield kho


def nang_cap(engine: Engine) -> None:
    """Đưa lược đồ lên phiên bản mới nhất."""
    cau_hinh = Config()
    cau_hinh.set_main_option("script_location", str(THU_MUC_MIGRATION))
    with engine.begin() as ket_noi:
        cau_hinh.attributes["connection"] = ket_noi
        command.upgrade(cau_hinh, "head")
    with mo_kho_trang_thai(engine) as kho:
        kho.setup()
