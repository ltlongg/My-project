"""Thông báo riêng qua bot Telegram, test bằng phản hồi mẫu theo tài liệu Bot API."""

import pytest

from siftly.notifications import TelegramNotifier
from siftly.publishers.telegram import TelegramPublishError
from tests.test_telegram_publisher import TOKEN, FakeTelegram

OWNER_ID = "987654321"


def test_alert_is_plain_text_sent_privately_to_owner() -> None:
    telegram = FakeTelegram()

    TelegramNotifier(telegram.client, TOKEN, OWNER_ID).notify(
        "Bản tin Công nghệ 08:00 ngày 07/10/2026 không được phát.\nLí do: <Không có> Bài gốc mới"
    )

    assert telegram.calls == [
        (
            "sendMessage",
            {
                "chat_id": OWNER_ID,
                "text": (
                    "Bản tin Công nghệ 08:00 ngày 07/10/2026 không được phát.\n"
                    "Lí do: <Không có> Bài gốc mới"
                ),
                "link_preview_options": {"is_disabled": True},
            },
        )
    ]


def test_owner_who_never_started_the_bot_raises_error_with_reason() -> None:
    telegram = FakeTelegram()
    telegram.returns("sendMessage", 400, "telegram_chat_not_found.json")

    with pytest.raises(TelegramPublishError) as error:
        TelegramNotifier(telegram.client, TOKEN, OWNER_ID).notify("Kỳ hỏng.")

    assert str(error.value) == "Telegram từ chối: Bad Request: chat not found"
