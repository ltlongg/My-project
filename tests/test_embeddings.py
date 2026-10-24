"""Bộ nhúng qua endpoint tương thích OpenAI, test bằng phản hồi đã ghi lại từ Text Embeddings
Inference chạy BAAI/bge-m3; không gọi mạng."""

import json
from pathlib import Path

import httpx
import pytest

from siftly.embeddings import EmbeddingError
from siftly.embeddings.endpoint import BATCH_SIZE, EndpointEmbedder

FIXTURES = Path(__file__).parent / "fixtures"
BASE_URL = "http://127.0.0.1:54321/v1"
MODEL = "BAAI/bge-m3"
# Hai văn bản của phản hồi mẫu: một sự kiện, hai ngôn ngữ.
TEXTS = [
    "Amazon tài trợ nhà máy điện hạt nhân ở Indiana",
    "Amazon is funding a new nuclear plant in Indiana",
]


class FakeService:
    """Đứng thay dịch vụ nhúng: ghi lại lời gọi và trả về phản hồi mẫu."""

    def __init__(self, status: int, response_file: str) -> None:
        self.requests: list[httpx.Request] = []
        self._status, self._content = status, (FIXTURES / response_file).read_bytes()
        self.client = httpx.Client(transport=httpx.MockTransport(self._respond))

    def _respond(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(
            self._status, content=self._content, headers={"content-type": "application/json"}
        )


def test_one_vector_per_text_in_order() -> None:
    service = FakeService(200, "tei_embeddings_ok.json")

    vectors = EndpointEmbedder(service.client, BASE_URL, MODEL).embed(TEXTS)

    [request] = service.requests
    assert str(request.url) == f"{BASE_URL}/embeddings"
    assert json.loads(request.content) == {"model": MODEL, "input": TEXTS}
    assert "authorization" not in request.headers
    assert [len(v) for v in vectors] == [1024, 1024]
    # bge-m3 trả vector đã chuẩn hoá; hai câu cùng nghĩa khác ngôn ngữ thì rất giống nhau.
    similarity = sum(a * b for a, b in zip(*vectors, strict=True))
    assert similarity > 0.85


def test_api_key_is_sent_when_given() -> None:
    service = FakeService(200, "tei_embeddings_ok.json")

    EndpointEmbedder(service.client, BASE_URL + "/", MODEL, "secret-key").embed(TEXTS)

    [request] = service.requests
    assert str(request.url) == f"{BASE_URL}/embeddings"
    assert request.headers["authorization"] == "Bearer secret-key"


def test_many_texts_are_split_into_several_calls() -> None:
    data = json.loads((FIXTURES / "tei_embeddings_ok.json").read_bytes())
    batch_sizes: list[int] = []

    def respond(request: httpx.Request) -> httpx.Response:
        inputs = json.loads(request.content)["input"]
        batch_sizes.append(len(inputs))
        vector = data["data"][0]["embedding"]
        return httpx.Response(
            200,
            json={"data": [{"index": i, "embedding": vector} for i in range(len(inputs))]},
        )

    client = httpx.Client(transport=httpx.MockTransport(respond))
    vectors = EndpointEmbedder(client, BASE_URL, MODEL).embed(["một câu"] * 70)

    assert len(vectors) == 70
    assert batch_sizes == [BATCH_SIZE, BATCH_SIZE, 70 - 2 * BATCH_SIZE]


def test_service_rejection_raises_error_with_service_message() -> None:
    service = FakeService(400, "tei_embeddings_error.json")

    with pytest.raises(EmbeddingError, match="`inputs` cannot be empty"):
        EndpointEmbedder(service.client, BASE_URL, MODEL).embed(TEXTS)


def test_vector_count_not_matching_text_count_raises_error() -> None:
    service = FakeService(200, "tei_embeddings_ok.json")

    with pytest.raises(EmbeddingError, match="2 vector cho 3 văn bản"):
        EndpointEmbedder(service.client, BASE_URL, MODEL).embed([*TEXTS, "câu thứ ba"])


def test_connection_error_raises_without_leaking_api_key() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"không tới được {request.headers.get('authorization')}")

    client = httpx.Client(transport=httpx.MockTransport(refuse))

    with pytest.raises(EmbeddingError, match="Không kết nối được tới dịch vụ nhúng") as error:
        EndpointEmbedder(client, BASE_URL, MODEL, "secret-key").embed(TEXTS)
    assert "secret-key" not in str(error.value)
