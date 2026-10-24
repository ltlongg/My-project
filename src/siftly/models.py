"""Các thực thể được lưu trong Postgres. Thuật ngữ theo CONTEXT.md."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Table,
    UniqueConstraint,
    func,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class SourceKind(StrEnum):
    RSS = "rss"


class ChannelKind(StrEnum):
    TELEGRAM = "telegram"


class RunOutcome(StrEnum):
    PUBLISHED = "published"
    NOT_PUBLISHED = "not_published"
    FAILED = "failed"


class Role(StrEnum):
    """Agent mà một Hướng dẫn chỉ dẫn."""

    EDITOR = "editor"
    VERIFIER = "verifier"


def _enum_column(kind: type[StrEnum]) -> Enum:
    # Lưu dạng chữ thay vì kiểu enum của Postgres để thêm giá trị không cần migration riêng.
    return Enum(kind, native_enum=False, length=32, values_callable=lambda e: [m.value for m in e])


class Base(DeclarativeBase):
    type_annotation_map = {datetime: DateTime(timezone=True)}


section_sources = Table(
    "section_sources",
    Base.metadata,
    Column("section_id", ForeignKey("sections.id", ondelete="CASCADE"), primary_key=True),
    Column("source_id", ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True),
)

section_channels = Table(
    "section_channels",
    Base.metadata,
    Column("section_id", ForeignKey("sections.id", ondelete="CASCADE"), primary_key=True),
    Column("channel_id", ForeignKey("channels.id", ondelete="CASCADE"), primary_key=True),
)

# Một Bài gốc chỉ lưu một lần; bảng này ghi nó đã được thấy ở những Nguồn nào.
article_sources = Table(
    "article_sources",
    Base.metadata,
    Column("article_id", ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True),
    Column("source_id", ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True),
)

# Các Bài gốc cùng nói về một sự kiện mà Gom Tin đã gom thành một ứng viên Tin.
candidate_articles = Table(
    "candidate_articles",
    Base.metadata,
    Column("candidate_id", ForeignKey("candidates.id", ondelete="CASCADE"), primary_key=True),
    Column("article_id", ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True),
)


class Section(Base):
    __tablename__ = "sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
    max_stories: Mapped[int]
    # Số ứng viên Tin tối đa qua Sơ tuyển để tới Biên tập mỗi Kỳ.
    shortlist_size: Mapped[int] = mapped_column(default=30, server_default="30")

    sources: Mapped[list[Source]] = relationship(secondary=section_sources, order_by="Source.id")
    channels: Mapped[list[Channel]] = relationship(
        secondary=section_channels, order_by="Channel.id"
    )


class Source(Base):
    __tablename__ = "sources"
    __table_args__ = (UniqueConstraint("kind", "url"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[SourceKind] = mapped_column(_enum_column(SourceKind))
    name: Mapped[str]
    url: Mapped[str]
    last_fetched_at: Mapped[datetime | None]
    last_error: Mapped[str | None]


class Channel(Base):
    __tablename__ = "channels"
    __table_args__ = (UniqueConstraint("kind", "address"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[ChannelKind] = mapped_column(_enum_column(ChannelKind))
    name: Mapped[str]
    address: Mapped[str]


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    normalized_url: Mapped[str] = mapped_column(unique=True)
    url: Mapped[str]
    title: Mapped[str]
    # Đoạn mô tả ngắn Nguồn kèm theo; không có thì để trống.
    description: Mapped[str | None]
    appeared_at: Mapped[datetime] = mapped_column(index=True)
    collected_at: Mapped[datetime]
    # Chưa có nghĩa là chưa ai cần đọc Bài gốc này, hoặc không lấy được nội dung.
    full_text: Mapped[str | None]
    # Vector nhúng dùng để gom Tin, cùng tên model đã tạo ra nó; chưa nhúng thì để trống. Không ghi
    # số chiều để đổi được sang model khác mà không cần migration.
    embedding: Mapped[list[float] | None] = mapped_column(VECTOR())
    embedding_model: Mapped[str | None]

    sources: Mapped[list[Source]] = relationship(secondary=article_sources, order_by="Source.id")


class Guideline(Base):
    __tablename__ = "guidelines"
    __table_args__ = (
        UniqueConstraint("role", "section_id", "version", postgresql_nulls_not_distinct=True),
        # Mỗi Agent, mỗi Chuyên mục chỉ có một phiên bản đang có hiệu lực.
        Index(
            "uq_guidelines_active",
            "role",
            "section_id",
            unique=True,
            postgresql_where="is_active",
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    role: Mapped[Role] = mapped_column(_enum_column(Role))
    # Để trống là Hướng dẫn chung cho mọi Chuyên mục.
    section_id: Mapped[int | None] = mapped_column(ForeignKey("sections.id", ondelete="CASCADE"))
    version: Mapped[int]
    content: Mapped[str]
    is_active: Mapped[bool]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.id"), index=True)
    run_at: Mapped[datetime]
    # Chưa có kết quả nghĩa là Kỳ đang chạy hoặc bị gián đoạn giữa chừng.
    outcome: Mapped[RunOutcome | None] = mapped_column(_enum_column(RunOutcome))
    reason: Mapped[str | None]
    # Phiên bản Hướng dẫn mà Biên tập và Kiểm chứng dùng ở Kỳ này.
    editor_guideline_id: Mapped[int | None] = mapped_column(ForeignKey("guidelines.id"))
    verifier_guideline_id: Mapped[int | None] = mapped_column(ForeignKey("guidelines.id"))

    section: Mapped[Section] = relationship()
    editor_guideline: Mapped[Guideline | None] = relationship(foreign_keys=[editor_guideline_id])
    verifier_guideline: Mapped[Guideline | None] = relationship(
        foreign_keys=[verifier_guideline_id]
    )
    # Mọi ứng viên Tin sau Gom Tin, điểm Sơ tuyển cao nhất trước, kể cả ứng viên bị loại.
    candidates: Mapped[list[Candidate]] = relationship(order_by="Candidate.position")
    bulletin: Mapped[Bulletin | None] = relationship(back_populates="run")

    @property
    def shortlist(self) -> list[Candidate]:
        """Các ứng viên qua Sơ tuyển, theo thứ tự: Biên tập chọn Tin trong số này."""
        return [candidate for candidate in self.candidates if candidate.shortlisted]


class Bulletin(Base):
    __tablename__ = "bulletins"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), unique=True)

    run: Mapped[Run] = relationship(back_populates="bulletin")
    # Mọi Tin Biên tập nộp, kể cả Tin bị bỏ vì không qua Kiểm chứng.
    stories: Mapped[list[Story]] = relationship(
        back_populates="bulletin", order_by="Story.position"
    )


class Candidate(Base):
    """Một ứng viên Tin của Kỳ: các Bài gốc Gom Tin cho là cùng nói về một sự kiện."""

    __tablename__ = "candidates"
    __table_args__ = (UniqueConstraint("run_id", "position"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"))
    # Thứ hạng theo điểm Sơ tuyển, từ 1; Biên tập thấy các ứng viên qua Sơ tuyển theo thứ tự này.
    position: Mapped[int]
    # Tin đã phát của cùng Chuyên mục mà ứng viên này giống; có thì ứng viên chỉ được phát như một
    # Tin "Cập nhật" của Tin đó.
    published_story_id: Mapped[int | None] = mapped_column(ForeignKey("stories.id"))
    # Điểm Sơ tuyển, và các điểm thành phần từ 0 tới 1 theo tên tín hiệu; ứng viên có từ trước khi
    # có Sơ tuyển thì để trống.
    score: Mapped[float | None]
    score_components: Mapped[dict[str, float] | None] = mapped_column(JSONB)
    # Có qua Sơ tuyển để tới Biên tập hay không.
    shortlisted: Mapped[bool] = mapped_column(server_default=true())

    articles: Mapped[list[Article]] = relationship(
        secondary=candidate_articles, order_by=[Article.appeared_at, Article.id]
    )
    published_story: Mapped[Story | None] = relationship(foreign_keys=[published_story_id])


class Story(Base):
    __tablename__ = "stories"
    __table_args__ = (UniqueConstraint("bulletin_id", "position"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    bulletin_id: Mapped[int] = mapped_column(ForeignKey("bulletins.id"))
    position: Mapped[int]
    # Bản viết cuối cùng; các bản trước nằm ở các lượt Kiểm chứng.
    title: Mapped[str]
    summary: Mapped[str]
    # Vì sao Biên tập chọn Tin này.
    reason: Mapped[str]
    # Ứng viên Tin được gom từ đó; các Bài gốc của nó là các Bài gốc của Tin.
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"))
    # Một trong các Bài gốc của Tin, do Biên tập chọn: Tin dẫn link tới nó.
    primary_article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"))
    # Có giá trị là Tin bị bỏ khỏi Bản tin vì không qua Kiểm chứng, và đây là lí do.
    drop_reason: Mapped[str | None]

    bulletin: Mapped[Bulletin] = relationship(back_populates="stories")
    candidate: Mapped[Candidate] = relationship(foreign_keys=[candidate_id])
    primary_article: Mapped[Article] = relationship()
    verifications: Mapped[list[Verification]] = relationship(
        back_populates="story", order_by="Verification.attempt", cascade="all, delete-orphan"
    )

    @property
    def update_of(self) -> Story | None:
        """Tin đã phát mà Tin này là bản "Cập nhật" của nó; None là Tin mới."""
        return self.candidate.published_story


class Verification(Base):
    """Một lần Kiểm chứng xét một bản viết của Tin; bản sau một lượt không đạt là bản viết lại."""

    __tablename__ = "verifications"
    __table_args__ = (UniqueConstraint("story_id", "attempt"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    story_id: Mapped[int] = mapped_column(ForeignKey("stories.id", ondelete="CASCADE"))
    # Lượt thứ mấy, từ 1; lượt 1 xét bản đầu tiên.
    attempt: Mapped[int]
    title: Mapped[str]
    summary: Mapped[str]
    passed: Mapped[bool]
    reason: Mapped[str]

    story: Mapped[Story] = relationship(back_populates="verifications")
