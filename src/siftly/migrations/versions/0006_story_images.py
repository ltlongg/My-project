"""Chụp ảnh: ảnh đã đi kèm từng Tin khi phát

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "story_images",
        sa.Column(
            "story_id",
            sa.Integer,
            sa.ForeignKey("stories.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("data", sa.LargeBinary),
        sa.Column("fallback_reason", sa.String),
    )


def downgrade() -> None:
    op.drop_table("story_images")
