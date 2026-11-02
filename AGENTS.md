# Quy tắc cho agent — reg-gpt

## Phạm vi và giao tiếp

- Dùng tiếng Việt, ngắn gọn: kết quả, bằng chứng kiểm tra, phần còn thiếu.
- Kiểm tra tiền đề của yêu cầu; chỉ ra mâu thuẫn hoặc thiếu thông tin quan trọng. Tự xử lý việc rõ ràng, ít rủi ro; hỏi khi ảnh hưởng dữ liệu, bảo mật hoặc mở rộng phạm vi.
- Hỏi đáp/review/chẩn đoán không mặc nhiên cho phép sửa, commit hoặc deploy. Chỉ triển khai trong phạm vi người dùng yêu cầu; không refactor, đổi kiến trúc hay thêm dependency ngoài phạm vi.
- Đọc trước khi sửa; giữ encoding, style, thay đổi của người khác và giấy phép AGPL. Không tự sửa chính sách YTC-only/không auto-refresh để làm test cũ đạt.

## Bắt đầu và tiếp tục trên máy khác

1. Kiểm tra cấu trúc, `git status --short --branch`, branch và remote. Repo chuẩn: `https://github.com/luugame97-sys/reg-gpt.git`, nhánh đồng bộ `main`.
2. Đọc báo cáo đầu tiên tồn tại: `_ai_workbench/reports/session_report.md`, `session_report.md`, `docs/session_report.md`, `development_log.md`. Đọc thêm [bàn giao](docs/DEVELOPMENT.md) và [cài máy mới](docs/SETUP_VI.md) khi cần. Báo cáo là snapshot, không thay thế việc kiểm tra hiện trạng.
3. Khi cần sửa/đồng bộ, `git fetch origin main` và đối chiếu trước khi làm. Chỉ fast-forward khi worktree sạch và nhánh phù hợp; không tự stash, reset hay ghi đè phần đang làm. Nhánh công việc mới dùng tiền tố `codex/`.
4. Lịch sử sạch bắt đầu ở `2dd9a0986b6e733d236d9d4158eefb80d43a9f07`. Lịch sử local cũ có credential: tuyệt đối không merge/push nhánh cũ, không `--all`, `--mirror`, force-push hoặc tạo lại lịch sử.
5. Tìm kiếm có giới hạn bằng `rg`; không quét dependency, build, DB, backup hoặc log lớn khi không cần. Không chạy tác vụ nền hay cài công cụ toàn máy ngoài yêu cầu.

## Tự động đồng bộ GitHub sau thay đổi

Người dùng đã yêu cầu mặc định tự cập nhật GitHub/VPS để chuyển máy làm tiếp. Áp dụng trong mỗi phiên có thay đổi được người dùng yêu cầu, trừ khi người dùng nói không commit/push/deploy:

1. Hoàn thiện thay đổi và kiểm thử phù hợp. Phân biệt test tĩnh, fixture, build và luồng thật; không báo hoàn tất nếu thiếu bằng chứng. Có thể tái dùng kết quả đã xác minh nếu input không đổi.
2. Cập nhật ngắn [docs/session_report.md](docs/session_report.md): thay đổi, test/giới hạn, trạng thái GitHub/VPS, việc dở và bước tiếp theo. Đây là bản bàn giao **không chứa dữ liệu riêng**, phải nằm trong Git. Nếu có phát hiện quan trọng, cập nhật thêm báo cáo private ở `_ai_workbench/reports/session_report.md`.
3. Rà diff và bí mật; stage chính xác file thuộc tác vụ. Không dùng `git add .`, `git add -A` hoặc gom thay đổi không rõ nguồn gốc. Không tự sửa/gộp phần của người khác.
4. Commit rồi push tự động, không chờ người dùng nhắc lại. Trước push, fetch và kiểm tra `origin/main` là tổ tiên của HEAD; chỉ push fast-forward đã kiểm tra bằng `git push origin HEAD:main`. Nếu có commit từ máy khác/xung đột, xử lý an toàn trong phạm vi hoặc báo rõ điểm chặn; không force.
5. Đối chiếu SHA local với `git ls-remote origin refs/heads/main`. Nếu lỗi quyền/mạng, giữ commit local và báo chính xác chưa lên GitHub; không in token hoặc tự thay credential.
6. Chỉ đồng bộ phần đã đủ điều kiện. Nếu việc còn dở, ghi rõ trong bàn giao; không đưa code chưa kiểm chứng lên production. Yêu cầu chỉ đọc hoặc không có thay đổi không cần tạo commit rỗng.

## Tự động cập nhật VPS khi có thay đổi runtime

- Đích đã được ủy quyền: dịch vụ `gpt-reg-review.service` ở `/opt/gpt-reg-review`, website `https://reg2.mg365.fun`. Theo [quy trình VPS](docs/DEPLOYMENT.md), kiểm tra đúng SSH host/key/service trước mỗi lần thay đổi. Không suy ra SSH host từ DNS website.
- Sau kiểm thử và push thành công, tự triển khai thay đổi runtime phù hợp nếu có quyền truy cập, backup/rollback đã chuẩn bị và gate tác vụ an toàn. Không hỏi lại cho triển khai thông thường trong phạm vi này. Nếu người dùng yêu cầu thứ tự khác, làm theo và ghi rõ trạng thái.
- Chỉ đổi tài liệu/test/AGENTS thì push GitHub, **không restart VPS**. Nếu runtime tương ứng đã triển khai và có bằng chứng khớp, không deploy lại chỉ vì tạo commit mới.
- Kiểm tra drift/hash trước khi ghi; không ghi đè source production khác baseline. Backup chọn lọc, giữ dữ liệu, giữ asset hash cũ cho tab đang mở; publish entry cuối cùng.
- Backend/restart phải kiểm tra job/worker/lease đang hoạt động. Không tự dừng, hủy, resume task hay bỏ qua gate để deploy. Không restore DB, đổi auth/firewall, chuyển máy đích hoặc chạy tác vụ provider/thanh toán để thử nếu chưa được yêu cầu riêng.
- Thiếu credential, gate bận, drift hoặc không có rollback an toàn: không deploy; vẫn bàn giao/đồng bộ source đã kiểm tra khi an toàn và ghi rõ lý do chặn. Không chờ ngầm hoặc tự mở monitor nền.
- Sau deploy kiểm tra hash/source, health, asset và hành vi liên quan an toàn; lưu release ID, backup, rollback và phần chưa E2E. Health 200 không chứng minh mọi luồng nghiệp vụ hoạt động.

## Dữ liệu, file hỗ trợ và bàn giao

- GitHub này là repo public. Không commit database/WAL, account thật, mật khẩu, OTP/2FA, token, proxy credential, API key, SSH key, `.env`, log riêng, backup hoặc helper chứa cấu hình máy. `.gitignore` không bảo vệ bí mật nằm trong file source đã tracked: luôn rà nội dung staged.
- Source/test/tài liệu theo cấu trúc dự án; file hỗ trợ chỉ ở `_ai_workbench/{tools,temp,logs,backups,reports}/`. Chỉ tạo khi cần, không tạo HTML ngoài yêu cầu.
- Không xóa file cũ/backup/cache không rõ nguồn; hỏi trước. Dọn file tạm tự tạo còn không cần nếu được phép, không thử lách thao tác bị chặn. Không dùng lệnh phá hủy nhắm root/workspace/home.
- Kết thúc nêu commit/nhánh đã push, release VPS hoặc lý do không deploy, kiểm thử và phần còn thiếu. Không tuyên bố đã đồng bộ khi mới commit local.
- `AGENTS.md` là chỉ dẫn trong phiên agent, không phải daemon/CI tự chạy khi tắt máy. Máy mới cần clone/pull repo và thiết lập riêng quyền GitHub/SSH; không chuyển secrets qua Git.
