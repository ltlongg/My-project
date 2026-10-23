"""Vòng agent: các Agent tự phán đoán khi làm một Bản tin (ADR 0001), viết bằng LangGraph."""

# Phần toàn văn đưa cho LLM; bài dài hơn thì cắt, vì tin chính nằm ở đầu bài. Biên tập và Kiểm
# chứng đọc cùng một phần, để Kiểm chứng không bắt lỗi chi tiết mà Biên tập chưa từng thấy.
MAX_FULL_TEXT = 20_000


def truncate_full_text(full_text: str) -> str:
    if len(full_text) <= MAX_FULL_TEXT:
        return full_text
    return full_text[:MAX_FULL_TEXT] + "\n[Bài còn dài; phần sau đã được cắt bớt.]"
