"""Bộ lấy nội dung cho Bài gốc loại bài báo: tải trang rồi trích phần thân bài."""

import httpx
import trafilatura

# Ngắn hơn mức này thì gần như chắc là trang chặn, tường phí hoặc trang không có bài.
TOAN_VAN_TOI_THIEU = 200


class LoiLayNoiDung(Exception):
    pass


class LayBaiBao:
    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def lay(self, dia_chi: str) -> str:
        try:
            phan_hoi = self._client.get(dia_chi, follow_redirects=True)
        except httpx.HTTPError as loi:
            raise LoiLayNoiDung(f"Không kết nối được tới {dia_chi}: {loi}") from loi
        if phan_hoi.is_error:
            raise LoiLayNoiDung(f"{dia_chi} trả về mã {phan_hoi.status_code}")

        toan_van = trafilatura.extract(phan_hoi.text, url=dia_chi, include_comments=False) or ""
        # Postgres không lưu được ký tự NUL.
        toan_van = toan_van.replace("\x00", "").strip()
        if len(toan_van) < TOAN_VAN_TOI_THIEU:
            raise LoiLayNoiDung(f"Không trích được thân bài từ {dia_chi}")
        return toan_van
