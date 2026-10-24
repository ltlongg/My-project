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
    op.add_column("articles", sa.Column("description", sa.String))
    op.add_column("articles", sa.Column("embedding", VECTOR()))
    op.add_column("articles", sa.Column("embedding_model", sa.String))
    op.create_table(
        "candidates",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "run_id", sa.Integer, sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("published_story_id", sa.Integer, sa.ForeignKey("stories.id")),
        sa.UniqueConstraint("run_id", "position"),
    )
    op.create_table(
        "candidate_articles",
        sa.Column(
            "candidate_id",
            sa.Integer,
            sa.ForeignKey("candidates.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "article_id",
            sa.Integer,
            sa.ForeignKey("articles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.add_column("stories", sa.Column("candidate_id", sa.Integer, sa.ForeignKey("candidates.id")))
    # Tin có từ trước khi có Gom Tin: mỗi Tin là một ứng viên chỉ gồm Bài gốc chính của nó.
    op.execute(
        """
        INSERT INTO candidates (run_id, position)
        SELECT bulletins.run_id, stories.position
        FROM stories JOIN bulletins ON bulletins.id = stories.bulletin_id
        """
    )
    op.execute(
        """
        UPDATE stories SET candidate_id = candidates.id
        FROM bulletins, candidates
        WHERE bulletins.id = stories.bulletin_id
          AND candidates.run_id = bulletins.run_id AND candidates.position = stories.position
        """
    )
    op.execute(
        """
        INSERT INTO candidate_articles (candidate_id, article_id)
        SELECT candidate_id, primary_article_id FROM stories
        """
    )
    op.alter_column("stories", "candidate_id", nullable=False)


def downgrade() -> None:
    op.drop_column("stories", "candidate_id")
    op.drop_table("candidate_articles")
    op.drop_table("candidates")
    op.drop_column("articles", "embedding_model")
    op.drop_column("articles", "embedding")
    op.drop_column("articles", "description")
