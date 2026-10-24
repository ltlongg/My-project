"""Phát hành: mỗi loại Kênh đăng là một bộ phát cùng giao diện."""

from collections.abc import Callable
from dataclasses import dataclass, field
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
    # Ảnh JPEG đi kèm Tin: ảnh chụp hay ảnh đại diện của Bài gốc chính; không có thì để trống.
    image: bytes | None = field(default=None, repr=False)

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
    def publish(
        self,
        address: str,
        bulletin: BulletinContent,
        *,
        skip: int = 0,
        on_sent: Callable[[], None] = lambda: None,
    ) -> None:
        """Phát `bulletin` tới Kênh đăng ở `address`. Ném lỗi khi không phát được.

        Bộ phát gửi Bản tin thành một hay nhiều phần theo thứ tự, luôn như nhau với cùng một Bản
        tin, ví dụ mỗi Tin một tin nhắn. Nó gọi `on_sent` ngay sau mỗi phần tới nơi, và bỏ qua
        `skip` phần đầu đã tới nơi ở lần phát trước, để phát tiếp sau khi hỏng giữa chừng không gửi
        lại phần nào.
        """
        ...

    def send_test(self, address: str, text: str) -> None:
        """Gửi một tin nhắn chữ thuần tới Kênh đăng ở `address`, để chủ hệ thống biết bot đã có
        quyền đăng ở đó. Ném lỗi khi không gửi được."""
        ...
