"""Ảnh đi kèm Tin, test tại điểm "Chạy Kỳ" với bộ chụp ảnh giả."""

import pytest

from siftly.collectors import NewArticle
from siftly.images import Capture, ImageKind
from siftly.models import RunOutcome
from tests.conftest import DraftStory, World, at, read, rewrite, submit

RSS = "https://bao.example/rss"
CHANNEL = "-1001"
A, B, C, D = (f"https://bao.example/{name}" for name in "abcd")


def tech(world: World) -> World:
    world.add_section("tech", name="Công nghệ", sources=[RSS], channels=[CHANNEL])
    world.collector.has(
        RSS,
        NewArticle(A, "Bài A", at(7, 7)),
        NewArticle(B, "Bài B", at(7, 6)),
        NewArticle(C, "Bài C", at(7, 5)),
    )
    return world


def sent_images(world: World) -> list[tuple[str, bytes | None]]:
    """Địa chỉ và ảnh của từng Tin trong Bản tin cuối cùng tới Kênh đăng giả."""
    _, bulletin = world.publisher.received[-1]
    return [(story.url, story.image) for story in bulletin.stories]


def test_each_story_goes_out_with_image_of_its_primary_article_and_is_stored_as_sent(
    world: World,
) -> None:
    tech(world)
    world.camera.has(A, Capture(ImageKind.SCREENSHOT, b"anh-chup-a"))
    world.camera.has(
        B, Capture(ImageKind.PREVIEW, b"anh-dai-dien-b", ("Không chụp được trang: mã 403",))
    )
    world.camera.has(C, Capture(ImageKind.NONE, None, ("Không chụp được trang", "Không có og")))

    run = world.runner.run("tech", at(7, 8))

    assert run.outcome is RunOutcome.PUBLISHED
    assert sent_images(world) == [(A, b"anh-chup-a"), (B, b"anh-dai-dien-b"), (C, None)]
    [stored_run] = world.runner.history("tech")
    assert stored_run.bulletin == world.publisher.received[0][1]
    assert world.stored_images() == {
        A: (ImageKind.SCREENSHOT, b"anh-chup-a", None),
        B: (ImageKind.PREVIEW, b"anh-dai-dien-b", "Không chụp được trang: mã 403"),
        C: (ImageKind.NONE, None, "Không chụp được trang\nKhông có og"),
    }


def test_camera_error_does_not_fail_run_and_story_goes_out_without_image(world: World) -> None:
    tech(world)
    world.camera.has(A, Capture(ImageKind.SCREENSHOT, b"anh-chup-a"))
    world.camera.fail(B, RuntimeError("trình duyệt sập\nchi tiết"))

    run = world.runner.run("tech", at(7, 8))

    assert run.outcome is RunOutcome.PUBLISHED
    assert run.reason is None
    assert sent_images(world) == [(A, b"anh-chup-a"), (B, None), (C, None)]
    assert world.stored_images()[B] == (ImageKind.NONE, None, "Chụp ảnh gặp lỗi: trình duyệt sập")


def editor_writes_wrong_story_about(world: World, wrong: str, *urls: str) -> None:
    """Biên tập nộp một Tin cho mỗi Bài gốc ở `urls`, Tin về `wrong` sai cả ba lần viết."""
    wrong_story = DraftStory(wrong, "Tiêu đề sai")
    world.verifier.flag("Tiêu đề sai", "Bài gốc không nói vậy")
    world.llm.will(
        read(*urls),
        submit(
            *(
                wrong_story if url == wrong else DraftStory(url, f"Tin {url[-1].upper()}")
                for url in urls
            )
        ),
        rewrite(wrong_story),
        rewrite(wrong_story),
    )


def test_only_stories_that_will_be_published_are_photographed(world: World) -> None:
    tech(world)
    world.collector.has(
        RSS,
        NewArticle(A, "Bài A", at(7, 7)),
        NewArticle(B, "Bài B", at(7, 6)),
        NewArticle(C, "Bài C", at(7, 5)),
        NewArticle(D, "Bài D", at(7, 4)),
    )
    editor_writes_wrong_story_about(world, D, A, B, C, D)

    run = world.runner.run("tech", at(7, 8))

    assert run.outcome is RunOutcome.PUBLISHED
    assert world.camera.captured == [A, B, C]


def test_bulletin_that_will_not_be_published_is_not_photographed(world: World) -> None:
    tech(world)
    editor_writes_wrong_story_about(world, A, A, B, C)

    run = world.runner.run("tech", at(7, 8))

    assert run.outcome is RunOutcome.FAILED
    assert run.reason is not None and run.reason.startswith("Chỉ 2 Tin qua Kiểm chứng")
    assert world.camera.captured == []


class PowerLoss(BaseException):
    """Tiến trình bị dừng giữa chừng: không phải lỗi mà Chạy Kỳ bắt được."""


def test_resumed_run_reuses_images_already_taken(world: World) -> None:
    tech(world)
    world.camera.has(A, Capture(ImageKind.SCREENSHOT, b"anh-chup-a"))
    world.publisher.fail(CHANNEL, PowerLoss())
    with pytest.raises(PowerLoss):
        world.runner.run("tech", at(7, 8))

    world.publisher.fix(CHANNEL)
    world.camera.has(A, Capture(ImageKind.SCREENSHOT, b"anh-chup-moi-a"))
    run = world.runner.resume("tech")

    assert run is not None and run.outcome is RunOutcome.PUBLISHED
    assert world.camera.captured == [A, B, C]
    assert sent_images(world) == [(A, b"anh-chup-a"), (B, None), (C, None)]
