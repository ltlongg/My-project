"""Bộ thu thập RSS, test bằng feed thật đã ghi lại ở tests/fixtures; không gọi mạng."""

from datetime import datetime
from pathlib import Path

import httpx
import pytest

from bulletin.collectors import BaiGocMoi
from bulletin.collectors.rss import MO_TA_TOI_DA, LoiThuThapRss, ThuThapRss
from tests.conftest import luc

DU_LIEU = Path(__file__).parent / "fixtures"
VNEXPRESS = "https://vnexpress.net/rss/khoa-hoc-cong-nghe.rss"
THE_VERGE = "https://www.theverge.com/rss/index.xml"


def tra_ve_file(ten_file: str) -> httpx.Client:
    """Một client mà mọi lời gọi đều nhận nội dung của file mẫu."""
    noi_dung = (DU_LIEU / ten_file).read_bytes()
    return httpx.Client(
        transport=httpx.MockTransport(
            lambda yeu_cau: httpx.Response(
                200, content=noi_dung, headers={"content-type": "application/xml; charset=utf-8"}
            )
        )
    )


def test_doc_feed_rss_thanh_bai_goc_co_tieu_de_link_va_gio_xuat_ban() -> None:
    bo_thu_thap = ThuThapRss(tra_ve_file("vnexpress_khoa_hoc_cong_nghe.rss"))

    bai_goc = bo_thu_thap.thu_thap(VNEXPRESS, luc(1, 0))

    assert len(bai_goc) == 60
    assert bai_goc[0] == BaiGocMoi(
        dia_chi="https://vnexpress.net/mo-hinh-cua-openai-giai-mat-thu-217-nam-cua-napoleon-5129006.html",
        tieu_de="Mô hình của OpenAI giải mật thư 217 năm của Napoleon",
        xuat_ban_luc=luc(7, 19),
        # Mô tả trong feed có kèm ảnh và link; chỉ giữ phần chữ.
        mo_ta=(
            "Mô hình GPT-6 Astra của OpenAI chỉ mất 6 giờ để phá giải bức mật thư từng khiến các "
            "chuyên gia đau đầu suốt hàng trăm năm."
        ),
    )
    assert bai_goc[-1].dia_chi == (
        "https://vnexpress.net/tp-hcm-du-kien-ho-tro-den-7-ty-dong-cho-du-an-phu-tro-ban-dan-5127911.html"
    )
    assert bai_goc[-1].tieu_de == "TP HCM dự kiến hỗ trợ đến 7 tỷ đồng cho dự án phụ trợ bán dẫn"
    assert bai_goc[-1].xuat_ban_luc == datetime.fromisoformat("2026-10-03T10:06:30+07:00")


def test_chi_tra_ve_bai_goc_xuat_ban_sau_moc() -> None:
    bo_thu_thap = ThuThapRss(tra_ve_file("vnexpress_khoa_hoc_cong_nghe.rss"))

    bai_goc = bo_thu_thap.thu_thap(VNEXPRESS, luc(7, 8))

    # Feed mẫu có 9 mục ghi giờ sau 08:00 ngày 07/10; mục ghi đúng 08:00 thuộc về Kỳ trước.
    assert len(bai_goc) == 9
    tieu_de = {bai.tieu_de for bai in bai_goc}
    assert "Nhà khoa học đầu tiên 'độc chiếm' giải Nobel Vật lý sau 34 năm" in tieu_de  # 09:53
    assert "Bản đồ 3D dẫn đường đặt stent động mạch chủ bị tách" not in tieu_de  # 08:00


def test_doc_feed_atom() -> None:
    bo_thu_thap = ThuThapRss(tra_ve_file("theverge.atom"))

    bai_goc = bo_thu_thap.thu_thap(THE_VERGE, luc(1, 0))

    assert len(bai_goc) == 10
    dau = bai_goc[0]
    assert dau.dia_chi == (
        "https://www.theverge.com/games/1006448/titanfall-2-vr-mod-circuitlord-jordan-juarez"
    )
    assert dau.tieu_de == "A free mod for Titanfall 2 makes it one of the best VR games ever"
    assert dau.xuat_ban_luc == datetime.fromisoformat("2026-10-07T12:15:00-04:00")
    # Mô tả dài được cắt còn phần đầu.
    assert dau.mo_ta is not None
    assert dau.mo_ta.startswith("Titanfall has a special place in my heart.")
    assert len(dau.mo_ta) <= MO_TA_TOI_DA


def test_thuc_the_html_trong_tieu_de_va_mo_ta_duoc_giai_ma() -> None:
    # Thanh Niên để thực thể HTML trong CDATA, nên feed gửi "h&uacute;t" thay vì "hút".
    bo_thu_thap = ThuThapRss(tra_ve_file("thanhnien_cong_nghe.rss"))

    [dau, _] = bo_thu_thap.thu_thap("https://thanhnien.vn/rss/cong-nghe.rss", luc(1, 0))

    assert dau.tieu_de == "Robot hút bụi có thể tiết lộ những gì về cuộc sống gia đình?"
    assert dau.mo_ta == (
        "Robot hút bụi có thể thu thập hình ảnh, dữ liệu không gian và thói quen sinh hoạt, làm "
        "dấy lên lo ngại về quyền riêng tư."
    )


def test_di_theo_chuyen_huong_cua_nguon() -> None:
    # VnExpress chuyển /rss/so-hoa.rss sang /rss/khoa-hoc-cong-nghe.rss bằng mã 302.
    noi_dung = (DU_LIEU / "vnexpress_khoa_hoc_cong_nghe.rss").read_bytes()

    def may_chu(yeu_cau: httpx.Request) -> httpx.Response:
        if yeu_cau.url.path == "/rss/so-hoa.rss":
            return httpx.Response(302, headers={"location": VNEXPRESS})
        return httpx.Response(200, content=noi_dung)

    bo_thu_thap = ThuThapRss(httpx.Client(transport=httpx.MockTransport(may_chu)))

    assert len(bo_thu_thap.thu_thap("https://vnexpress.net/rss/so-hoa.rss", luc(1, 0))) == 60


def test_may_chu_tra_ma_loi_thi_bao_loi_de_hieu() -> None:
    client = httpx.Client(transport=httpx.MockTransport(lambda yeu_cau: httpx.Response(503)))

    with pytest.raises(LoiThuThapRss, match=f"{VNEXPRESS} trả về mã 503"):
        ThuThapRss(client).thu_thap(VNEXPRESS, luc(1, 0))


def test_khong_ket_noi_duoc_thi_bao_loi_de_hieu() -> None:
    def mat_mang(yeu_cau: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=yeu_cau)

    client = httpx.Client(transport=httpx.MockTransport(mat_mang))

    with pytest.raises(LoiThuThapRss, match=f"Không kết nối được tới {VNEXPRESS}"):
        ThuThapRss(client).thu_thap(VNEXPRESS, luc(1, 0))


def test_dia_chi_khong_phai_feed_thi_bao_loi_de_hieu() -> None:
    trang_web = b"<!doctype html><html><head><title>Trang chu</title></head><body></body></html>"
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda yeu_cau: httpx.Response(
                200, content=trang_web, headers={"content-type": "text/html"}
            )
        )
    )

    with pytest.raises(LoiThuThapRss, match="không phải là RSS hay Atom"):
        ThuThapRss(client).thu_thap("https://vnexpress.net/", luc(1, 0))
