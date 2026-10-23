"""Bộ lấy nội dung cho Bài gốc loại bài báo: tải trang rồi trích phần thân bài."""

import httpx
import trafilatura

# Ngắn hơn mức này thì gần như chắc là trang chặn, tường phí hoặc trang không có bài.
MIN_FULL_TEXT = 200


class ExtractError(Exception):
    pass


class ArticleExtractor:
    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def extract(self, url: str) -> str:
        try:
            response = self._client.get(url, follow_redirects=True)
        except httpx.HTTPError as error:
            raise ExtractError(f"Không kết nối được tới {url}: {error}") from error
        if response.is_error:
            raise ExtractError(f"{url} trả về mã {response.status_code}")

        full_text = trafilatura.extract(response.text, url=url, include_comments=False) or ""
        # Postgres không lưu được ký tự NUL.
        full_text = full_text.replace("\x00", "").strip()
        if len(full_text) < MIN_FULL_TEXT:
            raise ExtractError(f"Không trích được thân bài từ {url}")
        return full_text
