"""Hai bộ tìm kiếm, test bằng phản hồi đã ghi lại từ Tavily và Brave; không gọi mạng."""

import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from bulletin.search import BoTimKiem, LoiTimKiem
from bulletin.search.brave import TimKiemBrave
from bulletin.search.tavily import TimKiemTavily

DU_LIEU = Path(__file__).parent / "fixtures"
KHOA = "khoa-bi-mat"
TRUY_VAN = "pin thể rắn mật độ năng lượng"

TaoBoTimKiem = Callable[[httpx.Client, str], BoTimKiem]


class DichVuGia:
    """Đứng thay dịch vụ tìm kiếm: ghi lại lời gọi và trả về phản hồi mẫu."""

    def __init__(self, ma: int, file_phan_hoi: str) -> None:
        self.yeu_cau: list[httpx.Request] = []
        self._ma, self._noi_dung = ma, (DU_LIEU / file_phan_hoi).read_bytes()
        self.client = httpx.Client(transport=httpx.MockTransport(self._tra_loi))

    def _tra_loi(self, yeu_cau: httpx.Request) -> httpx.Response:
        self.yeu_cau.append(yeu_cau)
        return httpx.Response(
            self._ma, content=self._noi_dung, headers={"content-type": "application/json"}
        )


def test_tavily_tra_ve_tieu_de_dia_chi_va_trich_doan() -> None:
    dich_vu = DichVuGia(200, "tavily_search_ok.json")

    ket_qua = TimKiemTavily(dich_vu.client, KHOA).tim(TRUY_VAN)

    [yeu_cau] = dich_vu.yeu_cau
    assert str(yeu_cau.url) == "https://api.tavily.com/search"
    assert yeu_cau.headers["authorization"] == f"Bearer {KHOA}"
    assert json.loads(yeu_cau.content)["query"] == TRUY_VAN
    assert len(ket_qua) == 3
    assert ket_qua[0].tieu_de == "Pin Lithium có thể đạt mật độ năng lượng 700 Wh/kg nhờ ..."
    assert ket_qua[0].dia_chi.startswith("https://vov.vn/the-gioi/pin-lithium-co-the-dat")
    assert ket_qua[0].trich_doan.startswith("Pin Lithium có thể đạt mật độ năng lượng 700 Wh/kg")


def test_brave_tra_ve_tieu_de_dia_chi_va_trich_doan_da_bo_the_html() -> None:
    dich_vu = DichVuGia(200, "brave_search_ok.json")

    ket_qua = TimKiemBrave(dich_vu.client, KHOA).tim(TRUY_VAN)

    [yeu_cau] = dich_vu.yeu_cau
    assert yeu_cau.url.host == "api.search.brave.com"
    assert yeu_cau.url.params["q"] == TRUY_VAN
    assert yeu_cau.headers["x-subscription-token"] == KHOA
    assert len(ket_qua) == 3
    assert ket_qua[0].tieu_de == "Pin thể rắn là gì? Khái niệm và ưu điểm của pin thể rắn | VinFast"
    assert ket_qua[0].dia_chi == (
        "https://vinfastauto.com/vn_vi/pin-the-ran-la-gi-khai-niem-va-uu-diem-cua-pin-the-ran"
    )
    # Brave bọc từ khớp trong thẻ <strong>.
    assert "gấp 2.5 lần pin Lithium-ion" in ket_qua[0].trich_doan
    assert "<" not in ket_qua[0].trich_doan


@pytest.mark.parametrize(
    ("tao", "ma", "file_phan_hoi", "loi_mong_doi"),
    [
        (
            TimKiemTavily,
            401,
            "tavily_sai_khoa.json",
            "Tavily từ chối: Unauthorized: missing or invalid API key.",
        ),
        (
            TimKiemBrave,
            422,
            "brave_sai_khoa.json",
            "Brave từ chối: The provided subscription token is invalid.",
        ),
    ],
)
def test_dich_vu_tu_choi_thi_bao_loi_kem_li_do(
    tao: TaoBoTimKiem, ma: int, file_phan_hoi: str, loi_mong_doi: str
) -> None:
    dich_vu = DichVuGia(ma, file_phan_hoi)

    with pytest.raises(LoiTimKiem) as loi:
        tao(dich_vu.client, KHOA).tim(TRUY_VAN)

    assert str(loi.value) == loi_mong_doi


@pytest.mark.parametrize(
    ("tao", "loi_mong_doi"),
    [
        (TimKiemTavily, "Không kết nối được tới Tavily (ConnectError)"),
        (TimKiemBrave, "Không kết nối được tới Brave (ConnectError)"),
    ],
)
def test_loi_ket_noi_khong_lam_lo_khoa(tao: TaoBoTimKiem, loi_mong_doi: str) -> None:
    def mat_mang(yeu_cau: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"không tới được {yeu_cau.url} với {yeu_cau.headers}")

    client = httpx.Client(transport=httpx.MockTransport(mat_mang))

    with pytest.raises(LoiTimKiem) as loi:
        tao(client, KHOA).tim(TRUY_VAN)

    assert str(loi.value) == loi_mong_doi
    assert loi.value.__cause__ is None
