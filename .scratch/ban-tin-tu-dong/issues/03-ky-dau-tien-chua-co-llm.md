# 03: Kỳ đầu tiên, chưa có LLM

**What to build:** Viên đạn dò đường của cả hệ thống. Một lệnh chạy một **Kỳ** cho một **Chuyên mục**: lấy **Bài gốc** từ một **Nguồn** RSS, lưu vào Postgres, và gửi vào một **Kênh đăng** Telegram một **Bản tin** thô gồm vài tiêu đề gốc kèm link. Chưa có LLM, chưa có ảnh, chưa có trang quản lí; **Chuyên mục**, **Nguồn** và **Kênh đăng** được nạp từ dữ liệu khởi tạo.

Ticket này đặt khung dự án (Python, Postgres, Docker Compose cho môi trường phát triển) và khuôn test tại điểm "Chạy Kỳ" mà mọi ticket sau dùng lại: **Nguồn** giả, **Kênh đăng** giả, đồng hồ giả, Postgres thật.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] Có một lối vào duy nhất "chạy một **Kỳ** cho **Chuyên mục** này tại thời điểm này"
- [x] Bộ thu thập RSS và bộ phát Telegram nằm sau hai giao diện chung cho mọi loại **Nguồn** và mọi loại **Kênh đăng**
- [x] **Bài gốc** được nhận diện bằng địa chỉ đã chuẩn hoá; chạy hai **Kỳ** liên tiếp không lưu trùng
- [x] Một **Kỳ** chỉ xét **Bài gốc** xuất hiện từ **Bản tin** trước của cùng **Chuyên mục**; lần đầu là 24 giờ gần nhất
- [x] Mỗi **Kỳ** được lưu lại với kết quả: đã phát, không phát, hoặc hỏng
- [x] Test tại điểm "Chạy Kỳ" khẳng định về thứ tới **Kênh đăng** giả và thứ được lưu, không gọi mạng
- [x] Bộ thu thập RSS và bộ phát Telegram có test riêng bằng dữ liệu đã ghi lại
- [x] Khi có token từ ticket 01, chạy lệnh thì tin nhắn xuất hiện trong nhóm Telegram thử
- [x] Có hướng dẫn ngắn để dựng môi trường và chạy test bằng một lệnh

## Comments

**2026-10-07, agent.** Đã làm xong phần code ở commit `2cde4f4`; 30 test xanh, mypy và ruff sạch. Chuyển sang `ready-for-human` vì tiêu chí còn lại cần token thật từ ticket 01: điền `TELEGRAM_BOT_TOKEN` và `TELEGRAM_CHAT_ID` vào `.env`, chạy `uv run bulletin khoi-tao` rồi `uv run bulletin chay-ky cong-nghe`, và xem tin nhắn có tới nhóm thử không.

Đã thử thật tới đâu: lệnh lấy được **Bài gốc** từ RSS của VnExpress, lưu vào Postgres và dựng được **Bản tin** 7 **Tin**; với token giả, Telegram trả về "Unauthorized" và **Kỳ** được lưu là hỏng kèm lí do. Phản hồi mẫu của Telegram trong `tests/fixtures/` được viết theo tài liệu Bot API, chưa phải ghi lại từ bot thật.

Ghi chú cho các ticket sau:

- Postgres của môi trường phát triển nghe ở cổng 54320, vì 5432 trên máy này đã có một Postgres khác. Dùng `127.0.0.1` thay cho `localhost`: trên Windows `localhost` thử IPv6 trước và chờ rất lâu.
- **Bài gốc** "xuất hiện" được tính theo giờ xuất bản mà **Nguồn** ghi (không có thì là lúc thu thập). Một bài ghi giờ trước **Bản tin** trước nhưng lên feed sau đó sẽ bị bỏ sót. Cần chủ hệ thống quyết định có tính theo lúc thu thập hay không; nên bàn cùng ticket 09, nơi việc thu thập tách khỏi **Kỳ**.
- Chuẩn hoá địa chỉ chưa gộp `http` với `https`, cũng chưa bỏ `www.`.
- **Bản tin** dài bị chia thành nhiều tin nhắn; nếu tin nhắn sau lỗi thì tin nhắn trước đã gửi rồi, và thử lại sẽ gửi trùng. Thuộc ticket 09 ("không bao giờ phát hai lần cho cùng một **Kỳ**").
- **Kỳ** bị ngắt giữa chừng (mất điện, tiến trình bị dừng) để lại một **Kỳ** chưa có kết quả; ticket 09 cần xử lí khi khởi động lại.

**2026-10-08, agent.** Đã chạy thật với token từ ticket 01: `uv run bulletin khoi-tao` rồi `uv run bulletin chay-ky cong-nghe`. **Kỳ** kết thúc "Đã phát" với 7 **Tin** từ RSS của VnExpress; Telegram nhận tin nhắn gửi vào nhóm thử. Đóng ticket. Các ghi chú cho ticket sau ở trên vẫn còn nguyên giá trị.
