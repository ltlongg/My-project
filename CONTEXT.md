# Bản tin tự động

Hệ thống cá nhân thu thập tin tức từ nhiều nơi, chọn lọc và tóm tắt sang tiếng Việt, rồi đăng thành bản tin định kỳ lên các nơi do chủ hệ thống quản lí.

## Language

### Nội dung

**Chuyên mục**:
Một dòng bản tin theo một lĩnh vực (ví dụ công nghệ, thời sự, tài chính), có **Nguồn**, giờ phát hành và **Kênh đăng** riêng.
_Avoid_: Agent, topic, feed, chủ đề

**Bản tin**:
Một lần phát hành của một **Chuyên mục** vào giờ cố định, gồm một số ít **Tin** đáng đọc nhất trong kỳ.
_Avoid_: Digest, newsletter, bài đăng

**Kỳ**:
Một lần hệ thống làm việc cho một **Chuyên mục** tại một giờ phát hành, kết thúc bằng một **Bản tin** được phát hoặc không phát.
_Avoid_: Run, lần chạy, job

**Tin**:
Một sự kiện hoặc câu chuyện, được gom từ một hay nhiều **Bài gốc** cùng nói về nó; là một mục trong **Bản tin**.
_Avoid_: Bài, story, cụm bài

**Bài gốc**:
Một nội dung nguyên bản do bên ngoài xuất bản (bài báo, bài đăng, video) mà hệ thống thu thập về, chưa qua xử lí.
_Avoid_: Bài viết, article, tin

**Bài gốc chính**:
**Bài gốc** duy nhất mà một **Tin** dẫn link và lấy ảnh chụp khi phát hành, ưu tiên nơi đưa tin đầu tiên hoặc nguồn gốc nhất.
_Avoid_: Nguồn chính, link chính

### Đầu vào và đầu ra

**Nguồn**:
Một nơi cụ thể hệ thống lấy **Bài gốc** về: một RSS feed, một tài khoản X, một kênh YouTube, hoặc một **Bảng xếp hạng**.
_Avoid_: Kênh, source, feed

**Bảng xếp hạng**:
Một **Nguồn** liệt kê những thứ đang được chú ý kèm tín hiệu về độ nổi (thứ hạng, số sao, số vote), ví dụ GitHub Trending hay Hugging Face Daily Papers.
_Avoid_: Trending, top list

**Kênh đăng**:
Một nơi cụ thể **Bản tin** được phát hành tới: một nhóm Telegram, một cuộc trò chuyện Zalo, một trang Facebook.
_Avoid_: Kênh (đứng một mình), channel, nhóm

### Agent

**Agent**:
Một vai trò AI có hướng dẫn riêng, tự đưa ra phán đoán trong phần việc của mình khi làm một **Bản tin**. Phần thu thập, gom bài và đăng không phải agent.
_Avoid_: Bot, worker; không dùng "agent" để chỉ **Chuyên mục**

**Biên tập**:
**Agent** chọn **Tin** nào vào **Bản tin** và viết nội dung từng **Tin**.
_Avoid_: Editor, writer, agent phân tích

**Kiểm chứng**:
**Agent** đối chiếu từng **Tin** đã viết với **Bài gốc** của nó và trả lại cho **Biên tập** nếu sai lệch.
_Avoid_: Kiểm duyệt, duyệt, reviewer

### Cải tiến

**Hướng dẫn**:
Văn bản chỉ dẫn một **Agent** cách làm phần việc của mình, có nhiều phiên bản và chỉ một phiên bản đang có hiệu lực.
_Avoid_: Prompt, cấu hình, tiêu chí

**Phản hồi**:
Đánh giá của người đọc về một **Tin** đã phát hành: thích, không thích, hoặc một lời nhắn bằng chữ.
_Avoid_: Feedback, rating, đánh giá

**Đề xuất cải tiến**:
Một thay đổi cụ thể đối với **Hướng dẫn** hoặc danh sách **Nguồn**, do agent soạn định kỳ từ **Phản hồi** và chỉ có hiệu lực khi chủ hệ thống đồng ý.
_Avoid_: Tự cải tiến, auto-tune
