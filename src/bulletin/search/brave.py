"""Bộ tìm kiếm dùng Brave Search."""

import re
from collections.abc import Sequence
from html import unescape

import httpx

from bulletin.search import RESULT_COUNT, SearchError, SearchResult

# Brave đánh dấu từ khớp trong trích đoạn bằng thẻ HTML.
HTML_TAG = re.compile(r"<[^>]+>")


class BraveSearch:
    def __init__(self, client: httpx.Client, api_key: str) -> None:
        self._client = client
        self._api_key = api_key

    def search(self, query: str) -> Sequence[SearchResult]:
        try:
            response = self._client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": RESULT_COUNT},
                headers={"X-Subscription-Token": self._api_key, "Accept": "application/json"},
            )
        except httpx.HTTPError as error:
            raise SearchError(f"Không kết nối được tới Brave ({type(error).__name__})") from None
        try:
            data = response.json()
        except ValueError:
            data = None
        if response.is_error or not isinstance(data, dict):
            returned = data.get("error") if isinstance(data, dict) else None
            detail = returned.get("detail") if isinstance(returned, dict) else None
            raise SearchError(f"Brave từ chối: {detail or f'mã {response.status_code}'}")
        return [
            SearchResult(
                title=_strip_tags(item.get("title")),
                url=str(item["url"]),
                snippet=_strip_tags(item.get("description")),
            )
            for item in (data.get("web") or {}).get("results") or []
            if item.get("url")
        ]


def _strip_tags(text: object) -> str:
    return unescape(HTML_TAG.sub("", str(text or "")))
