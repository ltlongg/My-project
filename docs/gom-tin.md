# Gom Tin: so độ giống nghĩa bằng vector nhúng

Ghi chú của ticket 06, đo ngày 2026-10-20. Đọc trước khi đổi ngưỡng, đổi model nhúng hay đổi phần văn bản được nhúng.

## Cách làm

**Gom Tin** là bước cố định (ADR 0001), chạy sau thu thập và trước **Biên tập**, ở `src/bulletin/gom_tin.py`.

1. Mỗi **Bài gốc** được nhúng một lần bằng `BAAI/bge-m3`, từ tiêu đề cộng mô tả RSS. Vector được lưu ở `bai_goc.vector_nhung` (pgvector), kèm tên model. Đổi model thì các **Bài gốc** cần dùng được nhúng lại.
2. Postgres tìm các cặp **Bài gốc** của **Kỳ** có độ giống (cosine) từ `NGUONG_CUNG_SU_KIEN` = 0,78 trở lên.
3. Gom theo liên kết đầy đủ: hai cụm chỉ nhập làm một khi *mọi* cặp giữa chúng đều đủ giống, nên A giống B, B giống C mà A không giống C thì không thành một cụm. Mỗi cụm là một ứng viên **Tin**.
4. Mỗi ứng viên được đối chiếu với các **Tin** đã phát của cùng **Chuyên mục** trong 7 ngày, theo cùng ngưỡng. Chỉ **Tin** đã tới người đọc mới được tính: **Kỳ** có kết quả "đã phát", và **Tin** không bị **Kiểm chứng** bỏ.
5. **Biên tập** thấy các ứng viên, mỗi ứng viên kèm **Tin** đã phát mà nó giống, nếu có. Nó chọn **Bài gốc chính** trong ứng viên. Với ứng viên trùng **Tin** đã phát, nó bỏ qua, hoặc phát như một **Tin** "Cập nhật" khi có diễn biến mới đáng kể.

Vector nhúng chỉ biết hai bài *nói về cùng một chuyện*, không biết bài sau có *gì mới*. Vì vậy việc phân biệt tin trùng với diễn biến mới là phán đoán của **Biên tập**, không phải luật trong code.

## Đo trên RSS thật

Dữ liệu: 370 mục từ 8 feed công nghệ (VnExpress hai mục, Tuổi Trẻ, Thanh Niên, Dân trí, The Verge, TechCrunch, Ars Technica), còn 310 **Bài gốc** sau khi bỏ link trùng.

### Nhúng gì: tiêu đề, hay tiêu đề cộng mô tả

| Cặp | Chỉ tiêu đề | Tiêu đề + mô tả | Cùng sự kiện? |
| --- | --- | --- | --- |
| Dân trí "Apple xác nhận sự kiện 28/10, MacBook Pro OLED…" / The Verge "Apple teases MacBook Pro event next week" | 0,69 | 0,84 | có |
| VnExpress "Musk nói sẽ tặng cổ phiếu SpaceX…" / The Verge "Elon Musk's proposed SpaceX stock giveaway…" | < 0,65 | 0,81 | có |
| The Verge "Amazon is funding a new nuclear plant in Indiana" / TechCrunch "Amazon to fund 12 small nuclear reactors…" | < 0,65 | 0,79 | có |
| Tuổi Trẻ / Dân trí: Vietnam Post nhận đầu số 075 | 0,78 | 0,82 | có |
| Thanh Niên "Apple dời lịch giao hàng iPhone Duo sang năm 2027" / Dân trí "Khách mua iPhone Duo có thể phải chờ đến Tết…" | 0,83 | 0,83 | có |
| Thanh Niên "Samsung ra mắt Galaxy F70…" / Dân trí "Samsung ra mắt bộ đôi Galaxy A08 và A18…" | – | 0,74 | không |
| Thanh Niên "Galaxy S27 có thể ra mắt sớm hơn…" / Dân trí "Lộ diện các phiên bản của loạt Galaxy S27…" | – | 0,75 | không |

Chỉ có tiêu đề thì hầu hết các cặp khác ngôn ngữ, và cả cặp Anh–Anh về Amazon, không đủ giống. Thêm mô tả đẩy chúng lên 0,79–0,84, trong khi các cặp khác sự kiện cùng chủ đề vẫn dưới 0,76. Cái giá là thời gian nhúng gấp đôi (xem dưới).

### Chọn ngưỡng

Gom 310 **Bài gốc** theo liên kết đầy đủ, nhúng tiêu đề + mô tả:

- **0,76**: 15 cụm nhiều bài. So với 0,78, thêm hai cụm: bản tin tổng hợp "Điểm tuần" gom với một tin lẻ (sai), và hai bài Dân trí về lỗi phai màu của iPhone 18 Pro Max (nhiều khả năng đúng). Ngoài ra tin đồn "MacBook OLED" của Thanh Niên nhập vào cụm sự kiện ngày 28/10.
- **0,78** (chọn): 13 cụm nhiều bài. Phần lớn đúng là cùng một sự kiện, trong đó ba cụm khác ngôn ngữ. Hai cụm đáng ngờ: hai bài Dân trí khác nhau về chuyện "tác phẩm AI bị sao chép", và một bài Thanh Niên về "công cụ của người sáng tạo" bị gom với tin laptop RTX Spark.
- **0,80**: 10 cụm nhiều bài. Mất cặp Amazon, cặp cùng sự kiện, cùng tiếng Anh, ở hai báo khác nhau.

Gom thiếu thì **Biên tập** thấy hai ứng viên cho một chuyện; **Hướng dẫn** dặn nó không chọn cả hai. Gom nhầm thì hai chuyện khác nhau chỉ còn một chỗ trong **Bản tin**. Ngưỡng 0,78 đứng giữa hai cái hại này. Bài dịch lại một bài khác ngôn ngữ đôi khi vẫn dưới ngưỡng, ví dụ VnExpress "Dùng AI 'độ' giao diện smart TV" và bài gốc tiếng Anh của TechCrunch.

### Chạy thật

- Hai **Kỳ** trên 7 **Nguồn** công nghệ thật: **Kỳ** đầu gom 69 **Bài gốc** thành 66 ứng viên, gồm hai cụm Việt–Anh (sự kiện MacBook, cổ phiếu SpaceX). **Bài gốc** của **Kỳ** sau giống nhất với **Tin** đã phát chỉ ở mức 0,61, nên không ứng viên nào bị đánh dấu.
- Kịch bản bán thật (Bài gốc, toàn văn, model nhúng và LLM đều thật, chỉ lịch xuất hiện là sắp đặt): sau khi **Tin** về iPhone Duo và về nhà máy hạt nhân của Amazon được phát, bài Dân trí và bài TechCrunch về hai chuyện đó ở **Kỳ** sau đều bị đánh dấu là đã phát. Khi có ứng viên khác để chọn, **Biên tập** bỏ qua cả hai. Khi bài Dân trí là ứng viên duy nhất, nó chọn bài đó làm "Cập nhật", với lí do là chi tiết mới về các đại lý Việt Nam hết suất đặt cọc.

## Tài nguyên

Đo trên máy phát triển (Intel i5-8400H, không GPU, Docker được 3,9 GB RAM), Text Embeddings Inference `cpu-1.8`:

- Lần đầu tải 2,3 GB model; tải từ Hugging Face mất khoảng 7 phút, có lúc chậm hẳn lại.
- Khi chạy chiếm khoảng 3,2 GB RAM. Với cấu hình mặc định, TEI hết bộ nhớ ngay lúc làm nóng model, vì nó làm nóng với lô 16.384 token. `compose.yaml` hạ xuống 2.048 token và bật `--auto-truncate`.
- Nhúng: khoảng 160 ms/bài với chỉ tiêu đề, 350 ms/bài với tiêu đề + mô tả. Vài trăm **Bài gốc** mới mỗi ngày tốn chừng hai phút; một **Kỳ** chỉ nhúng những bài chưa có vector.

Server ở ticket 16 cần thêm khoảng 3,5 GB RAM cho dịch vụ này. Nếu không đủ thì lùi về `intfloat/multilingual-e5-small` (384 chiều, khoảng 0,5 GB), như ghi chú ở ticket 02. Model đó chưa được đo, và ngưỡng phải đo lại.

## Khi nào đo lại

Đổi model nhúng, đổi phần văn bản được nhúng (`van_ban_nhung`), hoặc thêm loại **Nguồn** có văn bản khác hẳn RSS, như bài đăng X hay video YouTube. Script đo đã dùng không nằm trong repo: lấy RSS, nhúng, in các cặp theo từng khoảng độ giống, rồi gom ở vài ngưỡng. Ticket 15 nên biến việc này thành một phần của bộ đánh giá.
