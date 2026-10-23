"""Dữ liệu khởi tạo: đủ để chạy Kỳ đầu tiên khi chưa có trang quản lí."""

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from bulletin.models import (
    Channel,
    ChannelKind,
    Guideline,
    Role,
    Section,
    Source,
    SourceKind,
)

TECH_SLUG = "tech"
STARTER_RSS = ("VnExpress Khoa học công nghệ", "https://vnexpress.net/rss/khoa-hoc-cong-nghe.rss")
# Bản tạm để Biên tập chạy được; ticket 14 soạn Hướng dẫn khởi đầu đầy đủ.
TECH_EDITOR_GUIDELINE = """\
Phạm vi: tin công nghệ, ưu tiên AI (model mới, nghiên cứu, sản phẩm, chính sách), lập trình và \
công cụ cho người làm phần mềm, chip và hạ tầng tính toán, và các công ty công nghệ lớn.

Đáng đọc: sự kiện mới có tác động thật (ra mắt, số liệu, quyết định, sự cố), nêu được ai làm gì \
và con số cụ thể. Ưu tiên nơi đưa tin đầu tiên hoặc nguồn gốc nhất.

Không chọn: bài quảng cáo, khuyến mãi, mẹo vặt, bài đánh giá hay so sánh sản phẩm tiêu dùng không \
có gì mới, tin giải trí, và hai Tin cùng nói về một sự kiện.

Giọng văn: trung tính, đi thẳng vào việc, không giật tít, không bình luận thêm. Câu đầu của tóm \
tắt nói ngay điều gì đã xảy ra."""
# Bản tạm, chung cho mọi Chuyên mục; ticket 14 soạn Hướng dẫn khởi đầu đầy đủ.
VERIFIER_GUIDELINE = """\
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


def seed(session_factory: sessionmaker[Session], telegram_chat_id: str | None) -> None:
    """Tạo Chuyên mục công nghệ với một Nguồn RSS, Hướng dẫn cho Biên tập, Hướng dẫn chung cho
    Kiểm chứng và, nếu đã biết mã nhóm, một Kênh đăng Telegram.

    Chạy lại không tạo trùng và không ghi đè thứ đã có; chỉ bổ sung thứ còn thiếu.
    """
    with session_factory.begin() as session:
        section = session.scalar(select(Section).where(Section.slug == TECH_SLUG))
        if section is None:
            section = Section(slug=TECH_SLUG, name="Công nghệ", max_stories=7)
            session.add(section)

        name, url = STARTER_RSS
        source = session.scalar(
            select(Source).where(Source.kind == SourceKind.RSS, Source.url == url)
        ) or Source(kind=SourceKind.RSS, name=name, url=url)
        if source not in section.sources:
            section.sources.append(source)

        session.flush()
        has_editor_guideline = session.scalar(
            select(Guideline.id)
            .where(Guideline.role == Role.EDITOR, Guideline.section_id == section.id)
            .limit(1)
        )
        if not has_editor_guideline:
            session.add(
                Guideline(
                    role=Role.EDITOR,
                    section_id=section.id,
                    version=1,
                    content=TECH_EDITOR_GUIDELINE,
                    is_active=True,
                )
            )
        has_verifier_guideline = session.scalar(
            select(Guideline.id)
            .where(Guideline.role == Role.VERIFIER, Guideline.section_id.is_(None))
            .limit(1)
        )
        if not has_verifier_guideline:
            session.add(
                Guideline(
                    role=Role.VERIFIER,
                    section_id=None,
                    version=1,
                    content=VERIFIER_GUIDELINE,
                    is_active=True,
                )
            )

        if telegram_chat_id:
            channel = session.scalar(
                select(Channel).where(
                    Channel.kind == ChannelKind.TELEGRAM, Channel.address == telegram_chat_id
                )
            ) or Channel(
                kind=ChannelKind.TELEGRAM, name="Nhóm Telegram thử", address=telegram_chat_id
            )
            if channel not in section.channels:
                section.channels.append(channel)
