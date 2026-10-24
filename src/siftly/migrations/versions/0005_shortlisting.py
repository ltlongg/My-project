"""Sơ tuyển: điểm của từng ứng viên Tin, ứng viên nào tới Biên tập, giới hạn của từng Chuyên mục

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sections",
        sa.Column("shortlist_size", sa.Integer, nullable=False, server_default="30"),
    )
    op.add_column("candidates", sa.Column("score", sa.Float))
    op.add_column("candidates", sa.Column("score_components", JSONB))
    # Ứng viên có từ trước khi có Sơ tuyển đều đã tới Biên tập.
    op.add_column(
        "candidates",
        sa.Column("shortlisted", sa.Boolean, nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("candidates", "shortlisted")
    op.drop_column("candidates", "score_components")
    op.drop_column("candidates", "score")
    op.drop_column("sections", "shortlist_size")
