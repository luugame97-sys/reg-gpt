# Trạng thái bàn giao — 02/11/2026

Đọc cùng [AGENTS.md](../AGENTS.md), [cài máy mới](SETUP_VI.md) và [quy trình VPS](DEPLOYMENT.md). Đây là bản public, không chứa database hoặc credential; phải kiểm tra lại Git/VPS trước khi thay đổi.

## Mã nguồn và đồng bộ

- Nhánh bàn giao: `main` tại [luugame97-sys/reg-gpt](https://github.com/luugame97-sys/reg-gpt). Lịch sử sạch bắt đầu ở `2dd9a0986b6e733d236d9d4158eefb80d43a9f07`; không đưa lịch sử local cũ lên lại.
- Bản cập nhật này bổ sung source/test của fix lag, `AGENTS.md` tự commit/push và deploy có điều kiện, cùng tài liệu chuyển máy. SHA của snapshot là commit chứa báo cáo này; trạng thái push phải được đối chiếu với remote, không suy ra chỉ từ file báo cáo.
- Toàn bộ source/test/tài liệu cần chạy ứng dụng nằm trong Git. Không có DB, secret, dependency đã cài, build frontend hoặc bộ helper triển khai private. Clone mới cần cài/build; muốn điều khiển VPS cần cấu hình SSH riêng.

## Runtime đã triển khai

- Bản mới nhất đã xác minh: **`ui-smooth-20261102-055026`**, entry `index-rUGTG7i_.js`; 59/59 file hash khớp và health HTTP 200 tại thời điểm deploy. Không cần restart lại chỉ để đồng bộ Git/docs.
- Đã đồng đều kích thước nhãn thư mục/quốc gia/gói ở Tài khoản, nhóm nhãn tương tự ở UPI; gồm PC, mobile và dialog.
- Fix lag: chỉ mount PC hoặc mobile; tách đồng hồ sang component con; cache định dạng ngày/quota theo locale; dựng menu/popover khi mở; giảm duyệt lặp DOM dịch; hủy/bỏ request cũ khi chuyển trang/thư mục. API `include_summary` mặc định true; giao diện tái dùng summary tối đa 30 giây, vẫn tải mới hàng/tổng lọc và refresh khi cần.
- File chính: `webui/app.py`, `webui/frontend/src/views/Registered.vue`, các component `AccountCredentials.vue`, `AccountQuota.vue`, `UpiAccount.vue`, `api/request.js`, `api/register.js`, `i18n/domTranslator.js`. Không thêm dependency trong fix lag.

## Kiểm chứng và giới hạn

- Fix lag: **162 Node test + 59 Python test liên quan đạt**, Vite production build và kiểm tra whitespace đạt. Python: `tests/test_account_workspace.py`, `tests/test_account_filters.py`, `tests/test_account_quota.py`. Đồng bộ Git/docs tái sử dụng kết quả này vì runtime/test không thay đổi tiếp.
- Live 50 hàng: DOM 14.550 → 4.625. Fixture 250 account giả: cuộn PC 3 giây có long task 4 → 0; tác vụ render dài nhất khi chuyển thư mục 2.740 → 371 ms. Đây là mẫu ngắn, không phải cam kết FPS/latency trên mọi máy hay benchmark tải production.
- Đã kiểm tra chọn qua trang/PC-mobile, menu, quota, VI/EN/ngày giờ, OTP và mở thư mục live; không tràn ngang, không lỗi console trong các lượt kiểm tra. Không chạy đăng ký, refresh token, quét hay thanh toán thật để thử.
- Lần full Python trước fix lag: **1.065 đạt / 63 lỗi / 6 skip**. Lỗi cũ tập trung `test_upi_followup.py` (12) và `test_upi_local.py` (51), còn kỳ vọng local/auto-refresh trái chính sách YTC-only/chỉ chuyển thư mục. Chưa sửa các suite này hoặc chạy lại toàn bộ sau fix lag; không gọi toàn bộ test là xanh. Sáu skip cần helper private; chi tiết ở [DEVELOPMENT.md](DEVELOPMENT.md).
- Chưa kiểm trên máy mới hoàn toàn, điện thoại thật/Safari, tải đồng thời hoặc E2E provider/thanh toán. Không thay đổi chính sách UPI chỉ để vượt các test cũ.

## Tiếp tục

1. Clone/pull, đọc `AGENTS.md`, kiểm tra branch và source; cài/build theo `SETUP_VI.md` nếu máy mới.
2. Nếu sửa runtime, đối chiếu lại VPS và gate; release đang chạy đã chứa fix lag. Backup gần nhất: `/opt/gpt-reg-review/_ai_workbench/backups/ui-smooth-20261102-055026`; rollback có kiểm tra drift/idle, chỉ kiểm cú pháp, chưa thực thi; không tự restore DB.
3. Frontend production được build local. Tại lần deploy gần nhất, manifest npm trên VPS chưa ghi dependency lucide đã có trong bundle từ bản layout trước; đừng chạy npm ci/build từ manifest VPS một cách mù quáng. Dùng package/lockfile đã kiểm tra trong Git và build từ checkout nguồn sạch cho release mới.
4. Helper/bằng chứng chi tiết trên máy cũ ở `_ai_workbench/` và không được publish. Máy mới không có chúng: dùng runbook, quyền SSH riêng và kiểm tra lại; không tải toàn bộ workbench hoặc secret lên GitHub để bù thiếu.
5. Việc tồn đọng ngoài phạm vi đồng bộ: đánh giá từng test UPI cũ với chính sách hiện tại; đo thêm trên thiết bị thật nếu người dùng tiếp tục yêu cầu tối ưu.
