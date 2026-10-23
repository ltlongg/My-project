"""Bộ tìm kiếm dùng Tavily."""

from collections.abc import Sequence

import httpx

from bulletin.search import RESULT_COUNT, SearchError, SearchResult


class TavilySearch:
    def __init__(self, client: httpx.Client, api_key: str) -> None:
        self._client = client
        self._api_key = api_key

    def search(self, query: str) -> Sequence[SearchResult]:
        try:
            response = self._client.post(
                "https://api.tavily.com/search",
                json={"query": query, "max_results": RESULT_COUNT},
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
        except httpx.HTTPError as error:
            raise SearchError(f"Không kết nối được tới Tavily ({type(error).__name__})") from None
        try:
            data = response.json()
        except ValueError:
            data = None
        if response.is_error or not isinstance(data, dict):
            detail = data.get("detail") if isinstance(data, dict) else None
            message = detail.get("error") if isinstance(detail, dict) else detail
            raise SearchError(f"Tavily từ chối: {message or f'mã {response.status_code}'}")
        return [
            SearchResult(
                title=str(item.get("title") or ""),
                url=str(item["url"]),
                snippet=str(item.get("content") or ""),
            )
            for item in data.get("results") or []
            if item.get("url")
        ]
