"""Lịch: giờ phát và tạm dừng Chuyên mục, thử lại và thông báo riêng theo Kỳ, tiến độ phát

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sections", sa.Column("publish_time", sa.Time, nullable=False, server_default="08:00")
    )
    op.add_column(
        "sections",
        sa.Column("is_paused", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.add_column("runs", sa.Column("attempts", sa.Integer, nullable=False, server_default="1"))
    op.add_column("runs", sa.Column("retry_at", sa.DateTime(timezone=True)))
    op.add_column("runs", sa.Column("alerted_at", sa.DateTime(timezone=True)))
    # Kỳ có từ trước khi có Lịch thì coi như đã xong: Lịch không thử lại, không chạy tiếp và không
    # nhắn về chúng.
    op.execute("UPDATE runs SET alerted_at = run_at WHERE outcome IS DISTINCT FROM 'published'")
    op.create_table(
        "deliveries",
        sa.Column(
            "bulletin_id",
            sa.Integer,
            sa.ForeignKey("bulletins.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id"), primary_key=True),
        sa.Column("parts_sent", sa.Integer, nullable=False),
        sa.Column("delivered", sa.Boolean, nullable=False),
        sa.Column("error", sa.String),
    )


def downgrade() -> None:
    op.drop_table("deliveries")
    op.drop_column("runs", "alerted_at")
    op.drop_column("runs", "retry_at")
    op.drop_column("runs", "attempts")
    op.drop_column("sections", "is_paused")
    op.drop_column("sections", "publish_time")
