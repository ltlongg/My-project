"""Kết nối Postgres và nâng cấp lược đồ."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

THU_MUC_MIGRATION = Path(__file__).parent / "migrations"


def tao_engine(database_url: str) -> Engine:
    return create_engine(database_url)


def tao_mo_phien(engine: Engine) -> sessionmaker[Session]:
    """Trả về hàm mở phiên làm việc với cơ sở dữ liệu."""
    return sessionmaker(engine, expire_on_commit=False)


def nang_cap(engine: Engine) -> None:
    """Đưa lược đồ lên phiên bản mới nhất."""
    cau_hinh = Config()
    cau_hinh.set_main_option("script_location", str(THU_MUC_MIGRATION))
    with engine.begin() as ket_noi:
        cau_hinh.attributes["connection"] = ket_noi
        command.upgrade(cau_hinh, "head")
