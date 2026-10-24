"""Hai bộ tìm kiếm, test bằng phản hồi đã ghi lại từ Tavily và Brave; không gọi mạng."""

import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from siftly.search import Searcher, SearchError
from siftly.search.brave import BraveSearch
from siftly.search.tavily import TavilySearch

FIXTURES = Path(__file__).parent / "fixtures"
API_KEY = "secret-key"
QUERY = "pin thể rắn mật độ năng lượng"

MakeSearcher = Callable[[httpx.Client, str], Searcher]


class FakeService:
    """Đứng thay dịch vụ tìm kiếm: ghi lại lời gọi và trả về phản hồi mẫu."""

    def __init__(self, status: int, response_file: str) -> None:
        self.requests: list[httpx.Request] = []
        self._status, self._content = status, (FIXTURES / response_file).read_bytes()
        self.client = httpx.Client(transport=httpx.MockTransport(self._respond))

    def _respond(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(
            self._status, content=self._content, headers={"content-type": "application/json"}
        )


def test_tavily_returns_title_url_and_snippet() -> None:
    service = FakeService(200, "tavily_search_ok.json")

    results = TavilySearch(service.client, API_KEY).search(QUERY)

    [request] = service.requests
    assert str(request.url) == "https://api.tavily.com/search"
    assert request.headers["authorization"] == f"Bearer {API_KEY}"
    assert json.loads(request.content)["query"] == QUERY
    assert len(results) == 3
    assert results[0].title == "Pin Lithium có thể đạt mật độ năng lượng 700 Wh/kg nhờ ..."
    assert results[0].url.startswith("https://vov.vn/the-gioi/pin-lithium-co-the-dat")
    assert results[0].snippet.startswith("Pin Lithium có thể đạt mật độ năng lượng 700 Wh/kg")


def test_brave_returns_title_url_and_snippet_without_html_tags() -> None:
    service = FakeService(200, "brave_search_ok.json")

    results = BraveSearch(service.client, API_KEY).search(QUERY)

    [request] = service.requests
    assert request.url.host == "api.search.brave.com"
    assert request.url.params["q"] == QUERY
    assert request.headers["x-subscription-token"] == API_KEY
    assert len(results) == 3
    assert results[0].title == "Pin thể rắn là gì? Khái niệm và ưu điểm của pin thể rắn | VinFast"
    assert results[0].url == (
        "https://vinfastauto.com/vn_vi/pin-the-ran-la-gi-khai-niem-va-uu-diem-cua-pin-the-ran"
    )
    # Brave bọc từ khớp trong thẻ <strong>.
    assert "gấp 2.5 lần pin Lithium-ion" in results[0].snippet
    assert "<" not in results[0].snippet


@pytest.mark.parametrize(
    ("make", "status", "response_file", "expected_error"),
    [
        (
            TavilySearch,
            401,
            "tavily_invalid_key.json",
            "Tavily từ chối: Unauthorized: missing or invalid API key.",
        ),
        (
            BraveSearch,
            422,
            "brave_invalid_key.json",
            "Brave từ chối: The provided subscription token is invalid.",
        ),
    ],
)
def test_service_rejection_raises_error_with_reason(
    make: MakeSearcher, status: int, response_file: str, expected_error: str
) -> None:
    service = FakeService(status, response_file)

    with pytest.raises(SearchError) as error:
        make(service.client, API_KEY).search(QUERY)

    assert str(error.value) == expected_error


@pytest.mark.parametrize(
    ("make", "expected_error"),
    [
        (TavilySearch, "Không kết nối được tới Tavily (ConnectError)"),
        (BraveSearch, "Không kết nối được tới Brave (ConnectError)"),
    ],
)
def test_connection_error_does_not_leak_api_key(make: MakeSearcher, expected_error: str) -> None:
    def offline(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"không tới được {request.url} với {request.headers}")

    client = httpx.Client(transport=httpx.MockTransport(offline))

    with pytest.raises(SearchError) as error:
        make(client, API_KEY).search(QUERY)

    assert str(error.value) == expected_error
    assert error.value.__cause__ is None
