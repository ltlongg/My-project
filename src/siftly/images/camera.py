"""Chụp ảnh theo thứ tự: ảnh chụp trang, rồi ảnh đại diện, rồi không ảnh."""

import logging

import httpx

from siftly.images import Capture, ImageKind, Screenshotter
from siftly.images.preview import preview_image

log = logging.getLogger(__name__)


class ArticleCamera:
    def __init__(self, screenshotter: Screenshotter, client: httpx.Client) -> None:
        self._screenshotter = screenshotter
        self._client = client

    def capture(self, url: str) -> Capture:
        failures: list[str] = []
        try:
            return Capture(ImageKind.SCREENSHOT, self._screenshotter.screenshot(url))
        except Exception as error:
            log.info("Không chụp được %s: %s", url, error)
            failures.append(f"Không chụp được trang: {error}")
        try:
            return Capture(ImageKind.PREVIEW, preview_image(self._client, url), tuple(failures))
        except Exception as error:
            log.info("Không lấy được ảnh đại diện của %s: %s", url, error)
            failures.append(f"Không lấy được ảnh đại diện: {error}")
        return Capture(ImageKind.NONE, None, tuple(failures))
