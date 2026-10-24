"""Bộ thử endpoint LLM: từng model làm được gì, trước khi vòng agent dựa vào nó.

Gọi endpoint thật qua `siftly probe-llm`; mỗi model tốn khoảng mười lời gọi ngắn.
"""

import json
import time
from collections import Counter
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from siftly.vietnamese import is_vietnamese

# Tên và nhãn các phép thử trên từng model, theo thứ tự chạy và thứ tự cột trong báo cáo.
CHECKS = {
    "basic_call": "Gọi thường",
    "non_stream": "Không stream",
    "single_turn_tools": "Công cụ một lượt",
    "multi_turn_tools": "Công cụ nhiều lượt",
    "json_schema": "JSON theo schema",
    "json_via_prompt": "JSON theo prompt",
    "vietnamese": "Viết tiếng Việt",
}
MAX_TURNS = 6

Json = dict[str, Any]


class EndpointError(Exception):
    """Endpoint từ chối hoặc không tới được; thông điệp không chứa khoá."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        # Endpoint bảo chờ ngần này giây (đầu `retry-after`) rồi mới gọi lại model được.
        self.retry_after = retry_after


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class Reply:
    content: str
    tool_calls: tuple[ToolCall, ...] = ()
    # Một số model suy luận đòi nhận lại phần suy luận ở lượt sau.
    reasoning: str = ""

    def to_message(self) -> Json:
        message: Json = {"role": "assistant", "content": self.content}
        if self.reasoning:
            message["reasoning_content"] = self.reasoning
        if self.tool_calls:
            message["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": call.arguments},
                }
                for call in self.tool_calls
            ]
        return message


class LLMEndpoint:
    """Endpoint tương thích OpenAI, đủ cho bộ thử: liệt kê model, trò chuyện, tạo vector nhúng."""

    def __init__(self, client: httpx.Client, base_url: str, api_key: str) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {api_key}"}

    def models(self) -> list[str]:
        response = self._send("GET", "/models")
        return sorted(str(model["id"]) for model in _json(response)["data"])

    def chat(self, model: str, messages: Sequence[Json], **options: object) -> Reply:
        """Gọi dạng stream, là dạng mọi model của endpoint đều trả đúng chuẩn."""
        body = {"model": model, "messages": list(messages), "stream": True, **options}
        content, reasoning = "", ""
        calls: dict[int, dict[str, str]] = {}
        try:
            with self._client.stream(
                "POST", self._base_url + "/chat/completions", json=body, headers=self._headers
            ) as response:
                if response.is_error:
                    response.read()
                    raise _rejection_error(response)
                for line in response.iter_lines():
                    if not line.startswith("data:") or line[5:].strip() == "[DONE]":
                        continue
                    chunk = json.loads(line[5:])
                    if chunk.get("error"):
                        raise EndpointError(f"Lỗi giữa stream: {_error_message(chunk)}")
                    for choice in chunk.get("choices") or []:
                        delta = choice.get("delta") or {}
                        content += delta.get("content") or ""
                        reasoning += delta.get("reasoning_content") or ""
                        for call_chunk in delta.get("tool_calls") or []:
                            function = call_chunk.get("function") or {}
                            partial = calls.setdefault(
                                call_chunk.get("index", 0), {"id": "", "name": "", "arguments": ""}
                            )
                            partial["id"] += call_chunk.get("id") or ""
                            partial["name"] += function.get("name") or ""
                            partial["arguments"] += function.get("arguments") or ""
        except httpx.HTTPError as error:
            raise EndpointError(f"Không kết nối được ({type(error).__name__})") from None
        except ValueError:
            raise EndpointError("Stream có dòng không phải JSON") from None
        return Reply(content, tuple(ToolCall(**calls[index]) for index in sorted(calls)), reasoning)

    def chat_non_stream(self, model: str, messages: Sequence[Json]) -> str:
        """Gọi không stream và đọc thân phản hồi như một client chuẩn: cả thân phải là JSON."""
        body = {"model": model, "messages": list(messages)}
        message = _json(self._send("POST", "/chat/completions", body))["choices"][0]["message"]
        return str(message.get("content") or "")

    def embed(self, model: str, text: str) -> list[float]:
        body = {"model": model, "input": [text]}
        vector: list[float] = _json(self._send("POST", "/embeddings", body))["data"][0]["embedding"]
        return vector

    def _send(self, method: str, path: str, body: Json | None = None) -> httpx.Response:
        try:
            response = self._client.request(
                method, self._base_url + path, json=body, headers=self._headers
            )
        except httpx.HTTPError as error:
            raise EndpointError(f"Không kết nối được ({type(error).__name__})") from None
        if response.is_error:
            raise _rejection_error(response)
        return response


def _json(response: httpx.Response) -> Json:
    try:
        data = response.json()
    except ValueError:
        raise EndpointError(
            f"Thân phản hồi không phải JSON hợp lệ: …{response.text[-40:]!r}"
        ) from None
    if not isinstance(data, dict):
        raise EndpointError("Thân phản hồi không phải một đối tượng JSON")
    return data


def _error_message(data: object) -> str:
    error = data.get("error") if isinstance(data, dict) else None
    return str(error.get("message") if isinstance(error, dict) else error or data)


def _rejection_error(response: httpx.Response) -> EndpointError:
    try:
        message = _error_message(response.json())
    except ValueError:
        message = response.text[:200]
    retry_after = response.headers.get("retry-after", "")
    return EndpointError(
        f"HTTP {response.status_code}: {message}"
        + (f" (retry-after: {retry_after})" if retry_after else ""),
        retry_after=float(retry_after) if retry_after.isdigit() else None,
    )


@dataclass(frozen=True)
class CheckResult:
    # None là phép thử bị bỏ qua.
    passed: bool | None
    note: str = ""


@dataclass(frozen=True)
class ModelResult:
    model: str
    # Tổng thời gian của các lời gọi, không kể lúc chờ endpoint mở khoá.
    seconds: float
    checks: dict[str, CheckResult] = field(default_factory=dict)


def probe_model(
    endpoint: LLMEndpoint, model: str, sleep: Callable[[float], None] = time.sleep
) -> ModelResult:
    """Chạy mọi phép thử trên một model. Gọi thường không được thì bỏ qua phần còn lại.

    Endpoint có thể khoá cả model một lúc sau khi từ chối một lời gọi; khi đó chờ hết hạn
    (qua `sleep`) rồi mới đi tiếp, để lời gọi sau không bị từ chối oan.
    """
    runners: dict[str, Callable[[LLMEndpoint, str], CheckResult]] = {
        "basic_call": _basic_call,
        "non_stream": _non_stream,
        "single_turn_tools": _single_turn_tools,
        "multi_turn_tools": _multi_turn_tools,
        "json_schema": lambda e, m: _structured(e, m, use_schema=True),
        "json_via_prompt": lambda e, m: _structured(e, m, use_schema=False),
        "vietnamese": _vietnamese,
    }
    seconds = 0.0
    results: dict[str, CheckResult] = {}
    for name in CHECKS:
        if results and results["basic_call"].passed is not True:
            results[name] = CheckResult(None)
            continue
        started = time.monotonic()
        retry_after = None
        try:
            results[name] = runners[name](endpoint, model)
        except EndpointError as error:
            results[name] = CheckResult(False, str(error))
            retry_after = error.retry_after
        # Thời gian chờ mở khoá không tính vào thời gian làm việc của model.
        seconds += time.monotonic() - started
        if retry_after is not None:
            sleep(retry_after + 1)
    return ModelResult(model, seconds, results)


def probe_embedding(endpoint: LLMEndpoint, model: str) -> CheckResult:
    """Endpoint có tạo được vector nhúng bằng `model` không."""
    try:
        vector = endpoint.embed(model, "Hãng công bố mẫu pin thể rắn mới.")
    except EndpointError as error:
        return CheckResult(False, str(error))
    return CheckResult(True, f"{len(vector)} chiều")


def _user(content: str) -> list[Json]:
    return [{"role": "user", "content": content}]


def _basic_call(endpoint: LLMEndpoint, model: str) -> CheckResult:
    reply = endpoint.chat(model, _user("Trả lời đúng một từ: xin chào"))
    return CheckResult(bool(reply.content.strip()), "" if reply.content else "Trả về rỗng")


def _non_stream(endpoint: LLMEndpoint, model: str) -> CheckResult:
    content = endpoint.chat_non_stream(model, _user("Trả lời đúng một từ: xin chào"))
    return CheckResult(bool(content.strip()), "" if content else "Trả về rỗng")


def _tool(name: str, description: str, param: str, param_type: str) -> Json:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {param: {"type": param_type}},
                "required": [param],
                "additionalProperties": False,
            },
        },
    }


READ_ARTICLE = _tool("read_article", "Đọc toàn văn một Bài gốc theo mã.", "id", "integer")
SEARCH_ARTICLES = _tool(
    "search_articles", "Tìm Bài gốc theo từ khoá; trả về mã và tiêu đề.", "query", "string"
)
ARTICLES = {
    3310: (
        "Giá pin lithium giảm quý thứ ba liên tiếp",
        "Giá pin lithium-ion tiếp tục giảm do dư cung, theo báo cáo thị trường mới nhất.",
    ),
    # Con số chỉ có trong toàn văn, nên muốn trả lời đúng thì phải đọc bài.
    4172: (
        "QuantumCell công bố pin thể rắn có mật độ năng lượng kỷ lục",
        "QuantumCell cho biết mẫu pin thể rắn mới đạt mật độ năng lượng 487 Wh/kg trong thử "
        "nghiệm độc lập, và dự kiến sản xuất thử từ năm 2028.",
    ),
}
ARTICLE_TO_READ, FIGURE_IN_ARTICLE = 4172, "487"


def _args(call: ToolCall) -> Json:
    try:
        args = json.loads(call.arguments)
    except ValueError:
        return {}
    return args if isinstance(args, dict) else {}


def _single_turn_tools(endpoint: LLMEndpoint, model: str) -> CheckResult:
    reply = endpoint.chat(
        model, _user(f"Hãy đọc Bài gốc có mã {ARTICLE_TO_READ}."), tools=[READ_ARTICLE]
    )
    if not reply.tool_calls:
        return CheckResult(False, f"Không gọi công cụ, trả lời: {reply.content[:80]!r}")
    call = reply.tool_calls[0]
    if call.name != "read_article" or _args(call) != {"id": ARTICLE_TO_READ}:
        return CheckResult(False, f"Gọi sai: {call.name}({call.arguments})")
    return CheckResult(True)


def _run_tool(call: ToolCall) -> str:
    args = _args(call)
    if call.name == "search_articles":
        return json.dumps(
            [{"id": article_id, "title": title} for article_id, (title, _) in ARTICLES.items()],
            ensure_ascii=False,
        )
    if call.name == "read_article" and args.get("id") in ARTICLES:
        return ARTICLES[args["id"]][1]
    return f"Lỗi: không có {call.name}({call.arguments})"


def _multi_turn_tools(endpoint: LLMEndpoint, model: str) -> CheckResult:
    """Model phải tìm, đọc đúng bài rồi trả lời bằng con số chỉ có trong toàn văn."""
    messages = _user(
        "Dùng công cụ để tìm Bài gốc về pin thể rắn, đọc toàn văn bài đó, "
        "rồi cho biết mật độ năng lượng mà bài nêu."
    )
    called: list[str] = []
    for _ in range(MAX_TURNS):
        reply = endpoint.chat(model, messages, tools=[SEARCH_ARTICLES, READ_ARTICLE])
        if not reply.tool_calls:
            break
        messages.append(reply.to_message())
        for call in reply.tool_calls:
            called.append(f"{call.name}({call.arguments})")
            messages.append({"role": "tool", "tool_call_id": call.id, "content": _run_tool(call)})
    else:
        return CheckResult(False, f"Chưa trả lời sau {MAX_TURNS} lượt: {', '.join(called)}")

    called_names = [call.split("(")[0] for call in called]
    if "search_articles" not in called_names or "read_article" not in called_names:
        missing = "read_article" if "read_article" not in called_names else "search_articles"
        return CheckResult(False, f"Trả lời mà không gọi {missing}; đã gọi: {', '.join(called)}")
    if FIGURE_IN_ARTICLE not in reply.content:
        return CheckResult(False, f"Trả lời thiếu con số trong bài: {reply.content[:120]!r}")
    return CheckResult(True, f"{len(called)} lời gọi công cụ")


class _Assessment(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    score: int = Field(ge=1, le=10)
    should_pick: bool


ASSESSMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "score": {"type": "integer"},
        "should_pick": {"type": "boolean"},
    },
    "required": ["title", "summary", "score", "should_pick"],
    "additionalProperties": False,
}


def _structured(endpoint: LLMEndpoint, model: str, *, use_schema: bool) -> CheckResult:
    """Kết quả có cấu trúc, kiểm tra bằng code; có hoặc không nhờ tới `response_format`."""
    prompt = _user(
        "Đánh giá Bài gốc sau cho Chuyên mục công nghệ. Chỉ trả về một đối tượng JSON, không kèm "
        "chữ nào khác, gồm đúng các trường: title (chuỗi), summary (chuỗi, một câu), "
        "score (số nguyên từ 1 đến 10), should_pick (true hoặc false).\n\n"
        f"Bài gốc: {ARTICLES[ARTICLE_TO_READ][1]}"
    )
    options: dict[str, object] = {}
    if use_schema:
        options["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "assessment", "strict": True, "schema": ASSESSMENT_SCHEMA},
        }
    content = endpoint.chat(model, prompt, **options).content.strip()
    note = ""
    if content.startswith("```"):
        content = content.strip("`").removeprefix("json").strip()
        note = "Bọc trong khối ```; phải gỡ trước khi đọc"
    try:
        _Assessment.model_validate_json(content)
    except ValidationError as error:
        first = error.errors()[0]
        location = ".".join(str(part) for part in first["loc"]) or "gốc"
        return CheckResult(False, f"Sai ở {location}: {first['msg']}; nhận {content[:80]!r}")
    return CheckResult(True, note)


ENGLISH_PASSAGE = (
    "Nvidia said on Tuesday that its next-generation Rubin GPUs will be manufactured by TSMC "
    "using a 2-nanometer process, with volume shipments expected in the second half of 2027. "
    "The company claims the new chips cut inference costs by 30% compared with the current "
    "Blackwell generation."
)
NAMES_TO_KEEP = ("Nvidia", "Rubin", "GPU", "TSMC", "Blackwell")


def _vietnamese(endpoint: LLMEndpoint, model: str) -> CheckResult:
    """Tóm tắt tiếng Việt từ văn bản tiếng Anh. Chỉ soát được phần máy soát được; người đọc
    xem bản tóm tắt trong ghi chú để tự đánh giá câu chữ."""
    summary = endpoint.chat(
        model,
        _user(
            "Tóm tắt đoạn sau bằng tiếng Việt trong hai câu. Giữ nguyên tên riêng và thuật ngữ "
            f"chuyên ngành quen dùng bằng tiếng Anh.\n\n{ENGLISH_PASSAGE}"
        ),
    ).content.strip()
    missing = [name for name in NAMES_TO_KEEP if name not in summary]
    passed = is_vietnamese(summary) and not missing and "30" in summary
    return CheckResult(passed, " ".join(summary.split()))


def burst(endpoint: LLMEndpoint, model: str, call_count: int) -> Counter[str]:
    """Gửi `call_count` lời gọi cùng lúc để xem endpoint trả gì khi bị dồn; đếm theo kết quả."""

    def call(_: int) -> str:
        try:
            endpoint.chat(model, _user("Trả lời đúng một từ: xin chào"))
        except EndpointError as error:
            return str(error)
        return "thành công"

    with ThreadPoolExecutor(max_workers=call_count) as pool:
        return Counter(pool.map(call, range(call_count)))


def probe_models(
    endpoint: LLMEndpoint, models: Sequence[str], sleep: Callable[[float], None] = time.sleep
) -> list[ModelResult]:
    """Thử nhiều model, trả kết quả theo đúng thứ tự `models`.

    Model cùng tiền tố nhà cung cấp (phần trước dấu `/`) được thử lần lượt, vì nhiều tên có thể
    trỏ về cùng một model gốc và endpoint khoá theo model gốc. Các nhà cung cấp chạy song song.
    """
    by_provider: dict[str, list[str]] = {}
    for model in models:
        by_provider.setdefault(model.split("/")[0], []).append(model)

    def probe_provider(provider_models: list[str]) -> list[ModelResult]:
        return [probe_model(endpoint, model, sleep) for model in provider_models]

    with ThreadPoolExecutor(max_workers=max(len(by_provider), 1)) as pool:
        probed = {
            result.model: result
            for results in pool.map(probe_provider, by_provider.values())
            for result in results
        }
    return [probed[model] for model in models]


def report(results: Sequence[ModelResult]) -> str:
    """Bảng markdown đạt/không đạt theo model, kèm lí do của từng phép thử không đạt."""
    symbols = {True: "đạt", False: "KHÔNG", None: "–"}
    lines = [
        "| Model | " + " | ".join(CHECKS.values()) + " | Giây |",
        "| --- |" + " --- |" * (len(CHECKS) + 1),
    ]
    for result in results:
        cells = [symbols[result.checks[name].passed] for name in CHECKS]
        lines.append(f"| `{result.model}` | " + " | ".join(cells) + f" | {result.seconds:.0f} |")
    lines.append("")
    for result in results:
        for name, label in CHECKS.items():
            check = result.checks[name]
            if check.note and (check.passed is False or name == "vietnamese"):
                lines.append(f"- `{result.model}`, {label.lower()}: {check.note}")
    return "\n".join(lines)
