"""Bộ tìm kiếm dùng Tavily."""

from collections.abc import Sequence

import httpx

from bulletin.search import SO_KET_QUA, KetQuaTimKiem, LoiTimKiem


class TimKiemTavily:
    def __init__(self, client: httpx.Client, khoa: str) -> None:
        self._client = client
        self._khoa = khoa

    def tim(self, truy_van: str) -> Sequence[KetQuaTimKiem]:
        try:
            phan_hoi = self._client.post(
                "https://api.tavily.com/search",
                json={"query": truy_van, "max_results": SO_KET_QUA},
                headers={"Authorization": f"Bearer {self._khoa}"},
            )
        except httpx.HTTPError as loi:
            raise LoiTimKiem(f"Không kết nối được tới Tavily ({type(loi).__name__})") from None
        try:
            du_lieu = phan_hoi.json()
        except ValueError:
            du_lieu = None
        if phan_hoi.is_error or not isinstance(du_lieu, dict):
            chi_tiet = du_lieu.get("detail") if isinstance(du_lieu, dict) else None
            mo_ta = chi_tiet.get("error") if isinstance(chi_tiet, dict) else chi_tiet
            raise LoiTimKiem(f"Tavily từ chối: {mo_ta or f'mã {phan_hoi.status_code}'}")
        return [
            KetQuaTimKiem(
                tieu_de=str(muc.get("title") or ""),
                dia_chi=str(muc["url"]),
                trich_doan=str(muc.get("content") or ""),
            )
            for muc in du_lieu.get("results") or []
            if muc.get("url")
        ]
