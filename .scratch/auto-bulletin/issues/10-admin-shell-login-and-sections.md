# 10: Khung trang quản lí, đăng nhập, Chuyên mục

**What to build:** Chủ hệ thống mở trang quản lí trên trình duyệt, đăng nhập bằng một tài khoản duy nhất, và tạo, sửa, tạm dừng **Chuyên mục** mà không đụng tới code. Ticket này đặt khung cho mọi trang sau: API HTTP phía Python, ứng dụng React với shadcn/ui, bố cục ba tầng (thiết lập, theo dõi, cải tiến), và khuôn test tại điểm "API trang quản lí".

Giao diện cần đẹp và nhất quán; chọn và ghi lại một hệ giao diện (màu, chữ, khoảng cách, thành phần) để các ticket sau dùng lại thay vì tự chế.

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] Chưa đăng nhập thì không vào được trang nào và không gọi được API nào ngoài đăng nhập
- [ ] Chỉ có một tài khoản; mật khẩu lấy từ cấu hình môi trường
- [ ] Tạo và sửa được **Chuyên mục** với tên, mô tả phạm vi, giờ phát và số **Tin** mỗi **Bản tin**
- [ ] Tạm dừng và bật lại được một **Chuyên mục** mà không mất thiết lập
- [ ] Thay đổi trên trang có hiệu lực ở **Kỳ** kế tiếp mà không cần khởi động lại
- [ ] Giao diện bằng tiếng Việt, dùng thuật ngữ của `CONTEXT.md`
- [ ] Dùng được trên màn hình điện thoại, không cuộn ngang; có chế độ sáng và tối
- [ ] Thanh điều hướng có sẵn chỗ cho ba tầng thiết lập, theo dõi, cải tiến
- [ ] Test gọi API thật với Postgres thật phủ: đăng nhập, từ chối khi chưa đăng nhập, tạo, sửa, tạm dừng
