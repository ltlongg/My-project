"""Lịch, thử lại và thông báo riêng: test tại điểm "Chạy Kỳ" với đồng hồ giả."""

from datetime import UTC, datetime, time, timedelta

import pytest

from siftly.collectors import NewArticle
from siftly.images import Capture
from siftly.models import RunOutcome
from siftly.runner import RunInProgressError
from siftly.scheduler import Scheduler
from tests.conftest import DraftStory, World, at, read, rewrite, submit

RSS = "https://bao.example/rss"
CHANNEL = "-1001"
OTHER_CHANNEL = "-1002"
A, B, C = (f"https://bao.example/{name}" for name in "abc")


class PowerLoss(BaseException):
    """Tiến trình bị dừng giữa chừng: không phải lỗi mà Chạy Kỳ bắt được."""


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


def tech(world: World, channels: tuple[str, ...] = (CHANNEL,), paused: bool = False) -> World:
    """Chuyên mục công nghệ phát lúc 8:00, Nguồn có ba Bài gốc mới."""
    world.add_section(
        "tech", name="Công nghệ", sources=[RSS], channels=list(channels), paused=paused
    )
    world.collector.has(RSS, *three_articles("Bài", at(7, 7)))
    return world


def published_titles(world: World) -> list[list[str]]:
    """Tiêu đề các Tin đã tới Kênh đăng giả ở từng lần phát, theo thứ tự nhận."""
    return [[story.title for story in bulletin.stories] for _, bulletin in world.publisher.received]


def test_run_starts_at_publish_time_in_vietnam_time(world: World) -> None:
    tech(world)

    world.tick(at(7, 7, 59))
    assert world.publisher.received == []

    # Đồng hồ của máy chủ chạy theo UTC: 1:00 UTC là 8:00 giờ Việt Nam.
    world.tick(datetime(2026, 10, 7, 1, 0, tzinfo=UTC))

    assert published_titles(world) == [["Bài 1", "Bài 2", "Bài 3"]]
    [run] = world.runner.history("tech")
    assert (run.run_at, run.outcome) == (at(7, 8), RunOutcome.PUBLISHED)
    assert world.notifier.sent == []


def test_each_section_runs_once_a_day_at_its_own_publish_time(world: World) -> None:
    world.add_section("tech", name="Công nghệ", sources=[RSS], channels=[CHANNEL])
    world.add_section(
        "finance",
        name="Tài chính",
        sources=[RSS],
        channels=[OTHER_CHANNEL],
        publish_time=time(12),
    )
    world.collector.has(RSS, *three_articles("Bài", at(7, 7)))

    for moment in (at(7, 8), at(7, 8, 1), at(7, 12), at(7, 12, 1), at(7, 20)):
        world.tick(moment)
    world.collector.has(RSS, *three_articles("Bài hôm sau", at(8, 7)))
    world.tick(at(8, 8))

    assert [(address, bulletin.run_at) for address, bulletin in world.publisher.received] == [
        (CHANNEL, at(7, 8)),
        (OTHER_CHANNEL, at(7, 12)),
        (CHANNEL, at(8, 8)),
    ]


def test_collection_runs_every_hour_and_run_uses_articles_collected_earlier(
    world: World,
) -> None:
    world.add_section("tech", name="Công nghệ", sources=[RSS], channels=[CHANNEL])
    world.collector.has(RSS, NewArticle("https://bao.example/sang-som", "Bài sáng sớm", at(7, 3)))

    world.tick(at(7, 3))
    world.tick(at(7, 3, 30))
    assert world.collector.fetched == [RSS]
    world.tick(at(7, 4))
    assert world.collector.fetched == [RSS, RSS]

    # Bài sáng sớm đã trôi khỏi RSS feed trước giờ phát.
    world.collector.has(RSS, *three_articles("Bài", at(7, 7)))
    world.tick(at(7, 8))

    [titles] = published_titles(world)
    assert sorted(titles) == ["Bài 1", "Bài 2", "Bài 3", "Bài sáng sớm"]


def test_failed_run_is_retried_after_30_minutes_reusing_the_bulletin(world: World) -> None:
    tech(world)
    world.publisher.fail(CHANNEL, RuntimeError("Telegram quá tải"))
    world.tick(at(7, 8))
    [failed] = world.runner.history("tech")
    assert failed.outcome is RunOutcome.FAILED
    editor_calls = len(world.llm.received)

    world.publisher.fix(CHANNEL)
    world.tick(at(7, 8, 29))
    assert world.publisher.received == []
    world.tick(at(7, 8, 30))

    assert published_titles(world) == [["Bài 1", "Bài 2", "Bài 3"]]
    [run] = world.runner.history("tech")
    assert (run.run_at, run.outcome, run.reason, run.attempts) == (
        at(7, 8),
        RunOutcome.PUBLISHED,
        None,
        2,
    )
    # Lần thử lại phát đúng Bản tin đã dựng, không gọi Biên tập lần nữa.
    assert len(world.llm.received) == editor_calls
    assert world.notifier.sent == []


def test_run_stops_after_three_retries_and_alerts_owner_once(world: World) -> None:
    tech(world)
    world.publisher.fail(CHANNEL, RuntimeError("bot bị chặn khỏi nhóm"))

    for minutes in (0, 30, 60, 90):
        assert world.notifier.sent == []
        world.tick(at(7, 8) + timedelta(minutes=minutes))
    for minutes in (120, 150, 180, 240):
        world.tick(at(7, 8) + timedelta(minutes=minutes))

    [run] = world.runner.history("tech")
    assert (run.outcome, run.attempts) == (RunOutcome.FAILED, 4)
    assert world.publisher.received == []
    assert world.notifier.sent == [
        "Bản tin Công nghệ 08:00 ngày 07/10/2026 không được phát: Kỳ hỏng sau 4 lần chạy.\n"
        f"Lí do: Kênh đăng {CHANNEL} lỗi: bot bị chặn khỏi nhóm"
    ]


def test_run_that_does_not_publish_alerts_owner_and_is_not_retried(world: World) -> None:
    world.add_section("tech", name="Công nghệ", sources=[RSS], channels=[CHANNEL])
    world.collector.has(RSS, NewArticle("https://bao.example/cu", "Bài tuần trước", at(1, 9)))

    for moment in (at(7, 8), at(7, 8, 30), at(7, 9)):
        world.tick(moment)

    [run] = world.runner.history("tech")
    assert (run.outcome, run.attempts) == (RunOutcome.NOT_PUBLISHED, 1)
    assert world.notifier.sent == [
        "Bản tin Công nghệ 08:00 ngày 07/10/2026 không được phát.\nLí do: Không có Bài gốc mới"
    ]


def test_bulletin_with_too_few_stories_is_not_retried_and_alerts_owner_right_away(
    world: World,
) -> None:
    world.add_section("tech", name="Công nghệ", sources=[RSS], channels=[CHANNEL])
    world.collector.has(
        RSS,
        NewArticle(A, "Bài A", at(7, 7)),
        NewArticle(B, "Bài B", at(7, 6)),
        NewArticle(C, "Bài C", at(7, 5)),
    )
    wrong_story = DraftStory(A, "Tiêu đề sai")
    world.verifier.flag("Tiêu đề sai", "Bài gốc không nói vậy")
    world.llm.will(
        read(A, B, C),
        submit(wrong_story, DraftStory(B, "Tin B"), DraftStory(C, "Tin C")),
        rewrite(wrong_story),
        rewrite(wrong_story),
    )

    world.tick(at(7, 8))
    world.tick(at(7, 8, 30))

    [run] = world.runner.history("tech")
    assert (run.outcome, run.attempts) == (RunOutcome.FAILED, 1)
    [alert] = world.notifier.sent
    assert alert.startswith(
        "Bản tin Công nghệ 08:00 ngày 07/10/2026 không được phát: Kỳ hỏng.\n"
        "Lí do: Chỉ 2 Tin qua Kiểm chứng"
    )


def test_retry_after_publishing_broke_off_midway_sends_only_the_rest(world: World) -> None:
    tech(world)
    world.publisher.fail(CHANNEL, RuntimeError("Too Many Requests"), after=2)
    world.tick(at(7, 8))

    world.publisher.fix(CHANNEL)
    world.tick(at(7, 8, 30))

    assert published_titles(world) == [["Bài 1", "Bài 2"], ["Bài 3"]]
    [run] = world.runner.history("tech")
    assert (run.outcome, run.attempts) == (RunOutcome.PUBLISHED, 2)


def test_restart_while_publishing_resumes_without_sending_anything_twice(world: World) -> None:
    tech(world, channels=(CHANNEL, OTHER_CHANNEL))
    world.publisher.fail(OTHER_CHANNEL, PowerLoss(), after=1)
    with pytest.raises(PowerLoss):
        world.tick(at(7, 8))

    world.publisher.fix(OTHER_CHANNEL)
    world.restart()
    world.tick(at(7, 8, 5))

    assert [
        (address, [story.title for story in bulletin.stories])
        for address, bulletin in world.publisher.received
    ] == [
        (CHANNEL, ["Bài 1", "Bài 2", "Bài 3"]),
        (OTHER_CHANNEL, ["Bài 1"]),
        (OTHER_CHANNEL, ["Bài 2", "Bài 3"]),
    ]
    [run] = world.runner.history("tech")
    assert (run.outcome, run.attempts) == (RunOutcome.PUBLISHED, 1)


def test_interrupted_run_found_too_late_is_given_up_and_alerts_owner(world: World) -> None:
    tech(world)
    world.publisher.fail(CHANNEL, PowerLoss())
    with pytest.raises(PowerLoss):
        world.tick(at(7, 8))

    world.publisher.fix(CHANNEL)
    world.restart()
    world.tick(at(7, 11, 1))

    assert world.publisher.received == []
    [run] = world.runner.history("tech")
    assert run.outcome is RunOutcome.FAILED
    assert world.notifier.sent == [
        "Bản tin Công nghệ 08:00 ngày 07/10/2026 không được phát: Kỳ hỏng.\n"
        "Lí do: Kỳ bị gián đoạn giữa chừng và đã quá hạn để chạy tiếp"
    ]


def test_restart_runs_only_the_latest_missed_run_while_still_on_time(world: World) -> None:
    tech(world)

    # Dịch vụ không chạy từ ngày 4 tới 10:30 ngày 7.
    world.tick(at(7, 10, 30))
    world.tick(at(7, 10, 31))

    assert [bulletin.run_at for _, bulletin in world.publisher.received] == [at(7, 8)]
    assert len(world.runner.history("tech")) == 1


def test_run_missed_by_more_than_three_hours_is_skipped_and_schedule_goes_on(
    world: World,
) -> None:
    tech(world)

    world.tick(at(7, 11, 1))
    assert world.runner.history("tech") == []

    world.restart()
    world.collector.has(RSS, *three_articles("Bài hôm sau", at(8, 7)))
    world.tick(at(8, 8))

    assert [bulletin.run_at for _, bulletin in world.publisher.received] == [at(8, 8)]
    assert world.notifier.sent == []


def test_paused_section_does_not_collect_or_run_until_resumed(world: World) -> None:
    tech(world, paused=True)

    world.tick(at(7, 8))
    assert world.runner.history("tech") == []
    assert world.collector.fetched == []

    world.set_paused("tech", False)
    world.tick(at(7, 8, 1))

    assert published_titles(world) == [["Bài 1", "Bài 2", "Bài 3"]]


def test_pausing_section_stops_pending_retries(world: World) -> None:
    tech(world)
    world.publisher.fail(CHANNEL, RuntimeError("Telegram quá tải"))
    world.tick(at(7, 8))

    world.set_paused("tech", True)
    world.publisher.fix(CHANNEL)
    for moment in (at(7, 8, 30), at(7, 9), at(7, 10)):
        world.tick(moment)

    assert world.publisher.received == []
    [run] = world.runner.history("tech")
    assert run.attempts == 1
    assert world.notifier.sent == []


def test_failing_source_is_recorded_and_run_still_publishes_from_the_rest(world: World) -> None:
    failing_rss = "https://chet.example/rss"
    world.add_section("tech", name="Công nghệ", sources=[failing_rss, RSS], channels=[CHANNEL])
    world.collector.fail(failing_rss, RuntimeError("máy chủ trả về 503"))
    world.collector.has(RSS, *three_articles("Bài", at(7, 7)))

    world.tick(at(7, 6))
    assert world.source_errors() == {failing_rss: "máy chủ trả về 503", RSS: None}
    world.tick(at(7, 8))

    assert published_titles(world) == [["Bài 1", "Bài 2", "Bài 3"]]
    assert world.notifier.sent == []


def test_run_uses_articles_collected_earlier_when_every_source_fails_at_publish_time(
    world: World,
) -> None:
    tech(world)
    world.tick(at(7, 7, 30))

    world.collector.fail(RSS, RuntimeError("mất mạng"))
    world.tick(at(7, 8))

    assert published_titles(world) == [["Bài 1", "Bài 2", "Bài 3"]]
    assert world.source_errors() == {RSS: "mất mạng"}


def test_alert_that_could_not_be_sent_is_sent_on_a_later_tick(world: World) -> None:
    world.add_section("tech", name="Công nghệ", sources=[RSS], channels=[CHANNEL])
    world.notifier.fail(RuntimeError("Telegram không trả lời"))
    world.tick(at(7, 8))
    assert world.notifier.sent == []

    world.notifier.fail(None)
    world.tick(at(7, 8, 1))
    world.tick(at(7, 8, 2))

    assert world.notifier.sent == [
        "Bản tin Công nghệ 08:00 ngày 07/10/2026 không được phát.\nLí do: Không có Bài gốc mới"
    ]


def test_run_in_progress_in_another_process_is_not_run_again(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    tech(world)
    other_process = Scheduler(world.session_factory, world.runner, world.notifier, world.clock)
    refusals: list[str] = []
    capture = world.camera.capture

    def capture_while_another_process_wakes_up(url: str) -> Capture:
        if not refusals:
            refusals.append("")
            other_process.tick()
            with pytest.raises(RunInProgressError) as error:
                world.runner.resume("tech")
            refusals[0] = str(error.value)
        return capture(url)

    monkeypatch.setattr(world.camera, "capture", capture_while_another_process_wakes_up)
    world.tick(at(7, 8))

    assert refusals == ["Một tiến trình khác đang chạy Kỳ của Chuyên mục tech"]
    assert published_titles(world) == [["Bài 1", "Bài 2", "Bài 3"]]
    assert len(world.runner.history("tech")) == 1
