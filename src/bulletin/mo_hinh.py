"""Các thực thể được lưu trong Postgres. Tên theo thuật ngữ ở CONTEXT.md."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import Column, DateTime, Enum, ForeignKey, Index, Table, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class LoaiNguon(StrEnum):
    RSS = "rss"


class LoaiKenhDang(StrEnum):
    TELEGRAM = "telegram"


class KetQuaKy(StrEnum):
    DA_PHAT = "da_phat"
    KHONG_PHAT = "khong_phat"
    HONG = "hong"


class VaiTro(StrEnum):
    """Agent mà một Hướng dẫn chỉ dẫn."""

    BIEN_TAP = "bien_tap"
    KIEM_CHUNG = "kiem_chung"


def _cot_enum(loai: type[StrEnum]) -> Enum:
    # Lưu dạng chữ thay vì kiểu enum của Postgres để thêm giá trị không cần migration riêng.
    return Enum(loai, native_enum=False, length=32, values_callable=lambda e: [m.value for m in e])


class CoSo(DeclarativeBase):
    type_annotation_map = {datetime: DateTime(timezone=True)}


chuyen_muc_nguon = Table(
    "chuyen_muc_nguon",
    CoSo.metadata,
    Column("chuyen_muc_id", ForeignKey("chuyen_muc.id", ondelete="CASCADE"), primary_key=True),
    Column("nguon_id", ForeignKey("nguon.id", ondelete="CASCADE"), primary_key=True),
)

chuyen_muc_kenh_dang = Table(
    "chuyen_muc_kenh_dang",
    CoSo.metadata,
    Column("chuyen_muc_id", ForeignKey("chuyen_muc.id", ondelete="CASCADE"), primary_key=True),
    Column("kenh_dang_id", ForeignKey("kenh_dang.id", ondelete="CASCADE"), primary_key=True),
)

# Một Bài gốc chỉ lưu một lần; bảng này ghi nó đã được thấy ở những Nguồn nào.
bai_goc_nguon = Table(
    "bai_goc_nguon",
    CoSo.metadata,
    Column("bai_goc_id", ForeignKey("bai_goc.id", ondelete="CASCADE"), primary_key=True),
    Column("nguon_id", ForeignKey("nguon.id", ondelete="CASCADE"), primary_key=True),
)

# Các Bài gốc cùng nói về một sự kiện mà Gom Tin đã gom thành một ứng viên Tin.
ung_vien_bai_goc = Table(
    "ung_vien_bai_goc",
    CoSo.metadata,
    Column("ung_vien_id", ForeignKey("ung_vien.id", ondelete="CASCADE"), primary_key=True),
    Column("bai_goc_id", ForeignKey("bai_goc.id", ondelete="CASCADE"), primary_key=True),
)


class ChuyenMuc(CoSo):
    __tablename__ = "chuyen_muc"

    id: Mapped[int] = mapped_column(primary_key=True)
    ma: Mapped[str] = mapped_column(unique=True)
    ten: Mapped[str]
    so_tin_toi_da: Mapped[int]

    nguon: Mapped[list[Nguon]] = relationship(secondary=chuyen_muc_nguon, order_by="Nguon.id")
    kenh_dang: Mapped[list[KenhDang]] = relationship(
        secondary=chuyen_muc_kenh_dang, order_by="KenhDang.id"
    )


class Nguon(CoSo):
    __tablename__ = "nguon"
    __table_args__ = (UniqueConstraint("loai", "dia_chi"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    loai: Mapped[LoaiNguon] = mapped_column(_cot_enum(LoaiNguon))
    ten: Mapped[str]
    dia_chi: Mapped[str]
    lay_gan_nhat_luc: Mapped[datetime | None]
    loi_gan_nhat: Mapped[str | None]


class KenhDang(CoSo):
    __tablename__ = "kenh_dang"
    __table_args__ = (UniqueConstraint("loai", "dia_chi"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    loai: Mapped[LoaiKenhDang] = mapped_column(_cot_enum(LoaiKenhDang))
    ten: Mapped[str]
    dia_chi: Mapped[str]


class BaiGoc(CoSo):
    __tablename__ = "bai_goc"

    id: Mapped[int] = mapped_column(primary_key=True)
    dia_chi_chuan_hoa: Mapped[str] = mapped_column(unique=True)
    dia_chi: Mapped[str]
    tieu_de: Mapped[str]
    # Đoạn mô tả ngắn Nguồn kèm theo; không có thì để trống.
    mo_ta: Mapped[str | None]
    xuat_hien_luc: Mapped[datetime] = mapped_column(index=True)
    thu_thap_luc: Mapped[datetime]
    # Chưa có nghĩa là chưa ai cần đọc Bài gốc này, hoặc không lấy được nội dung.
    toan_van: Mapped[str | None]
    # Vector nhúng dùng để gom Tin, cùng tên model đã tạo ra nó; chưa nhúng thì để trống. Không ghi
    # số chiều để đổi được sang model khác mà không cần migration.
    vector_nhung: Mapped[list[float] | None] = mapped_column(VECTOR())
    mo_hinh_nhung: Mapped[str | None]

    nguon: Mapped[list[Nguon]] = relationship(secondary=bai_goc_nguon, order_by="Nguon.id")


class HuongDan(CoSo):
    __tablename__ = "huong_dan"
    __table_args__ = (
        UniqueConstraint(
            "vai_tro", "chuyen_muc_id", "phien_ban", postgresql_nulls_not_distinct=True
        ),
        # Mỗi Agent, mỗi Chuyên mục chỉ có một phiên bản đang có hiệu lực.
        Index(
            "uq_huong_dan_co_hieu_luc",
            "vai_tro",
            "chuyen_muc_id",
            unique=True,
            postgresql_where="co_hieu_luc",
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    vai_tro: Mapped[VaiTro] = mapped_column(_cot_enum(VaiTro))
    # Để trống là Hướng dẫn chung cho mọi Chuyên mục.
    chuyen_muc_id: Mapped[int | None] = mapped_column(
        ForeignKey("chuyen_muc.id", ondelete="CASCADE")
    )
    phien_ban: Mapped[int]
    noi_dung: Mapped[str]
    co_hieu_luc: Mapped[bool]
    tao_luc: Mapped[datetime] = mapped_column(server_default=func.now())


class Ky(CoSo):
    __tablename__ = "ky"

    id: Mapped[int] = mapped_column(primary_key=True)
    chuyen_muc_id: Mapped[int] = mapped_column(ForeignKey("chuyen_muc.id"), index=True)
    thoi_diem: Mapped[datetime]
    # Chưa có kết quả nghĩa là Kỳ đang chạy hoặc bị gián đoạn giữa chừng.
    ket_qua: Mapped[KetQuaKy | None] = mapped_column(_cot_enum(KetQuaKy))
    li_do: Mapped[str | None]
    # Phiên bản Hướng dẫn mà Biên tập và Kiểm chứng dùng ở Kỳ này.
    huong_dan_bien_tap_id: Mapped[int | None] = mapped_column(ForeignKey("huong_dan.id"))
    huong_dan_kiem_chung_id: Mapped[int | None] = mapped_column(ForeignKey("huong_dan.id"))

    chuyen_muc: Mapped[ChuyenMuc] = relationship()
    huong_dan_bien_tap: Mapped[HuongDan | None] = relationship(foreign_keys=[huong_dan_bien_tap_id])
    huong_dan_kiem_chung: Mapped[HuongDan | None] = relationship(
        foreign_keys=[huong_dan_kiem_chung_id]
    )
    # Các ứng viên Tin sau Gom Tin; Biên tập chọn Tin trong số này.
    ung_vien: Mapped[list[UngVien]] = relationship(order_by="UngVien.thu_tu")
    ban_tin: Mapped[BanTin | None] = relationship(back_populates="ky")


class BanTin(CoSo):
    __tablename__ = "ban_tin"

    id: Mapped[int] = mapped_column(primary_key=True)
    ky_id: Mapped[int] = mapped_column(ForeignKey("ky.id"), unique=True)

    ky: Mapped[Ky] = relationship(back_populates="ban_tin")
    # Mọi Tin Biên tập nộp, kể cả Tin bị bỏ vì không qua Kiểm chứng.
    tin: Mapped[list[Tin]] = relationship(back_populates="ban_tin", order_by="Tin.thu_tu")


class UngVien(CoSo):
    """Một ứng viên Tin của Kỳ: các Bài gốc Gom Tin cho là cùng nói về một sự kiện."""

    __tablename__ = "ung_vien"
    __table_args__ = (UniqueConstraint("ky_id", "thu_tu"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ky_id: Mapped[int] = mapped_column(ForeignKey("ky.id", ondelete="CASCADE"))
    # Thứ tự Biên tập thấy các ứng viên, từ 1.
    thu_tu: Mapped[int]
    # Tin đã phát của cùng Chuyên mục mà ứng viên này giống; có thì ứng viên chỉ được phát như một
    # Tin "Cập nhật" của Tin đó.
    tin_da_phat_id: Mapped[int | None] = mapped_column(ForeignKey("tin.id"))

    bai_goc: Mapped[list[BaiGoc]] = relationship(
        secondary=ung_vien_bai_goc, order_by=[BaiGoc.xuat_hien_luc, BaiGoc.id]
    )
    tin_da_phat: Mapped[Tin | None] = relationship(foreign_keys=[tin_da_phat_id])


class Tin(CoSo):
    __tablename__ = "tin"
    __table_args__ = (UniqueConstraint("ban_tin_id", "thu_tu"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ban_tin_id: Mapped[int] = mapped_column(ForeignKey("ban_tin.id"))
    thu_tu: Mapped[int]
    # Bản viết cuối cùng; các bản trước nằm ở các lượt Kiểm chứng.
    tieu_de: Mapped[str]
    tom_tat: Mapped[str]
    # Vì sao Biên tập chọn Tin này.
    li_do: Mapped[str]
    # Ứng viên Tin được gom từ đó; các Bài gốc của nó là các Bài gốc của Tin.
    ung_vien_id: Mapped[int] = mapped_column(ForeignKey("ung_vien.id"))
    # Một trong các Bài gốc của Tin, do Biên tập chọn: Tin dẫn link tới nó.
    bai_goc_chinh_id: Mapped[int] = mapped_column(ForeignKey("bai_goc.id"))
    # Có giá trị là Tin bị bỏ khỏi Bản tin vì không qua Kiểm chứng, và đây là lí do.
    li_do_bo: Mapped[str | None]

    ban_tin: Mapped[BanTin] = relationship(back_populates="tin")
    ung_vien: Mapped[UngVien] = relationship(foreign_keys=[ung_vien_id])
    bai_goc_chinh: Mapped[BaiGoc] = relationship()
    luot_kiem_chung: Mapped[list[LuotKiemChung]] = relationship(
        back_populates="tin", order_by="LuotKiemChung.lan", cascade="all, delete-orphan"
    )

    @property
    def cap_nhat_tin(self) -> Tin | None:
        """Tin đã phát mà Tin này là bản "Cập nhật" của nó; None là Tin mới."""
        return self.ung_vien.tin_da_phat


class LuotKiemChung(CoSo):
    """Một lần Kiểm chứng xét một bản viết của Tin; bản sau một lượt không đạt là bản viết lại."""

    __tablename__ = "luot_kiem_chung"
    __table_args__ = (UniqueConstraint("tin_id", "lan"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tin_id: Mapped[int] = mapped_column(ForeignKey("tin.id", ondelete="CASCADE"))
    # Lượt thứ mấy, từ 1; lượt 1 xét bản đầu tiên.
    lan: Mapped[int]
    tieu_de: Mapped[str]
    tom_tat: Mapped[str]
    dat: Mapped[bool]
    li_do: Mapped[str]

    tin: Mapped[Tin] = relationship(back_populates="luot_kiem_chung")
