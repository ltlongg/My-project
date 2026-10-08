# 22: Phản hồi qua Telegram

**What to build:** Chủ hệ thống nói cho hệ thống biết họ thích gì trong một giây. Dưới mỗi **Tin** trên Telegram có hai nút 👍 và 👎. Họ cũng nhắn chữ được cho bot, ví dụ "bớt tin về điện thoại". Mọi **Phản hồi** được ghi lại, phân biệt của chủ hệ thống với của thành viên nhóm, và xem được trên trang quản lí. Ticket này chỉ thu **Phản hồi**; việc dùng nó để cải tiến ở ticket 24.

**Blocked by:** 08, 10

**Status:** ready-for-agent

- [ ] Mỗi **Tin** trên Telegram có hai nút 👍 và 👎
- [ ] Bấm nút ghi một **Phản hồi** gắn với đúng **Tin** và đúng người bấm; bấm lại thì đổi, không cộng dồn
- [ ] **Phản hồi** của chủ hệ thống được đánh dấu riêng, nhận diện bằng mã người dùng Telegram đã khai
- [ ] **Phản hồi** của thành viên nhóm được ghi lại
- [ ] Tin nhắn chữ chủ hệ thống gửi riêng cho bot được ghi thành **Phản hồi** dạng lời nhắn; nếu là trả lời một **Tin** thì gắn với **Tin** đó
- [ ] Tin nhắn chữ của người khác gửi cho bot không được ghi thành **Phản hồi**
- [ ] Bot xác nhận ngắn gọn khi nhận lời nhắn của chủ hệ thống
- [ ] Trang quản lí hiện danh sách **Phản hồi**, lọc được theo **Chuyên mục** và theo người; trang một **Tin** hiện **Phản hồi** của nó
- [ ] Sự kiện từ Telegram được nhận qua webhook và chỉ chấp nhận khi đúng là từ Telegram
- [ ] Việc nhận **Phản hồi** có test bằng sự kiện đã ghi lại, gồm sự kiện lặp và sự kiện giả mạo
