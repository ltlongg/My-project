"""Khuôn test tại điểm "Chạy Kỳ": Nguồn giả, Kênh đăng giả, LLM theo kịch bản, bộ nhúng giả,
model chấm điểm giả, đồng hồ giả, Postgres thật.

Đồng hồ giả là tham số `run_at` của `Runner.run`: test tự nói "bây giờ" là lúc nào.
"""

import json
import math
import os
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from itertools import count
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.postgres import PostgresSaver
from pydantic import Field
from sqlalchemy import Engine, create_engine, func, make_url, select, text, update
from sqlalchemy.orm import Session, sessionmaker

from siftly.agents.editor import Editor
from siftly.agents.verifier import Verifier
from siftly.collectors import NewArticle
from siftly.db import (
    CHECKPOINT_TABLES,
    make_engine,
    make_session_factory,
    open_checkpointer,
    upgrade,
)
from siftly.models import (
    Article,
    Base,
    Candidate,
    Channel,
    ChannelKind,
    Guideline,
    Role,
    Section,
    Source,
    SourceKind,
    Story,
    Verification,
)
from siftly.publishers import BulletinContent
from siftly.runner import Runner
from siftly.search import SearchResult
from siftly.shortlisting import ATTENTION_SIGNALS, Shortlister, Signal
from siftly.urls import normalize_url

DEFAULT_URL = "postgresql+psycopg://bulletin:bulletin@127.0.0.1:54320/bulletin_test"
VIETNAM_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def at(day: int, hour: int, minute: int = 0) -> datetime:
    """Một thời điểm trong tháng 10/2026, giờ Việt Nam."""
    return datetime(2026, 10, day, hour, minute, tzinfo=VIETNAM_TZ)


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    url = make_url(os.environ.get("TEST_DATABASE_URL", DEFAULT_URL))
    database = url.database or ""
    # Lược đồ bị xoá sạch trước mỗi lần chạy, nên không bao giờ trỏ vào cơ sở dữ liệu thật.
    assert database.endswith("_test"), f"Cơ sở dữ liệu test phải có tên kết thúc bằng _test: {url}"

    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        exists = connection.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": database}
        )
        if not exists:
            connection.execute(text(f'CREATE DATABASE "{database}"'))
    admin.dispose()

    engine = make_engine(url.render_as_string(hide_password=False))
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    upgrade(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def checkpointer(engine: Engine) -> Iterator[PostgresSaver]:
    with open_checkpointer(engine) as saver:
        yield saver


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    """Hàm mở phiên làm việc trên một cơ sở dữ liệu đã dọn sạch."""
    tables = ", ".join(f'"{name}"' for name in (*Base.metadata.tables, *CHECKPOINT_TABLES))
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    return make_session_factory(engine)


class FakeCollector:
    """Bộ thu thập giả: trả về đúng những Bài gốc test đã đặt cho từng địa chỉ Nguồn."""

    def __init__(self) -> None:
        self._articles: dict[str, Sequence[NewArticle]] = {}
        self._errors: dict[str, Exception] = {}

    def has(self, url: str, *articles: NewArticle) -> None:
        self._articles[url] = articles
        self._errors.pop(url, None)

    def fail(self, url: str, error: Exception) -> None:
        self._errors[url] = error

    def collect(self, url: str, since: datetime) -> Sequence[NewArticle]:
        if url in self._errors:
            raise self._errors[url]
        return self._articles.get(url, ())


class FakePublisher:
    """Bộ phát giả: ghi lại mọi Bản tin tới từng địa chỉ Kênh đăng."""

    def __init__(self) -> None:
        self.received: list[tuple[str, BulletinContent]] = []
        self._errors: dict[str, Exception] = {}

    def fail(self, address: str, error: Exception) -> None:
        self._errors[address] = error

    def fix(self, address: str) -> None:
        del self._errors[address]

    def publish(self, address: str, bulletin: BulletinContent) -> None:
        if address in self._errors:
            raise self._errors[address]
        self.received.append((address, bulletin))


class FakeExtractor:
    """Bộ lấy nội dung giả: mọi Bài gốc đều có toàn văn, trừ những bài test đặt là hỏng."""

    def __init__(self) -> None:
        self.extracted: list[str] = []
        self._full_texts: dict[str, str] = {}
        self._errors: dict[str, Exception] = {}

    def has(self, url: str, full_text: str) -> None:
        self._full_texts[url] = full_text

    def fail(self, url: str, error: Exception) -> None:
        self._errors[url] = error

    def extract(self, url: str) -> str:
        self.extracted.append(url)
        if url in self._errors:
            raise self._errors[url]
        return self._full_texts.get(url, f"Toàn văn của {url}.")


class FakeSearcher:
    """Bộ tìm kiếm giả: ghi lại truy vấn và trả về kết quả test đã đặt."""

    def __init__(self) -> None:
        self.queries: list[str] = []
        self.results: Sequence[SearchResult] = ()

    def search(self, query: str) -> Sequence[SearchResult]:
        self.queries.append(query)
        return self.results


class FakeEmbedder:
    """Bộ nhúng giả: tiêu đề nào test đã đặt toạ độ thì nhận vector ấy, còn lại mỗi tiêu đề một
    vector riêng, vuông góc với mọi vector khác, tức là không giống gì cả.

    Văn bản được nhúng là tiêu đề rồi tới mô tả của Bài gốc; bộ nhúng giả chỉ nhìn dòng đầu.
    """

    model = "fake-embedder"
    DIMENSIONS = 1024
    # Các chiều đầu dành cho toạ độ test đặt; các chiều sau cấp cho tiêu đề chưa đặt.
    PINNED_DIMENSIONS = 16

    def __init__(self) -> None:
        self.embedded: list[str] = []
        self._vectors: dict[str, list[float]] = {}
        self._error: Exception | None = None

    def pin(self, title: str, *coordinates: float) -> None:
        """Bài gốc có tiêu đề `title` nhận vector có các toạ độ đầu là `coordinates`."""
        assert len(coordinates) <= self.PINNED_DIMENSIONS
        self._vectors[title] = [*coordinates, *[0.0] * (self.DIMENSIONS - len(coordinates))]

    def same_event(self, *titles: str) -> None:
        """Các Bài gốc có những tiêu đề này giống hệt nhau, và không giống Bài gốc nào khác."""
        dimension = self.PINNED_DIMENSIONS + len(self._vectors)
        for title in titles:
            self._vectors[title] = [1.0 if i == dimension else 0.0 for i in range(self.DIMENSIONS)]

    def fail(self, error: Exception | None) -> None:
        """Mọi lần nhúng sau đều ném `error`; None là chạy lại bình thường."""
        self._error = error

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if self._error is not None:
            raise self._error
        self.embedded += texts
        return [self._vector_for(text.split("\n")[0]) for text in texts]

    def _vector_for(self, title: str) -> list[float]:
        if title not in self._vectors:
            dimension = self.PINNED_DIMENSIONS + len(self._vectors)
            assert dimension < self.DIMENSIONS, "Test dùng quá nhiều tiêu đề cho bộ nhúng giả"
            self._vectors[title] = [1.0 if i == dimension else 0.0 for i in range(self.DIMENSIONS)]
        return self._vectors[title]


def unit_vector(similarity: float) -> tuple[float, float]:
    """Toạ độ của một vector đơn vị có độ giống `similarity` với vector (1, 0)."""
    return similarity, math.sqrt(1 - similarity**2)


@dataclass(frozen=True)
class SeenArticle:
    """Một Bài gốc của một ứng viên đúng như LLM thấy trong đề bài."""

    id: int
    title: str
    url: str
    # Thứ tự của ứng viên chứa Bài gốc này, từ 0.
    group: int
    # Tiêu đề Tin đã phát mà ứng viên giống; None là chuyện chưa phát.
    published_story: str | None = None


# Một bước của kịch bản: nhìn các ứng viên LLM được giao rồi trả lời.
Step = Callable[[Sequence[SeenArticle]], AIMessage]
_call_ids = count(1)


def _call(name: str, args: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "args": args, "id": f"call-{next(_call_ids)}", "type": "tool_call"}


def _id(seen: Sequence[SeenArticle], article: str | int) -> int:
    """Mã của ứng viên có địa chỉ `article`; số thì giữ nguyên, để test nộp cả mã không có."""
    if isinstance(article, int):
        return article
    return next(a.id for a in seen if a.url == article)


def read(*urls: str) -> Step:
    """LLM gọi công cụ đọc toàn văn cho từng Bài gốc."""
    return lambda seen: AIMessage(
        "", tool_calls=[_call("read_article", {"id": _id(seen, url)}) for url in urls]
    )


def search(query: str) -> Step:
    """LLM gọi công cụ tìm kiếm web."""
    return lambda seen: AIMessage("", tool_calls=[_call("web_search", {"query": query})])


def say(text: str) -> Step:
    """LLM trả lời bằng chữ, không gọi công cụ nào."""
    return lambda seen: AIMessage(text)


@dataclass(frozen=True)
class DraftStory:
    """Một Tin LLM nộp; `article` là địa chỉ của ứng viên, hoặc một mã tuỳ ý."""

    article: str | int
    title: str = "Tiêu đề do Biên tập viết"
    summary: str = "Tóm tắt bằng tiếng Việt do Biên tập viết từ toàn văn."
    reason: str = "Đáng đọc."


def submit(*stories: DraftStory) -> Step:
    """LLM nộp Bản tin gồm các Tin đã viết."""
    return lambda seen: AIMessage(
        "",
        tool_calls=[
            _call(
                "submit_bulletin",
                {
                    "stories": [
                        {
                            "article_id": _id(seen, s.article),
                            "title": s.title,
                            "summary": s.summary,
                            "reason": s.reason,
                        }
                        for s in stories
                    ]
                },
            )
        ],
    )


def rewrite(*stories: DraftStory) -> Step:
    """LLM nộp bản viết lại của các Tin bị Kiểm chứng trả lại; `reason` của DraftStory bị bỏ qua."""
    return lambda seen: AIMessage(
        "",
        tool_calls=[
            _call(
                "rewrite_stories",
                {
                    "stories": [
                        {
                            "article_id": _id(seen, s.article),
                            "title": s.title,
                            "summary": s.summary,
                        }
                        for s in stories
                    ]
                },
            )
        ],
    )


class ScriptedLLM(BaseChatModel):
    """LLM giả của Biên tập: trả lời lần lượt theo kịch bản test đặt.

    Không đặt kịch bản thì nó biên tập máy móc: đọc mọi ứng viên rồi nộp tất cả theo thứ tự được
    giao, giữ nguyên tiêu đề gốc. Một bước là ngoại lệ thì lời gọi đó ném ngoại lệ ấy.
    """

    script: list[Step | BaseException] = Field(default_factory=list)
    # Bước lặp lại mãi khi kịch bản đã hết, thay cho cách biên tập máy móc.
    repeat: Step | None = None
    # Các tin nhắn LLM nhận được ở từng lời gọi.
    received: list[list[BaseMessage]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Any, **options: Any) -> "ScriptedLLM":
        return self

    def will(self, *steps: Step | BaseException) -> None:
        """Đặt các bước tiếp theo của kịch bản."""
        self.script = list(steps)

    def text_received(self, call: int = -1) -> str:
        """Mọi thứ LLM đọc được ở một lời gọi, nối thành một văn bản."""
        return "\n".join(str(message.content) for message in self.received[call])

    def candidates_seen(self, call: int = 0) -> list[tuple[list[str], str | None]]:
        """Các ứng viên trong đề bài ở một lời gọi, theo thứ tự: địa chỉ các Bài gốc của ứng
        viên, và tiêu đề Tin đã phát mà nó giống."""
        candidates: list[tuple[list[str], str | None]] = []
        for article in _articles_in(self.received[call]):
            if article.group == len(candidates):
                candidates.append(([], article.published_story))
            candidates[article.group][0].append(article.url)
        return candidates

    def _generate(
        self, messages: list[BaseMessage], stop: Any = None, run_manager: Any = None, **_: Any
    ) -> ChatResult:
        self.received.append(list(messages))
        step = self.script.pop(0) if self.script else self.repeat
        if isinstance(step, BaseException):
            raise step
        seen = _articles_in(messages)
        if step is None:
            has_read = any(isinstance(message, ToolMessage) for message in messages)
            step = _submit_all if has_read else _read_all
        return ChatResult(generations=[ChatGeneration(message=step(seen))])


def _articles_in(messages: Sequence[BaseMessage]) -> list[SeenArticle]:
    """Các Bài gốc ứng viên trong đề bài của Biên tập: mỗi dòng JSON là một ứng viên."""
    task = next(str(m.content) for m in messages if isinstance(m, HumanMessage))
    candidate_lines = (json.loads(line) for line in task.splitlines() if line.startswith("{"))
    return [
        SeenArticle(
            article["id"],
            article["title"],
            article["url"],
            group,
            candidate["published_story"]["title"] if "published_story" in candidate else None,
        )
        for group, candidate in enumerate(candidate_lines)
        for article in candidate["articles"]
    ]


def _read_all(seen: Sequence[SeenArticle]) -> AIMessage:
    return read(*(a.url for a in seen))(seen)


def _submit_all(seen: Sequence[SeenArticle]) -> AIMessage:
    """Mỗi ứng viên một Tin, lấy Bài gốc đầu tiên của nó làm Bài gốc chính."""
    first_of_each_group = [a for i, a in enumerate(seen) if i == 0 or seen[i - 1].group != a.group]
    return submit(
        *(DraftStory(a.url, a.title, f"Tóm tắt của {a.title}.") for a in first_of_each_group)
    )(seen)


def verdict(passed: bool, reason: str = "") -> AIMessage:
    """Kiểm chứng trả kết luận về Tin đang xét."""
    return AIMessage("", tool_calls=[_call("verdict", {"passed": passed, "reason": reason})])


class RuleBasedVerifierLLM(BaseChatModel):
    """LLM giả của Kiểm chứng: Tin có chứa một chi tiết test đã đánh dấu là sai thì không đạt,
    còn lại đạt.

    Các bước đặt bằng `will` được dùng trước luật, để test cho nó trả lời hỏng hay ném lỗi.
    """

    wrong: dict[str, str] = Field(default_factory=dict)
    script: list[AIMessage | BaseException] = Field(default_factory=list)
    received: list[list[BaseMessage]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "rule-based-verifier"

    def bind_tools(self, tools: Any, **options: Any) -> "RuleBasedVerifierLLM":
        return self

    def flag(self, detail: str, reason: str) -> None:
        """Tin nào có `detail` trong tiêu đề hay tóm tắt thì không đạt, với lí do `reason`."""
        self.wrong[detail] = reason

    def will(self, *steps: AIMessage | BaseException) -> None:
        self.script = list(steps)

    def stories_checked(self) -> list[str]:
        """Tiêu đề của Tin ở từng lời gọi, theo thứ tự."""
        return [_story_under_check(messages)["title"] for messages in self.received]

    def text_received(self, call: int = -1) -> str:
        return "\n".join(str(message.content) for message in self.received[call])

    def _generate(
        self, messages: list[BaseMessage], stop: Any = None, run_manager: Any = None, **_: Any
    ) -> ChatResult:
        self.received.append(list(messages))
        if self.script:
            step = self.script.pop(0)
            if isinstance(step, BaseException):
                raise step
            return ChatResult(generations=[ChatGeneration(message=step)])
        story = _story_under_check(messages)
        content = f"{story['title']}\n{story['summary']}"
        reasons = [reason for detail, reason in self.wrong.items() if detail in content]
        return ChatResult(
            generations=[ChatGeneration(message=verdict(not reasons, "; ".join(reasons)))]
        )


def _story_under_check(messages: Sequence[BaseMessage]) -> dict[str, str]:
    """Tin Kiểm chứng được giao: dòng JSON cuối cùng của đề bài."""
    task = next(str(m.content) for m in messages if isinstance(m, HumanMessage))
    story: dict[str, str] = json.loads(task.splitlines()[-1])
    return story


class RuleBasedRaterLLM(BaseChatModel):
    """LLM giả của Sơ tuyển: ứng viên có tiêu đề chứa một chi tiết test đã đặt thì nhận mức phù
    hợp ấy, còn lại nhận `default`.

    Các bước đặt bằng `will` được dùng trước luật, để test cho nó trả lời hỏng hay ném lỗi.
    """

    default: int = 8
    relevance: dict[str, int] = Field(default_factory=dict)
    script: list[AIMessage | BaseException] = Field(default_factory=list)
    received: list[list[BaseMessage]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "rule-based-rater"

    def bind_tools(self, tools: Any, **options: Any) -> "RuleBasedRaterLLM":
        return self

    def rate(self, detail: str, relevance: int) -> None:
        """Ứng viên nào có `detail` trong một tiêu đề thì nhận mức phù hợp `relevance`."""
        self.relevance[detail] = relevance

    def will(self, *steps: AIMessage | BaseException) -> None:
        self.script = list(steps)

    def text_received(self, call: int = -1) -> str:
        return "\n".join(str(message.content) for message in self.received[call])

    def _generate(
        self, messages: list[BaseMessage], stop: Any = None, run_manager: Any = None, **_: Any
    ) -> ChatResult:
        self.received.append(list(messages))
        if self.script:
            step = self.script.pop(0)
            if isinstance(step, BaseException):
                raise step
            return ChatResult(generations=[ChatGeneration(message=step)])
        task = next(str(m.content) for m in messages if isinstance(m, HumanMessage))
        candidates = [json.loads(line) for line in task.splitlines() if line.startswith("{")]
        ratings = [
            {
                "id": candidate["id"],
                "relevance": next(
                    (
                        relevance
                        for detail, relevance in self.relevance.items()
                        if any(detail in title for title in candidate["titles"])
                    ),
                    self.default,
                ),
            }
            for candidate in candidates
        ]
        return ChatResult(generations=[ChatGeneration(message=ratings_reply(ratings))])


def ratings_reply(ratings: list[dict[str, Any]]) -> AIMessage:
    """Sơ tuyển trả điểm cho các ứng viên."""
    return AIMessage("", tool_calls=[_call("rate", {"ratings": ratings})])


DEFAULT_GUIDELINE = "Chọn Tin đáng đọc nhất."
DEFAULT_VERIFIER_GUIDELINE = "Đối chiếu số liệu, tên và ngày tháng với Bài gốc."


@dataclass
class World:
    """Mọi thứ một test "Chạy Kỳ" cần: thiết lập, các đầu giả và lối vào `runner`."""

    session_factory: sessionmaker[Session]
    checkpointer: PostgresSaver
    collector: FakeCollector = field(default_factory=FakeCollector)
    publisher: FakePublisher = field(default_factory=FakePublisher)
    extractor: FakeExtractor = field(default_factory=FakeExtractor)
    searcher: FakeSearcher = field(default_factory=FakeSearcher)
    embedder: FakeEmbedder = field(default_factory=FakeEmbedder)
    rater: RuleBasedRaterLLM = field(default_factory=RuleBasedRaterLLM)
    llm: ScriptedLLM = field(default_factory=ScriptedLLM)
    verifier: RuleBasedVerifierLLM = field(default_factory=RuleBasedVerifierLLM)
    runner: Runner = field(init=False)

    def __post_init__(self) -> None:
        self.use_signals(ATTENTION_SIGNALS)
        self.set_verifier_guideline(DEFAULT_VERIFIER_GUIDELINE)

    def use_signals(self, signals: Mapping[str, Signal]) -> None:
        """Sơ tuyển tính độ chú ý từ các tín hiệu này."""
        self.runner = Runner(
            self.session_factory,
            collectors={SourceKind.RSS: self.collector},
            publishers={ChannelKind.TELEGRAM: self.publisher},
            extractor=self.extractor,
            embedder=self.embedder,
            shortlister=Shortlister(self.rater, signals),
            editor=Editor(self.llm, Verifier(self.verifier), self.searcher, self.checkpointer),
        )

    def add_section(
        self,
        slug: str,
        *,
        name: str,
        sources: Sequence[str],
        channels: Sequence[str],
        max_stories: int = 7,
        shortlist_size: int = 30,
        guideline: str | None = DEFAULT_GUIDELINE,
    ) -> None:
        """Khai một Chuyên mục; Nguồn và Kênh đăng trùng địa chỉ được dùng chung.

        `guideline` là Hướng dẫn cho Biên tập, phiên bản 1; None là chưa có Hướng dẫn.
        """
        with self.session_factory.begin() as session:
            section = Section(
                slug=slug, name=name, max_stories=max_stories, shortlist_size=shortlist_size
            )
            for url in sources:
                existing = session.scalar(select(Source).where(Source.url == url))
                section.sources.append(existing or Source(kind=SourceKind.RSS, name=url, url=url))
            for address in channels:
                channel = session.scalar(select(Channel).where(Channel.address == address))
                section.channels.append(
                    channel or Channel(kind=ChannelKind.TELEGRAM, name=address, address=address)
                )
            session.add(section)
        if guideline is not None:
            self.set_guideline(slug, guideline)

    def set_guideline(self, section_slug: str, content: str) -> int:
        """Đặt một phiên bản Hướng dẫn mới của Biên tập có hiệu lực; trả về số phiên bản."""
        with self.session_factory() as session:
            section_id = session.scalars(
                select(Section.id).where(Section.slug == section_slug)
            ).one()
        return self._set_guideline(Role.EDITOR, section_id, content)

    def set_verifier_guideline(self, content: str | None) -> int:
        """Đặt một phiên bản Hướng dẫn chung mới của Kiểm chứng có hiệu lực; trả về số phiên bản.

        None là không còn phiên bản nào có hiệu lực.
        """
        return self._set_guideline(Role.VERIFIER, None, content)

    def _set_guideline(self, role: Role, section_id: int | None, content: str | None) -> int:
        with self.session_factory.begin() as session:
            same_kind = (
                Guideline.role == role,
                Guideline.section_id.is_(None)
                if section_id is None
                else Guideline.section_id == section_id,
            )
            version = (
                session.scalar(select(func.max(Guideline.version)).where(*same_kind)) or 0
            ) + 1
            session.execute(update(Guideline).where(*same_kind).values(is_active=False))
            if content is not None:
                session.add(
                    Guideline(
                        role=role,
                        section_id=section_id,
                        version=version,
                        content=content,
                        is_active=True,
                    )
                )
            return version

    def source_errors(self) -> dict[str, str | None]:
        """Lỗi gần nhất được lưu của từng Nguồn, theo địa chỉ; không lỗi là None."""
        with self.session_factory() as session:
            return {source.url: source.last_error for source in session.scalars(select(Source))}

    def stored_article_count(self) -> int:
        with self.session_factory() as session:
            return session.scalar(select(func.count()).select_from(Article)) or 0

    def stored_full_text(self, url: str) -> str | None:
        """Toàn văn được lưu của Bài gốc ở `url`; chưa có là None."""
        with self.session_factory() as session:
            return session.scalars(
                select(Article.full_text).where(Article.normalized_url == normalize_url(url))
            ).one()

    def stored_stories(self) -> list[tuple[str, str, str, str]]:
        """Các Tin đã lưu mà không bị bỏ, theo thứ tự: tiêu đề, tóm tắt, lí do chọn, địa chỉ Bài
        gốc chính."""
        with self.session_factory() as session:
            return [
                (story.title, story.summary, story.reason, story.primary_article.url)
                for story in session.scalars(
                    select(Story)
                    .where(Story.drop_reason.is_(None))
                    .order_by(Story.bulletin_id, Story.position)
                )
            ]

    def dropped_stories(self) -> list[tuple[str, str, str | None]]:
        """Các Tin đã lưu nhưng bị bỏ khỏi Bản tin: tiêu đề, địa chỉ Bài gốc chính, lí do bỏ."""
        with self.session_factory() as session:
            return [
                (story.title, story.primary_article.url, story.drop_reason)
                for story in session.scalars(
                    select(Story)
                    .where(Story.drop_reason.is_not(None))
                    .order_by(Story.bulletin_id, Story.position)
                )
            ]

    def story_articles(self, primary_url: str) -> list[str]:
        """Địa chỉ các Bài gốc của Tin có Bài gốc chính ở `primary_url`, sớm nhất trước."""
        with self.session_factory() as session:
            story = session.scalars(
                select(Story)
                .join(Article, Story.primary_article_id == Article.id)
                .where(Article.normalized_url == normalize_url(primary_url))
            ).one()
            return [article.url for article in story.candidate.articles]

    def update_of(self, title: str) -> str | None:
        """Tiêu đề Tin đã phát mà Tin `title` là bản "Cập nhật" của nó; None là Tin mới."""
        with self.session_factory() as session:
            story = session.scalars(select(Story).where(Story.title == title)).one()
            return story.update_of.title if story.update_of else None

    def stored_candidates(self) -> list[list[str]]:
        """Địa chỉ các Bài gốc của từng ứng viên đã lưu, theo Kỳ rồi theo thứ tự ứng viên."""
        with self.session_factory() as session:
            return [
                [article.url for article in candidate.articles]
                for candidate in session.scalars(
                    select(Candidate).order_by(Candidate.run_id, Candidate.position)
                )
            ]

    def stored_scores(self) -> list[tuple[list[str], float, dict[str, float], bool]]:
        """Từng ứng viên đã lưu, theo Kỳ rồi theo thứ hạng: địa chỉ các Bài gốc, điểm Sơ tuyển, các
        điểm thành phần, và có tới Biên tập không."""
        with self.session_factory() as session:
            return [
                (
                    [article.url for article in candidate.articles],
                    candidate.score or 0.0,
                    candidate.score_components or {},
                    candidate.shortlisted,
                )
                for candidate in session.scalars(
                    select(Candidate).order_by(Candidate.run_id, Candidate.position)
                )
            ]

    def verifications(self, url: str) -> list[tuple[str, str, bool, str]]:
        """Các lượt Kiểm chứng đã lưu của Tin về Bài gốc ở `url`, theo thứ tự: tiêu đề và tóm
        tắt được xét, đạt hay không, lí do."""
        with self.session_factory() as session:
            return [
                (verification.title, verification.summary, verification.passed, verification.reason)
                for verification in session.scalars(
                    select(Verification)
                    .join(Story)
                    .join(Article, Story.primary_article_id == Article.id)
                    .where(Article.normalized_url == normalize_url(url))
                    .order_by(Verification.story_id, Verification.attempt)
                )
            ]


@pytest.fixture
def world(session_factory: sessionmaker[Session], checkpointer: PostgresSaver) -> World:
    return World(session_factory, checkpointer)
