"""Bộ thử endpoint LLM, test bằng một endpoint giả trả lời theo kịch bản; không gọi mạng."""

import json
import threading
import time
from collections import Counter
from typing import Any

import httpx
import pytest

from bulletin.llm_probe import LLMEndpoint, probe_embedding, probe_model, probe_models

BASE_URL = "http://llm.example/v1"
API_KEY = "sk-test"
MODEL = "provider/test-model"


def _stream(*chunks: dict[str, Any]) -> httpx.Response:
    body = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"
    return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})


def _delta(delta: dict[str, Any], finish_reason: str | None = None) -> dict[str, Any]:
    return {"choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}]}


class FakeEndpoint:
    """Đứng thay endpoint LLM: một model ngoan, làm đúng mọi phép thử, trừ khi test bảo khác."""

    def __init__(self) -> None:
        self.ignore_tools = False
        self.guess_instead_of_reading = False
        self.prose_instead_of_json = False
        self.reject_response_format = False
        # Số giây endpoint từ chối mọi lời gọi tới model sau một lần từ chối; 0 là không khoá.
        self.lock_model_after_rejection = 0
        self.locked = False
        self.non_stream_with_done = False
        self.reply_in_english = False
        self.error: httpx.Response | None = None
        self.keys_received: set[str] = set()
        self.client = httpx.Client(transport=httpx.MockTransport(self._respond))

    @property
    def endpoint(self) -> LLMEndpoint:
        return LLMEndpoint(self.client, BASE_URL, API_KEY)

    def _respond(self, request: httpx.Request) -> httpx.Response:
        self.keys_received.add(request.headers.get("authorization", ""))
        body = json.loads(request.content)
        if request.url.path.endswith("/embeddings"):
            if self.error:
                return self.error
            return httpx.Response(200, json={"data": [{"embedding": [0.1] * 1536}]})
        if self.error:
            return self.error
        if self.locked or ("response_format" in body and self.reject_response_format):
            error_body = {"error": {"message": "response_format lạ"}}
            if not self.lock_model_after_rejection:
                return httpx.Response(400, json=error_body)
            self.locked = True
            retry = {"retry-after": str(self.lock_model_after_rejection)}
            return httpx.Response(400, json=error_body, headers=retry)

        tool_calls = self._tool_calls(body)
        content = None if tool_calls else self._content(body)
        if not body.get("stream"):
            message = {"role": "assistant", "content": content, "tool_calls": tool_calls}
            data = json.dumps({"choices": [{"message": message, "finish_reason": "stop"}]})
            if self.non_stream_with_done:
                data += "data: [DONE]\n\n"
            return httpx.Response(200, content=data)
        if tool_calls:
            [call] = tool_calls
            arguments = call["function"]["arguments"]
            head = {**call, "index": 0, "function": {**call["function"], "arguments": ""}}
            return _stream(
                _delta({"role": "assistant", "content": ""}),
                _delta({"tool_calls": [head]}),
                # Tham số tới thành nhiều mảnh, như endpoint thật.
                _delta({"tool_calls": [{"index": 0, "function": {"arguments": arguments[:3]}}]}),
                _delta({"tool_calls": [{"index": 0, "function": {"arguments": arguments[3:]}}]}),
                _delta({}, "tool_calls"),
            )
        assert content is not None
        middle = len(content) // 2
        return _stream(
            _delta({"content": content[:middle]}), _delta({"content": content[middle:]}, "stop")
        )

    def _tool_calls(self, body: dict[str, Any]) -> list[dict[str, Any]] | None:
        tool_names = {t["function"]["name"] for t in body.get("tools", [])}
        if not tool_names or self.ignore_tools:
            return None

        def call(name: str, **args: object) -> list[dict[str, Any]]:
            function = {"name": name, "arguments": json.dumps(args)}
            return [{"id": f"call_{name}", "type": "function", "function": function}]

        called = [
            c["function"]["name"]
            for message in body["messages"]
            if message["role"] == "assistant"
            for c in message.get("tool_calls") or []
        ]
        if "search_articles" not in tool_names:
            return None if called else call("read_article", id=4172)
        if not called:
            return call("search_articles", query="pin thể rắn")
        if called == ["search_articles"] and not self.guess_instead_of_reading:
            search_results = json.loads(body["messages"][-1]["content"])
            [article_id] = [a["id"] for a in search_results if "thể rắn" in a["title"]]
            return call("read_article", id=article_id)
        return None

    def _content(self, body: dict[str, Any]) -> str:
        last = body["messages"][-1]
        if last["role"] == "tool":
            if self.guess_instead_of_reading:
                return "Mật độ năng lượng khoảng 500 Wh/kg."
            # Nhắc lại đúng con số có trong kết quả của công cụ.
            [figure] = [w for w in last["content"].split() if w.isdigit() and len(w) == 3]
            return f"Bài nêu mật độ năng lượng {figure} Wh/kg."
        prompt = str(last["content"])
        if "JSON" in prompt:
            if self.prose_instead_of_json:
                return "Bài này đáng chọn, tôi cho 8 điểm."
            return json.dumps(
                {"title": "Pin thể rắn", "summary": "Một câu.", "score": 8, "should_pick": True}
            )
        if "Nvidia" in prompt:
            if self.reply_in_english:
                return "Nvidia says Rubin GPUs will be made by TSMC and cut costs by 30%."
            return (
                "Nvidia cho biết dòng GPU Rubin thế hệ tiếp theo sẽ do TSMC sản xuất trên tiến "
                "trình 2 nanomet. Hãng nói chip mới giảm 30% chi phí suy luận so với Blackwell."
            )
        return "xin chào"


def passed(fake: FakeEndpoint) -> dict[str, bool | None]:
    result = probe_model(fake.endpoint, MODEL)
    return {name: check.passed for name, check in result.checks.items()}


def test_model_doing_everything_right_passes_every_check() -> None:
    fake = FakeEndpoint()

    assert passed(fake) == {
        "basic_call": True,
        "non_stream": True,
        "single_turn_tools": True,
        "multi_turn_tools": True,
        "json_schema": True,
        "json_via_prompt": True,
        "vietnamese": True,
    }
    assert fake.keys_received == {f"Bearer {API_KEY}"}


def test_model_replying_in_text_instead_of_calling_tools_fails_both_tool_checks() -> None:
    fake = FakeEndpoint()
    fake.ignore_tools = True

    result = passed(fake)

    assert (result["single_turn_tools"], result["multi_turn_tools"]) == (False, False)
    assert result["basic_call"] is True
    assert result["vietnamese"] is True


def test_model_answering_without_reading_article_fails_multi_turn_tools() -> None:
    fake = FakeEndpoint()
    fake.guess_instead_of_reading = True

    checks = probe_model(fake.endpoint, MODEL).checks

    assert checks["single_turn_tools"].passed is True
    assert checks["multi_turn_tools"].passed is False
    assert "read_article" in checks["multi_turn_tools"].note


def test_prose_instead_of_json_fails_structured_output_checks() -> None:
    fake = FakeEndpoint()
    fake.prose_instead_of_json = True

    result = passed(fake)

    assert (result["json_schema"], result["json_via_prompt"]) == (False, False)


def test_endpoint_rejecting_response_format_fails_only_json_schema() -> None:
    fake = FakeEndpoint()
    fake.reject_response_format = True

    checks = probe_model(fake.endpoint, MODEL).checks

    assert checks["json_schema"].passed is False
    assert "response_format lạ" in checks["json_schema"].note
    assert checks["json_via_prompt"].passed is True


def test_endpoint_locking_model_after_rejection_makes_probe_wait_before_continuing() -> None:
    fake = FakeEndpoint()
    fake.reject_response_format = True
    fake.lock_model_after_rejection = 30
    waited: list[float] = []

    def sleep(seconds: float) -> None:
        waited.append(seconds)
        fake.locked = False

    checks = probe_model(fake.endpoint, MODEL, sleep=sleep).checks

    assert checks["json_schema"].passed is False
    # Không chờ thì hai phép thử sau cũng bị từ chối oan vì model đang bị khoá.
    assert (checks["json_via_prompt"].passed, checks["vietnamese"].passed) == (True, True)
    assert waited == [31]


def test_non_stream_body_with_done_line_fails_non_stream() -> None:
    fake = FakeEndpoint()
    fake.non_stream_with_done = True

    result = passed(fake)

    assert result["non_stream"] is False
    assert result["basic_call"] is True


def test_summary_still_in_english_fails_vietnamese() -> None:
    fake = FakeEndpoint()
    fake.reply_in_english = True

    assert passed(fake)["vietnamese"] is False


def test_model_rejected_by_endpoint_records_reason_and_skips_remaining_checks() -> None:
    fake = FakeEndpoint()
    fake.error = httpx.Response(
        400,
        json={"error": {"message": "model không dùng được với tài khoản này"}},
        headers={"retry-after": "28"},
    )

    waited: list[float] = []

    checks = probe_model(fake.endpoint, MODEL, sleep=waited.append).checks

    assert checks["basic_call"].passed is False
    assert checks["basic_call"].note == (
        "HTTP 400: model không dùng được với tài khoản này (retry-after: 28)"
    )
    # Chờ hết hạn khoá, để model kế tiếp cùng model gốc không bị từ chối oan.
    assert waited == [29]
    assert {name: check.passed for name, check in checks.items() if name != "basic_call"} == {
        "non_stream": None,
        "single_turn_tools": None,
        "multi_turn_tools": None,
        "json_schema": None,
        "json_via_prompt": None,
        "vietnamese": None,
    }


def test_endpoint_creating_embeddings_reports_dimensions() -> None:
    result = probe_embedding(FakeEndpoint().endpoint, "text-embedding-3-small")

    assert result.passed is True
    assert result.note == "1536 chiều"


def test_endpoint_unable_to_create_embeddings_reports_reason() -> None:
    fake = FakeEndpoint()
    fake.error = httpx.Response(
        400, json={"error": {"message": "No credentials for provider: openai"}}
    )

    result = probe_embedding(fake.endpoint, "text-embedding-3-small")

    assert result.passed is False
    assert result.note == "HTTP 400: No credentials for provider: openai"


def test_connection_error_is_reported_as_failure_without_crashing_probe() -> None:
    def offline(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("không tới được", request=request)

    endpoint = LLMEndpoint(httpx.Client(transport=httpx.MockTransport(offline)), BASE_URL, API_KEY)

    checks = probe_model(endpoint, MODEL).checks

    assert checks["basic_call"].passed is False
    assert checks["basic_call"].note == "Không kết nối được (ConnectError)"


def test_probe_models_keeps_order_and_never_calls_two_models_of_same_provider_at_once() -> None:
    lock = threading.Lock()
    in_flight: Counter[str] = Counter()
    peak: Counter[str] = Counter()
    fake = FakeEndpoint()

    def respond(request: httpx.Request) -> httpx.Response:
        provider = json.loads(request.content)["model"].split("/")[0]
        with lock:
            in_flight[provider] += 1
            peak[provider] = max(peak[provider], in_flight[provider])
        time.sleep(0.002)
        with lock:
            in_flight[provider] -= 1
        return fake._respond(request)

    endpoint = LLMEndpoint(httpx.Client(transport=httpx.MockTransport(respond)), BASE_URL, API_KEY)
    models = ["a/one", "b/one", "a/two", "b/two"]

    results = probe_models(endpoint, models)

    assert [result.model for result in results] == models
    assert all(result.checks["vietnamese"].passed for result in results)
    assert peak == {"a": 1, "b": 1}


@pytest.mark.parametrize("base_url", [BASE_URL, BASE_URL + "/"])
def test_lists_endpoint_models(base_url: str) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://llm.example/v1/models"
        return httpx.Response(200, json={"data": [{"id": "b/two"}, {"id": "a/one"}]})

    endpoint = LLMEndpoint(httpx.Client(transport=httpx.MockTransport(respond)), base_url, API_KEY)

    assert endpoint.models() == ["a/one", "b/two"]
