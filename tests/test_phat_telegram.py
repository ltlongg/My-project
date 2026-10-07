"""Bộ phát Telegram, test bằng phản hồi mẫu theo tài liệu Bot API; không gọi mạng."""

import json
from pathlib import Path

import httpx
import pytest

from bantin.phat_hanh import NoiDungBanTin, NoiDungTin
from bantin.phat_hanh.telegram import LoiPhatTelegram, PhatTelegram
from tests.conftest import luc

DU_LIEU = Path(__file__).parent / "du_lieu"
TOKEN = "123456:ABC-DEF"
MA_TRO_CHUYEN = "-1001234567890"


class TelegramGia:
    """Đứng thay api.telegram.org: ghi lại mọi lời gọi và trả về phản hồi mẫu."""

    def __init__(self, file_phan_hoi: str = "telegram_send_message_ok.json") -> None:
        self.loi_goi: list[tuple[str, dict[str, object]]] = []
        self._ma, self._noi_dung = 200, (DU_LIEU / file_phan_hoi).read_bytes()
        self.client = httpx.Client(transport=httpx.MockTransport(self._tra_loi))

    def tra_ve(self, ma: int, file_phan_hoi: str) -> None:
        self._ma, self._noi_dung = ma, (DU_LIEU / file_phan_hoi).read_bytes()

    def _tra_loi(self, yeu_cau: httpx.Request) -> httpx.Response:
        self.loi_goi.append((str(yeu_cau.url), json.loads(yeu_cau.content)))
        return httpx.Response(
            self._ma, content=self._noi_dung, headers={"content-type": "application/json"}
        )


def test_gui_ban_tin_thanh_mot_tin_nhan_gom_ten_chuyen_muc_ngay_va_cac_tieu_de_kem_link() -> None:
    telegram = TelegramGia()
    ban_tin = NoiDungBanTin(
        chuyen_muc="Công nghệ",
        thoi_diem=luc(7, 8),
        tin=(
            NoiDungTin('AT&T <mua> lại "X"', "https://bao.example/a?x=1&y=2"),
            NoiDungTin("Bài B", "https://bao.example/b"),
        ),
    )

    PhatTelegram(telegram.client, TOKEN).phat(MA_TRO_CHUYEN, ban_tin)

    assert telegram.loi_goi == [
        (
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            {
                "chat_id": MA_TRO_CHUYEN,
                "text": (
                    "<b>Bản tin Công nghệ</b> · 07/10/2026\n"
                    "\n"
                    '1. <a href="https://bao.example/a?x=1&amp;y=2">'
                    "AT&amp;T &lt;mua&gt; lại &quot;X&quot;</a>\n"
                    "\n"
                    '2. <a href="https://bao.example/b">Bài B</a>'
                ),
                "parse_mode": "HTML",
                "link_preview_options": {"is_disabled": True},
            },
        )
    ]


def test_ban_tin_dai_duoc_chia_thanh_nhieu_tin_nhan_trong_gioi_han_4096_ky_tu() -> None:
    telegram = TelegramGia()
    ban_tin = NoiDungBanTin(
        chuyen_muc="Công nghệ",
        thoi_diem=luc(7, 8),
        # Hai Tin liền nhau vừa 4096 nếu đếm theo ký tự, nhưng vượt nếu đếm theo UTF-16.
        tin=tuple(
            NoiDungTin(f"{so}" + "😀" * 299, f"https://bao.example/{so}/" + "a" * 1680)
            for so in range(1, 8)
        ),
    )

    PhatTelegram(telegram.client, TOKEN).phat(MA_TRO_CHUYEN, ban_tin)

    van_ban = [str(than["text"]) for _, than in telegram.loi_goi]
    assert len(van_ban) > 1
    # Telegram đếm theo đơn vị UTF-16, nên một emoji tính là hai.
    assert all(len(doan.encode("utf-16-le")) // 2 <= 4096 for doan in van_ban)
    assert van_ban[0].startswith("<b>Bản tin Công nghệ</b>")
    ca_ban_tin = "\n".join(van_ban)
    vi_tri = [ca_ban_tin.index(f"https://bao.example/{so}/") for so in range(1, 8)]
    assert vi_tri == sorted(vi_tri)


@pytest.mark.parametrize(
    ("ma", "file_phan_hoi", "loi_mong_doi"),
    [
        (
            403,
            "telegram_bot_bi_da_khoi_nhom.json",
            "Telegram từ chối: Forbidden: bot was kicked from the supergroup chat",
        ),
        (400, "telegram_khong_thay_nhom.json", "Telegram từ chối: Bad Request: chat not found"),
        (
            429,
            "telegram_qua_nhieu_loi_goi.json",
            "Telegram từ chối: Too Many Requests: retry after 35",
        ),
    ],
)
def test_telegram_tu_choi_thi_bao_loi_kem_li_do(
    ma: int, file_phan_hoi: str, loi_mong_doi: str
) -> None:
    telegram = TelegramGia()
    telegram.tra_ve(ma, file_phan_hoi)
    ban_tin = NoiDungBanTin("Công nghệ", luc(7, 8), (NoiDungTin("Bài A", "https://bao.example/a"),))

    with pytest.raises(LoiPhatTelegram) as loi:
        PhatTelegram(telegram.client, TOKEN).phat(MA_TRO_CHUYEN, ban_tin)

    assert str(loi.value) == loi_mong_doi


def test_loi_ket_noi_khong_lam_lo_token_cua_bot() -> None:
    def mat_mang(yeu_cau: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"không tới được {yeu_cau.url}", request=yeu_cau)

    client = httpx.Client(transport=httpx.MockTransport(mat_mang))
    ban_tin = NoiDungBanTin("Công nghệ", luc(7, 8), (NoiDungTin("Bài A", "https://bao.example/a"),))

    with pytest.raises(LoiPhatTelegram) as loi:
        PhatTelegram(client, TOKEN).phat(MA_TRO_CHUYEN, ban_tin)

    assert str(loi.value) == "Không kết nối được tới Telegram (ConnectError)"
    assert loi.value.__cause__ is None
