"""Thiết lập Chuyên mục: tạo, sửa, tạm dừng và bật lại.

Lịch và Chạy Kỳ đọc thiết lập từ cơ sở dữ liệu ở mỗi lượt, nên thay đổi có hiệu lực từ Kỳ kế tiếp
mà không cần khởi động lại.
"""

import re
import unicodedata
from collections.abc import Iterable
from datetime import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select

from siftly.admin.deps import Db, Invalid, clean_text
from siftly.models import Guideline, Role, Section
from siftly.seed import STARTER_EDITOR_GUIDELINE

MAX_NAME_LENGTH = 80
MAX_SCOPE_LENGTH = 2000
# Bản tin có 5–7 Tin; dưới 3 thì không phát, nên giới hạn thấp hơn 3 không ra được Bản tin nào.
MIN_STORIES, MAX_STORIES = 3, 10
TIME_PATTERN = re.compile(r"([01]\d|2[0-3]):([0-5]\d)")

router = APIRouter(prefix="/sections")


class SectionOut(BaseModel):
    id: int
    # Mã dùng ở dòng lệnh, như `siftly run tech`; đặt một lần khi tạo, không đổi.
    slug: str
    name: str
    scope: str
    # Giờ phát theo giờ Việt Nam, dạng "08:00".
    publish_time: str
    max_stories: int
    is_paused: bool


class SectionChanges(BaseModel):
    """Những gì sửa được; trường không gửi thì giữ nguyên."""

    name: str | None = None
    scope: str | None = None
    publish_time: str | None = None
    max_stories: int | None = None
    is_paused: bool | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        return None if value is None else clean_text(value, MAX_NAME_LENGTH)

    @field_validator("scope")
    @classmethod
    def _scope(cls, value: str | None) -> str | None:
        return None if value is None else clean_text(value, MAX_SCOPE_LENGTH)

    @field_validator("publish_time")
    @classmethod
    def _publish_time(cls, value: str | None) -> str | None:
        if value is not None and not TIME_PATTERN.fullmatch(value):
            raise ValueError("Giờ phát có dạng HH:MM, ví dụ 08:00")
        return value

    @field_validator("max_stories")
    @classmethod
    def _max_stories(cls, value: int | None) -> int | None:
        if value is not None and not MIN_STORIES <= value <= MAX_STORIES:
            raise ValueError(f"Số Tin mỗi Bản tin từ {MIN_STORIES} đến {MAX_STORIES}")
        return value


class NewSection(SectionChanges):
    """Chuyên mục mới cần đủ tên, phạm vi, giờ phát và số Tin."""

    name: str
    scope: str
    publish_time: str
    max_stories: int


@router.get("")
def list_sections(db: Db) -> list[SectionOut]:
    return [_out(section) for section in db.scalars(select(Section).order_by(Section.id))]


@router.post("", status_code=201)
def create_section(new: NewSection, db: Db) -> SectionOut:
    """Chuyên mục mới mặc định ở trạng thái tạm dừng, vì chưa có Nguồn và Kênh đăng nào: chạy lúc
    này chỉ ra một Kỳ hỏng. Nó có sẵn một Hướng dẫn khởi đầu cho Biên tập."""
    section = Section(slug=_free_slug(db, new.name), is_paused=True)
    _apply(section, new)
    db.add(section)
    db.flush()
    db.add(
        Guideline(
            role=Role.EDITOR,
            section_id=section.id,
            version=1,
            content=STARTER_EDITOR_GUIDELINE,
            is_active=True,
        )
    )
    db.commit()
    return _out(section)


@router.get("/{section_id}")
def get_section(section_id: int, db: Db) -> SectionOut:
    return _out(_find(db, section_id))


@router.patch("/{section_id}")
def update_section(section_id: int, changes: SectionChanges, db: Db) -> SectionOut:
    section = _find(db, section_id)
    _apply(section, changes)
    db.commit()
    return _out(section)


def _find(db: Db, section_id: int) -> Section:
    section = db.get(Section, section_id)
    if section is None:
        raise HTTPException(404, "Không có Chuyên mục này")
    return section


def find_all(db: Db, section_ids: Iterable[int]) -> list[Section]:
    """Các Chuyên mục theo mã số, để gắn Nguồn hay Kênh đăng vào; ném Invalid nếu thiếu cái nào."""
    wanted = set(section_ids)
    found = list(db.scalars(select(Section).where(Section.id.in_(wanted)).order_by(Section.id)))
    if len(found) < len(wanted):
        raise Invalid(section_ids="Không có Chuyên mục này")
    return found


def _apply(section: Section, changes: SectionChanges) -> None:
    if changes.name is not None:
        section.name = changes.name
    if changes.scope is not None:
        section.scope = changes.scope
    if changes.publish_time is not None:
        hour, minute = changes.publish_time.split(":")
        section.publish_time = time(int(hour), int(minute))
    if changes.max_stories is not None:
        section.max_stories = changes.max_stories
    if changes.is_paused is not None:
        section.is_paused = changes.is_paused


def _out(section: Section) -> SectionOut:
    return SectionOut(
        id=section.id,
        slug=section.slug,
        name=section.name,
        scope=section.scope,
        publish_time=section.publish_time.strftime("%H:%M"),
        max_stories=section.max_stories,
        is_paused=section.is_paused,
    )


def _free_slug(db: Db, name: str) -> str:
    """Mã chưa dùng, suy từ tên: "Thời sự" thành "thoi-su", trùng thì thêm "-2", "-3"…"""
    ascii_name = unicodedata.normalize("NFKD", name.replace("đ", "d").replace("Đ", "D"))
    base = re.sub(r"[^a-z0-9]+", "-", ascii_name.encode("ascii", "ignore").decode().lower())
    base = base.strip("-") or "chuyen-muc"
    taken = set(db.scalars(select(Section.slug).where(Section.slug.startswith(base))))
    slug, number = base, 1
    while slug in taken:
        number += 1
        slug = f"{base}-{number}"
    return slug
