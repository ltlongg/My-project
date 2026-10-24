# 10: Khung trang quản lí, đăng nhập, Chuyên mục

**What to build:** Chủ hệ thống mở trang quản lí trên trình duyệt, đăng nhập bằng một tài khoản duy nhất, và tạo, sửa, tạm dừng **Chuyên mục** mà không đụng tới code. Ticket này đặt khung cho mọi trang sau: API HTTP phía Python, ứng dụng React với shadcn/ui, bố cục ba tầng (thiết lập, theo dõi, cải tiến), và khuôn test tại điểm "API trang quản lí".

Giao diện cần đẹp và nhất quán; chọn và ghi lại một hệ giao diện (màu, chữ, khoảng cách, thành phần) để các ticket sau dùng lại thay vì tự chế.

**Blocked by:** 03

**Status:** ready-for-human

- [x] Chưa đăng nhập thì không vào được trang nào và không gọi được API nào ngoài đăng nhập
- [x] Chỉ có một tài khoản; mật khẩu lấy từ cấu hình môi trường
- [x] Tạo và sửa được **Chuyên mục** với tên, mô tả phạm vi, giờ phát và số **Tin** mỗi **Bản tin**
- [x] Tạm dừng và bật lại được một **Chuyên mục** mà không mất thiết lập
- [x] Thay đổi trên trang có hiệu lực ở **Kỳ** kế tiếp mà không cần khởi động lại
- [x] Giao diện bằng tiếng Việt, dùng thuật ngữ của `CONTEXT.md`
- [x] Dùng được trên màn hình điện thoại, không cuộn ngang; có chế độ sáng và tối
- [x] Thanh điều hướng có sẵn chỗ cho ba tầng thiết lập, theo dõi, cải tiến
- [x] Test gọi API thật với Postgres thật phủ: đăng nhập, từ chối khi chưa đăng nhập, tạo, sửa, tạm dừng

## Comments

**2026-10-24, agent.** Code xong trên nhánh `feat/shortlisting`, chưa commit. 197 test xanh (29 test mới ở `tests/test_admin_api.py`); mypy, ruff, `tsc` và oxlint sạch. Đã thử cố ý làm hỏng code (bỏ chặn đăng nhập, bỏ kiểm tra thoát thư mục khi phục vụ file, bỏ phạm vi khỏi lời gọi Biên tập) và test đều bắt được. Đã chạy thật `siftly admin` trên một cơ sở dữ liệu thử riêng (đã xoá sau đó) và đi qua bằng Chromium: đăng nhập sai rồi đúng, tạo, sửa, bật lại một **Chuyên mục**, nhập sai để xem lời nhắn, đăng xuất. Trang được chụp ở 1280px và 360px, cả sáng lẫn tối, và không trang nào cuộn ngang.

Cách làm:

- **API**: FastAPI ở `src/siftly/admin/`, mọi đường dẫn dưới `/api`. `siftly admin` chạy nó bằng uvicorn và phục vụ luôn bản dựng của `web/` từ cùng một cổng (mặc định `127.0.0.1:8000`), nên không cần CORS. Lỗi dữ liệu trả 422 với một lời nhắn tiếng Việt cho mỗi trường; trang hiện đúng lời nhắn đó.
- **Đăng nhập**: một tài khoản, `ADMIN_USERNAME` (mặc định `admin`) và `ADMIN_PASSWORD`. Phiên là một mã ngẫu nhiên trong cookie `HttpOnly`, `SameSite=Strict`, `Secure` khi chạy qua HTTPS. Bảng `admin_sessions` chỉ giữ dạng băm SHA-256 của mã, nên đăng xuất vô hiệu luôn cookie cũ. Phiên kéo dài 30 ngày. Router của API chặn mọi đường dẫn trừ `/api/login` và `/api/logout`, và test duyệt mọi đường dẫn có trong API, nên đường dẫn của ticket sau cũng tự được kiểm.
- **Chuyên mục**: `GET/POST /api/sections`, `GET/PATCH /api/sections/{id}`. Tạm dừng và bật lại là `PATCH {"is_paused": …}`, chỉ đổi cờ đó. Lịch và `Runner` vốn đã đọc thiết lập từ cơ sở dữ liệu ở mỗi lượt, nên không phải sửa gì để thay đổi có hiệu lực ở **Kỳ** kế tiếp. Test làm đúng việc này với Lịch đang chạy: đổi giờ phát, tạm dừng, bật lại, đổi phạm vi và số **Tin**.
- **Giao diện**: React, Vite, TypeScript, Tailwind 4 và shadcn/ui (`radix-nova`) ở `web/`, cùng react-router và TanStack Query. Font Be Vietnam Pro tự phục vụ. Có chế độ sáng, tối, theo máy. Trên máy tính có thanh điều hướng bên trái; dưới 768px nó thành ngăn kéo mở từ nút menu. Hệ giao diện được ghi ở `docs/ui.md`.
- **Ba tầng**: `web/src/components/nav.ts` khai Thiết lập (Chuyên mục, Nguồn, Kênh đăng), Theo dõi (Kỳ, Tìm Tin), Cải tiến (Hướng dẫn, Đề xuất cải tiến). Mục chưa có trang hiện mờ, kèm nhãn "Sắp có".

Quyết định đã tự chọn, cần chủ hệ thống xác nhận:

- **Mô tả phạm vi là cột riêng `sections.scope`**, và Sơ tuyển cùng **Biên tập** đọc nó: `Runner` ghép "Phạm vi của Chuyên mục: …" vào trước **Hướng dẫn** của **Biên tập**. Điều này thay quyết định ở ticket 07, nơi phạm vi chỉ nằm trong **Hướng dẫn**. Lí do: ticket này yêu cầu sửa phạm vi trên trang, còn sửa **Hướng dẫn** là việc của ticket 23. Phạm vi không có phiên bản như **Hướng dẫn**, và **Kỳ** không ghi lại phạm vi lúc nó chạy.
- **Dữ liệu khởi tạo**: `siftly init` điền phạm vi cho **Chuyên mục** công nghệ khi phạm vi còn trống. Đoạn "Phạm vi: …" được bỏ khỏi `TECH_EDITOR_GUIDELINE` để không nói hai lần, nhưng chỉ cho lần cài mới. **Hướng dẫn** đã có trong cơ sở dữ liệu phát triển vẫn còn đoạn đó, nên phạm vi tạm thời xuất hiện hai lần ở đó.
- **Chuyên mục mới mặc định tạm dừng** và có sẵn một **Hướng dẫn** khởi đầu chung (`STARTER_EDITOR_GUIDELINE`). Nếu không, Lịch sẽ chạy nó khi chưa có **Nguồn** hay **Kênh đăng**, rồi thử lại và nhắn báo hỏng.
- **Mã (`slug`) tự suy từ tên** khi tạo ("Thời sự" thành `thoi-su`; nếu trùng thì thêm `-2`), và không đổi sau đó, để `siftly run <mã>` vẫn chạy khi đổi tên.
- **Số Tin mỗi Bản tin từ 3 đến 10.** Giờ phát lấy theo phút (`HH:MM`). Tên tối đa 80 ký tự, phạm vi tối đa 2.000 ký tự.
- **Mật khẩu ngắn hơn 12 ký tự thì `siftly admin` không chạy**, vì trang mở ra Internet mà chỉ có một mật khẩu chặn. Chưa có giới hạn số lần đăng nhập sai (xem ghi chú cho ticket 16).
- **Bật lại trong vòng 3 giờ sau giờ phát thì Lịch chạy ngay Kỳ của giờ đó**, cũng như khi đổi giờ phát sang một giờ vừa qua. Đây là cách Lịch của ticket 09 vẫn chạy; ticket này không đổi gì ở đó.
- Ứng dụng React (HTML, JS, CSS) được trả cho cả người chưa đăng nhập, nhưng nó không chứa dữ liệu nào. Trang tự chuyển tới màn đăng nhập, và mọi dữ liệu chỉ đi qua API, nơi bị chặn.
- Ô giờ phát là ô `time` của trình duyệt, nên hiện 12 hay 24 giờ theo ngôn ngữ của trình duyệt hay điện thoại: máy để tiếng Anh thấy "08:00 AM". Giá trị gửi đi luôn là `08:00`.

Chuyển sang `ready-for-human` vì còn những việc cần chủ hệ thống:

- Thêm `ADMIN_PASSWORD` (và `ADMIN_USERNAME` nếu muốn) vào `.env`.
- `uv run siftly init` để nâng cơ sở dữ liệu phát triển lên 0008 và điền phạm vi cho **Chuyên mục** công nghệ. Lệnh này cũng nâng qua 0005 tới 0007 nếu chưa nâng. Mình không đụng tới cơ sở dữ liệu phát triển.
- `(cd web && npm ci && npm run build)`, rồi `uv run siftly admin` và mở trên trình duyệt, cả trên điện thoại.
- Xem qua các quyết định trên, nhất là chuyện phạm vi.
- Commit.

Ghi chú cho các ticket sau:

- Ticket 11, 12, 13, 23: thêm đường dẫn vào `src/siftly/admin/` (một file router cho mỗi nhóm, gắn vào router `protected` ở `app.py`), thêm hook ở `web/src/lib/`, trang ở `web/src/pages/`, `to` cho mục của mình ở `nav.ts` và một route ở `App.tsx`. Test dùng fixture `admin` hoặc `api` của `tests/conftest.py`. Dùng lại các mẫu ở `docs/ui.md`.
- Ticket 13: nút "Chạy xem trước" nên đặt ở trang sửa **Chuyên mục** (`web/src/pages/section-form.tsx`).
- Ticket 14: **Hướng dẫn** khởi đầu không cần nhắc lại phạm vi; phạm vi nằm ở `TECH_SCOPE` trong `seed.py`.
- Ticket 16: dựng `web/` trong Dockerfile (Node 22+) và đặt `ADMIN_WEB_DIR` nếu bản dựng không nằm ở `web/dist` so với thư mục chạy. Đặt `siftly admin --host 0.0.0.0` sau reverse proxy HTTPS. uvicorn chỉ tin `X-Forwarded-Proto` từ 127.0.0.1; nếu proxy ở container khác thì phải đặt `FORWARDED_ALLOW_IPS`, nếu không cookie sẽ thiếu `Secure`. Nên giới hạn số lần đăng nhập sai ở proxy hoặc trong `auth.py`.
- Ticket 23: phạm vi của **Chuyên mục** đứng ngoài **Hướng dẫn**. Nếu muốn có phiên bản và quay lui cho cả phạm vi thì cần quyết định thêm.
