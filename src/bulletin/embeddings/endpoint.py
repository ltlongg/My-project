"""Bộ nhúng gọi một endpoint `/embeddings` tương thích OpenAI, ví dụ Text Embeddings Inference
chạy `BAAI/bge-m3` (xem compose.yaml)."""

from collections.abc import Sequence

import httpx

from bulletin.embeddings import LoiNhung

# Text Embeddings Inference mặc định nhận tối đa ngần này văn bản mỗi lời gọi.
SO_VAN_BAN_MOI_LAN = 32


class NhungQuaEndpoint:
    def __init__(
        self, client: httpx.Client, dia_chi: str, mo_hinh: str, khoa: str | None = None
    ) -> None:
        self._client = client
        self._dia_chi = dia_chi.rstrip("/") + "/embeddings"
        self._khoa = khoa
        self.mo_hinh = mo_hinh

    def nhung(self, van_ban: Sequence[str]) -> list[list[float]]:
        vector: list[list[float]] = []
        for dau in range(0, len(van_ban), SO_VAN_BAN_MOI_LAN):
            vector += self._nhung_mot_lan(van_ban[dau : dau + SO_VAN_BAN_MOI_LAN])
        return vector

    def _nhung_mot_lan(self, van_ban: Sequence[str]) -> list[list[float]]:
        try:
            phan_hoi = self._client.post(
                self._dia_chi,
                json={"model": self.mo_hinh, "input": list(van_ban)},
                headers={"Authorization": f"Bearer {self._khoa}"} if self._khoa else None,
            )
        except httpx.HTTPError as loi:
            raise LoiNhung(
                f"Không kết nối được tới dịch vụ nhúng {self._dia_chi} ({type(loi).__name__})"
            ) from None
        try:
            du_lieu = phan_hoi.json()
        except ValueError:
            du_lieu = None
        if phan_hoi.is_error or not isinstance(du_lieu, dict):
            raise LoiNhung(f"Dịch vụ nhúng từ chối: {_mo_ta_loi(du_lieu, phan_hoi.status_code)}")
        muc = sorted(du_lieu.get("data") or [], key=lambda m: m.get("index", 0))
        if len(muc) != len(van_ban) or not all(m.get("embedding") for m in muc):
            raise LoiNhung(f"Dịch vụ nhúng trả {len(muc)} vector cho {len(van_ban)} văn bản")
        return [[float(so) for so in m["embedding"]] for m in muc]


def _mo_ta_loi(du_lieu: object, ma: int) -> str:
    """Lời lỗi của dịch vụ: Text Embeddings Inference trả `{"message": "..."}`, OpenAI trả
    `{"error": {"message": "..."}}`."""
    if not isinstance(du_lieu, dict):
        return f"mã {ma}"
    loi = du_lieu.get("error")
    loi = loi.get("message") if isinstance(loi, dict) else loi or du_lieu.get("message")
    return str(loi) if loi else f"mã {ma}"
