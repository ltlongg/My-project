"""Biên tập, test tại điểm "Chạy Kỳ" với LLM trả lời theo kịch bản."""

import pytest

from siftly.collectors import NewArticle
from siftly.models import RunOutcome
from siftly.publishers import StoryContent
from siftly.search import SearchResult
from tests.conftest import DraftStory, World, at, read, say, search, submit

RSS = "https://bao.example/rss"
CHANNEL = "-1001"
A, B, C, D = (f"https://bao.example/{name}" for name in "abcd")


def one_section(world: World, *urls: str, max_stories: int = 7) -> None:
    """Chuyên mục công nghệ có một Nguồn đang liệt kê các Bài gốc ở `urls`, mới nhất trước."""
    world.add_section(
        "tech",
        name="Công nghệ",
        sources=[RSS],
        channels=[CHANNEL],
        max_stories=max_stories,
    )
    world.collector.has(
        RSS,
        *(
            NewArticle(url, f"Original headline {position}", at(7, 7, 59 - position))
            for position, url in enumerate(urls)
        ),
    )


def published_stories(world: World) -> list[StoryContent]:
    """Các Tin của Bản tin duy nhất đã tới Kênh đăng giả."""
    [(_, bulletin)] = world.publisher.received
    return list(bulletin.stories)


def test_bulletin_has_the_stories_editor_picked_with_titles_and_summaries_it_wrote(
    world: World,
) -> None:
    one_section(world, A, B, C, D)
    world.llm.will(
        read(A, C, D),
        submit(
            DraftStory(
                C, "OpenAI ra mắt model mới", "OpenAI công bố model mới với giá rẻ hơn.", "Lớn"
            ),
            DraftStory(
                A, "Nvidia hoãn Rubin", "Nvidia lùi lịch giao GPU Rubin sang năm 2027.", "Mới"
            ),
            DraftStory(
                D, "Meta mở mã Llama 5", "Meta công bố Llama 5 dưới giấy phép mở.", "Đáng chú ý"
            ),
        ),
    )

    run = world.runner.run("tech", at(7, 8))

    assert run.outcome is RunOutcome.PUBLISHED
    # Bài B không được chọn; thứ tự là thứ tự Biên tập nộp.
    assert published_stories(world) == [
        StoryContent("OpenAI ra mắt model mới", "OpenAI công bố model mới với giá rẻ hơn.", C),
        StoryContent("Nvidia hoãn Rubin", "Nvidia lùi lịch giao GPU Rubin sang năm 2027.", A),
        StoryContent("Meta mở mã Llama 5", "Meta công bố Llama 5 dưới giấy phép mở.", D),
    ]
    assert world.stored_stories() == [
        ("OpenAI ra mắt model mới", "OpenAI công bố model mới với giá rẻ hơn.", "Lớn", C),
        ("Nvidia hoãn Rubin", "Nvidia lùi lịch giao GPU Rubin sang năm 2027.", "Mới", A),
        ("Meta mở mã Llama 5", "Meta công bố Llama 5 dưới giấy phép mở.", "Đáng chú ý", D),
    ]


def test_editor_can_read_article_full_text_and_full_text_is_stored(world: World) -> None:
    one_section(world, A, B)
    world.extractor.has(A, "QuantumCell đạt mật độ năng lượng 487 Wh/kg trong thử nghiệm độc lập.")
    world.llm.will(read(A), submit(DraftStory(A)))

    world.runner.run("tech", at(7, 8))

    assert "487 Wh/kg" in world.llm.text_received()
    assert world.stored_full_text(A) == (
        "QuantumCell đạt mật độ năng lượng 487 Wh/kg trong thử nghiệm độc lập."
    )
    # Bài gốc không ai đọc thì không bị tải về.
    assert world.extractor.extracted == [A]
    assert world.stored_full_text(B) is None


def test_stored_full_text_is_not_fetched_again_for_another_section(world: World) -> None:
    one_section(world, A)
    world.add_section("finance", name="Tài chính", sources=[RSS], channels=["-1002"])

    world.runner.run("tech", at(7, 8))
    world.runner.run("finance", at(7, 12))

    assert world.extractor.extracted == [A]


def test_editor_can_search_the_web_but_search_results_do_not_become_stories(
    world: World,
) -> None:
    one_section(world, A, B, C)
    world.searcher.results = [
        SearchResult("Rubin là gì", "https://la.example/rubin", "Rubin là thế hệ GPU kế tiếp.")
    ]
    unknown_id = 9999
    world.llm.will(
        read(A, B, C),
        search("Nvidia Rubin là gì"),
        submit(
            DraftStory(A),
            DraftStory(B),
            DraftStory(C),
            DraftStory(unknown_id, "Tin từ kết quả tìm kiếm"),
        ),
        submit(DraftStory(A), DraftStory(B), DraftStory(C)),
    )

    run = world.runner.run("tech", at(7, 8))

    assert world.searcher.queries == ["Nvidia Rubin là gì"]
    # Kết quả tìm kiếm tới được LLM ở lời gọi ngay sau đó.
    assert "Rubin là thế hệ GPU kế tiếp." in world.llm.text_received(2)
    # Bản nộp có Tin không dẫn tới ứng viên nào bị trả lại cả bản; bản sau mới được phát.
    assert "9999" in world.llm.text_received(3)
    assert run.outcome is RunOutcome.PUBLISHED
    assert [story.url for story in published_stories(world)] == [A, B, C]


def test_story_over_1024_characters_is_returned_to_editor_to_shorten(world: World) -> None:
    one_section(world, A, B, C)
    title = "Tiêu đề"
    # Tiêu đề, tóm tắt và link cách nhau hai dòng trống: vừa đúng 1.024 thì qua, thêm một thì không.
    just_fits = "ô" * (1024 - len(title) - len(A) - 4)
    world.llm.will(
        read(A, B, C),
        submit(DraftStory(A, title, just_fits + "ô"), DraftStory(B), DraftStory(C)),
        submit(DraftStory(A, title, just_fits), DraftStory(B), DraftStory(C)),
    )

    run = world.runner.run("tech", at(7, 8))

    assert "vượt giới hạn 1024" in world.llm.text_received()
    assert run.outcome is RunOutcome.PUBLISHED
    [story, *_] = published_stories(world)
    assert story.summary == just_fits
    assert story.length == 1024


def test_bulletin_with_more_stories_than_section_maximum_is_returned(world: World) -> None:
    one_section(world, A, B, C, D, max_stories=3)
    world.llm.will(
        read(A, B, C, D),
        submit(DraftStory(A), DraftStory(B), DraftStory(C), DraftStory(D)),
        submit(DraftStory(A), DraftStory(B), DraftStory(C)),
    )

    world.runner.run("tech", at(7, 8))

    assert [story.url for story in published_stories(world)] == [A, B, C]


@pytest.mark.parametrize(
    ("bad_story", "expected_reason"),
    [
        (DraftStory(B), "chưa đọc toàn văn"),
        (DraftStory(A, summary="OpenAI announced a cheaper model on Tuesday."), "bằng tiếng Việt"),
        (DraftStory(A, summary="Xem thêm tại https://la.example/bai nhé."), "không được chứa link"),
        (DraftStory(A, title="   "), "title"),
    ],
)
def test_story_breaking_rules_is_returned_with_reason(
    world: World, bad_story: DraftStory, expected_reason: str
) -> None:
    one_section(world, A, B, C, D)
    world.llm.will(
        read(A, C, D),
        submit(bad_story, DraftStory(C), DraftStory(D)),
        submit(DraftStory(A, "Tiêu đề đạt"), DraftStory(C), DraftStory(D)),
    )

    run = world.runner.run("tech", at(7, 8))

    assert expected_reason in world.llm.text_received()
    assert run.outcome is RunOutcome.PUBLISHED
    assert [story.url for story in published_stories(world)] == [A, C, D]
    assert published_stories(world)[0].title == "Tiêu đề đạt"


def test_unreadable_article_is_reported_to_editor_and_bulletin_still_goes_out(
    world: World,
) -> None:
    one_section(world, A, B, C, D)
    world.extractor.fail(A, RuntimeError("trang có tường phí"))
    world.llm.will(read(A, B, C, D), submit(DraftStory(B), DraftStory(C), DraftStory(D)))

    run = world.runner.run("tech", at(7, 8))

    assert "trang có tường phí" in world.llm.text_received()
    assert run.outcome is RunOutcome.PUBLISHED
    assert [story.url for story in published_stories(world)] == [B, C, D]


def test_editor_submitting_invalid_bulletin_forever_fails_run_and_nothing_is_published(
    world: World,
) -> None:
    one_section(world, A)
    world.llm.will(read(A))
    world.llm.repeat = submit(DraftStory(A, summary="Still not Vietnamese."))

    run = world.runner.run("tech", at(7, 8))

    assert run.outcome is RunOutcome.FAILED
    assert run.reason is not None
    assert run.reason.startswith("Biên tập nộp Bản tin không hợp lệ 3 lần; lần cuối: ")
    assert "bằng tiếng Việt" in run.reason
    assert world.publisher.received == []
    assert world.stored_stories() == []
    assert world.runner.history("tech") == [run]


def test_editor_never_submitting_fails_run_after_turn_limit(world: World) -> None:
    one_section(world, A)
    world.llm.repeat = say("Tôi nghĩ Bài A đáng đọc.")

    run = world.runner.run("tech", at(7, 8))

    assert run.outcome is RunOutcome.FAILED
    assert run.reason == "Biên tập chưa nộp Bản tin sau 40 lượt"
    assert len(world.llm.received) == 40
    assert world.publisher.received == []


def test_llm_error_fails_run_with_reason_and_nothing_is_published(world: World) -> None:
    one_section(world, A)
    world.llm.will(read(A), RuntimeError("HTTP 429: hết hạn mức"))

    run = world.runner.run("tech", at(7, 8))

    assert run.outcome is RunOutcome.FAILED
    assert run.reason == "Biên tập gặp lỗi: HTTP 429: hết hạn mức"
    assert world.publisher.received == []


def test_editor_guideline_is_read_from_data_per_section(world: World) -> None:
    world.add_section(
        "tech",
        name="Công nghệ",
        sources=[RSS],
        channels=[CHANNEL],
        guideline="Ưu tiên paper và repo nổi bật.",
    )
    world.add_section(
        "finance",
        name="Tài chính",
        sources=[RSS],
        channels=["-1002"],
        guideline="Không chọn tin crypto.",
    )
    world.collector.has(RSS, NewArticle(A, "Bài A", at(7, 7)))

    world.runner.run("tech", at(7, 8))
    tech_received = world.llm.text_received()
    world.runner.run("finance", at(7, 12))
    finance_received = world.llm.text_received()

    assert "Ưu tiên paper và repo nổi bật." in tech_received
    assert "Không chọn tin crypto." not in tech_received
    assert "Không chọn tin crypto." in finance_received
    assert "Ưu tiên paper và repo nổi bật." not in finance_received


def test_run_records_guideline_version_used(world: World) -> None:
    one_section(world, A)
    world.runner.run("tech", at(7, 8))

    assert world.set_guideline("tech", "Bớt tin về điện thoại.") == 2
    world.collector.has(RSS, NewArticle(B, "Bài B", at(8, 7)))
    world.runner.run("tech", at(8, 8))

    assert "Bớt tin về điện thoại." in world.llm.text_received()
    # Mới nhất trước.
    assert [run.editor_guideline_version for run in world.runner.history("tech")] == [2, 1]


def test_section_without_editor_guideline_fails_run_with_reason(world: World) -> None:
    world.add_section("tech", name="Công nghệ", sources=[RSS], channels=[CHANNEL], guideline=None)
    world.collector.has(RSS, NewArticle(A, "Bài A", at(7, 7)))

    run = world.runner.run("tech", at(7, 8))

    assert run.outcome is RunOutcome.FAILED
    assert run.reason == "Chuyên mục chưa có Hướng dẫn cho Biên tập"
    assert world.llm.received == []


def test_editor_receives_at_most_30_candidates_by_default(world: World) -> None:
    one_section(world, *(f"https://bao.example/{n}" for n in range(35)))
    # Mọi ứng viên cùng mức phù hợp nên 30 ứng viên mới nhất qua Sơ tuyển. Hai Bài gốc mới nhất là
    # một sự kiện, nên 30 ứng viên gồm 31 Bài gốc.
    world.embedder.same_event("Original headline 0", "Original headline 1")
    world.llm.will(read("https://bao.example/0"), submit(DraftStory("https://bao.example/0")))

    world.runner.run("tech", at(7, 8))

    assert len(world.llm.candidates_seen()) == 30
    task = world.llm.text_received(0)
    assert '"https://bao.example/30"' in task
    assert '"https://bao.example/31"' not in task


class PowerLoss(BaseException):
    """Tiến trình bị dừng giữa chừng: không phải lỗi mà Chạy Kỳ bắt được."""


def test_interrupted_run_resumes_from_editor_step_in_progress(world: World) -> None:
    one_section(world, A, B, C)
    world.extractor.has(A, "Toàn văn bài A có con số 487.")
    world.llm.will(read(A), read(B, C), PowerLoss())
    with pytest.raises(PowerLoss):
        world.runner.run("tech", at(7, 8))
    [unfinished] = world.runner.history("tech")
    assert unfinished.outcome is None
    calls_before = len(world.llm.received)

    world.llm.will(submit(DraftStory(A), DraftStory(B), DraftStory(C)))
    run = world.runner.resume("tech")

    assert run is not None and run.outcome is RunOutcome.PUBLISHED
    assert run.run_at == at(7, 8)
    assert [story.url for story in published_stories(world)] == [A, B, C]
    # Biên tập làm tiếp chứ không làm lại: chỉ thêm một lời gọi LLM, vẫn thấy toàn văn đã đọc
    # trước khi mất điện, và không Bài gốc nào bị tải lại.
    assert len(world.llm.received) == calls_before + 1
    assert "Toàn văn bài A có con số 487." in world.llm.text_received()
    # Việc không bị giao lại lần hai: cuộc trò chuyện chỉ dài thêm đúng phần đang dở.
    assert len(world.llm.received[-1]) == len(world.llm.received[-2])
    assert world.extractor.extracted == [A, B, C]
    assert world.runner.history("tech") == [run]


def test_resume_does_nothing_without_an_unfinished_run(world: World) -> None:
    one_section(world, A, B, C)
    assert world.runner.resume("tech") is None

    world.runner.run("tech", at(7, 8))

    assert world.runner.resume("tech") is None
    assert len(world.publisher.received) == 1
