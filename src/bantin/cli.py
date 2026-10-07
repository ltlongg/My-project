"""Dòng lệnh `bantin`: nạp dữ liệu khởi tạo và chạy một Kỳ ngay bây giờ."""

import argparse
import io
import logging
import sys
from collections.abc import Sequence
from datetime import UTC, datetime

import httpx

from bantin.cau_hinh import CauHinh
from bantin.chay_ky import ChayKy
from bantin.csdl import nang_cap, tao_engine, tao_mo_phien
from bantin.khoi_tao import MA_CONG_NGHE, khoi_tao
from bantin.mo_hinh import KetQuaKy, LoaiKenhDang, LoaiNguon
from bantin.phat_hanh.telegram import PhatTelegram
from bantin.thu_thap.rss import ThuThapRss

NHAN_KET_QUA = {
    KetQuaKy.DA_PHAT: "Đã phát",
    KetQuaKy.KHONG_PHAT: "Không phát",
    KetQuaKy.HONG: "Hỏng",
}


def main(argv: Sequence[str] | None = None) -> int:
    for luong in (sys.stdout, sys.stderr):
        # Console Windows mặc định không in được tiếng Việt khi đầu ra bị chuyển hướng.
        if isinstance(luong, io.TextIOWrapper):
            luong.reconfigure(encoding="utf-8")
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    # httpx ghi lại địa chỉ từng lời gọi, mà địa chỉ của Telegram có chứa token của bot.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    phan_tich = argparse.ArgumentParser(prog="bantin", description=__doc__)
    lenh = phan_tich.add_subparsers(dest="lenh", required=True)
    lenh.add_parser("khoi-tao", help="Nâng cấp lược đồ và nạp dữ liệu khởi tạo")
    lenh_chay_ky = lenh.add_parser("chay-ky", help="Chạy một Kỳ cho một Chuyên mục ngay bây giờ")
    lenh_chay_ky.add_argument("chuyen_muc", nargs="?", default=MA_CONG_NGHE, help="Mã Chuyên mục")
    tham_so = phan_tich.parse_args(argv)

    cau_hinh = CauHinh()
    engine = tao_engine(cau_hinh.database_url)
    mo_phien = tao_mo_phien(engine)

    if tham_so.lenh == "khoi-tao":
        nang_cap(engine)
        khoi_tao(mo_phien, cau_hinh.telegram_chat_id)
        if not cau_hinh.telegram_chat_id:
            print("Chưa có TELEGRAM_CHAT_ID nên chưa tạo Kênh đăng; điền vào .env rồi chạy lại.")
        print("Đã nạp dữ liệu khởi tạo.")
        return 0

    if not cau_hinh.telegram_bot_token:
        print("Thiếu TELEGRAM_BOT_TOKEN; điền vào .env rồi chạy lại.", file=sys.stderr)
        return 2
    with httpx.Client(
        timeout=20, headers={"User-Agent": "Mozilla/5.0 (compatible; bantin/0.1)"}
    ) as client:
        chay_ky = ChayKy(
            mo_phien,
            bo_thu_thap={LoaiNguon.RSS: ThuThapRss(client)},
            bo_phat={LoaiKenhDang.TELEGRAM: PhatTelegram(client, cau_hinh.telegram_bot_token)},
        )
        try:
            ky = chay_ky.chay(tham_so.chuyen_muc, datetime.now(UTC))
        except LookupError as loi:
            print(f"{loi}. Đã chạy `bantin khoi-tao` chưa?", file=sys.stderr)
            return 2

    assert ky.ket_qua is not None
    print(f"{NHAN_KET_QUA[ky.ket_qua]}" + (f": {ky.li_do}" if ky.li_do else ""))
    for thu_tu, tin in enumerate(ky.ban_tin.tin if ky.ban_tin else (), start=1):
        print(f"  {thu_tu}. {tin.tieu_de}\n     {tin.dia_chi}")
    return 1 if ky.ket_qua is KetQuaKy.HONG else 0
