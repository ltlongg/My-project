"""Bộ nhúng qua endpoint tương thích OpenAI, test bằng phản hồi đã ghi lại từ Text Embeddings
Inference chạy BAAI/bge-m3; không gọi mạng."""

import json
from pathlib import Path

import httpx
import pytest

from bulletin.embeddings import LoiNhung
from bulletin.embeddings.endpoint import SO_VAN_BAN_MOI_LAN, NhungQuaEndpoint

DU_LIEU = Path(__file__).parent / "fixtures"
DIA_CHI = "http://127.0.0.1:54321/v1"
MO_HINH = "BAAI/bge-m3"
# Hai văn bản của phản hồi mẫu: một sự kiện, hai ngôn ngữ.
VAN_BAN = [
    "Amazon tài trợ nhà máy điện hạt nhân ở Indiana",
    "Amazon is funding a new nuclear plant in Indiana",
]


class DichVuGia:
    """Đứng thay dịch vụ nhúng: ghi lại lời gọi và trả về phản hồi mẫu."""

    def __init__(self, ma: int, file_phan_hoi: str) -> None:
        self.yeu_cau: list[httpx.Request] = []
        self._ma, self._noi_dung = ma, (DU_LIEU / file_phan_hoi).read_bytes()
        self.client = httpx.Client(transport=httpx.MockTransport(self._tra_loi))

    def _tra_loi(self, yeu_cau: httpx.Request) -> httpx.Response:
        self.yeu_cau.append(yeu_cau)
        return httpx.Response(
            self._ma, content=self._noi_dung, headers={"content-type": "application/json"}
        )


def test_moi_van_ban_mot_vector_theo_dung_thu_tu() -> None:
    dich_vu = DichVuGia(200, "tei_embeddings_ok.json")

    vector = NhungQuaEndpoint(dich_vu.client, DIA_CHI, MO_HINH).nhung(VAN_BAN)

    [yeu_cau] = dich_vu.yeu_cau
    assert str(yeu_cau.url) == f"{DIA_CHI}/embeddings"
    assert json.loads(yeu_cau.content) == {"model": MO_HINH, "input": VAN_BAN}
    assert "authorization" not in yeu_cau.headers
    assert [len(v) for v in vector] == [1024, 1024]
    # bge-m3 trả vector đã chuẩn hoá; hai câu cùng nghĩa khác ngôn ngữ thì rất giống nhau.
    do_giong = sum(a * b for a, b in zip(*vector, strict=True))
    assert do_giong > 0.85


def test_khoa_duoc_gui_khi_co() -> None:
    dich_vu = DichVuGia(200, "tei_embeddings_ok.json")

    NhungQuaEndpoint(dich_vu.client, DIA_CHI + "/", MO_HINH, "khoa-bi-mat").nhung(VAN_BAN)

    [yeu_cau] = dich_vu.yeu_cau
    assert str(yeu_cau.url) == f"{DIA_CHI}/embeddings"
    assert yeu_cau.headers["authorization"] == "Bearer khoa-bi-mat"


def test_nhieu_van_ban_duoc_chia_thanh_nhieu_lan_goi() -> None:
    du_lieu = json.loads((DU_LIEU / "tei_embeddings_ok.json").read_bytes())
    so_van_ban: list[int] = []

    def tra_loi(yeu_cau: httpx.Request) -> httpx.Response:
        dau_vao = json.loads(yeu_cau.content)["input"]
        so_van_ban.append(len(dau_vao))
        vector = du_lieu["data"][0]["embedding"]
        return httpx.Response(
            200,
            json={"data": [{"index": i, "embedding": vector} for i in range(len(dau_vao))]},
        )

    client = httpx.Client(transport=httpx.MockTransport(tra_loi))
    vector = NhungQuaEndpoint(client, DIA_CHI, MO_HINH).nhung(["một câu"] * 70)

    assert len(vector) == 70
    assert so_van_ban == [SO_VAN_BAN_MOI_LAN, SO_VAN_BAN_MOI_LAN, 70 - 2 * SO_VAN_BAN_MOI_LAN]


def test_dich_vu_tu_choi_thi_bao_loi_kem_loi_nhan_cua_dich_vu() -> None:
    dich_vu = DichVuGia(400, "tei_embeddings_loi.json")

    with pytest.raises(LoiNhung, match="`inputs` cannot be empty"):
        NhungQuaEndpoint(dich_vu.client, DIA_CHI, MO_HINH).nhung(VAN_BAN)


def test_so_vector_khong_khop_so_van_ban_thi_bao_loi() -> None:
    dich_vu = DichVuGia(200, "tei_embeddings_ok.json")

    with pytest.raises(LoiNhung, match="2 vector cho 3 văn bản"):
        NhungQuaEndpoint(dich_vu.client, DIA_CHI, MO_HINH).nhung([*VAN_BAN, "câu thứ ba"])


def test_khong_ket_noi_duoc_thi_bao_loi_khong_lo_khoa() -> None:
    def tu_choi(yeu_cau: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"không tới được {yeu_cau.headers.get('authorization')}")

    client = httpx.Client(transport=httpx.MockTransport(tu_choi))

    with pytest.raises(LoiNhung, match="Không kết nối được tới dịch vụ nhúng") as loi:
        NhungQuaEndpoint(client, DIA_CHI, MO_HINH, "khoa-bi-mat").nhung(VAN_BAN)
    assert "khoa-bi-mat" not in str(loi.value)
