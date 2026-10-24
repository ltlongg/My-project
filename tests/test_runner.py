"""Test tại điểm "Chạy Kỳ": khẳng định về thứ tới Kênh đăng giả và thứ được lưu."""

from datetime import datetime, timedelta

import pytest

from siftly.collectors import NewArticle
from siftly.models import RunOutcome
from siftly.publishers import BulletinContent, StoryContent
from tests.conftest import DraftStory, World, at, read, submit

RSS = "https://bao.example/rss"
CHANNEL = "-1001"


def test_run_publishes_bulletin_of_stories_about_new_articles_with_links(world: World) -> None:
    world.add_section("tech", name="Công nghệ", sources=[RSS], channels=[CHANNEL])
    world.collector.has(
        RSS,
        NewArticle("https://bao.example/a", "Bài A", at(7, 6)),
        NewArticle("https://bao.example/b", "Bài B", at(7, 7)),
        NewArticle("https://bao.example/c", "Bài C", at(7, 5)),
    )

    run = world.runner.run("tech", at(7, 8))

    assert run.outcome is RunOutcome.PUBLISHED
    assert world.publisher.received == [
        (
            CHANNEL,
            BulletinContent(
                section="Công nghệ",
                run_at=at(7, 8),
                stories=(
                    StoryContent("Bài B", "Tóm tắt của Bài B.", "https://bao.example/b"),
                    StoryContent("Bài A", "Tóm tắt của Bài A.", "https://bao.example/a"),
                    StoryContent("Bài C", "Tóm tắt của Bài C.", "https://bao.example/c"),
                ),
            ),
        )
    ]


def published_titles(world: World) -> list[list[str]]:
    """Tiêu đề các Tin của từng Bản tin đã tới Kênh đăng giả, theo thứ tự nhận."""
    return [[story.title for story in bulletin.stories] for _, bulletin in world.publisher.received]


def three_articles(name: str, published_at: datetime) -> list[NewArticle]:
    """Ba Bài gốc "<name> 1" tới "<name> 3", cách nhau một phút, bài 1 mới nhất; đủ để Bản tin
    được phát."""
    return [
        NewArticle(
            f"https://bao.example/{name.replace(' ', '-')}-{number}",
            f"{name} {number}",
            published_at - timedelta(minutes=number),
        )
        for number in (1, 2, 3)
    ]


def test_first_run_only_considers_articles_from_last_24_hours(world: World) -> None:
    world.add_section("tech", name="Công nghệ", sources=[RSS], channels=[CHANNEL])
    world.collector.has(
        RSS,
        NewArticle("https://bao.example/cu", "Bài hôm kia", at(6, 7, 59)),
        *three_articles("Bài hôm qua", at(6, 8, 4)),
    )

    world.runner.run("tech", at(7, 8))

    assert published_titles(world) == [["Bài hôm qua 1", "Bài hôm qua 2", "Bài hôm qua 3"]]


def test_later_run_only_considers_articles_since_previous_bulletin(world: World) -> None:
    world.add_section("tech", name="Công nghệ", sources=[RSS], channels=[CHANNEL])
    morning = three_articles("Bài sáng", at(7, 7))
    afternoon = three_articles("Bài chiều", at(7, 15))
    world.collector.has(RSS, *morning)
    world.runner.run("tech", at(7, 8))

    # Nguồn vẫn còn liệt kê các bài buổi sáng, như một RSS feed thật.
    world.collector.has(RSS, *morning, *afternoon)
    world.runner.run("tech", at(8, 8))

    assert published_titles(world) == [
        ["Bài sáng 1", "Bài sáng 2", "Bài sáng 3"],
        ["Bài chiều 1", "Bài chiều 2", "Bài chiều 3"],
    ]


def test_same_article_under_two_urls_becomes_one_story(world: World) -> None:
    other_rss = "https://tonghop.example/rss"
    world.add_section("tech", name="Công nghệ", sources=[RSS, other_rss], channels=[CHANNEL])
    world.collector.has(
        RSS,
        NewArticle("https://bao.example/tin/a", "Bài A", at(7, 7)),
        *three_articles("Bài khác", at(7, 6)),
    )
    world.collector.has(
        other_rss,
        NewArticle(
            "HTTPS://Bao.Example/tin/a/?utm_source=tonghop&utm_medium=rss#binh-luan",
            "Bài A (qua trang tổng hợp)",
            at(7, 7, 30),
        ),
    )

    world.runner.run("tech", at(7, 8))

    assert published_titles(world) == [["Bài A", "Bài khác 1", "Bài khác 2", "Bài khác 3"]]


def test_no_new_articles_means_not_published(world: World) -> None:
    world.add_section("tech", name="Công nghệ", sources=[RSS], channels=[CHANNEL])
    world.collector.has(RSS, NewArticle("https://bao.example/cu", "Bài tuần trước", at(1, 9)))

    run = world.runner.run("tech", at(7, 8))

    assert run.outcome is RunOutcome.NOT_PUBLISHED
    assert run.reason == "Không có Bài gốc mới"
    assert world.publisher.received == []
    assert world.runner.history("tech") == [run]


def test_all_channels_failing_fails_run_and_articles_are_reconsidered_next_run(
    world: World,
) -> None:
    world.add_section("tech", name="Công nghệ", sources=[RSS], channels=[CHANNEL])
    world.collector.has(RSS, *three_articles("Bài", at(7, 7)))
    world.publisher.fail(CHANNEL, RuntimeError("bot bị chặn khỏi nhóm"))

    failed_run = world.runner.run("tech", at(7, 8))

    assert failed_run.outcome is RunOutcome.FAILED
    assert failed_run.reason == f"Kênh đăng {CHANNEL} lỗi: bot bị chặn khỏi nhóm"
    assert world.runner.history("tech") == [failed_run]

    world.publisher.fix(CHANNEL)
    next_run = world.runner.run("tech", at(7, 8, 30))

    assert next_run.outcome is RunOutcome.PUBLISHED
    assert published_titles(world) == [["Bài 1", "Bài 2", "Bài 3"]]


def test_one_failing_channel_does_not_block_others(world: World) -> None:
    failing_channel = "-1002"
    world.add_section("tech", name="Công nghệ", sources=[RSS], channels=[failing_channel, CHANNEL])
    world.collector.has(RSS, *three_articles("Bài", at(7, 7)))
    world.publisher.fail(failing_channel, RuntimeError("quá thời gian"))

    run = world.runner.run("tech", at(7, 8))

    assert run.outcome is RunOutcome.PUBLISHED
    assert run.reason == f"Kênh đăng {failing_channel} lỗi: quá thời gian"
    assert [address for address, _ in world.publisher.received] == [CHANNEL]


def test_one_failing_source_still_yields_bulletin_from_the_rest(world: World) -> None:
    failing_rss = "https://chet.example/rss"
    world.add_section("tech", name="Công nghệ", sources=[failing_rss, RSS], channels=[CHANNEL])
    world.collector.fail(failing_rss, RuntimeError("máy chủ trả về 503"))
    world.collector.has(RSS, *three_articles("Bài", at(7, 7)))

    run = world.runner.run("tech", at(7, 8))

    assert run.outcome is RunOutcome.PUBLISHED
    assert published_titles(world) == [["Bài 1", "Bài 2", "Bài 3"]]
    assert world.source_errors() == {failing_rss: "máy chủ trả về 503", RSS: None}


def test_all_sources_failing_fails_run(world: World) -> None:
    world.add_section("tech", name="Công nghệ", sources=[RSS], channels=[CHANNEL])
    world.collector.fail(RSS, RuntimeError("mất mạng"))

    run = world.runner.run("tech", at(7, 8))

    assert run.outcome is RunOutcome.FAILED
    assert run.reason == "Không thu thập được Nguồn nào"
    assert world.publisher.received == []


def test_consecutive_runs_do_not_store_duplicate_articles(world: World) -> None:
    world.add_section("tech", name="Công nghệ", sources=[RSS], channels=[CHANNEL])
    world.collector.has(
        RSS,
        NewArticle("https://bao.example/a", "Bài A", at(7, 6)),
        NewArticle("https://bao.example/b", "Bài B", at(7, 7)),
    )

    world.runner.run("tech", at(7, 8))
    world.runner.run("tech", at(7, 9))

    assert world.stored_article_count() == 2


def test_sections_sharing_a_source_have_own_window_and_articles_stored_once(
    world: World,
) -> None:
    finance_channel = "-1002"
    world.add_section("tech", name="Công nghệ", sources=[RSS], channels=[CHANNEL])
    world.add_section("finance", name="Tài chính", sources=[RSS], channels=[finance_channel])
    world.collector.has(RSS, *three_articles("Bài", at(7, 7)))

    world.runner.run("tech", at(7, 8))
    # Các bài đã phát ở Công nghệ nhưng với Tài chính chúng vẫn là mới.
    world.runner.run("finance", at(7, 12))

    titles = ["Bài 1", "Bài 2", "Bài 3"]
    assert [
        (address, bulletin.section, [story.title for story in bulletin.stories])
        for address, bulletin in world.publisher.received
    ] == [(CHANNEL, "Công nghệ", titles), (finance_channel, "Tài chính", titles)]
    assert world.stored_article_count() == 3


def test_section_without_channels_fails_run_with_reason(world: World) -> None:
    world.add_section("tech", name="Công nghệ", sources=[RSS], channels=[])
    world.collector.has(RSS, NewArticle("https://bao.example/a", "Bài A", at(7, 7)))

    run = world.runner.run("tech", at(7, 8))

    assert run.outcome is RunOutcome.FAILED
    assert run.reason == "Chuyên mục chưa có Kênh đăng nào đang bật"


def test_bulletin_is_stored_exactly_as_sent(world: World) -> None:
    world.add_section("tech", name="Công nghệ", sources=[RSS], channels=[CHANNEL])
    world.collector.has(
        RSS,
        NewArticle("https://bao.example/a", "Bài A", at(7, 6)),
        NewArticle("https://bao.example/b", "Bài B", at(7, 7)),
        NewArticle("https://bao.example/c", "Bài C", at(7, 5)),
    )

    world.runner.run("tech", at(7, 8))

    [(_, sent)] = world.publisher.received
    [stored_run] = world.runner.history("tech")
    assert stored_run.outcome is RunOutcome.PUBLISHED
    assert stored_run.bulletin == sent


def test_run_at_without_timezone_is_rejected(world: World) -> None:
    world.add_section("tech", name="Công nghệ", sources=[RSS], channels=[CHANNEL])

    with pytest.raises(ValueError, match="múi giờ"):
        world.runner.run("tech", datetime(2026, 10, 7, 8, 0))

    assert world.runner.history("tech") == []


def test_unexpected_error_still_leaves_failed_run_with_reason(world: World) -> None:
    world.add_section("tech", name="Công nghệ", sources=[RSS], channels=[CHANNEL])
    # Tiêu đề chứa ký tự NUL làm Postgres từ chối lưu Tin.
    world.collector.has(RSS, NewArticle("https://bao.example/a", "Bài A", at(7, 7)))
    world.llm.will(
        read("https://bao.example/a"), submit(DraftStory("https://bao.example/a", "Bài\x00 A"))
    )

    run = world.runner.run("tech", at(7, 8))

    assert run.outcome is RunOutcome.FAILED
    assert run.reason is not None and run.reason.startswith("Lỗi không lường trước: ")
    assert world.runner.history("tech") == [run]
    assert world.publisher.received == []


def test_section_without_sources_fails_run_with_reason(world: World) -> None:
    world.add_section("tech", name="Công nghệ", sources=[], channels=[CHANNEL])

    run = world.runner.run("tech", at(7, 8))

    assert run.outcome is RunOutcome.FAILED
    assert run.reason == "Chuyên mục chưa có Nguồn nào đang bật"
