from alembic import context
from sqlalchemy import create_engine

from bulletin.config import Settings
from bulletin.models import Base

target_metadata = Base.metadata


def run_migrations_online() -> None:
    # bulletin.db.upgrade truyền sẵn kết nối; lệnh alembic gọi trực tiếp thì đọc DATABASE_URL.
    connection = context.config.attributes.get("connection")
    if connection is not None:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
        return

    engine = create_engine(Settings().database_url)
    with engine.connect() as new_connection:
        context.configure(connection=new_connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
