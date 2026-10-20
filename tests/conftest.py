"""Khuôn test tại điểm "Chạy Kỳ": Nguồn giả, Kênh đăng giả, LLM theo kịch bản, đồng hồ giả,
Postgres thật.

Đồng hồ giả là tham số `thoi_diem` của `ChayKy.chay`: test tự nói "bây giờ" là lúc nào.
"""

import json
import os
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from itertools import count
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.postgres import PostgresSaver
from pydantic import Field
from sqlalchemy import Engine, create_engine, func, make_url, select, text, update
from sqlalchemy.orm import Session, sessionmaker

from bulletin.agents.bien_tap import BienTap
from bulletin.chay_ky import ChayKy
from bulletin.collectors import BaiGocMoi
from bulletin.csdl import BANG_TRANG_THAI, mo_kho_trang_thai, nang_cap, tao_engine, tao_mo_phien
from bulletin.dia_chi import chuan_hoa
from bulletin.mo_hinh import (
    BaiGoc,
    ChuyenMuc,
    CoSo,
    HuongDan,
    KenhDang,
    LoaiKenhDang,
    LoaiNguon,
    Nguon,
    Tin,
    VaiTro,
)
from bulletin.publishers import NoiDungBanTin
from bulletin.search import KetQuaTimKiem

URL_MAC_DINH = "postgresql+psycopg://bantin:bantin@127.0.0.1:54320/bantin_test"
GIO_VIET_NAM = ZoneInfo("Asia/Ho_Chi_Minh")


def luc(ngay: int, gio: int, phut: int = 0) -> datetime:
    """Một thời điểm trong tháng 10/2026, giờ Việt Nam."""
    return datetime(2026, 10, ngay, gio, phut, tzinfo=GIO_VIET_NAM)


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    url = make_url(os.environ.get("TEST_DATABASE_URL", URL_MAC_DINH))
    ten_csdl = url.database or ""
    # Lược đồ bị xoá sạch trước mỗi lần chạy, nên không bao giờ trỏ vào cơ sở dữ liệu thật.
    assert ten_csdl.endswith("_test"), f"Cơ sở dữ liệu test phải có tên kết thúc bằng _test: {url}"

    quan_tri = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with quan_tri.connect() as ket_noi:
        da_co = ket_noi.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :ten"), {"ten": ten_csdl}
        )
        if not da_co:
            ket_noi.execute(text(f'CREATE DATABASE "{ten_csdl}"'))
    quan_tri.dispose()

    engine = tao_engine(url.render_as_string(hide_password=False))
    with engine.begin() as ket_noi:
        ket_noi.execute(text("DROP SCHEMA public CASCADE"))
        ket_noi.execute(text("CREATE SCHEMA public"))
    nang_cap(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def kho_trang_thai(engine: Engine) -> Iterator[PostgresSaver]:
    with mo_kho_trang_thai(engine) as kho:
        yield kho


@pytest.fixture
def mo_phien(engine: Engine) -> sessionmaker[Session]:
    """Hàm mở phiên làm việc trên một cơ sở dữ liệu đã dọn sạch."""
    bang = ", ".join(f'"{ten}"' for ten in (*CoSo.metadata.tables, *BANG_TRANG_THAI))
    with engine.begin() as ket_noi:
        ket_noi.execute(text(f"TRUNCATE {bang} RESTART IDENTITY CASCADE"))
    return tao_mo_phien(engine)


class NguonGia:
    """Bộ thu thập giả: trả về đúng những Bài gốc test đã đặt cho từng địa chỉ Nguồn."""

    def __init__(self) -> None:
        self._bai_goc: dict[str, Sequence[BaiGocMoi]] = {}
        self._loi: dict[str, Exception] = {}

    def co(self, dia_chi: str, *bai_goc: BaiGocMoi) -> None:
        self._bai_goc[dia_chi] = bai_goc
        self._loi.pop(dia_chi, None)

    def hong(self, dia_chi: str, loi: Exception) -> None:
        self._loi[dia_chi] = loi

    def thu_thap(self, dia_chi: str, tu_moc: datetime) -> Sequence[BaiGocMoi]:
        if dia_chi in self._loi:
            raise self._loi[dia_chi]
        return self._bai_goc.get(dia_chi, ())


class KenhDangGia:
    """Bộ phát giả: ghi lại mọi Bản tin tới từng địa chỉ Kênh đăng."""

    def __init__(self) -> None:
        self.da_nhan: list[tuple[str, NoiDungBanTin]] = []
        self._loi: dict[str, Exception] = {}

    def hong(self, dia_chi: str, loi: Exception) -> None:
        self._loi[dia_chi] = loi

    def sua(self, dia_chi: str) -> None:
        del self._loi[dia_chi]

    def phat(self, dia_chi: str, ban_tin: NoiDungBanTin) -> None:
        if dia_chi in self._loi:
            raise self._loi[dia_chi]
        self.da_nhan.append((dia_chi, ban_tin))


class NoiDungGia:
    """Bộ lấy nội dung giả: mọi Bài gốc đều có toàn văn, trừ những bài test đặt là hỏng."""

    def __init__(self) -> None:
        self.da_lay: list[str] = []
        self._toan_van: dict[str, str] = {}
        self._loi: dict[str, Exception] = {}

    def co(self, dia_chi: str, toan_van: str) -> None:
        self._toan_van[dia_chi] = toan_van

    def hong(self, dia_chi: str, loi: Exception) -> None:
        self._loi[dia_chi] = loi

    def lay(self, dia_chi: str) -> str:
        self.da_lay.append(dia_chi)
        if dia_chi in self._loi:
            raise self._loi[dia_chi]
        return self._toan_van.get(dia_chi, f"Toàn văn của {dia_chi}.")


class TimKiemGia:
    """Bộ tìm kiếm giả: ghi lại truy vấn và trả về kết quả test đã đặt."""

    def __init__(self) -> None:
        self.da_tim: list[str] = []
        self.ket_qua: Sequence[KetQuaTimKiem] = ()

    def tim(self, truy_van: str) -> Sequence[KetQuaTimKiem]:
        self.da_tim.append(truy_van)
        return self.ket_qua


@dataclass(frozen=True)
class UngVienThay:
    """Một ứng viên đúng như LLM thấy trong đề bài."""

    ma: int
    tieu_de: str
    dia_chi: str


# Một bước của kịch bản: nhìn các ứng viên LLM được giao rồi trả lời.
Buoc = Callable[[Sequence[UngVienThay]], AIMessage]
_ma_goi = count(1)


def _goi(ten: str, tham_so: dict[str, Any]) -> dict[str, Any]:
    return {"name": ten, "args": tham_so, "id": f"goi-{next(_ma_goi)}", "type": "tool_call"}


def _ma(ung_vien: Sequence[UngVienThay], bai_goc: str | int) -> int:
    """Mã của ứng viên có địa chỉ `bai_goc`; số thì giữ nguyên, để test nộp cả mã không có."""
    if isinstance(bai_goc, int):
        return bai_goc
    return next(uv.ma for uv in ung_vien if uv.dia_chi == bai_goc)


def doc(*dia_chi: str) -> Buoc:
    """LLM gọi công cụ đọc toàn văn cho từng Bài gốc."""
    return lambda ung_vien: AIMessage(
        "", tool_calls=[_goi("doc_bai_goc", {"ma": _ma(ung_vien, dc)}) for dc in dia_chi]
    )


def tim(truy_van: str) -> Buoc:
    """LLM gọi công cụ tìm kiếm web."""
    return lambda ung_vien: AIMessage("", tool_calls=[_goi("tim_kiem_web", {"truy_van": truy_van})])


def noi(van_ban: str) -> Buoc:
    """LLM trả lời bằng chữ, không gọi công cụ nào."""
    return lambda ung_vien: AIMessage(van_ban)


@dataclass(frozen=True)
class TinViet:
    """Một Tin LLM nộp; `bai_goc` là địa chỉ của ứng viên, hoặc một mã tuỳ ý."""

    bai_goc: str | int
    tieu_de: str = "Tiêu đề do Biên tập viết"
    tom_tat: str = "Tóm tắt bằng tiếng Việt do Biên tập viết từ toàn văn."
    li_do: str = "Đáng đọc."


def nop(*tin: TinViet) -> Buoc:
    """LLM nộp Bản tin gồm các Tin đã viết."""
    return lambda ung_vien: AIMessage(
        "",
        tool_calls=[
            _goi(
                "nop_ban_tin",
                {
                    "tin": [
                        {
                            "ma_bai_goc": _ma(ung_vien, t.bai_goc),
                            "tieu_de": t.tieu_de,
                            "tom_tat": t.tom_tat,
                            "li_do": t.li_do,
                        }
                        for t in tin
                    ]
                },
            )
        ],
    )


class LLMTheoKichBan(BaseChatModel):
    """LLM giả của Biên tập: trả lời lần lượt theo kịch bản test đặt.

    Không đặt kịch bản thì nó biên tập máy móc: đọc mọi ứng viên rồi nộp tất cả theo thứ tự được
    giao, giữ nguyên tiêu đề gốc. Một bước là ngoại lệ thì lời gọi đó ném ngoại lệ ấy.
    """

    kich_ban: list[Buoc | BaseException] = Field(default_factory=list)
    # Bước lặp lại mãi khi kịch bản đã hết, thay cho cách biên tập máy móc.
    lap_lai: Buoc | None = None
    # Các tin nhắn LLM nhận được ở từng lời gọi.
    da_nhan: list[list[BaseMessage]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "theo-kich-ban"

    def bind_tools(self, tools: Any, **tuy_chon: Any) -> "LLMTheoKichBan":
        return self

    def se(self, *buoc: Buoc | BaseException) -> None:
        """Đặt các bước tiếp theo của kịch bản."""
        self.kich_ban = list(buoc)

    def van_ban_da_nhan(self, lan_goi: int = -1) -> str:
        """Mọi thứ LLM đọc được ở một lời gọi, nối thành một văn bản."""
        return "\n".join(str(tin_nhan.content) for tin_nhan in self.da_nhan[lan_goi])

    def _generate(
        self, messages: list[BaseMessage], stop: Any = None, run_manager: Any = None, **_: Any
    ) -> ChatResult:
        self.da_nhan.append(list(messages))
        buoc = self.kich_ban.pop(0) if self.kich_ban else self.lap_lai
        if isinstance(buoc, BaseException):
            raise buoc
        de_bai = next(str(tn.content) for tn in messages if isinstance(tn, HumanMessage))
        ung_vien = [
            UngVienThay(muc["ma"], muc["tieu_de"], muc["dia_chi"])
            for muc in map(json.loads, (d for d in de_bai.splitlines() if d.startswith("{")))
        ]
        if buoc is None:
            da_doc = any(isinstance(tn, ToolMessage) for tn in messages)
            buoc = _nop_tat_ca if da_doc else _doc_tat_ca
        return ChatResult(generations=[ChatGeneration(message=buoc(ung_vien))])


def _doc_tat_ca(ung_vien: Sequence[UngVienThay]) -> AIMessage:
    return doc(*(uv.dia_chi for uv in ung_vien))(ung_vien)


def _nop_tat_ca(ung_vien: Sequence[UngVienThay]) -> AIMessage:
    return nop(*(TinViet(uv.dia_chi, uv.tieu_de, f"Tóm tắt của {uv.tieu_de}.") for uv in ung_vien))(
        ung_vien
    )


HUONG_DAN_MAC_DINH = "Chọn Tin đáng đọc nhất."


@dataclass
class TheGioi:
    """Mọi thứ một test "Chạy Kỳ" cần: thiết lập, các đầu giả và lối vào `chay_ky`."""

    mo_phien: sessionmaker[Session]
    kho_trang_thai: PostgresSaver
    nguon: NguonGia = field(default_factory=NguonGia)
    kenh_dang: KenhDangGia = field(default_factory=KenhDangGia)
    noi_dung: NoiDungGia = field(default_factory=NoiDungGia)
    tim_kiem: TimKiemGia = field(default_factory=TimKiemGia)
    llm: LLMTheoKichBan = field(default_factory=LLMTheoKichBan)
    chay_ky: ChayKy = field(init=False)

    def __post_init__(self) -> None:
        self.chay_ky = ChayKy(
            self.mo_phien,
            bo_thu_thap={LoaiNguon.RSS: self.nguon},
            bo_phat={LoaiKenhDang.TELEGRAM: self.kenh_dang},
            lay_noi_dung=self.noi_dung,
            bien_tap=BienTap(self.llm, self.tim_kiem, self.kho_trang_thai),
        )

    def them_chuyen_muc(
        self,
        ma: str,
        *,
        ten: str,
        nguon: Sequence[str],
        kenh_dang: Sequence[str],
        so_tin_toi_da: int = 7,
        huong_dan: str | None = HUONG_DAN_MAC_DINH,
    ) -> None:
        """Khai một Chuyên mục; Nguồn và Kênh đăng trùng địa chỉ được dùng chung.

        `huong_dan` là Hướng dẫn cho Biên tập, phiên bản 1; None là chưa có Hướng dẫn.
        """
        with self.mo_phien.begin() as phien:
            chuyen_muc = ChuyenMuc(ma=ma, ten=ten, so_tin_toi_da=so_tin_toi_da)
            for dia_chi in nguon:
                da_co = phien.scalar(select(Nguon).where(Nguon.dia_chi == dia_chi))
                chuyen_muc.nguon.append(
                    da_co or Nguon(loai=LoaiNguon.RSS, ten=dia_chi, dia_chi=dia_chi)
                )
            for dia_chi in kenh_dang:
                kenh = phien.scalar(select(KenhDang).where(KenhDang.dia_chi == dia_chi))
                chuyen_muc.kenh_dang.append(
                    kenh or KenhDang(loai=LoaiKenhDang.TELEGRAM, ten=dia_chi, dia_chi=dia_chi)
                )
            phien.add(chuyen_muc)
        if huong_dan is not None:
            self.doi_huong_dan(ma, huong_dan)

    def doi_huong_dan(self, ma_chuyen_muc: str, noi_dung: str) -> int:
        """Đặt một phiên bản Hướng dẫn mới của Biên tập có hiệu lực; trả về số phiên bản."""
        with self.mo_phien.begin() as phien:
            chuyen_muc_id = phien.scalars(
                select(ChuyenMuc.id).where(ChuyenMuc.ma == ma_chuyen_muc)
            ).one()
            cua_chuyen_muc = (
                HuongDan.vai_tro == VaiTro.BIEN_TAP,
                HuongDan.chuyen_muc_id == chuyen_muc_id,
            )
            phien_ban = (
                phien.scalar(select(func.max(HuongDan.phien_ban)).where(*cua_chuyen_muc)) or 0
            ) + 1
            phien.execute(update(HuongDan).where(*cua_chuyen_muc).values(co_hieu_luc=False))
            phien.add(
                HuongDan(
                    vai_tro=VaiTro.BIEN_TAP,
                    chuyen_muc_id=chuyen_muc_id,
                    phien_ban=phien_ban,
                    noi_dung=noi_dung,
                    co_hieu_luc=True,
                )
            )
            return phien_ban

    def tinh_trang_nguon(self) -> dict[str, str | None]:
        """Lỗi gần nhất được lưu của từng Nguồn, theo địa chỉ; không lỗi là None."""
        with self.mo_phien() as phien:
            return {nguon.dia_chi: nguon.loi_gan_nhat for nguon in phien.scalars(select(Nguon))}

    def so_bai_goc_da_luu(self) -> int:
        with self.mo_phien() as phien:
            return phien.scalar(select(func.count()).select_from(BaiGoc)) or 0

    def toan_van_da_luu(self, dia_chi: str) -> str | None:
        """Toàn văn được lưu của Bài gốc ở `dia_chi`; chưa có là None."""
        with self.mo_phien() as phien:
            return phien.scalars(
                select(BaiGoc.toan_van).where(BaiGoc.dia_chi_chuan_hoa == chuan_hoa(dia_chi))
            ).one()

    def tin_da_luu(self) -> list[tuple[str, str, str, str]]:
        """Mọi Tin đã lưu theo thứ tự: tiêu đề, tóm tắt, lí do chọn, địa chỉ Bài gốc chính."""
        with self.mo_phien() as phien:
            return [
                (tin.tieu_de, tin.tom_tat, tin.li_do, tin.bai_goc_chinh.dia_chi)
                for tin in phien.scalars(select(Tin).order_by(Tin.ban_tin_id, Tin.thu_tu))
            ]


@pytest.fixture
def the_gioi(mo_phien: sessionmaker[Session], kho_trang_thai: PostgresSaver) -> TheGioi:
    return TheGioi(mo_phien, kho_trang_thai)
