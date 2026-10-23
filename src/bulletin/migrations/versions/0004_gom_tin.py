"""Gom Tin: mô tả và vector nhúng của Bài gốc, ứng viên Tin của Kỳ, Tin có nhiều Bài gốc

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import VECTOR

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column("bai_goc", sa.Column("mo_ta", sa.String))
    op.add_column("bai_goc", sa.Column("vector_nhung", VECTOR()))
    op.add_column("bai_goc", sa.Column("mo_hinh_nhung", sa.String))
    op.create_table(
        "ung_vien",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ky_id", sa.Integer, sa.ForeignKey("ky.id", ondelete="CASCADE"), nullable=False),
        sa.Column("thu_tu", sa.Integer, nullable=False),
        sa.Column("tin_da_phat_id", sa.Integer, sa.ForeignKey("tin.id")),
        sa.UniqueConstraint("ky_id", "thu_tu"),
    )
    op.create_table(
        "ung_vien_bai_goc",
        sa.Column(
            "ung_vien_id",
            sa.Integer,
            sa.ForeignKey("ung_vien.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "bai_goc_id",
            sa.Integer,
            sa.ForeignKey("bai_goc.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.add_column("tin", sa.Column("ung_vien_id", sa.Integer, sa.ForeignKey("ung_vien.id")))
    # Tin có từ trước khi có Gom Tin: mỗi Tin là một ứng viên chỉ gồm Bài gốc chính của nó.
    op.execute(
        """
        INSERT INTO ung_vien (ky_id, thu_tu)
        SELECT ban_tin.ky_id, tin.thu_tu FROM tin JOIN ban_tin ON ban_tin.id = tin.ban_tin_id
        """
    )
    op.execute(
        """
        UPDATE tin SET ung_vien_id = ung_vien.id
        FROM ban_tin, ung_vien
        WHERE ban_tin.id = tin.ban_tin_id
          AND ung_vien.ky_id = ban_tin.ky_id AND ung_vien.thu_tu = tin.thu_tu
        """
    )
    op.execute(
        """
        INSERT INTO ung_vien_bai_goc (ung_vien_id, bai_goc_id)
        SELECT ung_vien_id, bai_goc_chinh_id FROM tin
        """
    )
    op.alter_column("tin", "ung_vien_id", nullable=False)


def downgrade() -> None:
    op.drop_column("tin", "ung_vien_id")
    op.drop_table("ung_vien_bai_goc")
    op.drop_table("ung_vien")
    op.drop_column("bai_goc", "mo_hinh_nhung")
    op.drop_column("bai_goc", "vector_nhung")
    op.drop_column("bai_goc", "mo_ta")
