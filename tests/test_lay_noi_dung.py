"""Bộ lấy nội dung bài báo, test bằng một trang đã ghi lại; không gọi mạng."""

from pathlib import Path

import httpx
import pytest

from bulletin.extractors.bai_bao import LayBaiBao, LoiLayNoiDung

DU_LIEU = Path(__file__).parent / "fixtures"
BAI_BAO = "https://vnexpress.net/honor-600s-5g-dien-thoai-sieu-ben-pin-8-100-mah-5130044.html"


def client_tra_ve(ma: int, noi_dung: bytes) -> httpx.Client:
    def tra_loi(yeu_cau: httpx.Request) -> httpx.Response:
        return httpx.Response(
            ma, content=noi_dung, headers={"content-type": "text/html; charset=UTF-8"}
        )

    return httpx.Client(transport=httpx.MockTransport(tra_loi))


def test_trich_than_bai_cua_mot_bai_bao_va_bo_phan_quanh_trang() -> None:
    client = client_tra_ve(200, (DU_LIEU / "vnexpress_bai_bao.html").read_bytes())

    toan_van = LayBaiBao(client).lay(BAI_BAO)

    assert toan_van.startswith("Honor 600S 5G - điện thoại siêu bền, pin 8.100 mAh")
    assert "Giá khởi điểm của máy là 10,49 triệu đồng cho bản RAM 6 GB" in toan_van
    # Thanh điều hướng, ô bình luận và mã nguồn trang không lọt vào toàn văn.
    assert "Đăng nhập" not in toan_van
    assert "Ý kiến" not in toan_van
    assert "<" not in toan_van


def test_trang_khong_co_than_bai_thi_bao_loi() -> None:
    trang = "<html><body><p>Vui lòng đăng nhập để đọc tiếp.</p></body></html>".encode()

    with pytest.raises(LoiLayNoiDung, match="Không trích được thân bài"):
        LayBaiBao(client_tra_ve(200, trang)).lay(BAI_BAO)


def test_may_chu_tra_ma_loi_thi_bao_loi_kem_ma() -> None:
    with pytest.raises(LoiLayNoiDung, match="trả về mã 403"):
        LayBaiBao(client_tra_ve(403, b"Forbidden")).lay(BAI_BAO)


def test_khong_ket_noi_duoc_thi_bao_loi() -> None:
    def mat_mang(yeu_cau: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("mất mạng", request=yeu_cau)

    client = httpx.Client(transport=httpx.MockTransport(mat_mang))

    with pytest.raises(LoiLayNoiDung, match="Không kết nối được"):
        LayBaiBao(client).lay(BAI_BAO)
