"""Vòng agent: các Agent tự phán đoán khi làm một Bản tin (ADR 0001), viết bằng LangGraph."""

# Phần toàn văn đưa cho LLM; bài dài hơn thì cắt, vì tin chính nằm ở đầu bài. Biên tập và Kiểm
# chứng đọc cùng một phần, để Kiểm chứng không bắt lỗi chi tiết mà Biên tập chưa từng thấy.
TOAN_VAN_TOI_DA = 20_000


def cat_toan_van(toan_van: str) -> str:
    if len(toan_van) <= TOAN_VAN_TOI_DA:
        return toan_van
    return toan_van[:TOAN_VAN_TOI_DA] + "\n[Bài còn dài; phần sau đã được cắt bớt.]"
