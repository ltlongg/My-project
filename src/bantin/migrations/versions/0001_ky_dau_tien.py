"""Kỳ đầu tiên: Chuyên mục, Nguồn, Kênh đăng, Bài gốc, Kỳ, Bản tin, Tin

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chuyen_muc",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ma", sa.String, nullable=False, unique=True),
        sa.Column("ten", sa.String, nullable=False),
        sa.Column("so_tin_toi_da", sa.Integer, nullable=False),
    )
    op.create_table(
        "nguon",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("loai", sa.String(32), nullable=False),
        sa.Column("ten", sa.String, nullable=False),
        sa.Column("dia_chi", sa.String, nullable=False),
        sa.Column("lay_gan_nhat_luc", sa.DateTime(timezone=True)),
        sa.Column("loi_gan_nhat", sa.String),
        sa.UniqueConstraint("loai", "dia_chi"),
    )
    op.create_table(
        "kenh_dang",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("loai", sa.String(32), nullable=False),
        sa.Column("ten", sa.String, nullable=False),
        sa.Column("dia_chi", sa.String, nullable=False),
        sa.UniqueConstraint("loai", "dia_chi"),
    )
    op.create_table(
        "chuyen_muc_nguon",
        sa.Column(
            "chuyen_muc_id",
            sa.Integer,
            sa.ForeignKey("chuyen_muc.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "nguon_id", sa.Integer, sa.ForeignKey("nguon.id", ondelete="CASCADE"), primary_key=True
        ),
    )
    op.create_table(
        "chuyen_muc_kenh_dang",
        sa.Column(
            "chuyen_muc_id",
            sa.Integer,
            sa.ForeignKey("chuyen_muc.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "kenh_dang_id",
            sa.Integer,
            sa.ForeignKey("kenh_dang.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_table(
        "bai_goc",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("dia_chi_chuan_hoa", sa.String, nullable=False, unique=True),
        sa.Column("dia_chi", sa.String, nullable=False),
        sa.Column("tieu_de", sa.String, nullable=False),
        sa.Column("xuat_hien_luc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("thu_thap_luc", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_bai_goc_xuat_hien_luc", "bai_goc", ["xuat_hien_luc"])
    op.create_table(
        "bai_goc_nguon",
        sa.Column(
            "bai_goc_id",
            sa.Integer,
            sa.ForeignKey("bai_goc.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "nguon_id", sa.Integer, sa.ForeignKey("nguon.id", ondelete="CASCADE"), primary_key=True
        ),
    )
    op.create_table(
        "ky",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("chuyen_muc_id", sa.Integer, sa.ForeignKey("chuyen_muc.id"), nullable=False),
        sa.Column("thoi_diem", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ket_qua", sa.String(32)),
        sa.Column("li_do", sa.String),
    )
    op.create_index("ix_ky_chuyen_muc_id", "ky", ["chuyen_muc_id"])
    op.create_table(
        "ban_tin",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ky_id", sa.Integer, sa.ForeignKey("ky.id"), nullable=False, unique=True),
    )
    op.create_table(
        "tin",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ban_tin_id", sa.Integer, sa.ForeignKey("ban_tin.id"), nullable=False),
        sa.Column("thu_tu", sa.Integer, nullable=False),
        sa.Column("tieu_de", sa.String, nullable=False),
        sa.Column("bai_goc_chinh_id", sa.Integer, sa.ForeignKey("bai_goc.id"), nullable=False),
        sa.UniqueConstraint("ban_tin_id", "thu_tu"),
    )


def downgrade() -> None:
    for bang in (
        "tin",
        "ban_tin",
        "ky",
        "bai_goc_nguon",
        "bai_goc",
        "chuyen_muc_kenh_dang",
        "chuyen_muc_nguon",
        "kenh_dang",
        "nguon",
        "chuyen_muc",
    ):
        op.drop_table(bang)
