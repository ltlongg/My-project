"""Chụp trang bằng Playwright, với Chromium thật và các trang mẫu ở `fixtures/pages/`.

Trang mẫu được trả từ Python qua `context.route`, nên không gọi mạng. Trình duyệt là BROWSER_URL
trong .env (dịch vụ browser trong compose.yaml), để trống thì là Chromium đã cài.

Trên trang mẫu, tiêu đề bài có nền xanh dương, còn những thứ không được lọt vào ảnh có màu thuần
riêng: bảng cookie đỏ, header dính xanh lá, quảng cáo phủ màn hình vàng. Test đếm điểm ảnh theo màu.
"""

from collections.abc import Iterator
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from playwright.sync_api import Browser, BrowserContext, Playwright, Route, sync_playwright

from siftly.config import Settings
from siftly.images.screenshot import (
    VIEWPORT,
    PlaywrightScreenshotter,
    ScreenshotError,
    context_options,
    open_browser,
    screenshot_page,
)

PAGES = Path(__file__).parent / "fixtures" / "pages"
URL = "https://bao.example/bai-mau"

BLUE, RED, GREEN, YELLOW = (0, 0, 255), (255, 0, 0), (0, 255, 0), (255, 255, 0)


@pytest.fixture(scope="module")
def playwright() -> Iterator[Playwright]:
    with sync_playwright() as playwright:
        yield playwright


@pytest.fixture(scope="module")
def browser(playwright: Playwright) -> Iterator[Browser]:
    browser = open_browser(playwright, Settings().browser_url)
    yield browser
    browser.close()


class FakeSite:
    """Đứng thay các trang web: trả trang mẫu theo địa chỉ, ghi lại mọi yêu cầu tới nó."""

    def __init__(self, context: BrowserContext) -> None:
        self.requested: list[str] = []
        self._pages: dict[str, tuple[int, str]] = {}
        self._hanging: set[str] = set()
        context.route("**/*", self._serve)

    def has(self, url: str, page: str, status: int = 200) -> None:
        self._pages[url] = (status, (PAGES / page).read_text(encoding="utf-8"))

    def hangs(self, url: str) -> None:
        """Yêu cầu tới `url` không bao giờ được trả lời."""
        self._hanging.add(url)

    def _serve(self, route: Route) -> None:
        url = route.request.url
        self.requested.append(url)
        if url in self._hanging:
            return
        if url in self._pages:
            status, body = self._pages[url]
            route.fulfill(status=status, body=body, content_type="text/html; charset=utf-8")
        else:
            route.abort()


@pytest.fixture
def context(browser: Browser) -> Iterator[BrowserContext]:
    context = browser.new_context(**context_options(browser))
    yield context
    context.close()


@pytest.fixture
def site(context: BrowserContext) -> FakeSite:
    return FakeSite(context)


def screenshot(context: BrowserContext, url: str = URL, **options: float) -> Image.Image:
    return Image.open(BytesIO(screenshot_page(context.new_page(), url, **options)))


def pixels(
    image: Image.Image, color: tuple[int, int, int], top: float = 0, bottom: float = 1
) -> int:
    """Số điểm ảnh gần với `color`, trong dải từ `top` tới `bottom` của chiều cao ảnh."""
    band = image.convert("RGB").crop(
        (0, int(top * image.height), image.width, int(bottom * image.height))
    )
    total = 0
    for count, pixel in band.getcolors(band.width * band.height) or []:
        assert isinstance(pixel, tuple)
        if all(abs(channel - target) <= 40 for channel, target in zip(pixel, color, strict=True)):
            total += count
    return total


def test_screenshot_shows_headline_at_top_without_cookie_bar_sticky_header_or_overlay(
    site: FakeSite, context: BrowserContext
) -> None:
    site.has(URL, "article.html")

    image = screenshot(context)

    # Khung cỡ điện thoại, mật độ điểm ảnh gấp đôi.
    assert image.format == "JPEG"
    assert image.size == (VIEWPORT["width"] * 2, VIEWPORT["height"] * 2)
    # Tiêu đề nằm ở phần trên của ảnh dù phía trên nó có quảng cáo cao và khối chèn muộn.
    assert pixels(image, BLUE, bottom=0.4) > 0.2 * image.width * image.height * 0.4
    assert pixels(image, RED) < 100
    assert pixels(image, GREEN) < 100
    assert pixels(image, YELLOW) < 100


def test_consent_dialog_over_the_page_is_removed_and_page_scrolls_again(
    site: FakeSite, context: BrowserContext
) -> None:
    site.has(URL, "consent_modal.html")

    image = screenshot(context)

    assert pixels(image, BLUE, bottom=0.4) > 0
    assert pixels(image, RED) < 100


def test_consent_and_ad_scripts_are_not_loaded(site: FakeSite, context: BrowserContext) -> None:
    site.has(URL, "article.html")

    screenshot(context)

    assert site.requested == [URL]


@pytest.mark.parametrize(
    ("page", "status", "expected_error"),
    [
        ("article.html", 403, "Trang trả về mã 403"),
        ("challenge.html", 200, "Trang chặn trình duyệt tự động"),
        ("paywall.html", 200, "Trang có tường phí hoặc lớp phủ che bài"),
        ("no_headline.html", 200, "Không thấy tiêu đề bài trên trang"),
    ],
)
def test_page_that_cannot_show_the_article_is_not_captured(
    site: FakeSite, context: BrowserContext, page: str, status: int, expected_error: str
) -> None:
    site.has(URL, page, status)

    with pytest.raises(ScreenshotError) as error:
        screenshot(context)

    assert str(error.value) == expected_error


def test_page_that_does_not_load_in_time_is_not_captured(
    site: FakeSite, context: BrowserContext
) -> None:
    site.hangs(URL)

    with pytest.raises(ScreenshotError) as error:
        screenshot(context, navigation_timeout=1)

    assert str(error.value) == "Trang mở quá thời gian"


def test_screenshotter_reports_page_that_cannot_be_opened(browser: Browser) -> None:
    # Cổng 9 trên máy của trình duyệt không có gì lắng nghe.
    screenshotter = PlaywrightScreenshotter(lambda: browser)

    with pytest.raises(ScreenshotError) as error:
        screenshotter.screenshot("http://127.0.0.1:9/bai")

    assert str(error.value).startswith("Không mở được trang: ")


def test_screenshotter_reports_browser_that_cannot_be_opened(playwright: Playwright) -> None:
    screenshotter = PlaywrightScreenshotter(
        lambda: playwright.chromium.connect("ws://127.0.0.1:9/", timeout=2000)
    )

    with pytest.raises(ScreenshotError) as error:
        screenshotter.screenshot(URL)

    assert str(error.value).startswith("Không mở được trình duyệt: ")
