from alembic import context
from sqlalchemy import create_engine

from bantin.cau_hinh import CauHinh
from bantin.mo_hinh import CoSo

target_metadata = CoSo.metadata


def run_migrations_online() -> None:
    # bantin.csdl.nang_cap truyền sẵn kết nối; lệnh alembic gọi trực tiếp thì đọc DATABASE_URL.
    ket_noi = context.config.attributes.get("connection")
    if ket_noi is not None:
        context.configure(connection=ket_noi, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
        return

    engine = create_engine(CauHinh().database_url)
    with engine.connect() as ket_noi_moi:
        context.configure(connection=ket_noi_moi, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
