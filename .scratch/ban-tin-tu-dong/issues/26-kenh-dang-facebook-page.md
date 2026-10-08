# 26: Kênh đăng Facebook Page

**What to build:** Chủ hệ thống chia sẻ **Bản tin** công khai trên trang Facebook của mình. Họ thêm **Kênh đăng** loại Facebook Page trên trang quản lí, gắn vào **Chuyên mục**, và mỗi **Bản tin** thành một bài đăng duy nhất trên trang: nhiều ảnh, phần chữ liệt kê các **Tin** với tiêu đề, tóm tắt và link. Người chưa đăng nhập cũng thấy được bài.

Chỉ đăng lên trang; API đăng vào nhóm Facebook đã bị gỡ. Việc lấy quyền và token của trang là bước của chủ hệ thống; dùng `/wizard` để dẫn từng bước. Trang này công khai và không có người duyệt, nên **Kiểm chứng** là chốt chặn duy nhất.

**Blocked by:** 08, 11

**Status:** ready-for-agent

- [ ] Thêm được **Kênh đăng** loại Facebook Page trên trang quản lí; token của trang được mã hoá khi lưu
- [ ] Mỗi **Bản tin** thành đúng một bài đăng, có ảnh của các **Tin** và phần chữ liệt kê từng **Tin**
- [ ] Bài đăng hiện với người chưa đăng nhập; nếu app ở chế độ Development làm bài bị ẩn thì chuyển app sang Live và ghi lại cách làm
- [ ] Nội dung **Tin** giống hệt bản Telegram; chỉ định dạng khác
- [ ] **Tin** không có ảnh vẫn có mặt trong phần chữ
- [ ] Token hết hiệu lực được ghi là lỗi của **Kênh đăng** và chủ hệ thống nhận tin nhắn riêng
- [ ] Facebook lỗi không chặn và không làm trễ việc phát tới các **Kênh đăng** khác
- [ ] Bộ phát Facebook có test bằng phản hồi đã ghi lại, gồm lỗi token và lỗi tải ảnh
