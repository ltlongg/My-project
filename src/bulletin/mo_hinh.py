"""Các thực thể được lưu trong Postgres. Tên theo thuật ngữ ở CONTEXT.md."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

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
    xuat_hien_luc: Mapped[datetime] = mapped_column(index=True)
    thu_thap_luc: Mapped[datetime]
    # Chưa có nghĩa là chưa ai cần đọc Bài gốc này, hoặc không lấy được nội dung.
    toan_van: Mapped[str | None]

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
    # Phiên bản Hướng dẫn mà Biên tập dùng ở Kỳ này.
    huong_dan_bien_tap_id: Mapped[int | None] = mapped_column(ForeignKey("huong_dan.id"))

    chuyen_muc: Mapped[ChuyenMuc] = relationship()
    huong_dan_bien_tap: Mapped[HuongDan | None] = relationship()
    ban_tin: Mapped[BanTin | None] = relationship(back_populates="ky")


class BanTin(CoSo):
    __tablename__ = "ban_tin"

    id: Mapped[int] = mapped_column(primary_key=True)
    ky_id: Mapped[int] = mapped_column(ForeignKey("ky.id"), unique=True)

    ky: Mapped[Ky] = relationship(back_populates="ban_tin")
    tin: Mapped[list[Tin]] = relationship(back_populates="ban_tin", order_by="Tin.thu_tu")


class Tin(CoSo):
    __tablename__ = "tin"
    __table_args__ = (UniqueConstraint("ban_tin_id", "thu_tu"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ban_tin_id: Mapped[int] = mapped_column(ForeignKey("ban_tin.id"))
    thu_tu: Mapped[int]
    tieu_de: Mapped[str]
    tom_tat: Mapped[str]
    # Vì sao Biên tập chọn Tin này.
    li_do: Mapped[str]
    bai_goc_chinh_id: Mapped[int] = mapped_column(ForeignKey("bai_goc.id"))

    ban_tin: Mapped[BanTin] = relationship(back_populates="tin")
    bai_goc_chinh: Mapped[BaiGoc] = relationship()
