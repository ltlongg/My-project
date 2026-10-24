"""Chuẩn hoá địa chỉ để nhận ra cùng một Bài gốc dù link được viết khác nhau."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

DEFAULT_PORTS = {"http": 80, "https": 443}
TRACKING_PARAMS = frozenset(
    {"fbclid", "gclid", "dclid", "msclkid", "yclid", "igshid", "mc_cid", "mc_eid", "ref_src"}
)


def normalize_url(url: str) -> str:
    """Bỏ những phần không làm đổi nội dung trang: chữ hoa ở tên miền, tham số theo dõi,
    phần sau dấu #, dấu / ở cuối và cổng mặc định."""
    url = url.strip()
    parts = urlsplit(url)
    try:
        port = parts.port
    except ValueError:
        return url

    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    if port is not None and port != DEFAULT_PORTS.get(scheme):
        host = f"{host}:{port}"
    params = sorted(
        (name, value)
        for name, value in parse_qsl(parts.query, keep_blank_values=True)
        if not name.lower().startswith("utm_") and name.lower() not in TRACKING_PARAMS
    )
    return urlunsplit((scheme, host, parts.path.rstrip("/"), urlencode(params), ""))
