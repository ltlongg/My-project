# Agent chỉ ở phần phán đoán, phần còn lại là dây chuyền cố định

Chủ hệ thống muốn các agent AI tự làm việc, tự kiểm tra và tự cải tiến. Ta chọn hình dạng lai: thu thập **Bài gốc**, gom thành **Tin** và đăng lên **Kênh đăng** là các bước cố định chạy theo lịch; chỉ việc chọn và viết **Tin** (**Biên tập**), đối chiếu với **Bài gốc** (**Kiểm chứng**) và đề xuất sửa hướng dẫn là do agent làm. Lý do: các bước cố định lặp lại y hệt mỗi lần nên agent ở đó chỉ thêm chậm và khó dò lỗi, trong khi một **Bản tin** sai đúng giờ phát hành mà không biết bước nào gây ra thì rất khó sửa.

## Considered Options

- **Dây chuyền cố định hoàn toàn**, LLM chỉ làm từng việc nhỏ: bị loại vì mất khả năng tự kiểm tra và tự cải tiến mà chủ hệ thống muốn.
- **Đội agent tự chủ hoàn toàn**, một agent điều phối tự lập kế hoạch và giao cả việc thu thập: bị loại vì kém ổn định; chỉ đáng chọn nếu học về agent là mục tiêu riêng.

## Consequences

- Không có người duyệt trước khi đăng, nên **Kiểm chứng** là chốt chặn duy nhất: **Tin** không qua được sau hai lần viết lại thì bị bỏ khỏi **Bản tin**.
- Agent không tự sửa hướng dẫn của mình. Thay đổi chỉ có hiệu lực khi chủ hệ thống đồng ý với đề xuất, và mọi phiên bản hướng dẫn được giữ lại để quay lui.
