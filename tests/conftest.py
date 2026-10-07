"""Khuôn test tại điểm "Chạy Kỳ": Nguồn giả, Kênh đăng giả, đồng hồ giả, Postgres thật.

Đồng hồ giả là tham số `thoi_diem` của `ChayKy.chay`: test tự nói "bây giờ" là lúc nào.
"""

import os
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import Engine, create_engine, func, make_url, select, text
from sqlalchemy.orm import Session, sessionmaker

from bulletin.chay_ky import ChayKy
from bulletin.collectors import BaiGocMoi
from bulletin.csdl import nang_cap, tao_engine, tao_mo_phien
from bulletin.mo_hinh import BaiGoc, ChuyenMuc, CoSo, KenhDang, LoaiKenhDang, LoaiNguon, Nguon
from bulletin.publishers import NoiDungBanTin

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


@pytest.fixture
def mo_phien(engine: Engine) -> sessionmaker[Session]:
    """Hàm mở phiên làm việc trên một cơ sở dữ liệu đã dọn sạch."""
    bang = ", ".join(f'"{b.name}"' for b in CoSo.metadata.sorted_tables)
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


@dataclass
class TheGioi:
    """Mọi thứ một test "Chạy Kỳ" cần: thiết lập, hai đầu giả và lối vào `chay_ky`."""

    mo_phien: sessionmaker[Session]
    nguon: NguonGia = field(default_factory=NguonGia)
    kenh_dang: KenhDangGia = field(default_factory=KenhDangGia)
    chay_ky: ChayKy = field(init=False)

    def __post_init__(self) -> None:
        self.chay_ky = ChayKy(
            self.mo_phien,
            bo_thu_thap={LoaiNguon.RSS: self.nguon},
            bo_phat={LoaiKenhDang.TELEGRAM: self.kenh_dang},
        )

    def them_chuyen_muc(
        self,
        ma: str,
        *,
        ten: str,
        nguon: Sequence[str],
        kenh_dang: Sequence[str],
        so_tin_toi_da: int = 7,
    ) -> None:
        """Khai một Chuyên mục; Nguồn và Kênh đăng trùng địa chỉ được dùng chung."""
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

    def tinh_trang_nguon(self) -> dict[str, str | None]:
        """Lỗi gần nhất được lưu của từng Nguồn, theo địa chỉ; không lỗi là None."""
        with self.mo_phien() as phien:
            return {nguon.dia_chi: nguon.loi_gan_nhat for nguon in phien.scalars(select(Nguon))}

    def so_bai_goc_da_luu(self) -> int:
        with self.mo_phien() as phien:
            return phien.scalar(select(func.count()).select_from(BaiGoc)) or 0


@pytest.fixture
def the_gioi(mo_phien: sessionmaker[Session]) -> TheGioi:
    return TheGioi(mo_phien)
