"""Dòng lệnh `bulletin`: nạp dữ liệu khởi tạo, chạy một Kỳ ngay bây giờ, thử endpoint LLM."""

import argparse
import io
import logging
import sys
from collections.abc import Sequence
from datetime import UTC, datetime

import httpx
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from bulletin.agents.bien_tap import BienTap
from bulletin.cau_hinh import CauHinh
from bulletin.chay_ky import ChayKy
from bulletin.collectors.rss import ThuThapRss
from bulletin.csdl import mo_kho_trang_thai, nang_cap, tao_engine, tao_mo_phien
from bulletin.extractors.bai_bao import LayBaiBao
from bulletin.khoi_tao import MA_CONG_NGHE, khoi_tao
from bulletin.mo_hinh import KetQuaKy, LoaiKenhDang, LoaiNguon
from bulletin.publishers.telegram import PhatTelegram
from bulletin.search import BoTimKiem
from bulletin.search.brave import TimKiemBrave
from bulletin.search.tavily import TimKiemTavily
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
    lenh_chay_ky.add_argument(
        "--tiep",
        action="store_true",
        help="Chạy tiếp Kỳ gần nhất nếu nó bị gián đoạn giữa chừng, thay vì chạy một Kỳ mới",
    )
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

    khoa_tim_kiem = {"tavily": cau_hinh.tavily_api_key, "brave": cau_hinh.brave_api_key}
    model_bien_tap = cau_hinh.model_bien_tap or cau_hinh.model
    thieu = [
        ten
        for ten, gia_tri in {
            "TELEGRAM_BOT_TOKEN": cau_hinh.telegram_bot_token,
            "OPENAI_BASE_URL": cau_hinh.openai_base_url,
            "OPENAI_API_KEY": cau_hinh.openai_api_key,
            "MODEL_BIEN_TAP hoặc MODEL": model_bien_tap,
            f"{cau_hinh.cong_cu_tim_kiem.upper()}_API_KEY": khoa_tim_kiem[
                cau_hinh.cong_cu_tim_kiem
            ],
        }.items()
        if not gia_tri
    ]
    if thieu:
        print(f"Thiếu {', '.join(thieu)}; điền vào .env rồi chạy lại.", file=sys.stderr)
        return 2
    assert cau_hinh.telegram_bot_token and cau_hinh.openai_api_key and model_bien_tap
    with (
        httpx.Client(
            timeout=20, headers={"User-Agent": "Mozilla/5.0 (compatible; bulletin/0.1)"}
        ) as client,
        mo_kho_trang_thai(engine) as kho_trang_thai,
    ):
        tim_kiem: BoTimKiem = (
            TimKiemBrave(client, cau_hinh.brave_api_key or "")
            if cau_hinh.cong_cu_tim_kiem == "brave"
            else TimKiemTavily(client, cau_hinh.tavily_api_key or "")
        )
        llm = ChatOpenAI(
            model=model_bien_tap,
            base_url=cau_hinh.openai_base_url,
            api_key=SecretStr(cau_hinh.openai_api_key),
            # Model suy luận có thể nghĩ rất lâu trước khi trả chữ đầu tiên.
            timeout=300,
            max_retries=3,
        )
        chay_ky = ChayKy(
            mo_phien,
            bo_thu_thap={LoaiNguon.RSS: ThuThapRss(client)},
            bo_phat={LoaiKenhDang.TELEGRAM: PhatTelegram(client, cau_hinh.telegram_bot_token)},
            lay_noi_dung=LayBaiBao(client),
            bien_tap=BienTap(llm, tim_kiem, kho_trang_thai),
        )
        try:
            if tham_so.tiep:
                ky = chay_ky.chay_tiep(tham_so.chuyen_muc)
            else:
                ky = chay_ky.chay(tham_so.chuyen_muc, datetime.now(UTC))
        except LookupError as loi:
            print(f"{loi}. Đã chạy `bulletin khoi-tao` chưa?", file=sys.stderr)
            return 2

    if ky is None:
        print("Kỳ gần nhất đã có kết quả; không có gì để chạy tiếp.")
        return 0
    assert ky.ket_qua is not None
    print(f"{NHAN_KET_QUA[ky.ket_qua]}" + (f": {ky.li_do}" if ky.li_do else ""))
    if ky.phien_ban_huong_dan is not None:
        print(f"Hướng dẫn của Biên tập: phiên bản {ky.phien_ban_huong_dan}")
    for thu_tu, tin in enumerate(ky.ban_tin.tin if ky.ban_tin else (), start=1):
        print(f"  {thu_tu}. {tin.tieu_de}\n     {tin.tom_tat}\n     {tin.dia_chi}")
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
