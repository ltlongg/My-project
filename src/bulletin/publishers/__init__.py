"""Phát hành: mỗi loại Kênh đăng là một bộ phát cùng giao diện."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

# Giới hạn chú thích ảnh của Telegram, là giới hạn chặt nhất trong các Kênh đăng. Nội dung Tin
# được viết một lần cho mọi Kênh đăng nên Biên tập viết trong giới hạn này.
DO_DAI_TIN_TOI_DA = 1024
# Nhãn đứng trước tiêu đề của Tin có diễn biến mới so với một Tin đã phát.
NHAN_CAP_NHAT = "Cập nhật"


def do_dai(van_ban: str) -> int:
    """Độ dài tính theo đơn vị UTF-16, là cách Telegram đếm: một emoji tính là hai."""
    return len(van_ban.encode("utf-16-le")) // 2


@dataclass(frozen=True)
class NoiDungTin:
    tieu_de: str
    tom_tat: str
    dia_chi: str
    # Tin "Cập nhật": có diễn biến mới so với một Tin đã phát.
    cap_nhat: bool = False

    @property
    def tieu_de_kem_nhan(self) -> str:
        return f"{NHAN_CAP_NHAT}: {self.tieu_de}" if self.cap_nhat else self.tieu_de

    @property
    def do_dai(self) -> int:
        """Độ dài khi phát: tiêu đề kèm nhãn, tóm tắt và link, mỗi phần một đoạn."""
        return do_dai("\n\n".join((self.tieu_de_kem_nhan, self.tom_tat, self.dia_chi)))


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
