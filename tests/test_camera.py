"""Chụp ảnh theo thứ tự ảnh chụp trang, ảnh đại diện, không ảnh; trang và ảnh là dữ liệu đã ghi
lại, không gọi mạng."""

from collections.abc import Callable
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image

from siftly.images import ImageKind
from siftly.images.camera import ArticleCamera
from siftly.images.screenshot import ScreenshotError

FIXTURES = Path(__file__).parent / "fixtures"
ARTICLE = "https://vnexpress.net/bai-mau-4800000.html"
# Ảnh đại diện mà trang mẫu khai trong thẻ og:image.
PREVIEW = (
    "https://i2-vnexpress.vnecdn.net/2026/10/08/21505-1791453610.jpg"
    "?w=1200&h=675&q=100&dpr=1&fit=crop&s=D1WK9z2UGx5uc8OdkeFtpw"
)


def image(width: int, height: int, mode: str = "RGB", format: str = "JPEG") -> bytes:
    output = BytesIO()
    Image.new(mode, (width, height), (200, 30, 30, 0) if mode == "RGBA" else (200, 30, 30)).save(
        output, format
    )
    return output.getvalue()


def opened(data: bytes) -> Image.Image:
    return Image.open(BytesIO(data))


class FakeScreenshotter:
    def __init__(self, result: bytes | Exception) -> None:
        self.result = result
        self.urls: list[str] = []

    def screenshot(self, url: str) -> bytes:
        self.urls.append(url)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeWeb:
    """Đứng thay các trang và ảnh: địa chỉ nào test đã đặt thì trả về, còn lại là 404."""

    def __init__(self) -> None:
        self.requested: list[str] = []
        self._pages: dict[str, Callable[[], httpx.Response]] = {}
        self.client = httpx.Client(transport=httpx.MockTransport(self._respond))

    def has(self, url: str, content: bytes, content_type: str, status: int = 200) -> None:
        self._pages[url] = lambda: httpx.Response(
            status, content=content, headers={"content-type": content_type}
        )

    def has_page(self, url: str, html: str | bytes) -> None:
        self.has(url, html.encode() if isinstance(html, str) else html, "text/html; charset=utf-8")

    def _respond(self, request: httpx.Request) -> httpx.Response:
        self.requested.append(str(request.url))
        respond = self._pages.get(str(request.url))
        return respond() if respond else httpx.Response(404)


def vnexpress(web: FakeWeb) -> FakeWeb:
    web.has_page(ARTICLE, (FIXTURES / "vnexpress_article.html").read_bytes())
    return web


def test_screenshot_is_used_when_page_can_be_captured() -> None:
    web = vnexpress(FakeWeb())
    screenshotter = FakeScreenshotter(b"anh chup")

    capture = ArticleCamera(screenshotter, web.client).capture(ARTICLE)

    assert (capture.kind, capture.data, capture.failures) == (ImageKind.SCREENSHOT, b"anh chup", ())
    assert screenshotter.urls == [ARTICLE]
    assert web.requested == []


def test_page_that_cannot_be_captured_falls_back_to_its_preview_image_as_jpeg() -> None:
    web = vnexpress(FakeWeb())
    web.has(PREVIEW, image(2400, 1350, format="PNG"), "image/png")

    capture = ArticleCamera(FakeScreenshotter(ScreenshotError("Trang trả về mã 403")), web.client)
    result = capture.capture(ARTICLE)

    assert result.kind is ImageKind.PREVIEW
    assert result.failures == ("Không chụp được trang: Trang trả về mã 403",)
    assert result.data is not None
    preview = opened(result.data)
    # Thu nhỏ để cạnh dài nhất không quá 1280, đổi sang JPEG.
    assert (preview.format, preview.size) == ("JPEG", (1280, 720))


def test_relative_twitter_image_is_used_when_page_has_no_og_image() -> None:
    web = FakeWeb()
    web.has_page(
        "https://bao.example/tin/a",
        '<html><head><meta name="twitter:image" content="/anh/a.webp"></head></html>',
    )
    web.has("https://bao.example/anh/a.webp", image(800, 450, format="WEBP"), "image/webp")

    result = ArticleCamera(FakeScreenshotter(ScreenshotError("x")), web.client).capture(
        "https://bao.example/tin/a"
    )

    assert result.kind is ImageKind.PREVIEW
    assert result.data is not None and opened(result.data).format == "JPEG"


def test_transparent_preview_image_gets_white_background() -> None:
    web = FakeWeb()
    web.has_page(
        "https://bao.example/a",
        '<meta property="og:image" content="https://bao.example/a.png">',
    )
    web.has("https://bao.example/a.png", image(600, 400, mode="RGBA", format="PNG"), "image/png")

    result = ArticleCamera(FakeScreenshotter(ScreenshotError("x")), web.client).capture(
        "https://bao.example/a"
    )

    assert result.data is not None
    assert opened(result.data).convert("RGB").getpixel((300, 200)) == (255, 255, 255)


def test_no_usable_image_means_story_goes_out_without_image_with_both_reasons() -> None:
    web = FakeWeb()
    web.has_page("https://bao.example/khong-anh", "<html><head><title>Bài</title></head></html>")

    result = ArticleCamera(
        FakeScreenshotter(ScreenshotError("Trang chặn trình duyệt tự động")), web.client
    ).capture("https://bao.example/khong-anh")

    assert (result.kind, result.data) == (ImageKind.NONE, None)
    assert result.failures == (
        "Không chụp được trang: Trang chặn trình duyệt tự động",
        "Không lấy được ảnh đại diện: Trang không khai ảnh đại diện",
    )


def preview_failure(set_up: Callable[[FakeWeb], None]) -> str:
    web = vnexpress(FakeWeb())
    set_up(web)
    result = ArticleCamera(FakeScreenshotter(ScreenshotError("x")), web.client).capture(ARTICLE)
    assert (result.kind, result.data) == (ImageKind.NONE, None)
    return result.failures[-1]


def test_small_logo_as_preview_image_is_not_used() -> None:
    failure = preview_failure(lambda web: web.has(PREVIEW, image(150, 150), "image/jpeg"))

    assert failure == "Không lấy được ảnh đại diện: Ảnh đại diện 150×150 quá nhỏ hoặc quá dẹt"


def test_banner_strip_as_preview_image_is_not_used() -> None:
    failure = preview_failure(lambda web: web.has(PREVIEW, image(1500, 300), "image/jpeg"))

    assert failure == "Không lấy được ảnh đại diện: Ảnh đại diện 1500×300 quá nhỏ hoặc quá dẹt"


def test_preview_image_address_that_is_not_an_image_is_not_used() -> None:
    failure = preview_failure(lambda web: web.has_page(PREVIEW, "<html>Không tìm thấy</html>"))

    assert (
        failure
        == "Không lấy được ảnh đại diện: Không đọc được ảnh đại diện (UnidentifiedImageError)"
    )


def test_missing_preview_image_is_not_used() -> None:
    failure = preview_failure(lambda web: None)

    assert failure == "Không lấy được ảnh đại diện: Tải ảnh đại diện bị trả về mã 404"


def test_page_that_cannot_be_loaded_has_no_preview_image() -> None:
    web = FakeWeb()

    result = ArticleCamera(FakeScreenshotter(ScreenshotError("x")), web.client).capture(ARTICLE)

    assert result.failures[-1] == "Không lấy được ảnh đại diện: Tải trang bị trả về mã 404"
