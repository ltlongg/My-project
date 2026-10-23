# 06: Gom Tin và không phát lại

**What to build:** Người đọc không thấy một chuyện hai lần. Các **Bài gốc** cùng nói về một sự kiện được gom thành một ứng viên **Tin** trước khi tới **Biên tập**, và **Biên tập** chọn một **Bài gốc chính** trong số đó, ưu tiên nơi đưa tin đầu tiên hoặc nguồn gốc nhất. Ứng viên trùng với một **Tin** đã phát của cùng **Chuyên mục** bị loại, trừ khi có diễn biến mới đáng kể; khi đó nó được phát với nhãn "Cập nhật".

**Blocked by:** 04

**Status:** ready-for-human

- [x] Nhiều **Bài gốc** về cùng một sự kiện, kể cả khác ngôn ngữ, thành một ứng viên **Tin**
- [x] Một **Tin** có nhiều **Bài gốc** và đúng một **Bài gốc chính**
- [x] Ứng viên trùng với **Tin** đã phát của cùng **Chuyên mục** không xuất hiện lại
- [x] Ứng viên có diễn biến mới so với **Tin** đã phát được phát với nhãn "Cập nhật" và liên kết với **Tin** trước
- [x] **Tin** của **Kỳ** xem trước hoặc **Kỳ** không phát không được tính là đã phát
- [x] Việc so độ giống nghĩa dùng vector nhúng theo lựa chọn ở ticket 02, lưu trong Postgres
- [x] Test tại điểm "Chạy Kỳ" phủ: gom, không gom nhầm hai sự kiện khác nhau cùng chủ đề, không phát lại, và "Cập nhật"

## Comments

**2026-10-20, agent.** Code xong, chưa commit. 107 test xanh; mypy và ruff sạch. Code chính ở `src/bulletin/clustering.py`, bộ nối tới dịch vụ nhúng ở `src/bulletin/embeddings/`. Test tại điểm "Chạy Kỳ" ở `tests/test_clustering.py`. Số đo và lí do chọn ngưỡng ở `docs/clustering.md`.

Đã thử thật tới đâu:

- **Model nhúng.** `BAAI/bge-m3` chạy trong Text Embeddings Inference (dịch vụ `embeddings` trong `compose.yaml`), nhúng 370 mục từ 8 feed công nghệ Việt và Anh. Lựa chọn của ticket 02 được giữ.
- **Hai Kỳ thật** trên một cơ sở dữ liệu riêng: 7 **Nguồn** RSS thật, **Biên tập** là `cx/gpt-5.6-luna`, **Kiểm chứng** là `ds/deepseek-v4-pro`, **Kênh đăng** thay bằng lệnh in. Cả hai "Đã phát" với 7 **Tin**, mất 164 và 227 giây. **Kỳ** đầu gom 69 **Bài gốc** thành 66 ứng viên, trong đó có hai cụm Việt–Anh. **Kỳ** sau không có bài nào giống **Tin** đã phát (cao nhất 0,61).
- **Kịch bản bán thật cho nhánh "đã phát".** Bài gốc, toàn văn, model nhúng và LLM đều thật; chỉ lịch xuất hiện là sắp đặt. Bài Dân trí về iPhone Duo và bài TechCrunch về nhà máy hạt nhân của Amazon đều bị đánh dấu trùng với **Tin** đã phát ở **Kỳ** trước. Khi còn ứng viên khác, **Biên tập** bỏ qua cả hai. Khi bài Dân trí là ứng viên duy nhất, nó chọn bài đó làm "Cập nhật", kèm lí do có căn cứ (chi tiết mới về các đại lý Việt Nam).
- **Migration 0004** chạy trên một bản sao của cơ sở dữ liệu phát triển: 12/12 **Tin** cũ có ứng viên gồm **Bài gốc chính** của chúng; hạ cấp rồi nâng lại đều chạy. Cơ sở dữ liệu phát triển đã được nâng lên 0004.

Chuyển sang `ready-for-human` vì còn bốn việc cần chủ hệ thống:

- Chưa gửi **Bản tin** nào vào nhóm Telegram thử, và chưa thấy nhãn "Cập nhật" trên một **Bản tin** thật. Cách hiển thị nhãn chỉ có test.
- `docker compose up -d --wait` giờ dựng thêm dịch vụ `embeddings`. Trên máy này model đã nằm sẵn trong volume `myproject_nhung`; máy mới phải tải khoảng 2,3 GB. Khi chạy, dịch vụ chiếm khoảng 3,2 GB trong 3,9 GB RAM mà Docker đang có.
- Xem qua các quyết định dưới đây.
- Commit.

Quyết định đã tự chọn, cần chủ hệ thống xác nhận:

- **Phân biệt "trùng" với "có diễn biến mới" là việc của Biên tập, không phải luật trong code.** Vector nhúng chỉ biết hai bài nói cùng một chuyện, không biết bài sau có gì mới, và đây là phán đoán nên thuộc về agent (ADR 0001). **Gom Tin** đánh dấu ứng viên giống một **Tin** đã phát và đưa kèm tiêu đề, tóm tắt của **Tin** đó. **Biên tập** được dặn bỏ qua, trừ khi có diễn biến mới đáng kể. Code đảm bảo mọi **Tin** từ ứng viên đã đánh dấu đều mang nhãn "Cập nhật" và liên kết tới **Tin** trước. Hệ quả: một **Biên tập** kém có thể phát lại chuyện cũ dưới nhãn "Cập nhật", nhưng không bao giờ phát lại như tin mới.
- **Dịch vụ nhúng riêng.** Text Embeddings Inference chạy trong Docker với endpoint `/v1/embeddings` tương thích OpenAI, thay vì nạp model vào tiến trình Python, để ứng dụng không phải kéo torch hay onnxruntime về. Có ba biến mới: `EMBEDDING_BASE_URL`, `EMBEDDING_MODEL`, `EMBEDDING_API_KEY`; để trống thì dùng dịch vụ trong compose. Dịch vụ lỗi thì **Kỳ** hỏng với lí do "Gom Tin gặp lỗi: …", trước khi gọi LLM nào.
- **Nhúng tiêu đề kèm mô tả RSS.** Chỉ tiêu đề thì hầu hết các cặp khác ngôn ngữ không đủ giống (bảng ở `docs/clustering.md`). Bộ thu thập RSS giờ lưu thêm mô tả (tối đa 500 ký tự) và giải mã thực thể HTML trong tiêu đề, vì feed Thanh Niên gửi nguyên "h&agrave;ng". **Biên tập** cũng thấy mô tả trong danh sách ứng viên.
- **Ngưỡng 0,78, gom theo liên kết đầy đủ.** Mọi cặp trong một nhóm đều phải đủ giống, để tránh gom dây chuyền. Cùng ngưỡng đó dùng để đối chiếu với **Tin** đã phát.
- **Chỉ đối chiếu với Tin đã phát trong 7 ngày.** Chuyện cũ hơn mà xuất hiện lại thường là sự kiện mới cùng chủ đề, ví dụ đời điện thoại năm sau.
- **"Đã phát"** nghĩa là **Kỳ** có kết quả "đã phát" và **Tin** không bị **Kiểm chứng** bỏ. **Kỳ** hỏng vì mọi **Kênh đăng** đều lỗi không làm dịch mốc, nên **Bài gốc** của nó được xét lại như chuyện mới.
- **Tin chỉ được viết từ Bài gốc chính**, vì **Kiểm chứng** chỉ đối chiếu với nó. **Biên tập** đọc được các **Bài gốc** khác trong ứng viên, nhưng không được đưa chi tiết của chúng vào **Tin**. Mỗi ứng viên chỉ thành nhiều nhất một **Tin**; nộp hai **Tin** từ một ứng viên thì bị trả lại.
- **Ứng viên được lưu theo Kỳ** (bảng `candidates`, `candidate_articles`), và mỗi **Tin** trỏ tới ứng viên của nó (`stories.candidate_id`). **Bài gốc** của **Tin** là **Bài gốc** của ứng viên. Quan hệ "Cập nhật" suy ra từ `candidates.published_story_id`, không có cột riêng. **Kỳ** chạy tiếp dùng lại ứng viên đã lưu, kể cả khi dịch vụ nhúng đang tắt.
- **Giới hạn 30 giờ đếm theo ứng viên**, không còn theo **Bài gốc**. Trước khi gom có thêm một trần 500 **Bài gốc** mới nhất.
- **Nhãn** hiện là "Cập nhật: " đứng trước tiêu đề, và được tính vào giới hạn 1.024 ký tự.
- Biến môi trường để trống giờ được coi như chưa đặt (`env_ignore_empty`), để chép nguyên `.env.example` không ghi đè giá trị mặc định bằng chuỗi rỗng.

Điều chưa kiểm được bằng máy:

- Ngưỡng 0,78 mới được đo trên một ngày dữ liệu (310 **Bài gốc**, phần lớn từ báo Việt). Bài dịch lại từ một bài tiếng Anh đôi khi vẫn dưới ngưỡng.
- Chất lượng phán đoán "Cập nhật" của **Biên tập** chỉ có căn cứ từ hai lần chạy ở trên. LLM theo kịch bản chỉ chứng minh dây chuyền xử lí đúng lựa chọn của nó.
- **Kỳ** xem trước chưa tồn tại. Quy tắc "chỉ **Kỳ** đã phát mới được tính" sẽ loại nó, miễn là ticket 13 không ghi **Kỳ** xem trước là "đã phát".

Ghi chú cho các ticket sau:

- Ticket 07: thêm điểm vào bảng `candidates`; "số **Bài gốc**" là số dòng của ứng viên trong `candidate_articles`. Hiện chỉ 30 ứng viên mới nhất được lưu, trong khi 07 đòi lưu cả ứng viên bị loại.
- Ticket 12: ứng viên của một **Kỳ** là các "**Tin** được cân nhắc"; `candidates.published_story_id` cho biết ứng viên nào trùng chuyện đã phát.
- Ticket 13: **Kỳ** xem trước không được có kết quả "đã phát", hoặc `clustering.cluster` phải loại nó ra.
- Ticket 14: feed Tuổi Trẻ ghi giờ xuất bản kiểu `10/18/2026 2:07:00 PM`, feedparser không đọc được. Bộ thu thập coi bài không có giờ là vừa xuất hiện, nên lần đầu thêm feed này, mọi bài cũ của nó đều thành **Bài gốc** mới. Lỗi có từ ticket 03; nên sửa trước khi đưa Tuổi Trẻ vào **Nguồn** khởi đầu.
- Ticket 15: đo lại ngưỡng gom trên nhiều ngày, và đo phán đoán "Cập nhật" của **Biên tập**: bỏ qua bài kể lại, chọn bài có diễn biến mới.
- Ticket 16: server cần thêm khoảng 3,5 GB RAM cho dịch vụ nhúng; nếu thiếu thì lùi về `intfloat/multilingual-e5-small` và đo lại ngưỡng. Mặc định TEI hết bộ nhớ ngay lúc làm nóng model; `compose.yaml` đã đặt `--max-batch-tokens 2048 --auto-truncate`.
- "Ứng viên **Tin**" giờ là một thứ được lưu và các ticket sau dựa vào nó, nhưng chưa có trong `CONTEXT.md`. Nên thêm nếu chủ hệ thống đồng ý với tên này.
