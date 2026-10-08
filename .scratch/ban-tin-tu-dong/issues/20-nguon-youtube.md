# 20: Nguồn YouTube

**What to build:** Chủ hệ thống thêm kênh YouTube làm **Nguồn** và khai ngôn ngữ của kênh. Video mới của kênh được phát hiện bằng API, audio được tách ra và chuyển thành chữ, và video trở thành một **Bài gốc** có nội dung đầy đủ như một bài báo, nên **Biên tập** tóm tắt được mà người đọc không phải xem video. Ảnh của **Tin** là ảnh chụp trang video bằng Playwright.

Việc đầu tiên của ticket là thử xem từ IP của server có tách được audio và chụp được trang video không, có cần proxy hay cookies không. Điều khoản của YouTube cấm truy cập tự động và tải nội dung; chủ hệ thống đã biết và chấp nhận.

**Blocked by:** 08, 11, 19

**Status:** ready-for-agent

- [ ] Kết quả thử từ IP server được ghi lại trước khi làm tiếp
- [ ] Thêm được **Nguồn** loại kênh YouTube kèm ngôn ngữ (tiếng Việt hoặc tiếng Anh) trên trang quản lí và bấm thử được
- [ ] Video mới của kênh thành **Bài gốc** có tiêu đề, mô tả, thời lượng và văn bản chuyển từ audio
- [ ] Video dài hơn 90 phút hoặc ngắn hơn 2 phút bị bỏ qua, có ghi lí do
- [ ] Video không tách được audio hoặc không chuyển được thành chữ bị bỏ qua, có ghi lí do, và không làm trễ **Kỳ**
- [ ] Việc chuyển audio chạy trong lúc thu thập, không chạy trong **Kỳ**; **Kỳ** chỉ dùng video đã có văn bản
- [ ] File audio bị xoá sau khi chuyển xong
- [ ] Ảnh của **Tin** có **Bài gốc chính** là video là ảnh chụp trang video; không chụp được thì dùng ảnh thumbnail
- [ ] **Kiểm chứng** đối chiếu **Tin** với văn bản chuyển từ audio
- [ ] Bộ thu thập có test bằng phản hồi đã ghi lại; việc chuyển audio được thay bằng bản giả trong test
