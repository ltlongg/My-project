"""Biên tập, test tại điểm "Chạy Kỳ" với LLM trả lời theo kịch bản."""

import pytest

from bulletin.collectors import BaiGocMoi
from bulletin.mo_hinh import KetQuaKy
from bulletin.publishers import NoiDungTin
from bulletin.search import KetQuaTimKiem
from tests.conftest import TheGioi, TinViet, doc, luc, noi, nop, tim

RSS = "https://bao.example/rss"
KENH_DANG = "-1001"
A, B, C, D = (f"https://bao.example/{ten}" for ten in "abcd")


def mot_chuyen_muc(the_gioi: TheGioi, *dia_chi: str, so_tin_toi_da: int = 7) -> None:
    """Chuyên mục công nghệ có một Nguồn đang liệt kê các Bài gốc ở `dia_chi`, mới nhất trước."""
    the_gioi.them_chuyen_muc(
        "cong-nghe",
        ten="Công nghệ",
        nguon=[RSS],
        kenh_dang=[KENH_DANG],
        so_tin_toi_da=so_tin_toi_da,
    )
    the_gioi.nguon.co(
        RSS,
        *(
            BaiGocMoi(dc, f"Original headline {thu_tu}", luc(7, 7, 59 - thu_tu))
            for thu_tu, dc in enumerate(dia_chi)
        ),
    )


def tin_da_phat(the_gioi: TheGioi) -> list[NoiDungTin]:
    """Các Tin của Bản tin duy nhất đã tới Kênh đăng giả."""
    [(_, ban_tin)] = the_gioi.kenh_dang.da_nhan
    return list(ban_tin.tin)


def test_ban_tin_gom_nhung_tin_bien_tap_chon_voi_tieu_de_va_tom_tat_no_viet(
    the_gioi: TheGioi,
) -> None:
    mot_chuyen_muc(the_gioi, A, B, C, D)
    the_gioi.llm.se(
        doc(A, C, D),
        nop(
            TinViet(
                C, "OpenAI ra mắt model mới", "OpenAI công bố model mới với giá rẻ hơn.", "Lớn"
            ),
            TinViet(A, "Nvidia hoãn Rubin", "Nvidia lùi lịch giao GPU Rubin sang năm 2027.", "Mới"),
            TinViet(
                D, "Meta mở mã Llama 5", "Meta công bố Llama 5 dưới giấy phép mở.", "Đáng chú ý"
            ),
        ),
    )

    ky = the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    assert ky.ket_qua is KetQuaKy.DA_PHAT
    # Bài B không được chọn; thứ tự là thứ tự Biên tập nộp.
    assert tin_da_phat(the_gioi) == [
        NoiDungTin("OpenAI ra mắt model mới", "OpenAI công bố model mới với giá rẻ hơn.", C),
        NoiDungTin("Nvidia hoãn Rubin", "Nvidia lùi lịch giao GPU Rubin sang năm 2027.", A),
        NoiDungTin("Meta mở mã Llama 5", "Meta công bố Llama 5 dưới giấy phép mở.", D),
    ]
    assert the_gioi.tin_da_luu() == [
        ("OpenAI ra mắt model mới", "OpenAI công bố model mới với giá rẻ hơn.", "Lớn", C),
        ("Nvidia hoãn Rubin", "Nvidia lùi lịch giao GPU Rubin sang năm 2027.", "Mới", A),
        ("Meta mở mã Llama 5", "Meta công bố Llama 5 dưới giấy phép mở.", "Đáng chú ý", D),
    ]


def test_bien_tap_doc_duoc_toan_van_bai_goc_va_toan_van_duoc_luu(the_gioi: TheGioi) -> None:
    mot_chuyen_muc(the_gioi, A, B)
    the_gioi.noi_dung.co(A, "QuantumCell đạt mật độ năng lượng 487 Wh/kg trong thử nghiệm độc lập.")
    the_gioi.llm.se(doc(A), nop(TinViet(A)))

    the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    assert "487 Wh/kg" in the_gioi.llm.van_ban_da_nhan()
    assert the_gioi.toan_van_da_luu(A) == (
        "QuantumCell đạt mật độ năng lượng 487 Wh/kg trong thử nghiệm độc lập."
    )
    # Bài gốc không ai đọc thì không bị tải về.
    assert the_gioi.noi_dung.da_lay == [A]
    assert the_gioi.toan_van_da_luu(B) is None


def test_toan_van_da_luu_khong_bi_lay_lai_o_chuyen_muc_khac(the_gioi: TheGioi) -> None:
    mot_chuyen_muc(the_gioi, A)
    the_gioi.them_chuyen_muc("tai-chinh", ten="Tài chính", nguon=[RSS], kenh_dang=["-1002"])

    the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))
    the_gioi.chay_ky.chay("tai-chinh", luc(7, 12))

    assert the_gioi.noi_dung.da_lay == [A]


def test_bien_tap_tim_kiem_web_duoc_nhung_ket_qua_tim_kiem_khong_thanh_tin(
    the_gioi: TheGioi,
) -> None:
    mot_chuyen_muc(the_gioi, A, B, C)
    the_gioi.tim_kiem.ket_qua = [
        KetQuaTimKiem("Rubin là gì", "https://la.example/rubin", "Rubin là thế hệ GPU kế tiếp.")
    ]
    ma_la = 9999
    the_gioi.llm.se(
        doc(A, B, C),
        tim("Nvidia Rubin là gì"),
        nop(TinViet(A), TinViet(B), TinViet(C), TinViet(ma_la, "Tin từ kết quả tìm kiếm")),
        nop(TinViet(A), TinViet(B), TinViet(C)),
    )

    ky = the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    assert the_gioi.tim_kiem.da_tim == ["Nvidia Rubin là gì"]
    # Kết quả tìm kiếm tới được LLM ở lời gọi ngay sau đó.
    assert "Rubin là thế hệ GPU kế tiếp." in the_gioi.llm.van_ban_da_nhan(2)
    # Bản nộp có Tin không dẫn tới ứng viên nào bị trả lại cả bản; bản sau mới được phát.
    assert "9999" in the_gioi.llm.van_ban_da_nhan(3)
    assert ky.ket_qua is KetQuaKy.DA_PHAT
    assert [tin.dia_chi for tin in tin_da_phat(the_gioi)] == [A, B, C]


def test_tin_vuot_1024_ky_tu_bi_tra_lai_cho_bien_tap_viet_gon(the_gioi: TheGioi) -> None:
    mot_chuyen_muc(the_gioi, A, B, C)
    tieu_de = "Tiêu đề"
    # Tiêu đề, tóm tắt và link cách nhau hai dòng trống: vừa đúng 1.024 thì qua, thêm một thì không.
    vua_du = "ô" * (1024 - len(tieu_de) - len(A) - 4)
    the_gioi.llm.se(
        doc(A, B, C),
        nop(TinViet(A, tieu_de, vua_du + "ô"), TinViet(B), TinViet(C)),
        nop(TinViet(A, tieu_de, vua_du), TinViet(B), TinViet(C)),
    )

    ky = the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    assert "vượt giới hạn 1024" in the_gioi.llm.van_ban_da_nhan()
    assert ky.ket_qua is KetQuaKy.DA_PHAT
    [tin, *_] = tin_da_phat(the_gioi)
    assert tin.tom_tat == vua_du
    assert tin.do_dai == 1024


def test_ban_tin_nhieu_tin_hon_muc_toi_da_cua_chuyen_muc_bi_tra_lai(the_gioi: TheGioi) -> None:
    mot_chuyen_muc(the_gioi, A, B, C, D, so_tin_toi_da=3)
    the_gioi.llm.se(
        doc(A, B, C, D),
        nop(TinViet(A), TinViet(B), TinViet(C), TinViet(D)),
        nop(TinViet(A), TinViet(B), TinViet(C)),
    )

    the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    assert [tin.dia_chi for tin in tin_da_phat(the_gioi)] == [A, B, C]


@pytest.mark.parametrize(
    ("tin_hong", "li_do_tra_lai"),
    [
        (TinViet(B), "chưa đọc toàn văn"),
        (TinViet(A, tom_tat="OpenAI announced a cheaper model on Tuesday."), "bằng tiếng Việt"),
        (TinViet(A, tom_tat="Xem thêm tại https://la.example/bai nhé."), "không được chứa link"),
        (TinViet(A, tieu_de="   "), "tieu_de"),
    ],
)
def test_tin_khong_dat_quy_tac_bi_tra_lai_kem_li_do(
    the_gioi: TheGioi, tin_hong: TinViet, li_do_tra_lai: str
) -> None:
    mot_chuyen_muc(the_gioi, A, B, C, D)
    the_gioi.llm.se(
        doc(A, C, D),
        nop(tin_hong, TinViet(C), TinViet(D)),
        nop(TinViet(A, "Tiêu đề đạt"), TinViet(C), TinViet(D)),
    )

    ky = the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    assert li_do_tra_lai in the_gioi.llm.van_ban_da_nhan()
    assert ky.ket_qua is KetQuaKy.DA_PHAT
    assert [tin.dia_chi for tin in tin_da_phat(the_gioi)] == [A, C, D]
    assert tin_da_phat(the_gioi)[0].tieu_de == "Tiêu đề đạt"


def test_khong_doc_duoc_mot_bai_goc_thi_bien_tap_duoc_bao_va_ban_tin_van_ra(
    the_gioi: TheGioi,
) -> None:
    mot_chuyen_muc(the_gioi, A, B, C, D)
    the_gioi.noi_dung.hong(A, RuntimeError("trang có tường phí"))
    the_gioi.llm.se(doc(A, B, C, D), nop(TinViet(B), TinViet(C), TinViet(D)))

    ky = the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    assert "trang có tường phí" in the_gioi.llm.van_ban_da_nhan()
    assert ky.ket_qua is KetQuaKy.DA_PHAT
    assert [tin.dia_chi for tin in tin_da_phat(the_gioi)] == [B, C, D]


def test_bien_tap_nop_hong_mai_thi_ky_hong_va_khong_co_gi_duoc_phat(the_gioi: TheGioi) -> None:
    mot_chuyen_muc(the_gioi, A)
    the_gioi.llm.se(doc(A))
    the_gioi.llm.lap_lai = nop(TinViet(A, tom_tat="Still not Vietnamese."))

    ky = the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    assert ky.ket_qua is KetQuaKy.HONG
    assert ky.li_do is not None
    assert ky.li_do.startswith("Biên tập nộp Bản tin không hợp lệ 3 lần; lần cuối: ")
    assert "bằng tiếng Việt" in ky.li_do
    assert the_gioi.kenh_dang.da_nhan == []
    assert the_gioi.tin_da_luu() == []
    assert the_gioi.chay_ky.lich_su("cong-nghe") == [ky]


def test_bien_tap_khong_bao_gio_nop_thi_ky_hong_sau_so_luot_gioi_han(the_gioi: TheGioi) -> None:
    mot_chuyen_muc(the_gioi, A)
    the_gioi.llm.lap_lai = noi("Tôi nghĩ Bài A đáng đọc.")

    ky = the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    assert ky.ket_qua is KetQuaKy.HONG
    assert ky.li_do == "Biên tập chưa nộp Bản tin sau 40 lượt"
    assert len(the_gioi.llm.da_nhan) == 40
    assert the_gioi.kenh_dang.da_nhan == []


def test_llm_loi_thi_ky_hong_kem_li_do_va_khong_co_gi_duoc_phat(the_gioi: TheGioi) -> None:
    mot_chuyen_muc(the_gioi, A)
    the_gioi.llm.se(doc(A), RuntimeError("HTTP 429: hết hạn mức"))

    ky = the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    assert ky.ket_qua is KetQuaKy.HONG
    assert ky.li_do == "Biên tập gặp lỗi: HTTP 429: hết hạn mức"
    assert the_gioi.kenh_dang.da_nhan == []


def test_huong_dan_cua_bien_tap_duoc_doc_tu_du_lieu_theo_tung_chuyen_muc(
    the_gioi: TheGioi,
) -> None:
    the_gioi.them_chuyen_muc(
        "cong-nghe",
        ten="Công nghệ",
        nguon=[RSS],
        kenh_dang=[KENH_DANG],
        huong_dan="Ưu tiên paper và repo nổi bật.",
    )
    the_gioi.them_chuyen_muc(
        "tai-chinh",
        ten="Tài chính",
        nguon=[RSS],
        kenh_dang=["-1002"],
        huong_dan="Không chọn tin crypto.",
    )
    the_gioi.nguon.co(RSS, BaiGocMoi(A, "Bài A", luc(7, 7)))

    the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))
    cong_nghe_nhan = the_gioi.llm.van_ban_da_nhan()
    the_gioi.chay_ky.chay("tai-chinh", luc(7, 12))
    tai_chinh_nhan = the_gioi.llm.van_ban_da_nhan()

    assert "Ưu tiên paper và repo nổi bật." in cong_nghe_nhan
    assert "Không chọn tin crypto." not in cong_nghe_nhan
    assert "Không chọn tin crypto." in tai_chinh_nhan
    assert "Ưu tiên paper và repo nổi bật." not in tai_chinh_nhan


def test_ky_ghi_lai_phien_ban_huong_dan_da_dung(the_gioi: TheGioi) -> None:
    mot_chuyen_muc(the_gioi, A)
    the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    assert the_gioi.doi_huong_dan("cong-nghe", "Bớt tin về điện thoại.") == 2
    the_gioi.nguon.co(RSS, BaiGocMoi(B, "Bài B", luc(8, 7)))
    the_gioi.chay_ky.chay("cong-nghe", luc(8, 8))

    assert "Bớt tin về điện thoại." in the_gioi.llm.van_ban_da_nhan()
    # Mới nhất trước.
    assert [ky.phien_ban_huong_dan_bien_tap for ky in the_gioi.chay_ky.lich_su("cong-nghe")] == [
        2,
        1,
    ]


def test_chuyen_muc_chua_co_huong_dan_cho_bien_tap_thi_ky_hong_kem_li_do(
    the_gioi: TheGioi,
) -> None:
    the_gioi.them_chuyen_muc(
        "cong-nghe", ten="Công nghệ", nguon=[RSS], kenh_dang=[KENH_DANG], huong_dan=None
    )
    the_gioi.nguon.co(RSS, BaiGocMoi(A, "Bài A", luc(7, 7)))

    ky = the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    assert ky.ket_qua is KetQuaKy.HONG
    assert ky.li_do == "Chuyên mục chưa có Hướng dẫn cho Biên tập"
    assert the_gioi.llm.da_nhan == []


def test_bien_tap_chi_nhan_30_ung_vien_moi_nhat(the_gioi: TheGioi) -> None:
    mot_chuyen_muc(the_gioi, *(f"https://bao.example/{so}" for so in range(35)))
    # Hai Bài gốc mới nhất là một sự kiện, nên 30 ứng viên gồm 31 Bài gốc.
    the_gioi.nhung.cung_su_kien("Original headline 0", "Original headline 1")
    the_gioi.llm.se(doc("https://bao.example/0"), nop(TinViet("https://bao.example/0")))

    the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    assert len(the_gioi.llm.ung_vien_da_thay()) == 30
    de_bai = the_gioi.llm.van_ban_da_nhan(0)
    assert '"https://bao.example/30"' in de_bai
    assert '"https://bao.example/31"' not in de_bai


class MatDien(BaseException):
    """Tiến trình bị dừng giữa chừng: không phải lỗi mà Chạy Kỳ bắt được."""


def test_ky_bi_gian_doan_chay_tiep_tu_buoc_dang_do_cua_bien_tap(the_gioi: TheGioi) -> None:
    mot_chuyen_muc(the_gioi, A, B, C)
    the_gioi.noi_dung.co(A, "Toàn văn bài A có con số 487.")
    the_gioi.llm.se(doc(A), doc(B, C), MatDien())
    with pytest.raises(MatDien):
        the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))
    [ky_dang_do] = the_gioi.chay_ky.lich_su("cong-nghe")
    assert ky_dang_do.ket_qua is None
    so_lan_goi_truoc = len(the_gioi.llm.da_nhan)

    the_gioi.llm.se(nop(TinViet(A), TinViet(B), TinViet(C)))
    ky = the_gioi.chay_ky.chay_tiep("cong-nghe")

    assert ky is not None and ky.ket_qua is KetQuaKy.DA_PHAT
    assert ky.thoi_diem == luc(7, 8)
    assert [tin.dia_chi for tin in tin_da_phat(the_gioi)] == [A, B, C]
    # Biên tập làm tiếp chứ không làm lại: chỉ thêm một lời gọi LLM, vẫn thấy toàn văn đã đọc
    # trước khi mất điện, và không Bài gốc nào bị tải lại.
    assert len(the_gioi.llm.da_nhan) == so_lan_goi_truoc + 1
    assert "Toàn văn bài A có con số 487." in the_gioi.llm.van_ban_da_nhan()
    # Việc không bị giao lại lần hai: cuộc trò chuyện chỉ dài thêm đúng phần đang dở.
    assert len(the_gioi.llm.da_nhan[-1]) == len(the_gioi.llm.da_nhan[-2])
    assert the_gioi.noi_dung.da_lay == [A, B, C]
    assert the_gioi.chay_ky.lich_su("cong-nghe") == [ky]


def test_khong_co_ky_dang_do_thi_chay_tiep_khong_lam_gi(the_gioi: TheGioi) -> None:
    mot_chuyen_muc(the_gioi, A, B, C)
    assert the_gioi.chay_ky.chay_tiep("cong-nghe") is None

    the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    assert the_gioi.chay_ky.chay_tiep("cong-nghe") is None
    assert len(the_gioi.kenh_dang.da_nhan) == 1
