"""Thông báo riêng: bot nhắn cho chủ hệ thống những việc họ cần biết mà không phải vào trang quản
lí, như một Kỳ hỏng hẳn hoặc không phát."""

from typing import Protocol

import httpx

from siftly.publishers.telegram import call_bot


class Notifier(Protocol):
    def notify(self, text: str) -> None:
        """Nhắn `text` cho chủ hệ thống. Ném lỗi khi không nhắn được."""
        ...


class TelegramNotifier:
    """Nhắn chữ thuần vào cuộc trò chuyện riêng giữa bot và chủ hệ thống, theo mã người dùng
    Telegram của họ. Bot chỉ nhắn được cho người đã bấm Start với nó."""

    def __init__(self, client: httpx.Client, token: str, owner_id: str) -> None:
        self._client = client
        self._token = token
        self._owner_id = owner_id

    def notify(self, text: str) -> None:
        call_bot(
            self._client,
            self._token,
            "sendMessage",
            json={
                "chat_id": self._owner_id,
                "text": text,
                "link_preview_options": {"is_disabled": True},
            },
        )
