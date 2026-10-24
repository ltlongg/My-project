"""Trang quản lí: mô tả phạm vi của Chuyên mục, phiên đăng nhập

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Chuyên mục có từ trước để trống; `siftly init` điền phạm vi cho Chuyên mục công nghệ.
    op.add_column("sections", sa.Column("scope", sa.String, nullable=False, server_default=""))
    op.create_table(
        "admin_sessions",
        sa.Column("token_hash", sa.String, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("admin_sessions")
    op.drop_column("sections", "scope")
