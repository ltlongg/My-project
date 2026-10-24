# 09: Lịch, thử lại và thông báo riêng

**What to build:** Hệ thống tự chạy không cần ai bấm. Việc thu thập **Bài gốc** chạy định kỳ trong ngày; **Kỳ** của mỗi **Chuyên mục** tự chạy đúng giờ phát của nó theo giờ Việt Nam. **Kỳ** hỏng được thử lại sau 30 phút, tối đa ba lần. Khi một **Kỳ** hỏng hẳn hoặc không phát, bot nhắn riêng cho chủ hệ thống kèm lí do. Một **Nguồn** hỏng không làm hỏng **Kỳ**.

**Blocked by:** 03

**Status:** ready-for-human

- [x] **Kỳ** của một **Chuyên mục** tự chạy đúng giờ phát đã khai, theo múi giờ Asia/Ho_Chi_Minh
- [x] Việc thu thập chạy định kỳ, tách khỏi **Kỳ**; **Kỳ** dùng những **Bài gốc** đã thu thập
- [x] **Kỳ** hỏng được thử lại sau 30 phút, tối đa ba lần, rồi dừng
- [x] Một **Bản tin** không bao giờ được phát hai lần cho cùng một **Kỳ**, kể cả khi thử lại hoặc khởi động lại giữa chừng
- [x] Chủ hệ thống nhận tin nhắn riêng khi **Kỳ** hỏng hẳn hoặc không phát, có tên **Chuyên mục** và lí do
- [x] Lỗi của một **Nguồn** được ghi lại theo **Nguồn** và **Kỳ** vẫn chạy với các **Nguồn** còn lại
- [x] **Chuyên mục** đang tạm dừng không chạy **Kỳ**
- [x] Khởi động lại dịch vụ không làm mất lịch và không chạy bù hàng loạt các **Kỳ** đã lỡ
- [x] Test tại điểm "Chạy Kỳ" với đồng hồ giả phủ: đúng giờ, thử lại, dừng sau ba lần, thông báo, và **Nguồn** hỏng

## Comments

**2026-10-24, agent.** Code xong trên nhánh `feat/shortlisting`, chưa commit, nằm chung cây làm việc với ticket 08 (cũng chưa commit): `runner.py`, `publishers/telegram.py` và `tests/conftest.py` có thay đổi của cả hai ticket. 168 test xanh; mypy và ruff sạch. Code chính: `src/siftly/scheduler.py` (Lịch), `src/siftly/notifications.py` (thông báo riêng), `Runner.collect/retry/abandon` và khoá theo Chuyên mục ở `runner.py`, lệnh `siftly serve`, migration `0007_scheduling.py`. Test: `tests/test_scheduler.py` (18 test tại điểm "Chạy Kỳ" với đồng hồ giả), `tests/test_telegram_notifier.py`, thêm một test ở `tests/test_telegram_publisher.py`. Đã thử cố ý làm hỏng code (bỏ khoá, bỏ phần "bỏ qua phần đã gửi", đổi số lần thử, độ trễ, múi giờ…) và test đều bắt được.

Cách làm:

- **Lịch** (`siftly serve`) xét việc mỗi phút. Thu thập mọi **Nguồn** của **Chuyên mục** chưa tạm dừng mỗi giờ một lần. **Kỳ** vẫn thu thập thêm một lượt ngay trước khi gom **Tin**, nên `siftly run` chạy tay vẫn như cũ. **Kỳ** chỉ hỏng vì "Không thu thập được Nguồn nào" khi lượt đó hỏng hết *và* không có **Bài gốc** nào đã thu thập trước đó trong cửa sổ của **Kỳ**.
- Giờ phát là cột `sections.publish_time` (mặc định 08:00), tạm dừng là `sections.is_paused`. Chưa có chỗ sửa ngoài SQL; ticket 10 làm trang.
- **Thử lại** là chạy lại chính **Kỳ** đó (cùng dòng `runs`, `attempts` tăng dần), không tạo **Kỳ** mới. Những bước đã xong được dùng lại: ứng viên, **Bản tin**, ảnh. Riêng **Biên tập** chạy một lượt mới ở mỗi lần thử, vì lượt cũ đã kết thúc với lỗi thì làm tiếp chỉ trả lại đúng lỗi ấy.
- **Không phát hai lần**: bảng `deliveries` lưu theo **Bản tin** và **Kênh đăng** số phần đã tới nơi, sau từng tin nhắn. Thử lại hay chạy tiếp thì bỏ qua các phần đó. Giao diện bộ phát đổi thành `publish(address, bulletin, *, skip, on_sent)`. Với Telegram, mỗi tin nhắn là một phần.
- **Khoá**: suốt một **Kỳ**, `Runner` giữ khoá tư vấn của Postgres theo **Chuyên mục**. `siftly run` chạy tay khi Lịch đang chạy **Kỳ** đó, hoặc ngược lại, thì bên đến sau bị từ chối.
- **Thông báo riêng** là chữ thuần gửi tới `TELEGRAM_OWNER_ID`, mỗi **Kỳ** một lần (cột `runs.alerted_at`), ví dụ: "Bản tin Công nghệ 08:00 ngày 07/10/2026 không được phát: Kỳ hỏng sau 4 lần chạy. Lí do: …". Nhắn không được thì lượt sau nhắn lại.
- `siftly run` và `siftly serve` từ chối chạy khi lược đồ chưa ở phiên bản mới nhất.

Quyết định đã tự chọn, cần chủ hệ thống xác nhận:

- **"Tối đa ba lần" là ba lần thử lại**, tức tối đa bốn lần chạy: 8:00, 8:30, 9:00, 9:30, mỗi lần cách lần trước hỏng 30 phút.
- **Hạn chót 3 giờ sau giờ phát.** Dịch vụ chạy lại trong hạn thì **Kỳ** lỡ giờ được chạy muộn (khởi động lại lúc 10:30 thì **Bản tin** 8:00 phát lúc 10:30), **Kỳ** dở được chạy tiếp. Quá hạn thì **Kỳ** lỡ bị bỏ qua, không nhắn gì; **Kỳ** dở bị đánh dấu hỏng và có nhắn. Chỉ **Kỳ** gần nhất của mỗi **Chuyên mục** được xét.
- **Bản tin dưới ba Tin thì không thử lại** mà nhắn ngay, vì thử lại dùng đúng **Bản tin** ấy. Các lỗi thiết lập (chưa có **Nguồn**, **Kênh đăng**, **Hướng dẫn**) vẫn được thử lại, phòng khi chủ hệ thống sửa kịp.
- **Kỳ chạy tay** bằng `siftly run` mà hỏng thì Lịch đang chạy cũng thử lại và nhắn như **Kỳ** theo lịch.
- **Không nhắn** khi **Kỳ** đã phát nhưng có **Kênh đăng** lỗi; lỗi vẫn nằm ở `runs.reason`. Ticket chỉ yêu cầu nhắn khi hỏng hẳn hoặc không phát.
- **Tiến trình chết đúng lúc đang gửi một tin nhắn** thì khi chạy tiếp, tin nhắn ấy có thể bị gửi lại một lần, vì không biết nó đã tới chưa. Mọi trường hợp khác không gửi trùng.
- Migration đánh dấu các **Kỳ** có từ trước là đã nhắn, để Lịch không nhắn về chúng.

Chuyển sang `ready-for-human` vì còn những việc cần chủ hệ thống:

- `uv run siftly init` để nâng cơ sở dữ liệu phát triển lên 0007 (đang ở 0004; lệnh này cũng nâng qua 0005 và 0006 của ticket 07, 08).
- Mở cuộc trò chuyện riêng với bot và bấm Start, rồi chạy `uv run siftly serve` qua một giờ phát thật. Chưa gửi gì tới Telegram thật: thông báo riêng mới được test bằng phản hồi mẫu.
- Xem qua các quyết định trên.
- Commit (có thể tách hai commit 08 và 09, nhưng ba file kể trên mang thay đổi của cả hai).

Sự cố trong lúc làm: một lần thử lệnh `siftly serve` lỡ chạy thật trên cơ sở dữ liệu phát triển khoảng hai phút. Lược đồ ở đó còn là 0004, nên mọi lượt hỏng ngay ở câu truy vấn đầu: không **Kỳ** nào được tạo, không gì được gửi. Bước kiểm tra lược đồ nói trên được thêm vì lần này.

Ghi chú cho các ticket sau:

- Ticket 10: sửa giờ phát và tạm dừng chỉ là sửa `publish_time` và `is_paused`; Lịch đọc lại mỗi phút nên không cần khởi động lại. Đổi giờ phát sang một giờ đã qua trong ngày, trong vòng 3 giờ, thì Lịch chạy luôn một **Kỳ** cho giờ mới.
- Ticket 12: `runs.attempts`, `runs.retry_at`, `runs.alerted_at`, và `deliveries` (theo **Kênh đăng**: số phần đã gửi, đã phát trọn chưa, lỗi gần nhất).
- Ticket 13: **Kỳ** xem trước sẽ phải được Lịch bỏ qua (không thử lại, không nhắn), ví dụ đặt sẵn `alerted_at` hoặc thêm một cột riêng.
- Ticket 16: trên server, `siftly serve` là dịch vụ chạy lâu trong compose, cần `restart: unless-stopped`. Chỉ nên chạy một bản: khoá chặn được chạy trùng một **Kỳ**, nhưng hai bản sẽ cùng thu thập và thay nhau ghi log "đang chạy ở nơi khác".
- Ticket 18: khi phiên X hết hạn, thông báo riêng đã có sẵn `Notifier`.
- Ticket 22: webhook nhận **Phản hồi** chạy ở tiến trình khác; Lịch không đụng tới.

