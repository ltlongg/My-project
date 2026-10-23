"""Kiểm chứng và vòng viết lại, test tại điểm "Chạy Kỳ" với LLM trả lời theo kịch bản."""

import pytest
from langchain_core.messages import AIMessage

from bulletin.collectors import NewArticle
from bulletin.models import RunOutcome
from tests.conftest import (
    DEFAULT_VERIFIER_GUIDELINE,
    DraftStory,
    World,
    at,
    read,
    rewrite,
    submit,
    verdict,
)

RSS = "https://bao.example/rss"
CHANNEL = "-1001"
A, B, C, D = (f"https://bao.example/{name}" for name in "abcd")

FULL_TEXT_A = "Nvidia cho biết sẽ giao 3.000 GPU Rubin đầu tiên trong quý 3/2027."
WRONG_YEAR = "Bài gốc ghi quý 3/2027, không phải năm 2028."
# Tin về Bài gốc A: bản sai năm Kiểm chứng bắt được, và bản đúng.
A_WRONG = DraftStory(
    A,
    "Nvidia giao GPU Rubin năm 2028",
    "Nvidia cho biết hãng sẽ bắt đầu giao 3.000 GPU Rubin đầu tiên cho khách hàng vào năm 2028.",
)
A_RIGHT = DraftStory(
    A,
    "Nvidia giao GPU Rubin trong quý 3/2027",
    "Nvidia cho biết hãng sẽ bắt đầu giao 3.000 GPU Rubin đầu tiên cho khách trong quý 3/2027.",
)
STORY_B, STORY_C, STORY_D = (DraftStory(url, f"Tiêu đề {url[-1].upper()}") for url in (B, C, D))


def one_section(world: World, *urls: str) -> None:
    """Chuyên mục công nghệ có một Nguồn đang liệt kê các Bài gốc ở `urls`, mới nhất trước.

    Kiểm chứng bắt Tin nào viết sai năm của Bài gốc A.
    """
    world.add_section("tech", name="Công nghệ", sources=[RSS], channels=[CHANNEL])
    world.collector.has(
        RSS,
        *(
            NewArticle(url, f"Original headline {position}", at(7, 7, 59 - position))
            for position, url in enumerate(urls)
        ),
    )
    world.extractor.has(A, FULL_TEXT_A)
    world.verifier.flag("2028", WRONG_YEAR)


def published_titles(world: World) -> list[str]:
    """Tiêu đề các Tin của Bản tin duy nhất đã tới Kênh đăng giả."""
    [(_, bulletin)] = world.publisher.received
    return [story.title for story in bulletin.stories]


def test_story_passing_at_once_is_published_and_verification_is_stored(world: World) -> None:
    one_section(world, A, B, C)
    world.llm.will(read(A, B, C), submit(A_RIGHT, STORY_B, STORY_C))

    run = world.runner.run("tech", at(7, 8))

    assert run.outcome is RunOutcome.PUBLISHED
    assert published_titles(world) == [A_RIGHT.title, STORY_B.title, STORY_C.title]
    # Mỗi Tin được xét một lần, đối chiếu với toàn văn Bài gốc của chính nó theo Hướng dẫn.
    assert world.verifier.stories_checked() == [A_RIGHT.title, STORY_B.title, STORY_C.title]
    assert FULL_TEXT_A in world.verifier.text_received(0)
    assert FULL_TEXT_A not in world.verifier.text_received(1)
    assert DEFAULT_VERIFIER_GUIDELINE in world.verifier.text_received(0)
    assert world.verifications(A) == [(A_RIGHT.title, A_RIGHT.summary, True, "")]
    # Không Tin nào bị trả lại thì Biên tập không phải làm gì thêm sau khi nộp.
    assert len(world.llm.received) == 2


def test_failing_story_is_rewritten_per_verifier_reason_then_published(world: World) -> None:
    one_section(world, A, B, C)
    world.llm.will(read(A, B, C), submit(A_WRONG, STORY_B, STORY_C), rewrite(A_RIGHT))

    run = world.runner.run("tech", at(7, 8))

    assert WRONG_YEAR in world.llm.text_received()
    assert run.outcome is RunOutcome.PUBLISHED
    assert published_titles(world) == [A_RIGHT.title, STORY_B.title, STORY_C.title]
    assert world.verifications(A) == [
        (A_WRONG.title, A_WRONG.summary, False, WRONG_YEAR),
        (A_RIGHT.title, A_RIGHT.summary, True, ""),
    ]
    # Tin đã đạt không bị xét lại.
    assert world.verifier.stories_checked() == [
        A_WRONG.title,
        STORY_B.title,
        STORY_C.title,
        A_RIGHT.title,
    ]
    assert world.dropped_stories() == []


def test_story_still_failing_after_two_rewrites_is_dropped_with_reason(world: World) -> None:
    one_section(world, A, B, C, D)
    attempt_2 = DraftStory(
        A,
        "Nvidia giao Rubin cuối năm 2028",
        "Theo Nvidia, lô 3.000 GPU Rubin đầu tiên sẽ được giao tới khách hàng vào cuối năm 2028.",
    )
    attempt_3 = DraftStory(
        A,
        "Rubin tới tay khách năm 2028",
        "Khách hàng của Nvidia sẽ nhận được 3.000 GPU Rubin đầu tiên trong năm 2028.",
    )
    world.llm.will(
        read(A, B, C, D),
        submit(A_WRONG, STORY_B, STORY_C, STORY_D),
        rewrite(attempt_2),
        rewrite(attempt_3),
    )

    run = world.runner.run("tech", at(7, 8))

    assert run.outcome is RunOutcome.PUBLISHED
    assert published_titles(world) == [STORY_B.title, STORY_C.title, STORY_D.title]
    assert world.dropped_stories() == [
        (attempt_3.title, A, f"Không qua Kiểm chứng sau 2 lần viết lại: {WRONG_YEAR}")
    ]
    assert world.verifications(A) == [
        (draft.title, draft.summary, False, WRONG_YEAR) for draft in (A_WRONG, attempt_2, attempt_3)
    ]
    # Không có lần viết lại thứ ba: Biên tập chỉ được gọi để đọc, nộp và hai lần viết lại.
    assert len(world.llm.received) == 4


def test_fewer_than_three_verified_stories_means_not_published_and_run_failed(
    world: World,
) -> None:
    one_section(world, A, B, C)
    world.llm.will(
        read(A, B, C), submit(A_WRONG, STORY_B, STORY_C), rewrite(A_WRONG), rewrite(A_WRONG)
    )

    run = world.runner.run("tech", at(7, 8))

    assert run.outcome is RunOutcome.FAILED
    assert run.reason == "Chỉ 2 Tin qua Kiểm chứng, dưới mức tối thiểu 3; Bản tin không được phát"
    assert world.publisher.received == []
    # Bản tin không phát vẫn được lưu, kể cả Tin bị bỏ.
    assert [story[0] for story in world.stored_stories()] == [STORY_B.title, STORY_C.title]
    assert [story[1] for story in world.dropped_stories()] == [A]
    assert world.runner.history("tech") == [run]


@pytest.mark.parametrize(
    ("bad_draft", "expected_reason"),
    [
        (STORY_B, "không bị trả lại"),
        (
            DraftStory(A, A_RIGHT.title, "Nvidia ships 3,000 Rubin GPUs in Q3 2027."),
            "tiếng Việt",
        ),
    ],
)
def test_invalid_rewrite_is_returned_with_reason(
    world: World, bad_draft: DraftStory, expected_reason: str
) -> None:
    one_section(world, A, B, C)
    world.llm.will(
        read(A, B, C), submit(A_WRONG, STORY_B, STORY_C), rewrite(bad_draft), rewrite(A_RIGHT)
    )

    run = world.runner.run("tech", at(7, 8))

    assert expected_reason in world.llm.text_received()
    assert run.outcome is RunOutcome.PUBLISHED
    assert published_titles(world) == [A_RIGHT.title, STORY_B.title, STORY_C.title]
    # Bản bị code trả lại không tới Kiểm chứng và không tính là một lần viết lại.
    assert [v[0] for v in world.verifications(A)] == [A_WRONG.title, A_RIGHT.title]


def test_verifier_returning_invalid_verdict_once_is_reminded_and_run_still_publishes(
    world: World,
) -> None:
    one_section(world, A, B, C)
    world.llm.will(read(A, B, C), submit(A_RIGHT, STORY_B, STORY_C))
    world.verifier.will(AIMessage("Tin này đạt."))

    run = world.runner.run("tech", at(7, 8))

    assert run.outcome is RunOutcome.PUBLISHED
    assert world.verifier.stories_checked() == [
        A_RIGHT.title,
        A_RIGHT.title,
        STORY_B.title,
        STORY_C.title,
    ]


def test_verifier_returning_invalid_verdicts_forever_fails_run_and_nothing_is_published(
    world: World,
) -> None:
    one_section(world, A, B, C)
    world.llm.will(read(A, B, C), submit(A_RIGHT, STORY_B, STORY_C))
    # Không đạt mà không nêu lí do thì Biên tập không biết sửa gì, nên cũng là hỏng.
    world.verifier.will(AIMessage("Tin này đạt."), verdict(False), AIMessage("Đạt."))

    run = world.runner.run("tech", at(7, 8))

    assert run.outcome is RunOutcome.FAILED
    assert run.reason is not None
    assert run.reason.startswith("Kiểm chứng trả kết luận không hợp lệ 3 lần; lần cuối: ")
    assert world.publisher.received == []
    assert world.stored_stories() == []


def test_verifier_llm_error_fails_run_with_reason(world: World) -> None:
    one_section(world, A, B, C)
    world.llm.will(read(A, B, C), submit(A_RIGHT, STORY_B, STORY_C))
    world.verifier.will(RuntimeError("HTTP 503: model quá tải"))

    run = world.runner.run("tech", at(7, 8))

    assert run.outcome is RunOutcome.FAILED
    assert run.reason == "Kiểm chứng gặp lỗi: HTTP 503: model quá tải"
    assert world.publisher.received == []


def test_verifier_guideline_is_shared_read_from_data_and_run_records_version(
    world: World,
) -> None:
    one_section(world, A, B, C)
    world.add_section("finance", name="Tài chính", sources=[RSS], channels=["-1002"])

    world.runner.run("tech", at(7, 8))
    assert DEFAULT_VERIFIER_GUIDELINE in world.verifier.text_received()
    assert world.set_verifier_guideline("Soát kỹ tên riêng.") == 2
    world.runner.run("finance", at(7, 12))

    assert "Soát kỹ tên riêng." in world.verifier.text_received()
    assert DEFAULT_VERIFIER_GUIDELINE not in world.verifier.text_received()
    assert [run.verifier_guideline_version for run in world.runner.history("tech")] == [1]
    assert [run.verifier_guideline_version for run in world.runner.history("finance")] == [2]


def test_missing_verifier_guideline_fails_run_before_calling_llm(world: World) -> None:
    one_section(world, A, B, C)
    world.set_verifier_guideline(None)

    run = world.runner.run("tech", at(7, 8))

    assert run.outcome is RunOutcome.FAILED
    assert run.reason == "Chưa có Hướng dẫn cho Kiểm chứng"
    assert world.llm.received == []


class PowerLoss(BaseException):
    """Tiến trình bị dừng giữa chừng: không phải lỗi mà Chạy Kỳ bắt được."""


def test_run_interrupted_during_rewrite_resumes_without_rechecking_passed_stories(
    world: World,
) -> None:
    one_section(world, A, B, C)
    world.llm.will(read(A, B, C), submit(A_WRONG, STORY_B, STORY_C), PowerLoss())
    with pytest.raises(PowerLoss):
        world.runner.run("tech", at(7, 8))

    world.llm.will(rewrite(A_RIGHT))
    run = world.runner.resume("tech")

    assert run is not None and run.outcome is RunOutcome.PUBLISHED
    assert published_titles(world) == [A_RIGHT.title, STORY_B.title, STORY_C.title]
    assert world.verifier.stories_checked() == [
        A_WRONG.title,
        STORY_B.title,
        STORY_C.title,
        A_RIGHT.title,
    ]
    assert [v[2] for v in world.verifications(A)] == [False, True]
