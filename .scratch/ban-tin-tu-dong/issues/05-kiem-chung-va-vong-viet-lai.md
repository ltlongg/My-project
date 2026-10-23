# 05: Kiểm chứng và vòng viết lại

**What to build:** Không **Tin** nào được phát khi chưa qua agent **Kiểm chứng**. **Kiểm chứng** đối chiếu tiêu đề và tóm tắt của từng **Tin** với toàn văn **Bài gốc** của nó, và trả về đạt hoặc không đạt kèm lí do cụ thể. **Tin** không đạt quay lại **Biên tập** để viết lại, tối đa hai lần, rồi bị bỏ khỏi **Bản tin**. Vì không có người duyệt, đây là chốt chặn duy nhất (ADR 0001).

**Blocked by:** 04

**Status:** ready-for-human

- [x] **Kiểm chứng** bắt các sai lệch về số liệu, tên, ngày tháng, và tiêu đề nói quá so với **Bài gốc**
- [x] **Tin** không đạt được viết lại với lí do của **Kiểm chứng** làm đầu vào; sau hai lần viết lại vẫn không đạt thì bị bỏ
- [x] Mỗi lượt **Kiểm chứng**, lí do, và bản viết lại tương ứng được lưu theo **Tin**
- [x] **Tin** bị bỏ được lưu kèm lí do, không biến mất
- [x] Sau **Kiểm chứng** còn dưới ba **Tin** thì **Bản tin** không được phát và **Kỳ** được ghi là hỏng
- [x] **Hướng dẫn** của **Kiểm chứng** là một bản chung cho mọi **Chuyên mục**, đọc từ dữ liệu; **Kỳ** ghi lại phiên bản đã dùng
- [x] **Kiểm chứng** dùng cấu hình model riêng, độc lập với **Biên tập**
- [x] Test tại điểm "Chạy Kỳ" phủ: đạt ngay, đạt sau khi viết lại, bị bỏ sau hai lần, và không phát vì dưới ba **Tin**

## Comments

**2026-10-20, agent.** Đã làm xong phần code, chưa commit; 86 test xanh, mypy và ruff sạch. **Kiểm chứng** ở `src/bulletin/agents/kiem_chung.py`, nằm trong vòng LangGraph của **Biên tập** (`src/bulletin/agents/bien_tap.py`) như một bước riêng; test tại điểm "Chạy Kỳ" ở `tests/test_kiem_chung.py`.

Đã thử thật tới đâu: một **Kỳ** với RSS của VnExpress, bộ lấy nội dung thật, **Biên tập** là `cx/gpt-5.6-luna`, **Kiểm chứng** là `ds/deepseek-v4-pro`, trên một cơ sở dữ liệu riêng (`bantin_thu`), **Kênh đăng** thay bằng lệnh in ra màn hình. Kết quả "Đã phát" với 5 **Tin**, 155 giây. **Kiểm chứng** trả lại đúng một **Tin**: tóm tắt viết robot "chưa đi được trên địa hình không bằng phẳng" trong khi **Bài gốc** chỉ nói khả năng đó "chưa được kiểm chứng", và tiêu đề thêm chữ "khoảng" vào giá 400 USD. **Biên tập** viết lại một lần thì đạt. Mỗi lượt **Kiểm chứng** mất 7–35 giây.

Chuyển sang `ready-for-human` vì bốn việc cần chủ hệ thống:

- Đặt `MODEL_KIEM_CHUNG=ds/deepseek-v4-pro` trong `.env`. Hiện `.env` chưa có biến này nên **Kiểm chứng** dùng `MODEL`, tức cùng model với **Biên tập**, ngược với lựa chọn ở `docs/llm-endpoint.md`.
- Chưa gửi **Bản tin** có **Kiểm chứng** vào nhóm Telegram thử. Cơ sở dữ liệu phát triển đã được nâng cấp lên migration 0003 và có **Hướng dẫn** của **Kiểm chứng** phiên bản 1. Lưu ý: **Kỳ** mới chỉ xét **Bài gốc** từ sau **Bản tin** lúc 14:38 hôm nay, nên chạy ngay bây giờ nhiều khả năng ra dưới ba **Tin** và hỏng.
- Xem qua các quyết định dưới đây.
- Commit.

Quyết định đã tự chọn, cần chủ hệ thống xác nhận:

- **Dưới ba Tin** áp dụng cho mọi **Bản tin**, kể cả khi **Biên tập** chọn ít hơn ba ngay từ đầu, không chỉ khi **Kiểm chứng** bỏ bớt. Vì vậy các test cũ phát một hai **Tin** đã được tăng lên ba **Bài gốc**.
- **Bản tin** không được phát vẫn được lưu, gồm cả **Tin** bị bỏ (cột `li_do_bo`) và mọi lượt **Kiểm chứng** (bảng `luot_kiem_chung`: bản được xét, đạt hay không, lí do).
- **Kiểm chứng** xét từng **Tin** bằng một lời gọi LLM và trả kết luận qua công cụ `ket_luan`. Không đạt mà không nêu lí do thì coi là kết luận hỏng. Hỏng ba lần liền hoặc LLM lỗi thì **Kỳ** hỏng và không có gì được phát.
- **Biên tập** viết lại bằng công cụ mới `viet_lai_tin` và phải gửi đủ các **Tin** bị trả lại trong một lần. Bản viết lại cũng qua bước soát bằng code như bản nộp đầu. Bản bị code trả lại không tính là một lần viết lại, nhưng tính vào giới hạn ba lần nộp hỏng chung của cả **Kỳ**.
- **Tin** đã đạt không bị xét lại. **Biên tập** không được thêm **Tin** khác thay cho **Tin** bị bỏ.
- Tiêu chí đối chiếu (số liệu, tên, ngày tháng, tiêu đề nói quá) nằm trong **Hướng dẫn** của **Kiểm chứng**, tức là trong dữ liệu, theo đúng điều ticket 14 đòi. Khung cố định trong code chỉ nói cách làm: toàn văn **Bài gốc** là căn cứ duy nhất, và lí do phải chỉ ra chi tiết sai. Hệ quả: sửa **Hướng dẫn** có thể làm yếu chốt chặn. Bản trong dữ liệu khởi tạo là bản tạm; ticket 14 soạn bản đầy đủ.
- **Kiểm chứng** đọc đúng phần toàn văn **Biên tập** đã đọc (tối đa 20.000 ký tự đầu), để không bắt lỗi chi tiết mà **Biên tập** chưa từng thấy.
- Việc kiểm tra "**Chuyên mục** chưa có **Kênh đăng**" được chuyển lên trước **Biên tập**, để không tốn lời gọi LLM cho **Bản tin** không có nơi phát.
- `KyDaChay.phien_ban_huong_dan` đổi tên thành `phien_ban_huong_dan_bien_tap`, đi cùng `phien_ban_huong_dan_kiem_chung`.

Điều chưa kiểm được bằng máy: **Kiểm chứng** có thật sự bắt được sai lệch về số liệu, tên, ngày tháng và tiêu đề nói quá hay không. LLM theo kịch bản chỉ chứng minh dây chuyền xử lí đúng kết luận của nó; căn cứ về chất lượng hiện chỉ có lần chạy thật ở trên. "Dùng cấu hình model riêng" cũng chỉ thấy ở lệnh `chay-ky` (biến `MODEL_KIEM_CHUNG`), chưa có test.

Ghi chú cho các ticket sau:

- Ticket 15: đo khả năng bắt chi tiết bịa của **Kiểm chứng**. Lần chạy thật cho thấy nó có thể bắt bẻ những chỗ rất nhỏ ("khoảng 400 USD" so với "400 USD"); nên đo cả tỉ lệ trả lại oan.
- Ticket 12: lượt **Kiểm chứng**, lí do và bản viết lại nằm ở bảng `luot_kiem_chung` theo **Tin**; **Tin** bị bỏ có `li_do_bo`. `KyDaChay.ban_tin` chỉ gồm **Tin** được phát.
- Ticket 09: **Kỳ** hỏng vì dưới ba **Tin** thì thử lại sẽ tạo **Kỳ** mới và **Biên tập** làm lại từ đầu.
- **Kiểm chứng** chạy lần lượt từng **Tin**. Với bảy **Tin** và `ds/deepseek-v4-pro` có thể mất 3–4 phút; chạy song song nếu thời gian trở thành vấn đề.
