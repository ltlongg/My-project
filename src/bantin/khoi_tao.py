"""Dữ liệu khởi tạo: đủ để chạy Kỳ đầu tiên khi chưa có trang quản lí."""

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from bantin.mo_hinh import ChuyenMuc, KenhDang, LoaiKenhDang, LoaiNguon, Nguon

MA_CONG_NGHE = "cong-nghe"
RSS_KHOI_DAU = ("VnExpress Khoa học công nghệ", "https://vnexpress.net/rss/khoa-hoc-cong-nghe.rss")


def khoi_tao(mo_phien: sessionmaker[Session], ma_tro_chuyen_telegram: str | None) -> None:
    """Tạo Chuyên mục công nghệ với một Nguồn RSS và, nếu đã biết mã nhóm, một Kênh đăng Telegram.

    Chạy lại không tạo trùng; chỉ bổ sung thứ còn thiếu.
    """
    with mo_phien.begin() as phien:
        chuyen_muc = phien.scalar(select(ChuyenMuc).where(ChuyenMuc.ma == MA_CONG_NGHE))
        if chuyen_muc is None:
            chuyen_muc = ChuyenMuc(ma=MA_CONG_NGHE, ten="Công nghệ", so_tin_toi_da=7)
            phien.add(chuyen_muc)

        ten, dia_chi = RSS_KHOI_DAU
        nguon = phien.scalar(
            select(Nguon).where(Nguon.loai == LoaiNguon.RSS, Nguon.dia_chi == dia_chi)
        ) or Nguon(loai=LoaiNguon.RSS, ten=ten, dia_chi=dia_chi)
        if nguon not in chuyen_muc.nguon:
            chuyen_muc.nguon.append(nguon)

        if ma_tro_chuyen_telegram:
            kenh = phien.scalar(
                select(KenhDang).where(
                    KenhDang.loai == LoaiKenhDang.TELEGRAM,
                    KenhDang.dia_chi == ma_tro_chuyen_telegram,
                )
            ) or KenhDang(
                loai=LoaiKenhDang.TELEGRAM, ten="Nhóm Telegram thử", dia_chi=ma_tro_chuyen_telegram
            )
            if kenh not in chuyen_muc.kenh_dang:
                chuyen_muc.kenh_dang.append(kenh)
