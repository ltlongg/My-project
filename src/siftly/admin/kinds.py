"""Các loại Nguồn và Kênh đăng như trang quản lí hỏi: tên loại, cách điền địa chỉ, dạng hợp lệ.

Thêm một loại là thêm một mục ở đây, cùng bộ thu thập hay bộ phát của nó; màn hình thêm Nguồn và
Kênh đăng tự hiện loại mới.
"""

import re
from dataclasses import dataclass

from pydantic import BaseModel

from siftly.models import ChannelKind, SourceKind


@dataclass(frozen=True)
class Kind:
    label: str
    # Nhãn, chữ mẫu và gợi ý của ô địa chỉ.
    address_label: str
    placeholder: str
    hint: str
    # Địa chỉ hợp lệ khớp trọn mẫu này; không khớp thì báo `invalid`.
    pattern: re.Pattern[str]
    invalid: str

    def check(self, address: str) -> str | None:
        """Lời nhắn khi `address` không đúng dạng; đúng thì None."""
        return None if self.pattern.fullmatch(address) else self.invalid


class KindOut(BaseModel):
    kind: str
    label: str
    address_label: str
    placeholder: str
    hint: str


SOURCE_KINDS: dict[SourceKind, Kind] = {
    SourceKind.RSS: Kind(
        label="RSS",
        address_label="Địa chỉ RSS",
        placeholder="https://vnexpress.net/rss/tin-moi-nhat.rss",
        hint="Địa chỉ của feed RSS hoặc Atom, không phải trang chủ của báo.",
        pattern=re.compile(r"https?://[^\s/]+\S*"),
        invalid="Địa chỉ bắt đầu bằng http:// hoặc https://",
    ),
}

CHANNEL_KINDS: dict[ChannelKind, Kind] = {
    ChannelKind.TELEGRAM: Kind(
        label="Telegram",
        address_label="Mã cuộc trò chuyện",
        placeholder="-1001234567890",
        hint=(
            "Mã của nhóm hay kênh Telegram, như -1001234567890, hoặc @ten_kenh với kênh công khai. "
            "Thêm bot vào đó trước, với quyền gửi tin."
        ),
        pattern=re.compile(r"-?\d+|@\w{4,}"),
        invalid="Mã là một số, như -1001234567890, hoặc @ten_kenh",
    ),
}


def kinds_out(kinds: dict[SourceKind, Kind] | dict[ChannelKind, Kind]) -> list[KindOut]:
    return [
        KindOut(
            kind=kind,
            label=info.label,
            address_label=info.address_label,
            placeholder=info.placeholder,
            hint=info.hint,
        )
        for kind, info in kinds.items()
    ]
