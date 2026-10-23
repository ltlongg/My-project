"""Bộ thu thập cho Nguồn loại RSS (đọc được cả RSS và Atom)."""

import re
from collections.abc import Sequence
from datetime import UTC, datetime
from html import unescape
from time import struct_time

import feedparser
import httpx

from bulletin.collectors import NewArticle

# Mô tả dài hơn thì cắt; phần đầu là đủ để biết bài nói về chuyện gì.
MAX_DESCRIPTION = 500
HTML_TAG = re.compile(r"<[^>]+>")


class RssCollectError(Exception):
    pass


class RssCollector:
    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def collect(self, url: str, since: datetime) -> Sequence[NewArticle]:
        try:
            response = self._client.get(url, follow_redirects=True)
        except httpx.HTTPError as error:
            raise RssCollectError(f"Không kết nối được tới {url}: {error}") from error
        if response.is_error:
            raise RssCollectError(f"{url} trả về mã {response.status_code}")

        feed = feedparser.parse(
            response.content,
            response_headers={"content-type": response.headers.get("content-type", "")},
        )
        if not feed.version:
            raise RssCollectError(f"{url} không phải là RSS hay Atom")

        articles = []
        for entry in feed.entries:
            link, title = entry.get("link"), _plain_text(entry.get("title", ""))
            if not link or not title:
                continue
            published_at = _to_datetime(
                entry.get("published_parsed") or entry.get("updated_parsed")
            )
            # Mục không ghi giờ xuất bản thì không biết cũ hay mới; để nơi gọi quyết định.
            if published_at is None or published_at > since:
                description = _plain_text(entry.get("summary", ""))[:MAX_DESCRIPTION].strip()
                articles.append(
                    NewArticle(
                        url=link,
                        title=title,
                        published_at=published_at,
                        description=description or None,
                    )
                )
        return articles


def _plain_text(text: str) -> str:
    """Bỏ thẻ HTML, giải mã thực thể HTML và gộp khoảng trắng.

    Có Nguồn để thực thể HTML trong CDATA, nên feedparser trả về nguyên "h&agrave;ng".
    """
    return " ".join(unescape(HTML_TAG.sub(" ", text)).split())


def _to_datetime(utc_time: struct_time | None) -> datetime | None:
    return datetime(*utc_time[:6], tzinfo=UTC) if utc_time else None
