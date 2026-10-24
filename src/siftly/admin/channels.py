"""Thiết lập Kênh đăng: thêm, sửa, tắt và bật lại, gắn vào Chuyên mục, và gửi tin nhắn thử.

Không xoá Kênh đăng: các lần phát đã qua vẫn ghi là tới Kênh đăng đó. Tắt là cách ngừng gửi Bản
tin tới một Kênh đăng.
"""

import logging
from collections.abc import Mapping

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import select

from siftly.admin import sections
from siftly.admin.deps import Db, Invalid, clean_text
from siftly.admin.kinds import CHANNEL_KINDS, KindOut, kinds_out
from siftly.models import Channel, ChannelKind
from siftly.publishers import Publisher

log = logging.getLogger(__name__)

MAX_NAME_LENGTH = 80
MAX_ADDRESS_LENGTH = 200
TEST_MESSAGE = "Tin nhắn thử từ trang quản lí Siftly: Bản tin sẽ được gửi tới đây."

router = APIRouter(prefix="/channels")


class ChannelOut(BaseModel):
    id: int
    kind: ChannelKind
    name: str
    address: str
    is_enabled: bool
    section_ids: list[int]


class ChannelChanges(BaseModel):
    """Những gì sửa được; trường không gửi thì giữ nguyên. Loại Kênh đăng không đổi được."""

    name: str | None = None
    address: str | None = None
    section_ids: list[int] | None = None
    is_enabled: bool | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        return None if value is None else clean_text(value, MAX_NAME_LENGTH)

    @field_validator("address")
    @classmethod
    def _address(cls, value: str | None) -> str | None:
        return None if value is None else clean_text(value, MAX_ADDRESS_LENGTH)


class NewChannel(ChannelChanges):
    kind: ChannelKind
    name: str
    address: str
    section_ids: list[int] = []


class Trial(BaseModel):
    """Một Kênh đăng, đã lưu hay chưa, để gửi tin nhắn thử."""

    kind: ChannelKind
    address: str

    @field_validator("address")
    @classmethod
    def _address(cls, value: str) -> str:
        return clean_text(value, MAX_ADDRESS_LENGTH)


class TrialResult(BaseModel):
    # Lời nhắn khi không gửi được; gửi được thì để trống.
    error: str | None


@router.get("/kinds")
def list_kinds() -> list[KindOut]:
    return kinds_out(CHANNEL_KINDS)


@router.post("/test")
def try_channel(trial: Trial, request: Request) -> TrialResult:
    """Gửi một tin nhắn thử tới Kênh đăng, để biết bot đã có quyền đăng ở đó."""
    if problem := CHANNEL_KINDS[trial.kind].check(trial.address):
        raise Invalid(address=problem)
    publishers: Mapping[ChannelKind, Publisher] = request.app.state.publishers
    publisher = publishers.get(trial.kind)
    if publisher is None:
        label = CHANNEL_KINDS[trial.kind].label
        return TrialResult(error=f"Máy chủ chưa có bộ phát cho Kênh đăng loại {label}")
    try:
        publisher.send_test(trial.address, TEST_MESSAGE)
    except Exception as error:
        log.info("Tin nhắn thử tới %s không gửi được", trial.address, exc_info=True)
        return TrialResult(error=(str(error).splitlines() or [type(error).__name__])[0])
    return TrialResult(error=None)


@router.get("")
def list_channels(db: Db) -> list[ChannelOut]:
    return [_out(channel) for channel in db.scalars(select(Channel).order_by(Channel.id))]


@router.post("", status_code=201)
def create_channel(new: NewChannel, db: Db) -> ChannelOut:
    channel = Channel(kind=new.kind)
    _apply(db, channel, new)
    db.add(channel)
    db.commit()
    return _out(channel)


@router.get("/{channel_id}")
def get_channel(channel_id: int, db: Db) -> ChannelOut:
    return _out(_find(db, channel_id))


@router.patch("/{channel_id}")
def update_channel(channel_id: int, changes: ChannelChanges, db: Db) -> ChannelOut:
    channel = _find(db, channel_id)
    _apply(db, channel, changes)
    db.commit()
    return _out(channel)


def _find(db: Db, channel_id: int) -> Channel:
    channel = db.get(Channel, channel_id)
    if channel is None:
        raise HTTPException(404, "Không có Kênh đăng này")
    return channel


def _apply(db: Db, channel: Channel, changes: ChannelChanges) -> None:
    """Ghi thay đổi vào `channel`; ném Invalid trước khi ghi gì nếu có trường chưa hợp lệ."""
    if changes.address is not None:
        if problem := CHANNEL_KINDS[channel.kind].check(changes.address):
            raise Invalid(address=problem)
        same = db.scalar(
            select(Channel).where(
                Channel.kind == channel.kind,
                Channel.address == changes.address,
                Channel.id != channel.id,
            )
        )
        if same is not None:
            raise Invalid(address=f"Đã có Kênh đăng {same.name} với mã này")
    attached = None if changes.section_ids is None else sections.find_all(db, changes.section_ids)
    if changes.name is not None:
        channel.name = changes.name
    if changes.address is not None:
        channel.address = changes.address
    if attached is not None:
        channel.sections = attached
    if changes.is_enabled is not None:
        channel.is_enabled = changes.is_enabled


def _out(channel: Channel) -> ChannelOut:
    return ChannelOut(
        id=channel.id,
        kind=channel.kind,
        name=channel.name,
        address=channel.address,
        is_enabled=channel.is_enabled,
        section_ids=[section.id for section in channel.sections],
    )
