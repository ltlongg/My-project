"""Kiểm chứng: các lượt Kiểm chứng của Tin, Tin bị bỏ, Hướng dẫn của Kiểm chứng mà Kỳ dùng

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ky", sa.Column("huong_dan_kiem_chung_id", sa.Integer, sa.ForeignKey("huong_dan.id"))
    )
    op.add_column("tin", sa.Column("li_do_bo", sa.String))
    op.create_table(
        "luot_kiem_chung",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "tin_id", sa.Integer, sa.ForeignKey("tin.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("lan", sa.Integer, nullable=False),
        sa.Column("tieu_de", sa.String, nullable=False),
        sa.Column("tom_tat", sa.String, nullable=False),
        sa.Column("dat", sa.Boolean, nullable=False),
        sa.Column("li_do", sa.String, nullable=False),
        sa.UniqueConstraint("tin_id", "lan"),
    )


def downgrade() -> None:
    op.drop_table("luot_kiem_chung")
    op.drop_column("tin", "li_do_bo")
    op.drop_column("ky", "huong_dan_kiem_chung_id")
