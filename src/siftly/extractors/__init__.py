"""Lấy nội dung: biến một Bài gốc thành văn bản đầy đủ."""

from typing import Protocol


class Extractor(Protocol):
    def extract(self, url: str) -> str:
        """Trả về toàn văn của Bài gốc ở `url`.

        Ném lỗi khi không lấy được; nơi gọi chịu trách nhiệm ghi lại và đi tiếp.
        """
        ...
