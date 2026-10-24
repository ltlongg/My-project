# 08: Ảnh chụp và Bản tin dạng ảnh

**What to build:** **Bản tin** trên Telegram có hình dạng cuối cùng: một tin nhắn mở đầu nêu tên **Chuyên mục** và ngày, rồi mỗi **Tin** là một tin nhắn ảnh chụp **Bài gốc chính** kèm chú thích gồm tiêu đề, tóm tắt và link. Ảnh được chụp bằng Playwright; không chụp được thì dùng ảnh đại diện của bài; không có cả hai thì **Tin** vẫn được phát, không ảnh.

**Blocked by:** 04

**Status:** ready-for-human

- [x] Có một module "nhận địa chỉ, trả về ảnh" theo thứ tự: ảnh chụp trang, ảnh đại diện, không ảnh
- [x] Ảnh chụp thấy được tiêu đề và phần đầu bài, không bị bảng cookie che ở các trang phổ biến trong danh sách **Nguồn**
- [x] Trang chặn trình duyệt tự động, quá thời gian hoặc có tường phí thì rơi xuống ảnh đại diện, không làm hỏng **Kỳ**
- [x] **Bản tin** mở đầu bằng một tin nhắn nêu tên **Chuyên mục** và ngày
- [x] Mỗi **Tin** là một tin nhắn riêng; chú thích không vượt 1.024 ký tự
- [x] **Tin** "Cập nhật" hiện nhãn đó trong chú thích
- [x] Ảnh và nội dung đúng như đã gửi được lưu theo **Tin**, để xem lại sau
- [x] Bộ phát Telegram có test bằng dữ liệu đã ghi lại cho: có ảnh, không ảnh, chú thích sát giới hạn, và Telegram trả lỗi

## Comments

**2026-10-24, agent.** Code xong trên nhánh `feat/shortlisting`, chưa commit. 147 test xanh; mypy và ruff sạch. Code chính ở `src/siftly/images/` (`camera.py` là thứ tự rơi xuống, `screenshot.py` cùng `prepare_page.js` là bộ chụp Playwright, `preview.py` là ảnh đại diện), bộ phát ở `src/siftly/publishers/telegram.py`, migration `0006_story_images.py`. Test: `tests/test_story_images.py` (tại điểm "Chạy Kỳ"), `tests/test_screenshots.py` (Chromium thật, trang mẫu ở `tests/fixtures/pages/`), `tests/test_camera.py`, `tests/test_telegram_publisher.py`.

Cách chụp:

- **Khung cỡ điện thoại** 480×720, mật độ ×2, ra ảnh JPEG 960×1440, khoảng 100–220 KB. Đã thử cả khung máy tính 1024×768: khi Telegram thu về bề ngang điện thoại, chữ quá nhỏ để đọc.
- **Dọn trang** trước khi chụp: chặn tải script của các bảng hỏi cookie phổ biến (OneTrust, Cookiebot, Didomi, Sourcepoint…) và vài mạng quảng cáo, gỡ phần tử dính có chữ cookie/consent/privacy, gỡ lớp phủ che giữa màn hình, mở lại cuộn trang, cuộn tới `h1` của bài. Khi trang đã đứng yên thì cuộn lại một lần nữa (ảnh tải lười, quảng cáo nở ra làm bố cục dịch), làm trong suốt mọi phần tử dính còn lại như header hay thanh quảng cáo, chờ 0,5 giây rồi làm lại, để bắt các header kiểu "cuộn ngược thì hiện lại".
- **Không chụp, rơi xuống ảnh đại diện** khi trang trả mã từ 400 trở lên, khi tiêu đề trang hay `h1` giống trang kiểm tra bot ("Just a moment", "Human verification"…), khi có lớp phủ lớn che giữa màn hình kèm chữ kiểu đăng ký/đăng nhập/premium (tường phí), khi không có `h1` nào, và khi mở trang quá 20 giây. Hết thời gian chờ trang tải xong (8 giây) hay đứng yên (3 giây) thì vẫn chụp.
- **Ảnh đại diện** lấy theo thứ tự `og:image:secure_url`, `og:image`, `twitter:image`, được đổi sang JPEG, cạnh dài nhất không quá 1.280. Bỏ ảnh có cạnh ngắn dưới 200 hoặc dẹt hơn 3:1, vì đó thường là logo hay dải quảng cáo. Phần trong suốt thành nền trắng.

Đã thử thật tới đâu:

- **Bộ chụp ảnh thật trên 24 bài thật của 12 Nguồn** (hai bài mới nhất mỗi Nguồn), từ IP Singapore của máy phát triển: VnExpress, Thanh Niên, Dân trí, Tuổi Trẻ, GenK, The Verge, TechCrunch, CoinDesk, Wired, Bloomberg, Engadget, Ars Technica. 19 bài ra ảnh chụp, mỗi bài 4–13 giây. Tôi đã xem từng ảnh: thấy tiêu đề ở đầu ảnh, không có bảng cookie (The Verge có một thanh "Privacy Rights", đã được gỡ), không bị header che. Hai bài Engadget bị chặn (403) nên dùng ảnh đại diện. Hai bài Ars Technica (405) và một bài Bloomberg (403) không có ảnh nào, vì trang chặn luôn cả lời tải bằng httpx.
- Lỗi đã thấy và chưa sửa: tooltip "Chọn Báo Thanh Niên làm nguồn ưu tiên" vẫn lọt vào ảnh vì nó không phải phần tử dính. Bài Dân trí tràn ngang ở khung hẹp nên chữ bị cắt mép phải. Bài Bloomberg phần dưới mờ đi vì tường phí chèn trong bài; tiêu đề và đoạn đầu vẫn rõ.
- **Migration 0006** chạy trên một bản sao của cơ sở dữ liệu phát triển (đang ở 0004): nâng lên 0006, hạ xuống 0005 rồi nâng lại đều chạy. `alembic check` chỉ báo các bảng checkpoint của LangGraph, vốn nằm ngoài Alembic. Cơ sở dữ liệu phát triển **chưa** được nâng.
- **Chưa gửi gì tới Telegram thật.** `sendPhoto` dạng multipart mới chỉ được test bằng phản hồi mẫu.

Chuyển sang `ready-for-human` vì còn những việc cần chủ hệ thống:

- `docker compose up -d --wait` giờ dựng thêm dịch vụ `browser` (ảnh `mcr.microsoft.com/playwright:v1.64.1-noble`, khoảng 3,5 GB). Máy này không có sudo để cài thư viện hệ thống cho Chromium, nên đó là cách duy nhất chạy được ở đây. Đã thêm `BROWSER_URL=ws://127.0.0.1:3000/` vào `.env`.
- Chạy một **Kỳ** thật (`uv run siftly run tech`, lệnh này nâng cơ sở dữ liệu lên 0006 qua `siftly init` hoặc lần chạy đầu) và nhìn **Bản tin** trong nhóm Telegram thử: tin nhắn mở đầu, ảnh, chú thích, link, nhãn "Cập nhật".
- Xem qua các quyết định dưới đây.
- Commit.

Quyết định đã tự chọn, cần chủ hệ thống xác nhận:

- **Chromium chạy trong Docker, ứng dụng nối tới qua WebSocket** (`playwright run-server`), thay vì nạp trình duyệt vào tiến trình Python. Để trống `BROWSER_URL` thì tự mở Chromium cài bằng `playwright install`, dùng cho Windows hay macOS. Gói `playwright` được ghim `<1.65`, vì client và server phải cùng phiên bản; đổi phiên bản thì đổi cả ảnh trong `compose.yaml`. Trình duyệt chỉ được mở ở lần chụp đầu, và trình duyệt không mở được thì chỉ là ảnh rơi xuống ảnh đại diện, **Kỳ** không hỏng.
- **Chụp sau Kiểm chứng, chỉ cho Tin sắp phát.** **Bản tin** dưới ba **Tin** thì không chụp gì. Chụp tuần tự, nên 7 **Tin** tốn khoảng một phút.
- **Ảnh lưu trong Postgres**, bảng `story_images` (khoá là `story_id`): `kind` là `screenshot`, `preview` hoặc `none`, `data` là JPEG, `fallback_reason` là lí do phải dùng cách kém hơn, mỗi lí do một dòng. Chọn Postgres thay vì thư mục file vì dung lượng nhỏ (khoảng 3 MB mỗi ngày cho ba **Chuyên mục**) và sao lưu cùng phần còn lại. Có dòng `none` để **Kỳ** chạy tiếp không chụp lại một **Tin** đã gửi không ảnh.
- **"Nội dung đúng như đã gửi"** là `StoryContent` lưu kèm ảnh. Bộ phát Telegram dựng tin nhắn một cách tất định từ đó, nên không lưu riêng HTML đã gửi cho từng **Kênh đăng**.
- **Chú thích**: tiêu đề in đậm (kèm "Cập nhật: " nếu có), tóm tắt, rồi link hiện nguyên địa chỉ. Chữ hiện ra đúng bằng thứ `StoryContent.length` đếm, nên giới hạn Biên tập đang giữ vẫn đúng. Nếu vẫn vượt 1.024 (dữ liệu cũ chẳng hạn) thì cắt tóm tắt kèm "…", rồi tới tiêu đề, không bao giờ cắt link. **Tin** không ảnh là tin nhắn chữ cùng nội dung, cùng giới hạn. Tin nhắn không còn đánh số thứ tự, vì mỗi **Tin** được chuyển tiếp riêng.
- **Telegram từ chối một ảnh thì Kênh đăng đó lỗi**, như mọi lỗi Telegram khác; không gửi lại dạng chữ. Ảnh luôn là JPEG đã kiểm cỡ, nên rủi ro này thấp.

Ghi chú cho các ticket sau:

- Ticket 09: một **Bản tin** giờ là 1 + N tin nhắn. **Kênh đăng** lỗi giữa chừng thì nhóm đã nhận một phần, và thử lại sẽ gửi lại từ đầu. Cần nhớ tin nhắn nào đã gửi, hoặc chấp nhận trùng. Giới hạn của Telegram là khoảng 20 tin nhắn mỗi phút cho một nhóm; 8 tin nhắn liền nhau chưa chạm tới.
- Ticket 12: ảnh và lí do rơi xuống nằm ở `Story.image`; `fallback_reason` cho biết vì sao không chụp được trang.
- Ticket 14: Ars Technica, Bloomberg và Engadget chặn trình duyệt tự động từ IP Singapore; Ars và Bloomberg chặn cả httpx, nên **Tin** của họ sẽ không có ảnh. Có thể lấy ảnh từ `media:content` của RSS làm bậc thứ ba.
- Ticket 16: server cần thêm dịch vụ `browser`; nên đặt `mem_limit` và đo RAM khi chụp.
- Ticket 20: trang video YouTube có `h1` nên đi qua được bộ chụp này, nhưng chưa thử; có thể vướng hộp hỏi cookie của Google ở IP châu Âu.
- Ticket 22: nút 👍/👎 gắn vào từng tin nhắn ảnh qua `reply_markup` của `sendPhoto`.
- Ticket 27: dọn ảnh sau 90 ngày bằng cách đặt `story_images.data` về trống, giữ lại `kind`.

