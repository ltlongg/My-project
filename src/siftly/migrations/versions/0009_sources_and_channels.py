"""Quản lí Nguồn và Kênh đăng: tắt và bật lại

Revision ID: 0009
Revises: 0008
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("sources", "channels"):
        op.add_column(
            table, sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.true())
        )


def downgrade() -> None:
    for table in ("channels", "sources"):
        op.drop_column(table, "is_enabled")
