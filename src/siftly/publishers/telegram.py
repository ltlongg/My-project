"""Bộ phát cho Kênh đăng loại Telegram. Địa chỉ của Kênh đăng là mã cuộc trò chuyện.

Một Bản tin là một tin nhắn mở đầu nêu tên Chuyên mục và ngày, rồi mỗi Tin một tin nhắn riêng để
người đọc chuyển tiếp được từng Tin: tin nhắn ảnh có chú thích khi Tin có ảnh, tin nhắn chữ cùng
nội dung khi không.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from html import escape
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from siftly.publishers import BulletinContent, StoryContent, text_length

VIETNAM_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
# Giới hạn của Telegram cho chú thích ảnh, đếm sau khi bỏ thẻ HTML. Tin không ảnh cũng giữ giới
# hạn này, để Tin trông như nhau dù có ảnh hay không.
CAPTION_LIMIT = 1024
ELLIPSIS = "…"


class TelegramPublishError(Exception):
    pass


@dataclass(frozen=True)
class Message:
    """Một tin nhắn sẽ gửi: chữ HTML, kèm ảnh JPEG nếu là tin nhắn ảnh."""

    text: str
    photo: bytes | None = field(default=None, repr=False)


class TelegramPublisher:
    """Mỗi tin nhắn là một phần của Bản tin."""

    def __init__(self, client: httpx.Client, token: str) -> None:
        self._client = client
        self._token = token

    def publish(
        self,
        address: str,
        bulletin: BulletinContent,
        *,
        skip: int = 0,
        on_sent: Callable[[], None] = lambda: None,
    ) -> None:
        for message in build_messages(bulletin)[skip:]:
            if message.photo is None:
                call_bot(
                    self._client,
                    self._token,
                    "sendMessage",
                    json={
                        "chat_id": address,
                        "text": message.text,
                        "parse_mode": "HTML",
                        "link_preview_options": {"is_disabled": True},
                    },
                )
            else:
                call_bot(
                    self._client,
                    self._token,
                    "sendPhoto",
                    data={"chat_id": address, "caption": message.text, "parse_mode": "HTML"},
                    files={"photo": ("tin.jpg", message.photo, "image/jpeg")},
                )
            on_sent()


def call_bot(client: httpx.Client, token: str, method: str, **request: Any) -> None:
    """Gọi một phương thức của Bot API; ném TelegramPublishError khi Telegram không làm được."""
    try:
        response = client.post(f"https://api.telegram.org/bot{token}/{method}", **request)
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


def build_messages(bulletin: BulletinContent) -> list[Message]:
    """Dựng Bản tin thành các tin nhắn HTML theo thứ tự gửi."""
    date = bulletin.run_at.astimezone(VIETNAM_TZ).strftime("%d/%m/%Y")
    opening = Message(f"<b>Bản tin {escape(bulletin.section)}</b> · {date}")
    return [opening, *(Message(_story_text(story), story.image) for story in bulletin.stories)]


def _story_text(story: StoryContent) -> str:
    """Tiêu đề, tóm tắt và link, trong giới hạn chú thích.

    Biên tập đã viết trong giới hạn; nếu vẫn vượt thì cắt tóm tắt, rồi tới tiêu đề, không bao giờ
    cắt link.
    """
    title, summary, url = story.labeled_title, story.summary, story.url
    excess = story.length - CAPTION_LIMIT
    if excess > 0:
        shortened = _shorten(summary, text_length(summary) - excess)
        excess -= text_length(summary) - text_length(shortened)
        summary = shortened
    if excess > 0:
        title = _shorten(title, text_length(title) - excess)
    return (
        f'<b>{escape(title)}</b>\n\n{escape(summary)}\n\n<a href="{escape(url)}">{escape(url)}</a>'
    )


def _shorten(text: str, limit: int) -> str:
    """Phần đầu của `text` kèm dấu "…", dài không quá `limit` đơn vị UTF-16."""
    if limit < text_length(ELLIPSIS):
        return ""
    kept, length = [], text_length(ELLIPSIS)
    for character in text:
        length += text_length(character)
        if length > limit:
            break
        kept.append(character)
    return "".join(kept).rstrip() + ELLIPSIS
