# Bản tin tự động

Status: ready-for-agent

Thuật ngữ in đậm được định nghĩa trong `CONTEXT.md`. Quyết định về hình dạng agent nằm ở ADR 0001.

## Problem Statement

Chủ hệ thống thích đọc tin công nghệ, tài chính và thời sự nhưng không có thời gian. Tin nằm rải ở nhiều nơi (báo, X, YouTube, các bảng xếp hạng paper và repo), phần lớn bằng tiếng Anh, và phần đáng đọc lẫn trong rất nhiều thứ không đáng đọc. Đọc hết thì không kịp; đọc lướt thì bỏ sót thứ quan trọng và không chắc mình hiểu đúng.

## Solution

Một hệ thống cá nhân chạy trên server của chủ hệ thống. Mỗi ngày, với mỗi **Chuyên mục**, nó thu thập **Bài gốc** từ các **Nguồn** đã khai, gom những bài cùng nói về một sự kiện thành **Tin**, để agent **Biên tập** chọn 5–7 **Tin** đáng đọc nhất và viết lại bằng tiếng Việt, để agent **Kiểm chứng** đối chiếu từng **Tin** với **Bài gốc**, rồi phát thành một **Bản tin** lên các **Kênh đăng** do chủ hệ thống quản lí. Không ai phải duyệt trước khi đăng.

Chủ hệ thống điều khiển mọi thứ qua một trang quản lí: khai **Chuyên mục**, **Nguồn**, **Kênh đăng**; xem vì sao một **Tin** được chọn hay bị loại; và đồng ý hoặc từ chối các **Đề xuất cải tiến** mà hệ thống soạn từ **Phản hồi** của họ.

## User Stories

### Đọc Bản tin

1. Là người đọc, tôi muốn nhận một **Bản tin** công nghệ lúc 8:00, tài chính lúc 12:00 và thời sự lúc 20:00 giờ Việt Nam, để tôi biết khi nào có tin mà không phải tự đi tìm.
2. Là người đọc, tôi muốn mỗi **Bản tin** chỉ có 5–7 **Tin**, để tôi đọc hết được trong vài phút.
3. Là người đọc, tôi muốn mỗi **Tin** có tiêu đề, tóm tắt 4–6 câu, ảnh chụp **Bài gốc chính** và link tới nó, để tôi hiểu được tin mà không cần mở link, và mở được khi muốn đọc kỹ.
4. Là người đọc, tôi muốn tóm tắt viết bằng tiếng Việt kể cả khi **Bài gốc** bằng tiếng Anh, để tôi đọc nhanh.
5. Là người đọc, tôi muốn tên riêng và thuật ngữ chuyên ngành quen dùng được giữ nguyên tiếng Anh, để tôi tra cứu tiếp được và không phải đoán bản dịch.
6. Là người đọc, tôi muốn nhiều **Bài gốc** về cùng một sự kiện chỉ thành một **Tin**, để tôi không đọc một chuyện nhiều lần.
7. Là người đọc, tôi muốn **Tin** đã phát không xuất hiện lại ở **Bản tin** sau, để mỗi **Bản tin** đều là thứ mới.
8. Là người đọc, tôi muốn một **Tin** có diễn biến mới đáng kể được phát lại với nhãn "Cập nhật", để tôi biết chuyện đã thay đổi.
9. Là người đọc, tôi muốn mỗi **Bản tin** mở đầu bằng một tin nhắn nêu tên **Chuyên mục** và ngày, để tôi phân biệt các **Bản tin** trong cùng một nhóm.
10. Là người đọc, tôi muốn mỗi **Tin** là một tin nhắn riêng có ảnh, để tôi chuyển tiếp được từng **Tin** cho người khác.
11. Là người đọc tin công nghệ, tôi muốn thấy paper và repo đang được chú ý thật sự, để tôi không bỏ lỡ thứ cả ngành đang bàn.
12. Là người đọc tin tài chính, tôi muốn tin vĩ mô Việt Nam và thế giới cùng tin về doanh nghiệp lớn, không có crypto, bảng giá hay khuyến nghị mua bán, để **Bản tin** đúng thứ tôi quan tâm.
13. Là người đọc tin thời sự, tôi muốn cả tin trong nước và thế giới, để tôi nắm được cả hai trong một lần đọc.
14. Là người đọc, tôi muốn nội dung của một video YouTube được tóm tắt như một bài báo, để tôi không phải xem cả video.
15. Là người đọc, tôi muốn một **Tin** không lấy được ảnh chụp vẫn được phát với ảnh đại diện của bài, hoặc không ảnh, để tôi không mất tin vì lỗi ảnh.

### Tin cậy

16. Là chủ hệ thống, tôi muốn mỗi **Tin** được **Kiểm chứng** đối chiếu với **Bài gốc** trước khi phát, để số liệu, tên và ngày tháng không bị bịa.
17. Là chủ hệ thống, tôi muốn **Tin** không qua được **Kiểm chứng** được **Biên tập** viết lại tối đa hai lần rồi bị bỏ, để thà thiếu một **Tin** còn hơn phát một **Tin** sai.
18. Là chủ hệ thống, tôi muốn **Bản tin** còn dưới ba **Tin** thì không phát, để nhóm không nhận một bản dở.
19. Là chủ hệ thống, tôi muốn **Kỳ** bị hỏng được thử lại sau 30 phút, tối đa ba lần, để sự cố tạm thời không làm mất **Bản tin**.
20. Là chủ hệ thống, tôi muốn bot nhắn riêng cho tôi khi một **Kỳ** hỏng hoặc không phát, kèm lí do, để tôi biết mà không phải vào trang quản lí.
21. Là chủ hệ thống, tôi muốn một **Nguồn** hỏng không làm hỏng cả **Kỳ**, để **Bản tin** vẫn ra từ các **Nguồn** còn lại.
22. Là chủ hệ thống, tôi muốn được báo riêng khi phiên đăng nhập X hết hạn hoặc bị chặn, để tôi nạp lại.
23. Là chủ hệ thống, tôi muốn **Tin** chỉ lấy từ **Nguồn** tôi đã khai, để tôi kiểm soát chất lượng qua danh sách **Nguồn**.
24. Là chủ hệ thống, tôi muốn **Biên tập** được tìm kiếm web để hiểu bối cảnh của một **Tin**, để tóm tắt chính xác hơn mà không đưa nguồn lạ vào **Bản tin**.
25. Là chủ hệ thống, tôi muốn một video không chuyển được thành chữ thì bị bỏ qua, để một video hỏng không làm trễ **Bản tin**.

### Thiết lập

26. Là chủ hệ thống, tôi muốn đăng nhập trang quản lí bằng một tài khoản duy nhất, để người khác không vào được.
27. Là chủ hệ thống, tôi muốn tạo và sửa **Chuyên mục** với tên, mô tả phạm vi, giờ phát và số **Tin** mỗi **Bản tin**, để tôi tự điều chỉnh mà không sửa code.
28. Là chủ hệ thống, tôi muốn tạm dừng một **Chuyên mục**, để tôi ngừng nhận **Bản tin** của nó mà không xoá thiết lập.
29. Là chủ hệ thống, tôi muốn thêm **Nguồn** loại RSS bằng một địa chỉ, để theo dõi một tờ báo hay blog.
30. Là chủ hệ thống, tôi muốn thêm **Nguồn** loại tài khoản X bằng tên tài khoản, để theo dõi người tôi tin.
31. Là chủ hệ thống, tôi muốn thêm **Nguồn** loại kênh YouTube và khai ngôn ngữ của kênh, để video được chuyển thành chữ bằng đúng model.
32. Là chủ hệ thống, tôi muốn thêm **Nguồn** loại **Bảng xếp hạng**, để tin công nghệ có tín hiệu về độ nổi.
33. Là chủ hệ thống, tôi muốn gắn một **Nguồn** vào một hay nhiều **Chuyên mục**, để một tờ báo lớn phục vụ được cả tài chính lẫn thời sự.
34. Là chủ hệ thống, tôi muốn bấm thử một **Nguồn** và thấy vài **Bài gốc** nó trả về, để biết tôi khai đúng trước khi lưu.
35. Là chủ hệ thống, tôi muốn thấy tình trạng từng **Nguồn** (lần lấy gần nhất, số **Bài gốc**, lỗi gần nhất), để phát hiện **Nguồn** chết.
36. Là chủ hệ thống, tôi muốn tắt một **Nguồn** mà không xoá, để tạm bỏ nó ra khỏi **Bản tin**.
37. Là chủ hệ thống, tôi muốn thêm **Kênh đăng** và gắn nó với các **Chuyên mục**, để mỗi nhóm chỉ nhận **Chuyên mục** họ quan tâm.
38. Là chủ hệ thống, tôi muốn gửi một tin nhắn thử tới một **Kênh đăng**, để biết bot đã có quyền đăng.
39. Là chủ hệ thống, tôi muốn nạp cookies phiên đăng nhập X và cấu hình proxy trên trang quản lí, để việc thu thập X chạy được mà tôi không phải vào server.
40. Là chủ hệ thống, tôi muốn bấm chạy ngay một **Kỳ** cho một **Chuyên mục** ở chế độ xem trước, không đăng, để thử thiết lập mới mà không làm phiền nhóm.

### Theo dõi

41. Là chủ hệ thống, tôi muốn xem danh sách các **Kỳ** với kết quả (đã phát, không phát, hỏng), để biết hệ thống có chạy đều không.
42. Là chủ hệ thống, tôi muốn mở một **Bản tin** đã phát và thấy đúng những gì đã gửi đi, để đối chiếu khi có người hỏi.
43. Là chủ hệ thống, tôi muốn với mỗi **Tin** thấy được tất cả **Bài gốc** của nó, **Bài gốc chính**, điểm và lí do **Biên tập** chọn, để hiểu vì sao nó có mặt.
44. Là chủ hệ thống, tôi muốn thấy những **Tin** được cân nhắc nhưng không được chọn, và những **Tin** bị **Kiểm chứng** loại kèm lí do, để biết hệ thống bỏ qua cái gì.
45. Là chủ hệ thống, tôi muốn thấy từng lần **Kiểm chứng** trả lại và **Biên tập** đã sửa gì, để đánh giá hai agent làm việc ra sao.
46. Là chủ hệ thống, tôi muốn từ một **Tin** mở được vết chi tiết các lần gọi LLM và công cụ, để dò lỗi khi một **Tin** sai.
47. Là chủ hệ thống, tôi muốn thấy chi phí và số lần gọi LLM theo **Kỳ** và theo ngày, để biết hệ thống tiêu tốn bao nhiêu.
48. Là chủ hệ thống, tôi muốn tìm lại một **Tin** cũ theo từ khoá, để tra lại thứ tôi nhớ đã đọc.

### Phản hồi và cải tiến

49. Là chủ hệ thống, tôi muốn bấm 👍 hoặc 👎 ngay dưới mỗi **Tin** trên Telegram, để cho **Phản hồi** trong một giây.
50. Là chủ hệ thống, tôi muốn nhắn chữ cho bot, ví dụ "bớt tin về điện thoại", để nói điều mà nút bấm không diễn đạt được.
51. Là chủ hệ thống, tôi muốn chỉ **Phản hồi** của tôi làm thay đổi **Hướng dẫn**, để người khác trong nhóm không lái **Bản tin** của tôi.
52. Là thành viên nhóm, tôi muốn 👍/👎 của tôi được ghi nhận, để chủ hệ thống thấy nhóm thích gì.
53. Là chủ hệ thống, tôi muốn mỗi tuần nhận một **Đề xuất cải tiến** nêu rõ đổi gì trong **Hướng dẫn** hoặc danh sách **Nguồn** và dựa trên **Phản hồi** nào, để tôi quyết định có căn cứ.
54. Là chủ hệ thống, tôi muốn xem **Đề xuất cải tiến** dưới dạng so sánh trước và sau, để thấy chính xác cái gì thay đổi.
55. Là chủ hệ thống, tôi muốn đồng ý hoặc từ chối một **Đề xuất cải tiến** bằng một lần bấm, để việc cải tiến không tốn thời gian của tôi.
56. Là chủ hệ thống, tôi muốn agent không bao giờ tự sửa **Hướng dẫn** khi tôi chưa đồng ý, để **Bản tin** không trôi dần theo hướng tôi không chọn.
57. Là chủ hệ thống, tôi muốn xem và sửa tay **Hướng dẫn** của **Biên tập** cho từng **Chuyên mục** và **Hướng dẫn** chung của **Kiểm chứng**, để tự chỉnh khi tôi biết mình muốn gì.
58. Là chủ hệ thống, tôi muốn mọi phiên bản **Hướng dẫn** được lưu và quay lui được, để gỡ một thay đổi làm **Bản tin** tệ đi.
59. Là chủ hệ thống, tôi muốn thấy mỗi **Bản tin** được làm theo phiên bản **Hướng dẫn** nào, để liên hệ chất lượng với thay đổi.
60. Là chủ hệ thống, tôi muốn khi **Biên tập** gặp một nơi đưa tin tốt ngoài danh sách thì nó đề xuất thêm **Nguồn** trong **Đề xuất cải tiến**, để danh sách **Nguồn** tốt dần lên.

### Kênh đăng khác

61. Là chủ hệ thống, tôi muốn nhận **Bản tin** qua Zalo Bot trong cuộc trò chuyện riêng, để đọc được trên ứng dụng tôi dùng nhiều nhất.
62. Là chủ hệ thống, tôi muốn mỗi **Bản tin** được đăng lên trang Facebook của tôi thành một bài nhiều ảnh, để chia sẻ công khai mà không làm trang ngập bài.
63. Là chủ hệ thống, tôi muốn một **Kênh đăng** hỏng không chặn các **Kênh đăng** khác, để Telegram vẫn nhận **Bản tin** khi Zalo lỗi.

### Giao diện

64. Là chủ hệ thống, tôi muốn trang quản lí bằng tiếng Việt, đẹp và nhất quán, để tôi muốn dùng nó.
65. Là chủ hệ thống, tôi muốn trang quản lí dùng được trên điện thoại, để xem vì sao một **Tin** sai ngay khi vừa đọc nó.

## Implementation Decisions

### Hình dạng tổng thể

- Theo ADR 0001: thu thập, gom **Tin** và phát hành là các bước cố định; chỉ **Biên tập**, **Kiểm chứng** và việc soạn **Đề xuất cải tiến** là agent.
- Ngôn ngữ phía máy chủ là Python. Vòng agent viết bằng LangGraph, trạng thái của vòng được lưu vào cơ sở dữ liệu để một **Kỳ** bị gián đoạn chạy tiếp được.
- Cơ sở dữ liệu là Postgres, dùng cả cho tìm kiếm theo độ giống nghĩa khi gom **Tin**.
- Trang quản lí là một ứng dụng React dùng shadcn/ui, nói chuyện với phần máy chủ qua một API HTTP.
- Triển khai bằng Docker Compose trên server Linux của chủ hệ thống, HTTPS trên tên miền sẵn có.
- Múi giờ của mọi lịch là Asia/Ho_Chi_Minh.

### Các module

Mỗi module giấu nhiều việc sau một giao diện nhỏ.

- **Chạy Kỳ**: một lối vào duy nhất, "chạy một **Kỳ** cho **Chuyên mục** này tại thời điểm này, có đăng hay chỉ xem trước". Nó gọi lần lượt các module dưới đây và ghi lại kết quả từng bước. Đây là điểm kiểm thử chính.
- **Thu thập**: mỗi loại **Nguồn** là một bộ thu thập cùng giao diện, "trả về các **Bài gốc** mới kể từ mốc này". Bốn loại: RSS, **Bảng xếp hạng**, tài khoản X, kênh YouTube. **Bài gốc** được nhận diện bằng địa chỉ đã chuẩn hoá và chỉ lưu một lần dù **Nguồn** thuộc nhiều **Chuyên mục**. Lỗi của một bộ thu thập được ghi lại và không lan ra ngoài.
- **Lấy nội dung**: biến một **Bài gốc** thành văn bản đầy đủ. Bài báo: trích phần thân bài. Video: tách audio rồi chuyển thành chữ.
- **Chuyển audio thành chữ**: một giao diện, hai model tự chạy trên server, chọn theo ngôn ngữ khai ở **Nguồn**: Zipformer của hynt cho tiếng Việt, Phonon-2 cho tiếng Anh. Bỏ qua video dài hơn 90 phút hoặc ngắn hơn 2 phút.
- **Gom Tin**: gom các **Bài gốc** cùng nói về một sự kiện thành ứng viên **Tin**, và đối chiếu với **Tin** đã phát của cùng **Chuyên mục** để loại trùng hoặc đánh dấu "Cập nhật".
- **Sơ tuyển**: bước cố định, rút danh sách ứng viên xuống tối đa khoảng 30 **Tin** trước khi tới **Biên tập**, dựa trên độ mới, số **Bài gốc**, tín hiệu từ **Bảng xếp hạng** và điểm phù hợp với phạm vi **Chuyên mục** do một model nhỏ chấm.
- **Vòng agent**: **Biên tập** chọn **Tin** từ danh sách sơ tuyển, chọn **Bài gốc chính** và viết tiêu đề, tóm tắt bằng tiếng Việt, kèm lí do chọn. **Kiểm chứng** đối chiếu từng **Tin** với văn bản **Bài gốc** và trả về kết luận đạt hoặc không đạt kèm lí do. **Tin** không đạt quay lại **Biên tập**, tối đa hai lần viết lại, sau đó bị bỏ. Công cụ của **Biên tập**: đọc toàn văn một **Bài gốc**, và tìm kiếm web để đọc bối cảnh.
- **Chụp ảnh**: nhận một địa chỉ, trả về một ảnh. Thứ tự: ảnh chụp trang bằng Playwright, rồi ảnh đại diện của bài, rồi không ảnh. Với video YouTube là ảnh chụp trang video.
- **Phát hành**: mỗi loại **Kênh đăng** là một bộ phát cùng giao diện, "phát **Bản tin** này". Mỗi bộ phát tự lo định dạng và giới hạn của nền tảng. Lỗi của một **Kênh đăng** không chặn các **Kênh đăng** khác.
- **Nhận Phản hồi**: nhận sự kiện từ Telegram qua webhook: bấm nút dưới **Tin**, và tin nhắn chữ gửi cho bot. Chủ hệ thống được nhận diện bằng mã người dùng Telegram đã khai.
- **Cải tiến**: mỗi tuần một agent đọc **Phản hồi** và các **Bản tin** của tuần, soạn một **Đề xuất cải tiến**. Đồng ý thì tạo phiên bản **Hướng dẫn** mới và đặt nó có hiệu lực; từ chối thì không đổi gì.
- **Lịch**: kích hoạt **Chạy Kỳ** theo giờ của từng **Chuyên mục**, thử lại sau 30 phút khi hỏng, tối đa ba lần, và kích hoạt việc thu thập định kỳ trong ngày.
- **Thông báo riêng**: bot nhắn cho chủ hệ thống khi **Kỳ** hỏng hoặc không phát, và khi phiên đăng nhập X cần nạp lại.
- **API trang quản lí**: thiết lập, theo dõi, cải tiến. Đăng nhập bằng một tài khoản duy nhất.

### Quy tắc của một Kỳ

- Một **Kỳ** xét các **Bài gốc** xuất hiện từ **Bản tin** trước của cùng **Chuyên mục**; lần đầu là 24 giờ gần nhất.
- Giờ phát mặc định: công nghệ 8:00, tài chính 12:00, thời sự 20:00.
- Mỗi **Bản tin** 5–7 **Tin**. Sau **Kiểm chứng** còn dưới ba **Tin** thì không phát, coi như **Kỳ** hỏng.
- Không có bước người duyệt.
- Chế độ xem trước chạy trọn **Kỳ** nhưng không gọi **Kênh đăng** và không tính các **Tin** đó là đã phát.

### Nguồn

- X: thu thập bằng Playwright với cookies và proxy do chủ hệ thống nạp. Chỉ lấy bài đăng gốc và chuỗi bài của chính tài khoản đó. Khi bị chặn hoặc hết phiên: bỏ qua X, báo riêng, **Kỳ** vẫn chạy. Bộ thu thập phải thay được bằng cách khác mà không đụng tới phần còn lại.
- YouTube: phát hiện video mới bằng API, lấy nội dung bằng cách tách audio và chuyển thành chữ.
- **Bảng xếp hạng**: lưu kèm mỗi **Bài gốc** thứ hạng và số sao hoặc số vote tại thời điểm lấy.
- Cookies phiên đăng nhập được mã hoá khi lưu. Khoá API và token bot nằm trong biến môi trường, không nằm trong cơ sở dữ liệu.

### Kênh đăng

- Telegram: một tin nhắn mở đầu, rồi mỗi **Tin** một tin nhắn ảnh có chú thích tối đa 1.024 ký tự gồm tiêu đề, tóm tắt, link, kèm hai nút 👍 và 👎.
- Zalo Bot: gửi vào cuộc trò chuyện riêng, mỗi tin nhắn tối đa 2.000 ký tự, cùng nội dung với Telegram.
- Facebook Page: mỗi **Bản tin** một bài đăng nhiều ảnh, phần chữ liệt kê các **Tin**.
- Nội dung **Tin** được viết một lần; mỗi bộ phát chỉ đổi định dạng. **Biên tập** viết trong giới hạn của Telegram.

### LLM

- Mọi lời gọi đi qua một endpoint tương thích OpenAI, cấu hình bằng địa chỉ, khoá và tên model. Mỗi vai trò (sơ tuyển, **Biên tập**, **Kiểm chứng**, cải tiến) cấu hình model riêng. Gemini và Anthropic là lựa chọn thay thế cho từng vai trò.
- Kết quả có cấu trúc do LLM trả về được kiểm tra bằng code, không tin vào tính năng của endpoint.
- Mọi lần gọi của agent được ghi vết lên Langfuse bản cloud. Lí do chọn, lí do loại và kết quả từng bước vẫn được lưu trong cơ sở dữ liệu của hệ thống; trang quản lí không phụ thuộc vào Langfuse để hiển thị.
- Công cụ tìm kiếm web mặc định là Tavily, thay được bằng Brave.

### Dữ liệu

- Các thực thể: **Chuyên mục**, **Nguồn**, **Kênh đăng**, **Bài gốc**, **Tin**, **Bản tin**, **Kỳ**, **Hướng dẫn** (theo phiên bản), **Phản hồi**, **Đề xuất cải tiến**.
- **Nguồn** và **Chuyên mục** là quan hệ nhiều-nhiều. **Kênh đăng** và **Chuyên mục** cũng vậy.
- Một **Tin** có nhiều **Bài gốc**, trong đó đúng một là **Bài gốc chính**.
- **Hướng dẫn** của **Biên tập** gắn với từng **Chuyên mục**; **Hướng dẫn** của **Kiểm chứng** là một bản chung. Mỗi thứ có đúng một phiên bản đang có hiệu lực. Mỗi **Kỳ** ghi lại phiên bản nó dùng.
- **Kỳ** lưu kết quả từng bước: ứng viên sau gom, danh sách sơ tuyển, lựa chọn và lí do của **Biên tập**, từng lượt **Kiểm chứng**, kết quả từng **Kênh đăng**, chi phí LLM.
- **Bài gốc** và ảnh chụp giữ 90 ngày. **Bản tin**, **Tin** đã phát, **Phản hồi** và các phiên bản **Hướng dẫn** giữ vĩnh viễn.

### Trang quản lí

- Ba tầng: thiết lập, theo dõi, cải tiến. Giao diện tiếng Việt, dùng được trên điện thoại, có chế độ sáng và tối.
- **Hướng dẫn** ban đầu cho ba **Chuyên mục** và cho **Kiểm chứng** được soạn sẵn theo phạm vi đã thống nhất; chủ hệ thống sửa trên trang.
- Danh sách RSS và **Bảng xếp hạng** khởi đầu được soạn sẵn và đã kiểm tra từng địa chỉ; tài khoản X và kênh YouTube do chủ hệ thống nhập.

## Testing Decisions

Test tốt chỉ kiểm tra hành vi nhìn thấy được từ bên ngoài module: cho đầu vào, khẳng định về thứ được gửi đi và thứ được lưu lại. Không khẳng định về thứ tự gọi hàm bên trong, câu chữ của prompt, hay cấu trúc trạng thái của vòng agent.

Ba điểm kiểm thử, đã được chủ hệ thống đồng ý:

1. **Chạy Kỳ** (điểm chính). Đầu vào: **Bài gốc** giả từ **Nguồn** giả, LLM trả lời theo kịch bản, đồng hồ giả, Postgres thật. Khẳng định về những gì tới **Kênh đăng** giả và những gì được lưu. Phủ: gom nhiều **Bài gốc** thành một **Tin**; chọn 5–7 **Tin**; viết lại tối đa hai lần rồi bỏ; dưới ba **Tin** thì không phát; không phát lại **Tin** cũ; nhãn "Cập nhật"; một **Nguồn** hỏng vẫn ra **Bản tin**; một **Kênh đăng** hỏng không chặn kênh khác; chế độ xem trước không đăng; thử lại khi hỏng; thông báo riêng.
2. **API trang quản lí**. Gọi API thật với Postgres thật: thiết lập **Chuyên mục**, **Nguồn**, **Kênh đăng**; lịch sử **Kỳ**; phiên bản **Hướng dẫn** và quay lui; đồng ý và từ chối **Đề xuất cải tiến**; đăng nhập.
3. **Từng bộ nối ra bên ngoài**. Mỗi bộ thu thập, mỗi bộ phát, chụp ảnh và chuyển audio được test riêng bằng dữ liệu đã ghi lại, không gọi mạng: đọc đúng phản hồi mẫu của RSS, X, YouTube, **Bảng xếp hạng**; dựng đúng tin nhắn Telegram, Zalo, bài đăng Facebook trong giới hạn ký tự; xử lí đúng các phản hồi lỗi.

Ngoài ba điểm trên có một **bộ đánh giá agent** chạy riêng với LLM thật trên một tập **Bài gốc** mẫu, không chặn build: **Kiểm chứng** có bắt được **Tin** có chi tiết bịa không, bản dịch có đúng nghĩa không, **Biên tập** có chọn đúng phạm vi **Chuyên mục** không. Chạy lại mỗi khi đổi model hoặc **Hướng dẫn** mặc định.

Chưa có test nào trong repo để làm mẫu; các test đầu tiên của lát cắt đầu sẽ đặt khuôn cho phần còn lại.

## Out of Scope

- So sánh cách các **Nguồn** đưa cùng một tin, nhận định "tin này có nghĩa gì với mình", theo dõi xu hướng nhiều ngày.
- Tin nóng phát ngay khi phát hiện.
- Nhiều người quản lí, hoặc người ngoài tự tạo **Chuyên mục**.
- Người duyệt trước khi đăng.
- Agent tự áp dụng thay đổi **Hướng dẫn**.
- **Tin** lấy từ kết quả tìm kiếm web ngoài danh sách **Nguồn**.
- Đăng vào nhóm Facebook, nhóm Zalo, và Zalo Official Account.
- API chính thức của X.
- Crypto, bảng giá chứng khoán, khuyến nghị mua bán.
- Tự chạy Langfuse trên server.
- **Phản hồi** qua Zalo và Facebook; chỉ Telegram có nút và nhận tin nhắn.

Các mục hoãn có chủ đích được giữ ở `.scratch/backlog.md`.

## Further Notes

### Thứ tự làm

1. Lát cắt đầu: **Chuyên mục** công nghệ, chỉ **Nguồn** RSS, trọn dây chuyền tới Telegram lúc 8:00 (thu thập, gom **Tin**, sơ tuyển, **Biên tập**, **Kiểm chứng**, chụp ảnh, phát), kèm tầng thiết lập và theo dõi tối thiểu.
2. **Bảng xếp hạng**.
3. X.
4. YouTube.
5. Hai **Chuyên mục** còn lại.
6. **Phản hồi** và **Đề xuất cải tiến**, cùng tầng cải tiến của trang quản lí.
7. Zalo Bot.
8. Facebook Page.

### Cần thử trước khi dựa vào

- ~~Tool calling qua endpoint tương thích OpenAI với model định dùng.~~ Đã thử ở ticket 02: chạy được, vòng agent đi qua endpoint. Kết quả có cấu trúc lấy bằng prompt hoặc tool calling, không dùng `response_format` kiểu `json_schema`. Chi tiết và model cho từng vai trò ở `docs/llm-endpoint.md`.
- Zalo Bot có chủ động gửi tin cho người dùng được không. Nếu không, Zalo bị loại khỏi phạm vi.
- Bài đăng lên Facebook Page từ app ở chế độ Development có hiện với người ngoài không; nếu không thì chuyển app sang Live.
- Playwright có lấy được X và trang video YouTube từ IP server qua proxy không.
- ~~Endpoint có định tuyến được lời gọi tạo vector nhúng không.~~ Đã thử ở ticket 02: không. Gom **Tin** dùng model nhúng tự chạy `BAAI/bge-m3`; ticket 06 kiểm lại lựa chọn này.

### Rủi ro đã biết và đã chấp nhận

- Điều khoản của X cấm thu thập tự động; tài khoản dùng để đăng nhập có thể bị hạn chế. Nên dùng tài khoản phụ.
- Điều khoản của YouTube cấm truy cập tự động và tải nội dung.
- Zipformer của hynt có giấy phép CC BY-NC-ND 4.0, chỉ dùng phi thương mại. Cần xem lại nếu trang Facebook có kiếm tiền.
- Facebook Page là công khai và không có người duyệt; **Kiểm chứng** là chốt chặn duy nhất.
- Nếu endpoint LLM chạy trên gói thuê bao thay vì khoá API trả theo lượng dùng, một hệ thống chạy tự động có thể vi phạm điều khoản của nhà cung cấp và làm cạn hạn mức dùng chung.

### Còn mở

- Chưa ghi ADR cho việc thu thập X và YouTube bằng trình duyệt tự động thay vì API chính thức; chờ chủ hệ thống nêu lí do.
- Chưa chọn biến thể Zipformer (30M hay 150M).
