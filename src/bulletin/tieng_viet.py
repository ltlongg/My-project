"""Nhận ra văn bản tiếng Việt bằng phần máy soát được: chữ cái mang dấu."""

CHU_CO_DAU = frozenset("ăâđêôơưàảãáạằẳẵắặầẩẫấậèẻẽéẹềểễếệìỉĩíịòỏõóọồổỗốộờởỡớợùủũúụừửữứựỳỷỹýỵ")
# Văn bản tiếng Việt có khoảng một phần năm chữ cái mang dấu; tiếng Anh thì không có chữ nào.
# Ngưỡng thấp để tóm tắt giữ nhiều tên riêng tiếng Anh vẫn được nhận là tiếng Việt.
TI_LE_CHU_CO_DAU_TOI_THIEU = 0.08


def la_tieng_viet(van_ban: str) -> bool:
    chu_cai = [chu for chu in van_ban.lower() if chu.isalpha()]
    co_dau = sum(chu in CHU_CO_DAU for chu in chu_cai)
    return co_dau >= TI_LE_CHU_CO_DAU_TOI_THIEU * max(len(chu_cai), 1)
