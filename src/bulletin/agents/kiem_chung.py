"""Kiểm chứng: Agent đối chiếu từng Tin đã viết với toàn văn Bài gốc của nó.

Mỗi lần xét là một Tin. LLM trả kết luận bằng công cụ `ket_luan`; kết luận được kiểm tra bằng
code, hỏng thì nhắc lại, hỏng quá số lần cho phép thì là lỗi của Kỳ.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from bulletin.agents import cat_toan_van

log = logging.getLogger(__name__)

SO_LAN_TRA_LOI_HONG_TOI_DA = 3

KHUNG = """\
Bạn là Kiểm chứng của một bản tin tiếng Việt phát định kỳ, và là chốt chặn duy nhất trước khi \
Tin được phát: không ai duyệt lại sau bạn. Bạn nhận một Tin do Biên tập viết (tiêu đề và tóm tắt) \
cùng toàn văn Bài gốc của nó.

Đối chiếu Tin với toàn văn theo Hướng dẫn bên dưới. Toàn văn Bài gốc là căn cứ duy nhất: chi tiết \
nào không có trong đó thì coi như không có căn cứ, kể cả khi bạn tin là nó đúng.

Gọi ket_luan đúng một lần. dat là true khi Tin đạt. Khi không đạt, li_do phải chỉ ra từng chi tiết \
sai, Tin viết gì và Bài gốc nói gì, để Biên tập sửa được mà không phải đoán."""

NHAC_DUNG_CONG_CU = "Câu trả lời bằng chữ không được ghi nhận. Hãy gọi ket_luan."

CONG_CU = [
    {
        "type": "function",
        "function": {
            "name": "ket_luan",
            "description": "Kết luận Tin đạt hay không đạt khi đối chiếu với Bài gốc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dat": {"type": "boolean", "description": "Tin có đạt không"},
                    "li_do": {
                        "type": "string",
                        "description": (
                            "Những chi tiết sai và Bài gốc nói gì; bắt buộc khi không đạt"
                        ),
                    },
                },
                "required": ["dat", "li_do"],
            },
        },
    }
]


@dataclass(frozen=True)
class KetLuan:
    dat: bool
    # Khi đạt thì có thể trống.
    li_do: str


class LoiKiemChung(Exception):
    """Kiểm chứng không ra được kết luận hợp lệ."""


class _KetLuanNop(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    dat: bool
    li_do: str = ""

    @model_validator(mode="after")
    def _khong_dat_phai_co_li_do(self) -> "_KetLuanNop":
        if not self.dat and not self.li_do:
            raise ValueError("không đạt thì phải nêu li_do")
        return self


class KiemChung:
    def __init__(self, llm: BaseChatModel) -> None:
        self._llm = llm.bind_tools(CONG_CU)

    def xet(
        self, huong_dan: str, tieu_de_bai_goc: str, toan_van: str, tieu_de: str, tom_tat: str
    ) -> KetLuan:
        """Đối chiếu một Tin (`tieu_de`, `tom_tat`) với Bài gốc của nó.

        Ném `LoiKiemChung` khi LLM lỗi hoặc mãi không trả được kết luận hợp lệ.
        """
        tin = json.dumps({"tieu_de": tieu_de, "tom_tat": tom_tat}, ensure_ascii=False)
        tin_nhan: list[AnyMessage] = [
            SystemMessage(f"{KHUNG}\n\n# Hướng dẫn của Kiểm chứng\n\n{huong_dan}"),
            HumanMessage(
                f"Bài gốc: {tieu_de_bai_goc}\n\nToàn văn Bài gốc:\n{cat_toan_van(toan_van)}\n\n"
                f"Tin cần đối chiếu:\n{tin}"
            ),
        ]
        loi: list[str] = []
        for _ in range(SO_LAN_TRA_LOI_HONG_TOI_DA):
            try:
                tra_loi = self._llm.invoke(tin_nhan)
            except Exception as loi_goi:
                raise LoiKiemChung(
                    f"Kiểm chứng gặp lỗi: {str(loi_goi).splitlines()[0]}"
                ) from loi_goi
            assert isinstance(tra_loi, AIMessage)
            ket_luan, loi, tra_lai = _doc_ket_luan(tra_loi)
            if ket_luan is not None:
                return ket_luan
            log.warning("Kiểm chứng trả kết luận không hợp lệ: %s", "; ".join(loi))
            tin_nhan += [tra_loi, *tra_lai]
        raise LoiKiemChung(
            f"Kiểm chứng trả kết luận không hợp lệ {SO_LAN_TRA_LOI_HONG_TOI_DA} lần; lần cuối: "
            + "; ".join(loi)
        )


def _doc_ket_luan(
    tra_loi: AIMessage,
) -> tuple[KetLuan | None, list[str], list[AnyMessage]]:
    """Kết luận trong câu trả lời nếu hợp lệ; nếu không thì các lỗi và tin nhắn trả lại LLM."""
    goi_ket_luan = [goi for goi in tra_loi.tool_calls if goi["name"] == "ket_luan"]
    if len(goi_ket_luan) == 1 and not tra_loi.invalid_tool_calls:
        tham_so: dict[str, Any] = goi_ket_luan[0]["args"]
        try:
            nop = _KetLuanNop.model_validate(tham_so)
            return KetLuan(nop.dat, nop.li_do), [], []
        except ValidationError as loi_tham_so:
            loi = [
                f"{'.'.join(str(phan) for phan in muc['loc']) or 'tham số'}: {muc['msg']}"
                for muc in loi_tham_so.errors()
            ]
    elif goi_ket_luan or tra_loi.invalid_tool_calls:
        loi = ["phải gọi ket_luan đúng một lần, với tham số JSON hợp lệ"]
    else:
        loi = ["không gọi ket_luan"]

    noi_dung = "Chưa hợp lệ, hãy gọi lại ket_luan:\n" + "\n".join(f"- {muc}" for muc in loi)
    tra_lai: list[AnyMessage] = [
        ToolMessage(noi_dung, tool_call_id=goi["id"] or "")
        for goi in (*tra_loi.tool_calls, *tra_loi.invalid_tool_calls)
    ]
    return None, loi, tra_lai or [HumanMessage(NHAC_DUNG_CONG_CU)]
