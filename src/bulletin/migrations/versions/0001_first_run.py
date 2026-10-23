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
        "sections",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("slug", sa.String, nullable=False, unique=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("max_stories", sa.Integer, nullable=False),
    )
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("url", sa.String, nullable=False),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String),
        sa.UniqueConstraint("kind", "url"),
    )
    op.create_table(
        "channels",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("address", sa.String, nullable=False),
        sa.UniqueConstraint("kind", "address"),
    )
    op.create_table(
        "section_sources",
        sa.Column(
            "section_id",
            sa.Integer,
            sa.ForeignKey("sections.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "source_id",
            sa.Integer,
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_table(
        "section_channels",
        sa.Column(
            "section_id",
            sa.Integer,
            sa.ForeignKey("sections.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "channel_id",
            sa.Integer,
            sa.ForeignKey("channels.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_table(
        "articles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("normalized_url", sa.String, nullable=False, unique=True),
        sa.Column("url", sa.String, nullable=False),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("appeared_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_articles_appeared_at", "articles", ["appeared_at"])
    op.create_table(
        "article_sources",
        sa.Column(
            "article_id",
            sa.Integer,
            sa.ForeignKey("articles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "source_id",
            sa.Integer,
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_table(
        "runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("section_id", sa.Integer, sa.ForeignKey("sections.id"), nullable=False),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome", sa.String(32)),
        sa.Column("reason", sa.String),
    )
    op.create_index("ix_runs_section_id", "runs", ["section_id"])
    op.create_table(
        "bulletins",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("runs.id"), nullable=False, unique=True),
    )
    op.create_table(
        "stories",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("bulletin_id", sa.Integer, sa.ForeignKey("bulletins.id"), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("primary_article_id", sa.Integer, sa.ForeignKey("articles.id"), nullable=False),
        sa.UniqueConstraint("bulletin_id", "position"),
    )


def downgrade() -> None:
    for table in (
        "stories",
        "bulletins",
        "runs",
        "article_sources",
        "articles",
        "section_channels",
        "section_sources",
        "channels",
        "sources",
        "sections",
    ):
        op.drop_table(table)
