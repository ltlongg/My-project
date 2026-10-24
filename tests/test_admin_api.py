"""Trang quản lí: đăng nhập và thiết lập Chuyên mục, test tại điểm "API trang quản lí"."""

import re
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from siftly.admin import create_app
from siftly.admin.auth import COOKIE
from siftly.models import Guideline, Role
from siftly.seed import STARTER_EDITOR_GUIDELINE
from tests.conftest import ADMIN, FakeClock, World, at
from tests.test_scheduler import CHANNEL, RSS, published_titles, three_articles

NEWS = {
    "name": "Thời sự",
    "scope": "Tin trong nước và thế giới: chính sách, kinh tế vĩ mô, sự kiện lớn.",
    "publish_time": "20:00",
    "max_stories": 6,
}


def log_in(api: TestClient, username: str = ADMIN.username, password: str = ADMIN.password) -> int:
    response = api.post("/api/login", json={"username": username, "password": password})
    return response.status_code


def create(admin: TestClient, **fields: Any) -> dict[str, Any]:
    response = admin.post("/api/sections", json={**NEWS, **fields})
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


def sections(admin: TestClient) -> list[dict[str, Any]]:
    response = admin.get("/api/sections")
    assert response.status_code == 200, response.text
    listed: list[dict[str, Any]] = response.json()
    return listed


# Đăng nhập


def test_the_one_account_logs_in_with_the_password_from_the_environment(api: TestClient) -> None:
    assert api.get("/api/session").status_code == 401

    response = api.post("/api/login", json={"username": ADMIN.username, "password": ADMIN.password})

    assert response.status_code == 204
    cookie = response.headers["set-cookie"]
    assert "httponly" in cookie.lower() and "samesite=strict" in cookie.lower()
    assert api.get("/api/session").json() == {"username": ADMIN.username}
    assert api.get("/api/sections").status_code == 200


@pytest.mark.parametrize(
    ("username", "password"),
    [
        (ADMIN.username, "mat-khau-sai"),
        ("nguoi-khac", ADMIN.password),
        (ADMIN.username, ""),
        (ADMIN.username, ADMIN.password.upper()),
    ],
)
def test_wrong_username_or_password_is_refused(
    api: TestClient, username: str, password: str
) -> None:
    response = api.post("/api/login", json={"username": username, "password": password})

    assert response.status_code == 401
    assert response.json() == {"detail": "Sai tên đăng nhập hoặc mật khẩu"}
    assert COOKIE not in api.cookies
    assert api.get("/api/sections").status_code == 401


def test_every_api_path_except_logging_in_is_refused_without_logging_in(api: TestClient) -> None:
    app: FastAPI = api.app  # type: ignore[assignment]
    routes = [
        (method.upper(), path)
        for path, methods in app.openapi()["paths"].items()
        for method in methods
        if path not in ("/api/login", "/api/logout")
    ]
    assert ("GET", "/api/sections") in routes

    for method, path in routes:
        response = api.request(method, re.sub(r"\{\w+\}", "1", path), json={})
        assert response.status_code == 401, (method, path)
        assert response.json() == {"detail": "Chưa đăng nhập"}


def test_a_made_up_session_cookie_is_refused(api: TestClient) -> None:
    api.cookies.set(COOKIE, "ma-tu-che")

    assert api.get("/api/sections").status_code == 401


def test_logging_out_ends_the_session(admin: TestClient) -> None:
    token = admin.cookies[COOKIE]

    assert admin.post("/api/logout").status_code == 204

    assert admin.get("/api/sections").status_code == 401
    # Cookie cũ, nếu ai đó còn giữ, cũng hết dùng được.
    admin.cookies.set(COOKIE, token)
    assert admin.get("/api/sections").status_code == 401


def test_a_session_lasts_thirty_days(admin: TestClient, api_clock: FakeClock) -> None:
    api_clock.now += timedelta(days=30) - timedelta(minutes=1)
    assert admin.get("/api/sections").status_code == 200

    api_clock.now += timedelta(minutes=1)
    assert admin.get("/api/sections").status_code == 401

    assert log_in(admin) == 204
    assert admin.get("/api/sections").status_code == 200


# Chuyên mục


def test_creating_a_section_stores_its_settings(admin: TestClient) -> None:
    created = create(admin)

    assert created == {
        "id": created["id"],
        "slug": "thoi-su",
        **NEWS,
        # Chưa có Nguồn và Kênh đăng nên chưa chạy.
        "is_paused": True,
    }
    assert sections(admin) == [created]
    assert admin.get(f"/api/sections/{created['id']}").json() == created


def test_a_new_section_has_a_starter_guideline_for_the_editor(
    admin: TestClient, session_factory: sessionmaker[Session]
) -> None:
    created = create(admin)

    with session_factory() as session:
        guidelines = session.scalars(
            select(Guideline).where(Guideline.section_id == created["id"])
        ).all()
    assert [(g.role, g.version, g.is_active, g.content) for g in guidelines] == [
        (Role.EDITOR, 1, True, STARTER_EDITOR_GUIDELINE)
    ]


def test_section_codes_come_from_the_name_and_never_repeat(admin: TestClient) -> None:
    codes = [
        create(admin, name="Thời sự")["slug"],
        create(admin, name="Thời sự")["slug"],
        create(admin, name="Tài chính & Đầu tư")["slug"],
        create(admin, name="Đời sống")["slug"],
        create(admin, name="???")["slug"],
    ]

    assert codes == ["thoi-su", "thoi-su-2", "tai-chinh-dau-tu", "doi-song", "chuyen-muc"]


@pytest.mark.parametrize(
    ("fields", "errors"),
    [
        ({"name": "   "}, {"name": "Cần điền"}),
        ({"scope": ""}, {"scope": "Cần điền"}),
        ({"name": "x" * 81}, {"name": "Dài quá 80 ký tự"}),
        ({"publish_time": "25:00"}, {"publish_time": "Giờ phát có dạng HH:MM, ví dụ 08:00"}),
        ({"publish_time": "8h"}, {"publish_time": "Giờ phát có dạng HH:MM, ví dụ 08:00"}),
        ({"max_stories": 2}, {"max_stories": "Số Tin mỗi Bản tin từ 3 đến 10"}),
        ({"max_stories": 11}, {"max_stories": "Số Tin mỗi Bản tin từ 3 đến 10"}),
        ({"max_stories": "nhiều"}, {"max_stories": "Giá trị không hợp lệ"}),
    ],
)
def test_invalid_settings_are_refused_with_a_message_per_field(
    admin: TestClient, fields: dict[str, Any], errors: dict[str, str]
) -> None:
    response = admin.post("/api/sections", json={**NEWS, **fields})

    assert response.status_code == 422
    assert response.json() == {"detail": "Dữ liệu chưa hợp lệ", "fields": errors}
    assert sections(admin) == []


def test_a_new_section_needs_every_setting(admin: TestClient) -> None:
    response = admin.post("/api/sections", json={"name": "Thời sự"})

    assert response.status_code == 422
    assert response.json()["fields"] == {
        "scope": "Cần điền",
        "publish_time": "Cần điền",
        "max_stories": "Cần điền",
    }


def test_editing_a_section_changes_only_what_was_sent(admin: TestClient) -> None:
    created = create(admin)

    response = admin.patch(
        f"/api/sections/{created['id']}",
        json={"name": "Thời sự tối", "publish_time": "21:30", "max_stories": 5},
    )

    assert response.status_code == 200
    edited = {
        **created,
        "name": "Thời sự tối",
        "publish_time": "21:30",
        "max_stories": 5,
    }
    # Mã không đổi theo tên, để `siftly run thoi-su` vẫn chạy.
    assert response.json() == edited
    assert sections(admin) == [edited]

    admin.patch(f"/api/sections/{created['id']}", json={"scope": "Chỉ tin trong nước."})
    assert sections(admin) == [{**edited, "scope": "Chỉ tin trong nước."}]


def test_an_invalid_edit_changes_nothing(admin: TestClient) -> None:
    created = create(admin)

    response = admin.patch(
        f"/api/sections/{created['id']}", json={"name": "Thời sự tối", "max_stories": 0}
    )

    assert response.status_code == 422
    assert sections(admin) == [created]


def test_pausing_and_resuming_keeps_every_setting(admin: TestClient) -> None:
    created = create(admin, is_paused=False)
    assert created["is_paused"] is False

    paused = admin.patch(f"/api/sections/{created['id']}", json={"is_paused": True}).json()
    assert paused == {**created, "is_paused": True}

    resumed = admin.patch(f"/api/sections/{created['id']}", json={"is_paused": False}).json()
    assert resumed == created
    assert sections(admin) == [created]


def test_an_unknown_section_is_not_found(admin: TestClient) -> None:
    for response in (
        admin.get("/api/sections/999"),
        admin.patch("/api/sections/999", json={"name": "Thời sự"}),
    ):
        assert response.status_code == 404
        assert response.json() == {"detail": "Không có Chuyên mục này"}


# Thay đổi trên trang và Kỳ kế tiếp


def tech_section_id(admin: TestClient) -> int:
    [section] = [section for section in sections(admin) if section["slug"] == "tech"]
    section_id: int = section["id"]
    return section_id


def test_a_new_publish_time_applies_from_the_next_run_without_restarting(
    world: World, admin: TestClient
) -> None:
    world.add_section("tech", name="Công nghệ", sources=[RSS], channels=[CHANNEL])
    world.collector.has(RSS, *three_articles("Bài", at(7, 7)))
    world.tick(at(7, 7))

    admin.patch(f"/api/sections/{tech_section_id(admin)}", json={"publish_time": "12:00"})

    world.tick(at(7, 8))
    assert published_titles(world) == []
    world.tick(at(7, 12))
    assert published_titles(world) == [["Bài 1", "Bài 2", "Bài 3"]]


def test_pausing_on_the_page_stops_the_next_run_and_resuming_brings_it_back(
    world: World, admin: TestClient
) -> None:
    world.add_section("tech", name="Công nghệ", sources=[RSS], channels=[CHANNEL])
    section = f"/api/sections/{tech_section_id(admin)}"
    world.collector.has(RSS, *three_articles("Bài", at(7, 7)))
    world.tick(at(7, 7))

    admin.patch(section, json={"is_paused": True})
    world.tick(at(7, 8))
    assert published_titles(world) == []
    assert world.runner.history("tech") == []

    admin.patch(section, json={"is_paused": False})
    world.collector.has(RSS, *three_articles("Bài hôm sau", at(8, 7)))
    world.tick(at(8, 8))
    assert published_titles(world) == [["Bài hôm sau 1", "Bài hôm sau 2", "Bài hôm sau 3"]]


def test_scope_and_story_count_set_on_the_page_reach_the_next_run(
    world: World, admin: TestClient
) -> None:
    world.add_section("tech", name="Công nghệ", sources=[RSS], channels=[CHANNEL])
    world.collector.has(RSS, *three_articles("Bài", at(7, 7)))
    scope = "Chỉ tin về chip bán dẫn và nhà máy chip."

    admin.patch(f"/api/sections/{tech_section_id(admin)}", json={"scope": scope, "max_stories": 4})
    world.runner.run("tech", at(7, 8))

    assert scope in world.rater.text_received(0)
    assert scope in world.llm.text_received(0)
    assert "đến 4 Tin" in world.llm.text_received(0)


# Ứng dụng React


def test_the_app_is_served_for_every_page_but_not_for_the_api(
    session_factory: sessionmaker[Session], tmp_path: Path
) -> None:
    (tmp_path / "index.html").write_text("<div id=root></div>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path.parent / "secret.txt").write_text("bí mật")

    with TestClient(create_app(session_factory, ADMIN, web_dir=tmp_path)) as client:
        for page in ("/", "/sections", "/sections/1"):
            response = client.get(page)
            assert (response.status_code, response.text) == (200, "<div id=root></div>")
        assert client.get("/assets/app.js").text == "console.log(1)"
        for escape in ("/..%2fsecret.txt", "/%2e%2e/secret.txt"):
            assert client.get(escape).text == "<div id=root></div>"
        assert client.get("/api/khong-co").status_code == 404
        assert client.get("/api/sections").status_code == 401
