"""Bộ lấy nội dung bài báo, test bằng một trang đã ghi lại; không gọi mạng."""

from pathlib import Path

import httpx
import pytest

from bulletin.extractors.article import ArticleExtractor, ExtractError

FIXTURES = Path(__file__).parent / "fixtures"
ARTICLE_URL = "https://vnexpress.net/honor-600s-5g-dien-thoai-sieu-ben-pin-8-100-mah-5130044.html"


def client_returning(status: int, content: bytes) -> httpx.Client:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status, content=content, headers={"content-type": "text/html; charset=UTF-8"}
        )

    return httpx.Client(transport=httpx.MockTransport(respond))


def test_extracts_article_body_and_drops_page_chrome() -> None:
    client = client_returning(200, (FIXTURES / "vnexpress_article.html").read_bytes())

    full_text = ArticleExtractor(client).extract(ARTICLE_URL)

    assert full_text.startswith("Honor 600S 5G - điện thoại siêu bền, pin 8.100 mAh")
    assert "Giá khởi điểm của máy là 10,49 triệu đồng cho bản RAM 6 GB" in full_text
    # Thanh điều hướng, ô bình luận và mã nguồn trang không lọt vào toàn văn.
    assert "Đăng nhập" not in full_text
    assert "Ý kiến" not in full_text
    assert "<" not in full_text


def test_page_without_article_body_raises_error() -> None:
    page = "<html><body><p>Vui lòng đăng nhập để đọc tiếp.</p></body></html>".encode()

    with pytest.raises(ExtractError, match="Không trích được thân bài"):
        ArticleExtractor(client_returning(200, page)).extract(ARTICLE_URL)


def test_server_error_status_raises_error_with_status() -> None:
    with pytest.raises(ExtractError, match="trả về mã 403"):
        ArticleExtractor(client_returning(403, b"Forbidden")).extract(ARTICLE_URL)


def test_connection_failure_raises_error() -> None:
    def offline(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("mất mạng", request=request)

    client = httpx.Client(transport=httpx.MockTransport(offline))

    with pytest.raises(ExtractError, match="Không kết nối được"):
        ArticleExtractor(client).extract(ARTICLE_URL)
