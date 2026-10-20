"""Biên tập: toàn văn Bài gốc, Hướng dẫn theo phiên bản, tóm tắt và lí do chọn của Tin

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bai_goc", sa.Column("toan_van", sa.String))
    op.create_table(
        "huong_dan",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("vai_tro", sa.String(32), nullable=False),
        sa.Column("chuyen_muc_id", sa.Integer, sa.ForeignKey("chuyen_muc.id", ondelete="CASCADE")),
        sa.Column("phien_ban", sa.Integer, nullable=False),
        sa.Column("noi_dung", sa.String, nullable=False),
        sa.Column("co_hieu_luc", sa.Boolean, nullable=False),
        sa.Column(
            "tao_luc", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "vai_tro", "chuyen_muc_id", "phien_ban", postgresql_nulls_not_distinct=True
        ),
    )
    op.create_index(
        "uq_huong_dan_co_hieu_luc",
        "huong_dan",
        ["vai_tro", "chuyen_muc_id"],
        unique=True,
        postgresql_where=sa.text("co_hieu_luc"),
        postgresql_nulls_not_distinct=True,
    )
    op.add_column(
        "ky", sa.Column("huong_dan_bien_tap_id", sa.Integer, sa.ForeignKey("huong_dan.id"))
    )
    # Tin của các Bản tin trước ticket 04 chỉ có tiêu đề gốc.
    for cot in ("tom_tat", "li_do"):
        op.add_column("tin", sa.Column(cot, sa.String, nullable=False, server_default=""))
        op.alter_column("tin", cot, server_default=None)


def downgrade() -> None:
    op.drop_column("tin", "li_do")
    op.drop_column("tin", "tom_tat")
    op.drop_column("ky", "huong_dan_bien_tap_id")
    op.drop_table("huong_dan")
    op.drop_column("bai_goc", "toan_van")
