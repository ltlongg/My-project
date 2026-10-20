"""Biên tập: Agent chọn Tin nào vào Bản tin và viết từng Tin bằng tiếng Việt.

Vòng làm việc: LLM gọi công cụ (đọc toàn văn một Bài gốc, tìm kiếm web) cho tới khi nộp Bản tin
bằng công cụ `nop_ban_tin`. Bản nộp được kiểm tra bằng code; chưa hợp lệ thì trả lại kèm lí do.
Trạng thái của vòng được lưu sau từng bước, nên gọi lại `lam` với cùng `ma_luong` là chạy tiếp.
"""

import json
import logging
import operator
import re
from collections.abc import Callable, Sequence
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

from bulletin.publishers import DO_DAI_TIN_TOI_DA, NoiDungTin
from bulletin.search import BoTimKiem
from bulletin.tieng_viet import la_tieng_viet

log = logging.getLogger(__name__)

GIO_VIET_NAM = ZoneInfo("Asia/Ho_Chi_Minh")
# Số Tin Biên tập nên chọn khi đủ Bài gốc đáng đọc; mức trần là của từng Chuyên mục.
SO_TIN_NEN_CO = 5
# Số lần gọi LLM tối đa trong một Kỳ, đủ để đọc vài chục Bài gốc rồi nộp.
SO_LUOT_TOI_DA = 40
SO_LAN_NOP_HONG_TOI_DA = 3
# Phần toàn văn đưa cho LLM; bài dài hơn thì cắt, vì tin chính nằm ở đầu bài.
TOAN_VAN_TOI_DA = 20_000
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

Quy tắc viết mỗi Tin:
- Tiêu đề và tóm tắt bằng tiếng Việt, kể cả khi Bài gốc bằng tiếng Anh. Tóm tắt dài 4–6 câu, đủ \
để người đọc hiểu tin mà không cần mở link.
- Giữ nguyên tiếng Anh tên riêng (người, công ty, sản phẩm, model) và thuật ngữ chuyên ngành quen \
dùng (ví dụ GPU, open source, fine-tuning); không dịch chúng.
- Số liệu, tên và ngày tháng phải đúng như Bài gốc.
- Tiêu đề, tóm tắt và link của Bài gốc cộng lại không quá {DO_DAI_TIN_TOI_DA} ký tự. Không chèn \
link vào tiêu đề hay tóm tắt.
- li_do: một hai câu cho biết vì sao Tin này đáng vào Bản tin."""

NHAC_DUNG_CONG_CU = (
    "Câu trả lời bằng chữ không được ghi nhận. Hãy làm tiếp bằng công cụ; khi đã viết xong các "
    "Tin thì gọi nop_ban_tin."
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
        {
            "tin": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "ma_bai_goc": {
                            "type": "integer",
                            "description": "Mã của Bài gốc mà Tin dẫn link tới",
                        },
                        "tieu_de": {"type": "string", "description": "Tiêu đề tiếng Việt"},
                        "tom_tat": {"type": "string", "description": "Tóm tắt tiếng Việt, 4–6 câu"},
                        "li_do": {"type": "string", "description": "Vì sao chọn Tin này"},
                    },
                    "required": ["ma_bai_goc", "tieu_de", "tom_tat", "li_do"],
                },
            }
        },
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
    so_tin_toi_da: int
    ung_vien: Sequence[UngVien]


@dataclass(frozen=True)
class TinDaViet:
    ma_bai_goc: int
    tieu_de: str
    tom_tat: str
    li_do: str


class LoiBienTap(Exception):
    """Biên tập không ra được một Bản tin hợp lệ."""


class _TinNop(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    ma_bai_goc: int
    tieu_de: str = Field(min_length=1)
    tom_tat: str = Field(min_length=1)
    li_do: str = Field(min_length=1)

    @field_validator("tieu_de", "tom_tat")
    @classmethod
    def _mot_doan(cls, van_ban: str) -> str:
        return " ".join(van_ban.split())


class _BanTinNop(BaseModel):
    tin: list[_TinNop] = Field(min_length=1)


class _ThamSoDoc(BaseModel):
    ma: int


class _ThamSoTim(BaseModel):
    truy_van: str = Field(min_length=1)


class _TrangThai(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    # Mã và link của các ứng viên: bản nộp được soát theo đây, kể cả khi chạy tiếp.
    ung_vien: list[dict[str, Any]]
    so_tin_toi_da: int
    da_doc: Annotated[list[int], operator.add]
    so_luot: int
    so_lan_nop_hong: int
    # Một trong hai có giá trị thì vòng kết thúc.
    tin: list[dict[str, Any]] | None
    loi: str | None


class BienTap:
    def __init__(
        self, llm: BaseChatModel, tim_kiem: BoTimKiem, kho_trang_thai: BaseCheckpointSaver[Any]
    ) -> None:
        self._llm = llm.bind_tools(CONG_CU)
        self._tim_kiem = tim_kiem
        self._kho_trang_thai = kho_trang_thai

    def lam(
        self, ma_luong: str, de_bai: DeBai, doc_bai_goc: Callable[[int], str]
    ) -> list[TinDaViet]:
        """Chọn và viết các Tin cho `de_bai`; `doc_bai_goc` trả về toàn văn theo mã Bài gốc.

        `ma_luong` nhận diện lần làm việc này. Lần trước cùng mã mà dở dang thì làm tiếp từ bước
        đang dở và bỏ qua `de_bai`; đã xong thì trả lại kết quả cũ. Ném `LoiBienTap` khi Biên tập
        không nộp được Bản tin hợp lệ.
        """
        do_thi = self._do_thi(doc_bai_goc)
        cau_hinh: Any = {
            "configurable": {"thread_id": ma_luong},
            "recursion_limit": 2 * SO_LUOT_TOI_DA + 5,
        }
        da_luu = do_thi.get_state(cau_hinh)
        if da_luu.values and not da_luu.next:
            ket_thuc = da_luu.values
        else:
            dau_vao = None if da_luu.values else _khoi_dau(de_bai)
            # Lưu xong từng bước rồi mới làm bước sau, để mất điện giữa chừng không mất bước nào.
            ket_thuc = do_thi.invoke(dau_vao, cau_hinh, durability="sync")
        if ket_thuc["tin"] is None:
            raise LoiBienTap(f"Biên tập {ket_thuc['loi']}")
        return [TinDaViet(**tin) for tin in ket_thuc["tin"]]

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
            tin: list[dict[str, Any]] | None = None
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
                        ban_nop = _BanTinNop.model_validate(tham_so)
                        loi_nop = _soat(
                            ban_nop, ung_vien, da_doc | set(moi_doc), state["so_tin_toi_da"]
                        )
                        if loi_nop:
                            noi_dung = _tra_lai(loi_nop)
                        else:
                            tin = [tin_nop.model_dump() for tin_nop in ban_nop.tin]
                            noi_dung = "Đã nhận Bản tin."
                    else:
                        noi_dung = f"Không có công cụ {ten}."
                except ValidationError as loi:
                    loi_tham_so = [
                        f"{'.'.join(str(phan) for phan in muc['loc']) or 'tham số'}: {muc['msg']}"
                        for muc in loi.errors()
                    ]
                    if ten == "nop_ban_tin":
                        loi_nop = loi_tham_so
                    noi_dung = _tra_lai(loi_tham_so)
                tin_nhan.append(ToolMessage(noi_dung, tool_call_id=goi["id"] or ""))
            if not tin_nhan:
                tin_nhan.append(HumanMessage(NHAC_DUNG_CONG_CU))

            cap_nhat: dict[str, Any] = {"messages": tin_nhan, "da_doc": moi_doc, "tin": tin}
            if tin is None:
                so_lan_nop_hong = state["so_lan_nop_hong"] + (1 if loi_nop else 0)
                cap_nhat["so_lan_nop_hong"] = so_lan_nop_hong
                if so_lan_nop_hong >= SO_LAN_NOP_HONG_TOI_DA:
                    cap_nhat["loi"] = (
                        f"nộp Bản tin không hợp lệ {so_lan_nop_hong} lần; lần cuối: "
                        + "; ".join(loi_nop)
                    )
                elif state["so_luot"] >= SO_LUOT_TOI_DA:
                    cap_nhat["loi"] = f"chưa nộp Bản tin sau {SO_LUOT_TOI_DA} lượt"
            return cap_nhat

        def buoc_sau(state: _TrangThai) -> str:
            xong = state["tin"] is not None or state["loi"] is not None
            return END if xong else "goi_llm"

        return (
            StateGraph(_TrangThai)
            .add_node("goi_llm", goi_llm)
            .add_node("chay_cong_cu", chay_cong_cu)
            .add_edge(START, "goi_llm")
            .add_edge("goi_llm", "chay_cong_cu")
            .add_conditional_edges("chay_cong_cu", buoc_sau, ["goi_llm", END])
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
        if len(toan_van) > TOAN_VAN_TOI_DA:
            toan_van = toan_van[:TOAN_VAN_TOI_DA] + "\n[Bài còn dài; phần sau đã được cắt bớt.]"
        return True, toan_van

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
        "ung_vien": [{"ma": uv.ma, "dia_chi": uv.dia_chi} for uv in de_bai.ung_vien],
        "so_tin_toi_da": toi_da,
        "da_doc": [],
        "so_luot": 0,
        "so_lan_nop_hong": 0,
        "tin": None,
        "loi": None,
    }


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
        # Tiêu đề ngắn và nhiều tên riêng nên không soát được bằng cách này.
        if not la_tieng_viet(tin.tom_tat):
            loi.append(f"Tin về Bài gốc {ma}: tóm tắt phải bằng tiếng Việt.")
        if CO_LINK.search(tin.tieu_de) or CO_LINK.search(tin.tom_tat):
            loi.append(f"Tin về Bài gốc {ma}: tiêu đề và tóm tắt không được chứa link.")
        do_dai = NoiDungTin(tin.tieu_de, tin.tom_tat, ung_vien[ma]).do_dai
        if do_dai > DO_DAI_TIN_TOI_DA:
            loi.append(
                f"Tin về Bài gốc {ma}: tiêu đề, tóm tắt và link dài {do_dai} ký tự, vượt giới hạn "
                f"{DO_DAI_TIN_TOI_DA}; rút gọn {do_dai - DO_DAI_TIN_TOI_DA} ký tự."
            )
    return loi


def _tra_lai(loi: Sequence[str]) -> str:
    return "Chưa hợp lệ, hãy sửa rồi gọi lại:\n" + "\n".join(f"- {muc}" for muc in loi)
