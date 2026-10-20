"""Chạy Kỳ: lối vào duy nhất để làm một Bản tin cho một Chuyên mục tại một thời điểm."""

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, literal, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from bulletin.agents.bien_tap import BienTap, DeBai, LoiBienTap, UngVien
from bulletin.agents.kiem_chung import LoiKiemChung
from bulletin.collectors import BaiGocMoi, BoThuThap
from bulletin.dia_chi import chuan_hoa
from bulletin.extractors import BoLayNoiDung
from bulletin.mo_hinh import (
    BaiGoc,
    BanTin,
    ChuyenMuc,
    HuongDan,
    KenhDang,
    KetQuaKy,
    Ky,
    LoaiKenhDang,
    LoaiNguon,
    LuotKiemChung,
    Nguon,
    Tin,
    VaiTro,
    bai_goc_nguon,
    chuyen_muc_nguon,
)
from bulletin.publishers import BoPhat, NoiDungBanTin, NoiDungTin

log = logging.getLogger(__name__)

# Kỳ đầu tiên của một Chuyên mục chưa có Bản tin trước để làm mốc.
KHOANG_LAN_DAU = timedelta(hours=24)
# Số Bài gốc mới nhất đưa cho Biên tập, cho tới khi có bước sơ tuyển (ticket 07).
SO_UNG_VIEN_TOI_DA = 30
# Bản tin có ít Tin qua Kiểm chứng hơn số này thì không phát, coi như Kỳ hỏng.
SO_TIN_TOI_THIEU = 3


@dataclass(frozen=True)
class KyDaChay:
    """Một Kỳ đúng như đã lưu."""

    thoi_diem: datetime
    # Chưa có kết quả nghĩa là Kỳ đang chạy hoặc bị gián đoạn giữa chừng.
    ket_qua: KetQuaKy | None
    li_do: str | None
    ban_tin: NoiDungBanTin | None
    # Phiên bản Hướng dẫn mà Biên tập và Kiểm chứng đã dùng; chưa tới bước Biên tập thì để trống.
    phien_ban_huong_dan_bien_tap: int | None = None
    phien_ban_huong_dan_kiem_chung: int | None = None


class ChayKy:
    def __init__(
        self,
        mo_phien: sessionmaker[Session],
        bo_thu_thap: Mapping[LoaiNguon, BoThuThap],
        bo_phat: Mapping[LoaiKenhDang, BoPhat],
        lay_noi_dung: BoLayNoiDung,
        bien_tap: BienTap,
    ) -> None:
        self._mo_phien = mo_phien
        self._bo_thu_thap = bo_thu_thap
        self._bo_phat = bo_phat
        self._lay_noi_dung = lay_noi_dung
        self._bien_tap = bien_tap

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
            return self._hoan_tat(phien, ky, moc)

    def chay_tiep(self, ma_chuyen_muc: str) -> KyDaChay | None:
        """Chạy tiếp Kỳ gần nhất của Chuyên mục nếu nó bị gián đoạn giữa chừng.

        Biên tập làm tiếp từ bước đang dở chứ không làm lại từ đầu. Trả về None khi Kỳ gần nhất
        đã có kết quả, tức là không có gì để chạy tiếp.
        """
        with self._mo_phien() as phien:
            chuyen_muc = _chuyen_muc(phien, ma_chuyen_muc)
            ky = phien.scalar(
                select(Ky)
                .where(Ky.chuyen_muc_id == chuyen_muc.id)
                .order_by(Ky.thoi_diem.desc(), Ky.id.desc())
                .limit(1)
            )
            if ky is None or ky.ket_qua is not None:
                return None
            return self._hoan_tat(phien, ky, _moc(phien, chuyen_muc, ky.thoi_diem))

    def _hoan_tat(self, phien: Session, ky: Ky, moc: datetime) -> KyDaChay:
        """Làm Bản tin cho một Kỳ đã lưu và ghi kết quả vào nó."""
        try:
            ky.ket_qua, ky.li_do = self._lam_ban_tin(phien, ky, moc)
        except Exception as loi:
            phien.rollback()
            log.exception("Kỳ của Chuyên mục %s gặp lỗi không lường trước", ky.chuyen_muc.ma)
            ky.ket_qua = KetQuaKy.HONG
            ky.li_do = f"Lỗi không lường trước: {str(loi).splitlines()[0]}"
        phien.commit()
        return _da_chay(ky)

    def _lam_ban_tin(self, phien: Session, ky: Ky, moc: datetime) -> tuple[KetQuaKy, str | None]:
        """Thu thập, để Biên tập dựng Bản tin và Kiểm chứng xét nó, rồi phát; trả về kết quả của
        Kỳ kèm lí do.

        Mọi bước đều làm lại được trên cùng một Kỳ, để Kỳ bị gián đoạn chạy tiếp được.
        """
        chuyen_muc = ky.chuyen_muc
        if not chuyen_muc.nguon:
            return KetQuaKy.HONG, "Chuyên mục chưa có Nguồn nào"
        if ky.huong_dan_bien_tap is None:
            ky.huong_dan_bien_tap = phien.scalar(
                select(HuongDan).where(
                    HuongDan.vai_tro == VaiTro.BIEN_TAP,
                    HuongDan.chuyen_muc_id == chuyen_muc.id,
                    HuongDan.co_hieu_luc,
                )
            )
        if ky.huong_dan_bien_tap is None:
            return KetQuaKy.HONG, "Chuyên mục chưa có Hướng dẫn cho Biên tập"
        if ky.huong_dan_kiem_chung is None:
            ky.huong_dan_kiem_chung = phien.scalar(
                select(HuongDan).where(
                    HuongDan.vai_tro == VaiTro.KIEM_CHUNG,
                    HuongDan.chuyen_muc_id.is_(None),
                    HuongDan.co_hieu_luc,
                )
            )
        if ky.huong_dan_kiem_chung is None:
            return KetQuaKy.HONG, "Chưa có Hướng dẫn cho Kiểm chứng"
        lay_duoc = [self._thu_thap(phien, nguon, moc, ky.thoi_diem) for nguon in chuyen_muc.nguon]
        phien.commit()
        if not any(lay_duoc):
            # Hỏng chứ không phải "không phát": thử lại sau có thể lấy được.
            return KetQuaKy.HONG, "Không thu thập được Nguồn nào"
        # Xét trước khi gọi Agent, để không tốn lời gọi LLM cho Bản tin không có nơi phát.
        if not chuyen_muc.kenh_dang:
            return KetQuaKy.HONG, "Chuyên mục chưa có Kênh đăng nào"

        if ky.ban_tin is None:
            ung_vien = _ung_vien(phien, chuyen_muc, moc, ky.thoi_diem)
            if not ung_vien:
                return KetQuaKy.KHONG_PHAT, "Không có Bài gốc mới"
            de_bai = DeBai(
                chuyen_muc=chuyen_muc.ten,
                thoi_diem=ky.thoi_diem,
                huong_dan=ky.huong_dan_bien_tap.noi_dung,
                huong_dan_kiem_chung=ky.huong_dan_kiem_chung.noi_dung,
                so_tin_toi_da=chuyen_muc.so_tin_toi_da,
                ung_vien=ung_vien,
            )
            # Biên tập làm việc lâu; không giữ giao dịch nào mở trong lúc đó.
            phien.commit()
            try:
                tin_da_viet = self._bien_tap.lam(f"ky-{ky.id}-bien-tap", de_bai, self._doc_bai_goc)
            except (LoiBienTap, LoiKiemChung) as loi:
                return KetQuaKy.HONG, str(loi)
            except Exception as loi:
                log.exception("Biên tập của Chuyên mục %s gặp lỗi", chuyen_muc.ma)
                return KetQuaKy.HONG, f"Biên tập gặp lỗi: {str(loi).splitlines()[0]}"
            ky.ban_tin = BanTin(
                tin=[
                    Tin(
                        thu_tu=thu_tu,
                        tieu_de=tin.tieu_de,
                        tom_tat=tin.tom_tat,
                        li_do=tin.li_do,
                        bai_goc_chinh_id=tin.ma_bai_goc,
                        li_do_bo=tin.li_do_bo,
                        luot_kiem_chung=[
                            LuotKiemChung(
                                lan=lan,
                                tieu_de=ban.tieu_de,
                                tom_tat=ban.tom_tat,
                                dat=ban.dat,
                                li_do=ban.li_do,
                            )
                            for lan, ban in enumerate(tin.ban_viet, start=1)
                        ],
                    )
                    for thu_tu, tin in enumerate(tin_da_viet, start=1)
                ]
            )
            # Bản tin được lưu trước khi phát, để Kỳ hỏng vẫn cho thấy nó định gửi gì.
            phien.commit()

        so_tin = len(_tin_duoc_phat(ky.ban_tin))
        if so_tin < SO_TIN_TOI_THIEU:
            return KetQuaKy.HONG, (
                f"Chỉ {so_tin} Tin qua Kiểm chứng, dưới mức tối thiểu {SO_TIN_TOI_THIEU}; "
                "Bản tin không được phát"
            )
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

    def _doc_bai_goc(self, ma: int) -> str:
        """Toàn văn của một Bài gốc; lần đầu thì lấy về và lưu lại."""
        with self._mo_phien() as phien:
            bai_goc = phien.get_one(BaiGoc, ma)
            if bai_goc.toan_van is None:
                bai_goc.toan_van = self._lay_noi_dung.lay(bai_goc.dia_chi)
                phien.commit()
            return bai_goc.toan_van

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
        tin=tuple(
            NoiDungTin(tin.tieu_de, tin.tom_tat, tin.bai_goc_chinh.dia_chi)
            for tin in _tin_duoc_phat(ban_tin)
        ),
    )


def _tin_duoc_phat(ban_tin: BanTin) -> list[Tin]:
    """Các Tin đã qua Kiểm chứng, theo thứ tự Biên tập nộp."""
    return [tin for tin in ban_tin.tin if tin.li_do_bo is None]


def _da_chay(ky: Ky) -> KyDaChay:
    return KyDaChay(
        thoi_diem=ky.thoi_diem,
        ket_qua=ky.ket_qua,
        li_do=ky.li_do,
        ban_tin=_noi_dung(ky.ban_tin) if ky.ban_tin else None,
        phien_ban_huong_dan_bien_tap=(
            ky.huong_dan_bien_tap.phien_ban if ky.huong_dan_bien_tap else None
        ),
        phien_ban_huong_dan_kiem_chung=(
            ky.huong_dan_kiem_chung.phien_ban if ky.huong_dan_kiem_chung else None
        ),
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


def _ung_vien(
    phien: Session, chuyen_muc: ChuyenMuc, moc: datetime, thoi_diem: datetime
) -> list[UngVien]:
    """Bài gốc từ Nguồn của Chuyên mục xuất hiện trong khoảng (moc, thoi_diem], mới nhất trước.

    Chưa có bước gom Tin, nên mỗi Bài gốc là một ứng viên Tin cho Biên tập.
    """
    cua_chuyen_muc = (
        select(bai_goc_nguon.c.bai_goc_id)
        .join(chuyen_muc_nguon, chuyen_muc_nguon.c.nguon_id == bai_goc_nguon.c.nguon_id)
        .where(chuyen_muc_nguon.c.chuyen_muc_id == chuyen_muc.id)
    )
    bai_goc = phien.scalars(
        select(BaiGoc)
        .where(
            BaiGoc.id.in_(cua_chuyen_muc),
            BaiGoc.xuat_hien_luc > moc,
            BaiGoc.xuat_hien_luc <= thoi_diem,
        )
        .order_by(BaiGoc.xuat_hien_luc.desc(), BaiGoc.id)
        .limit(SO_UNG_VIEN_TOI_DA)
    )
    return [
        UngVien(
            ma=bai.id,
            tieu_de=bai.tieu_de,
            # Bài gốc có thể được thấy ở cả Nguồn của Chuyên mục khác.
            nguon=next(nguon.ten for nguon in bai.nguon if nguon in chuyen_muc.nguon),
            dia_chi=bai.dia_chi,
            xuat_hien_luc=bai.xuat_hien_luc,
        )
        for bai in bai_goc
    ]
