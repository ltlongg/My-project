"""Bộ phát cho Kênh đăng loại Telegram. Địa chỉ của Kênh đăng là mã cuộc trò chuyện."""

from html import escape
from zoneinfo import ZoneInfo

import httpx

from bulletin.publishers import BulletinContent, text_length

VIETNAM_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
# Giới hạn của Telegram cho một tin nhắn chữ.
MESSAGE_LIMIT = 4096
MAX_TITLE_LENGTH = 300


class TelegramPublishError(Exception):
    pass


class TelegramPublisher:
    def __init__(self, client: httpx.Client, token: str) -> None:
        self._client = client
        self._token = token

    def publish(self, address: str, bulletin: BulletinContent) -> None:
        for text in build_messages(bulletin):
            self._send(address, text)

    def _send(self, chat_id: str, text: str) -> None:
        try:
            response = self._client.post(
                f"https://api.telegram.org/bot{self._token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "link_preview_options": {"is_disabled": True},
                },
            )
        except httpx.HTTPError as error:
            # Không nối lỗi gốc vào: nó mang theo địa chỉ có chứa token của bot.
            raise TelegramPublishError(
                f"Không kết nối được tới Telegram ({type(error).__name__})"
            ) from None

        try:
            result = response.json()
        except ValueError:
            result = None
        if not isinstance(result, dict) or not result.get("ok"):
            description = isinstance(result, dict) and result.get("description")
            raise TelegramPublishError(
                f"Telegram từ chối: {description or f'mã {response.status_code}'}"
            )


def build_messages(bulletin: BulletinContent) -> list[str]:
    """Dựng Bản tin thành các tin nhắn HTML, mỗi tin nhắn trong giới hạn của Telegram."""
    date = bulletin.run_at.astimezone(VIETNAM_TZ).strftime("%d/%m/%Y")
    blocks = [f"<b>Bản tin {escape(bulletin.section)}</b> · {date}"]
    for position, story in enumerate(bulletin.stories, start=1):
        title = story.labeled_title
        if len(title) > MAX_TITLE_LENGTH:
            title = title[: MAX_TITLE_LENGTH - 1] + "…"
        blocks.append(
            f'{position}. <a href="{escape(story.url)}"><b>{escape(title)}</b></a>\n'
            f"{escape(story.summary)}"
        )

    messages: list[str] = []
    for block in blocks:
        if messages and text_length(messages[-1]) + 2 + text_length(block) <= MESSAGE_LIMIT:
            messages[-1] += "\n\n" + block
        else:
            messages.append(block)
    return messages
