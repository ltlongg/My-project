# 11: Quản lí Nguồn và Kênh đăng

**What to build:** Chủ hệ thống khai **Nguồn** và **Kênh đăng** trên trang quản lí và gắn chúng vào **Chuyên mục**. Trước khi lưu một **Nguồn** RSS, họ bấm thử và thấy vài **Bài gốc** nó trả về. Trước khi dùng một **Kênh đăng**, họ gửi một tin nhắn thử. Họ thấy tình trạng của từng **Nguồn** để phát hiện **Nguồn** chết.

**Blocked by:** 10

**Status:** ready-for-human

- [x] Thêm, sửa, tắt và bật lại được **Nguồn** loại RSS
- [x] Bấm thử một **Nguồn** trả về vài **Bài gốc** mẫu hoặc một thông báo lỗi dễ hiểu, không lưu gì
- [x] Mỗi **Nguồn** hiện lần lấy gần nhất, số **Bài gốc** gần đây và lỗi gần nhất
- [x] Một **Nguồn** gắn được vào nhiều **Chuyên mục**; **Bài gốc** của nó vẫn chỉ được lưu một lần
- [x] **Nguồn** đang tắt không được thu thập và không góp ứng viên cho **Kỳ**
- [x] Thêm, sửa, tắt được **Kênh đăng** loại Telegram, và gắn vào một hay nhiều **Chuyên mục**
- [x] Gửi được một tin nhắn thử tới một **Kênh đăng** và thấy kết quả thành công hoặc lỗi
- [x] Một **Chuyên mục** phát **Bản tin** tới mọi **Kênh đăng** đang bật của nó
- [x] Màn hình thêm **Nguồn** và **Kênh đăng** nhận được loại mới mà không phải viết lại, để các ticket X, YouTube, **Bảng xếp hạng**, Zalo, Facebook cắm vào
- [x] Test gọi API thật phủ các hành vi trên

## Comments

**2026-10-24, agent.** Code xong trên nhánh `feat/shortlisting`, chưa commit, nằm chung cây làm việc với ticket 10 (cũng chưa commit). 239 test xanh (40 test mới ở `tests/test_admin_sources_and_channels.py`, 2 ở `tests/test_telegram_publisher.py`); mypy, ruff, `tsc` và oxlint sạch. Đã thử cố ý làm hỏng bốn chỗ lọc **Nguồn** và **Kênh đăng** đang tắt trong `Runner`, và mỗi lần đều có test bắt được. Đã chạy thật `siftly admin` trên một cơ sở dữ liệu thử riêng (đã xoá sau đó), với token bot giả, và đi qua bằng Chromium: lấy thử một địa chỉ sai dạng, một feed không tồn tại và feed thật của VnExpress (trả 53 **Bài gốc**, hiện 5 bài mới nhất), thêm **Nguồn**, thêm trùng địa chỉ, tắt ở danh sách, thêm **Kênh đăng** và gửi tin nhắn thử (Telegram trả "Unauthorized" vì token giả), rồi xem khối **Nguồn** và **Kênh đăng** ở trang **Chuyên mục**. Trang được chụp ở 1280px và 360px, sáng và tối, và không trang nào cuộn ngang.

Cách làm:

- **Dữ liệu**: migration 0009 thêm `is_enabled` cho `sources` và `channels`, mặc định bật. `Section.enabled_sources` và `Section.enabled_channels` là thứ `Runner` dùng: thu thập định kỳ, thu thập trước **Kỳ**, lấy **Bài gốc** cho Gom Tin và phát chỉ đi qua những cái đang bật. **Bài gốc** thấy ở cả một **Nguồn** tắt lẫn một **Nguồn** bật vẫn vào **Kỳ**. **Kỳ** không còn **Nguồn** hay **Kênh đăng** nào đang bật thì hỏng với lí do "… chưa có Nguồn nào đang bật" hay "… chưa có Kênh đăng nào đang bật".
- **API**: `GET/POST /api/sources`, `GET/PATCH /api/sources/{id}`, `POST /api/sources/test`, `GET /api/sources/kinds`, và cùng bộ ấy cho `/api/channels`. Gắn vào **Chuyên mục** là trường `section_ids` của **Nguồn** hay **Kênh đăng**. Trùng địa chỉ, sai dạng, hay **Chuyên mục** không có đều trả 422 với lời nhắn theo trường, như **Chuyên mục**.
- **Bấm thử**: `siftly admin` giờ có bộ thu thập RSS và, khi có `TELEGRAM_BOT_TOKEN`, bộ phát Telegram. Lấy thử gọi đúng bộ thu thập mà Lịch dùng, không lọc theo thời gian, và trả 5 **Bài gốc** mới nhất cùng tổng số. Lỗi trả về là lời nhắn của bộ thu thập, như "… trả về mã 404" hay "… không phải là RSS hay Atom". Tin nhắn thử là phương thức mới `send_test` của giao diện bộ phát, gửi chữ thuần.
- **Tình trạng Nguồn**: lần lấy gần nhất là `last_fetched_at` sẵn có (ghi cả khi lỗi), lỗi gần nhất là `last_error`, và "gần đây" là số **Bài gốc** của **Nguồn** xuất hiện trong 7 ngày qua.
- **Loại mới**: `src/siftly/admin/kinds.py` khai mỗi loại một mục (tên, nhãn, chữ mẫu và gợi ý của ô địa chỉ, dạng hợp lệ). Màn hình thêm mới lấy danh sách loại từ API và dựng ô địa chỉ từ đó, nên không phải sửa giao diện.
- **Giao diện**: trang `/sources`, `/sources/new`, `/sources/:id`, `/channels`, `/channels/new`, `/channels/:id`, cùng khối "Nguồn và Kênh đăng" ở trang sửa **Chuyên mục**, có nút thêm mới đã gắn sẵn **Chuyên mục** đó. Các mẫu mới (chọn loại, gắn vào **Chuyên mục**, bấm thử, thời điểm) được ghi ở `docs/ui.md`. Thêm thành phần `checkbox` và `select` của shadcn.

Quyết định đã tự chọn, cần chủ hệ thống xác nhận:

- **Không xoá được Nguồn hay Kênh đăng**, chỉ tắt. **Bài gốc** đã thu thập và các lần phát đã qua vẫn trỏ tới chúng. Ticket không đòi xoá; nếu cần thì phải quyết định số phận của **Bài gốc** chỉ thấy ở **Nguồn** đó.
- **Loại không đổi được sau khi thêm.** Đổi loại là đổi nghĩa của địa chỉ; muốn đổi thì thêm cái mới và tắt cái cũ.
- **Gắn vào Chuyên mục làm ở trang Nguồn và Kênh đăng**; trang **Chuyên mục** chỉ liệt kê và dẫn tới đó.
- **Cùng loại thì không trùng địa chỉ** (ràng buộc sẵn có của bảng), báo lỗi kèm tên cái đã có.
- **Mã Telegram** nhận một số (có thể âm) hoặc `@ten_kenh` từ 4 ký tự. Địa chỉ RSS phải bắt đầu bằng `http://` hoặc `https://`.
- **Nguồn và Kênh đăng mới mặc định bật.** Gắn vào một **Chuyên mục** đang chạy là nó vào **Kỳ** kế tiếp ngay.
- **Tin nhắn thử** là chữ thuần "Tin nhắn thử từ trang quản lí Siftly: Bản tin sẽ được gửi tới đây." Lỗi hiện nguyên lời của Telegram, như "Telegram từ chối: Bad Request: chat not found"; chưa dịch hay giải thích thêm.
- **"Gần đây" là 7 ngày**, tính theo lúc **Bài gốc** xuất hiện, không theo lúc thu thập.
- **Không lưu lần lấy được gần nhất** riêng với lần lấy gần nhất: một **Nguồn** đang lỗi cho thấy lúc nó lỗi gần nhất, chứ không cho thấy nó chết từ bao giờ. Cần thì thêm một cột.

Chuyển sang `ready-for-human` vì còn những việc cần chủ hệ thống:

- `uv run siftly init` để nâng cơ sở dữ liệu phát triển lên 0009 (cùng 0008 của ticket 10 nếu chưa nâng). Mình không đụng tới cơ sở dữ liệu phát triển.
- `(cd web && npm ci && npm run build)`, rồi `uv run siftly admin`; bấm "Gửi tin nhắn thử" với nhóm Telegram thật để chắc bot gửi được.
- Xem qua các quyết định trên.
- Commit, tách khỏi ticket 10 nếu muốn: file của ticket này là `src/siftly/admin/{kinds,sources,channels}.py`, migration 0009, `tests/test_admin_sources_and_channels.py`, `web/src/lib/{kinds,sources,channels,format}.ts`, `web/src/components/{enabled,kind-select,section-picker,source-health}.tsx`, `web/src/components/ui/{checkbox,select}.tsx`, `web/src/pages/{sources,source-form,channels,channel-form}.tsx`; còn lại là sửa chung trên các file của ticket 10 và `runner.py`, `models.py`, `publishers/`, `conftest.py`, `test_runner.py`, `test_telegram_publisher.py`.

Ghi chú cho các ticket sau:

- Ticket 17, 18, 20 (loại **Nguồn** mới): thêm giá trị vào `SourceKind`, bộ thu thập vào `collectors` ở cả `_open_runner` và `_admin` của `cli.py`, và một mục ở `SOURCE_KINDS` trong `admin/kinds.py`. Địa chỉ của mọi loại nằm ở cột `sources.url`. Ticket 20 cần thêm ô ngôn ngữ: `Kind` hiện chỉ mô tả một ô địa chỉ, nên phải mở rộng nó (và `KindOut`, `SourceForm`) cho các ô riêng của từng loại.
- Ticket 25, 26 (loại **Kênh đăng** mới): thêm giá trị vào `ChannelKind`, bộ phát có cả `publish` lẫn `send_test`, một mục ở `CHANNEL_KINDS`, và nối vào `publishers` ở hai chỗ của `cli.py`. Token của trang Facebook cần chỗ lưu riêng, chưa có.
- Ticket 12: lỗi gần nhất của **Kênh đăng** đã có trong `deliveries.error` theo từng **Bản tin**; trang **Kênh đăng** chưa hiện nó.
