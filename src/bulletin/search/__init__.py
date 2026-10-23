"""Tìm kiếm web: mỗi dịch vụ tìm kiếm là một bộ tìm kiếm cùng giao diện."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

RESULT_COUNT = 5


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str


class Searcher(Protocol):
    def search(self, query: str) -> Sequence[SearchResult]:
        """Trả về vài kết quả đầu cho `query`. Ném lỗi khi không tìm được."""
        ...


class SearchError(Exception):
    """Dịch vụ tìm kiếm từ chối hoặc không tới được; thông điệp không chứa khoá."""
