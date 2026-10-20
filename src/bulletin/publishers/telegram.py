"""Bộ phát cho Kênh đăng loại Telegram. Địa chỉ của Kênh đăng là mã cuộc trò chuyện."""

from html import escape
from zoneinfo import ZoneInfo

import httpx

from bulletin.publishers import NoiDungBanTin, do_dai

GIO_VIET_NAM = ZoneInfo("Asia/Ho_Chi_Minh")
# Giới hạn của Telegram cho một tin nhắn chữ.
GIOI_HAN_TIN_NHAN = 4096
TIEU_DE_TOI_DA = 300


class LoiPhatTelegram(Exception):
    pass


class PhatTelegram:
    def __init__(self, client: httpx.Client, token: str) -> None:
        self._client = client
        self._token = token

    def phat(self, dia_chi: str, ban_tin: NoiDungBanTin) -> None:
        for van_ban in dung_tin_nhan(ban_tin):
            self._gui(dia_chi, van_ban)

    def _gui(self, ma_tro_chuyen: str, van_ban: str) -> None:
        try:
            phan_hoi = self._client.post(
                f"https://api.telegram.org/bot{self._token}/sendMessage",
                json={
                    "chat_id": ma_tro_chuyen,
                    "text": van_ban,
                    "parse_mode": "HTML",
                    "link_preview_options": {"is_disabled": True},
                },
            )
        except httpx.HTTPError as loi:
            # Không nối lỗi gốc vào: nó mang theo địa chỉ có chứa token của bot.
            raise LoiPhatTelegram(
                f"Không kết nối được tới Telegram ({type(loi).__name__})"
            ) from None

        try:
            ket_qua = phan_hoi.json()
        except ValueError:
            ket_qua = None
        if not isinstance(ket_qua, dict) or not ket_qua.get("ok"):
            mo_ta = isinstance(ket_qua, dict) and ket_qua.get("description")
            raise LoiPhatTelegram(f"Telegram từ chối: {mo_ta or f'mã {phan_hoi.status_code}'}")


def dung_tin_nhan(ban_tin: NoiDungBanTin) -> list[str]:
    """Dựng Bản tin thành các tin nhắn HTML, mỗi tin nhắn trong giới hạn của Telegram."""
    ngay = ban_tin.thoi_diem.astimezone(GIO_VIET_NAM).strftime("%d/%m/%Y")
    cac_doan = [f"<b>Bản tin {escape(ban_tin.chuyen_muc)}</b> · {ngay}"]
    for thu_tu, tin in enumerate(ban_tin.tin, start=1):
        tieu_de = tin.tieu_de_kem_nhan
        if len(tieu_de) > TIEU_DE_TOI_DA:
            tieu_de = tieu_de[: TIEU_DE_TOI_DA - 1] + "…"
        cac_doan.append(
            f'{thu_tu}. <a href="{escape(tin.dia_chi)}"><b>{escape(tieu_de)}</b></a>\n'
            f"{escape(tin.tom_tat)}"
        )

    tin_nhan: list[str] = []
    for doan in cac_doan:
        if tin_nhan and do_dai(tin_nhan[-1]) + 2 + do_dai(doan) <= GIOI_HAN_TIN_NHAN:
            tin_nhan[-1] += "\n\n" + doan
        else:
            tin_nhan.append(doan)
    return tin_nhan
