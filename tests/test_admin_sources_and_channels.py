"""Trang quản lí: Nguồn và Kênh đăng, test tại điểm "API trang quản lí" cùng Chạy Kỳ."""

from datetime import datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from siftly.collectors import NewArticle
from siftly.collectors.rss import RssCollectError
from siftly.models import RunOutcome
from siftly.publishers.telegram import TelegramPublishError
from tests.conftest import FakeClock, World, at
from tests.test_admin_api import create, sections
from tests.test_scheduler import CHANNEL, OTHER_CHANNEL, RSS, published_titles, three_articles

OTHER_RSS = "https://bao-khac.example/rss"
VNEXPRESS = {
    "kind": "rss",
    "name": "VnExpress",
    "url": "https://vnexpress.net/rss/tin-moi-nhat.rss",
}
GROUP = {"kind": "telegram", "name": "Nhóm gia đình", "address": "-1001234567890"}


def add_source(admin: TestClient, **fields: Any) -> dict[str, Any]:
    response = admin.post("/api/sources", json={**VNEXPRESS, **fields})
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


def add_channel(admin: TestClient, **fields: Any) -> dict[str, Any]:
    response = admin.post("/api/channels", json={**GROUP, **fields})
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


def listed(admin: TestClient, path: str) -> list[dict[str, Any]]:
    response = admin.get(path)
    assert response.status_code == 200, response.text
    found: list[dict[str, Any]] = response.json()
    return found


def by_url(admin: TestClient, url: str) -> dict[str, Any]:
    [source] = [source for source in listed(admin, "/api/sources") if source["url"] == url]
    return source


def by_address(admin: TestClient, address: str) -> dict[str, Any]:
    [channel] = [c for c in listed(admin, "/api/channels") if c["address"] == address]
    return channel


def fetched_at(source: dict[str, Any]) -> datetime | None:
    value = source["last_fetched_at"]
    return None if value is None else datetime.fromisoformat(value)


def section_id(admin: TestClient, slug: str) -> int:
    [section] = [section for section in sections(admin) if section["slug"] == slug]
    found: int = section["id"]
    return found


# Các loại


def test_the_add_screens_learn_the_kinds_from_the_api(admin: TestClient) -> None:
    source_kinds = listed(admin, "/api/sources/kinds")
    channel_kinds = listed(admin, "/api/channels/kinds")

    assert [(kind["kind"], kind["label"]) for kind in source_kinds] == [("rss", "RSS")]
    assert [(kind["kind"], kind["label"]) for kind in channel_kinds] == [("telegram", "Telegram")]
    for kind in (*source_kinds, *channel_kinds):
        assert set(kind) == {"kind", "label", "address_label", "placeholder", "hint"}
        assert all(kind.values())


# Nguồn


def test_adding_a_source_stores_it_attached_to_its_sections(admin: TestClient) -> None:
    news, finance = create(admin)["id"], create(admin, name="Tài chính")["id"]

    created = add_source(admin, section_ids=[finance, news])

    assert created == {
        "id": created["id"],
        **VNEXPRESS,
        "is_enabled": True,
        "section_ids": [news, finance],
        "last_fetched_at": None,
        "last_error": None,
        "recent_articles": 0,
    }
    assert listed(admin, "/api/sources") == [created]
    assert admin.get(f"/api/sources/{created['id']}").json() == created


def test_trying_a_source_shows_a_few_of_its_newest_articles_and_stores_nothing(
    world: World, admin: TestClient
) -> None:
    world.collector.has(
        VNEXPRESS["url"],
        *(
            NewArticle(
                f"https://vnexpress.net/bai-{number}",
                f"Bài {number}",
                at(7, number),
                description=f"Mô tả {number}",
            )
            for number in range(1, 8)
        ),
        NewArticle("https://vnexpress.net/khong-gio", "Bài không ghi giờ"),
    )

    response = admin.post("/api/sources/test", json={"kind": "rss", "url": VNEXPRESS["url"]})

    assert response.status_code == 200
    result = response.json()
    assert (result["total"], result["error"]) == (8, None)
    assert [article["title"] for article in result["articles"]] == [
        "Bài 7",
        "Bài 6",
        "Bài 5",
        "Bài 4",
        "Bài 3",
    ]
    assert result["articles"][0] == {
        "title": "Bài 7",
        "url": "https://vnexpress.net/bai-7",
        "published_at": at(7, 7).isoformat(),
        "description": "Mô tả 7",
    }
    assert world.stored_article_count() == 0
    assert listed(admin, "/api/sources") == []


def test_trying_a_source_that_does_not_work_shows_why(world: World, admin: TestClient) -> None:
    url = "https://vnexpress.net/khong-co.rss"
    world.collector.fail(url, RssCollectError(f"{url} trả về mã 404"))

    response = admin.post("/api/sources/test", json={"kind": "rss", "url": url})

    assert response.status_code == 200
    assert response.json() == {"articles": [], "total": 0, "error": f"{url} trả về mã 404"}


def test_trying_an_empty_source_says_it_has_no_articles(admin: TestClient) -> None:
    response = admin.post("/api/sources/test", json={"kind": "rss", "url": OTHER_RSS})

    assert response.json() == {"articles": [], "total": 0, "error": None}


@pytest.mark.parametrize(
    ("fields", "errors"),
    [
        ({"name": " "}, {"name": "Cần điền"}),
        ({"name": "x" * 81}, {"name": "Dài quá 80 ký tự"}),
        ({"url": ""}, {"url": "Cần điền"}),
        ({"url": "vnexpress.net/rss"}, {"url": "Địa chỉ bắt đầu bằng http:// hoặc https://"}),
        (
            {"url": "https:// có khoảng trắng"},
            {"url": "Địa chỉ bắt đầu bằng http:// hoặc https://"},
        ),
        ({"kind": "fax"}, {"kind": "Giá trị không hợp lệ"}),
        ({"section_ids": [999]}, {"section_ids": "Không có Chuyên mục này"}),
        ({"section_ids": ["một"]}, {"section_ids": "Giá trị không hợp lệ"}),
    ],
)
def test_invalid_sources_are_refused_with_a_message_per_field(
    admin: TestClient, fields: dict[str, Any], errors: dict[str, str]
) -> None:
    response = admin.post("/api/sources", json={**VNEXPRESS, **fields})

    assert response.status_code == 422
    assert response.json() == {"detail": "Dữ liệu chưa hợp lệ", "fields": errors}
    assert listed(admin, "/api/sources") == []


def test_trying_an_invalid_address_is_refused_before_fetching(
    world: World, admin: TestClient
) -> None:
    response = admin.post("/api/sources/test", json={"kind": "rss", "url": "vnexpress.net"})

    assert response.status_code == 422
    assert response.json()["fields"] == {"url": "Địa chỉ bắt đầu bằng http:// hoặc https://"}
    assert world.collector.fetched == []


def test_the_same_address_cannot_be_added_twice(admin: TestClient) -> None:
    first = add_source(admin)
    other = add_source(admin, name="Báo khác", url=OTHER_RSS)

    for response in (
        admin.post("/api/sources", json={**VNEXPRESS, "name": "Trùng"}),
        admin.patch(f"/api/sources/{other['id']}", json={"url": VNEXPRESS["url"]}),
    ):
        assert response.status_code == 422
        assert response.json()["fields"] == {"url": "Đã có Nguồn VnExpress với địa chỉ này"}
    assert listed(admin, "/api/sources") == [first, other]
    # Giữ nguyên địa chỉ của chính nó không phải là trùng.
    assert admin.patch(f"/api/sources/{first['id']}", json=VNEXPRESS).status_code == 200


def test_editing_a_source_changes_only_what_was_sent(admin: TestClient) -> None:
    news, finance = create(admin)["id"], create(admin, name="Tài chính")["id"]
    created = add_source(admin, section_ids=[news])

    response = admin.patch(
        f"/api/sources/{created['id']}",
        json={"name": "VnExpress mới nhất", "section_ids": [finance]},
    )

    assert response.status_code == 200
    edited = {**created, "name": "VnExpress mới nhất", "section_ids": [finance]}
    assert response.json() == edited
    assert listed(admin, "/api/sources") == [edited]

    admin.patch(f"/api/sources/{created['id']}", json={"url": OTHER_RSS, "section_ids": []})
    assert listed(admin, "/api/sources") == [{**edited, "url": OTHER_RSS, "section_ids": []}]


def test_an_invalid_source_edit_changes_nothing(admin: TestClient) -> None:
    created = add_source(admin, section_ids=[create(admin)["id"]])

    response = admin.patch(
        f"/api/sources/{created['id']}",
        json={"name": "Tên mới", "section_ids": [], "url": "ftp://vnexpress.net"},
    )

    assert response.status_code == 422
    assert listed(admin, "/api/sources") == [created]


def test_turning_a_source_off_and_on_keeps_every_setting(admin: TestClient) -> None:
    created = add_source(admin, section_ids=[create(admin)["id"]])

    off = admin.patch(f"/api/sources/{created['id']}", json={"is_enabled": False}).json()
    assert off == {**created, "is_enabled": False}

    on = admin.patch(f"/api/sources/{created['id']}", json={"is_enabled": True}).json()
    assert on == created


def test_each_source_shows_its_last_fetch_recent_articles_and_last_error(
    world: World, admin: TestClient, api_clock: FakeClock
) -> None:
    world.add_section("tech", name="Công nghệ", sources=[RSS, OTHER_RSS], channels=[CHANNEL])
    world.collector.has(
        RSS,
        *three_articles("Bài", at(7, 7)),
        NewArticle("https://bao.example/cu", "Bài cũ", at(7, 7) - timedelta(days=8)),
    )
    world.collector.fail(OTHER_RSS, RssCollectError(f"{OTHER_RSS} trả về mã 500"))
    world.runner.collect(at(7, 7))
    api_clock.now = at(7, 9)

    working, broken = by_url(admin, RSS), by_url(admin, OTHER_RSS)

    # Bài gốc cũ đã quá 7 ngày nên không tính là gần đây.
    assert (fetched_at(working), working["last_error"], working["recent_articles"]) == (
        at(7, 7),
        None,
        3,
    )
    assert (fetched_at(broken), broken["last_error"], broken["recent_articles"]) == (
        at(7, 7),
        f"{OTHER_RSS} trả về mã 500",
        0,
    )

    # Nguồn lấy lại được thì hết lỗi.
    world.collector.has(OTHER_RSS)
    world.runner.collect(at(7, 8))
    assert by_url(admin, OTHER_RSS)["last_error"] is None

    api_clock.now = at(7, 7) + timedelta(days=7)
    assert by_url(admin, RSS)["recent_articles"] == 0


def test_a_source_in_two_sections_serves_both_and_its_articles_are_stored_once(
    world: World, admin: TestClient
) -> None:
    news = create(admin, name="Thời sự", publish_time="08:00", is_paused=False)["id"]
    finance = create(admin, name="Tài chính", publish_time="12:00", is_paused=False)["id"]
    add_source(admin, url=RSS, section_ids=[news, finance])
    add_channel(admin, address=CHANNEL, section_ids=[news])
    add_channel(admin, name="Nhóm tài chính", address=OTHER_CHANNEL, section_ids=[finance])
    world.collector.has(RSS, *three_articles("Bài", at(7, 7)))

    world.runner.run("thoi-su", at(7, 8))
    world.runner.run("tai-chinh", at(7, 12))

    titles = ["Bài 1", "Bài 2", "Bài 3"]
    assert [
        (address, bulletin.section, [story.title for story in bulletin.stories])
        for address, bulletin in world.publisher.received
    ] == [(CHANNEL, "Thời sự", titles), (OTHER_CHANNEL, "Tài chính", titles)]
    assert world.stored_article_count() == 3


def test_a_source_turned_off_is_not_collected_and_adds_no_candidates(
    world: World, admin: TestClient
) -> None:
    world.add_section("tech", name="Công nghệ", sources=[RSS, OTHER_RSS], channels=[CHANNEL])
    world.collector.has(RSS, *three_articles("Bài", at(7, 7)))
    world.collector.has(OTHER_RSS, *three_articles("Bài báo khác", at(7, 7)))
    # Bài gốc của Nguồn thu thập trước khi tắt cũng không vào Kỳ.
    world.runner.collect(at(7, 7))
    world.collector.fetched.clear()

    off = admin.patch(f"/api/sources/{by_url(admin, OTHER_RSS)['id']}", json={"is_enabled": False})
    assert off.status_code == 200
    world.runner.collect(at(7, 7, 30))
    world.runner.run("tech", at(7, 8))

    assert world.collector.fetched == [RSS, RSS]
    assert published_titles(world) == [["Bài 1", "Bài 2", "Bài 3"]]
    candidate_urls = [url for candidate in world.stored_candidates() for url in candidate]
    assert sorted(candidate_urls) == sorted(a.url for a in three_articles("Bài", at(7, 7)))


def test_a_section_whose_sources_are_all_off_fails_its_run(world: World, admin: TestClient) -> None:
    world.add_section("tech", name="Công nghệ", sources=[RSS], channels=[CHANNEL])
    world.collector.has(RSS, *three_articles("Bài", at(7, 7)))
    admin.patch(f"/api/sources/{by_url(admin, RSS)['id']}", json={"is_enabled": False})

    run = world.runner.run("tech", at(7, 8))

    assert (run.outcome, run.reason) == (
        RunOutcome.FAILED,
        "Chuyên mục chưa có Nguồn nào đang bật",
    )
    assert world.collector.fetched == []


def test_an_unknown_source_is_not_found(admin: TestClient) -> None:
    for response in (
        admin.get("/api/sources/999"),
        admin.patch("/api/sources/999", json={"name": "VnExpress"}),
    ):
        assert response.status_code == 404
        assert response.json() == {"detail": "Không có Nguồn này"}


# Kênh đăng


def test_adding_a_channel_stores_it_attached_to_its_sections(admin: TestClient) -> None:
    news, finance = create(admin)["id"], create(admin, name="Tài chính")["id"]

    created = add_channel(admin, section_ids=[news, finance])

    assert created == {
        "id": created["id"],
        **GROUP,
        "is_enabled": True,
        "section_ids": [news, finance],
    }
    assert listed(admin, "/api/channels") == [created]
    assert admin.get(f"/api/channels/{created['id']}").json() == created


def test_sending_a_test_message_reaches_the_channel(world: World, admin: TestClient) -> None:
    response = admin.post(
        "/api/channels/test", json={"kind": "telegram", "address": GROUP["address"]}
    )

    assert response.status_code == 200
    assert response.json() == {"error": None}
    [(address, text)] = world.publisher.tests_received
    assert address == GROUP["address"]
    assert "thử" in text
    # Tin nhắn thử không phải là một Bản tin.
    assert world.publisher.received == []


def test_a_test_message_that_cannot_be_sent_shows_why(world: World, admin: TestClient) -> None:
    world.publisher.fail(
        GROUP["address"], TelegramPublishError("Telegram từ chối: Bad Request: chat not found")
    )

    response = admin.post(
        "/api/channels/test", json={"kind": "telegram", "address": GROUP["address"]}
    )

    assert response.json() == {"error": "Telegram từ chối: Bad Request: chat not found"}
    assert world.publisher.tests_received == []


@pytest.mark.parametrize(
    ("fields", "errors"),
    [
        ({"name": ""}, {"name": "Cần điền"}),
        ({"address": " "}, {"address": "Cần điền"}),
        (
            {"address": "nhóm gia đình"},
            {"address": "Mã là một số, như -1001234567890, hoặc @ten_kenh"},
        ),
        (
            {"address": "https://t.me/abc"},
            {"address": "Mã là một số, như -1001234567890, hoặc @ten_kenh"},
        ),
        ({"kind": "zalo"}, {"kind": "Giá trị không hợp lệ"}),
        ({"section_ids": [999]}, {"section_ids": "Không có Chuyên mục này"}),
    ],
)
def test_invalid_channels_are_refused_with_a_message_per_field(
    admin: TestClient, fields: dict[str, Any], errors: dict[str, str]
) -> None:
    response = admin.post("/api/channels", json={**GROUP, **fields})

    assert response.status_code == 422
    assert response.json() == {"detail": "Dữ liệu chưa hợp lệ", "fields": errors}
    assert listed(admin, "/api/channels") == []


@pytest.mark.parametrize("address", ["-1001234567890", "123456789", "@ban_tin_cong_nghe"])
def test_chat_ids_and_public_channel_names_are_accepted(admin: TestClient, address: str) -> None:
    assert add_channel(admin, address=address)["address"] == address


def test_the_same_chat_cannot_be_added_twice(admin: TestClient) -> None:
    add_channel(admin)

    response = admin.post("/api/channels", json={**GROUP, "name": "Trùng"})

    assert response.status_code == 422
    assert response.json()["fields"] == {"address": "Đã có Kênh đăng Nhóm gia đình với mã này"}


def test_editing_and_turning_a_channel_off_and_on_keeps_the_rest(admin: TestClient) -> None:
    news = create(admin)["id"]
    created = add_channel(admin, section_ids=[news])

    edited = admin.patch(
        f"/api/channels/{created['id']}", json={"name": "Nhóm bạn", "address": "-1009"}
    ).json()
    assert edited == {**created, "name": "Nhóm bạn", "address": "-1009"}

    off = admin.patch(f"/api/channels/{created['id']}", json={"is_enabled": False}).json()
    assert off == {**edited, "is_enabled": False}
    on = admin.patch(f"/api/channels/{created['id']}", json={"is_enabled": True}).json()
    assert on == edited
    assert listed(admin, "/api/channels") == [edited]


def test_a_section_publishes_to_every_channel_that_is_on(world: World, admin: TestClient) -> None:
    world.add_section("tech", name="Công nghệ", sources=[RSS], channels=[CHANNEL])
    tech = section_id(admin, "tech")
    add_channel(admin, name="Nhóm thứ hai", address=OTHER_CHANNEL, section_ids=[tech])
    third = add_channel(admin, name="Nhóm thứ ba", address="-1003", section_ids=[tech])
    admin.patch(f"/api/channels/{third['id']}", json={"is_enabled": False})
    world.collector.has(RSS, *three_articles("Bài", at(7, 7)))

    world.runner.run("tech", at(7, 8))

    assert [address for address, _ in world.publisher.received] == [CHANNEL, OTHER_CHANNEL]

    admin.patch(f"/api/channels/{third['id']}", json={"is_enabled": True})
    admin.patch(f"/api/channels/{by_address(admin, CHANNEL)['id']}", json={"is_enabled": False})
    world.collector.has(RSS, *three_articles("Bài hôm sau", at(8, 7)))
    world.runner.run("tech", at(8, 8))

    assert [address for address, _ in world.publisher.received[2:]] == [OTHER_CHANNEL, "-1003"]


def test_a_section_whose_channels_are_all_off_fails_its_run(
    world: World, admin: TestClient
) -> None:
    world.add_section("tech", name="Công nghệ", sources=[RSS], channels=[CHANNEL])
    world.collector.has(RSS, *three_articles("Bài", at(7, 7)))
    admin.patch(f"/api/channels/{by_address(admin, CHANNEL)['id']}", json={"is_enabled": False})

    run = world.runner.run("tech", at(7, 8))

    assert (run.outcome, run.reason) == (
        RunOutcome.FAILED,
        "Chuyên mục chưa có Kênh đăng nào đang bật",
    )
    assert world.publisher.received == []


def test_an_unknown_channel_is_not_found(admin: TestClient) -> None:
    for response in (
        admin.get("/api/channels/999"),
        admin.patch("/api/channels/999", json={"name": "Nhóm"}),
    ):
        assert response.status_code == 404
        assert response.json() == {"detail": "Không có Kênh đăng này"}
