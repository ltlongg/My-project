"""Bộ thu thập RSS, test bằng feed thật đã ghi lại ở tests/fixtures; không gọi mạng."""

from datetime import datetime
from pathlib import Path

import httpx
import pytest

from siftly.collectors import NewArticle
from siftly.collectors.rss import MAX_DESCRIPTION, RssCollectError, RssCollector
from tests.conftest import at

FIXTURES = Path(__file__).parent / "fixtures"
VNEXPRESS = "https://vnexpress.net/rss/khoa-hoc-cong-nghe.rss"
THE_VERGE = "https://www.theverge.com/rss/index.xml"


def serving_file(file_name: str) -> httpx.Client:
    """Một client mà mọi lời gọi đều nhận nội dung của file mẫu."""
    content = (FIXTURES / file_name).read_bytes()
    return httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, content=content, headers={"content-type": "application/xml; charset=utf-8"}
            )
        )
    )


def test_reads_rss_feed_into_articles_with_title_link_and_publish_time() -> None:
    collector = RssCollector(serving_file("vnexpress_science_tech.rss"))

    articles = collector.collect(VNEXPRESS, at(1, 0))

    assert len(articles) == 60
    assert articles[0] == NewArticle(
        url="https://vnexpress.net/mo-hinh-cua-openai-giai-mat-thu-217-nam-cua-napoleon-5129006.html",
        title="Mô hình của OpenAI giải mật thư 217 năm của Napoleon",
        published_at=at(7, 19),
        # Mô tả trong feed có kèm ảnh và link; chỉ giữ phần chữ.
        description=(
            "Mô hình GPT-6 Astra của OpenAI chỉ mất 6 giờ để phá giải bức mật thư từng khiến các "
            "chuyên gia đau đầu suốt hàng trăm năm."
        ),
    )
    assert articles[-1].url == (
        "https://vnexpress.net/tp-hcm-du-kien-ho-tro-den-7-ty-dong-cho-du-an-phu-tro-ban-dan-5127911.html"
    )
    assert articles[-1].title == "TP HCM dự kiến hỗ trợ đến 7 tỷ đồng cho dự án phụ trợ bán dẫn"
    assert articles[-1].published_at == datetime.fromisoformat("2026-10-03T10:06:30+07:00")


def test_only_returns_articles_published_after_since() -> None:
    collector = RssCollector(serving_file("vnexpress_science_tech.rss"))

    articles = collector.collect(VNEXPRESS, at(7, 8))

    # Feed mẫu có 9 mục ghi giờ sau 08:00 ngày 07/10; mục ghi đúng 08:00 thuộc về Kỳ trước.
    assert len(articles) == 9
    titles = {article.title for article in articles}
    assert "Nhà khoa học đầu tiên 'độc chiếm' giải Nobel Vật lý sau 34 năm" in titles  # 09:53
    assert "Bản đồ 3D dẫn đường đặt stent động mạch chủ bị tách" not in titles  # 08:00


def test_reads_atom_feed() -> None:
    collector = RssCollector(serving_file("theverge.atom"))

    articles = collector.collect(THE_VERGE, at(1, 0))

    assert len(articles) == 10
    first = articles[0]
    assert first.url == (
        "https://www.theverge.com/games/1006448/titanfall-2-vr-mod-circuitlord-jordan-juarez"
    )
    assert first.title == "A free mod for Titanfall 2 makes it one of the best VR games ever"
    assert first.published_at == datetime.fromisoformat("2026-10-07T12:15:00-04:00")
    # Mô tả dài được cắt còn phần đầu.
    assert first.description is not None
    assert first.description.startswith("Titanfall has a special place in my heart.")
    assert len(first.description) <= MAX_DESCRIPTION


def test_html_entities_in_title_and_description_are_decoded() -> None:
    # Thanh Niên để thực thể HTML trong CDATA, nên feed gửi "h&uacute;t" thay vì "hút".
    collector = RssCollector(serving_file("thanhnien_tech.rss"))

    [first, _] = collector.collect("https://thanhnien.vn/rss/cong-nghe.rss", at(1, 0))

    assert first.title == "Robot hút bụi có thể tiết lộ những gì về cuộc sống gia đình?"
    assert first.description == (
        "Robot hút bụi có thể thu thập hình ảnh, dữ liệu không gian và thói quen sinh hoạt, làm "
        "dấy lên lo ngại về quyền riêng tư."
    )


def test_follows_source_redirects() -> None:
    # VnExpress chuyển /rss/so-hoa.rss sang /rss/khoa-hoc-cong-nghe.rss bằng mã 302.
    content = (FIXTURES / "vnexpress_science_tech.rss").read_bytes()

    def server(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/rss/so-hoa.rss":
            return httpx.Response(302, headers={"location": VNEXPRESS})
        return httpx.Response(200, content=content)

    collector = RssCollector(httpx.Client(transport=httpx.MockTransport(server)))

    assert len(collector.collect("https://vnexpress.net/rss/so-hoa.rss", at(1, 0))) == 60


def test_server_error_status_raises_readable_error() -> None:
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(503)))

    with pytest.raises(RssCollectError, match=f"{VNEXPRESS} trả về mã 503"):
        RssCollector(client).collect(VNEXPRESS, at(1, 0))


def test_connection_failure_raises_readable_error() -> None:
    def offline(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    client = httpx.Client(transport=httpx.MockTransport(offline))

    with pytest.raises(RssCollectError, match=f"Không kết nối được tới {VNEXPRESS}"):
        RssCollector(client).collect(VNEXPRESS, at(1, 0))


def test_url_that_is_not_a_feed_raises_readable_error() -> None:
    web_page = b"<!doctype html><html><head><title>Trang chu</title></head><body></body></html>"
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, content=web_page, headers={"content-type": "text/html"}
            )
        )
    )

    with pytest.raises(RssCollectError, match="không phải là RSS hay Atom"):
        RssCollector(client).collect("https://vnexpress.net/", at(1, 0))
