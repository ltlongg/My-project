"""Những thứ mọi đường dẫn của API dùng chung."""

from collections.abc import Callable, Iterator
from datetime import datetime
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session


def _session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


def _clock(request: Request) -> Callable[[], datetime]:
    clock: Callable[[], datetime] = request.app.state.clock
    return clock


# Một phiên làm việc với cơ sở dữ liệu cho mỗi lời gọi; đường dẫn tự commit.
Db = Annotated[Session, Depends(_session)]
Clock = Annotated[Callable[[], datetime], Depends(_clock)]


class Invalid(Exception):
    """Dữ liệu gửi lên chưa hợp lệ theo cách chỉ đường dẫn biết, như một địa chỉ đã có: trả 422
    với một lời nhắn tiếng Việt cho mỗi trường, như lỗi kiểm tra dữ liệu thường."""

    def __init__(self, **fields: str) -> None:
        super().__init__(fields)
        self.fields = fields


def clean_text(value: str, max_length: int) -> str:
    """Chữ đã bỏ khoảng trắng hai đầu; trống hoặc dài quá thì ném ValueError kèm lời nhắn."""
    value = value.strip()
    if not value:
        raise ValueError("Cần điền")
    if len(value) > max_length:
        raise ValueError(f"Dài quá {max_length} ký tự")
    return value
