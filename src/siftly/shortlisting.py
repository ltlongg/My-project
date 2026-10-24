"""Sơ tuyển: chấm điểm các ứng viên Tin sau Gom Tin và chỉ chuyển nhóm điểm cao nhất cho Biên tập.

Đây là bước cố định, không phải Agent (ADR 0001). Một model nhỏ chấm mức phù hợp của từng ứng viên
với phạm vi Chuyên mục; phần còn lại là công thức.

Điểm = mức phù hợp × (0,5 + 0,5 × độ chú ý). Mức phù hợp quyết định chính: độ chú ý chỉ làm điểm
lớn gấp đôi là cùng, nên một ứng viên ngoài phạm vi không vượt được ứng viên đúng phạm vi nhờ mới
hay nhờ nhiều Bài gốc. Độ chú ý là trung bình có trọng số của các tín hiệu trong
`ATTENTION_SIGNALS`; thêm một tín hiệu (ví dụ Bảng xếp hạng) không đổi cách tính của các tín hiệu
còn lại.
"""

import json
import logging
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, Field, ValidationError

from siftly.clustering import ArticleCluster
from siftly.models import Article

log = logging.getLogger(__name__)

# Ứng viên có mức phù hợp dưới mức này là ngoài phạm vi Chuyên mục: không tới Biên tập, kể cả khi
# còn chỗ trong giới hạn.
MIN_RELEVANCE = 0.3
# Độ mới giảm một nửa sau mỗi khoảng này, tính từ Bài gốc mới nhất của ứng viên.
RECENCY_HALF_LIFE = timedelta(hours=12)
# Số ứng viên trong một lời gọi chấm điểm, và số lời gọi chạy cùng lúc.
BATCH_SIZE = 40
MAX_CONCURRENT_CALLS = 4
MAX_INVALID_REPLIES = 3
# Phần của ứng viên đưa cho model chấm điểm: vài tiêu đề đầu và một đoạn mô tả ngắn là đủ.
MAX_TITLES = 3
MAX_DESCRIPTION = 300

SYSTEM_PROMPT = """\
Bạn chấm điểm sơ tuyển cho một bản tin tiếng Việt phát định kỳ. Mỗi ứng viên là một sự kiện, gồm \
tiêu đề của một hay nhiều Bài gốc cùng nói về nó, có thể bằng nhiều ngôn ngữ.

Chấm từng ứng viên theo mức phù hợp với phạm vi của Chuyên mục, mô tả trong Hướng dẫn bên dưới, \
bằng một số nguyên từ 0 đến 10:
- 10: đúng trọng tâm của phạm vi.
- 5: liên quan nhưng ở rìa phạm vi.
- 0: ngoài phạm vi, hoặc thuộc loại Hướng dẫn nói không chọn.

Chỉ chấm sự phù hợp, không chấm độ mới hay độ nổi của tin. Gọi rate đúng một lần, chấm mọi ứng \
viên, mỗi ứng viên đúng một lần."""

USE_TOOLS_REMINDER = "Câu trả lời bằng chữ không được ghi nhận. Hãy gọi rate."

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "rate",
            "description": "Chấm mức phù hợp với phạm vi Chuyên mục cho mọi ứng viên.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ratings": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer", "description": "Mã của ứng viên"},
                                "relevance": {
                                    "type": "integer",
                                    "description": "Mức phù hợp, từ 0 đến 10",
                                },
                            },
                            "required": ["id", "relevance"],
                        },
                    }
                },
                "required": ["ratings"],
            },
        },
    }
]


@dataclass(frozen=True)
class Signal:
    """Một tín hiệu độ chú ý: đo một ứng viên từ các Bài gốc của nó, ra số từ 0 tới 1."""

    weight: float
    measure: Callable[[Sequence[Article], datetime], float]


def recency(articles: Sequence[Article], run_at: datetime) -> float:
    """1 khi Bài gốc mới nhất vừa xuất hiện, giảm một nửa sau mỗi `RECENCY_HALF_LIFE`."""
    age = max(run_at - max(article.appeared_at for article in articles), timedelta(0))
    return float(0.5 ** (age / RECENCY_HALF_LIFE))


def coverage(articles: Sequence[Article], run_at: datetime) -> float:
    """0 với một Bài gốc; mỗi Bài gốc thêm rút nửa khoảng cách còn lại tới 1."""
    return 1 - 0.5 ** (len(articles) - 1)


ATTENTION_SIGNALS: Mapping[str, Signal] = {
    "recency": Signal(1.0, recency),
    "coverage": Signal(1.0, coverage),
}


@dataclass(frozen=True)
class RankedCandidate:
    cluster: ArticleCluster
    score: float
    # Điểm thành phần từ 0 tới 1: `relevance` và từng tín hiệu độ chú ý, theo tên.
    components: dict[str, float]
    # Có tới Biên tập hay không.
    shortlisted: bool


class ShortlistError(Exception):
    """Model chấm điểm lỗi hoặc không trả được điểm hợp lệ."""


class Shortlister:
    def __init__(
        self, llm: BaseChatModel, signals: Mapping[str, Signal] = ATTENTION_SIGNALS
    ) -> None:
        self._llm = llm.bind_tools(TOOLS)
        self._signals = signals

    def rank(
        self,
        guideline: str,
        clusters: Sequence[ArticleCluster],
        run_at: datetime,
        size: int,
    ) -> list[RankedCandidate]:
        """Chấm điểm mọi ứng viên theo Hướng dẫn của Biên tập (`guideline`, nơi mô tả phạm vi
        Chuyên mục) và đánh dấu tối đa `size` ứng viên điểm cao nhất, trong phạm vi, là qua.

        Trả về mọi ứng viên, điểm cao nhất trước; bằng điểm thì giữ thứ tự của `clusters`. Ném
        `ShortlistError` khi không chấm được.
        """
        if not clusters:
            return []
        batches = [
            range(start, min(start + BATCH_SIZE, len(clusters)))
            for start in range(0, len(clusters), BATCH_SIZE)
        ]
        with ThreadPoolExecutor(MAX_CONCURRENT_CALLS) as pool:
            rated = pool.map(lambda batch: self._rate(guideline, clusters, batch), batches)
            relevance = {index: rating for ratings in rated for index, rating in ratings.items()}

        total_weight = sum(signal.weight for signal in self._signals.values())
        scored = []
        for index, cluster in enumerate(clusters):
            attention = {
                name: signal.measure(cluster.articles, run_at)
                for name, signal in self._signals.items()
            }
            mean_attention = (
                sum(self._signals[name].weight * value for name, value in attention.items())
                / total_weight
                if total_weight
                else 0.0
            )
            score = relevance[index] * (0.5 + 0.5 * mean_attention)
            scored.append((score, {"relevance": relevance[index], **attention}, cluster))
        scored.sort(key=lambda item: item[0], reverse=True)

        ranked = []
        shortlisted_count = 0
        for score, components, cluster in scored:
            shortlisted = components["relevance"] >= MIN_RELEVANCE and shortlisted_count < size
            shortlisted_count += shortlisted
            ranked.append(RankedCandidate(cluster, score, components, shortlisted))
        log.info("Sơ tuyển %s trong %s ứng viên Tin", shortlisted_count, len(ranked))
        return ranked

    def _rate(
        self, guideline: str, clusters: Sequence[ArticleCluster], batch: range
    ) -> dict[int, float]:
        """Mức phù hợp, từ 0 tới 1, của các ứng viên có thứ tự trong `batch`."""
        lines = "\n".join(
            json.dumps({"id": index + 1, **_describe(clusters[index])}, ensure_ascii=False)
            for index in batch
        )
        messages: list[AnyMessage] = [
            SystemMessage(f"{SYSTEM_PROMPT}\n\n# Hướng dẫn của Chuyên mục\n\n{guideline}"),
            HumanMessage(f"Ứng viên, mỗi dòng một ứng viên:\n{lines}"),
        ]
        expected = {index + 1 for index in batch}
        errors: list[str] = []
        for _ in range(MAX_INVALID_REPLIES):
            try:
                reply = self._llm.invoke(messages)
            except Exception as call_error:
                raise ShortlistError(
                    f"Sơ tuyển gặp lỗi: {str(call_error).splitlines()[0]}"
                ) from call_error
            assert isinstance(reply, AIMessage)
            ratings, errors, feedback = _parse_ratings(reply, expected)
            if ratings is not None:
                return {candidate_id - 1: rating / 10 for candidate_id, rating in ratings.items()}
            log.warning("Sơ tuyển trả điểm không hợp lệ: %s", "; ".join(errors))
            messages += [reply, *feedback]
        raise ShortlistError(
            f"Sơ tuyển trả điểm không hợp lệ {MAX_INVALID_REPLIES} lần; lần cuối: "
            + "; ".join(errors)
        )


def _describe(cluster: ArticleCluster) -> dict[str, Any]:
    """Ứng viên như model chấm điểm thấy: vài tiêu đề, và mô tả đầu tiên có được."""
    description = next((a.description for a in cluster.articles if a.description), None)
    return {
        "titles": [article.title for article in cluster.articles[:MAX_TITLES]],
        **({"description": description[:MAX_DESCRIPTION]} if description else {}),
    }


class _Rating(BaseModel):
    id: int
    relevance: int = Field(ge=0, le=10)


class _Ratings(BaseModel):
    ratings: list[_Rating]


def _parse_ratings(
    reply: AIMessage, expected: set[int]
) -> tuple[dict[int, int] | None, list[str], list[AnyMessage]]:
    """Điểm trong câu trả lời, theo mã ứng viên, nếu hợp lệ; nếu không thì các lỗi và tin nhắn trả
    lại LLM."""
    rate_calls = [call for call in reply.tool_calls if call["name"] == "rate"]
    errors: list[str] = []
    if len(rate_calls) == 1 and not reply.invalid_tool_calls:
        try:
            submitted = _Ratings.model_validate(rate_calls[0]["args"])
        except ValidationError as validation_error:
            errors = [
                f"{'.'.join(str(part) for part in item['loc']) or 'tham số'}: {item['msg']}"
                for item in validation_error.errors()
            ]
        else:
            ids = [rating.id for rating in submitted.ratings]
            if missing := sorted(expected - set(ids)):
                errors.append(f"chưa chấm ứng viên {', '.join(map(str, missing))}")
            if unknown := sorted(set(ids) - expected):
                errors.append(f"không có ứng viên {', '.join(map(str, unknown))}")
            if repeated := sorted({i for i in ids if ids.count(i) > 1}):
                errors.append(f"chấm hơn một lần ứng viên {', '.join(map(str, repeated))}")
            if not errors:
                return {rating.id: rating.relevance for rating in submitted.ratings}, [], []
    elif rate_calls or reply.invalid_tool_calls:
        errors = ["phải gọi rate đúng một lần, với tham số JSON hợp lệ"]
    else:
        errors = ["không gọi rate"]

    content = "Chưa hợp lệ, hãy gọi lại rate:\n" + "\n".join(f"- {item}" for item in errors)
    feedback: list[AnyMessage] = [
        ToolMessage(content, tool_call_id=call["id"] or "")
        for call in (*reply.tool_calls, *reply.invalid_tool_calls)
    ]
    return None, errors, feedback or [HumanMessage(USE_TOOLS_REMINDER)]
