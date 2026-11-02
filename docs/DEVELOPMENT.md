# Bàn giao mã nguồn — 02/11/2026

Đọc [AGENTS.md](../AGENTS.md) để áp dụng quy tắc tự đồng bộ, [trạng thái mới nhất](session_report.md) để tiếp tục công việc và [quy trình VPS](DEPLOYMENT.md) trước khi triển khai.

## Phạm vi bản xuất

Bản này lấy mã nguồn hiện có từ workspace đang phát triển, gồm backend Python/FastAPI, frontend Vue, test và giấy phép. Các cập nhật trước đó chưa commit cũng được đưa vào bản xuất. Không chứa database, tài khoản thật, cấu hình production, log, backup, bản build hoặc workbench riêng.

Lịch sử Git local trước lần xuất này từng chứa khóa API đã được bỏ khỏi source. Nhánh GitHub bắt đầu bằng commit gốc mới, không có các commit cũ làm parent. Lịch sử cũ chỉ giữ local để đối chiếu; không push các nhánh lịch sử cũ, `--all` hoặc `--mirror`.

## Các phần chính

| Phần | Đường dẫn |
|---|---|
| API và vòng đời ứng dụng | `webui/app.py` |
| Database và migration | `webui/db.py` |
| Đăng ký / mail / môi trường | `auth_flow.py`, `mail_providers/`, `webui/registrar.py`, `webui/environment.py`, `webui/mail_supply.py` |
| Tài khoản, gói và quota | `webui/account_*.py` |
| Refresh token và tác vụ | `webui/token_refresh.py`, `webui/token_refresh_jobs.py` |
| UPI và Camellia | `webui/upi*.py`, `webui/camellia.py` |
| Giao diện, ngôn ngữ, trạng thái tác vụ | `webui/frontend/src/` |
| Kiểm thử | `tests/` |

## Trạng thái và ràng buộc cần giữ

- Giao diện mặc định tiếng Việt, hỗ trợ tiếng Anh/Trung; đã có bố cục PC/mobile, bộ lọc tài khoản, thư mục, quota, tiến độ tác vụ và thống kê lưu lượng.
- UPI có xuất LS, chọn nhiều trang, tạm dừng/tiếp tục và âm thanh theo cài đặt. API hiện chỉ cho provider YTC; chế độ local/Camellia cũ còn mã nguồn nhưng không được bật qua API.
- Khi YTC báo quét thành công, công cụ chuyển tài khoản sang thư mục `PLUS`. Đây là thao tác phân loại thư mục; không đồng nghĩa đã kiểm chứng độc lập gói thuê bao.
- Không tự làm mới AT/plan/quota sau quét. Cưỡng chế refresh cần giữ bước xác nhận và đúng phạm vi lựa chọn. Không thay đổi các chính sách này chỉ để xử lý lỗi giao diện.
- Snapshot triển khai gần nhất là `ui-smooth-20261102-055026` (fix lag), đã gồm bản đồng đều nhãn `account-badges-20261102-050951`. Phải kiểm tra lại source và trạng thái VPS trước lần triển khai tiếp theo.
- Đã giảm render trùng PC/mobile, tách clock/cache formatter, lazy overlay, giảm duyệt DOM dịch và tránh tải lại summary không cần thiết. Chi tiết và số đo có giới hạn trong `docs/session_report.md`.
- Chưa có bằng chứng E2E thực tế cho toàn bộ đăng ký, thanh toán hoặc provider UPI. Các snapshot tác vụ local/Camellia trước đây không chứng minh luồng đang được hỗ trợ hiện tại thành công.

## Kiểm chứng

- Bản fix lag mới nhất: **162 test Node + 59 test Python liên quan/build/whitespace đạt**; đã kiểm tra UI fixture và live PC/mobile. Không chạy lại toàn bộ Python trong fix lag; các kết quả full suite bên dưới thuộc lần xuất source trước đó.

- Build frontend đạt; 157 test Node đạt. Đã dùng dependency Node có sẵn và đối chiếu package/lockfile, chưa cài lại toàn bộ dependency trong môi trường mới hoàn toàn.
- Trên checkout chỉ có source: 1.065 test Python đạt, 63 thất bại, 6 skip. Sáu test skip cần helper triển khai riêng không nằm trong GitHub; khi chạy tại workspace có helper, cả sáu test đạt.
- 63 lỗi nằm trong `tests/test_upi_followup.py` (12) và `tests/test_upi_local.py` (51). Các suite còn kỳ vọng provider local hoặc tự refresh/kiểm tra gói/quota trong khi API hiện đã khóa YTC-only và chỉ chuyển thư mục. Cần đánh giá và đồng bộ từng test với chính sách hiện tại; chưa sửa các suite này trong lần xuất mã. Bốn test chính sách hiện tại ở `tests/test_upi_ytc_only.py` đều đạt trong lần chạy toàn bộ.
- Smoke ASGI với database rỗng: HTML, health, stats và asset frontend đều HTTP 200; không có lần thử gọi mạng bên ngoài. Đây là kiểm tra ứng dụng trong môi trường thử, chưa phải luồng provider/thanh toán thật hoặc thử trên máy khác.

## Cách tiếp tục

1. Đọc `AGENTS.md`, `docs/session_report.md`, `docs/SETUP_VI.md`; kiểm tra Git và các file liên quan trước khi sửa.
2. Giữ các thay đổi đang làm của người khác, không đổi kiến trúc/dependency ngoài yêu cầu.
3. Chạy kiểm tra phù hợp; phân biệt test fixture, build và luồng provider thật.
4. Tự commit/push mã nguồn đã kiểm tra và bản bàn giao public để máy khác có thể pull. Runtime triển khai theo `docs/DEPLOYMENT.md` khi có quyền/gate/rollback; docs-only không restart. Không tự đồng bộ database qua Git.
5. Nếu có workbench local, file hỗ trợ nằm trong `_ai_workbench/{tools,temp,logs,backups,reports}/`; chỉ tạo khi cần và không đưa thông tin riêng lên GitHub.

Giữ giấy phép AGPL-3.0 ở `LICENSE`, giấy phép thành phần trong `webui/licenses/` và credit thiết kế có sẵn trong source.
