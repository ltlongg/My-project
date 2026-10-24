"""Chụp ảnh: nhận địa chỉ Bài gốc chính, trả về ảnh đi kèm Tin khi phát."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class ImageKind(StrEnum):
    # Ảnh chụp trang, thấy tiêu đề và phần đầu bài.
    SCREENSHOT = "screenshot"
    # Ảnh đại diện trang tự khai (og:image), khi không chụp được trang.
    PREVIEW = "preview"
    # Không có ảnh nào dùng được; Tin được phát không ảnh.
    NONE = "none"


@dataclass(frozen=True)
class Capture:
    kind: ImageKind
    # Ảnh JPEG; không có ảnh thì để trống.
    data: bytes | None
    # Vì sao không dùng được từng cách đứng trước, ví dụ vì sao không chụp được trang.
    failures: tuple[str, ...] = ()


class Camera(Protocol):
    def capture(self, url: str) -> Capture:
        """Ảnh cho Bài gốc ở `url`. Không ném lỗi: không có ảnh nào thì trả về loại NONE."""
        ...


class Screenshotter(Protocol):
    def screenshot(self, url: str) -> bytes:
        """Ảnh chụp JPEG của trang ở `url`. Ném lỗi khi không chụp được một ảnh dùng được."""
        ...
