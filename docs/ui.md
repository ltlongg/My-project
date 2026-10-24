# Giao diện trang quản lí

Mọi trang của trang quản lí dùng chung hệ giao diện dưới đây. Ticket sau dùng lại các thành phần và
mẫu có sẵn; cần thứ chưa có thì thêm vào đây trước, thay vì tự chế trong một trang.

## Nền tảng

- React, Vite, TypeScript ở `web/`. Định tuyến bằng `react-router`, dữ liệu bằng TanStack Query
  (`web/src/lib/*.ts`, mỗi nhóm thực thể một file hook như `sections.ts`).
- Thành phần là [shadcn/ui](https://ui.shadcn.com), kiểu `radix-nova`, nằm ở `web/src/components/ui/`.
  Thêm thành phần bằng `npx shadcn@4.22.1 add <tên>` trong `web/`. Biểu tượng là `lucide-react`.
- Mọi lời gọi API đi qua `api()` ở `web/src/lib/api.ts`: lỗi thành `ApiError` mang lời nhắn tiếng
  Việt của máy chủ, kèm `fields` khi dữ liệu chưa hợp lệ. Gặp 401 giữa chừng thì tự về trang đăng nhập.

## Màu

Màu là biến CSS ở `web/src/index.css`, có bản sáng và bản tối. Chỉ dùng tên vai trò (`bg-primary`,
`text-muted-foreground`…), không dùng mã màu hay màu Tailwind trần như `bg-blue-600`.

| Vai trò | Dùng cho |
| --- | --- |
| `background`, `foreground` | Nền trang, chữ chính |
| `card` | Khối nội dung, biểu mẫu |
| `muted-foreground` | Mô tả, gợi ý, thông tin phụ |
| `primary` (xanh lam, hue 263) | Hành động chính của trang, mục điều hướng đang chọn, công tắc bật |
| `destructive` | Lỗi, hành động xoá |
| `success` | Trạng thái tốt: đang chạy, đã phát |
| `warning` | Trạng thái cần chú ý nhưng không phải lỗi: tạm dừng, không phát |
| `sidebar-*` | Thanh điều hướng |

Màu nền xám trung tính (`neutral`). Mỗi trang chỉ có một nút `primary`; các nút khác là `outline`
hoặc `ghost`.

## Chữ

- Font **Be Vietnam Pro** (400, 500, 600, 700), tự phục vụ qua `@fontsource`, vì được thiết kế cho
  dấu tiếng Việt.
- Tiêu đề trang: `text-2xl font-semibold tracking-tight`. Tiêu đề khối: `CardTitle`. Chữ thường:
  `text-sm`. Mô tả, gợi ý: `text-sm text-muted-foreground`.
- Mã, lệnh và tên cột trong `<code>`.

## Khoảng cách và bố cục

- Thang khoảng cách của Tailwind, bước 4px. Giữa các khối trong trang `gap-6`, giữa các trường của
  biểu mẫu `gap-5`, giữa nhãn và ô nhập `gap-2`.
- Nội dung trang rộng tối đa `max-w-4xl`, lề `px-4` trên điện thoại, `sm:px-6` từ màn hình nhỏ.
- Bo góc theo `--radius` (0,625rem): khối `rounded-xl`, nút và ô nhập `rounded-lg`.
- Điểm ngắt duy nhất cho khung trang là `md` (768px): dưới đó thanh điều hướng thành ngăn kéo mở từ
  nút menu.

## Khung trang và điều hướng

- `AppShell` (`web/src/components/app-shell.tsx`) bọc mọi trang sau đăng nhập và chặn người chưa
  đăng nhập. Thanh trên cùng có chế độ sáng tối (`ThemeMenu`: sáng, tối, theo máy) và tài khoản.
- Điều hướng khai ở `web/src/components/nav.ts`, chia ba tầng **Thiết lập**, **Theo dõi**, **Cải
  tiến**. Mục chưa có trang hiện mờ với nhãn "Sắp có"; ticket làm trang đó chỉ cần thêm `to` cho mục
  của mình và một route ở `web/src/App.tsx`.
- Đường dẫn bằng tiếng Anh, theo tên trong code của `CONTEXT.md`: `/sections`, `/sources`,
  `/channels`, `/runs`, `/guidelines`…

## Mẫu dùng lại

- **Đầu trang**: `PageHeader` (`web/src/components/page.tsx`) với tiêu đề, một câu mô tả, nút hành
  động chính, và liên kết quay lại (`back`) ở trang con.
- **Danh sách**: mỗi thực thể một `Card`: tên là liên kết tới trang của nó, nhãn trạng thái cạnh
  tên, mô tả cắt ở hai dòng, thông tin phụ có biểu tượng, nút "Sửa" ở `CardAction`. Không dùng bảng
  cho danh sách ít cột, vì bảng phải cuộn ngang trên điện thoại.
- **Trống**: khối viền đứt, biểu tượng, một câu nói chưa có gì, một câu chỉ cách bắt đầu, nút tạo.
- **Đang tải**: `Skeleton` cùng hình dạng với thứ sắp hiện. **Lỗi tải**: `Alert` loại
  `destructive` với lời nhắn của máy chủ.
- **Biểu mẫu**: nằm trong một `Card`; mỗi trường là `Field` (nhãn, ô nhập, gợi ý; khi máy chủ báo
  lỗi thì lời nhắn lỗi thay chỗ gợi ý và ô nhập có `aria-invalid`). Nút ở cuối, ngăn bằng đường kẻ:
  "Huỷ" (`outline`) rồi nút chính; trên điện thoại hai nút trải hết chiều ngang, nút chính ở trên.
  Nút chính bị tắt khi chưa có gì thay đổi.
- **Trạng thái**: `Badge` loại `success` hoặc `warning`, chữ ngắn ("Đang chạy", "Tạm dừng"). Có
  sẵn `SectionStatus` cho **Chuyên mục** và `EnabledStatus` ("Đang bật", "Đã tắt") cho **Nguồn**,
  **Kênh đăng** (`web/src/components/enabled.tsx`). Lỗi là `Badge` loại `destructive`.
- **Bật tắt**: `Switch` với `Label` nói trạng thái hiện tại, áp dụng ngay khi bấm, không cần lưu.
  `EnabledSwitch` làm sẵn việc này kèm thông báo kết quả. Trang sửa có một khối riêng cho nó ở
  cuối, nói rõ tắt thì điều gì dừng và điều gì giữ nguyên.
- **Chọn loại**: `KindSelect` (`web/src/components/kind-select.tsx`) với danh sách loại lấy từ API
  (`/sources/kinds`, `/channels/kinds`). Nhãn, chữ mẫu và gợi ý của ô địa chỉ cũng đến từ đó, nên
  loại mới chỉ cần khai ở `src/siftly/admin/kinds.py`. Ở trang sửa, loại bị tắt.
- **Gắn vào Chuyên mục**: `SectionPicker` (`web/src/components/section-picker.tsx`), mỗi **Chuyên
  mục** một ô đánh dấu kèm trạng thái. Trang mở với `?section=<id>` thì đánh dấu sẵn **Chuyên mục**
  đó, như nút "Thêm Nguồn" ở trang của **Chuyên mục**.
- **Bấm thử**: nút `outline` cạnh ô cần thử, trải hết chiều ngang dưới ô trên điện thoại. Kết quả
  hiện ngay dưới ô, không dùng `toast`, vì cần đọc: được thì một dòng `text-success` có biểu tượng,
  kèm dữ liệu mẫu trong khối `bg-muted/40`; không được thì `Alert` loại `destructive` với lời nhắn
  của máy chủ. Kết quả biến mất khi ô đổi giá trị, để không nhầm là kết quả của giá trị mới.
- **Thời điểm**: "5 phút trước" bằng `formatAgo`, kèm giờ Việt Nam đầy đủ ở `title`
  (`web/src/lib/format.ts`).
- **Kết quả một hành động**: thông báo `toast` của `sonner` ở giữa phía trên, một câu.
- Nút hành động chính và nút của biểu mẫu dùng `size="lg"` để dễ bấm trên điện thoại.

## Chữ trên trang

- Tiếng Việt, dùng thuật ngữ của `CONTEXT.md` và viết hoa đúng như ở đó: **Chuyên mục**, **Kỳ**,
  **Tin**, **Bài gốc**, **Kênh đăng**… Không dùng từ ở mục _Avoid_.
- Câu ngắn, viết hoa chữ đầu câu, không viết hoa mọi chữ của nhãn. Nhãn nút là động từ: "Tạo
  Chuyên mục", "Lưu thay đổi".
- Lời nhắn lỗi của dữ liệu do máy chủ viết (`fields` của lỗi 422), để trang và API nói cùng một câu.

## Điện thoại

- Mọi trang thử ở chiều ngang 360px: không cuộn ngang, chữ không bị cắt, nút đủ lớn để bấm.
- Thứ rộng (bảng, mã dài) tự cuộn trong khối của nó, không đẩy cả trang.
