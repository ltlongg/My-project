"""Nhận ra văn bản tiếng Việt bằng phần máy soát được: chữ cái mang dấu."""

DIACRITIC_LETTERS = frozenset("ăâđêôơưàảãáạằẳẵắặầẩẫấậèẻẽéẹềểễếệìỉĩíịòỏõóọồổỗốộờởỡớợùủũúụừửữứựỳỷỹýỵ")
# Văn bản tiếng Việt có khoảng một phần năm chữ cái mang dấu; tiếng Anh thì không có chữ nào.
# Ngưỡng thấp để tóm tắt giữ nhiều tên riêng tiếng Anh vẫn được nhận là tiếng Việt.
MIN_DIACRITIC_RATIO = 0.08


def is_vietnamese(text: str) -> bool:
    letters = [char for char in text.lower() if char.isalpha()]
    with_diacritics = sum(char in DIACRITIC_LETTERS for char in letters)
    return with_diacritics >= MIN_DIACRITIC_RATIO * max(len(letters), 1)
