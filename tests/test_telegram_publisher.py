"""Bộ phát Telegram, test bằng phản hồi mẫu theo tài liệu Bot API; không gọi mạng."""

import json
from pathlib import Path

import httpx
import pytest

from siftly.publishers import BulletinContent, StoryContent
from siftly.publishers.telegram import TelegramPublisher, TelegramPublishError
from tests.conftest import at

FIXTURES = Path(__file__).parent / "fixtures"
TOKEN = "123456:ABC-DEF"
CHAT_ID = "-1001234567890"


class FakeTelegram:
    """Đứng thay api.telegram.org: ghi lại mọi lời gọi và trả về phản hồi mẫu."""

    def __init__(self, response_file: str = "telegram_send_message_ok.json") -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self._status, self._content = 200, (FIXTURES / response_file).read_bytes()
        self.client = httpx.Client(transport=httpx.MockTransport(self._respond))

    def returns(self, status: int, response_file: str) -> None:
        self._status, self._content = status, (FIXTURES / response_file).read_bytes()

    def _respond(self, request: httpx.Request) -> httpx.Response:
        self.calls.append((str(request.url), json.loads(request.content)))
        return httpx.Response(
            self._status, content=self._content, headers={"content-type": "application/json"}
        )


def test_sends_bulletin_as_one_message_with_section_name_date_and_each_story_with_link() -> None:
    telegram = FakeTelegram()
    bulletin = BulletinContent(
        section="Công nghệ",
        run_at=at(7, 8),
        stories=(
            StoryContent(
                'AT&T <mua> lại "X"',
                "Thương vụ trị giá <10 tỷ USD.",
                "https://bao.example/a?x=1&y=2",
            ),
            StoryContent("Bài B", "Tóm tắt của Bài B.", "https://bao.example/b"),
        ),
    )

    TelegramPublisher(telegram.client, TOKEN).publish(CHAT_ID, bulletin)

    assert telegram.calls == [
        (
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            {
                "chat_id": CHAT_ID,
                "text": (
                    "<b>Bản tin Công nghệ</b> · 07/10/2026\n"
                    "\n"
                    '1. <a href="https://bao.example/a?x=1&amp;y=2">'
                    "<b>AT&amp;T &lt;mua&gt; lại &quot;X&quot;</b></a>\n"
                    "Thương vụ trị giá &lt;10 tỷ USD.\n"
                    "\n"
                    '2. <a href="https://bao.example/b"><b>Bài B</b></a>\n'
                    "Tóm tắt của Bài B."
                ),
                "parse_mode": "HTML",
                "link_preview_options": {"is_disabled": True},
            },
        )
    ]


def test_update_story_has_label_before_title() -> None:
    telegram = FakeTelegram()
    bulletin = BulletinContent(
        section="Công nghệ",
        run_at=at(8, 8),
        stories=(
            StoryContent(
                "Apple chốt giao iPhone Duo từ tháng 1/2027",
                "Tóm tắt.",
                "https://bao.example/duo",
                is_update=True,
            ),
        ),
    )

    TelegramPublisher(telegram.client, TOKEN).publish(CHAT_ID, bulletin)

    [(_, params)] = telegram.calls
    assert '1. <a href="https://bao.example/duo"><b>Cập nhật: Apple chốt giao iPhone Duo' in str(
        params["text"]
    )


def test_update_label_counts_toward_story_length() -> None:
    story = StoryContent("Tiêu đề", "Tóm tắt.", "https://bao.example/a")

    assert StoryContent(story.title, story.summary, story.url, is_update=True).length == (
        story.length + len("Cập nhật: ")
    )


def test_long_bulletin_is_split_into_messages_within_4096_character_limit() -> None:
    telegram = FakeTelegram()
    bulletin = BulletinContent(
        section="Công nghệ",
        run_at=at(7, 8),
        # Hai Tin liền nhau vừa 4096 nếu đếm theo ký tự, nhưng vượt nếu đếm theo UTF-16.
        stories=tuple(
            StoryContent(f"{n}" + "😀" * 299, "Tóm tắt.", f"https://bao.example/{n}/" + "a" * 1680)
            for n in range(1, 8)
        ),
    )

    TelegramPublisher(telegram.client, TOKEN).publish(CHAT_ID, bulletin)

    texts = [str(body["text"]) for _, body in telegram.calls]
    assert len(texts) > 1
    # Telegram đếm theo đơn vị UTF-16, nên một emoji tính là hai.
    assert all(len(text.encode("utf-16-le")) // 2 <= 4096 for text in texts)
    assert texts[0].startswith("<b>Bản tin Công nghệ</b>")
    whole_bulletin = "\n".join(texts)
    positions = [whole_bulletin.index(f"https://bao.example/{n}/") for n in range(1, 8)]
    assert positions == sorted(positions)


@pytest.mark.parametrize(
    ("status", "response_file", "expected_error"),
    [
        (
            403,
            "telegram_bot_kicked.json",
            "Telegram từ chối: Forbidden: bot was kicked from the supergroup chat",
        ),
        (400, "telegram_chat_not_found.json", "Telegram từ chối: Bad Request: chat not found"),
        (
            429,
            "telegram_too_many_requests.json",
            "Telegram từ chối: Too Many Requests: retry after 35",
        ),
    ],
)
def test_telegram_rejection_raises_error_with_reason(
    status: int, response_file: str, expected_error: str
) -> None:
    telegram = FakeTelegram()
    telegram.returns(status, response_file)
    bulletin = BulletinContent(
        "Công nghệ", at(7, 8), (StoryContent("Bài A", "Tóm tắt.", "https://bao.example/a"),)
    )

    with pytest.raises(TelegramPublishError) as error:
        TelegramPublisher(telegram.client, TOKEN).publish(CHAT_ID, bulletin)

    assert str(error.value) == expected_error


def test_connection_error_does_not_leak_bot_token() -> None:
    def offline(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"không tới được {request.url}", request=request)

    client = httpx.Client(transport=httpx.MockTransport(offline))
    bulletin = BulletinContent(
        "Công nghệ", at(7, 8), (StoryContent("Bài A", "Tóm tắt.", "https://bao.example/a"),)
    )

    with pytest.raises(TelegramPublishError) as error:
        TelegramPublisher(client, TOKEN).publish(CHAT_ID, bulletin)

    assert str(error.value) == "Không kết nối được tới Telegram (ConnectError)"
    assert error.value.__cause__ is None
