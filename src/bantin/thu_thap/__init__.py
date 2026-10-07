"""Thu thập: mỗi loại Nguồn là một bộ thu thập cùng giao diện."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class BaiGocMoi:
    """Một Bài gốc vừa lấy về từ Nguồn, chưa lưu."""

    dia_chi: str
    tieu_de: str
    # Nguồn không cho biết thời điểm xuất bản thì để trống.
    xuat_ban_luc: datetime | None = None


class BoThuThap(Protocol):
    def thu_thap(self, dia_chi: str, tu_moc: datetime) -> Sequence[BaiGocMoi]:
        """Trả về các Bài gốc mới của Nguồn ở `dia_chi` kể từ `tu_moc`.

        Ném lỗi khi không lấy được; nơi gọi chịu trách nhiệm ghi lại và đi tiếp.
        """
        ...
