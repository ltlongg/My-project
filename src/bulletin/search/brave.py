"""Bộ tìm kiếm dùng Brave Search."""

import re
from collections.abc import Sequence
from html import unescape

import httpx

from bulletin.search import SO_KET_QUA, KetQuaTimKiem, LoiTimKiem

# Brave đánh dấu từ khớp trong trích đoạn bằng thẻ HTML.
THE_HTML = re.compile(r"<[^>]+>")


class TimKiemBrave:
    def __init__(self, client: httpx.Client, khoa: str) -> None:
        self._client = client
        self._khoa = khoa

    def tim(self, truy_van: str) -> Sequence[KetQuaTimKiem]:
        try:
            phan_hoi = self._client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": truy_van, "count": SO_KET_QUA},
                headers={"X-Subscription-Token": self._khoa, "Accept": "application/json"},
            )
        except httpx.HTTPError as loi:
            raise LoiTimKiem(f"Không kết nối được tới Brave ({type(loi).__name__})") from None
        try:
            du_lieu = phan_hoi.json()
        except ValueError:
            du_lieu = None
        if phan_hoi.is_error or not isinstance(du_lieu, dict):
            loi_tra_ve = du_lieu.get("error") if isinstance(du_lieu, dict) else None
            mo_ta = loi_tra_ve.get("detail") if isinstance(loi_tra_ve, dict) else None
            raise LoiTimKiem(f"Brave từ chối: {mo_ta or f'mã {phan_hoi.status_code}'}")
        return [
            KetQuaTimKiem(
                tieu_de=_bo_the(muc.get("title")),
                dia_chi=str(muc["url"]),
                trich_doan=_bo_the(muc.get("description")),
            )
            for muc in (du_lieu.get("web") or {}).get("results") or []
            if muc.get("url")
        ]


def _bo_the(van_ban: object) -> str:
    return unescape(THE_HTML.sub("", str(van_ban or "")))
