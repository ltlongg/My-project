"""Ảnh đại diện của một trang: ảnh trang tự khai trong thẻ meta để mạng xã hội hiển thị."""

from html.parser import HTMLParser
from io import BytesIO
from urllib.parse import urljoin

import httpx
from PIL import Image, ImageOps

# Thứ tự ưu tiên của các thẻ khai ảnh đại diện.
PREVIEW_TAGS = ("og:image:secure_url", "og:image", "twitter:image", "twitter:image:src")
# Ảnh nhỏ hơn hoặc dẹt hơn thế này thường là logo hay dải quảng cáo, không phải ảnh của bài.
MIN_SIDE = 200
MAX_ASPECT_RATIO = 3
# Telegram nhận ảnh tới 10 MB; ảnh được thu nhỏ để cạnh dài nhất không quá mức này.
MAX_DOWNLOAD = 10 * 1024 * 1024
MAX_SIDE = 1280
JPEG_QUALITY = 85


class PreviewError(Exception):
    pass


def preview_image(client: httpx.Client, url: str) -> bytes:
    """Ảnh đại diện của trang ở `url`, dạng JPEG. Ném PreviewError khi không có ảnh dùng được."""
    page = _get(client, url, "trang")
    image_url = _preview_url(page.text, str(page.url))
    if image_url is None:
        raise PreviewError("Trang không khai ảnh đại diện")
    return to_jpeg(_get(client, image_url, "ảnh đại diện").content)


def to_jpeg(data: bytes) -> bytes:
    """Đổi một ảnh bất kì sang JPEG đủ nhỏ để gửi đi. Ném PreviewError khi ảnh không dùng được."""
    try:
        with Image.open(BytesIO(data)) as opened:
            image = ImageOps.exif_transpose(opened)
            image.load()
    except Exception as error:
        raise PreviewError(f"Không đọc được ảnh đại diện ({type(error).__name__})") from None
    width, height = image.size
    if min(width, height) < MIN_SIDE or max(width, height) > MAX_ASPECT_RATIO * min(width, height):
        raise PreviewError(f"Ảnh đại diện {width}×{height} quá nhỏ hoặc quá dẹt")
    if image.mode != "RGB":
        # Phần trong suốt thành nền trắng thay vì nền đen.
        rgba = image.convert("RGBA")
        image = Image.new("RGB", rgba.size, "white")
        image.paste(rgba, mask=rgba.getchannel("A"))
    image.thumbnail((MAX_SIDE, MAX_SIDE))
    output = BytesIO()
    image.save(output, "JPEG", quality=JPEG_QUALITY)
    return output.getvalue()


def _get(client: httpx.Client, url: str, what: str) -> httpx.Response:
    try:
        response = client.get(url, follow_redirects=True)
    except httpx.HTTPError as error:
        raise PreviewError(f"Không tải được {what} ({type(error).__name__})") from None
    if response.is_error:
        raise PreviewError(f"Tải {what} bị trả về mã {response.status_code}")
    if len(response.content) > MAX_DOWNLOAD:
        raise PreviewError(f"{what.capitalize()} quá lớn")
    return response


def _preview_url(html: str, page_url: str) -> str | None:
    parser = _MetaParser()
    parser.feed(html)
    for tag in PREVIEW_TAGS:
        if parser.meta.get(tag):
            return urljoin(page_url, parser.meta[tag])
    return None


class _MetaParser(HTMLParser):
    """Gom nội dung các thẻ meta theo `property` hoặc `name`; thẻ đầu tiên của mỗi tên thắng."""

    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta":
            return
        attributes = dict(attrs)
        name = (attributes.get("property") or attributes.get("name") or "").lower()
        content = (attributes.get("content") or "").strip()
        if name and content:
            self.meta.setdefault(name, content)
