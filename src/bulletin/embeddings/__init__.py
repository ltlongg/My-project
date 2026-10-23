"""Vector nhúng: biến văn bản thành vector để so độ giống nghĩa khi gom Tin."""

from collections.abc import Sequence
from typing import Protocol


class Embedder(Protocol):
    # Tên model nhúng. Vector của hai model khác nhau không so được với nhau.
    model: str

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Trả về một vector cho mỗi văn bản, theo đúng thứ tự. Ném lỗi khi không nhúng được."""
        ...


class EmbeddingError(Exception):
    """Dịch vụ nhúng từ chối hoặc không tới được; thông điệp không chứa khoá."""
