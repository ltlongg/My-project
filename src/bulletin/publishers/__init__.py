"""Phát hành: mỗi loại Kênh đăng là một bộ phát cùng giao diện."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class NoiDungTin:
    tieu_de: str
    dia_chi: str


@dataclass(frozen=True)
class NoiDungBanTin:
    """Bản tin đúng như sẽ gửi đi; mỗi bộ phát chỉ đổi định dạng."""

    chuyen_muc: str
    thoi_diem: datetime
    tin: tuple[NoiDungTin, ...]


class BoPhat(Protocol):
    def phat(self, dia_chi: str, ban_tin: NoiDungBanTin) -> None:
        """Phát `ban_tin` tới Kênh đăng ở `dia_chi`. Ném lỗi khi không phát được."""
        ...
