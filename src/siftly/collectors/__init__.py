"""Thu thập: mỗi loại Nguồn là một bộ thu thập cùng giao diện."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class NewArticle:
    """Một Bài gốc vừa lấy về từ Nguồn, chưa lưu."""

    url: str
    title: str
    # Nguồn không cho biết thời điểm xuất bản thì để trống.
    published_at: datetime | None = None
    # Đoạn mô tả ngắn Nguồn kèm theo, dạng chữ thuần; không có thì để trống.
    description: str | None = None


class Collector(Protocol):
    def collect(self, url: str, since: datetime) -> Sequence[NewArticle]:
        """Trả về các Bài gốc mới của Nguồn ở `url` kể từ `since`.

        Ném lỗi khi không lấy được; nơi gọi chịu trách nhiệm ghi lại và đi tiếp.
        """
        ...
