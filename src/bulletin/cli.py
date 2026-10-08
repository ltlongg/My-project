"""Dòng lệnh `bulletin`: nạp dữ liệu khởi tạo, chạy một Kỳ ngay bây giờ, thử endpoint LLM."""

import argparse
import io
import logging
import sys
from collections.abc import Sequence
from datetime import UTC, datetime

import httpx

from bulletin.cau_hinh import CauHinh
from bulletin.chay_ky import ChayKy
from bulletin.collectors.rss import ThuThapRss
from bulletin.csdl import nang_cap, tao_engine, tao_mo_phien
from bulletin.khoi_tao import MA_CONG_NGHE, khoi_tao
from bulletin.mo_hinh import KetQuaKy, LoaiKenhDang, LoaiNguon
from bulletin.publishers.telegram import PhatTelegram
from bulletin.thu_llm import (
    EndpointLLM,
    LoiEndpoint,
    bao_cao,
    don_dap,
    thu_nhieu_model,
    thu_nhung,
)

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

    phan_tich = argparse.ArgumentParser(prog="bulletin", description=__doc__)
    lenh = phan_tich.add_subparsers(dest="lenh", required=True)
    lenh.add_parser("khoi-tao", help="Nâng cấp lược đồ và nạp dữ liệu khởi tạo")
    lenh_chay_ky = lenh.add_parser("chay-ky", help="Chạy một Kỳ cho một Chuyên mục ngay bây giờ")
    lenh_chay_ky.add_argument("chuyen_muc", nargs="?", default=MA_CONG_NGHE, help="Mã Chuyên mục")
    lenh_thu_llm = lenh.add_parser(
        "thu-llm", help="Thử từng model của endpoint LLM và in báo cáo markdown"
    )
    lenh_thu_llm.add_argument("model", nargs="*", help="Model cần thử; bỏ trống là mọi model")
    lenh_thu_llm.add_argument(
        "--nhung", default="text-embedding-3-small", help="Model dùng để thử tạo vector nhúng"
    )
    lenh_thu_llm.add_argument(
        "--don-dap",
        nargs=2,
        metavar=("MODEL", "SO_LOI_GOI"),
        help="Gửi cùng lúc ngần ấy lời gọi tới một model để xem endpoint trả gì khi bị dồn",
    )
    tham_so = phan_tich.parse_args(argv)

    cau_hinh = CauHinh()
    if tham_so.lenh == "thu-llm":
        return _thu_llm(cau_hinh, tham_so)

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
        timeout=20, headers={"User-Agent": "Mozilla/5.0 (compatible; bulletin/0.1)"}
    ) as client:
        chay_ky = ChayKy(
            mo_phien,
            bo_thu_thap={LoaiNguon.RSS: ThuThapRss(client)},
            bo_phat={LoaiKenhDang.TELEGRAM: PhatTelegram(client, cau_hinh.telegram_bot_token)},
        )
        try:
            ky = chay_ky.chay(tham_so.chuyen_muc, datetime.now(UTC))
        except LookupError as loi:
            print(f"{loi}. Đã chạy `bulletin khoi-tao` chưa?", file=sys.stderr)
            return 2

    assert ky.ket_qua is not None
    print(f"{NHAN_KET_QUA[ky.ket_qua]}" + (f": {ky.li_do}" if ky.li_do else ""))
    for thu_tu, tin in enumerate(ky.ban_tin.tin if ky.ban_tin else (), start=1):
        print(f"  {thu_tu}. {tin.tieu_de}\n     {tin.dia_chi}")
    return 1 if ky.ket_qua is KetQuaKy.HONG else 0


def _thu_llm(cau_hinh: CauHinh, tham_so: argparse.Namespace) -> int:
    if not cau_hinh.openai_base_url or not cau_hinh.openai_api_key:
        print(
            "Thiếu OPENAI_BASE_URL hoặc OPENAI_API_KEY; điền vào .env rồi chạy lại.",
            file=sys.stderr,
        )
        return 2
    dia_chi, khoa = cau_hinh.openai_base_url, cau_hinh.openai_api_key
    # Model suy luận có thể nghĩ rất lâu trước khi trả chữ đầu tiên.
    with httpx.Client(timeout=httpx.Timeout(300, connect=10)) as client:
        endpoint = EndpointLLM(client, dia_chi, khoa)
        try:
            cac_model = tham_so.model or endpoint.cac_model()
        except LoiEndpoint as loi:
            print(f"Không lấy được danh sách model: {loi}", file=sys.stderr)
            return 1
        ket_qua = thu_nhieu_model(endpoint, cac_model)
        print("## Từng model", "", bao_cao(ket_qua), sep="\n")

        nhung = thu_nhung(endpoint, tham_so.nhung)
        ket_luan = "đạt" if nhung.dat else "KHÔNG"
        print("", "## Vector nhúng", "", sep="\n")
        print(f"- `{tham_so.nhung}`: {ket_luan}, {nhung.ghi_chu}")

        model_song = next((kq.model for kq in ket_qua if kq.phep_thu["goi_thuong"].dat), None)
        tu_choi = {
            "Khoá sai": (EndpointLLM(client, dia_chi, "sk-sai"), model_song or cac_model[0]),
            "Model không tồn tại": (endpoint, "khong-co/model-nay"),
        }
        print("", "## Khi endpoint từ chối", "", sep="\n")
        for tinh_huong, (noi_goi, model) in tu_choi.items():
            try:
                noi_goi.tro_chuyen(model, [{"role": "user", "content": "xin chào"}])
                print(f"- {tinh_huong}: endpoint vẫn trả lời")
            except LoiEndpoint as loi:
                print(f"- {tinh_huong}: {loi}")

        if tham_so.don_dap:
            model, so_loi_goi = tham_so.don_dap[0], int(tham_so.don_dap[1])
            print("", f"## {so_loi_goi} lời gọi cùng lúc tới `{model}`", "", sep="\n")
            for ket_qua_goi, so_lan in don_dap(endpoint, model, so_loi_goi).most_common():
                print(f"- {so_lan} lần: {ket_qua_goi}")
    return 0
