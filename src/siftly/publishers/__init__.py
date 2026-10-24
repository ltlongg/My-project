"""Phát hành: mỗi loại Kênh đăng là một bộ phát cùng giao diện."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

# Giới hạn chú thích ảnh của Telegram, là giới hạn chặt nhất trong các Kênh đăng. Nội dung Tin
# được viết một lần cho mọi Kênh đăng nên Biên tập viết trong giới hạn này.
MAX_STORY_LENGTH = 1024
# Nhãn đứng trước tiêu đề của Tin có diễn biến mới so với một Tin đã phát.
UPDATE_LABEL = "Cập nhật"


def text_length(text: str) -> int:
    """Độ dài tính theo đơn vị UTF-16, là cách Telegram đếm: một emoji tính là hai."""
    return len(text.encode("utf-16-le")) // 2


@dataclass(frozen=True)
class StoryContent:
    title: str
    summary: str
    url: str
    # Tin "Cập nhật": có diễn biến mới so với một Tin đã phát.
    is_update: bool = False

    @property
    def labeled_title(self) -> str:
        return f"{UPDATE_LABEL}: {self.title}" if self.is_update else self.title

    @property
    def length(self) -> int:
        """Độ dài khi phát: tiêu đề kèm nhãn, tóm tắt và link, mỗi phần một đoạn."""
        return text_length("\n\n".join((self.labeled_title, self.summary, self.url)))


@dataclass(frozen=True)
class BulletinContent:
    """Bản tin đúng như sẽ gửi đi; mỗi bộ phát chỉ đổi định dạng."""

    section: str
    run_at: datetime
    stories: tuple[StoryContent, ...]


class Publisher(Protocol):
    def publish(self, address: str, bulletin: BulletinContent) -> None:
        """Phát `bulletin` tới Kênh đăng ở `address`. Ném lỗi khi không phát được."""
        ...
