"""Chạy Kỳ: lối vào duy nhất để làm một Bản tin cho một Chuyên mục tại một thời điểm."""

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, literal, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from bulletin.collectors import BaiGocMoi, BoThuThap
from bulletin.dia_chi import chuan_hoa
from bulletin.mo_hinh import (
    BaiGoc,
    BanTin,
    ChuyenMuc,
    KenhDang,
    KetQuaKy,
    Ky,
    LoaiKenhDang,
    LoaiNguon,
    Nguon,
    Tin,
    bai_goc_nguon,
    chuyen_muc_nguon,
)
from bulletin.publishers import BoPhat, NoiDungBanTin, NoiDungTin

log = logging.getLogger(__name__)

# Kỳ đầu tiên của một Chuyên mục chưa có Bản tin trước để làm mốc.
KHOANG_LAN_DAU = timedelta(hours=24)


@dataclass(frozen=True)
class KyDaChay:
    """Một Kỳ đúng như đã lưu."""

    thoi_diem: datetime
    # Chưa có kết quả nghĩa là Kỳ đang chạy hoặc bị gián đoạn giữa chừng.
    ket_qua: KetQuaKy | None
    li_do: str | None
    ban_tin: NoiDungBanTin | None


class ChayKy:
    def __init__(
        self,
        mo_phien: sessionmaker[Session],
        bo_thu_thap: Mapping[LoaiNguon, BoThuThap],
        bo_phat: Mapping[LoaiKenhDang, BoPhat],
    ) -> None:
        self._mo_phien = mo_phien
        self._bo_thu_thap = bo_thu_thap
        self._bo_phat = bo_phat

    def chay(self, ma_chuyen_muc: str, thoi_diem: datetime) -> KyDaChay:
        """Chạy một Kỳ cho Chuyên mục `ma_chuyen_muc` tại `thoi_diem`."""
        if thoi_diem.tzinfo is None:
            raise ValueError("thoi_diem phải có múi giờ")
        with self._mo_phien() as phien:
            chuyen_muc = _chuyen_muc(phien, ma_chuyen_muc)
            moc = _moc(phien, chuyen_muc, thoi_diem)
            ky = Ky(chuyen_muc=chuyen_muc, thoi_diem=thoi_diem)
            phien.add(ky)
            # Kỳ được lưu trước khi làm gì khác, để lỗi nào cũng để lại một Kỳ có kết quả.
            phien.commit()
            try:
                ky.ket_qua, ky.li_do = self._lam_ban_tin(phien, ky, moc)
            except Exception as loi:
                log.exception("Kỳ của Chuyên mục %s gặp lỗi không lường trước", ma_chuyen_muc)
                phien.rollback()
                ky.ket_qua = KetQuaKy.HONG
                ky.li_do = f"Lỗi không lường trước: {str(loi).splitlines()[0]}"
            phien.commit()
            return _da_chay(ky)

    def _lam_ban_tin(self, phien: Session, ky: Ky, moc: datetime) -> tuple[KetQuaKy, str | None]:
        """Thu thập, dựng Bản tin và phát; trả về kết quả của Kỳ kèm lí do."""
        chuyen_muc = ky.chuyen_muc
        if not chuyen_muc.nguon:
            return KetQuaKy.HONG, "Chuyên mục chưa có Nguồn nào"
        lay_duoc = [self._thu_thap(phien, nguon, moc, ky.thoi_diem) for nguon in chuyen_muc.nguon]
        phien.commit()
        if not any(lay_duoc):
            # Hỏng chứ không phải "không phát": thử lại sau có thể lấy được.
            return KetQuaKy.HONG, "Không thu thập được Nguồn nào"

        bai_goc = _bai_goc_trong_ky(phien, chuyen_muc, moc, ky.thoi_diem)
        if not bai_goc:
            return KetQuaKy.KHONG_PHAT, "Không có Bài gốc mới"
        ky.ban_tin = BanTin(
            tin=[
                Tin(thu_tu=thu_tu, tieu_de=bai.tieu_de, bai_goc_chinh=bai)
                for thu_tu, bai in enumerate(bai_goc, start=1)
            ]
        )
        # Bản tin được lưu trước khi phát, để Kỳ hỏng vẫn cho thấy nó định gửi gì.
        phien.commit()

        if not chuyen_muc.kenh_dang:
            return KetQuaKy.HONG, "Chuyên mục chưa có Kênh đăng nào"
        loi_phat = self._phat(chuyen_muc.kenh_dang, _noi_dung(ky.ban_tin))
        da_toi = len(chuyen_muc.kenh_dang) - len(loi_phat)
        return (KetQuaKy.DA_PHAT if da_toi else KetQuaKy.HONG), "; ".join(loi_phat) or None

    def _thu_thap(self, phien: Session, nguon: Nguon, moc: datetime, thoi_diem: datetime) -> bool:
        """Lấy và lưu Bài gốc mới của một Nguồn; trả về có lấy được hay không.

        Lỗi được ghi lại ở Nguồn, không lan ra ngoài.
        """
        nguon.lay_gan_nhat_luc = thoi_diem
        try:
            bai_moi = self._bo_thu_thap[nguon.loai].thu_thap(nguon.dia_chi, moc)
            with phien.begin_nested():
                _luu_bai_goc(phien, nguon, bai_moi, thoi_diem)
        except Exception as loi:
            log.exception("Không thu thập được Nguồn %s", nguon.ten)
            nguon.loi_gan_nhat = str(loi)
            return False
        nguon.loi_gan_nhat = None
        return True

    def _phat(self, kenh_dang: Sequence[KenhDang], noi_dung: NoiDungBanTin) -> list[str]:
        """Phát tới từng Kênh đăng; trả về lỗi của những Kênh đăng không phát được."""
        loi_phat = []
        for kenh in kenh_dang:
            try:
                self._bo_phat[kenh.loai].phat(kenh.dia_chi, noi_dung)
            except Exception as loi:
                log.exception("Không phát được tới Kênh đăng %s", kenh.ten)
                loi_phat.append(f"Kênh đăng {kenh.ten} lỗi: {loi}")
        return loi_phat

    def lich_su(self, ma_chuyen_muc: str) -> list[KyDaChay]:
        """Các Kỳ đã lưu của Chuyên mục, mới nhất trước."""
        with self._mo_phien() as phien:
            chuyen_muc = _chuyen_muc(phien, ma_chuyen_muc)
            cac_ky = phien.scalars(
                select(Ky)
                .where(Ky.chuyen_muc_id == chuyen_muc.id)
                .order_by(Ky.thoi_diem.desc(), Ky.id.desc())
            )
            return [_da_chay(ky) for ky in cac_ky]


def _chuyen_muc(phien: Session, ma: str) -> ChuyenMuc:
    chuyen_muc = phien.scalar(select(ChuyenMuc).where(ChuyenMuc.ma == ma))
    if chuyen_muc is None:
        raise LookupError(f"Không có Chuyên mục nào có mã {ma!r}")
    return chuyen_muc


def _noi_dung(ban_tin: BanTin) -> NoiDungBanTin:
    return NoiDungBanTin(
        chuyen_muc=ban_tin.ky.chuyen_muc.ten,
        thoi_diem=ban_tin.ky.thoi_diem,
        tin=tuple(NoiDungTin(tin.tieu_de, tin.bai_goc_chinh.dia_chi) for tin in ban_tin.tin),
    )


def _da_chay(ky: Ky) -> KyDaChay:
    return KyDaChay(
        thoi_diem=ky.thoi_diem,
        ket_qua=ky.ket_qua,
        li_do=ky.li_do,
        ban_tin=_noi_dung(ky.ban_tin) if ky.ban_tin else None,
    )


def _moc(phien: Session, chuyen_muc: ChuyenMuc, thoi_diem: datetime) -> datetime:
    """Mốc bắt đầu của Kỳ: Bản tin trước của cùng Chuyên mục, lần đầu là 24 giờ gần nhất."""
    ban_tin_truoc = phien.scalar(
        select(func.max(Ky.thoi_diem)).where(
            Ky.chuyen_muc_id == chuyen_muc.id, Ky.ket_qua == KetQuaKy.DA_PHAT
        )
    )
    return ban_tin_truoc or thoi_diem - KHOANG_LAN_DAU


def _luu_bai_goc(
    phien: Session, nguon: Nguon, bai_moi: Sequence[BaiGocMoi], thoi_diem: datetime
) -> None:
    """Lưu các Bài gốc chưa có và ghi nhận chúng đã được thấy ở `nguon`."""
    if not bai_moi:
        return
    chuan_hoa_cua = {bai.dia_chi: chuan_hoa(bai.dia_chi) for bai in bai_moi}
    phien.execute(
        insert(BaiGoc)
        .values(
            [
                {
                    "dia_chi_chuan_hoa": chuan_hoa_cua[bai.dia_chi],
                    "dia_chi": bai.dia_chi,
                    "tieu_de": bai.tieu_de,
                    # Nguồn ghi giờ xuất bản ở tương lai thì coi như vừa xuất hiện.
                    "xuat_hien_luc": min(bai.xuat_ban_luc or thoi_diem, thoi_diem),
                    "thu_thap_luc": thoi_diem,
                }
                for bai in bai_moi
            ]
        )
        .on_conflict_do_nothing(index_elements=[BaiGoc.dia_chi_chuan_hoa])
    )
    thay_o_nguon = select(BaiGoc.id, literal(nguon.id)).where(
        BaiGoc.dia_chi_chuan_hoa.in_(chuan_hoa_cua.values())
    )
    phien.execute(
        insert(bai_goc_nguon)
        .from_select(["bai_goc_id", "nguon_id"], thay_o_nguon)
        .on_conflict_do_nothing()
    )


def _bai_goc_trong_ky(
    phien: Session, chuyen_muc: ChuyenMuc, moc: datetime, thoi_diem: datetime
) -> Sequence[BaiGoc]:
    """Bài gốc từ Nguồn của Chuyên mục xuất hiện trong khoảng (moc, thoi_diem], mới nhất trước."""
    cua_chuyen_muc = (
        select(bai_goc_nguon.c.bai_goc_id)
        .join(chuyen_muc_nguon, chuyen_muc_nguon.c.nguon_id == bai_goc_nguon.c.nguon_id)
        .where(chuyen_muc_nguon.c.chuyen_muc_id == chuyen_muc.id)
    )
    return phien.scalars(
        select(BaiGoc)
        .where(
            BaiGoc.id.in_(cua_chuyen_muc),
            BaiGoc.xuat_hien_luc > moc,
            BaiGoc.xuat_hien_luc <= thoi_diem,
        )
        .order_by(BaiGoc.xuat_hien_luc.desc(), BaiGoc.id)
        .limit(chuyen_muc.so_tin_toi_da)
    ).all()
