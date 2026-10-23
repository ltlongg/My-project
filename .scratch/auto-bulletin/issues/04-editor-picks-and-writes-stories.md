# 04: Biên tập chọn và viết Tin tiếng Việt

**What to build:** **Bản tin** không còn là danh sách tiêu đề gốc. Agent **Biên tập** đọc các ứng viên của **Kỳ**, chọn 5–7 **Tin** đáng đọc nhất theo **Hướng dẫn** của **Chuyên mục**, và viết cho mỗi **Tin** một tiêu đề và một tóm tắt 4–6 câu bằng tiếng Việt từ toàn văn **Bài gốc**, kèm lí do chọn. Ở ticket này mỗi **Bài gốc** là một ứng viên **Tin**; việc gom và sơ tuyển đến sau.

Vòng agent viết bằng LangGraph theo ADR 0001; model theo kết quả ticket 02.

**Blocked by:** 02, 03

**Status:** done

- [x] Toàn văn của một **Bài gốc** loại bài báo được trích ra và lưu lại
- [x] **Biên tập** có công cụ đọc toàn văn một **Bài gốc** và công cụ tìm kiếm web; công cụ tìm kiếm thay được giữa Tavily và Brave
- [x] Mỗi **Tin** được chọn có tiêu đề, tóm tắt tiếng Việt, **Bài gốc chính** và lí do chọn, tất cả được lưu
- [x] Tên riêng và thuật ngữ chuyên ngành quen dùng được giữ nguyên tiếng Anh
- [x] Tiêu đề, tóm tắt và link của một **Tin** vừa trong 1.024 ký tự
- [x] **Tin** chỉ dẫn tới **Bài gốc** từ **Nguồn** đã khai; kết quả tìm kiếm web không trở thành **Tin**
- [x] **Hướng dẫn** của **Biên tập** được đọc từ dữ liệu theo **Chuyên mục**, không viết cứng trong code; **Kỳ** ghi lại phiên bản đã dùng
- [x] Kết quả có cấu trúc từ LLM được kiểm tra bằng code; kết quả hỏng được xử lí như một lỗi của **Kỳ**, không phát ra ngoài
- [x] Trạng thái của vòng agent được lưu để một **Kỳ** bị gián đoạn chạy tiếp được
- [x] Test tại điểm "Chạy Kỳ" với LLM trả lời theo kịch bản phủ các hành vi trên

## Comments

**2026-10-08, agent.** Đã làm xong phần code, chưa commit; 74 test xanh, mypy và ruff sạch. Vòng agent ở `src/bulletin/agents/editor.py`, test tại điểm "Chạy Kỳ" ở `tests/test_editor.py`.

Đã thử thật tới đâu: một **Kỳ** với RSS của VnExpress, bộ lấy nội dung thật và `cx/gpt-5.6-luna`, trên cơ sở dữ liệu test, **Kênh đăng** thay bằng lệnh in ra màn hình. Kết quả "Đã phát" với 6 **Tin** tiếng Việt, chọn từ 17 **Bài gốc**, đọc toàn văn 7 bài, hai lời gọi LLM, khoảng 20 giây. Tên riêng và thuật ngữ được giữ nguyên (Surface Laptop Ultra, RTX Spark, CUDA, wafer, startup). **Tin** dài nhất 876 ký tự. **Biên tập** không gọi tìm kiếm web lần nào trong lần chạy đó; Tavily và Brave mới được gọi thật một lần mỗi bên để ghi phản hồi mẫu cho test.

Chuyển sang `ready-for-human` vì ba việc cần chủ hệ thống:

- Chưa gửi **Bản tin** kiểu mới vào nhóm Telegram thử. Cơ sở dữ liệu phát triển đã được nâng cấp (`uv run bulletin init`); chạy `uv run bulletin run tech` rồi xem tin nhắn trong nhóm.
- Xem qua các quyết định dưới đây.
- Commit.

Quyết định đã tự chọn, cần chủ hệ thống xác nhận:

- **Số Tin.** Code chỉ chặn bản nộp có nhiều hơn số **Tin** tối đa của **Chuyên mục**. Mức 5 là lời dặn trong đề bài ("chọn từ 5 đến 7, chỉ chọn ít hơn khi không đủ **Bài gốc** đáng đọc"), không bị ép: ép thì ngày ít tin **Biên tập** phải chọn cả tin ngoài phạm vi.
- **1.024 ký tự** được đếm trên tiêu đề, tóm tắt và nguyên link, cách nhau một dòng trống, theo đơn vị UTF-16 như Telegram đếm. Cách đếm này dư an toàn nếu ticket 08 giấu link sau chữ.
- **Bản tin trên Telegram** vẫn là một tin nhắn (tự chia khi quá 4.096 ký tự), mỗi **Tin** gồm tiêu đề đậm gắn link và tóm tắt. Với 6 **Tin** nó đã chia thành hai tin nhắn. Mỗi **Tin** một tin nhắn là việc của ticket 08.
- **Ứng viên** là 30 **Bài gốc** mới nhất của **Kỳ**, cho tới khi có sơ tuyển (ticket 07).
- **Bản nộp hỏng** được trả lại cho **Biên tập** kèm lí do; hỏng ba lần, hoặc quá 40 lời gọi LLM mà chưa nộp, thì **Kỳ** hỏng và không có gì được phát. Một **Tin** hỏng làm cả bản nộp bị trả lại.
- Ngoài các tiêu chí của ticket, code còn trả lại **Tin** viết về **Bài gốc** chưa đọc toàn văn, tóm tắt không phải tiếng Việt, và tiêu đề hay tóm tắt có chèn link.
- **Hướng dẫn** của **Biên tập** cho công nghệ trong dữ liệu khởi tạo là bản tạm, đủ để chạy; ticket 14 soạn bản đầy đủ. Quy tắc chung cho mọi **Chuyên mục** (tiếng Việt, 4–6 câu, giữ tên riêng, giới hạn độ dài) nằm trong khung cố định của code, không nằm trong **Hướng dẫn**.

Điều chưa kiểm được bằng máy: tiêu chí giữ nguyên tên riêng và thuật ngữ tiếng Anh. LLM theo kịch bản không chứng minh được điều này; căn cứ hiện có là lần chạy thật ở trên. Bộ đánh giá agent (ticket 15) nên đo nó.

Ghi chú cho các ticket sau:

- Ticket 05: bảng `guidelines` đã có cột vai trò và cho phép để trống **Chuyên mục**, sẵn cho **Hướng dẫn** chung của **Kiểm chứng**.
- Ticket 09: `Runner.resume` (lệnh `run --resume`) chỉ chạy tiếp **Kỳ** gần nhất chưa có kết quả. **Kỳ** hỏng vì LLM lỗi giữa chừng vẫn còn trạng thái đã lưu, nhưng lần thử lại hiện tạo **Kỳ** mới và **Biên tập** làm lại từ đầu (toàn văn đã lưu thì không tải lại). **Kỳ** bị dừng sau khi **Bản tin** đã lưu sẽ phát lại khi chạy tiếp, dù có thể đã gửi dở.
- Ticket 12: chưa ghi vết lên Langfuse.
- Ticket 27: trạng thái của vòng agent nằm trong ba bảng `checkpoints`, `checkpoint_blobs`, `checkpoint_writes` do LangGraph tự tạo (ngoài Alembic, tạo trong `upgrade`), theo mã `run-<id>-editor`. Chúng chứa cả toàn văn đã đọc và chưa có gì dọn.
- Không lấy được toàn văn một **Bài gốc** thì **Biên tập** được báo và chọn bài khác; lỗi đó chưa được lưu theo **Bài gốc**.

**2026-10-20, agent.** Đã chạy thật trên cơ sở dữ liệu phát triển: `uv run bulletin run tech` kết thúc "Đã phát" với 5 **Tin** tiếng Việt gửi vào nhóm Telegram thử, đọc toàn văn 7 **Bài gốc**, khoảng 30 giây; tên riêng giữ nguyên (DHS, Claude Code, Apollo Research, Petal, NorthPoint Development). Chủ hệ thống chọn đóng ticket và chấp nhận các quyết định ở trên. Lần chạy ngay trước đó hỏng vì proxy LLM trên máy chưa bật ("Connection error"): **Kỳ** được ghi là hỏng, không có gì được phát, đúng như mong đợi; ticket 09 sẽ lo phần thử lại.
