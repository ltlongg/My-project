"""Vector nhúng: biến văn bản thành vector để so độ giống nghĩa khi gom Tin."""

from collections.abc import Sequence
from typing import Protocol


class BoNhung(Protocol):
    # Tên model nhúng. Vector của hai model khác nhau không so được với nhau.
    mo_hinh: str

    def nhung(self, van_ban: Sequence[str]) -> list[list[float]]:
        """Trả về một vector cho mỗi văn bản, theo đúng thứ tự. Ném lỗi khi không nhúng được."""
        ...


class LoiNhung(Exception):
    """Dịch vụ nhúng từ chối hoặc không tới được; thông điệp không chứa khoá."""
