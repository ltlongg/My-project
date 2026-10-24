"""Thiết lập Nguồn: thêm, sửa, tắt và bật lại, gắn vào Chuyên mục, bấm thử trước khi lưu, và tình
trạng thu thập của từng Nguồn.

Không xoá Nguồn: Bài gốc đã thu thập vẫn ghi là thấy ở Nguồn đó. Tắt là cách bỏ một Nguồn ra khỏi
Bản tin.
"""

import logging
from collections.abc import Collection, Mapping
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select

from siftly.admin import sections
from siftly.admin.deps import Clock, Db, Invalid, clean_text
from siftly.admin.kinds import SOURCE_KINDS, KindOut, kinds_out
from siftly.collectors import Collector
from siftly.models import Article, Source, SourceKind, article_sources

log = logging.getLogger(__name__)

MAX_NAME_LENGTH = 80
MAX_URL_LENGTH = 2000
# "Gần đây" ở tình trạng của Nguồn: số Bài gốc xuất hiện trong khoảng này.
RECENT = timedelta(days=7)
# Số Bài gốc mẫu khi bấm thử: đủ để nhận ra đúng Nguồn mà không dài quá một màn hình.
SAMPLE_SIZE = 5
# Bấm thử lấy mọi bài Nguồn đang trả về, không lọc theo thời gian.
EVERYTHING = datetime(1970, 1, 1, tzinfo=UTC)

router = APIRouter(prefix="/sources")


class SourceOut(BaseModel):
    id: int
    kind: SourceKind
    name: str
    url: str
    is_enabled: bool
    section_ids: list[int]
    # Lần thu thập gần nhất, lấy được hay không; chưa thu thập lần nào thì để trống.
    last_fetched_at: datetime | None
    # Lỗi của lần thu thập gần nhất; lấy được thì để trống.
    last_error: str | None
    # Số Bài gốc thấy ở Nguồn này xuất hiện trong 7 ngày qua.
    recent_articles: int


class SourceChanges(BaseModel):
    """Những gì sửa được; trường không gửi thì giữ nguyên. Loại Nguồn không đổi được."""

    name: str | None = None
    url: str | None = None
    section_ids: list[int] | None = None
    is_enabled: bool | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        return None if value is None else clean_text(value, MAX_NAME_LENGTH)

    @field_validator("url")
    @classmethod
    def _url(cls, value: str | None) -> str | None:
        return None if value is None else clean_text(value, MAX_URL_LENGTH)


class NewSource(SourceChanges):
    kind: SourceKind
    name: str
    url: str
    section_ids: list[int] = []


class Trial(BaseModel):
    """Một Nguồn chưa lưu, để bấm thử."""

    kind: SourceKind
    url: str

    @field_validator("url")
    @classmethod
    def _url(cls, value: str) -> str:
        return clean_text(value, MAX_URL_LENGTH)


class SampleArticle(BaseModel):
    title: str
    url: str
    published_at: datetime | None
    description: str | None


class TrialResult(BaseModel):
    # Vài Bài gốc mới nhất Nguồn đang trả về; lỗi thì trống.
    articles: list[SampleArticle]
    # Số Bài gốc Nguồn đang trả về, kể cả những bài không hiện ở đây.
    total: int
    # Lời nhắn khi không lấy được; lấy được thì để trống.
    error: str | None


@router.get("/kinds")
def list_kinds() -> list[KindOut]:
    return kinds_out(SOURCE_KINDS)


@router.post("/test")
def try_source(trial: Trial, request: Request) -> TrialResult:
    """Lấy thử Nguồn và trả về vài Bài gốc mẫu, không lưu gì."""
    if problem := SOURCE_KINDS[trial.kind].check(trial.url):
        raise Invalid(url=problem)
    collectors: Mapping[SourceKind, Collector] = request.app.state.collectors
    collector = collectors.get(trial.kind)
    if collector is None:
        label = SOURCE_KINDS[trial.kind].label
        return TrialResult(
            articles=[], total=0, error=f"Máy chủ chưa có bộ thu thập cho Nguồn loại {label}"
        )
    try:
        found = collector.collect(trial.url, EVERYTHING)
    except Exception as error:
        log.info("Bấm thử Nguồn %s không lấy được", trial.url, exc_info=True)
        return TrialResult(articles=[], total=0, error=_first_line(error))
    newest = sorted(found, key=lambda article: article.published_at or EVERYTHING, reverse=True)
    return TrialResult(
        articles=[
            SampleArticle(
                title=article.title,
                url=article.url,
                published_at=article.published_at,
                description=article.description,
            )
            for article in newest[:SAMPLE_SIZE]
        ],
        total=len(found),
        error=None,
    )


@router.get("")
def list_sources(db: Db, clock: Clock) -> list[SourceOut]:
    found = list(db.scalars(select(Source).order_by(Source.id)))
    counts = _recent_counts(db, clock(), [source.id for source in found])
    return [_out(source, counts) for source in found]


@router.post("", status_code=201)
def create_source(new: NewSource, db: Db, clock: Clock) -> SourceOut:
    source = Source(kind=new.kind)
    _apply(db, source, new)
    db.add(source)
    db.commit()
    return _out(source, _recent_counts(db, clock(), [source.id]))


@router.get("/{source_id}")
def get_source(source_id: int, db: Db, clock: Clock) -> SourceOut:
    source = _find(db, source_id)
    return _out(source, _recent_counts(db, clock(), [source.id]))


@router.patch("/{source_id}")
def update_source(source_id: int, changes: SourceChanges, db: Db, clock: Clock) -> SourceOut:
    source = _find(db, source_id)
    _apply(db, source, changes)
    db.commit()
    return _out(source, _recent_counts(db, clock(), [source.id]))


def _find(db: Db, source_id: int) -> Source:
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(404, "Không có Nguồn này")
    return source


def _apply(db: Db, source: Source, changes: SourceChanges) -> None:
    """Ghi thay đổi vào `source`; ném Invalid trước khi ghi gì nếu có trường chưa hợp lệ."""
    if changes.url is not None:
        if problem := SOURCE_KINDS[source.kind].check(changes.url):
            raise Invalid(url=problem)
        same = db.scalar(
            select(Source).where(
                Source.kind == source.kind, Source.url == changes.url, Source.id != source.id
            )
        )
        if same is not None:
            raise Invalid(url=f"Đã có Nguồn {same.name} với địa chỉ này")
    attached = None if changes.section_ids is None else sections.find_all(db, changes.section_ids)
    if changes.name is not None:
        source.name = changes.name
    if changes.url is not None:
        source.url = changes.url
    if attached is not None:
        source.sections = attached
    if changes.is_enabled is not None:
        source.is_enabled = changes.is_enabled


def _recent_counts(db: Db, now: datetime, source_ids: Collection[int]) -> dict[int, int]:
    """Số Bài gốc xuất hiện trong 7 ngày qua của từng Nguồn; Nguồn không có bài nào thì vắng."""
    rows = db.execute(
        select(article_sources.c.source_id, func.count())
        .join(Article, Article.id == article_sources.c.article_id)
        .where(article_sources.c.source_id.in_(source_ids), Article.appeared_at > now - RECENT)
        .group_by(article_sources.c.source_id)
    )
    return {source_id: count for source_id, count in rows}


def _out(source: Source, recent_counts: Mapping[int, int]) -> SourceOut:
    return SourceOut(
        id=source.id,
        kind=source.kind,
        name=source.name,
        url=source.url,
        is_enabled=source.is_enabled,
        section_ids=[section.id for section in source.sections],
        last_fetched_at=source.last_fetched_at,
        last_error=source.last_error,
        recent_articles=recent_counts.get(source.id, 0),
    )


def _first_line(error: Exception) -> str:
    return (str(error).splitlines() or [type(error).__name__])[0]
