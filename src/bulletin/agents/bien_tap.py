"""Biên tập: Agent chọn Tin nào vào Bản tin và viết từng Tin bằng tiếng Việt.

Vòng làm việc: LLM gọi công cụ (đọc toàn văn một Bài gốc, tìm kiếm web) cho tới khi nộp Bản tin
bằng công cụ `nop_ban_tin`. Bản nộp được kiểm tra bằng code; chưa hợp lệ thì trả lại kèm lí do.
Bản hợp lệ được Kiểm chứng đối chiếu từng Tin với Bài gốc; Tin không đạt quay lại Biên tập để viết
lại bằng `viet_lai_tin`, tối đa hai lần, rồi bị bỏ.
Trạng thái của vòng được lưu sau từng bước, nên gọi lại `lam` với cùng `ma_luong` là chạy tiếp.
"""

import json
import logging
import operator
import re
from collections.abc import Callable, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any, TypedDict
from zoneinfo import ZoneInfo

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from bulletin.agents import cat_toan_van
from bulletin.agents.kiem_chung import KiemChung
from bulletin.publishers import DO_DAI_TIN_TOI_DA, NoiDungTin
from bulletin.search import BoTimKiem
from bulletin.tieng_viet import la_tieng_viet

log = logging.getLogger(__name__)

GIO_VIET_NAM = ZoneInfo("Asia/Ho_Chi_Minh")
# Số Tin Biên tập nên chọn khi đủ Bài gốc đáng đọc; mức trần là của từng Chuyên mục.
SO_TIN_NEN_CO = 5
# Số lần gọi LLM tối đa trong một Kỳ, đủ để đọc vài chục Bài gốc, nộp rồi viết lại.
SO_LUOT_TOI_DA = 40
SO_LAN_NOP_HONG_TOI_DA = 3
# Tin không qua Kiểm chứng được viết lại tối đa ngần này lần rồi bị bỏ (ADR 0001).
SO_LAN_VIET_LAI_TOI_DA = 2
CO_LINK = re.compile(r"https?://|www\.", re.IGNORECASE)

KHUNG = f"""\
Bạn là Biên tập của một bản tin tiếng Việt phát định kỳ. Mỗi Kỳ bạn nhận danh sách Bài gốc ứng \
viên của một Chuyên mục, chọn những Tin đáng đọc nhất và viết từng Tin bằng tiếng Việt.

Cách làm:
1. Dựa vào tiêu đề và Nguồn để khoanh những Bài gốc đáng cân nhắc theo Hướng dẫn của Chuyên mục.
2. Gọi doc_bai_goc để đọc toàn văn mọi Bài gốc định chọn. Chỉ được viết Tin về Bài gốc đã đọc \
toàn văn, và chỉ viết điều có trong toàn văn đó.
3. Khi cần hiểu bối cảnh (một cái tên lạ, một sự kiện trước đó) thì gọi tim_kiem_web. Kết quả tìm \
kiếm chỉ để hiểu bối cảnh: không đưa chi tiết chỉ có ở đó vào Tin, và không biến nó thành Tin.
4. Gọi nop_ban_tin với các Tin đã chọn, Tin đáng đọc nhất đứng trước. Nếu bản nộp bị trả lại thì \
sửa theo lí do rồi nộp lại.
5. Kiểm chứng đối chiếu từng Tin với toàn văn Bài gốc. Tin không đạt được trả lại kèm lí do: viết \
lại đúng theo Bài gốc rồi gọi viet_lai_tin. Tin vẫn không đạt sau {SO_LAN_VIET_LAI_TOI_DA} lần \
viết lại thì bị bỏ khỏi Bản tin.

Quy tắc viết mỗi Tin:
- Tiêu đề và tóm tắt bằng tiếng Việt, kể cả khi Bài gốc bằng tiếng Anh. Tóm tắt dài 4–6 câu, đủ \
để người đọc hiểu tin mà không cần mở link.
- Giữ nguyên tiếng Anh tên riêng (người, công ty, sản phẩm, model) và thuật ngữ chuyên ngành quen \
dùng (ví dụ GPU, open source, fine-tuning); không dịch chúng.
- Số liệu, tên và ngày tháng phải đúng như Bài gốc. Tiêu đề không nói quá điều Bài gốc nói.
- Tiêu đề, tóm tắt và link của Bài gốc cộng lại không quá {DO_DAI_TIN_TOI_DA} ký tự. Không chèn \
link vào tiêu đề hay tóm tắt.
- li_do: một hai câu cho biết vì sao Tin này đáng vào Bản tin."""

NHAC_DUNG_CONG_CU = (
    "Câu trả lời bằng chữ không được ghi nhận. Hãy làm tiếp bằng công cụ; khi đã viết xong các "
    "Tin thì gọi nop_ban_tin, hoặc viet_lai_tin nếu đang có Tin bị Kiểm chứng trả lại."
)


def _cong_cu(ten: str, mo_ta: str, thuoc_tinh: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": ten,
            "description": mo_ta,
            "parameters": {
                "type": "object",
                "properties": thuoc_tinh,
                "required": list(thuoc_tinh),
            },
        },
    }


_THUOC_TINH_BAN_VIET = {
    "ma_bai_goc": {"type": "integer", "description": "Mã của Bài gốc mà Tin dẫn link tới"},
    "tieu_de": {"type": "string", "description": "Tiêu đề tiếng Việt"},
    "tom_tat": {"type": "string", "description": "Tóm tắt tiếng Việt, 4–6 câu"},
}


def _danh_sach_tin(thuoc_tinh: dict[str, Any]) -> dict[str, Any]:
    return {
        "tin": {
            "type": "array",
            "items": {"type": "object", "properties": thuoc_tinh, "required": list(thuoc_tinh)},
        }
    }


CONG_CU = [
    _cong_cu(
        "doc_bai_goc",
        "Đọc toàn văn một Bài gốc trong danh sách ứng viên.",
        {"ma": {"type": "integer", "description": "Mã của Bài gốc"}},
    ),
    _cong_cu(
        "tim_kiem_web",
        "Tìm kiếm web để hiểu bối cảnh của một Tin. Kết quả không phải là Bài gốc.",
        {"truy_van": {"type": "string", "description": "Điều cần tìm"}},
    ),
    _cong_cu(
        "nop_ban_tin",
        "Nộp các Tin đã chọn và viết xong, Tin đáng đọc nhất đứng trước.",
        _danh_sach_tin(
            {
                **_THUOC_TINH_BAN_VIET,
                "li_do": {"type": "string", "description": "Vì sao chọn Tin này"},
            }
        ),
    ),
    _cong_cu(
        "viet_lai_tin",
        "Nộp bản viết lại của mọi Tin bị Kiểm chứng trả lại.",
        _danh_sach_tin(_THUOC_TINH_BAN_VIET),
    ),
]


@dataclass(frozen=True)
class UngVien:
    """Một Bài gốc Biên tập được cân nhắc trong Kỳ."""

    ma: int
    tieu_de: str
    nguon: str
    dia_chi: str
    xuat_hien_luc: datetime


@dataclass(frozen=True)
class DeBai:
    """Việc giao cho Biên tập ở một Kỳ."""

    chuyen_muc: str
    thoi_diem: datetime
    huong_dan: str
    huong_dan_kiem_chung: str
    so_tin_toi_da: int
    ung_vien: Sequence[UngVien]


@dataclass(frozen=True)
class BanViet:
    """Một bản viết của một Tin cùng kết luận của Kiểm chứng về nó."""

    tieu_de: str
    tom_tat: str
    dat: bool
    # Lí do của Kiểm chứng; khi đạt thì có thể trống.
    li_do: str


@dataclass(frozen=True)
class TinDaViet:
    ma_bai_goc: int
    # Vì sao Biên tập chọn Tin này.
    li_do: str
    # Bản đầu rồi các bản viết lại, theo thứ tự; bản cuối là bản được dùng.
    ban_viet: tuple[BanViet, ...]

    @property
    def tieu_de(self) -> str:
        return self.ban_viet[-1].tieu_de

    @property
    def tom_tat(self) -> str:
        return self.ban_viet[-1].tom_tat

    @property
    def li_do_bo(self) -> str | None:
        """Vì sao Tin bị bỏ khỏi Bản tin; None là Tin đã qua Kiểm chứng."""
        cuoi = self.ban_viet[-1]
        if cuoi.dat:
            return None
        return f"Không qua Kiểm chứng sau {len(self.ban_viet) - 1} lần viết lại: {cuoi.li_do}"


class LoiBienTap(Exception):
    """Biên tập không ra được một Bản tin hợp lệ."""


class _BanVietNop(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    ma_bai_goc: int
    tieu_de: str = Field(min_length=1)
    tom_tat: str = Field(min_length=1)

    @field_validator("tieu_de", "tom_tat")
    @classmethod
    def _mot_doan(cls, van_ban: str) -> str:
        return " ".join(van_ban.split())


class _TinNop(_BanVietNop):
    li_do: str = Field(min_length=1)


class _BanTinNop(BaseModel):
    tin: list[_TinNop] = Field(min_length=1)


class _VietLaiNop(BaseModel):
    tin: list[_BanVietNop] = Field(min_length=1)


class _ThamSoDoc(BaseModel):
    ma: int


class _ThamSoTim(BaseModel):
    truy_van: str = Field(min_length=1)


class _TrangThai(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    # Mã, tiêu đề và link của các ứng viên: bản nộp được soát theo đây, kể cả khi chạy tiếp.
    ung_vien: list[dict[str, Any]]
    so_tin_toi_da: int
    huong_dan_kiem_chung: str
    da_doc: Annotated[list[int], operator.add]
    so_luot: int
    so_lan_nop_hong: int
    # Chưa nộp được Bản tin hợp lệ thì là None. Sau đó là các Tin theo thứ tự nộp, mỗi Tin có
    # `ma_bai_goc`, `li_do` và `ban_viet`; bản viết cuối chưa có `dat` là đang chờ Kiểm chứng.
    tin: list[dict[str, Any]] | None
    # Có giá trị thì vòng kết thúc vì Biên tập không làm được.
    loi: str | None


def _cho_kiem_chung(tin: dict[str, Any]) -> bool:
    return bool(tin["ban_viet"][-1]["dat"] is None)


def _cho_viet_lai(tin: dict[str, Any]) -> bool:
    return tin["ban_viet"][-1]["dat"] is False and len(tin["ban_viet"]) <= SO_LAN_VIET_LAI_TOI_DA


class BienTap:
    def __init__(
        self,
        llm: BaseChatModel,
        kiem_chung: KiemChung,
        tim_kiem: BoTimKiem,
        kho_trang_thai: BaseCheckpointSaver[Any],
    ) -> None:
        self._llm = llm.bind_tools(CONG_CU)
        self._kiem_chung = kiem_chung
        self._tim_kiem = tim_kiem
        self._kho_trang_thai = kho_trang_thai

    def lam(
        self, ma_luong: str, de_bai: DeBai, doc_bai_goc: Callable[[int], str]
    ) -> list[TinDaViet]:
        """Chọn, viết và cho Kiểm chứng xét các Tin của `de_bai`; `doc_bai_goc` trả về toàn văn
        theo mã Bài gốc.

        Trả về mọi Tin đã nộp theo thứ tự nộp, kể cả Tin bị bỏ vì không qua Kiểm chứng.
        `ma_luong` nhận diện lần làm việc này. Lần trước cùng mã mà dở dang thì làm tiếp từ bước
        đang dở và bỏ qua `de_bai`; đã xong thì trả lại kết quả cũ. Ném `LoiBienTap` khi Biên tập
        không nộp được Bản tin hợp lệ, và `LoiKiemChung` khi Kiểm chứng không ra được kết luận.
        """
        do_thi = self._do_thi(doc_bai_goc)
        cau_hinh: Any = {
            "configurable": {"thread_id": ma_luong},
            # Mỗi lượt là hai bước, cộng một bước Kiểm chứng cho bản nộp và từng lần viết lại.
            "recursion_limit": 2 * SO_LUOT_TOI_DA + SO_LAN_VIET_LAI_TOI_DA + 5,
        }
        da_luu = do_thi.get_state(cau_hinh)
        if da_luu.values and not da_luu.next:
            ket_thuc = da_luu.values
        else:
            dau_vao = None if da_luu.values else _khoi_dau(de_bai)
            # Lưu xong từng bước rồi mới làm bước sau, để mất điện giữa chừng không mất bước nào.
            ket_thuc = do_thi.invoke(dau_vao, cau_hinh, durability="sync")
        if ket_thuc["loi"] is not None:
            raise LoiBienTap(f"Biên tập {ket_thuc['loi']}")
        return [
            TinDaViet(
                ma_bai_goc=tin["ma_bai_goc"],
                li_do=tin["li_do"],
                ban_viet=tuple(BanViet(**ban) for ban in tin["ban_viet"]),
            )
            for tin in ket_thuc["tin"]
        ]

    def _do_thi(self, doc_bai_goc: Callable[[int], str]) -> Any:
        # LangGraph nhận diện node qua tham số tên `state`.
        def goi_llm(state: _TrangThai) -> dict[str, Any]:
            tra_loi = self._llm.invoke(state["messages"])
            return {"messages": [tra_loi], "so_luot": state["so_luot"] + 1}

        def chay_cong_cu(state: _TrangThai) -> dict[str, Any]:
            tra_loi = state["messages"][-1]
            assert isinstance(tra_loi, AIMessage)
            ung_vien = {uv["ma"]: uv["dia_chi"] for uv in state["ung_vien"]}
            da_doc = set(state["da_doc"])
            moi_doc: list[int] = []
            tin_nhan: list[AnyMessage] = [
                ToolMessage("Tham số không phải JSON hợp lệ.", tool_call_id=goi["id"] or "")
                for goi in tra_loi.invalid_tool_calls
            ]
            tin = deepcopy(state["tin"])
            loi_nop: list[str] = []
            for goi in tra_loi.tool_calls:
                ten, tham_so = goi["name"], goi["args"]
                try:
                    if ten == "doc_bai_goc":
                        ma = _ThamSoDoc.model_validate(tham_so).ma
                        doc_duoc, noi_dung = self._doc(ma, ung_vien, doc_bai_goc)
                        if doc_duoc:
                            moi_doc.append(ma)
                    elif ten == "tim_kiem_web":
                        noi_dung = self._tim(_ThamSoTim.model_validate(tham_so).truy_van)
                    elif ten == "nop_ban_tin":
                        if tin is not None:
                            loi_nop = [
                                "Bản tin đã được nhận. Chỉ viết lại các Tin bị Kiểm chứng trả "
                                "lại, bằng viet_lai_tin."
                            ]
                        else:
                            ban_nop = _BanTinNop.model_validate(tham_so)
                            loi_nop = _soat(
                                ban_nop, ung_vien, da_doc | set(moi_doc), state["so_tin_toi_da"]
                            )
                            if not loi_nop:
                                tin = [_tin_moi(tin_nop) for tin_nop in ban_nop.tin]
                        noi_dung = (
                            _tra_lai(loi_nop)
                            if loi_nop
                            else "Đã nhận Bản tin; các Tin được chuyển cho Kiểm chứng."
                        )
                    elif ten == "viet_lai_tin":
                        cho_viet_lai = {
                            muc["ma_bai_goc"]: muc for muc in tin or () if _cho_viet_lai(muc)
                        }
                        if not cho_viet_lai:
                            loi_nop = ["Không có Tin nào đang chờ viết lại."]
                        else:
                            viet_lai = _VietLaiNop.model_validate(tham_so)
                            loi_nop = _soat_viet_lai(viet_lai, cho_viet_lai, ung_vien)
                            if not loi_nop:
                                for ban in viet_lai.tin:
                                    cho_viet_lai[ban.ma_bai_goc]["ban_viet"].append(
                                        _ban_viet_moi(ban)
                                    )
                        noi_dung = (
                            _tra_lai(loi_nop)
                            if loi_nop
                            else "Đã nhận các bản viết lại; chúng được chuyển cho Kiểm chứng."
                        )
                    else:
                        noi_dung = f"Không có công cụ {ten}."
                except ValidationError as loi:
                    loi_tham_so = [
                        f"{'.'.join(str(phan) for phan in muc['loc']) or 'tham số'}: {muc['msg']}"
                        for muc in loi.errors()
                    ]
                    if ten in ("nop_ban_tin", "viet_lai_tin"):
                        loi_nop = loi_tham_so
                    noi_dung = _tra_lai(loi_tham_so)
                tin_nhan.append(ToolMessage(noi_dung, tool_call_id=goi["id"] or ""))
            if not tin_nhan:
                tin_nhan.append(HumanMessage(NHAC_DUNG_CONG_CU))

            so_lan_nop_hong = state["so_lan_nop_hong"] + (1 if loi_nop else 0)
            cap_nhat: dict[str, Any] = {
                "messages": tin_nhan,
                "da_doc": moi_doc,
                "tin": tin,
                "so_lan_nop_hong": so_lan_nop_hong,
            }
            if so_lan_nop_hong >= SO_LAN_NOP_HONG_TOI_DA:
                cap_nhat["loi"] = (
                    f"nộp Bản tin không hợp lệ {so_lan_nop_hong} lần; lần cuối: "
                    + "; ".join(loi_nop)
                )
            elif state["so_luot"] >= SO_LUOT_TOI_DA and not any(map(_cho_kiem_chung, tin or ())):
                viec = "nộp Bản tin" if tin is None else "viết lại xong các Tin bị trả lại"
                cap_nhat["loi"] = f"chưa {viec} sau {SO_LUOT_TOI_DA} lượt"
            return cap_nhat

        def kiem_chung(state: _TrangThai) -> dict[str, Any]:
            assert state["tin"] is not None
            tin = deepcopy(state["tin"])
            tieu_de_goc = {uv["ma"]: uv["tieu_de"] for uv in state["ung_vien"]}
            for muc in filter(_cho_kiem_chung, tin):
                ma, ban = muc["ma_bai_goc"], muc["ban_viet"][-1]
                ket_luan = self._kiem_chung.xet(
                    state["huong_dan_kiem_chung"],
                    tieu_de_goc[ma],
                    doc_bai_goc(ma),
                    ban["tieu_de"],
                    ban["tom_tat"],
                )
                ban["dat"], ban["li_do"] = ket_luan.dat, ket_luan.li_do
                log.info(
                    "Kiểm chứng Tin về Bài gốc %s: %s",
                    ma,
                    "đạt" if ket_luan.dat else f"không đạt, {ket_luan.li_do}",
                )
            cap_nhat: dict[str, Any] = {"tin": tin}
            if any(map(_cho_viet_lai, tin)):
                cap_nhat["messages"] = [HumanMessage(_yeu_cau_viet_lai(tin))]
            return cap_nhat

        def sau_cong_cu(state: _TrangThai) -> str:
            if state["loi"] is not None:
                return END
            if any(map(_cho_kiem_chung, state["tin"] or ())):
                return "kiem_chung"
            return "goi_llm"

        def sau_kiem_chung(state: _TrangThai) -> str:
            assert state["tin"] is not None
            return "goi_llm" if any(map(_cho_viet_lai, state["tin"])) else END

        return (
            StateGraph(_TrangThai)
            .add_node("goi_llm", goi_llm)
            .add_node("chay_cong_cu", chay_cong_cu)
            .add_node("kiem_chung", kiem_chung)
            .add_edge(START, "goi_llm")
            .add_edge("goi_llm", "chay_cong_cu")
            .add_conditional_edges("chay_cong_cu", sau_cong_cu, ["goi_llm", "kiem_chung", END])
            .add_conditional_edges("kiem_chung", sau_kiem_chung, ["goi_llm", END])
            .compile(checkpointer=self._kho_trang_thai)
        )

    def _doc(
        self, ma: int, ung_vien: dict[int, str], doc_bai_goc: Callable[[int], str]
    ) -> tuple[bool, str]:
        """Toàn văn của ứng viên `ma` cho LLM đọc, kèm có đọc được hay không."""
        if ma not in ung_vien:
            return False, f"Không có Bài gốc mã {ma} trong danh sách ứng viên."
        log.info("Biên tập đọc Bài gốc %s", ung_vien[ma])
        try:
            toan_van = doc_bai_goc(ma)
        except Exception as loi:
            log.warning("Không đọc được Bài gốc %s: %s", ung_vien[ma], loi)
            return False, f"Không đọc được toàn văn Bài gốc {ma}: {loi}. Hãy chọn Bài gốc khác."
        return True, cat_toan_van(toan_van)

    def _tim(self, truy_van: str) -> str:
        log.info("Biên tập tìm kiếm web: %s", truy_van)
        try:
            ket_qua = self._tim_kiem.tim(truy_van)
        except Exception as loi:
            log.warning("Tìm kiếm web lỗi: %s", loi)
            return f"Không tìm kiếm được: {loi}. Hãy làm tiếp mà không cần tìm kiếm."
        if not ket_qua:
            return "Không có kết quả."
        return "Kết quả tìm kiếm (chỉ để hiểu bối cảnh, không phải Bài gốc):\n" + "\n".join(
            f"{thu_tu}. {muc.tieu_de}\n   {muc.dia_chi}\n   {muc.trich_doan}"
            for thu_tu, muc in enumerate(ket_qua, start=1)
        )


def _khoi_dau(de_bai: DeBai) -> _TrangThai:
    toi_da = de_bai.so_tin_toi_da
    ung_vien = "\n".join(
        json.dumps(
            {
                "ma": uv.ma,
                "tieu_de": uv.tieu_de,
                "nguon": uv.nguon,
                "dia_chi": uv.dia_chi,
                "xuat_hien_luc": uv.xuat_hien_luc.astimezone(GIO_VIET_NAM).isoformat(
                    timespec="minutes"
                ),
            },
            ensure_ascii=False,
        )
        for uv in de_bai.ung_vien
    )
    viec = (
        f"Chuyên mục: {de_bai.chuyen_muc}\n"
        f"Bây giờ là {de_bai.thoi_diem.astimezone(GIO_VIET_NAM).isoformat(timespec='minutes')}.\n"
        f"Chọn từ {min(SO_TIN_NEN_CO, toi_da)} đến {toi_da} Tin đáng đọc nhất; chỉ chọn ít hơn "
        f"khi không đủ Bài gốc đáng đọc, và không bao giờ quá {toi_da}.\n\n"
        f"Ứng viên, mỗi dòng một Bài gốc:\n{ung_vien}"
    )
    return {
        "messages": [
            SystemMessage(f"{KHUNG}\n\n# Hướng dẫn của Chuyên mục\n\n{de_bai.huong_dan}"),
            HumanMessage(viec),
        ],
        "ung_vien": [
            {"ma": uv.ma, "tieu_de": uv.tieu_de, "dia_chi": uv.dia_chi} for uv in de_bai.ung_vien
        ],
        "so_tin_toi_da": toi_da,
        "huong_dan_kiem_chung": de_bai.huong_dan_kiem_chung,
        "da_doc": [],
        "so_luot": 0,
        "so_lan_nop_hong": 0,
        "tin": None,
        "loi": None,
    }


def _ban_viet_moi(ban: _BanVietNop) -> dict[str, Any]:
    return {"tieu_de": ban.tieu_de, "tom_tat": ban.tom_tat, "dat": None, "li_do": None}


def _tin_moi(tin: _TinNop) -> dict[str, Any]:
    return {"ma_bai_goc": tin.ma_bai_goc, "li_do": tin.li_do, "ban_viet": [_ban_viet_moi(tin)]}


def _soat(
    ban_nop: _BanTinNop, ung_vien: dict[int, str], da_doc: set[int], so_tin_toi_da: int
) -> list[str]:
    """Những chỗ bản nộp chưa hợp lệ; rỗng là hợp lệ."""
    loi = []
    if len(ban_nop.tin) > so_tin_toi_da:
        loi.append(f"Có {len(ban_nop.tin)} Tin, nhiều hơn mức tối đa {so_tin_toi_da}.")
    ma_da_gap: set[int] = set()
    for tin in ban_nop.tin:
        ma = tin.ma_bai_goc
        if ma not in ung_vien:
            loi.append(
                f"Bài gốc mã {ma} không có trong danh sách ứng viên. Tin chỉ được dẫn tới Bài gốc "
                "ứng viên, không dẫn tới kết quả tìm kiếm."
            )
            continue
        if ma in ma_da_gap:
            loi.append(f"Bài gốc {ma} được dùng cho hơn một Tin.")
        ma_da_gap.add(ma)
        if ma not in da_doc:
            loi.append(f"Tin về Bài gốc {ma}: chưa đọc toàn văn; gọi doc_bai_goc trước khi viết.")
        loi += _soat_ban_viet(tin, ung_vien[ma])
    return loi


def _soat_viet_lai(
    viet_lai: _VietLaiNop, cho_viet_lai: dict[int, dict[str, Any]], ung_vien: dict[int, str]
) -> list[str]:
    """Những chỗ bản viết lại chưa hợp lệ; rỗng là hợp lệ."""
    loi = []
    ma_da_gap: set[int] = set()
    for ban in viet_lai.tin:
        ma = ban.ma_bai_goc
        if ma not in cho_viet_lai:
            loi.append(f"Tin về Bài gốc {ma} không bị trả lại; chỉ viết lại Tin bị trả lại.")
            continue
        if ma in ma_da_gap:
            loi.append(f"Tin về Bài gốc {ma} được viết lại hơn một lần trong cùng bản nộp.")
        ma_da_gap.add(ma)
        loi += _soat_ban_viet(ban, ung_vien[ma])
    for ma in cho_viet_lai.keys() - ma_da_gap:
        loi.append(f"Thiếu bản viết lại của Tin về Bài gốc {ma}.")
    return loi


def _soat_ban_viet(ban: _BanVietNop, dia_chi: str) -> list[str]:
    """Những chỗ một bản viết vi phạm quy tắc viết; rỗng là hợp lệ."""
    loi = []
    ma = ban.ma_bai_goc
    # Tiêu đề ngắn và nhiều tên riêng nên không soát được bằng cách này.
    if not la_tieng_viet(ban.tom_tat):
        loi.append(f"Tin về Bài gốc {ma}: tóm tắt phải bằng tiếng Việt.")
    if CO_LINK.search(ban.tieu_de) or CO_LINK.search(ban.tom_tat):
        loi.append(f"Tin về Bài gốc {ma}: tiêu đề và tóm tắt không được chứa link.")
    do_dai = NoiDungTin(ban.tieu_de, ban.tom_tat, dia_chi).do_dai
    if do_dai > DO_DAI_TIN_TOI_DA:
        loi.append(
            f"Tin về Bài gốc {ma}: tiêu đề, tóm tắt và link dài {do_dai} ký tự, vượt giới hạn "
            f"{DO_DAI_TIN_TOI_DA}; rút gọn {do_dai - DO_DAI_TIN_TOI_DA} ký tự."
        )
    return loi


def _yeu_cau_viet_lai(tin: Sequence[dict[str, Any]]) -> str:
    """Lời Kiểm chứng gửi Biên tập: những Tin phải viết lại, và những Tin vừa bị bỏ."""
    viet_lai = [
        f"- Bài gốc {muc['ma_bai_goc']}, lần viết lại {len(muc['ban_viet'])}/"
        f"{SO_LAN_VIET_LAI_TOI_DA}. Bản hiện tại: {muc['ban_viet'][-1]['tieu_de']!r}. "
        f"Lí do: {muc['ban_viet'][-1]['li_do']}"
        for muc in tin
        if _cho_viet_lai(muc)
    ]
    bi_bo = [
        str(muc["ma_bai_goc"])
        for muc in tin
        if muc["ban_viet"][-1]["dat"] is False and not _cho_viet_lai(muc)
    ]
    loi_nhan = (
        "Kiểm chứng đã đối chiếu các Tin với Bài gốc. Những Tin dưới đây không đạt: viết lại "
        "từng Tin theo lí do, chỉ dựa trên toàn văn Bài gốc, rồi gọi viet_lai_tin với đủ các Tin "
        "này. Các Tin khác không cần sửa.\n" + "\n".join(viet_lai)
    )
    if bi_bo:
        loi_nhan += (
            f"\n\nTin về Bài gốc {', '.join(bi_bo)} đã bị bỏ khỏi Bản tin vì không đạt sau "
            f"{SO_LAN_VIET_LAI_TOI_DA} lần viết lại."
        )
    return loi_nhan


def _tra_lai(loi: Sequence[str]) -> str:
    return "Chưa hợp lệ, hãy sửa rồi gọi lại:\n" + "\n".join(f"- {muc}" for muc in loi)
