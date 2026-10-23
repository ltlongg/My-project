"""Dữ liệu khởi tạo: đủ để chạy Kỳ đầu tiên khi chưa có trang quản lí."""

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from bulletin.mo_hinh import (
    ChuyenMuc,
    HuongDan,
    KenhDang,
    LoaiKenhDang,
    LoaiNguon,
    Nguon,
    VaiTro,
)

MA_CONG_NGHE = "cong-nghe"
RSS_KHOI_DAU = ("VnExpress Khoa học công nghệ", "https://vnexpress.net/rss/khoa-hoc-cong-nghe.rss")
# Bản tạm để Biên tập chạy được; ticket 14 soạn Hướng dẫn khởi đầu đầy đủ.
HUONG_DAN_BIEN_TAP_CONG_NGHE = """\
Phạm vi: tin công nghệ, ưu tiên AI (model mới, nghiên cứu, sản phẩm, chính sách), lập trình và \
công cụ cho người làm phần mềm, chip và hạ tầng tính toán, và các công ty công nghệ lớn.

Đáng đọc: sự kiện mới có tác động thật (ra mắt, số liệu, quyết định, sự cố), nêu được ai làm gì \
và con số cụ thể. Ưu tiên nơi đưa tin đầu tiên hoặc nguồn gốc nhất.

Không chọn: bài quảng cáo, khuyến mãi, mẹo vặt, bài đánh giá hay so sánh sản phẩm tiêu dùng không \
có gì mới, tin giải trí, và hai Tin cùng nói về một sự kiện.

Giọng văn: trung tính, đi thẳng vào việc, không giật tít, không bình luận thêm. Câu đầu của tóm \
tắt nói ngay điều gì đã xảy ra."""
# Bản tạm, chung cho mọi Chuyên mục; ticket 14 soạn Hướng dẫn khởi đầu đầy đủ.
HUONG_DAN_KIEM_CHUNG = """\
Đối chiếu từng chi tiết của tiêu đề và tóm tắt với toàn văn Bài gốc:
- Số liệu: con số, đơn vị, tỉ lệ, tiền tệ, và con số đó đo cái gì.
- Tên: người, tổ chức, sản phẩm, model, địa danh; ai làm gì, ai nói gì.
- Ngày tháng và thời gian: khi nào việc xảy ra, việc đã xảy ra hay mới là dự kiến.
- Tiêu đề không nói quá Bài gốc: không biến dự kiến thành sự thật, khả năng thành chắc chắn, một \
trường hợp thành xu hướng; không thêm "đầu tiên", "lớn nhất", "chấn động" khi Bài gốc không nói.
- Không có chi tiết nào ngoài Bài gốc, và bản dịch giữ đúng nghĩa.

Không đạt khi có ít nhất một chi tiết sai, không có căn cứ trong Bài gốc, hoặc tiêu đề nói quá. \
Đạt khi mọi chi tiết đều có căn cứ; văn phong vụng, thiếu một chi tiết phụ hay cách chọn ý không \
phải lí do để không đạt."""


def khoi_tao(mo_phien: sessionmaker[Session], ma_tro_chuyen_telegram: str | None) -> None:
    """Tạo Chuyên mục công nghệ với một Nguồn RSS, Hướng dẫn cho Biên tập, Hướng dẫn chung cho
    Kiểm chứng và, nếu đã biết mã nhóm, một Kênh đăng Telegram.

    Chạy lại không tạo trùng và không ghi đè thứ đã có; chỉ bổ sung thứ còn thiếu.
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

        phien.flush()
        da_co_huong_dan = phien.scalar(
            select(HuongDan.id)
            .where(HuongDan.vai_tro == VaiTro.BIEN_TAP, HuongDan.chuyen_muc_id == chuyen_muc.id)
            .limit(1)
        )
        if not da_co_huong_dan:
            phien.add(
                HuongDan(
                    vai_tro=VaiTro.BIEN_TAP,
                    chuyen_muc_id=chuyen_muc.id,
                    phien_ban=1,
                    noi_dung=HUONG_DAN_BIEN_TAP_CONG_NGHE,
                    co_hieu_luc=True,
                )
            )
        da_co_huong_dan_kiem_chung = phien.scalar(
            select(HuongDan.id)
            .where(HuongDan.vai_tro == VaiTro.KIEM_CHUNG, HuongDan.chuyen_muc_id.is_(None))
            .limit(1)
        )
        if not da_co_huong_dan_kiem_chung:
            phien.add(
                HuongDan(
                    vai_tro=VaiTro.KIEM_CHUNG,
                    chuyen_muc_id=None,
                    phien_ban=1,
                    noi_dung=HUONG_DAN_KIEM_CHUNG,
                    co_hieu_luc=True,
                )
            )

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
