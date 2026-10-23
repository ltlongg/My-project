# 17: Nguồn Bảng xếp hạng

**What to build:** Tin công nghệ có tín hiệu thật về độ nổi. Chủ hệ thống thêm **Nguồn** loại **Bảng xếp hạng** trên trang quản lí: GitHub Trending, Hugging Face Daily Papers, Hacker News. Mỗi mục trên bảng thành một **Bài gốc** có kèm thứ hạng và số sao hoặc số vote tại lúc lấy, và các con số đó được dùng khi sơ tuyển, để "paper nổi tiếng" và "repo hay" không còn là LLM đoán.

**Blocked by:** 07, 11

**Status:** ready-for-agent

- [ ] Thêm được **Nguồn** loại **Bảng xếp hạng** trên trang quản lí và bấm thử được như RSS
- [ ] Có bộ thu thập cho GitHub Trending, Hugging Face Daily Papers và Hacker News, cùng giao diện với các bộ thu thập khác
- [ ] Mỗi **Bài gốc** từ **Bảng xếp hạng** lưu kèm thứ hạng và số sao hoặc số vote tại lúc lấy
- [ ] Một mục đứng trên bảng nhiều ngày không thành nhiều **Bài gốc**
- [ ] Một paper hay repo xuất hiện cả trên **Bảng xếp hạng** lẫn trong một bài báo được gom thành một **Tin**; **Bài gốc chính** ưu tiên paper hoặc repo gốc
- [ ] Tín hiệu độ nổi tham gia vào điểm sơ tuyển và hiện trong các thành phần của điểm
- [ ] **Biên tập** thấy được tín hiệu độ nổi của ứng viên
- [ ] Mỗi bộ thu thập có test bằng dữ liệu đã ghi lại; ba **Nguồn** này được thêm vào dữ liệu khởi tạo của công nghệ
