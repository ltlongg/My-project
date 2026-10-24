# 07: Sơ tuyển

**What to build:** **Biên tập** không phải đọc hàng trăm ứng viên mỗi **Kỳ**. Một bước cố định chấm điểm các ứng viên **Tin** và chỉ chuyển tối đa khoảng 30 ứng viên điểm cao nhất cho **Biên tập**. Điểm dựa trên độ mới, số **Bài gốc** cùng nói về sự kiện, và mức phù hợp với phạm vi **Chuyên mục** do một model nhỏ chấm. Đây là bước cố định, không phải agent (ADR 0001).

**Blocked by:** 06

**Status:** ready-for-human

- [x] Mỗi ứng viên **Tin** có một điểm và các thành phần của điểm được lưu lại
- [x] **Biên tập** chỉ nhận số ứng viên trong giới hạn; giới hạn cấu hình được
- [x] Ứng viên bị loại ở bước này được lưu, kèm điểm
- [x] Ứng viên ngoài phạm vi **Chuyên mục** (ví dụ crypto trong tài chính) bị điểm thấp và không tới **Biên tập**
- [x] Cách tính điểm nhận được thêm tín hiệu mới mà không đổi phần còn lại, để ticket **Bảng xếp hạng** cắm vào
- [x] Bước sơ tuyển dùng cấu hình model riêng
- [x] Test tại điểm "Chạy Kỳ" với nhiều ứng viên khẳng định chỉ nhóm điểm cao tới **Biên tập**

## Comments

**2026-10-24, agent.** Code xong trên nhánh `feat/shortlisting`, chưa commit. 119 test xanh; mypy và ruff sạch. Code chính ở `src/siftly/shortlisting.py`, migration `0005_shortlisting.py`, test tại điểm "Chạy Kỳ" ở `tests/test_shortlisting.py`.

Cách tính điểm:

- **Điểm = mức phù hợp × (0,5 + 0,5 × độ chú ý).** Mức phù hợp (0–10 do model nhỏ chấm, lưu dạng 0–1) quyết định chính; độ chú ý chỉ làm điểm lớn gấp đôi là cùng. Nhờ vậy một tin crypto mới và nhiều nơi đưa không vượt được tin đúng phạm vi nhưng cũ hơn.
- **Độ chú ý** là trung bình có trọng số của các tín hiệu trong `ATTENTION_SIGNALS`: độ mới (giảm một nửa sau mỗi 12 giờ, tính từ **Bài gốc** mới nhất của ứng viên) và số **Bài gốc** (1 bài là 0, 2 bài 0,5, 3 bài 0,75…). Mỗi tín hiệu là một hàm nhận các **Bài gốc** của ứng viên, trả số 0–1, kèm trọng số. Ticket 17 thêm một mục `"leaderboard"` vào đó; test `test_new_signal_plugs_in_without_changing_the_others` làm đúng việc này.
- **Ngưỡng phạm vi 0,3**: ứng viên chấm dưới 3/10 không tới **Biên tập** kể cả khi còn chỗ trong giới hạn. Nếu không còn ứng viên nào trong phạm vi thì **Kỳ** "Không phát" với lí do "Không ứng viên Tin nào trong phạm vi Chuyên mục".

Đã thử thật tới đâu:

- **Model thật trên RSS thật**, không qua cơ sở dữ liệu (kịch bản tạm, mỗi **Bài gốc** một ứng viên): 64 mục từ VnExpress công nghệ, VnExpress kinh doanh, The Verge và CoinDesk, model `ag/gemini-3.8-flash-low`, mỗi lần chấm cả 64 ứng viên mất khoảng 5 giây (2 lời gọi). Với Hướng dẫn công nghệ hiện có, tin giá vàng, lãi suất, thuế đều được 0 điểm. Với một Hướng dẫn tài chính thử ("Không chọn: tiền mã hoá…"), mọi tin Bitcoin, Ethereum, stablecoin đều được 0–0,2 và không qua. Ở công nghệ, vài tin crypto lấn sang AI hay bảo mật được 0,3–0,7 và vẫn qua, điều này hợp lí.
- **Migration 0005** chạy trên một bản sao của cơ sở dữ liệu phát triển: 12/12 ứng viên cũ có `shortlisted = true` và `score` trống, `sections.shortlist_size` = 30. Hạ cấp rồi nâng lại đều chạy. `alembic check` không thấy lệch nào ở các bảng của ta. Cơ sở dữ liệu phát triển **chưa** được nâng lên 0005.
- **Chưa chạy trọn một Kỳ thật**, vì `.env` chưa có `TELEGRAM_BOT_TOKEN`.

Chuyển sang `ready-for-human` vì còn những việc cần chủ hệ thống:

- **Chọn `SHORTLIST_MODEL`.** `ds/deepseek-chat`, model `docs/llm-endpoint.md` chọn cho Sơ tuyển, không còn trên endpoint. Đề xuất `ag/gemini-3.8-flash-low`: nó đã chạy tốt trong lần thử ở trên, nhưng chưa qua `siftly probe-llm`. Để trống thì Sơ tuyển dùng `MODEL`, tức `cx/gpt-6-luna`, chạy được nhưng tốn hơn.
- Chạy `uv run siftly init` (hoặc một Kỳ) để nâng cơ sở dữ liệu phát triển lên 0005.
- Xem qua các quyết định dưới đây.
- Commit.

Quyết định đã tự chọn, cần chủ hệ thống xác nhận:

- **Phạm vi Chuyên mục lấy từ Hướng dẫn của Biên tập**, không có cột "phạm vi" riêng. Model chấm điểm đọc nguyên Hướng dẫn đó, kể cả mục "Không chọn". Hệ quả: sửa Hướng dẫn (ticket 23) đổi luôn cách sơ tuyển.
- **Giới hạn là cột `sections.shortlist_size`**, mặc định 30, để trang quản lí (ticket 10/11) sửa được theo từng **Chuyên mục**. Không phải biến môi trường.
- **Mọi ứng viên đều được lưu** ở bảng `candidates`, kèm `score`, `score_components` (JSONB, theo tên tín hiệu) và `shortlisted`. `position` giờ là thứ hạng theo điểm, và **Biên tập** thấy các ứng viên đã qua theo đúng thứ tự đó, thay vì mới nhất trước. Tín hiệu mới không cần migration.
- **Không lưu lí do loại.** Lí do suy ra được từ điểm: `relevance` < 0,3 là ngoài phạm vi, còn lại là không lọt vào nhóm đầu.
- **Chấm theo lô 40 ứng viên, tối đa 4 lời gọi cùng lúc.** Trả lời hỏng (thiếu, thừa hay trùng ứng viên, điểm ngoài 0–10, không gọi `rate`) thì được trả lại kèm lí do, tối đa 3 lần. Model lỗi thì **Kỳ** hỏng với lí do "Sơ tuyển gặp lỗi: …" trước khi gọi **Biên tập**. Vector nhúng đã tạo vẫn được lưu, nên **Kỳ** sau không phải nhúng lại.
- **Kỳ chạy tiếp dùng lại điểm đã lưu**, không chấm lại.

Ghi chú cho các ticket sau:

- Ticket 12: "danh sách sơ tuyển" là `Run.shortlist`; ứng viên bị loại là `candidates.shortlisted = false`, kèm điểm thành phần để hiển thị.
- Ticket 15: nên đo mức phù hợp do model chấm trên nhiều ngày, nhất là các tin ở rìa phạm vi (crypto lấn sang AI, chính sách công nghệ), và xem ngưỡng 0,3 có hợp không.
- Ticket 17: thêm `"leaderboard": Signal(trọng_số, hàm)` vào `ATTENTION_SIGNALS`; hàm đọc thứ hạng hay số sao đã lưu kèm **Bài gốc**.
- `docs/llm-endpoint.md` cần chạy lại `probe-llm` vì danh sách model trên endpoint đã đổi nhiều (không còn nhóm `ds/`, có thêm nhóm `ag/`).
