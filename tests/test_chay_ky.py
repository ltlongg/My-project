"""Test tại điểm "Chạy Kỳ": khẳng định về thứ tới Kênh đăng giả và thứ được lưu."""

from datetime import datetime

import pytest

from bulletin.collectors import BaiGocMoi
from bulletin.mo_hinh import KetQuaKy
from bulletin.publishers import NoiDungBanTin, NoiDungTin
from tests.conftest import TheGioi, TinViet, doc, luc, nop

RSS = "https://bao.example/rss"
KENH_DANG = "-1001"


def test_ky_phat_ban_tin_gom_cac_tin_ve_bai_goc_moi_kem_link(the_gioi: TheGioi) -> None:
    the_gioi.them_chuyen_muc("cong-nghe", ten="Công nghệ", nguon=[RSS], kenh_dang=[KENH_DANG])
    the_gioi.nguon.co(
        RSS,
        BaiGocMoi("https://bao.example/a", "Bài A", luc(7, 6)),
        BaiGocMoi("https://bao.example/b", "Bài B", luc(7, 7)),
    )

    ky = the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    assert ky.ket_qua is KetQuaKy.DA_PHAT
    assert the_gioi.kenh_dang.da_nhan == [
        (
            KENH_DANG,
            NoiDungBanTin(
                chuyen_muc="Công nghệ",
                thoi_diem=luc(7, 8),
                tin=(
                    NoiDungTin("Bài B", "Tóm tắt của Bài B.", "https://bao.example/b"),
                    NoiDungTin("Bài A", "Tóm tắt của Bài A.", "https://bao.example/a"),
                ),
            ),
        )
    ]


def tieu_de_da_phat(the_gioi: TheGioi) -> list[list[str]]:
    """Tiêu đề các Tin của từng Bản tin đã tới Kênh đăng giả, theo thứ tự nhận."""
    return [[tin.tieu_de for tin in ban_tin.tin] for _, ban_tin in the_gioi.kenh_dang.da_nhan]


def test_ky_dau_tien_chi_xet_bai_goc_cua_24_gio_gan_nhat(the_gioi: TheGioi) -> None:
    the_gioi.them_chuyen_muc("cong-nghe", ten="Công nghệ", nguon=[RSS], kenh_dang=[KENH_DANG])
    the_gioi.nguon.co(
        RSS,
        BaiGocMoi("https://bao.example/cu", "Bài hôm kia", luc(6, 7, 59)),
        BaiGocMoi("https://bao.example/moi", "Bài hôm qua", luc(6, 8, 1)),
    )

    the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    assert tieu_de_da_phat(the_gioi) == [["Bài hôm qua"]]


def test_ky_sau_chi_xet_bai_goc_xuat_hien_tu_ban_tin_truoc(the_gioi: TheGioi) -> None:
    the_gioi.them_chuyen_muc("cong-nghe", ten="Công nghệ", nguon=[RSS], kenh_dang=[KENH_DANG])
    bai_sang = BaiGocMoi("https://bao.example/sang", "Bài buổi sáng", luc(7, 7))
    bai_chieu = BaiGocMoi("https://bao.example/chieu", "Bài buổi chiều", luc(7, 15))
    the_gioi.nguon.co(RSS, bai_sang)
    the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    # Nguồn vẫn còn liệt kê bài buổi sáng, như một RSS feed thật.
    the_gioi.nguon.co(RSS, bai_sang, bai_chieu)
    the_gioi.chay_ky.chay("cong-nghe", luc(8, 8))

    assert tieu_de_da_phat(the_gioi) == [["Bài buổi sáng"], ["Bài buổi chiều"]]


def test_cung_bai_goc_duoi_hai_dia_chi_khac_nhau_chi_thanh_mot_tin(the_gioi: TheGioi) -> None:
    rss_khac = "https://tonghop.example/rss"
    the_gioi.them_chuyen_muc(
        "cong-nghe", ten="Công nghệ", nguon=[RSS, rss_khac], kenh_dang=[KENH_DANG]
    )
    the_gioi.nguon.co(RSS, BaiGocMoi("https://bao.example/tin/a", "Bài A", luc(7, 7)))
    the_gioi.nguon.co(
        rss_khac,
        BaiGocMoi(
            "HTTPS://Bao.Example/tin/a/?utm_source=tonghop&utm_medium=rss#binh-luan",
            "Bài A (qua trang tổng hợp)",
            luc(7, 7, 30),
        ),
    )

    the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    assert tieu_de_da_phat(the_gioi) == [["Bài A"]]


def test_khong_co_bai_goc_moi_thi_khong_phat(the_gioi: TheGioi) -> None:
    the_gioi.them_chuyen_muc("cong-nghe", ten="Công nghệ", nguon=[RSS], kenh_dang=[KENH_DANG])
    the_gioi.nguon.co(RSS, BaiGocMoi("https://bao.example/cu", "Bài tuần trước", luc(1, 9)))

    ky = the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    assert ky.ket_qua is KetQuaKy.KHONG_PHAT
    assert ky.li_do == "Không có Bài gốc mới"
    assert the_gioi.kenh_dang.da_nhan == []
    assert the_gioi.chay_ky.lich_su("cong-nghe") == [ky]


def test_moi_kenh_dang_deu_loi_thi_ky_hong_va_bai_goc_duoc_xet_lai_o_ky_sau(
    the_gioi: TheGioi,
) -> None:
    the_gioi.them_chuyen_muc("cong-nghe", ten="Công nghệ", nguon=[RSS], kenh_dang=[KENH_DANG])
    the_gioi.nguon.co(RSS, BaiGocMoi("https://bao.example/a", "Bài A", luc(7, 7)))
    the_gioi.kenh_dang.hong(KENH_DANG, RuntimeError("bot bị chặn khỏi nhóm"))

    ky_hong = the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    assert ky_hong.ket_qua is KetQuaKy.HONG
    assert ky_hong.li_do == f"Kênh đăng {KENH_DANG} lỗi: bot bị chặn khỏi nhóm"
    assert the_gioi.chay_ky.lich_su("cong-nghe") == [ky_hong]

    the_gioi.kenh_dang.sua(KENH_DANG)
    ky_sau = the_gioi.chay_ky.chay("cong-nghe", luc(7, 8, 30))

    assert ky_sau.ket_qua is KetQuaKy.DA_PHAT
    assert tieu_de_da_phat(the_gioi) == [["Bài A"]]


def test_mot_kenh_dang_loi_khong_chan_kenh_dang_khac(the_gioi: TheGioi) -> None:
    kenh_dang_loi = "-1002"
    the_gioi.them_chuyen_muc(
        "cong-nghe", ten="Công nghệ", nguon=[RSS], kenh_dang=[kenh_dang_loi, KENH_DANG]
    )
    the_gioi.nguon.co(RSS, BaiGocMoi("https://bao.example/a", "Bài A", luc(7, 7)))
    the_gioi.kenh_dang.hong(kenh_dang_loi, RuntimeError("quá thời gian"))

    ky = the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    assert ky.ket_qua is KetQuaKy.DA_PHAT
    assert ky.li_do == f"Kênh đăng {kenh_dang_loi} lỗi: quá thời gian"
    assert [dia_chi for dia_chi, _ in the_gioi.kenh_dang.da_nhan] == [KENH_DANG]


def test_mot_nguon_loi_van_ra_ban_tin_tu_nguon_con_lai(the_gioi: TheGioi) -> None:
    rss_loi = "https://chet.example/rss"
    the_gioi.them_chuyen_muc(
        "cong-nghe", ten="Công nghệ", nguon=[rss_loi, RSS], kenh_dang=[KENH_DANG]
    )
    the_gioi.nguon.hong(rss_loi, RuntimeError("máy chủ trả về 503"))
    the_gioi.nguon.co(RSS, BaiGocMoi("https://bao.example/a", "Bài A", luc(7, 7)))

    ky = the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    assert ky.ket_qua is KetQuaKy.DA_PHAT
    assert tieu_de_da_phat(the_gioi) == [["Bài A"]]
    assert the_gioi.tinh_trang_nguon() == {rss_loi: "máy chủ trả về 503", RSS: None}


def test_moi_nguon_deu_loi_thi_ky_hong(the_gioi: TheGioi) -> None:
    the_gioi.them_chuyen_muc("cong-nghe", ten="Công nghệ", nguon=[RSS], kenh_dang=[KENH_DANG])
    the_gioi.nguon.hong(RSS, RuntimeError("mất mạng"))

    ky = the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    assert ky.ket_qua is KetQuaKy.HONG
    assert ky.li_do == "Không thu thập được Nguồn nào"
    assert the_gioi.kenh_dang.da_nhan == []


def test_hai_ky_lien_tiep_khong_luu_trung_bai_goc(the_gioi: TheGioi) -> None:
    the_gioi.them_chuyen_muc("cong-nghe", ten="Công nghệ", nguon=[RSS], kenh_dang=[KENH_DANG])
    the_gioi.nguon.co(
        RSS,
        BaiGocMoi("https://bao.example/a", "Bài A", luc(7, 6)),
        BaiGocMoi("https://bao.example/b", "Bài B", luc(7, 7)),
    )

    the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))
    the_gioi.chay_ky.chay("cong-nghe", luc(7, 9))

    assert the_gioi.so_bai_goc_da_luu() == 2


def test_hai_chuyen_muc_chung_nguon_co_moc_rieng_va_bai_goc_chi_luu_mot_lan(
    the_gioi: TheGioi,
) -> None:
    kenh_dang_tai_chinh = "-1002"
    the_gioi.them_chuyen_muc("cong-nghe", ten="Công nghệ", nguon=[RSS], kenh_dang=[KENH_DANG])
    the_gioi.them_chuyen_muc(
        "tai-chinh", ten="Tài chính", nguon=[RSS], kenh_dang=[kenh_dang_tai_chinh]
    )
    the_gioi.nguon.co(RSS, BaiGocMoi("https://bao.example/a", "Bài A", luc(7, 7)))

    the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))
    # Bài A đã phát ở Công nghệ nhưng với Tài chính nó vẫn là mới.
    the_gioi.chay_ky.chay("tai-chinh", luc(7, 12))

    assert [
        (dia_chi, ban_tin.chuyen_muc, [tin.tieu_de for tin in ban_tin.tin])
        for dia_chi, ban_tin in the_gioi.kenh_dang.da_nhan
    ] == [(KENH_DANG, "Công nghệ", ["Bài A"]), (kenh_dang_tai_chinh, "Tài chính", ["Bài A"])]
    assert the_gioi.so_bai_goc_da_luu() == 1


def test_chuyen_muc_chua_co_kenh_dang_thi_ky_hong_kem_li_do(the_gioi: TheGioi) -> None:
    the_gioi.them_chuyen_muc("cong-nghe", ten="Công nghệ", nguon=[RSS], kenh_dang=[])
    the_gioi.nguon.co(RSS, BaiGocMoi("https://bao.example/a", "Bài A", luc(7, 7)))

    ky = the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    assert ky.ket_qua is KetQuaKy.HONG
    assert ky.li_do == "Chuyên mục chưa có Kênh đăng nào"


def test_ban_tin_duoc_luu_dung_nhu_da_gui(the_gioi: TheGioi) -> None:
    the_gioi.them_chuyen_muc("cong-nghe", ten="Công nghệ", nguon=[RSS], kenh_dang=[KENH_DANG])
    the_gioi.nguon.co(
        RSS,
        BaiGocMoi("https://bao.example/a", "Bài A", luc(7, 6)),
        BaiGocMoi("https://bao.example/b", "Bài B", luc(7, 7)),
    )

    the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    [(_, da_gui)] = the_gioi.kenh_dang.da_nhan
    [ky_da_luu] = the_gioi.chay_ky.lich_su("cong-nghe")
    assert ky_da_luu.ket_qua is KetQuaKy.DA_PHAT
    assert ky_da_luu.ban_tin == da_gui


def test_thoi_diem_khong_co_mui_gio_bi_tu_choi(the_gioi: TheGioi) -> None:
    the_gioi.them_chuyen_muc("cong-nghe", ten="Công nghệ", nguon=[RSS], kenh_dang=[KENH_DANG])

    with pytest.raises(ValueError, match="múi giờ"):
        the_gioi.chay_ky.chay("cong-nghe", datetime(2026, 10, 7, 8, 0))

    assert the_gioi.chay_ky.lich_su("cong-nghe") == []


def test_loi_khong_luong_truoc_van_de_lai_mot_ky_hong_kem_li_do(the_gioi: TheGioi) -> None:
    the_gioi.them_chuyen_muc("cong-nghe", ten="Công nghệ", nguon=[RSS], kenh_dang=[KENH_DANG])
    # Tiêu đề chứa ký tự NUL làm Postgres từ chối lưu Tin.
    the_gioi.nguon.co(RSS, BaiGocMoi("https://bao.example/a", "Bài A", luc(7, 7)))
    the_gioi.llm.se(
        doc("https://bao.example/a"), nop(TinViet("https://bao.example/a", "Bài\x00 A"))
    )

    ky = the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    assert ky.ket_qua is KetQuaKy.HONG
    assert ky.li_do is not None and ky.li_do.startswith("Lỗi không lường trước: ")
    assert the_gioi.chay_ky.lich_su("cong-nghe") == [ky]
    assert the_gioi.kenh_dang.da_nhan == []


def test_chuyen_muc_chua_co_nguon_thi_ky_hong_kem_li_do(the_gioi: TheGioi) -> None:
    the_gioi.them_chuyen_muc("cong-nghe", ten="Công nghệ", nguon=[], kenh_dang=[KENH_DANG])

    ky = the_gioi.chay_ky.chay("cong-nghe", luc(7, 8))

    assert ky.ket_qua is KetQuaKy.HONG
    assert ky.li_do == "Chuyên mục chưa có Nguồn nào"
