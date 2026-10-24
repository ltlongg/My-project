"""Bộ nhúng gọi một endpoint `/embeddings` tương thích OpenAI, ví dụ Text Embeddings Inference
chạy `BAAI/bge-m3` (xem compose.yaml)."""

from collections.abc import Sequence

import httpx

from siftly.embeddings import EmbeddingError

# Text Embeddings Inference mặc định nhận tối đa ngần này văn bản mỗi lời gọi.
BATCH_SIZE = 32


class EndpointEmbedder:
    def __init__(
        self, client: httpx.Client, base_url: str, model: str, api_key: str | None = None
    ) -> None:
        self._client = client
        self._url = base_url.rstrip("/") + "/embeddings"
        self._api_key = api_key
        self.model = model

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH_SIZE):
            vectors += self._embed_batch(texts[start : start + BATCH_SIZE])
        return vectors

    def _embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        try:
            response = self._client.post(
                self._url,
                json={"model": self.model, "input": list(texts)},
                headers={"Authorization": f"Bearer {self._api_key}"} if self._api_key else None,
            )
        except httpx.HTTPError as error:
            raise EmbeddingError(
                f"Không kết nối được tới dịch vụ nhúng {self._url} ({type(error).__name__})"
            ) from None
        try:
            data = response.json()
        except ValueError:
            data = None
        if response.is_error or not isinstance(data, dict):
            raise EmbeddingError(
                f"Dịch vụ nhúng từ chối: {_error_message(data, response.status_code)}"
            )
        items = sorted(data.get("data") or [], key=lambda item: item.get("index", 0))
        if len(items) != len(texts) or not all(item.get("embedding") for item in items):
            raise EmbeddingError(f"Dịch vụ nhúng trả {len(items)} vector cho {len(texts)} văn bản")
        return [[float(x) for x in item["embedding"]] for item in items]


def _error_message(data: object, status_code: int) -> str:
    """Lời lỗi của dịch vụ: Text Embeddings Inference trả `{"message": "..."}`, OpenAI trả
    `{"error": {"message": "..."}}`."""
    if not isinstance(data, dict):
        return f"mã {status_code}"
    error = data.get("error")
    error = error.get("message") if isinstance(error, dict) else error or data.get("message")
    return str(error) if error else f"mã {status_code}"
