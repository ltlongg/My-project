"""Bộ thử endpoint LLM: từng model làm được gì, trước khi vòng agent dựa vào nó.

Gọi endpoint thật qua `bulletin thu-llm`; mỗi model tốn khoảng mười lời gọi ngắn.
"""

import json
import time
from collections import Counter
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from bulletin.tieng_viet import la_tieng_viet

# Tên và nhãn các phép thử trên từng model, theo thứ tự chạy và thứ tự cột trong báo cáo.
PHEP_THU = {
    "goi_thuong": "Gọi thường",
    "khong_stream": "Không stream",
    "cong_cu_mot_luot": "Công cụ một lượt",
    "cong_cu_nhieu_luot": "Công cụ nhiều lượt",
    "json_schema": "JSON theo schema",
    "json_theo_prompt": "JSON theo prompt",
    "tieng_viet": "Viết tiếng Việt",
}
SO_LUOT_TOI_DA = 6

Json = dict[str, Any]


class LoiEndpoint(Exception):
    """Endpoint từ chối hoặc không tới được; thông điệp không chứa khoá."""

    def __init__(self, thong_diep: str, cho_giay: float | None = None) -> None:
        super().__init__(thong_diep)
        # Endpoint bảo chờ ngần này giây (đầu `retry-after`) rồi mới gọi lại model được.
        self.cho_giay = cho_giay


@dataclass(frozen=True)
class GoiCongCu:
    id: str
    ten: str
    tham_so: str


@dataclass(frozen=True)
class TraLoi:
    noi_dung: str
    goi_cong_cu: tuple[GoiCongCu, ...] = ()
    # Một số model suy luận đòi nhận lại phần suy luận ở lượt sau.
    suy_luan: str = ""

    def thanh_tin_nhan(self) -> Json:
        tin: Json = {"role": "assistant", "content": self.noi_dung}
        if self.suy_luan:
            tin["reasoning_content"] = self.suy_luan
        if self.goi_cong_cu:
            tin["tool_calls"] = [
                {
                    "id": g.id,
                    "type": "function",
                    "function": {"name": g.ten, "arguments": g.tham_so},
                }
                for g in self.goi_cong_cu
            ]
        return tin


class EndpointLLM:
    """Endpoint tương thích OpenAI, đủ cho bộ thử: liệt kê model, trò chuyện, tạo vector nhúng."""

    def __init__(self, client: httpx.Client, dia_chi: str, khoa: str) -> None:
        self._client = client
        self._dia_chi = dia_chi.rstrip("/")
        self._dau = {"Authorization": f"Bearer {khoa}"}

    def cac_model(self) -> list[str]:
        phan_hoi = self._gui("GET", "/models")
        return sorted(str(model["id"]) for model in _json(phan_hoi)["data"])

    def tro_chuyen(self, model: str, tin_nhan: Sequence[Json], **tuy_chon: object) -> TraLoi:
        """Gọi dạng stream, là dạng mọi model của endpoint đều trả đúng chuẩn."""
        than = {"model": model, "messages": list(tin_nhan), "stream": True, **tuy_chon}
        noi_dung, suy_luan = "", ""
        goi: dict[int, dict[str, str]] = {}
        try:
            with self._client.stream(
                "POST", self._dia_chi + "/chat/completions", json=than, headers=self._dau
            ) as phan_hoi:
                if phan_hoi.is_error:
                    phan_hoi.read()
                    raise _loi_tu_choi(phan_hoi)
                for dong in phan_hoi.iter_lines():
                    if not dong.startswith("data:") or dong[5:].strip() == "[DONE]":
                        continue
                    manh = json.loads(dong[5:])
                    if manh.get("error"):
                        raise LoiEndpoint(f"Lỗi giữa stream: {_thong_diep(manh)}")
                    for lua_chon in manh.get("choices") or []:
                        delta = lua_chon.get("delta") or {}
                        noi_dung += delta.get("content") or ""
                        suy_luan += delta.get("reasoning_content") or ""
                        for manh_goi in delta.get("tool_calls") or []:
                            ham = manh_goi.get("function") or {}
                            dang_gom = goi.setdefault(
                                manh_goi.get("index", 0), {"id": "", "ten": "", "tham_so": ""}
                            )
                            dang_gom["id"] += manh_goi.get("id") or ""
                            dang_gom["ten"] += ham.get("name") or ""
                            dang_gom["tham_so"] += ham.get("arguments") or ""
        except httpx.HTTPError as loi:
            raise LoiEndpoint(f"Không kết nối được ({type(loi).__name__})") from None
        except ValueError:
            raise LoiEndpoint("Stream có dòng không phải JSON") from None
        return TraLoi(noi_dung, tuple(GoiCongCu(**goi[vi_tri]) for vi_tri in sorted(goi)), suy_luan)

    def tro_chuyen_khong_stream(self, model: str, tin_nhan: Sequence[Json]) -> str:
        """Gọi không stream và đọc thân phản hồi như một client chuẩn: cả thân phải là JSON."""
        than = {"model": model, "messages": list(tin_nhan)}
        thong_diep = _json(self._gui("POST", "/chat/completions", than))["choices"][0]["message"]
        return str(thong_diep.get("content") or "")

    def nhung(self, model: str, van_ban: str) -> list[float]:
        than = {"model": model, "input": [van_ban]}
        vector: list[float] = _json(self._gui("POST", "/embeddings", than))["data"][0]["embedding"]
        return vector

    def _gui(self, phuong_thuc: str, duong: str, than: Json | None = None) -> httpx.Response:
        try:
            phan_hoi = self._client.request(
                phuong_thuc, self._dia_chi + duong, json=than, headers=self._dau
            )
        except httpx.HTTPError as loi:
            raise LoiEndpoint(f"Không kết nối được ({type(loi).__name__})") from None
        if phan_hoi.is_error:
            raise _loi_tu_choi(phan_hoi)
        return phan_hoi


def _json(phan_hoi: httpx.Response) -> Json:
    try:
        du_lieu = phan_hoi.json()
    except ValueError:
        raise LoiEndpoint(
            f"Thân phản hồi không phải JSON hợp lệ: …{phan_hoi.text[-40:]!r}"
        ) from None
    if not isinstance(du_lieu, dict):
        raise LoiEndpoint("Thân phản hồi không phải một đối tượng JSON")
    return du_lieu


def _thong_diep(du_lieu: object) -> str:
    loi = du_lieu.get("error") if isinstance(du_lieu, dict) else None
    return str(loi.get("message") if isinstance(loi, dict) else loi or du_lieu)


def _loi_tu_choi(phan_hoi: httpx.Response) -> LoiEndpoint:
    try:
        thong_diep = _thong_diep(phan_hoi.json())
    except ValueError:
        thong_diep = phan_hoi.text[:200]
    cho = phan_hoi.headers.get("retry-after", "")
    return LoiEndpoint(
        f"HTTP {phan_hoi.status_code}: {thong_diep}" + (f" (retry-after: {cho})" if cho else ""),
        cho_giay=float(cho) if cho.isdigit() else None,
    )


@dataclass(frozen=True)
class KetQuaThu:
    # None là phép thử bị bỏ qua.
    dat: bool | None
    ghi_chu: str = ""


@dataclass(frozen=True)
class KetQuaModel:
    model: str
    # Tổng thời gian của các lời gọi, không kể lúc chờ endpoint mở khoá.
    giay: float
    phep_thu: dict[str, KetQuaThu] = field(default_factory=dict)


def thu_model(
    endpoint: EndpointLLM, model: str, ngu: Callable[[float], None] = time.sleep
) -> KetQuaModel:
    """Chạy mọi phép thử trên một model. Gọi thường không được thì bỏ qua phần còn lại.

    Endpoint có thể khoá cả model một lúc sau khi từ chối một lời gọi; khi đó chờ hết hạn
    (qua `ngu`) rồi mới đi tiếp, để lời gọi sau không bị từ chối oan.
    """
    cach_thu: dict[str, Callable[[EndpointLLM, str], KetQuaThu]] = {
        "goi_thuong": _goi_thuong,
        "khong_stream": _khong_stream,
        "cong_cu_mot_luot": _cong_cu_mot_luot,
        "cong_cu_nhieu_luot": _cong_cu_nhieu_luot,
        "json_schema": lambda e, m: _co_cau_truc(e, m, dung_schema=True),
        "json_theo_prompt": lambda e, m: _co_cau_truc(e, m, dung_schema=False),
        "tieng_viet": _tieng_viet,
    }
    giay = 0.0
    ket_qua: dict[str, KetQuaThu] = {}
    for ten in PHEP_THU:
        if ket_qua and ket_qua["goi_thuong"].dat is not True:
            ket_qua[ten] = KetQuaThu(None)
            continue
        bat_dau = time.monotonic()
        cho_giay = None
        try:
            ket_qua[ten] = cach_thu[ten](endpoint, model)
        except LoiEndpoint as loi:
            ket_qua[ten] = KetQuaThu(False, str(loi))
            cho_giay = loi.cho_giay
        # Thời gian chờ mở khoá không tính vào thời gian làm việc của model.
        giay += time.monotonic() - bat_dau
        if cho_giay is not None:
            ngu(cho_giay + 1)
    return KetQuaModel(model, giay, ket_qua)


def thu_nhung(endpoint: EndpointLLM, model: str) -> KetQuaThu:
    """Endpoint có tạo được vector nhúng bằng `model` không."""
    try:
        vector = endpoint.nhung(model, "Hãng công bố mẫu pin thể rắn mới.")
    except LoiEndpoint as loi:
        return KetQuaThu(False, str(loi))
    return KetQuaThu(True, f"{len(vector)} chiều")


def _nguoi_dung(noi_dung: str) -> list[Json]:
    return [{"role": "user", "content": noi_dung}]


def _goi_thuong(endpoint: EndpointLLM, model: str) -> KetQuaThu:
    tra_loi = endpoint.tro_chuyen(model, _nguoi_dung("Trả lời đúng một từ: xin chào"))
    return KetQuaThu(bool(tra_loi.noi_dung.strip()), "" if tra_loi.noi_dung else "Trả về rỗng")


def _khong_stream(endpoint: EndpointLLM, model: str) -> KetQuaThu:
    noi_dung = endpoint.tro_chuyen_khong_stream(model, _nguoi_dung("Trả lời đúng một từ: xin chào"))
    return KetQuaThu(bool(noi_dung.strip()), "" if noi_dung else "Trả về rỗng")


def _cong_cu(ten: str, mo_ta: str, tham_so: str, kieu: str) -> Json:
    return {
        "type": "function",
        "function": {
            "name": ten,
            "description": mo_ta,
            "parameters": {
                "type": "object",
                "properties": {tham_so: {"type": kieu}},
                "required": [tham_so],
                "additionalProperties": False,
            },
        },
    }


DOC_BAI_GOC = _cong_cu("doc_bai_goc", "Đọc toàn văn một Bài gốc theo mã.", "ma", "integer")
TIM_BAI_GOC = _cong_cu(
    "tim_bai_goc", "Tìm Bài gốc theo từ khoá; trả về mã và tiêu đề.", "tu_khoa", "string"
)
BAI_GOC = {
    3310: (
        "Giá pin lithium giảm quý thứ ba liên tiếp",
        "Giá pin lithium-ion tiếp tục giảm do dư cung, theo báo cáo thị trường mới nhất.",
    ),
    # Con số chỉ có trong toàn văn, nên muốn trả lời đúng thì phải đọc bài.
    4172: (
        "QuantumCell công bố pin thể rắn có mật độ năng lượng kỷ lục",
        "QuantumCell cho biết mẫu pin thể rắn mới đạt mật độ năng lượng 487 Wh/kg trong thử "
        "nghiệm độc lập, và dự kiến sản xuất thử từ năm 2028.",
    ),
}
MA_CAN_DOC, CON_SO_TRONG_BAI = 4172, "487"


def _tham_so(goi: GoiCongCu) -> Json:
    try:
        tham_so = json.loads(goi.tham_so)
    except ValueError:
        return {}
    return tham_so if isinstance(tham_so, dict) else {}


def _cong_cu_mot_luot(endpoint: EndpointLLM, model: str) -> KetQuaThu:
    tra_loi = endpoint.tro_chuyen(
        model, _nguoi_dung(f"Hãy đọc Bài gốc có mã {MA_CAN_DOC}."), tools=[DOC_BAI_GOC]
    )
    if not tra_loi.goi_cong_cu:
        return KetQuaThu(False, f"Không gọi công cụ, trả lời: {tra_loi.noi_dung[:80]!r}")
    goi = tra_loi.goi_cong_cu[0]
    if goi.ten != "doc_bai_goc" or _tham_so(goi) != {"ma": MA_CAN_DOC}:
        return KetQuaThu(False, f"Gọi sai: {goi.ten}({goi.tham_so})")
    return KetQuaThu(True)


def _chay_cong_cu(goi: GoiCongCu) -> str:
    tham_so = _tham_so(goi)
    if goi.ten == "tim_bai_goc":
        return json.dumps(
            [{"ma": ma, "tieu_de": tieu_de} for ma, (tieu_de, _) in BAI_GOC.items()],
            ensure_ascii=False,
        )
    if goi.ten == "doc_bai_goc" and tham_so.get("ma") in BAI_GOC:
        return BAI_GOC[tham_so["ma"]][1]
    return f"Lỗi: không có {goi.ten}({goi.tham_so})"


def _cong_cu_nhieu_luot(endpoint: EndpointLLM, model: str) -> KetQuaThu:
    """Model phải tìm, đọc đúng bài rồi trả lời bằng con số chỉ có trong toàn văn."""
    tin_nhan = _nguoi_dung(
        "Dùng công cụ để tìm Bài gốc về pin thể rắn, đọc toàn văn bài đó, "
        "rồi cho biết mật độ năng lượng mà bài nêu."
    )
    da_goi: list[str] = []
    for _ in range(SO_LUOT_TOI_DA):
        tra_loi = endpoint.tro_chuyen(model, tin_nhan, tools=[TIM_BAI_GOC, DOC_BAI_GOC])
        if not tra_loi.goi_cong_cu:
            break
        tin_nhan.append(tra_loi.thanh_tin_nhan())
        for goi in tra_loi.goi_cong_cu:
            da_goi.append(f"{goi.ten}({goi.tham_so})")
            tin_nhan.append({"role": "tool", "tool_call_id": goi.id, "content": _chay_cong_cu(goi)})
    else:
        return KetQuaThu(False, f"Chưa trả lời sau {SO_LUOT_TOI_DA} lượt: {', '.join(da_goi)}")

    ten_da_goi = [goi.split("(")[0] for goi in da_goi]
    if "tim_bai_goc" not in ten_da_goi or "doc_bai_goc" not in ten_da_goi:
        thieu = "doc_bai_goc" if "doc_bai_goc" not in ten_da_goi else "tim_bai_goc"
        return KetQuaThu(False, f"Trả lời mà không gọi {thieu}; đã gọi: {', '.join(da_goi)}")
    if CON_SO_TRONG_BAI not in tra_loi.noi_dung:
        return KetQuaThu(False, f"Trả lời thiếu con số trong bài: {tra_loi.noi_dung[:120]!r}")
    return KetQuaThu(True, f"{len(da_goi)} lời gọi công cụ")


class _DanhGia(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    tieu_de: str = Field(min_length=1)
    tom_tat: str = Field(min_length=1)
    diem: int = Field(ge=1, le=10)
    nen_chon: bool


SCHEMA_DANH_GIA = {
    "type": "object",
    "properties": {
        "tieu_de": {"type": "string"},
        "tom_tat": {"type": "string"},
        "diem": {"type": "integer"},
        "nen_chon": {"type": "boolean"},
    },
    "required": ["tieu_de", "tom_tat", "diem", "nen_chon"],
    "additionalProperties": False,
}


def _co_cau_truc(endpoint: EndpointLLM, model: str, *, dung_schema: bool) -> KetQuaThu:
    """Kết quả có cấu trúc, kiểm tra bằng code; có hoặc không nhờ tới `response_format`."""
    de_bai = _nguoi_dung(
        "Đánh giá Bài gốc sau cho Chuyên mục công nghệ. Chỉ trả về một đối tượng JSON, không kèm "
        "chữ nào khác, gồm đúng các trường: tieu_de (chuỗi), tom_tat (chuỗi, một câu), "
        "diem (số nguyên từ 1 đến 10), nen_chon (true hoặc false).\n\n"
        f"Bài gốc: {BAI_GOC[MA_CAN_DOC][1]}"
    )
    tuy_chon: dict[str, object] = {}
    if dung_schema:
        tuy_chon["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "danh_gia", "strict": True, "schema": SCHEMA_DANH_GIA},
        }
    noi_dung = endpoint.tro_chuyen(model, de_bai, **tuy_chon).noi_dung.strip()
    ghi_chu = ""
    if noi_dung.startswith("```"):
        noi_dung = noi_dung.strip("`").removeprefix("json").strip()
        ghi_chu = "Bọc trong khối ```; phải gỡ trước khi đọc"
    try:
        _DanhGia.model_validate_json(noi_dung)
    except ValidationError as loi:
        dau_tien = loi.errors()[0]
        vi_tri = ".".join(str(phan) for phan in dau_tien["loc"]) or "gốc"
        return KetQuaThu(False, f"Sai ở {vi_tri}: {dau_tien['msg']}; nhận {noi_dung[:80]!r}")
    return KetQuaThu(True, ghi_chu)


DOAN_TIENG_ANH = (
    "Nvidia said on Tuesday that its next-generation Rubin GPUs will be manufactured by TSMC "
    "using a 2-nanometer process, with volume shipments expected in the second half of 2027. "
    "The company claims the new chips cut inference costs by 30% compared with the current "
    "Blackwell generation."
)
TEN_PHAI_GIU = ("Nvidia", "Rubin", "GPU", "TSMC", "Blackwell")


def _tieng_viet(endpoint: EndpointLLM, model: str) -> KetQuaThu:
    """Tóm tắt tiếng Việt từ văn bản tiếng Anh. Chỉ soát được phần máy soát được; người đọc
    xem bản tóm tắt trong ghi chú để tự đánh giá câu chữ."""
    tom_tat = endpoint.tro_chuyen(
        model,
        _nguoi_dung(
            "Tóm tắt đoạn sau bằng tiếng Việt trong hai câu. Giữ nguyên tên riêng và thuật ngữ "
            f"chuyên ngành quen dùng bằng tiếng Anh.\n\n{DOAN_TIENG_ANH}"
        ),
    ).noi_dung.strip()
    thieu = [ten for ten in TEN_PHAI_GIU if ten not in tom_tat]
    dat = la_tieng_viet(tom_tat) and not thieu and "30" in tom_tat
    return KetQuaThu(dat, " ".join(tom_tat.split()))


def don_dap(endpoint: EndpointLLM, model: str, so_loi_goi: int) -> Counter[str]:
    """Gửi `so_loi_goi` lời gọi cùng lúc để xem endpoint trả gì khi bị dồn; đếm theo kết quả."""

    def goi(_: int) -> str:
        try:
            endpoint.tro_chuyen(model, _nguoi_dung("Trả lời đúng một từ: xin chào"))
        except LoiEndpoint as loi:
            return str(loi)
        return "thành công"

    with ThreadPoolExecutor(max_workers=so_loi_goi) as nhom:
        return Counter(nhom.map(goi, range(so_loi_goi)))


def thu_nhieu_model(
    endpoint: EndpointLLM, cac_model: Sequence[str], ngu: Callable[[float], None] = time.sleep
) -> list[KetQuaModel]:
    """Thử nhiều model, trả kết quả theo đúng thứ tự `cac_model`.

    Model cùng tiền tố nhà cung cấp (phần trước dấu `/`) được thử lần lượt, vì nhiều tên có thể
    trỏ về cùng một model gốc và endpoint khoá theo model gốc. Các nhà cung cấp chạy song song.
    """
    theo_nha: dict[str, list[str]] = {}
    for model in cac_model:
        theo_nha.setdefault(model.split("/")[0], []).append(model)

    def thu_mot_nha(nhom_model: list[str]) -> list[KetQuaModel]:
        return [thu_model(endpoint, model, ngu) for model in nhom_model]

    with ThreadPoolExecutor(max_workers=max(len(theo_nha), 1)) as nhom:
        da_thu = {
            kq.model: kq for cac_kq in nhom.map(thu_mot_nha, theo_nha.values()) for kq in cac_kq
        }
    return [da_thu[model] for model in cac_model]


def bao_cao(ket_qua: Sequence[KetQuaModel]) -> str:
    """Bảng markdown đạt/không đạt theo model, kèm lí do của từng phép thử không đạt."""
    ki_hieu = {True: "đạt", False: "KHÔNG", None: "–"}
    dong = [
        "| Model | " + " | ".join(PHEP_THU.values()) + " | Giây |",
        "| --- |" + " --- |" * (len(PHEP_THU) + 1),
    ]
    for model in ket_qua:
        cac_o = [ki_hieu[model.phep_thu[ten].dat] for ten in PHEP_THU]
        dong.append(f"| `{model.model}` | " + " | ".join(cac_o) + f" | {model.giay:.0f} |")
    dong.append("")
    for model in ket_qua:
        for ten, nhan in PHEP_THU.items():
            phep = model.phep_thu[ten]
            if phep.ghi_chu and (phep.dat is False or ten == "tieng_viet"):
                dong.append(f"- `{model.model}`, {nhan.lower()}: {phep.ghi_chu}")
    return "\n".join(dong)
