"""Biên tập: Agent chọn Tin nào vào Bản tin và viết từng Tin bằng tiếng Việt.

Vòng làm việc: LLM gọi công cụ (đọc toàn văn một Bài gốc, tìm kiếm web) cho tới khi nộp Bản tin
bằng công cụ `submit_bulletin`. Bản nộp được kiểm tra bằng code; chưa hợp lệ thì trả lại kèm lí do.
Bản hợp lệ được Kiểm chứng đối chiếu từng Tin với Bài gốc; Tin không đạt quay lại Biên tập để viết
lại bằng `rewrite_stories`, tối đa hai lần, rồi bị bỏ.
Trạng thái của vòng được lưu sau từng bước, nên gọi lại `work` với cùng `thread_id` là chạy tiếp.
"""

import json
import logging
import operator
import re
from collections.abc import Callable, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any, TypedDict
from zoneinfo import ZoneInfo

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from bulletin.agents import truncate_full_text
from bulletin.agents.verifier import Verifier
from bulletin.publishers import MAX_STORY_LENGTH, StoryContent
from bulletin.search import Searcher
from bulletin.vietnamese import is_vietnamese

log = logging.getLogger(__name__)

VIETNAM_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
# Số Tin Biên tập nên chọn khi đủ Bài gốc đáng đọc; mức trần là của từng Chuyên mục.
TARGET_STORIES = 5
# Số lần gọi LLM tối đa trong một Kỳ, đủ để đọc vài chục Bài gốc, nộp rồi viết lại.
MAX_TURNS = 40
MAX_FAILED_SUBMISSIONS = 3
# Tin không qua Kiểm chứng được viết lại tối đa ngần này lần rồi bị bỏ (ADR 0001).
MAX_REWRITES = 2
HAS_LINK = re.compile(r"https?://|www\.", re.IGNORECASE)

SYSTEM_PROMPT = f"""\
Bạn là Biên tập của một bản tin tiếng Việt phát định kỳ. Mỗi Kỳ bạn nhận danh sách ứng viên Tin \
của một Chuyên mục, chọn những Tin đáng đọc nhất và viết từng Tin bằng tiếng Việt.

Mỗi ứng viên là một sự kiện, gồm một hay nhiều Bài gốc cùng nói về nó, có thể từ nhiều Nguồn và \
nhiều ngôn ngữ. Mỗi ứng viên chỉ thành nhiều nhất một Tin. Với mỗi Tin, chọn một Bài gốc chính \
trong ứng viên: Tin dẫn link tới nó và chỉ được viết từ nó. Ưu tiên nơi đưa tin đầu tiên hoặc \
nguồn gốc nhất (trang của chính tổ chức trong tin, bài nghiên cứu gốc, tờ báo có tin sớm nhất), \
miễn là đủ chi tiết.

Ứng viên có published_story là chuyện đã có trong một Bản tin trước. Bỏ qua nó, trừ khi Bài gốc \
có diễn biến mới đáng kể so với Tin đã phát (quyết định, con số hay kết quả mới), không chỉ là \
một bài khác kể lại cùng chuyện. Nếu chọn, Tin được phát với nhãn "Cập nhật" (đừng tự viết nhãn \
này vào tiêu đề): tiêu đề và câu đầu của tóm tắt nói ngay điều mới, reason nêu điều mới so với \
Tin đã phát.

Cách làm:
1. Dựa vào tiêu đề và Nguồn để khoanh những ứng viên đáng cân nhắc theo Hướng dẫn của Chuyên mục.
2. Gọi read_article để đọc toàn văn Bài gốc chính của mọi Tin định viết. Chỉ được viết Tin khi \
đã đọc toàn văn Bài gốc chính, và chỉ viết điều có trong toàn văn đó.
3. Khi cần hiểu bối cảnh (một cái tên lạ, một sự kiện trước đó) thì gọi web_search. Kết quả tìm \
kiếm chỉ để hiểu bối cảnh: không đưa chi tiết chỉ có ở đó vào Tin, và không biến nó thành Tin.
4. Gọi submit_bulletin với các Tin đã chọn, Tin đáng đọc nhất đứng trước. Nếu bản nộp bị trả lại \
thì sửa theo lí do rồi nộp lại.
5. Kiểm chứng đối chiếu từng Tin với toàn văn Bài gốc chính. Tin không đạt được trả lại kèm lí \
do: viết lại đúng theo Bài gốc chính rồi gọi rewrite_stories. Tin vẫn không đạt sau \
{MAX_REWRITES} lần viết lại thì bị bỏ khỏi Bản tin.

Quy tắc viết mỗi Tin:
- Tiêu đề và tóm tắt bằng tiếng Việt, kể cả khi Bài gốc bằng tiếng Anh. Tóm tắt dài 4–6 câu, đủ \
để người đọc hiểu tin mà không cần mở link.
- Giữ nguyên tiếng Anh tên riêng (người, công ty, sản phẩm, model) và thuật ngữ chuyên ngành quen \
dùng (ví dụ GPU, open source, fine-tuning); không dịch chúng.
- Số liệu, tên và ngày tháng phải đúng như Bài gốc. Tiêu đề không nói quá điều Bài gốc nói.
- Tiêu đề, tóm tắt và link của Bài gốc chính cộng lại không quá {MAX_STORY_LENGTH} ký tự. Không \
chèn link vào tiêu đề hay tóm tắt.
- reason: một hai câu cho biết vì sao Tin này đáng vào Bản tin."""

USE_TOOLS_REMINDER = (
    "Câu trả lời bằng chữ không được ghi nhận. Hãy làm tiếp bằng công cụ; khi đã viết xong các "
    "Tin thì gọi submit_bulletin, hoặc rewrite_stories nếu đang có Tin bị Kiểm chứng trả lại."
)


def _tool(name: str, description: str, properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": list(properties),
            },
        },
    }


_DRAFT_PROPERTIES = {
    "article_id": {"type": "integer", "description": "Mã của Bài gốc chính, mà Tin dẫn link tới"},
    "title": {"type": "string", "description": "Tiêu đề tiếng Việt"},
    "summary": {"type": "string", "description": "Tóm tắt tiếng Việt, 4–6 câu"},
}


def _story_list(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "stories": {
            "type": "array",
            "items": {"type": "object", "properties": properties, "required": list(properties)},
        }
    }


TOOLS = [
    _tool(
        "read_article",
        "Đọc toàn văn một Bài gốc của một ứng viên.",
        {"id": {"type": "integer", "description": "Mã của Bài gốc"}},
    ),
    _tool(
        "web_search",
        "Tìm kiếm web để hiểu bối cảnh của một Tin. Kết quả không phải là Bài gốc.",
        {"query": {"type": "string", "description": "Điều cần tìm"}},
    ),
    _tool(
        "submit_bulletin",
        "Nộp các Tin đã chọn và viết xong, Tin đáng đọc nhất đứng trước.",
        _story_list(
            {
                **_DRAFT_PROPERTIES,
                "reason": {"type": "string", "description": "Vì sao chọn Tin này"},
            }
        ),
    ),
    _tool(
        "rewrite_stories",
        "Nộp bản viết lại của mọi Tin bị Kiểm chứng trả lại.",
        _story_list(_DRAFT_PROPERTIES),
    ),
]


@dataclass(frozen=True)
class CandidateArticle:
    id: int
    title: str
    source: str
    url: str
    appeared_at: datetime
    description: str | None = None


@dataclass(frozen=True)
class PublishedStory:
    """Một Tin đã tới người đọc ở Bản tin trước."""

    published_at: datetime
    title: str
    summary: str


@dataclass(frozen=True)
class Candidate:
    """Một ứng viên Tin Biên tập được cân nhắc trong Kỳ: các Bài gốc cùng nói về một sự kiện."""

    articles: Sequence[CandidateArticle]
    # Tin đã phát mà ứng viên giống; có thì ứng viên chỉ được chọn như một Tin "Cập nhật".
    published_story: PublishedStory | None = None


@dataclass(frozen=True)
class Assignment:
    """Việc giao cho Biên tập ở một Kỳ."""

    section: str
    run_at: datetime
    guideline: str
    verifier_guideline: str
    max_stories: int
    candidates: Sequence[Candidate]


@dataclass(frozen=True)
class Draft:
    """Một bản viết của một Tin cùng kết luận của Kiểm chứng về nó."""

    title: str
    summary: str
    passed: bool
    # Lí do của Kiểm chứng; khi đạt thì có thể trống.
    reason: str


@dataclass(frozen=True)
class WrittenStory:
    article_id: int
    # Vì sao Biên tập chọn Tin này.
    reason: str
    # Bản đầu rồi các bản viết lại, theo thứ tự; bản cuối là bản được dùng.
    drafts: tuple[Draft, ...]

    @property
    def title(self) -> str:
        return self.drafts[-1].title

    @property
    def summary(self) -> str:
        return self.drafts[-1].summary

    @property
    def drop_reason(self) -> str | None:
        """Vì sao Tin bị bỏ khỏi Bản tin; None là Tin đã qua Kiểm chứng."""
        last = self.drafts[-1]
        if last.passed:
            return None
        return f"Không qua Kiểm chứng sau {len(self.drafts) - 1} lần viết lại: {last.reason}"


class EditorError(Exception):
    """Biên tập không ra được một Bản tin hợp lệ."""


class _SubmittedDraft(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    article_id: int
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)

    @field_validator("title", "summary")
    @classmethod
    def _single_paragraph(cls, text: str) -> str:
        return " ".join(text.split())


class _SubmittedStory(_SubmittedDraft):
    reason: str = Field(min_length=1)


class _SubmittedBulletin(BaseModel):
    stories: list[_SubmittedStory] = Field(min_length=1)


class _SubmittedRewrite(BaseModel):
    stories: list[_SubmittedDraft] = Field(min_length=1)


class _ReadArgs(BaseModel):
    id: int


class _SearchArgs(BaseModel):
    query: str = Field(min_length=1)


class _State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    # Mỗi Bài gốc của các ứng viên: mã, tiêu đề, link, thứ tự ứng viên (`group`) và ứng viên có là
    # chuyện đã phát không (`is_update`). Bản nộp được soát theo đây, kể cả khi chạy tiếp.
    candidates: list[dict[str, Any]]
    max_stories: int
    verifier_guideline: str
    read_ids: Annotated[list[int], operator.add]
    turns: int
    failed_submissions: int
    # Chưa nộp được Bản tin hợp lệ thì là None. Sau đó là các Tin theo thứ tự nộp, mỗi Tin có
    # `article_id`, `reason` và `drafts`; bản viết cuối chưa có `passed` là đang chờ Kiểm chứng.
    stories: list[dict[str, Any]] | None
    # Có giá trị thì vòng kết thúc vì Biên tập không làm được.
    error: str | None


def _awaiting_verification(story: dict[str, Any]) -> bool:
    return bool(story["drafts"][-1]["passed"] is None)


def _awaiting_rewrite(story: dict[str, Any]) -> bool:
    return story["drafts"][-1]["passed"] is False and len(story["drafts"]) <= MAX_REWRITES


class Editor:
    def __init__(
        self,
        llm: BaseChatModel,
        verifier: Verifier,
        searcher: Searcher,
        checkpointer: BaseCheckpointSaver[Any],
    ) -> None:
        self._llm = llm.bind_tools(TOOLS)
        self._verifier = verifier
        self._searcher = searcher
        self._checkpointer = checkpointer

    def work(
        self, thread_id: str, assignment: Assignment, read_article: Callable[[int], str]
    ) -> list[WrittenStory]:
        """Chọn, viết và cho Kiểm chứng xét các Tin của `assignment`; `read_article` trả về toàn
        văn theo mã Bài gốc.

        Trả về mọi Tin đã nộp theo thứ tự nộp, kể cả Tin bị bỏ vì không qua Kiểm chứng.
        `thread_id` nhận diện lần làm việc này. Lần trước cùng mã mà dở dang thì làm tiếp từ bước
        đang dở và bỏ qua `assignment`; đã xong thì trả lại kết quả cũ. Ném `EditorError` khi Biên
        tập không nộp được Bản tin hợp lệ, và `VerifierError` khi Kiểm chứng không ra được kết luận.
        """
        graph = self._graph(read_article)
        config: Any = {
            "configurable": {"thread_id": thread_id},
            # Mỗi lượt là hai bước, cộng một bước Kiểm chứng cho bản nộp và từng lần viết lại.
            "recursion_limit": 2 * MAX_TURNS + MAX_REWRITES + 5,
        }
        saved = graph.get_state(config)
        if saved.values and not saved.next:
            final = saved.values
        else:
            initial = None if saved.values else _initial_state(assignment)
            # Lưu xong từng bước rồi mới làm bước sau, để mất điện giữa chừng không mất bước nào.
            final = graph.invoke(initial, config, durability="sync")
        if final["error"] is not None:
            raise EditorError(f"Biên tập {final['error']}")
        return [
            WrittenStory(
                article_id=story["article_id"],
                reason=story["reason"],
                drafts=tuple(Draft(**draft) for draft in story["drafts"]),
            )
            for story in final["stories"]
        ]

    def _graph(self, read_article: Callable[[int], str]) -> Any:
        # LangGraph nhận diện node qua tham số tên `state`.
        def call_llm(state: _State) -> dict[str, Any]:
            reply = self._llm.invoke(state["messages"])
            return {"messages": [reply], "turns": state["turns"] + 1}

        def run_tools(state: _State) -> dict[str, Any]:
            reply = state["messages"][-1]
            assert isinstance(reply, AIMessage)
            candidates = {c["id"]: c for c in state["candidates"]}
            read_ids = set(state["read_ids"])
            newly_read: list[int] = []
            messages: list[AnyMessage] = [
                ToolMessage("Tham số không phải JSON hợp lệ.", tool_call_id=call["id"] or "")
                for call in reply.invalid_tool_calls
            ]
            stories = deepcopy(state["stories"])
            submission_errors: list[str] = []
            for call in reply.tool_calls:
                name, args = call["name"], call["args"]
                try:
                    if name == "read_article":
                        article_id = _ReadArgs.model_validate(args).id
                        was_read, content = self._read(article_id, candidates, read_article)
                        if was_read:
                            newly_read.append(article_id)
                    elif name == "web_search":
                        content = self._search(_SearchArgs.model_validate(args).query)
                    elif name == "submit_bulletin":
                        if stories is not None:
                            submission_errors = [
                                "Bản tin đã được nhận. Chỉ viết lại các Tin bị Kiểm chứng trả "
                                "lại, bằng rewrite_stories."
                            ]
                        else:
                            submission = _SubmittedBulletin.model_validate(args)
                            submission_errors = _check_submission(
                                submission,
                                candidates,
                                read_ids | set(newly_read),
                                state["max_stories"],
                            )
                            if not submission_errors:
                                stories = [_new_story(story) for story in submission.stories]
                        content = (
                            _rejection(submission_errors)
                            if submission_errors
                            else "Đã nhận Bản tin; các Tin được chuyển cho Kiểm chứng."
                        )
                    elif name == "rewrite_stories":
                        awaiting = {
                            story["article_id"]: story
                            for story in stories or ()
                            if _awaiting_rewrite(story)
                        }
                        if not awaiting:
                            submission_errors = ["Không có Tin nào đang chờ viết lại."]
                        else:
                            rewrite = _SubmittedRewrite.model_validate(args)
                            submission_errors = _check_rewrite(rewrite, awaiting, candidates)
                            if not submission_errors:
                                for draft in rewrite.stories:
                                    awaiting[draft.article_id]["drafts"].append(_new_draft(draft))
                        content = (
                            _rejection(submission_errors)
                            if submission_errors
                            else "Đã nhận các bản viết lại; chúng được chuyển cho Kiểm chứng."
                        )
                    else:
                        content = f"Không có công cụ {name}."
                except ValidationError as error:
                    arg_errors = [
                        f"{'.'.join(str(part) for part in item['loc']) or 'tham số'}: {item['msg']}"
                        for item in error.errors()
                    ]
                    if name in ("submit_bulletin", "rewrite_stories"):
                        submission_errors = arg_errors
                    content = _rejection(arg_errors)
                messages.append(ToolMessage(content, tool_call_id=call["id"] or ""))
            if not messages:
                messages.append(HumanMessage(USE_TOOLS_REMINDER))

            failed_submissions = state["failed_submissions"] + (1 if submission_errors else 0)
            update: dict[str, Any] = {
                "messages": messages,
                "read_ids": newly_read,
                "stories": stories,
                "failed_submissions": failed_submissions,
            }
            if failed_submissions >= MAX_FAILED_SUBMISSIONS:
                update["error"] = (
                    f"nộp Bản tin không hợp lệ {failed_submissions} lần; lần cuối: "
                    + "; ".join(submission_errors)
                )
            elif state["turns"] >= MAX_TURNS and not any(
                map(_awaiting_verification, stories or ())
            ):
                task = "nộp Bản tin" if stories is None else "viết lại xong các Tin bị trả lại"
                update["error"] = f"chưa {task} sau {MAX_TURNS} lượt"
            return update

        def verify(state: _State) -> dict[str, Any]:
            assert state["stories"] is not None
            stories = deepcopy(state["stories"])
            article_titles = {c["id"]: c["title"] for c in state["candidates"]}
            for story in filter(_awaiting_verification, stories):
                article_id, draft = story["article_id"], story["drafts"][-1]
                verdict = self._verifier.check(
                    state["verifier_guideline"],
                    article_titles[article_id],
                    read_article(article_id),
                    draft["title"],
                    draft["summary"],
                )
                draft["passed"], draft["reason"] = verdict.passed, verdict.reason
                log.info(
                    "Kiểm chứng Tin về Bài gốc %s: %s",
                    article_id,
                    "đạt" if verdict.passed else f"không đạt, {verdict.reason}",
                )
            update: dict[str, Any] = {"stories": stories}
            if any(map(_awaiting_rewrite, stories)):
                update["messages"] = [HumanMessage(_rewrite_request(stories))]
            return update

        def after_tools(state: _State) -> str:
            if state["error"] is not None:
                return END
            if any(map(_awaiting_verification, state["stories"] or ())):
                return "verify"
            return "call_llm"

        def after_verify(state: _State) -> str:
            assert state["stories"] is not None
            return "call_llm" if any(map(_awaiting_rewrite, state["stories"])) else END

        return (
            StateGraph(_State)
            .add_node("call_llm", call_llm)
            .add_node("run_tools", run_tools)
            .add_node("verify", verify)
            .add_edge(START, "call_llm")
            .add_edge("call_llm", "run_tools")
            .add_conditional_edges("run_tools", after_tools, ["call_llm", "verify", END])
            .add_conditional_edges("verify", after_verify, ["call_llm", END])
            .compile(checkpointer=self._checkpointer)
        )

    def _read(
        self,
        article_id: int,
        candidates: dict[int, dict[str, Any]],
        read_article: Callable[[int], str],
    ) -> tuple[bool, str]:
        """Toàn văn của Bài gốc `article_id` cho LLM đọc, kèm có đọc được hay không."""
        if article_id not in candidates:
            return False, f"Không có Bài gốc mã {article_id} trong danh sách ứng viên."
        url = candidates[article_id]["url"]
        log.info("Biên tập đọc Bài gốc %s", url)
        try:
            full_text = read_article(article_id)
        except Exception as error:
            log.warning("Không đọc được Bài gốc %s: %s", url, error)
            return (
                False,
                f"Không đọc được toàn văn Bài gốc {article_id}: {error}. Hãy chọn Bài gốc khác.",
            )
        return True, truncate_full_text(full_text)

    def _search(self, query: str) -> str:
        log.info("Biên tập tìm kiếm web: %s", query)
        try:
            results = self._searcher.search(query)
        except Exception as error:
            log.warning("Tìm kiếm web lỗi: %s", error)
            return f"Không tìm kiếm được: {error}. Hãy làm tiếp mà không cần tìm kiếm."
        if not results:
            return "Không có kết quả."
        return "Kết quả tìm kiếm (chỉ để hiểu bối cảnh, không phải Bài gốc):\n" + "\n".join(
            f"{position}. {result.title}\n   {result.url}\n   {result.snippet}"
            for position, result in enumerate(results, start=1)
        )


def _local_time(moment: datetime) -> str:
    return moment.astimezone(VIETNAM_TZ).isoformat(timespec="minutes")


def _describe_candidate(candidate: Candidate) -> str:
    """Một ứng viên như Biên tập thấy: một dòng JSON."""
    description: dict[str, Any] = {
        "articles": [
            {
                "id": article.id,
                "title": article.title,
                **({"description": article.description} if article.description else {}),
                "source": article.source,
                "url": article.url,
                "appeared_at": _local_time(article.appeared_at),
            }
            for article in candidate.articles
        ]
    }
    if candidate.published_story is not None:
        description["published_story"] = {
            "published_at": _local_time(candidate.published_story.published_at),
            "title": candidate.published_story.title,
            "summary": candidate.published_story.summary,
        }
    return json.dumps(description, ensure_ascii=False)


def _initial_state(assignment: Assignment) -> _State:
    max_stories = assignment.max_stories
    candidates = "\n".join(map(_describe_candidate, assignment.candidates))
    task = (
        f"Chuyên mục: {assignment.section}\n"
        f"Bây giờ là {_local_time(assignment.run_at)}.\n"
        f"Chọn từ {min(TARGET_STORIES, max_stories)} đến {max_stories} Tin đáng đọc nhất; chỉ "
        f"chọn ít hơn khi không đủ Bài gốc đáng đọc, và không bao giờ quá {max_stories}.\n\n"
        f"Ứng viên, mỗi dòng một ứng viên:\n{candidates}"
    )
    return {
        "messages": [
            SystemMessage(
                f"{SYSTEM_PROMPT}\n\n# Hướng dẫn của Chuyên mục\n\n{assignment.guideline}"
            ),
            HumanMessage(task),
        ],
        "candidates": [
            {
                "id": article.id,
                "title": article.title,
                "url": article.url,
                "group": position,
                "is_update": candidate.published_story is not None,
            }
            for position, candidate in enumerate(assignment.candidates)
            for article in candidate.articles
        ],
        "max_stories": max_stories,
        "verifier_guideline": assignment.verifier_guideline,
        "read_ids": [],
        "turns": 0,
        "failed_submissions": 0,
        "stories": None,
        "error": None,
    }


def _new_draft(draft: _SubmittedDraft) -> dict[str, Any]:
    return {"title": draft.title, "summary": draft.summary, "passed": None, "reason": None}


def _new_story(story: _SubmittedStory) -> dict[str, Any]:
    return {"article_id": story.article_id, "reason": story.reason, "drafts": [_new_draft(story)]}


def _check_submission(
    submission: _SubmittedBulletin,
    candidates: dict[int, dict[str, Any]],
    read_ids: set[int],
    max_stories: int,
) -> list[str]:
    """Những chỗ bản nộp chưa hợp lệ; rỗng là hợp lệ."""
    errors = []
    if len(submission.stories) > max_stories:
        errors.append(f"Có {len(submission.stories)} Tin, nhiều hơn mức tối đa {max_stories}.")
    # Bài gốc chính đã dùng đầu tiên của từng ứng viên.
    seen_groups: dict[int, int] = {}
    for story in submission.stories:
        article_id = story.article_id
        if article_id not in candidates:
            errors.append(
                f"Bài gốc mã {article_id} không có trong danh sách ứng viên. Tin chỉ được dẫn tới "
                "Bài gốc ứng viên, không dẫn tới kết quả tìm kiếm."
            )
            continue
        # Trạng thái lưu từ trước khi có Gom Tin không có `group`: mỗi Bài gốc là một ứng viên.
        group = candidates[article_id].get("group", -article_id)
        if group in seen_groups:
            earlier = seen_groups[group]
            errors.append(
                f"Bài gốc {article_id} được dùng cho hơn một Tin."
                if earlier == article_id
                else f"Bài gốc {earlier} và {article_id} thuộc cùng một ứng viên, tức cùng một sự "
                "kiện; mỗi ứng viên chỉ thành một Tin."
            )
        seen_groups.setdefault(group, article_id)
        if article_id not in read_ids:
            errors.append(
                f"Tin về Bài gốc {article_id}: chưa đọc toàn văn; gọi read_article trước khi viết."
            )
        errors += _check_draft(story, candidates[article_id])
    return errors


def _check_rewrite(
    rewrite: _SubmittedRewrite,
    awaiting: dict[int, dict[str, Any]],
    candidates: dict[int, dict[str, Any]],
) -> list[str]:
    """Những chỗ bản viết lại chưa hợp lệ; rỗng là hợp lệ."""
    errors = []
    seen_ids: set[int] = set()
    for draft in rewrite.stories:
        article_id = draft.article_id
        if article_id not in awaiting:
            errors.append(
                f"Tin về Bài gốc {article_id} không bị trả lại; chỉ viết lại Tin bị trả lại."
            )
            continue
        if article_id in seen_ids:
            errors.append(
                f"Tin về Bài gốc {article_id} được viết lại hơn một lần trong cùng bản nộp."
            )
        seen_ids.add(article_id)
        errors += _check_draft(draft, candidates[article_id])
    for article_id in awaiting.keys() - seen_ids:
        errors.append(f"Thiếu bản viết lại của Tin về Bài gốc {article_id}.")
    return errors


def _check_draft(draft: _SubmittedDraft, primary_article: dict[str, Any]) -> list[str]:
    """Những chỗ một bản viết vi phạm quy tắc viết; rỗng là hợp lệ."""
    errors = []
    article_id = draft.article_id
    # Tiêu đề ngắn và nhiều tên riêng nên không soát được bằng cách này.
    if not is_vietnamese(draft.summary):
        errors.append(f"Tin về Bài gốc {article_id}: tóm tắt phải bằng tiếng Việt.")
    if HAS_LINK.search(draft.title) or HAS_LINK.search(draft.summary):
        errors.append(f"Tin về Bài gốc {article_id}: tiêu đề và tóm tắt không được chứa link.")
    length = StoryContent(
        draft.title,
        draft.summary,
        primary_article["url"],
        primary_article.get("is_update", False),
    ).length
    if length > MAX_STORY_LENGTH:
        errors.append(
            f"Tin về Bài gốc {article_id}: tiêu đề, tóm tắt và link dài {length} ký tự, vượt "
            f"giới hạn {MAX_STORY_LENGTH}; rút gọn {length - MAX_STORY_LENGTH} ký tự."
        )
    return errors


def _rewrite_request(stories: Sequence[dict[str, Any]]) -> str:
    """Lời Kiểm chứng gửi Biên tập: những Tin phải viết lại, và những Tin vừa bị bỏ."""
    to_rewrite = [
        f"- Bài gốc {story['article_id']}, lần viết lại {len(story['drafts'])}/"
        f"{MAX_REWRITES}. Bản hiện tại: {story['drafts'][-1]['title']!r}. "
        f"Lí do: {story['drafts'][-1]['reason']}"
        for story in stories
        if _awaiting_rewrite(story)
    ]
    dropped = [
        str(story["article_id"])
        for story in stories
        if story["drafts"][-1]["passed"] is False and not _awaiting_rewrite(story)
    ]
    message = (
        "Kiểm chứng đã đối chiếu các Tin với Bài gốc. Những Tin dưới đây không đạt: viết lại "
        "từng Tin theo lí do, chỉ dựa trên toàn văn Bài gốc, rồi gọi rewrite_stories với đủ các "
        "Tin này. Các Tin khác không cần sửa.\n" + "\n".join(to_rewrite)
    )
    if dropped:
        message += (
            f"\n\nTin về Bài gốc {', '.join(dropped)} đã bị bỏ khỏi Bản tin vì không đạt sau "
            f"{MAX_REWRITES} lần viết lại."
        )
    return message


def _rejection(errors: Sequence[str]) -> str:
    return "Chưa hợp lệ, hãy sửa rồi gọi lại:\n" + "\n".join(f"- {error}" for error in errors)
