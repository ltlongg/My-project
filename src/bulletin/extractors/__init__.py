"""Lấy nội dung: biến một Bài gốc thành văn bản đầy đủ."""

from typing import Protocol


class BoLayNoiDung(Protocol):
    def lay(self, dia_chi: str) -> str:
        """Trả về toàn văn của Bài gốc ở `dia_chi`.

        Ném lỗi khi không lấy được; nơi gọi chịu trách nhiệm ghi lại và đi tiếp.
        """
        ...
