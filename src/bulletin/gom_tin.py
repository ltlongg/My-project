"""Gom Tin: gom các Bài gốc cùng nói về một sự kiện thành ứng viên Tin, và đối chiếu ứng viên với
các Tin đã phát của cùng Chuyên mục.

Đây là bước cố định, không phải Agent (ADR 0001). Độ giống nghĩa là cosine giữa các vector nhúng
của Bài gốc, lưu và so trong Postgres bằng pgvector.
"""

import logging
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import Float, select
from sqlalchemy.orm import Session, aliased

from bulletin.embeddings import BoNhung
from bulletin.mo_hinh import BaiGoc, BanTin, KetQuaKy, Ky, Tin, ung_vien_bai_goc

log = logging.getLogger(__name__)

# Hai Bài gốc giống nhau từ mức này trở lên thì coi là cùng một sự kiện. Chọn bằng cách đo trên
# RSS thật với BAAI/bge-m3; xem docs/gom-tin.md trước khi đổi.
NGUONG_CUNG_SU_KIEN = 0.78
# Ứng viên chỉ được đối chiếu với các Tin đã phát trong khoảng này. Chuyện cũ hơn mà xuất hiện lại
# thường là một sự kiện mới cùng chủ đề (ví dụ đời điện thoại năm sau), không phải tin trùng.
KHOANG_SO_VOI_DA_PHAT = timedelta(days=7)


@dataclass(frozen=True)
class NhomBaiGoc:
    """Một ứng viên Tin: các Bài gốc cùng nói về một sự kiện, xuất hiện sớm nhất trước."""

    bai_goc: tuple[BaiGoc, ...]
    # Tin đã phát của cùng Chuyên mục mà nhóm này giống nhất; None là chuyện chưa phát.
    tin_da_phat_id: int | None


def gom(
    phien: Session,
    bo_nhung: BoNhung,
    chuyen_muc_id: int,
    bai_goc: Sequence[BaiGoc],
    thoi_diem: datetime,
) -> list[NhomBaiGoc]:
    """Gom `bai_goc` thành các ứng viên Tin, ứng viên có Bài gốc mới nhất đứng trước.

    Bài gốc nào chưa có vector của model hiện tại thì được nhúng và lưu lại. Ném lỗi khi không
    nhúng được.
    """
    if not bai_goc:
        return []
    ma = [bai.id for bai in bai_goc]
    da_phat = phien.execute(
        select(Tin.id, ung_vien_bai_goc.c.bai_goc_id, Ky.thoi_diem)
        .join(BanTin, BanTin.id == Tin.ban_tin_id)
        .join(Ky, Ky.id == BanTin.ky_id)
        .join(ung_vien_bai_goc, ung_vien_bai_goc.c.ung_vien_id == Tin.ung_vien_id)
        .where(
            Ky.chuyen_muc_id == chuyen_muc_id,
            # Tin của Kỳ không phát hay hỏng chưa tới người đọc nào.
            Ky.ket_qua == KetQuaKy.DA_PHAT,
            Ky.thoi_diem >= thoi_diem - KHOANG_SO_VOI_DA_PHAT,
            Ky.thoi_diem < thoi_diem,
            Tin.li_do_bo.is_(None),
        )
    ).all()
    _nhung_neu_thieu(phien, bo_nhung, {*ma, *(dong.bai_goc_id for dong in da_phat)})

    tin_chua_bai = defaultdict(list)
    for dong in da_phat:
        tin_chua_bai[dong.bai_goc_id].append((dong.thoi_diem, dong.id))
    # Với mỗi Bài gốc của Kỳ: Tin đã phát giống nó nhất, hoà thì Tin phát gần đây hơn.
    tin_giong: dict[int, tuple[float, datetime, int]] = {}
    for ma_bai, ma_bai_da_phat, do_giong in _cap_giong(phien, ma, list(tin_chua_bai)):
        for phat_luc, ma_tin in tin_chua_bai[ma_bai_da_phat]:
            tin_giong[ma_bai] = max(
                tin_giong.get(ma_bai, (-1.0, phat_luc, 0)), (do_giong, phat_luc, ma_tin)
            )

    theo_ma = {bai.id: bai for bai in bai_goc}
    nhom = []
    for cum in _gom_cum(ma, _cap_giong(phien, ma, ma)):
        giong_nhat = max((tin_giong[m] for m in cum if m in tin_giong), default=None)
        nhom.append(
            NhomBaiGoc(
                tuple(sorted((theo_ma[m] for m in cum), key=lambda b: (b.xuat_hien_luc, b.id))),
                giong_nhat[2] if giong_nhat else None,
            )
        )
    # Mới nhất trước, như thứ tự Bài gốc trước khi có Gom Tin.
    nhom.sort(
        key=lambda n: (max(b.xuat_hien_luc for b in n.bai_goc), -n.bai_goc[0].id), reverse=True
    )
    log.info("Gom %s Bài gốc thành %s ứng viên Tin", len(bai_goc), len(nhom))
    return nhom


def van_ban_nhung(bai_goc: BaiGoc) -> str:
    """Phần của Bài gốc được nhúng để so độ giống nghĩa: tiêu đề, và mô tả nếu có.

    Chỉ tiêu đề thì hai bài khác ngôn ngữ về cùng một sự kiện thường không đủ giống (xem
    docs/gom-tin.md).
    """
    return "\n".join(filter(None, (bai_goc.tieu_de, bai_goc.mo_ta)))


def _nhung_neu_thieu(phien: Session, bo_nhung: BoNhung, ma: set[int]) -> None:
    """Nhúng và lưu vector cho các Bài gốc trong `ma` chưa có vector của model hiện tại."""
    thieu = list(
        phien.scalars(
            select(BaiGoc)
            .where(
                BaiGoc.id.in_(ma),
                BaiGoc.mo_hinh_nhung.is_distinct_from(bo_nhung.mo_hinh),
            )
            .order_by(BaiGoc.id)
        )
    )
    if not thieu:
        return
    vector = bo_nhung.nhung([van_ban_nhung(bai) for bai in thieu])
    for bai, vec in zip(thieu, vector, strict=True):
        bai.vector_nhung, bai.mo_hinh_nhung = vec, bo_nhung.mo_hinh
    phien.flush()


def _cap_giong(
    phien: Session, ma_a: Sequence[int], ma_b: Sequence[int]
) -> list[tuple[int, int, float]]:
    """Các cặp (Bài gốc trong `ma_a`, Bài gốc khác trong `ma_b`) giống nhau từ ngưỡng trở lên,
    kèm độ giống."""
    if not ma_a or not ma_b:
        return []
    a, b = aliased(BaiGoc), aliased(BaiGoc)
    khoang_cach = a.vector_nhung.op("<=>", return_type=Float)(b.vector_nhung)
    dong = phien.execute(
        select(a.id, b.id, 1 - khoang_cach).where(
            a.id.in_(ma_a),
            b.id.in_(ma_b),
            a.id != b.id,
            khoang_cach <= 1 - NGUONG_CUNG_SU_KIEN,
        )
    )
    return [(ma_1, ma_2, float(do_giong)) for ma_1, ma_2, do_giong in dong]


def _gom_cum(ma: Sequence[int], cap: Sequence[tuple[int, int, float]]) -> list[frozenset[int]]:
    """Gom theo kiểu liên kết đầy đủ: hai cụm chỉ nhập làm một khi mọi cặp Bài gốc giữa chúng đều
    đủ giống. Nhờ vậy A giống B, B giống C mà A không giống C thì A và C không chung cụm.

    Cặp giống nhất được xét trước. Trả về các cụm theo thứ tự Bài gốc đầu tiên của chúng trong `ma`.
    """
    giong = {frozenset((m1, m2)) for m1, m2, _ in cap}
    cum: dict[int, frozenset[int]] = {m: frozenset((m,)) for m in ma}
    for m1, m2, _ in sorted(cap, key=lambda c: (-c[2], c[0], c[1])):
        c1, c2 = cum[m1], cum[m2]
        if c1 is c2 or not all(frozenset((x, y)) in giong for x in c1 for y in c2):
            continue
        hop = c1 | c2
        for m in hop:
            cum[m] = hop
    da_gap: set[frozenset[int]] = set()
    ket_qua = []
    for m in ma:
        if cum[m] not in da_gap:
            da_gap.add(cum[m])
            ket_qua.append(cum[m])
    return ket_qua
