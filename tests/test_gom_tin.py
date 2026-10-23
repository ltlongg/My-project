"""Gom Tin và không phát lại, test tại điểm "Chạy Kỳ" với bộ nhúng giả và LLM theo kịch bản."""

from datetime import datetime

import pytest

from bulletin.collectors import BaiGocMoi
from bulletin.embeddings import LoiNhung
from bulletin.mo_hinh import KetQuaKy
from bulletin.publishers import NoiDungTin
from tests.conftest import TheGioi, TinViet, doc, huong, luc, nop, viet_lai

RSS = "https://bao.example/rss"
RSS_ANH = "https://news.example/rss"
KENH_DANG = "-1001"


def bai(ten: str, tieu_de: str, xuat_ban_luc: datetime, mo_ta: str | None = None) -> BaiGocMoi:
    return BaiGocMoi(f"https://bao.example/{ten}", tieu_de, xuat_ban_luc, mo_ta)


def ba_bai_phu(ngay: int) -> list[BaiGocMoi]:
    """Ba Bài gốc không liên quan gì tới nhau, đủ để Bản tin được phát."""
    return [
        bai(f"phu-{ngay}-{so}", f"Tin phụ {so} ngày {ngay}", luc(ngay, 6, so)) for so in (1, 2, 3)
    ]


def tieu_de(*bai_goc: BaiGocMoi) -> list[TinViet]:
    """Mỗi Bài gốc một Tin, giữ nguyên tiêu đề gốc."""
    return [TinViet(b.dia_chi, b.tieu_de) for b in bai_goc]


def dia_chi(*bai_goc: BaiGocMoi) -> list[str]:
    return [b.dia_chi for b in bai_goc]


def tieu_de_da_phat(the_gioi: TheGioi) -> list[list[str]]:
    return [[tin.tieu_de for tin in ban_tin.tin] for _, ban_tin in the_gioi.kenh_dang.da_nhan]


@pytest.fixture
def cong_nghe(the_gioi: TheGioi) -> TheGioi:
    the_gioi.them_chuyen_muc(
        "cong-nghe", ten="Công nghệ", nguon=[RSS, RSS_ANH], kenh_dang=[KENH_DANG]
    )
    return the_gioi


def test_bai_goc_cung_su_kien_khac_ngon_ngu_thanh_mot_tin_voi_bai_goc_chinh_bien_tap_chon(
    cong_nghe: TheGioi,
) -> None:
    viet = bai("amazon", "Amazon tài trợ nhà máy điện hạt nhân ở Indiana", luc(7, 7, 10))
    anh = BaiGocMoi(
        "https://news.example/amazon-nuclear",
        "Amazon is funding a new nuclear plant in Indiana",
        luc(7, 6, 30),
        "Amazon will fund 12 small modular reactors at a former coal plant.",
    )
    phu = ba_bai_phu(7)
    cong_nghe.nhung.cung_su_kien(viet.tieu_de, anh.tieu_de)
    cong_nghe.nguon.co(RSS, viet, *phu)
    cong_nghe.nguon.co(RSS_ANH, anh)
    # Biên tập chọn bài tiếng Anh, nơi đưa tin đầu tiên, làm Bài gốc chính.
    cong_nghe.llm.se(doc(anh.dia_chi, *dia_chi(*phu)), nop(*tieu_de(anh, *phu)))

    ky = cong_nghe.chay_ky.chay("cong-nghe", luc(7, 8))

    assert ky.ket_qua is KetQuaKy.DA_PHAT
    # Biên tập thấy hai Bài gốc là một ứng viên, bài xuất hiện sớm nhất đứng trước.
    assert ([anh.dia_chi, viet.dia_chi], None) in cong_nghe.llm.ung_vien_da_thay()
    assert len(cong_nghe.llm.ung_vien_da_thay()) == 4
    [(_, ban_tin)] = cong_nghe.kenh_dang.da_nhan
    assert ban_tin.tin[0] == NoiDungTin(
        anh.tieu_de, "Tóm tắt bằng tiếng Việt do Biên tập viết từ toàn văn.", anh.dia_chi
    )
    assert cong_nghe.bai_goc_cua_tin(anh.dia_chi) == [anh.dia_chi, viet.dia_chi]
    # Văn bản được nhúng là tiêu đề kèm mô tả, nếu Nguồn có mô tả.
    assert f"{anh.tieu_de}\n{anh.mo_ta}" in cong_nghe.nhung.da_nhung


def test_hai_su_kien_khac_nhau_cung_chu_de_khong_bi_gom(cong_nghe: TheGioi) -> None:
    f70 = bai("f70", "Samsung ra mắt Galaxy F70 giá dưới 5,5 triệu đồng", luc(7, 7))
    a08 = bai("a08", "Samsung ra mắt bộ đôi Galaxy A08 và A18", luc(7, 7, 5))
    # Độ giống đo được giữa hai bài này trên RSS thật với BAAI/bge-m3 (docs/gom-tin.md).
    cong_nghe.nhung.dat(f70.tieu_de, 1, 0)
    cong_nghe.nhung.dat(a08.tieu_de, *huong(0.74))
    cong_nghe.nguon.co(RSS, f70, a08, *ba_bai_phu(7))

    cong_nghe.chay_ky.chay("cong-nghe", luc(7, 8))

    assert [nhom for nhom, _ in cong_nghe.llm.ung_vien_da_thay()][:2] == [
        [a08.dia_chi],
        [f70.dia_chi],
    ]
    assert tieu_de_da_phat(cong_nghe)[0][:2] == [a08.tieu_de, f70.tieu_de]


def test_a_giong_b_b_giong_c_ma_a_khong_giong_c_thi_khong_gom_ca_ba(cong_nghe: TheGioi) -> None:
    a, b, c = (bai(ten, f"Bài {ten}", luc(7, 7, so)) for so, ten in enumerate("abc"))
    # A và B rất giống nhau, B và C giống nhau, nhưng A với C chỉ giống chừng 0,54.
    cong_nghe.nhung.dat(a.tieu_de, 1, 0)
    cong_nghe.nhung.dat(b.tieu_de, *huong(0.9))
    goc_b, goc_bc = huong(0.9), huong(0.85)
    cong_nghe.nhung.dat(
        c.tieu_de,
        goc_b[0] * goc_bc[0] - goc_b[1] * goc_bc[1],
        goc_b[1] * goc_bc[0] + goc_b[0] * goc_bc[1],
    )
    cong_nghe.nguon.co(RSS, a, b, c)

    cong_nghe.chay_ky.chay("cong-nghe", luc(7, 8))

    assert [nhom for nhom, _ in cong_nghe.llm.ung_vien_da_thay()] == [
        [c.dia_chi],
        [a.dia_chi, b.dia_chi],
    ]


def test_hai_tin_tu_cung_mot_ung_vien_bi_tra_lai_cho_bien_tap(cong_nghe: TheGioi) -> None:
    a1 = bai("a1", "Apple dời lịch giao iPhone Duo sang năm 2027", luc(7, 7))
    a2 = bai("a2", "Khách mua iPhone Duo có thể phải chờ đến Tết để nhận máy", luc(7, 7, 20))
    phu = ba_bai_phu(7)
    cong_nghe.nhung.cung_su_kien(a1.tieu_de, a2.tieu_de)
    cong_nghe.nguon.co(RSS, a1, a2, *phu)
    cong_nghe.llm.se(
        doc(*dia_chi(a1, a2, *phu)), nop(*tieu_de(a1, a2, *phu)), nop(*tieu_de(a1, *phu))
    )

    ky = cong_nghe.chay_ky.chay("cong-nghe", luc(7, 8))

    assert "thuộc cùng một ứng viên" in cong_nghe.llm.van_ban_da_nhan()
    assert ky.ket_qua is KetQuaKy.DA_PHAT
    assert tieu_de_da_phat(cong_nghe) == [[a1.tieu_de, *(p.tieu_de for p in phu)]]


# Một chuyện được phát ở Kỳ ngày 7, rồi một Bài gốc khác về cùng chuyện xuất hiện trước Kỳ ngày 8.
DA_PHAT = bai("duo-1", "Apple dời lịch giao iPhone Duo sang năm 2027", luc(7, 7))
TIN_DA_PHAT = TinViet(
    DA_PHAT.dia_chi,
    "Apple lùi lịch giao iPhone Duo sang 2027",
    "Apple thông báo khách đặt iPhone Duo sẽ nhận máy từ năm 2027.",
)
CUNG_CHUYEN = bai("duo-2", "Apple xác nhận iPhone Duo giao từ tháng 1/2027", luc(8, 7))


def phat_roi_lai_gap(the_gioi: TheGioi) -> list[BaiGocMoi]:
    """Kỳ ngày 7 phát Tin về DA_PHAT; trả về ba Bài gốc phụ của ngày 8."""
    the_gioi.nhung.cung_su_kien(DA_PHAT.tieu_de, CUNG_CHUYEN.tieu_de)
    phu_7, phu_8 = ba_bai_phu(7), ba_bai_phu(8)
    the_gioi.nguon.co(RSS, DA_PHAT, *phu_7)
    the_gioi.llm.se(doc(*dia_chi(DA_PHAT, *phu_7)), nop(TIN_DA_PHAT, *tieu_de(*phu_7)))
    assert the_gioi.chay_ky.chay("cong-nghe", luc(7, 8)).ket_qua is KetQuaKy.DA_PHAT
    the_gioi.nguon.co(RSS, CUNG_CHUYEN, *phu_8)
    return phu_8


def test_ung_vien_trung_tin_da_phat_duoc_danh_dau_va_khong_phat_lai_khi_bien_tap_bo_qua(
    cong_nghe: TheGioi,
) -> None:
    phu_8 = phat_roi_lai_gap(cong_nghe)
    cong_nghe.llm.se(doc(*dia_chi(*phu_8)), nop(*tieu_de(*phu_8)))

    ky = cong_nghe.chay_ky.chay("cong-nghe", luc(8, 8))

    lan_goi_dau_ky_8 = len(cong_nghe.llm.da_nhan) - 2
    assert ([CUNG_CHUYEN.dia_chi], TIN_DA_PHAT.tieu_de) in cong_nghe.llm.ung_vien_da_thay(
        lan_goi_dau_ky_8
    )
    # Biên tập đọc được Tin đã phát nói gì để so xem có gì mới.
    assert TIN_DA_PHAT.tom_tat in cong_nghe.llm.van_ban_da_nhan(lan_goi_dau_ky_8)
    assert ky.ket_qua is KetQuaKy.DA_PHAT
    assert tieu_de_da_phat(cong_nghe)[1] == [p.tieu_de for p in phu_8]


def test_ung_vien_co_dien_bien_moi_duoc_phat_voi_nhan_cap_nhat_va_lien_ket_tin_truoc(
    cong_nghe: TheGioi,
) -> None:
    phu_8 = phat_roi_lai_gap(cong_nghe)
    cap_nhat = TinViet(
        CUNG_CHUYEN.dia_chi,
        "Apple chốt giao iPhone Duo từ tháng 1/2027",
        "Apple xác nhận những chiếc iPhone Duo đầu tiên sẽ tới tay khách từ tháng 1/2027.",
    )
    cong_nghe.llm.se(doc(*dia_chi(CUNG_CHUYEN, *phu_8)), nop(cap_nhat, *tieu_de(*phu_8)))

    cong_nghe.chay_ky.chay("cong-nghe", luc(8, 8))

    [_, (_, ban_tin)] = cong_nghe.kenh_dang.da_nhan
    assert ban_tin.tin[0] == NoiDungTin(
        cap_nhat.tieu_de, cap_nhat.tom_tat, CUNG_CHUYEN.dia_chi, cap_nhat=True
    )
    assert [tin.cap_nhat for tin in ban_tin.tin[1:]] == [False] * 3
    assert cong_nghe.cap_nhat_cua(cap_nhat.tieu_de) == TIN_DA_PHAT.tieu_de
    assert cong_nghe.cap_nhat_cua(phu_8[0].tieu_de) is None


def test_tin_cua_ky_khong_phat_duoc_khong_tinh_la_da_phat(cong_nghe: TheGioi) -> None:
    cong_nghe.nhung.cung_su_kien(DA_PHAT.tieu_de, CUNG_CHUYEN.tieu_de)
    cong_nghe.nguon.co(RSS, DA_PHAT, *ba_bai_phu(7))
    cong_nghe.kenh_dang.hong(KENH_DANG, RuntimeError("bot bị chặn khỏi nhóm"))
    assert cong_nghe.chay_ky.chay("cong-nghe", luc(7, 8)).ket_qua is KetQuaKy.HONG

    cong_nghe.kenh_dang.sua(KENH_DANG)
    cung_chuyen = bai("duo-3", CUNG_CHUYEN.tieu_de, luc(7, 10))
    cong_nghe.nguon.co(RSS, DA_PHAT, cung_chuyen, *ba_bai_phu(7))
    cong_nghe.chay_ky.chay("cong-nghe", luc(7, 12))

    # Bản tin lúc 8:00 không tới ai, nên Bài gốc của nó được xét lại và chuyện vẫn là chuyện mới.
    assert ([DA_PHAT.dia_chi, cung_chuyen.dia_chi], None) in cong_nghe.llm.ung_vien_da_thay(-2)


def test_tin_bi_kiem_chung_bo_khong_tinh_la_da_phat(cong_nghe: TheGioi) -> None:
    cong_nghe.nhung.cung_su_kien(DA_PHAT.tieu_de, CUNG_CHUYEN.tieu_de)
    phu_7 = ba_bai_phu(7)
    cong_nghe.nguon.co(RSS, DA_PHAT, *phu_7)
    cong_nghe.kiem_chung.bat("2027", "Bài gốc không nói năm giao máy.")
    cong_nghe.llm.se(
        doc(*dia_chi(DA_PHAT, *phu_7)),
        nop(TIN_DA_PHAT, *tieu_de(*phu_7)),
        viet_lai(TIN_DA_PHAT),
        viet_lai(TIN_DA_PHAT),
    )
    assert cong_nghe.chay_ky.chay("cong-nghe", luc(7, 8)).ket_qua is KetQuaKy.DA_PHAT
    assert [tin[1] for tin in cong_nghe.tin_bi_bo()] == [DA_PHAT.dia_chi]

    cong_nghe.kiem_chung.sai.clear()
    cong_nghe.nguon.co(RSS, CUNG_CHUYEN, *ba_bai_phu(8))
    cong_nghe.chay_ky.chay("cong-nghe", luc(8, 8))

    assert ([CUNG_CHUYEN.dia_chi], None) in cong_nghe.llm.ung_vien_da_thay(-2)


def test_tin_da_phat_hon_bay_ngay_truoc_khong_duoc_doi_chieu(cong_nghe: TheGioi) -> None:
    cong_nghe.nhung.cung_su_kien(DA_PHAT.tieu_de, CUNG_CHUYEN.tieu_de)
    cong_nghe.nguon.co(RSS, DA_PHAT, *ba_bai_phu(7))
    cong_nghe.chay_ky.chay("cong-nghe", luc(7, 8))

    sau_tam_ngay = bai("duo-3", CUNG_CHUYEN.tieu_de, luc(15, 7))
    cong_nghe.nguon.co(RSS, sau_tam_ngay, *ba_bai_phu(15))
    cong_nghe.chay_ky.chay("cong-nghe", luc(15, 8))

    assert ([sau_tam_ngay.dia_chi], None) in cong_nghe.llm.ung_vien_da_thay(-2)


def test_dich_vu_nhung_loi_thi_ky_hong_truoc_khi_goi_bien_tap_va_ky_sau_xet_lai(
    cong_nghe: TheGioi,
) -> None:
    phu = ba_bai_phu(7)
    cong_nghe.nguon.co(RSS, *phu)
    cong_nghe.nhung.hong(LoiNhung("Không kết nối được tới dịch vụ nhúng (ConnectError)"))

    ky = cong_nghe.chay_ky.chay("cong-nghe", luc(7, 8))

    assert ky.ket_qua is KetQuaKy.HONG
    assert ky.li_do == "Gom Tin gặp lỗi: Không kết nối được tới dịch vụ nhúng (ConnectError)"
    assert cong_nghe.llm.da_nhan == []
    assert cong_nghe.kenh_dang.da_nhan == []

    cong_nghe.nhung.hong(None)
    assert cong_nghe.chay_ky.chay("cong-nghe", luc(7, 9)).ket_qua is KetQuaKy.DA_PHAT
    assert tieu_de_da_phat(cong_nghe) == [[p.tieu_de for p in reversed(phu)]]


def test_moi_bai_goc_chi_duoc_nhung_mot_lan_cho_toi_khi_doi_model(cong_nghe: TheGioi) -> None:
    cong_nghe.them_chuyen_muc("tai-chinh", ten="Tài chính", nguon=[RSS], kenh_dang=["-1002"])
    cong_nghe.nguon.co(RSS, DA_PHAT, *ba_bai_phu(7))
    cong_nghe.chay_ky.chay("cong-nghe", luc(7, 8))
    cong_nghe.chay_ky.chay("tai-chinh", luc(7, 12))
    # Bài gốc của Tin đã phát cũng đã có vector, không phải nhúng lại khi đối chiếu ở Kỳ sau.
    cong_nghe.nguon.co(RSS, *ba_bai_phu(8))
    cong_nghe.chay_ky.chay("cong-nghe", luc(8, 8))

    assert len(cong_nghe.nhung.da_nhung) == 7

    cong_nghe.nhung.mo_hinh = "nhung-gia-2"
    cong_nghe.nguon.co(RSS, *ba_bai_phu(9))
    cong_nghe.chay_ky.chay("cong-nghe", luc(9, 8))

    # Vector của model cũ không so được với model mới: ba Bài gốc mới, cùng các Bài gốc đã phát
    # trong bảy ngày qua, được nhúng lại.
    assert len(cong_nghe.nhung.da_nhung) == 7 + 3 + 7


class MatDien(BaseException):
    """Tiến trình bị dừng giữa chừng: không phải lỗi mà Chạy Kỳ bắt được."""


def test_ky_chay_tiep_dung_lai_dung_cac_ung_vien_da_gom(cong_nghe: TheGioi) -> None:
    a1 = bai("a1", "Apple dời lịch giao iPhone Duo sang năm 2027", luc(7, 7))
    a2 = bai("a2", "Khách mua iPhone Duo có thể phải chờ đến Tết để nhận máy", luc(7, 7, 20))
    cong_nghe.nhung.cung_su_kien(a1.tieu_de, a2.tieu_de)
    cong_nghe.nguon.co(RSS, a1, a2, *ba_bai_phu(7))
    cong_nghe.llm.se(MatDien())
    with pytest.raises(MatDien):
        cong_nghe.chay_ky.chay("cong-nghe", luc(7, 8))
    ung_vien = cong_nghe.ung_vien_da_luu()

    # Dịch vụ nhúng hỏng cũng không sao: ứng viên đã được gom và lưu từ lần trước.
    cong_nghe.nhung.hong(LoiNhung("dịch vụ nhúng đang tắt"))
    ky = cong_nghe.chay_ky.chay_tiep("cong-nghe")

    assert ky is not None and ky.ket_qua is KetQuaKy.DA_PHAT
    assert cong_nghe.ung_vien_da_luu() == ung_vien
    assert [a1.dia_chi, a2.dia_chi] in ung_vien
    assert cong_nghe.bai_goc_cua_tin(a1.dia_chi) == [a1.dia_chi, a2.dia_chi]
