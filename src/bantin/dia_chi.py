"""Chuẩn hoá địa chỉ để nhận ra cùng một Bài gốc dù link được viết khác nhau."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

CONG_MAC_DINH = {"http": 80, "https": 443}
THAM_SO_THEO_DOI = frozenset(
    {"fbclid", "gclid", "dclid", "msclkid", "yclid", "igshid", "mc_cid", "mc_eid", "ref_src"}
)


def chuan_hoa(dia_chi: str) -> str:
    """Bỏ những phần không làm đổi nội dung trang: chữ hoa ở tên miền, tham số theo dõi,
    phần sau dấu #, dấu / ở cuối và cổng mặc định."""
    dia_chi = dia_chi.strip()
    phan = urlsplit(dia_chi)
    try:
        cong = phan.port
    except ValueError:
        return dia_chi

    giao_thuc = phan.scheme.lower()
    may_chu = (phan.hostname or "").lower()
    if cong is not None and cong != CONG_MAC_DINH.get(giao_thuc):
        may_chu = f"{may_chu}:{cong}"
    tham_so = sorted(
        (ten, gia_tri)
        for ten, gia_tri in parse_qsl(phan.query, keep_blank_values=True)
        if not ten.lower().startswith("utm_") and ten.lower() not in THAM_SO_THEO_DOI
    )
    return urlunsplit((giao_thuc, may_chu, phan.path.rstrip("/"), urlencode(tham_so), ""))
