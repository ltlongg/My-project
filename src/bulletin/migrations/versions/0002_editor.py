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
    op.add_column("articles", sa.Column("full_text", sa.String))
    op.create_table(
        "guidelines",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("section_id", sa.Integer, sa.ForeignKey("sections.id", ondelete="CASCADE")),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("content", sa.String, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("role", "section_id", "version", postgresql_nulls_not_distinct=True),
    )
    op.create_index(
        "uq_guidelines_active",
        "guidelines",
        ["role", "section_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
        postgresql_nulls_not_distinct=True,
    )
    op.add_column(
        "runs", sa.Column("editor_guideline_id", sa.Integer, sa.ForeignKey("guidelines.id"))
    )
    # Tin của các Bản tin trước ticket 04 chỉ có tiêu đề gốc.
    for column in ("summary", "reason"):
        op.add_column("stories", sa.Column(column, sa.String, nullable=False, server_default=""))
        op.alter_column("stories", column, server_default=None)


def downgrade() -> None:
    op.drop_column("stories", "reason")
    op.drop_column("stories", "summary")
    op.drop_column("runs", "editor_guideline_id")
    op.drop_table("guidelines")
    op.drop_column("articles", "full_text")
