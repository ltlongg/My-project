"""Kiểm chứng và vòng viết lại, test tại điểm "Chạy Kỳ" với LLM trả lời theo kịch bản."""

import pytest
from langchain_core.messages import AIMessage

from bulletin.collectors import BaiGocMoi
from bulletin.mo_hinh import KetQuaKy
from tests.conftest import (
    HUONG_DAN_KIEM_CHUNG_MAC_DINH,
    TheGioi,
    TinViet,
    doc,
    ket_luan,
    luc,
    nop,
    viet_lai,
)

RSS = "https://bao.example/rss"
KENH_DANG = "-1001"
A, B, C, D = (f"https://bao.example/{ten}" for ten in "abcd")

TOAN_VAN_A = "Nvidia cho biết sẽ giao 3.000 GPU Rubin đầu tiên trong quý 3/2027."
SAI_NAM = "Bài gốc ghi quý 3/2027, không phải năm 2028."
# Tin về Bài gốc A: bản sai năm Kiểm chứng bắt được, và bản đúng.
A_SAI = TinViet(
    A,
    "Nvidia giao GPU Rubin năm 2028",
    "Nvidia cho biết hãng sẽ bắt đầu giao 3.000 GPU Rubin đầu tiên cho khách hàng vào năm 2028.",
)
A_DUNG = TinViet(
    A,
    "Nvidia giao GPU Rubin trong quý 3/2027",
    "Nvidia cho biết hãng sẽ bắt đầu giao 3.000 GPU Rubin đầu tiên cho khách trong quý 3/2027.",
)
TIN_B, TIN_C, TIN_D = (TinViet(dc, f"Tiêu đề {dc[-1].upper()}") for dc in (B, C, D))


def mot_chuyen_muc(the_gioi: TheGioi, *dia_chi: str) -> None:
    """Chuyên mục công nghệ có một Nguồn đang liệt kê các Bài gốc ở `dia_chi`, mới nhất trước.

    Kiểm chứng bắt Tin nào viết sai năm của Bài gốc A.
    """
    the_gioi.them_chuyen_muc("cong-nghe", ten="Công nghệ", nguon=[RSS], kenh_dang=[KENH_DANG])
    the_gioi.nguon.co(
        RSS,
        *(
            BaiGocMoi(dc, f"Original headline {thu_tu}", luc(7, 7, 59 - thu_tu))
            for thu_tu, dc in enumerate(dia_chi)
        ),
    )
    the_gioi.noi_dung.co(A, TOAN_VAN_A)
    the_gioi.kiem_chung.bat("2028", SAI_NAM)


def tieu_de_da_phat(the_gioi: TheGioi) -> list[str]:
    """Tiêu đề các Tin của Bản tin duy nhất đã tới Kênh đăng giả."""
    [(_, ban_tin)] = the_gioi.kenh_dang.da_nhan
    return [tin.tieu_de for tin in ban_tin.tin]


def test_tin_dat_ngay_thi_duoc_phat_va_luot_kiem_chung_duoc_luu(the_gioi: TheGioi) -> None:
    mot_chuyen_muc(the_gioi, A, B, C)
    the_gioi.llm.se(doc(A, B, C), nop(A_DUNG, TIN_B, TIN_C))

    ky = the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    assert ky.ket_qua is KetQuaKy.DA_PHAT
    assert tieu_de_da_phat(the_gioi) == [A_DUNG.tieu_de, TIN_B.tieu_de, TIN_C.tieu_de]
    # Mỗi Tin được xét một lần, đối chiếu với toàn văn Bài gốc của chính nó theo Hướng dẫn.
    assert the_gioi.kiem_chung.tin_da_xet() == [A_DUNG.tieu_de, TIN_B.tieu_de, TIN_C.tieu_de]
    assert TOAN_VAN_A in the_gioi.kiem_chung.van_ban_da_nhan(0)
    assert TOAN_VAN_A not in the_gioi.kiem_chung.van_ban_da_nhan(1)
    assert HUONG_DAN_KIEM_CHUNG_MAC_DINH in the_gioi.kiem_chung.van_ban_da_nhan(0)
    assert the_gioi.luot_kiem_chung(A) == [(A_DUNG.tieu_de, A_DUNG.tom_tat, True, "")]
    # Không Tin nào bị trả lại thì Biên tập không phải làm gì thêm sau khi nộp.
    assert len(the_gioi.llm.da_nhan) == 2


def test_tin_khong_dat_duoc_viet_lai_theo_li_do_cua_kiem_chung_roi_duoc_phat(
    the_gioi: TheGioi,
) -> None:
    mot_chuyen_muc(the_gioi, A, B, C)
    the_gioi.llm.se(doc(A, B, C), nop(A_SAI, TIN_B, TIN_C), viet_lai(A_DUNG))

    ky = the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    assert SAI_NAM in the_gioi.llm.van_ban_da_nhan()
    assert ky.ket_qua is KetQuaKy.DA_PHAT
    assert tieu_de_da_phat(the_gioi) == [A_DUNG.tieu_de, TIN_B.tieu_de, TIN_C.tieu_de]
    assert the_gioi.luot_kiem_chung(A) == [
        (A_SAI.tieu_de, A_SAI.tom_tat, False, SAI_NAM),
        (A_DUNG.tieu_de, A_DUNG.tom_tat, True, ""),
    ]
    # Tin đã đạt không bị xét lại.
    assert the_gioi.kiem_chung.tin_da_xet() == [
        A_SAI.tieu_de,
        TIN_B.tieu_de,
        TIN_C.tieu_de,
        A_DUNG.tieu_de,
    ]
    assert the_gioi.tin_bi_bo() == []


def test_tin_van_khong_dat_sau_hai_lan_viet_lai_thi_bi_bo_kem_li_do(the_gioi: TheGioi) -> None:
    mot_chuyen_muc(the_gioi, A, B, C, D)
    lan_2 = TinViet(
        A,
        "Nvidia giao Rubin cuối năm 2028",
        "Theo Nvidia, lô 3.000 GPU Rubin đầu tiên sẽ được giao tới khách hàng vào cuối năm 2028.",
    )
    lan_3 = TinViet(
        A,
        "Rubin tới tay khách năm 2028",
        "Khách hàng của Nvidia sẽ nhận được 3.000 GPU Rubin đầu tiên trong năm 2028.",
    )
    the_gioi.llm.se(
        doc(A, B, C, D), nop(A_SAI, TIN_B, TIN_C, TIN_D), viet_lai(lan_2), viet_lai(lan_3)
    )

    ky = the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    assert ky.ket_qua is KetQuaKy.DA_PHAT
    assert tieu_de_da_phat(the_gioi) == [TIN_B.tieu_de, TIN_C.tieu_de, TIN_D.tieu_de]
    assert the_gioi.tin_bi_bo() == [
        (lan_3.tieu_de, A, f"Không qua Kiểm chứng sau 2 lần viết lại: {SAI_NAM}")
    ]
    assert the_gioi.luot_kiem_chung(A) == [
        (ban.tieu_de, ban.tom_tat, False, SAI_NAM) for ban in (A_SAI, lan_2, lan_3)
    ]
    # Không có lần viết lại thứ ba: Biên tập chỉ được gọi để đọc, nộp và hai lần viết lại.
    assert len(the_gioi.llm.da_nhan) == 4


def test_duoi_ba_tin_qua_kiem_chung_thi_khong_phat_va_ky_hong(the_gioi: TheGioi) -> None:
    mot_chuyen_muc(the_gioi, A, B, C)
    the_gioi.llm.se(doc(A, B, C), nop(A_SAI, TIN_B, TIN_C), viet_lai(A_SAI), viet_lai(A_SAI))

    ky = the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    assert ky.ket_qua is KetQuaKy.HONG
    assert ky.li_do == "Chỉ 2 Tin qua Kiểm chứng, dưới mức tối thiểu 3; Bản tin không được phát"
    assert the_gioi.kenh_dang.da_nhan == []
    # Bản tin không phát vẫn được lưu, kể cả Tin bị bỏ.
    assert [tin[0] for tin in the_gioi.tin_da_luu()] == [TIN_B.tieu_de, TIN_C.tieu_de]
    assert [tin[1] for tin in the_gioi.tin_bi_bo()] == [A]
    assert the_gioi.chay_ky.lich_su("cong-nghe") == [ky]


@pytest.mark.parametrize(
    ("ban_hong", "li_do_tra_lai"),
    [
        (TIN_B, "không bị trả lại"),
        (TinViet(A, A_DUNG.tieu_de, "Nvidia ships 3,000 Rubin GPUs in Q3 2027."), "tiếng Việt"),
    ],
)
def test_ban_viet_lai_khong_hop_le_bi_tra_lai_kem_li_do(
    the_gioi: TheGioi, ban_hong: TinViet, li_do_tra_lai: str
) -> None:
    mot_chuyen_muc(the_gioi, A, B, C)
    the_gioi.llm.se(doc(A, B, C), nop(A_SAI, TIN_B, TIN_C), viet_lai(ban_hong), viet_lai(A_DUNG))

    ky = the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    assert li_do_tra_lai in the_gioi.llm.van_ban_da_nhan()
    assert ky.ket_qua is KetQuaKy.DA_PHAT
    assert tieu_de_da_phat(the_gioi) == [A_DUNG.tieu_de, TIN_B.tieu_de, TIN_C.tieu_de]
    # Bản bị code trả lại không tới Kiểm chứng và không tính là một lần viết lại.
    assert [luot[0] for luot in the_gioi.luot_kiem_chung(A)] == [A_SAI.tieu_de, A_DUNG.tieu_de]


def test_kiem_chung_tra_ket_luan_hong_mot_lan_thi_duoc_nhac_va_ky_van_ra(
    the_gioi: TheGioi,
) -> None:
    mot_chuyen_muc(the_gioi, A, B, C)
    the_gioi.llm.se(doc(A, B, C), nop(A_DUNG, TIN_B, TIN_C))
    the_gioi.kiem_chung.se(AIMessage("Tin này đạt."))

    ky = the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    assert ky.ket_qua is KetQuaKy.DA_PHAT
    assert the_gioi.kiem_chung.tin_da_xet() == [
        A_DUNG.tieu_de,
        A_DUNG.tieu_de,
        TIN_B.tieu_de,
        TIN_C.tieu_de,
    ]


def test_kiem_chung_tra_ket_luan_hong_mai_thi_ky_hong_va_khong_co_gi_duoc_phat(
    the_gioi: TheGioi,
) -> None:
    mot_chuyen_muc(the_gioi, A, B, C)
    the_gioi.llm.se(doc(A, B, C), nop(A_DUNG, TIN_B, TIN_C))
    # Không đạt mà không nêu lí do thì Biên tập không biết sửa gì, nên cũng là hỏng.
    the_gioi.kiem_chung.se(AIMessage("Tin này đạt."), ket_luan(False), AIMessage("Đạt."))

    ky = the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    assert ky.ket_qua is KetQuaKy.HONG
    assert ky.li_do is not None
    assert ky.li_do.startswith("Kiểm chứng trả kết luận không hợp lệ 3 lần; lần cuối: ")
    assert the_gioi.kenh_dang.da_nhan == []
    assert the_gioi.tin_da_luu() == []


def test_llm_cua_kiem_chung_loi_thi_ky_hong_kem_li_do(the_gioi: TheGioi) -> None:
    mot_chuyen_muc(the_gioi, A, B, C)
    the_gioi.llm.se(doc(A, B, C), nop(A_DUNG, TIN_B, TIN_C))
    the_gioi.kiem_chung.se(RuntimeError("HTTP 503: model quá tải"))

    ky = the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    assert ky.ket_qua is KetQuaKy.HONG
    assert ky.li_do == "Kiểm chứng gặp lỗi: HTTP 503: model quá tải"
    assert the_gioi.kenh_dang.da_nhan == []


def test_huong_dan_cua_kiem_chung_la_ban_chung_doc_tu_du_lieu_va_ky_ghi_phien_ban(
    the_gioi: TheGioi,
) -> None:
    mot_chuyen_muc(the_gioi, A, B, C)
    the_gioi.them_chuyen_muc("tai-chinh", ten="Tài chính", nguon=[RSS], kenh_dang=["-1002"])

    the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))
    assert HUONG_DAN_KIEM_CHUNG_MAC_DINH in the_gioi.kiem_chung.van_ban_da_nhan()
    assert the_gioi.doi_huong_dan_kiem_chung("Soát kỹ tên riêng.") == 2
    the_gioi.chay_ky.chay("tai-chinh", luc(7, 12))

    assert "Soát kỹ tên riêng." in the_gioi.kiem_chung.van_ban_da_nhan()
    assert HUONG_DAN_KIEM_CHUNG_MAC_DINH not in the_gioi.kiem_chung.van_ban_da_nhan()
    assert [ky.phien_ban_huong_dan_kiem_chung for ky in the_gioi.chay_ky.lich_su("cong-nghe")] == [
        1
    ]
    assert [ky.phien_ban_huong_dan_kiem_chung for ky in the_gioi.chay_ky.lich_su("tai-chinh")] == [
        2
    ]


def test_chua_co_huong_dan_cho_kiem_chung_thi_ky_hong_truoc_khi_goi_llm(the_gioi: TheGioi) -> None:
    mot_chuyen_muc(the_gioi, A, B, C)
    the_gioi.doi_huong_dan_kiem_chung(None)

    ky = the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    assert ky.ket_qua is KetQuaKy.HONG
    assert ky.li_do == "Chưa có Hướng dẫn cho Kiểm chứng"
    assert the_gioi.llm.da_nhan == []


class MatDien(BaseException):
    """Tiến trình bị dừng giữa chừng: không phải lỗi mà Chạy Kỳ bắt được."""


def test_ky_bi_gian_doan_luc_viet_lai_chay_tiep_ma_khong_xet_lai_tin_da_dat(
    the_gioi: TheGioi,
) -> None:
    mot_chuyen_muc(the_gioi, A, B, C)
    the_gioi.llm.se(doc(A, B, C), nop(A_SAI, TIN_B, TIN_C), MatDien())
    with pytest.raises(MatDien):
        the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    the_gioi.llm.se(viet_lai(A_DUNG))
    ky = the_gioi.chay_ky.chay_tiep("cong-nghe")

    assert ky is not None and ky.ket_qua is KetQuaKy.DA_PHAT
    assert tieu_de_da_phat(the_gioi) == [A_DUNG.tieu_de, TIN_B.tieu_de, TIN_C.tieu_de]
    assert the_gioi.kiem_chung.tin_da_xet() == [
        A_SAI.tieu_de,
        TIN_B.tieu_de,
        TIN_C.tieu_de,
        A_DUNG.tieu_de,
    ]
    assert [luot[2] for luot in the_gioi.luot_kiem_chung(A)] == [False, True]
