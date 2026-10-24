"""Chụp trang bằng Playwright: khung cỡ điện thoại, cuộn tới tiêu đề bài, không bảng cookie."""

from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from playwright.sync_api import Browser, Page, Playwright, Route
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

PREPARE_PAGE = (Path(__file__).parent / "prepare_page.js").read_text(encoding="utf-8")
# Khung cỡ điện thoại với mật độ điểm ảnh gấp đôi. Telegram thu ảnh về bề ngang màn hình điện
# thoại, nên chữ trong ảnh chụp khung máy tính nhỏ quá không đọc được.
VIEWPORT = {"width": 480, "height": 720}
DEVICE_SCALE_FACTOR = 2
JPEG_QUALITY = 75
# Thời gian chờ, theo giây. Hết thời gian chờ trang tải xong hay đứng yên thì vẫn chụp; chỉ hết
# thời gian mở trang mới là không chụp được.
NAVIGATION_TIMEOUT = 20.0
LOAD_TIMEOUT = 8.0
SETTLE_TIMEOUT = 3.0
# Chờ header kiểu "cuộn ngược thì hiện lại" hiện ra, để lần ẩn cuối bắt được nó.
REAPPEAR_WAIT = 0.5
# Bảng hỏi cookie và quảng cáo phổ biến: không tải thì không phải gỡ, và trang tải nhanh hơn.
BLOCKED_HOSTS = (
    "cookielaw.org",
    "onetrust.com",
    "cookiebot.com",
    "consensu.org",
    "privacy-mgmt.com",
    "privacy-center.org",
    "usercentrics.eu",
    "trustarc.com",
    "doubleclick.net",
    "googlesyndication.com",
    "adnxs.com",
    "amazon-adsystem.com",
)
PAGE_FAILURES = {
    "bot": "Trang chặn trình duyệt tự động",
    "wall": "Trang có tường phí hoặc lớp phủ che bài",
    "no_headline": "Không thấy tiêu đề bài trên trang",
}


class ScreenshotError(Exception):
    pass


def open_browser(playwright: Playwright, url: str | None) -> Browser:
    """Chromium: kết nối tới Playwright server ở `url`, để trống thì tự mở Chromium đã cài."""
    return playwright.chromium.connect(url) if url else playwright.chromium.launch()


def context_options(browser: Browser) -> dict[str, Any]:
    """Thiết lập cho phiên trình duyệt của mỗi lần chụp."""
    major_version = browser.version.split(".")[0]
    return {
        "viewport": VIEWPORT,
        "device_scale_factor": DEVICE_SCALE_FACTOR,
        "locale": "vi-VN",
        "timezone_id": "Asia/Ho_Chi_Minh",
        # Chromium không giao diện tự xưng là "HeadlessChrome", và nhiều trang chặn ngay vì thế.
        "user_agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/{major_version}.0.0.0 Safari/537.36"
        ),
    }


class PlaywrightScreenshotter:
    """Mỗi lần chụp trong một phiên trình duyệt mới. Trình duyệt chỉ được mở ở lần chụp đầu, để
    Kỳ không cần chụp thì không tốn công mở."""

    def __init__(self, open_browser: Callable[[], Browser]) -> None:
        self._open_browser = open_browser
        self._browser: Browser | None = None

    def screenshot(self, url: str) -> bytes:
        try:
            if self._browser is None or not self._browser.is_connected():
                self._browser = self._open_browser()
            context = self._browser.new_context(**context_options(self._browser))
        except PlaywrightError as error:
            raise ScreenshotError(f"Không mở được trình duyệt: {_first_line(error)}") from None
        try:
            return screenshot_page(context.new_page(), url)
        finally:
            context.close()

    def close(self) -> None:
        if self._browser is not None:
            self._browser.close()


def screenshot_page(page: Page, url: str, navigation_timeout: float = NAVIGATION_TIMEOUT) -> bytes:
    """Mở `url` trong `page`, dọn trang và chụp phần đầu bài thành ảnh JPEG.

    Ném ScreenshotError khi trang trả mã lỗi, chặn trình duyệt tự động, có tường phí, không có
    tiêu đề bài, hoặc mở quá thời gian.
    """
    page.route("**/*", _block_distractions)
    try:
        response = page.goto(url, wait_until="domcontentloaded", timeout=navigation_timeout * 1000)
        if response is not None and response.status >= 400:
            raise ScreenshotError(f"Trang trả về mã {response.status}")
        _wait_for(page, "load", LOAD_TIMEOUT)
        _prepare(page, "clean")
        _wait_for(page, "networkidle", SETTLE_TIMEOUT)
        _prepare(page, "settle")
        page.wait_for_timeout(REAPPEAR_WAIT * 1000)
        _prepare(page, "settle")
        return page.screenshot(type="jpeg", quality=JPEG_QUALITY)
    except PlaywrightTimeoutError:
        raise ScreenshotError("Trang mở quá thời gian") from None
    except PlaywrightError as error:
        raise ScreenshotError(f"Không mở được trang: {_first_line(error)}") from None


def _block_distractions(route: Route) -> None:
    host = urlsplit(route.request.url).hostname or ""
    blocked = any(host == name or host.endswith(f".{name}") for name in BLOCKED_HOSTS)
    if blocked or route.request.resource_type == "media":
        route.abort()
    else:
        route.fallback()


def _wait_for(page: Page, state: Any, timeout: float) -> None:
    with suppress(PlaywrightTimeoutError):
        page.wait_for_load_state(state, timeout=timeout * 1000)


def _prepare(page: Page, step: str) -> None:
    result = page.evaluate(PREPARE_PAGE, step)
    if result.get("error"):
        raise ScreenshotError(PAGE_FAILURES[result["error"]])


def _first_line(error: Exception) -> str:
    return (str(error).splitlines() or [type(error).__name__])[0]
