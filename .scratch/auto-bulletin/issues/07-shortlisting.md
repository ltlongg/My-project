# 07: Sơ tuyển

**What to build:** **Biên tập** không phải đọc hàng trăm ứng viên mỗi **Kỳ**. Một bước cố định chấm điểm các ứng viên **Tin** và chỉ chuyển tối đa khoảng 30 ứng viên điểm cao nhất cho **Biên tập**. Điểm dựa trên độ mới, số **Bài gốc** cùng nói về sự kiện, và mức phù hợp với phạm vi **Chuyên mục** do một model nhỏ chấm. Đây là bước cố định, không phải agent (ADR 0001).

**Blocked by:** 06

**Status:** ready-for-agent

- [ ] Mỗi ứng viên **Tin** có một điểm và các thành phần của điểm được lưu lại
- [ ] **Biên tập** chỉ nhận số ứng viên trong giới hạn; giới hạn cấu hình được
- [ ] Ứng viên bị loại ở bước này được lưu, kèm điểm
- [ ] Ứng viên ngoài phạm vi **Chuyên mục** (ví dụ crypto trong tài chính) bị điểm thấp và không tới **Biên tập**
- [ ] Cách tính điểm nhận được thêm tín hiệu mới mà không đổi phần còn lại, để ticket **Bảng xếp hạng** cắm vào
- [ ] Bước sơ tuyển dùng cấu hình model riêng
- [ ] Test tại điểm "Chạy Kỳ" với nhiều ứng viên khẳng định chỉ nhóm điểm cao tới **Biên tập**
