"""Kiểm chứng: Agent đối chiếu từng Tin đã viết với toàn văn Bài gốc của nó.

Mỗi lần xét là một Tin. LLM trả kết luận bằng công cụ `verdict`; kết luận được kiểm tra bằng
code, hỏng thì nhắc lại, hỏng quá số lần cho phép thì là lỗi của Kỳ.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from bulletin.agents import truncate_full_text

log = logging.getLogger(__name__)

MAX_INVALID_REPLIES = 3

SYSTEM_PROMPT = """\
Bạn là Kiểm chứng của một bản tin tiếng Việt phát định kỳ, và là chốt chặn duy nhất trước khi \
Tin được phát: không ai duyệt lại sau bạn. Bạn nhận một Tin do Biên tập viết (tiêu đề và tóm tắt) \
cùng toàn văn Bài gốc của nó.

Đối chiếu Tin với toàn văn theo Hướng dẫn bên dưới. Toàn văn Bài gốc là căn cứ duy nhất: chi tiết \
nào không có trong đó thì coi như không có căn cứ, kể cả khi bạn tin là nó đúng.

Gọi verdict đúng một lần. passed là true khi Tin đạt. Khi không đạt, reason phải chỉ ra từng chi \
tiết sai, Tin viết gì và Bài gốc nói gì, để Biên tập sửa được mà không phải đoán."""

USE_TOOLS_REMINDER = "Câu trả lời bằng chữ không được ghi nhận. Hãy gọi verdict."

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "verdict",
            "description": "Kết luận Tin đạt hay không đạt khi đối chiếu với Bài gốc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "passed": {"type": "boolean", "description": "Tin có đạt không"},
                    "reason": {
                        "type": "string",
                        "description": (
                            "Những chi tiết sai và Bài gốc nói gì; bắt buộc khi không đạt"
                        ),
                    },
                },
                "required": ["passed", "reason"],
            },
        },
    }
]


@dataclass(frozen=True)
class Verdict:
    passed: bool
    # Khi đạt thì có thể trống.
    reason: str


class VerifierError(Exception):
    """Kiểm chứng không ra được kết luận hợp lệ."""


class _SubmittedVerdict(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    passed: bool
    reason: str = ""

    @model_validator(mode="after")
    def _failure_needs_reason(self) -> "_SubmittedVerdict":
        if not self.passed and not self.reason:
            raise ValueError("không đạt thì phải nêu reason")
        return self


class Verifier:
    def __init__(self, llm: BaseChatModel) -> None:
        self._llm = llm.bind_tools(TOOLS)

    def check(
        self, guideline: str, article_title: str, full_text: str, title: str, summary: str
    ) -> Verdict:
        """Đối chiếu một Tin (`title`, `summary`) với Bài gốc của nó.

        Ném `VerifierError` khi LLM lỗi hoặc mãi không trả được kết luận hợp lệ.
        """
        story = json.dumps({"title": title, "summary": summary}, ensure_ascii=False)
        messages: list[AnyMessage] = [
            SystemMessage(f"{SYSTEM_PROMPT}\n\n# Hướng dẫn của Kiểm chứng\n\n{guideline}"),
            HumanMessage(
                f"Bài gốc: {article_title}\n\n"
                f"Toàn văn Bài gốc:\n{truncate_full_text(full_text)}\n\n"
                f"Tin cần đối chiếu:\n{story}"
            ),
        ]
        errors: list[str] = []
        for _ in range(MAX_INVALID_REPLIES):
            try:
                reply = self._llm.invoke(messages)
            except Exception as call_error:
                raise VerifierError(
                    f"Kiểm chứng gặp lỗi: {str(call_error).splitlines()[0]}"
                ) from call_error
            assert isinstance(reply, AIMessage)
            verdict, errors, feedback = _parse_verdict(reply)
            if verdict is not None:
                return verdict
            log.warning("Kiểm chứng trả kết luận không hợp lệ: %s", "; ".join(errors))
            messages += [reply, *feedback]
        raise VerifierError(
            f"Kiểm chứng trả kết luận không hợp lệ {MAX_INVALID_REPLIES} lần; lần cuối: "
            + "; ".join(errors)
        )


def _parse_verdict(
    reply: AIMessage,
) -> tuple[Verdict | None, list[str], list[AnyMessage]]:
    """Kết luận trong câu trả lời nếu hợp lệ; nếu không thì các lỗi và tin nhắn trả lại LLM."""
    verdict_calls = [call for call in reply.tool_calls if call["name"] == "verdict"]
    if len(verdict_calls) == 1 and not reply.invalid_tool_calls:
        args: dict[str, Any] = verdict_calls[0]["args"]
        try:
            submitted = _SubmittedVerdict.model_validate(args)
            return Verdict(submitted.passed, submitted.reason), [], []
        except ValidationError as validation_error:
            errors = [
                f"{'.'.join(str(part) for part in item['loc']) or 'tham số'}: {item['msg']}"
                for item in validation_error.errors()
            ]
    elif verdict_calls or reply.invalid_tool_calls:
        errors = ["phải gọi verdict đúng một lần, với tham số JSON hợp lệ"]
    else:
        errors = ["không gọi verdict"]

    content = "Chưa hợp lệ, hãy gọi lại verdict:\n" + "\n".join(f"- {item}" for item in errors)
    feedback: list[AnyMessage] = [
        ToolMessage(content, tool_call_id=call["id"] or "")
        for call in (*reply.tool_calls, *reply.invalid_tool_calls)
    ]
    return None, errors, feedback or [HumanMessage(USE_TOOLS_REMINDER)]
