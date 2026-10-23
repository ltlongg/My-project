"""Tìm kiếm web: mỗi dịch vụ tìm kiếm là một bộ tìm kiếm cùng giao diện."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

SO_KET_QUA = 5


@dataclass(frozen=True)
class KetQuaTimKiem:
    tieu_de: str
    dia_chi: str
    trich_doan: str


class BoTimKiem(Protocol):
    def tim(self, truy_van: str) -> Sequence[KetQuaTimKiem]:
        """Trả về vài kết quả đầu cho `truy_van`. Ném lỗi khi không tìm được."""
        ...


class LoiTimKiem(Exception):
    """Dịch vụ tìm kiếm từ chối hoặc không tới được; thông điệp không chứa khoá."""
