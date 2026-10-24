"""Sơ tuyển, test tại điểm "Chạy Kỳ" với model chấm điểm giả và LLM theo kịch bản."""

from collections.abc import Sequence
from datetime import datetime

import pytest
from langchain_core.messages import AIMessage

from siftly.collectors import NewArticle
from siftly.models import Article, RunOutcome
from siftly.shortlisting import ATTENTION_SIGNALS, SYSTEM_PROMPT, Signal, coverage, recency
from tests.conftest import World, at, ratings_reply

RSS = "https://bao.example/rss"
CHANNEL = "-1001"
FINANCE_GUIDELINE = "Phạm vi: chứng khoán, ngân hàng, kinh tế vĩ mô. Không chọn: tiền mã hoá."


def article(name: str, title: str, published_at: datetime) -> NewArticle:
    return NewArticle(f"https://bao.example/{name}", title, published_at)


def finance(world: World, shortlist_size: int = 30) -> World:
    world.add_section(
        "finance",
        name="Tài chính",
        sources=[RSS],
        channels=[CHANNEL],
        shortlist_size=shortlist_size,
        guideline=FINANCE_GUIDELINE,
    )
    return world


def seen_by_editor(world: World) -> list[list[str]]:
    return [group for group, _ in world.llm.candidates_seen()]


def test_only_highest_scoring_candidates_reach_editor_and_the_rest_are_stored_with_scores(
    world: World,
) -> None:
    finance(world, shortlist_size=3)
    rate_cut = article("lai-suat", "Ngân hàng Nhà nước giảm lãi suất điều hành", at(7, 7))
    vn_index = article("vn-index", "VN-Index vượt 1.500 điểm", at(7, 7, 30))
    gold = article("vang", "Giá vàng nhẫn lập đỉnh mới", at(7, 7, 50))
    inflation = article("lam-phat", "Lạm phát tháng 10 tăng 3,2%", at(7, 2))
    etf = article("etf", "Ra mắt quỹ ETF mới", at(7, 7, 55))
    world.collector.has(RSS, rate_cut, vn_index, gold, inflation, etf)
    for detail, relevance in {"lãi suất": 10, "VN-Index": 9, "vàng": 6, "Lạm phát": 9}.items():
        world.rater.rate(detail, relevance)
    world.rater.rate("ETF", 5)

    world.runner.run("finance", at(7, 8))

    # Tin lạm phát cũ hơn sáu tiếng nhưng đúng trọng tâm, nên vượt hai Tin mới mà ở rìa phạm vi.
    assert seen_by_editor(world) == [[rate_cut.url], [vn_index.url], [inflation.url]]
    scores = world.stored_scores()
    assert [urls for urls, *_ in scores] == [
        [rate_cut.url],
        [vn_index.url],
        [inflation.url],
        [gold.url],
        [etf.url],
    ]
    assert [shortlisted for *_, shortlisted in scores] == [True, True, True, False, False]
    assert [score for _, score, *_ in scores] == sorted(
        (score for _, score, *_ in scores), reverse=True
    )
    _, score, components, _ = scores[2]
    assert components == {
        "relevance": 0.9,
        "recency": pytest.approx(0.5**0.5),
        "coverage": 0.0,
    }
    assert score == pytest.approx(0.9 * (0.5 + 0.5 * (0.5**0.5 + 0) / 2))


def test_more_articles_about_the_same_event_raise_the_score(world: World) -> None:
    finance(world, shortlist_size=1)
    alone = article("alone", "Vietcombank tăng vốn điều lệ", at(7, 7, 30))
    covered = [article(f"fed-{n}", f"Fed giữ nguyên lãi suất ({n})", at(7, 7, n)) for n in (1, 2)]
    world.embedder.same_event(*(a.title for a in covered))
    world.collector.has(RSS, alone, *covered)

    world.runner.run("finance", at(7, 8))

    assert seen_by_editor(world) == [[a.url for a in covered]]
    assert world.stored_scores()[0][2]["coverage"] == 0.5


def test_off_topic_candidates_score_low_and_never_reach_editor_even_with_room_left(
    world: World,
) -> None:
    finance(world)
    on_topic = [
        article(f"ck-{n}", f"Cổ phiếu ngân hàng tăng phiên {n}", at(7, 5, n)) for n in (1, 2, 3)
    ]
    # Tin crypto mới hơn và được nhiều nơi đưa, nhưng ngoài phạm vi Chuyên mục.
    bitcoin = [
        article(f"btc-{n}", f"Bitcoin vượt 150.000 USD ({n})", at(7, 7, 50 + n)) for n in (1, 2, 3)
    ]
    world.embedder.same_event(*(a.title for a in bitcoin))
    world.collector.has(RSS, *bitcoin, *on_topic)
    world.rater.rate("Bitcoin", 1)

    run = world.runner.run("finance", at(7, 8))

    assert run.outcome is RunOutcome.PUBLISHED
    assert [a.url for a in bitcoin] not in seen_by_editor(world)
    assert len(seen_by_editor(world)) == 3
    *on_topic_scores, (urls, bitcoin_score, components, shortlisted) = world.stored_scores()
    assert urls == [a.url for a in bitcoin]
    assert components["relevance"] == pytest.approx(0.1)
    assert not shortlisted
    assert all(bitcoin_score < score for _, score, *_ in on_topic_scores)
    # Model chấm điểm biết phạm vi Chuyên mục qua Hướng dẫn của Biên tập.
    assert FINANCE_GUIDELINE in world.rater.text_received(0)


def test_run_without_any_candidate_in_scope_is_not_published(world: World) -> None:
    finance(world)
    world.collector.has(RSS, article("btc", "Bitcoin vượt 150.000 USD", at(7, 7)))
    world.rater.rate("Bitcoin", 0)

    run = world.runner.run("finance", at(7, 8))

    assert run.outcome is RunOutcome.NOT_PUBLISHED
    assert run.reason == "Không ứng viên Tin nào trong phạm vi Chuyên mục"
    assert world.llm.received == []
    assert [shortlisted for *_, shortlisted in world.stored_scores()] == [False]


def test_new_signal_plugs_in_without_changing_the_others(world: World) -> None:
    finance(world, shortlist_size=1)
    trending = article("trending", "Cổ phiếu FPT dẫn đầu thanh khoản", at(7, 6))
    fresh = article("fresh", "Cổ phiếu HPG tăng trần", at(7, 7, 55))
    world.collector.has(RSS, trending, fresh)

    def on_leaderboard(articles: Sequence[Article], run_at: datetime) -> float:
        return 1.0 if any("FPT" in a.title for a in articles) else 0.0

    world.use_signals({**ATTENTION_SIGNALS, "leaderboard": Signal(2.0, on_leaderboard)})

    world.runner.run("finance", at(7, 8))

    # Không có tín hiệu mới thì Tin mới hơn đứng đầu; có nó thì Tin trên Bảng xếp hạng vượt lên.
    assert seen_by_editor(world) == [[trending.url]]
    [(_, score, components, _), (_, _, fresh_components, _)] = world.stored_scores()
    assert components == {
        "relevance": 0.8,
        "recency": pytest.approx(0.5 ** (2 / 12)),
        "coverage": 0.0,
        "leaderboard": 1.0,
    }
    assert score == pytest.approx(0.8 * (0.5 + 0.5 * (0.5 ** (2 / 12) + 0 + 2 * 1) / 4))
    assert fresh_components["leaderboard"] == 0.0


def test_attention_signals_measure_freshness_and_article_count(world: World) -> None:
    finance(world)
    world.collector.has(RSS, article("a", "Bài A", at(7, 7)))
    world.runner.run("finance", at(7, 8))
    with world.session_factory() as session:
        [stored] = session.query(Article).all()
        assert recency([stored], at(7, 19)) == pytest.approx(0.5)
        assert recency([stored], at(7, 7)) == 1.0
        assert coverage([stored] * 3, at(7, 8)) == 0.75


def test_shortlisting_uses_its_own_model(world: World) -> None:
    finance(world)
    world.collector.has(RSS, *(article(f"{n}", f"Bài {n}", at(7, 7, n)) for n in range(3)))

    world.runner.run("finance", at(7, 8))

    assert len(world.rater.received) == 1
    assert SYSTEM_PROMPT in world.rater.text_received(0)
    assert all(SYSTEM_PROMPT not in world.llm.text_received(call) for call in range(2))


def test_many_candidates_are_rated_in_batches(world: World) -> None:
    finance(world, shortlist_size=5)
    world.collector.has(
        RSS, *(article(f"{n}", f"Bài {n}", at(7, 6 + n // 60, n % 60)) for n in range(90))
    )

    world.runner.run("finance", at(7, 8))

    assert len(world.rater.received) == 3
    scores = world.stored_scores()
    assert len(scores) == 90
    assert sum(shortlisted for *_, shortlisted in scores) == 5
    assert len(seen_by_editor(world)) == 5


def test_invalid_ratings_are_sent_back_for_correction(world: World) -> None:
    finance(world)
    world.collector.has(RSS, *(article(f"{n}", f"Bài {n}", at(7, 7, n)) for n in range(3)))
    world.rater.will(ratings_reply([{"id": 1, "relevance": 7}, {"id": 2, "relevance": 11}]))

    run = world.runner.run("finance", at(7, 8))

    assert run.outcome is RunOutcome.PUBLISHED
    feedback = world.rater.text_received(1)
    assert "ratings.1.relevance" in feedback
    world.rater.received.clear()
    world.rater.will(ratings_reply([{"id": 1, "relevance": 7}, {"id": 1, "relevance": 7}]))
    world.collector.has(RSS, *(article(f"b{n}", f"Bài sau {n}", at(7, 9, n)) for n in range(3)))
    world.runner.run("finance", at(7, 10))
    assert "chưa chấm ứng viên 2, 3" in world.rater.text_received(1)
    assert "chấm hơn một lần ứng viên 1" in world.rater.text_received(1)


def test_rater_that_never_replies_validly_fails_run_before_editor(world: World) -> None:
    finance(world)
    world.collector.has(RSS, *(article(f"{n}", f"Bài {n}", at(7, 7, n)) for n in range(3)))
    world.rater.will(*[AIMessage("Tôi nghĩ mọi Tin đều hay.")] * 3)

    run = world.runner.run("finance", at(7, 8))

    assert run.outcome is RunOutcome.FAILED
    assert run.reason == "Sơ tuyển trả điểm không hợp lệ 3 lần; lần cuối: không gọi rate"
    assert world.llm.received == []


def test_rater_error_fails_run_before_editor_and_next_run_reconsiders(world: World) -> None:
    finance(world)
    articles = [article(f"{n}", f"Bài {n}", at(7, 7, n)) for n in range(3)]
    world.collector.has(RSS, *articles)
    world.rater.will(RuntimeError("Endpoint LLM trả 503"))

    run = world.runner.run("finance", at(7, 8))

    assert run.outcome is RunOutcome.FAILED
    assert run.reason == "Sơ tuyển gặp lỗi: Endpoint LLM trả 503"
    assert world.llm.received == []
    assert world.stored_scores() == []

    assert world.runner.run("finance", at(7, 9)).outcome is RunOutcome.PUBLISHED
    assert len(seen_by_editor(world)) == 3
    # Vector nhúng của lần trước đã được lưu, không phải nhúng lại.
    assert len(world.embedder.embedded) == 3


class PowerLoss(BaseException):
    """Tiến trình bị dừng giữa chừng: không phải lỗi mà Chạy Kỳ bắt được."""


def test_resumed_run_reuses_stored_scores_without_rating_again(world: World) -> None:
    finance(world, shortlist_size=3)
    world.collector.has(RSS, *(article(f"{n}", f"Bài {n}", at(7, 7, n)) for n in range(5)))
    world.llm.will(PowerLoss())
    with pytest.raises(PowerLoss):
        world.runner.run("finance", at(7, 8))
    scores = world.stored_scores()
    calls = len(world.rater.received)

    world.rater.will(RuntimeError("Endpoint LLM trả 503"))
    run = world.runner.resume("finance")

    assert run is not None and run.outcome is RunOutcome.PUBLISHED
    assert len(world.rater.received) == calls
    assert world.stored_scores() == scores
    assert len(world.llm.candidates_seen(-1)) == 3
