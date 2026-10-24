"""Các thực thể được lưu trong Postgres. Thuật ngữ theo CONTEXT.md."""

from __future__ import annotations

from datetime import datetime, time
from enum import StrEnum

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    LargeBinary,
    Table,
    UniqueConstraint,
    false,
    func,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from siftly.images import ImageKind


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
    # Mô tả phạm vi do chủ hệ thống viết: Sơ tuyển và Biên tập đọc nó cùng Hướng dẫn của Biên tập.
    scope: Mapped[str] = mapped_column(default="", server_default="")
    max_stories: Mapped[int]
    # Số ứng viên Tin tối đa qua Sơ tuyển để tới Biên tập mỗi Kỳ.
    shortlist_size: Mapped[int] = mapped_column(default=30, server_default="30")
    # Giờ phát theo giờ Việt Nam: Lịch chạy một Kỳ của Chuyên mục vào giờ này mỗi ngày.
    publish_time: Mapped[time] = mapped_column(default=time(8), server_default="08:00")
    # Chuyên mục đang tạm dừng thì Lịch không chạy Kỳ nào cho nó; thiết lập vẫn giữ nguyên.
    is_paused: Mapped[bool] = mapped_column(default=False, server_default=false())

    # Mọi Nguồn và Kênh đăng đã gắn, kể cả những cái đang tắt.
    sources: Mapped[list[Source]] = relationship(
        secondary=section_sources, order_by="Source.id", back_populates="sections"
    )
    channels: Mapped[list[Channel]] = relationship(
        secondary=section_channels, order_by="Channel.id", back_populates="sections"
    )

    @property
    def enabled_sources(self) -> list[Source]:
        """Các Nguồn Kỳ thu thập và lấy ứng viên từ đó."""
        return [source for source in self.sources if source.is_enabled]

    @property
    def enabled_channels(self) -> list[Channel]:
        """Các Kênh đăng nhận Bản tin của Chuyên mục."""
        return [channel for channel in self.channels if channel.is_enabled]


class Source(Base):
    __tablename__ = "sources"
    __table_args__ = (UniqueConstraint("kind", "url"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[SourceKind] = mapped_column(_enum_column(SourceKind))
    name: Mapped[str]
    url: Mapped[str]
    # Nguồn đang tắt không được thu thập và không góp ứng viên cho Kỳ nào; thiết lập vẫn giữ nguyên.
    is_enabled: Mapped[bool] = mapped_column(default=True, server_default=true())
    # Lần thu thập gần nhất, thành công hay không, và lỗi của lần ấy; lấy được thì để trống.
    last_fetched_at: Mapped[datetime | None]
    last_error: Mapped[str | None]

    sections: Mapped[list[Section]] = relationship(
        secondary=section_sources, order_by="Section.id", back_populates="sources"
    )


class Channel(Base):
    __tablename__ = "channels"
    __table_args__ = (UniqueConstraint("kind", "address"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[ChannelKind] = mapped_column(_enum_column(ChannelKind))
    name: Mapped[str]
    address: Mapped[str]
    # Kênh đăng đang tắt không nhận Bản tin nào; thiết lập vẫn giữ nguyên.
    is_enabled: Mapped[bool] = mapped_column(default=True, server_default=true())

    sections: Mapped[list[Section]] = relationship(
        secondary=section_channels, order_by="Section.id", back_populates="channels"
    )


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
    # Số lần đã chạy Kỳ này: lần đầu, rồi mỗi lần thử lại sau khi hỏng thêm một.
    attempts: Mapped[int] = mapped_column(default=1, server_default="1")
    # Lúc Lịch sẽ thử lại Kỳ hỏng này; trống là không có lần thử lại nào đang chờ.
    retry_at: Mapped[datetime | None]
    # Lúc chủ hệ thống được nhắn riêng về việc Kỳ này hỏng hẳn hoặc không phát; trống là chưa nhắn.
    alerted_at: Mapped[datetime | None]

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
    deliveries: Mapped[list[Delivery]] = relationship(
        order_by="Delivery.channel_id", cascade="all, delete-orphan"
    )


class Delivery(Base):
    """Việc phát một Bản tin tới một Kênh đăng.

    Bộ phát gửi Bản tin thành nhiều phần theo thứ tự, ví dụ mỗi Tin một tin nhắn. Tiến độ được lưu
    sau từng phần, để lần phát tiếp sau khi hỏng giữa chừng bỏ qua những phần đã tới nơi.
    """

    __tablename__ = "deliveries"

    bulletin_id: Mapped[int] = mapped_column(
        ForeignKey("bulletins.id", ondelete="CASCADE"), primary_key=True
    )
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"), primary_key=True)
    # Số phần đầu của Bản tin đã tới Kênh đăng.
    parts_sent: Mapped[int]
    # Kênh đăng đã nhận trọn Bản tin.
    delivered: Mapped[bool]
    # Lỗi của lần phát gần nhất; phát trọn rồi thì để trống.
    error: Mapped[str | None]

    channel: Mapped[Channel] = relationship()


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
    # Ảnh đã đi kèm Tin khi phát; chưa có nghĩa là chưa tới bước chụp ảnh.
    image: Mapped[StoryImage | None] = relationship(cascade="all, delete-orphan")

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


class StoryImage(Base):
    """Ảnh đi kèm một Tin khi phát, đúng như đã gửi tới mọi Kênh đăng."""

    __tablename__ = "story_images"

    story_id: Mapped[int] = mapped_column(
        ForeignKey("stories.id", ondelete="CASCADE"), primary_key=True
    )
    kind: Mapped[ImageKind] = mapped_column(_enum_column(ImageKind))
    # Ảnh JPEG; Tin được phát không ảnh thì để trống.
    data: Mapped[bytes | None] = mapped_column(LargeBinary)
    # Vì sao không dùng được cách tốt hơn, ví dụ vì sao không chụp được trang; mỗi lí do một dòng.
    fallback_reason: Mapped[str | None]


class AdminSession(Base):
    """Một phiên đăng nhập trang quản lí. Chỉ lưu dạng băm của mã phiên trong cookie."""

    __tablename__ = "admin_sessions"

    token_hash: Mapped[str] = mapped_column(primary_key=True)
    created_at: Mapped[datetime]
    expires_at: Mapped[datetime]
