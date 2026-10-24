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
        "runs", sa.Column("verifier_guideline_id", sa.Integer, sa.ForeignKey("guidelines.id"))
    )
    op.add_column("stories", sa.Column("drop_reason", sa.String))
    op.create_table(
        "verifications",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "story_id",
            sa.Integer,
            sa.ForeignKey("stories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("attempt", sa.Integer, nullable=False),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("summary", sa.String, nullable=False),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("reason", sa.String, nullable=False),
        sa.UniqueConstraint("story_id", "attempt"),
    )


def downgrade() -> None:
    op.drop_table("verifications")
    op.drop_column("stories", "drop_reason")
    op.drop_column("runs", "verifier_guideline_id")
