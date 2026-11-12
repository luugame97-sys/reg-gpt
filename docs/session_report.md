# Trạng thái bàn giao — 12/11/2026

Đọc cùng [AGENTS.md](../AGENTS.md), [cài máy mới](SETUP_VI.md) và [quy trình VPS](DEPLOYMENT.md). Đây là bản public, không chứa database hoặc credential; phải kiểm tra lại Git/VPS trước khi thay đổi.

## Form đăng nhập web và truy cập IP — 12/11/2026 — CHỜ GATE VPS

- Thêm form đăng nhập VI/EN/ZH, sáng/tối, hiện/ẩn mật khẩu, báo lỗi và đếm thời gian khóa; giữ trang đang mở sau đăng nhập. Có nút đăng xuất. Giao diện chỉ tải dữ liệu/tác vụ sau khi xác nhận phiên; API hết phiên đưa về form, không gọi hộp Basic của trình duyệt.
- Backend dùng lại file hash mật khẩu quản trị đang có, không chuyển mật khẩu vào Git/DB/frontend. Phiên ngẫu nhiên giữ ở RAM tối đa 12 giờ, cookie HttpOnly/SameSite=Strict; HTTPS có Secure, HTTP chỉ cho IP được cấu hình rõ. Đăng xuất, hết hạn hoặc đổi file mật khẩu làm mất hiệu lực phiên. Giữ giới hạn 3 lần thử/5 phút và khóa 15 phút, chặn ghi khác Origin, bảo vệ API/SSE/OpenAPI và ẩn thống kê health khi chưa đăng nhập. Local chưa cấu hình auth vẫn dùng như trước; yêu cầu loopback trực tiếp phục vụ vận hành, request qua proxy phải đăng nhập.
- File chính: `webui/web_auth.py`, `webui/app.py`, `frontend/src/{App.vue,webAuth.js}`, `components/WebLogin.vue`, `api/request.js`, `layouts/AdminLayout.vue`, `locales/ui.js`. Không thêm dependency. Kiểm hash Unix cần native `crypt`, đã kiểm trên Linux Python 3.10; backend thiếu hỗ trợ hoặc file mật khẩu lỗi trả lỗi đóng, không mở quyền truy cập.
- Kiểm chứng: **76 Python đạt, 1 skip native Unix trên Windows** (đã kiểm lại bằng smoke Linux), **168 Node đạt**, build Vite đạt. HTTP fixture thực hiện đăng nhập → API kho rỗng → đăng xuất → API bị chặn. Test bao gồm cookie, Origin, giả header proxy, hết hạn/thu hồi phiên, đổi hash, input quá lớn và 8 lần đăng nhập sai đồng thời. DB local giữ nguyên hash. Không thử account/provider/thanh toán thật. Công cụ UI bị chặn vì không xác nhận URL cửa sổ Chrome; chưa xác minh form trên Chrome thật hoặc mobile.
- Gói private đã stage và smoke hash/phiên trên VPS đạt; **chưa áp dụng** vì có background refresh đang chạy. Giữ Basic và firewall production hiện tại; không restart, hủy job, mở cổng hoặc tự đặt monitor chờ. Sau push cần kiểm lại gate/CAS, backup nguồn + SQLite, bật auth backend trước khi bỏ Basic/mở đúng cổng IP; giữ asset cũ. Rollback đã chuẩn bị và kiểm cú pháp, chưa chạy. Thông tin đích, cấu hình bảo mật và proof chi tiết chỉ giữ trong workbench private.

## Sửa nhận diện OTP và quét lại lỗi gói — 12/11/2026

- Đăng nhập thông thường giữ lỗi mạng/máy chủ, không chuyển sang đăng ký dự phòng. Chỉ chờ OTP email khi có trạng thái email verification hoặc đúng đường dẫn xác minh; URL thiếu hoặc chuỗi xác minh nằm trong query không đủ bằng chứng. Luồng mật khẩu/2FA và OTP email thực sự vẫn được giữ.
- Đợt kiểm tra gói thử tối đa 3 proxy cho lỗi kết nối khi đọc gói. Chỉ lượt đầu được làm mới AT; đổi proxy không đăng nhập lại. HTTP 401/403/429 và lỗi chứng chỉ không bị coi là lý do tự đổi proxy. Giữ kiểm tra TLS và dừng khi gặp giới hạn tốc độ.
- Tài khoản/Tác vụ có **Quét lại tài khoản lỗi**, đọc đầy đủ kết quả theo job gốc, kiểm lại tình trạng tài khoản và chống gửi trùng. Có lựa chọn **Kiểm tra lại lỗi OTP mail đã lưu**, mặc định tắt; chỉ bỏ trạng thái chờ OTP trong lượt người dùng yêu cầu, vẫn chặn khóa/sai thông tin. Không xóa lỗi cũ hàng loạt hoặc tự chạy lại lịch sử.
- UI cho xem số lượng trước khi bắt đầu, chọn proxy/worker; retry mặc định tối đa 10 worker. Bỏ qua acc đã kiểm tra gói thành công, đã xóa hoặc bị chặn, không quét lại toàn kho.
- Kiểm chứng: 337 Python liên quan (291 regression, 3 case OTP thực sự và 43 OAuth), 164 Node đạt; Vite build đạt. Browser fixture lấy đủ 231 acc qua nhiều trang, tùy chọn OTP tăng đúng 1 acc, hoàn tất 231/231 và chuyển URL sang job mới; không lỗi console/tràn ngang tại viewport đã kiểm tra. Không đăng nhập/quét tài khoản thật để thử, chưa chứng minh mọi lỗi OTP/SSL thực tế đều đã hết.
- Source nhánh `codex/account-otp-plan-retry-20261112`, commit runtime `17621e27e429b4905436f934c628efe2cb6c96ed` đã push và đối chiếu với `origin/main`. Release **`otp-plan-retry-20261111-183350`** đã triển khai ngày 12/11 giờ Việt Nam; 63/63 hash đạt, health 200, entry phục vụ khớp build, SQLite quick_check OK. API preview retry trên đợt có hơn 200 kết quả trả đúng toàn bộ phạm vi và số loại trừ; không bắt đầu quét thật.
- Preflight đối chiếu 12 source sửa và 77 input; gate idle gồm refresh lease trước restart. Backup source + SQLite: `/opt/gpt-reg-review/_ai_workbench/backups/otp-plan-retry-20261111-183350`. Hash toàn bộ trường tài khoản/mail/settings và lịch sử UPI giữ nguyên qua deploy. Rollback có CAS/idle và đã kiểm cú pháp, chưa thực thi; không restore DB, giữ asset cũ.
- Đã đóng tab và dừng preview local. Automatic approval review chặn lệnh xóa fixture với `blocked by policy`; giữ khoảng 84 MB file kiểm thử riêng của phiên dưới `_ai_workbench/temp/`, không thử vượt chặn. Bằng chứng chi tiết và helper release nằm trong workbench private, không đưa lên Git.

Các mục dưới là bàn giao baseline trước lần sửa này; không coi kết quả cũ là kiểm chứng cho source mới.

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
