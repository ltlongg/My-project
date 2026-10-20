"""Bộ thu thập cho Nguồn loại RSS (đọc được cả RSS và Atom)."""

import re
from collections.abc import Sequence
from datetime import UTC, datetime
from html import unescape
from time import struct_time

import feedparser
import httpx

from bulletin.collectors import BaiGocMoi

# Mô tả dài hơn thì cắt; phần đầu là đủ để biết bài nói về chuyện gì.
MO_TA_TOI_DA = 500
THE_HTML = re.compile(r"<[^>]+>")


class LoiThuThapRss(Exception):
    pass


class ThuThapRss:
    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def thu_thap(self, dia_chi: str, tu_moc: datetime) -> Sequence[BaiGocMoi]:
        try:
            phan_hoi = self._client.get(dia_chi, follow_redirects=True)
        except httpx.HTTPError as loi:
            raise LoiThuThapRss(f"Không kết nối được tới {dia_chi}: {loi}") from loi
        if phan_hoi.is_error:
            raise LoiThuThapRss(f"{dia_chi} trả về mã {phan_hoi.status_code}")

        feed = feedparser.parse(
            phan_hoi.content,
            response_headers={"content-type": phan_hoi.headers.get("content-type", "")},
        )
        if not feed.version:
            raise LoiThuThapRss(f"{dia_chi} không phải là RSS hay Atom")

        bai_goc = []
        for muc in feed.entries:
            link, tieu_de = muc.get("link"), _chu_thuan(muc.get("title", ""))
            if not link or not tieu_de:
                continue
            xuat_ban_luc = _thoi_diem(muc.get("published_parsed") or muc.get("updated_parsed"))
            # Mục không ghi giờ xuất bản thì không biết cũ hay mới; để nơi gọi quyết định.
            if xuat_ban_luc is None or xuat_ban_luc > tu_moc:
                mo_ta = _chu_thuan(muc.get("summary", ""))[:MO_TA_TOI_DA].strip() or None
                bai_goc.append(
                    BaiGocMoi(dia_chi=link, tieu_de=tieu_de, xuat_ban_luc=xuat_ban_luc, mo_ta=mo_ta)
                )
        return bai_goc


def _chu_thuan(van_ban: str) -> str:
    """Bỏ thẻ HTML, giải mã thực thể HTML và gộp khoảng trắng.

    Có Nguồn để thực thể HTML trong CDATA, nên feedparser trả về nguyên "h&agrave;ng".
    """
    return " ".join(unescape(THE_HTML.sub(" ", van_ban)).split())


def _thoi_diem(gio_utc: struct_time | None) -> datetime | None:
    return datetime(*gio_utc[:6], tzinfo=UTC) if gio_utc else None
