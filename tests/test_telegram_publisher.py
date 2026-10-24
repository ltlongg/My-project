"""Bộ phát Telegram, test bằng phản hồi mẫu theo tài liệu Bot API; không gọi mạng."""

import json
import re
from email.message import Message
from email.parser import BytesParser
from email.policy import HTTP
from html import unescape
from pathlib import Path

import httpx
import pytest

from siftly.publishers import BulletinContent, StoryContent
from siftly.publishers.telegram import TelegramPublisher, TelegramPublishError
from tests.conftest import at

FIXTURES = Path(__file__).parent / "fixtures"
TOKEN = "123456:ABC-DEF"
CHAT_ID = "-1001234567890"
API = f"https://api.telegram.org/bot{TOKEN}"
PHOTO = b"\xff\xd8\xff\xe0 anh JPEG"


class FakeTelegram:
    """Đứng thay api.telegram.org: ghi lại mọi lời gọi và trả về phản hồi mẫu theo phương thức."""

    def __init__(self) -> None:
        # Phương thức, và các tham số đã gửi; tham số của sendPhoto gồm cả ảnh dạng bytes.
        self.calls: list[tuple[str, dict[str, object]]] = []
        self._responses = {
            "sendMessage": (200, "telegram_send_message_ok.json"),
            "sendPhoto": (200, "telegram_send_photo_ok.json"),
        }
        self.client = httpx.Client(transport=httpx.MockTransport(self._respond))

    def returns(self, method: str, status: int, response_file: str) -> None:
        self._responses[method] = (status, response_file)

    def _respond(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        assert url.startswith(f"{API}/")
        method = url.removeprefix(f"{API}/")
        self.calls.append((method, _params(request)))
        status, response_file = self._responses[method]
        return httpx.Response(
            status,
            content=(FIXTURES / response_file).read_bytes(),
            headers={"content-type": "application/json"},
        )


def _params(request: httpx.Request) -> dict[str, object]:
    if request.headers["content-type"] == "application/json":
        params: dict[str, object] = json.loads(request.content)
        return params
    head = f"Content-Type: {request.headers['content-type']}\r\n\r\n".encode()
    form = BytesParser(policy=HTTP).parsebytes(head + request.read())
    assert isinstance(form, Message)
    params = {}
    for part in form.iter_parts():
        name, payload = (
            part.get_param("name", header="content-disposition"),
            part.get_payload(decode=True),
        )
        assert isinstance(name, str) and isinstance(payload, bytes)
        params[name] = payload if part.get_filename() else payload.decode()
        if part.get_filename():
            params[f"{name}_content_type"] = part.get_content_type()
    return params


def bulletin(*stories: StoryContent) -> BulletinContent:
    return BulletinContent(section="Công nghệ", run_at=at(7, 8), stories=stories)


def test_bulletin_opens_with_section_and_date_then_each_story_is_its_own_photo_message() -> None:
    telegram = FakeTelegram()

    TelegramPublisher(telegram.client, TOKEN).publish(
        CHAT_ID,
        bulletin(
            StoryContent(
                'AT&T <mua> lại "X"',
                "Thương vụ trị giá <10 tỷ USD.",
                "https://bao.example/a?x=1&y=2",
                image=PHOTO,
            ),
            StoryContent("Bài B", "Tóm tắt của Bài B.", "https://bao.example/b", image=b"anh B"),
        ),
    )

    assert telegram.calls == [
        (
            "sendMessage",
            {
                "chat_id": CHAT_ID,
                "text": "<b>Bản tin Công nghệ</b> · 07/10/2026",
                "parse_mode": "HTML",
                "link_preview_options": {"is_disabled": True},
            },
        ),
        (
            "sendPhoto",
            {
                "chat_id": CHAT_ID,
                "caption": (
                    "<b>AT&amp;T &lt;mua&gt; lại &quot;X&quot;</b>\n"
                    "\n"
                    "Thương vụ trị giá &lt;10 tỷ USD.\n"
                    "\n"
                    '<a href="https://bao.example/a?x=1&amp;y=2">'
                    "https://bao.example/a?x=1&amp;y=2</a>"
                ),
                "parse_mode": "HTML",
                "photo": PHOTO,
                "photo_content_type": "image/jpeg",
            },
        ),
        (
            "sendPhoto",
            {
                "chat_id": CHAT_ID,
                "caption": (
                    "<b>Bài B</b>\n\nTóm tắt của Bài B.\n\n"
                    '<a href="https://bao.example/b">https://bao.example/b</a>'
                ),
                "parse_mode": "HTML",
                "photo": b"anh B",
                "photo_content_type": "image/jpeg",
            },
        ),
    ]


def test_story_without_image_is_a_text_message_with_the_same_content() -> None:
    telegram = FakeTelegram()

    TelegramPublisher(telegram.client, TOKEN).publish(
        CHAT_ID,
        bulletin(
            StoryContent("Bài A", "Tóm tắt A.", "https://bao.example/a", image=PHOTO),
            StoryContent("Bài B", "Tóm tắt B.", "https://bao.example/b"),
        ),
    )

    [_, (_, with_photo), (method, without_photo)] = telegram.calls
    assert method == "sendMessage"
    assert without_photo == {
        "chat_id": CHAT_ID,
        "text": (
            "<b>Bài B</b>\n\nTóm tắt B.\n\n"
            '<a href="https://bao.example/b">https://bao.example/b</a>'
        ),
        "parse_mode": "HTML",
        "link_preview_options": {"is_disabled": True},
    }
    assert str(with_photo["caption"]).startswith("<b>Bài A</b>\n\nTóm tắt A.")


def test_update_story_has_label_before_title() -> None:
    telegram = FakeTelegram()

    TelegramPublisher(telegram.client, TOKEN).publish(
        CHAT_ID,
        bulletin(
            StoryContent(
                "Apple chốt giao iPhone Duo từ tháng 1/2027",
                "Tóm tắt.",
                "https://bao.example/duo",
                is_update=True,
                image=PHOTO,
            )
        ),
    )

    [_, (_, params)] = telegram.calls
    assert str(params["caption"]).startswith("<b>Cập nhật: Apple chốt giao iPhone Duo")


def test_update_label_counts_toward_story_length() -> None:
    story = StoryContent("Tiêu đề", "Tóm tắt.", "https://bao.example/a")

    assert StoryContent(story.title, story.summary, story.url, is_update=True).length == (
        story.length + len("Cập nhật: ")
    )


def visible_text(html: str) -> str:
    """Chữ người đọc thấy, là thứ Telegram đếm vào giới hạn chú thích: bỏ thẻ, giải mã thực thể."""
    return unescape(re.sub(r"<[^>]+>", "", html))


def utf16_length(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


URL = "https://bao.example/sat-gioi-han"


def story_of_length(length: int) -> StoryContent:
    """Tin có ảnh dài đúng `length` đơn vị UTF-16 khi phát; tóm tắt có emoji, tính là hai."""
    title = "Tiêu đề sát giới hạn"
    fixed = utf16_length(f"{title}\n\n\n\n{URL}")
    summary = "😀" * ((length - fixed) // 2) + "a" * ((length - fixed) % 2)
    story = StoryContent(title, summary, URL, image=PHOTO)
    assert story.length == length
    return story


def caption_sent(story: StoryContent) -> str:
    telegram = FakeTelegram()
    TelegramPublisher(telegram.client, TOKEN).publish(CHAT_ID, bulletin(story))
    [_, (_, params)] = telegram.calls
    return str(params["caption"])


def test_caption_at_exactly_1024_characters_is_sent_whole() -> None:
    story = story_of_length(1024)

    caption = visible_text(caption_sent(story))

    assert caption == f"{story.title}\n\n{story.summary}\n\n{URL}"
    assert utf16_length(caption) == 1024


def test_caption_over_1024_characters_is_shortened_in_summary_and_keeps_link() -> None:
    story = story_of_length(1030)

    caption = visible_text(caption_sent(story))

    assert utf16_length(caption) <= 1024
    assert caption.startswith(f"{story.title}\n\n😀")
    assert caption.endswith(f"…\n\n{URL}")


@pytest.mark.parametrize(
    ("method", "status", "response_file", "expected_error"),
    [
        (
            "sendMessage",
            403,
            "telegram_bot_kicked.json",
            "Telegram từ chối: Forbidden: bot was kicked from the supergroup chat",
        ),
        (
            "sendMessage",
            400,
            "telegram_chat_not_found.json",
            "Telegram từ chối: Bad Request: chat not found",
        ),
        (
            "sendPhoto",
            429,
            "telegram_too_many_requests.json",
            "Telegram từ chối: Too Many Requests: retry after 35",
        ),
        (
            "sendPhoto",
            400,
            "telegram_photo_invalid_dimensions.json",
            "Telegram từ chối: Bad Request: PHOTO_INVALID_DIMENSIONS",
        ),
    ],
)
def test_telegram_rejection_raises_error_with_reason(
    method: str, status: int, response_file: str, expected_error: str
) -> None:
    telegram = FakeTelegram()
    telegram.returns(method, status, response_file)

    with pytest.raises(TelegramPublishError) as error:
        TelegramPublisher(telegram.client, TOKEN).publish(
            CHAT_ID,
            bulletin(StoryContent("Bài A", "Tóm tắt.", "https://bao.example/a", image=PHOTO)),
        )

    assert str(error.value) == expected_error


def test_connection_error_does_not_leak_bot_token() -> None:
    def offline(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"không tới được {request.url}", request=request)

    client = httpx.Client(transport=httpx.MockTransport(offline))

    with pytest.raises(TelegramPublishError) as error:
        TelegramPublisher(client, TOKEN).publish(
            CHAT_ID, bulletin(StoryContent("Bài A", "Tóm tắt.", "https://bao.example/a"))
        )

    assert str(error.value) == "Không kết nối được tới Telegram (ConnectError)"
    assert error.value.__cause__ is None


def test_publishing_again_skips_messages_already_sent_and_reports_each_one_sent() -> None:
    telegram = FakeTelegram()
    telegram.returns("sendPhoto", 429, "telegram_too_many_requests.json")
    sent: list[None] = []

    with pytest.raises(TelegramPublishError):
        TelegramPublisher(telegram.client, TOKEN).publish(
            CHAT_ID,
            bulletin(
                StoryContent("Bài A", "Tóm tắt A.", "https://bao.example/a"),
                StoryContent("Bài B", "Tóm tắt B.", "https://bao.example/b"),
                StoryContent("Bài C", "Tóm tắt C.", "https://bao.example/c", image=PHOTO),
            ),
            # Tin nhắn mở đầu và Tin A đã tới ở lần phát trước.
            skip=2,
            on_sent=lambda: sent.append(None),
        )

    assert [
        str(params.get("text", params.get("caption"))).split("\n")[0]
        for _, params in telegram.calls
    ] == ["<b>Bài B</b>", "<b>Bài C</b>"]
    # Chỉ Tin B tới nơi; Tin C bị từ chối.
    assert len(sent) == 1


def test_test_message_is_plain_text_sent_to_the_chat() -> None:
    telegram = FakeTelegram()

    TelegramPublisher(telegram.client, TOKEN).send_test(CHAT_ID, "Tin nhắn thử <không phải HTML>")

    assert telegram.calls == [
        ("sendMessage", {"chat_id": CHAT_ID, "text": "Tin nhắn thử <không phải HTML>"})
    ]


def test_test_message_to_a_chat_the_bot_left_raises_error_with_reason() -> None:
    telegram = FakeTelegram()
    telegram.returns("sendMessage", 403, "telegram_bot_kicked.json")

    with pytest.raises(TelegramPublishError) as error:
        TelegramPublisher(telegram.client, TOKEN).send_test(CHAT_ID, "Tin nhắn thử")

    assert (
        str(error.value) == "Telegram từ chối: Forbidden: bot was kicked from the supergroup chat"
    )
