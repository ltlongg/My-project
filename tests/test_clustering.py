"""Gom Tin và không phát lại, test tại điểm "Chạy Kỳ" với bộ nhúng giả và LLM theo kịch bản."""

from datetime import datetime

import pytest

from siftly.collectors import NewArticle
from siftly.embeddings import EmbeddingError
from siftly.models import RunOutcome
from siftly.publishers import StoryContent
from tests.conftest import DraftStory, World, at, read, rewrite, submit, unit_vector

RSS = "https://bao.example/rss"
ENGLISH_RSS = "https://news.example/rss"
CHANNEL = "-1001"


def article(
    name: str, title: str, published_at: datetime, description: str | None = None
) -> NewArticle:
    return NewArticle(f"https://bao.example/{name}", title, published_at, description)


def three_fillers(day: int) -> list[NewArticle]:
    """Ba Bài gốc không liên quan gì tới nhau, đủ để Bản tin được phát."""
    return [article(f"phu-{day}-{n}", f"Tin phụ {n} ngày {day}", at(day, 6, n)) for n in (1, 2, 3)]


def as_written(*articles: NewArticle) -> list[DraftStory]:
    """Mỗi Bài gốc một Tin, giữ nguyên tiêu đề gốc."""
    return [DraftStory(a.url, a.title) for a in articles]


def urls(*articles: NewArticle) -> list[str]:
    return [a.url for a in articles]


def published_titles(world: World) -> list[list[str]]:
    return [[story.title for story in bulletin.stories] for _, bulletin in world.publisher.received]


@pytest.fixture
def tech(world: World) -> World:
    world.add_section("tech", name="Công nghệ", sources=[RSS, ENGLISH_RSS], channels=[CHANNEL])
    return world


def test_same_event_articles_in_different_languages_become_one_story_with_editor_chosen_primary(
    tech: World,
) -> None:
    vietnamese = article("amazon", "Amazon tài trợ nhà máy điện hạt nhân ở Indiana", at(7, 7, 10))
    english = NewArticle(
        "https://news.example/amazon-nuclear",
        "Amazon is funding a new nuclear plant in Indiana",
        at(7, 6, 30),
        "Amazon will fund 12 small modular reactors at a former coal plant.",
    )
    fillers = three_fillers(7)
    tech.embedder.same_event(vietnamese.title, english.title)
    tech.collector.has(RSS, vietnamese, *fillers)
    tech.collector.has(ENGLISH_RSS, english)
    # Biên tập chọn bài tiếng Anh, nơi đưa tin đầu tiên, làm Bài gốc chính.
    tech.llm.will(read(english.url, *urls(*fillers)), submit(*as_written(english, *fillers)))

    run = tech.runner.run("tech", at(7, 8))

    assert run.outcome is RunOutcome.PUBLISHED
    # Biên tập thấy hai Bài gốc là một ứng viên, bài xuất hiện sớm nhất đứng trước.
    assert ([english.url, vietnamese.url], None) in tech.llm.candidates_seen()
    assert len(tech.llm.candidates_seen()) == 4
    [(_, bulletin)] = tech.publisher.received
    assert bulletin.stories[0] == StoryContent(
        english.title, "Tóm tắt bằng tiếng Việt do Biên tập viết từ toàn văn.", english.url
    )
    assert tech.story_articles(english.url) == [english.url, vietnamese.url]
    # Văn bản được nhúng là tiêu đề kèm mô tả, nếu Nguồn có mô tả.
    assert f"{english.title}\n{english.description}" in tech.embedder.embedded


def test_two_different_events_on_same_topic_are_not_clustered(tech: World) -> None:
    f70 = article("f70", "Samsung ra mắt Galaxy F70 giá dưới 5,5 triệu đồng", at(7, 7))
    a08 = article("a08", "Samsung ra mắt bộ đôi Galaxy A08 và A18", at(7, 7, 5))
    # Độ giống đo được giữa hai bài này trên RSS thật với BAAI/bge-m3 (docs/clustering.md).
    tech.embedder.pin(f70.title, 1, 0)
    tech.embedder.pin(a08.title, *unit_vector(0.74))
    tech.collector.has(RSS, f70, a08, *three_fillers(7))

    tech.runner.run("tech", at(7, 8))

    assert [group for group, _ in tech.llm.candidates_seen()][:2] == [
        [a08.url],
        [f70.url],
    ]
    assert published_titles(tech)[0][:2] == [a08.title, f70.title]


def test_a_like_b_and_b_like_c_but_a_unlike_c_are_not_all_clustered(tech: World) -> None:
    a, b, c = (article(name, f"Bài {name}", at(7, 7, n)) for n, name in enumerate("abc"))
    # A và B rất giống nhau, B và C giống nhau, nhưng A với C chỉ giống chừng 0,54.
    tech.embedder.pin(a.title, 1, 0)
    tech.embedder.pin(b.title, *unit_vector(0.9))
    angle_b, angle_bc = unit_vector(0.9), unit_vector(0.85)
    tech.embedder.pin(
        c.title,
        angle_b[0] * angle_bc[0] - angle_b[1] * angle_bc[1],
        angle_b[1] * angle_bc[0] + angle_b[0] * angle_bc[1],
    )
    tech.collector.has(RSS, a, b, c)

    tech.runner.run("tech", at(7, 8))

    assert sorted(group for group, _ in tech.llm.candidates_seen()) == [
        [a.url, b.url],
        [c.url],
    ]


def test_two_stories_from_same_candidate_are_rejected_back_to_editor(tech: World) -> None:
    a1 = article("a1", "Apple dời lịch giao iPhone Duo sang năm 2027", at(7, 7))
    a2 = article("a2", "Khách mua iPhone Duo có thể phải chờ đến Tết để nhận máy", at(7, 7, 20))
    fillers = three_fillers(7)
    tech.embedder.same_event(a1.title, a2.title)
    tech.collector.has(RSS, a1, a2, *fillers)
    tech.llm.will(
        read(*urls(a1, a2, *fillers)),
        submit(*as_written(a1, a2, *fillers)),
        submit(*as_written(a1, *fillers)),
    )

    run = tech.runner.run("tech", at(7, 8))

    assert "thuộc cùng một ứng viên" in tech.llm.text_received()
    assert run.outcome is RunOutcome.PUBLISHED
    assert published_titles(tech) == [[a1.title, *(f.title for f in fillers)]]


# Một chuyện được phát ở Kỳ ngày 7, rồi một Bài gốc khác về cùng chuyện xuất hiện trước Kỳ ngày 8.
PUBLISHED = article("duo-1", "Apple dời lịch giao iPhone Duo sang năm 2027", at(7, 7))
PUBLISHED_STORY = DraftStory(
    PUBLISHED.url,
    "Apple lùi lịch giao iPhone Duo sang 2027",
    "Apple thông báo khách đặt iPhone Duo sẽ nhận máy từ năm 2027.",
)
SAME_STORY = article("duo-2", "Apple xác nhận iPhone Duo giao từ tháng 1/2027", at(8, 7))


def publish_then_meet_again(world: World) -> list[NewArticle]:
    """Kỳ ngày 7 phát Tin về PUBLISHED; trả về ba Bài gốc phụ của ngày 8."""
    world.embedder.same_event(PUBLISHED.title, SAME_STORY.title)
    fillers_7, fillers_8 = three_fillers(7), three_fillers(8)
    world.collector.has(RSS, PUBLISHED, *fillers_7)
    world.llm.will(
        read(*urls(PUBLISHED, *fillers_7)), submit(PUBLISHED_STORY, *as_written(*fillers_7))
    )
    assert world.runner.run("tech", at(7, 8)).outcome is RunOutcome.PUBLISHED
    world.collector.has(RSS, SAME_STORY, *fillers_8)
    return fillers_8


def test_candidate_matching_published_story_is_marked_and_not_republished_when_editor_skips_it(
    tech: World,
) -> None:
    fillers_8 = publish_then_meet_again(tech)
    tech.llm.will(read(*urls(*fillers_8)), submit(*as_written(*fillers_8)))

    run = tech.runner.run("tech", at(8, 8))

    first_call_of_day_8 = len(tech.llm.received) - 2
    assert ([SAME_STORY.url], PUBLISHED_STORY.title) in tech.llm.candidates_seen(
        first_call_of_day_8
    )
    # Biên tập đọc được Tin đã phát nói gì để so xem có gì mới.
    assert PUBLISHED_STORY.summary in tech.llm.text_received(first_call_of_day_8)
    assert run.outcome is RunOutcome.PUBLISHED
    assert published_titles(tech)[1] == [f.title for f in fillers_8]


def test_candidate_with_new_development_is_published_with_update_label_and_linked_to_earlier_story(
    tech: World,
) -> None:
    fillers_8 = publish_then_meet_again(tech)
    update = DraftStory(
        SAME_STORY.url,
        "Apple chốt giao iPhone Duo từ tháng 1/2027",
        "Apple xác nhận những chiếc iPhone Duo đầu tiên sẽ tới tay khách từ tháng 1/2027.",
    )
    tech.llm.will(read(*urls(SAME_STORY, *fillers_8)), submit(update, *as_written(*fillers_8)))

    tech.runner.run("tech", at(8, 8))

    [_, (_, bulletin)] = tech.publisher.received
    assert bulletin.stories[0] == StoryContent(
        update.title, update.summary, SAME_STORY.url, is_update=True
    )
    assert [story.is_update for story in bulletin.stories[1:]] == [False] * 3
    assert tech.update_of(update.title) == PUBLISHED_STORY.title
    assert tech.update_of(fillers_8[0].title) is None


def test_stories_of_unpublished_run_do_not_count_as_published(tech: World) -> None:
    tech.embedder.same_event(PUBLISHED.title, SAME_STORY.title)
    tech.collector.has(RSS, PUBLISHED, *three_fillers(7))
    tech.publisher.fail(CHANNEL, RuntimeError("bot bị chặn khỏi nhóm"))
    assert tech.runner.run("tech", at(7, 8)).outcome is RunOutcome.FAILED

    tech.publisher.fix(CHANNEL)
    same_story = article("duo-3", SAME_STORY.title, at(7, 10))
    tech.collector.has(RSS, PUBLISHED, same_story, *three_fillers(7))
    tech.runner.run("tech", at(7, 12))

    # Bản tin lúc 8:00 không tới ai, nên Bài gốc của nó được xét lại và chuyện vẫn là chuyện mới.
    assert ([PUBLISHED.url, same_story.url], None) in tech.llm.candidates_seen(-2)


def test_story_dropped_by_verifier_does_not_count_as_published(tech: World) -> None:
    tech.embedder.same_event(PUBLISHED.title, SAME_STORY.title)
    fillers_7 = three_fillers(7)
    tech.collector.has(RSS, PUBLISHED, *fillers_7)
    tech.verifier.flag("2027", "Bài gốc không nói năm giao máy.")
    tech.llm.will(
        read(*urls(PUBLISHED, *fillers_7)),
        submit(PUBLISHED_STORY, *as_written(*fillers_7)),
        rewrite(PUBLISHED_STORY),
        rewrite(PUBLISHED_STORY),
    )
    assert tech.runner.run("tech", at(7, 8)).outcome is RunOutcome.PUBLISHED
    assert [story[1] for story in tech.dropped_stories()] == [PUBLISHED.url]

    tech.verifier.wrong.clear()
    tech.collector.has(RSS, SAME_STORY, *three_fillers(8))
    tech.runner.run("tech", at(8, 8))

    assert ([SAME_STORY.url], None) in tech.llm.candidates_seen(-2)


def test_stories_published_more_than_seven_days_ago_are_not_compared(tech: World) -> None:
    tech.embedder.same_event(PUBLISHED.title, SAME_STORY.title)
    tech.collector.has(RSS, PUBLISHED, *three_fillers(7))
    tech.runner.run("tech", at(7, 8))

    eight_days_later = article("duo-3", SAME_STORY.title, at(15, 7))
    tech.collector.has(RSS, eight_days_later, *three_fillers(15))
    tech.runner.run("tech", at(15, 8))

    assert ([eight_days_later.url], None) in tech.llm.candidates_seen(-2)


def test_embedding_service_error_fails_run_before_editor_and_next_run_reconsiders(
    tech: World,
) -> None:
    fillers = three_fillers(7)
    tech.collector.has(RSS, *fillers)
    tech.embedder.fail(EmbeddingError("Không kết nối được tới dịch vụ nhúng (ConnectError)"))

    run = tech.runner.run("tech", at(7, 8))

    assert run.outcome is RunOutcome.FAILED
    assert run.reason == "Gom Tin gặp lỗi: Không kết nối được tới dịch vụ nhúng (ConnectError)"
    assert tech.llm.received == []
    assert tech.publisher.received == []

    tech.embedder.fail(None)
    assert tech.runner.run("tech", at(7, 9)).outcome is RunOutcome.PUBLISHED
    assert published_titles(tech) == [[f.title for f in reversed(fillers)]]


def test_each_article_is_embedded_once_until_model_changes(tech: World) -> None:
    tech.add_section("finance", name="Tài chính", sources=[RSS], channels=["-1002"])
    tech.collector.has(RSS, PUBLISHED, *three_fillers(7))
    tech.runner.run("tech", at(7, 8))
    tech.runner.run("finance", at(7, 12))
    # Bài gốc của Tin đã phát cũng đã có vector, không phải nhúng lại khi đối chiếu ở Kỳ sau.
    tech.collector.has(RSS, *three_fillers(8))
    tech.runner.run("tech", at(8, 8))

    assert len(tech.embedder.embedded) == 7

    tech.embedder.model = "fake-embedder-2"
    tech.collector.has(RSS, *three_fillers(9))
    tech.runner.run("tech", at(9, 8))

    # Vector của model cũ không so được với model mới: ba Bài gốc mới, cùng các Bài gốc đã phát
    # trong bảy ngày qua, được nhúng lại.
    assert len(tech.embedder.embedded) == 7 + 3 + 7


class PowerLoss(BaseException):
    """Tiến trình bị dừng giữa chừng: không phải lỗi mà Chạy Kỳ bắt được."""


def test_resumed_run_reuses_exactly_the_clustered_candidates(tech: World) -> None:
    a1 = article("a1", "Apple dời lịch giao iPhone Duo sang năm 2027", at(7, 7))
    a2 = article("a2", "Khách mua iPhone Duo có thể phải chờ đến Tết để nhận máy", at(7, 7, 20))
    tech.embedder.same_event(a1.title, a2.title)
    tech.collector.has(RSS, a1, a2, *three_fillers(7))
    tech.llm.will(PowerLoss())
    with pytest.raises(PowerLoss):
        tech.runner.run("tech", at(7, 8))
    candidates = tech.stored_candidates()

    # Dịch vụ nhúng hỏng cũng không sao: ứng viên đã được gom và lưu từ lần trước.
    tech.embedder.fail(EmbeddingError("dịch vụ nhúng đang tắt"))
    run = tech.runner.resume("tech")

    assert run is not None and run.outcome is RunOutcome.PUBLISHED
    assert tech.stored_candidates() == candidates
    assert [a1.url, a2.url] in candidates
    assert tech.story_articles(a1.url) == [a1.url, a2.url]
