# Đồng bộ VPS an toàn

## Đích và quyền

- Website: `https://reg2.mg365.fun`.
- App root: `/opt/gpt-reg-review`; systemd service: `gpt-reg-review.service`.
- Backend nội bộ: `http://127.0.0.1:8765`; Python trên VPS: `/opt/gpt-reg-review/venv/bin/python`.
- GitHub là nguồn bàn giao code, không chứa dữ liệu hay cấu hình bảo vệ VPS. Push Git không tự chạy deploy bằng CI; agent thực hiện quy trình theo [AGENTS.md](../AGENTS.md) khi đủ điều kiện.

Người dùng đã cho phép tự cập nhật dịch vụ trên sau thay đổi runtime trong phạm vi yêu cầu. Không bao gồm đổi host, auth/TLS/firewall, migration phá hủy dữ liệu, dừng/hủy/resume tác vụ hoặc thao tác provider/thanh toán thật.

## Chuẩn bị máy mới

1. Clone và cài/build theo [SETUP_VI.md](SETUP_VI.md). Xác thực GitHub bằng cơ chế credential của máy; không đưa PAT vào remote URL/file tracked.
2. Thiết lập OpenSSH hoặc công cụ SSH có sẵn bằng credential chuyển qua kênh riêng. Có thể đặt alias **`reg2`** trong cấu hình SSH người dùng, trỏ tới host/user/key production đã được chủ dự án xác nhận. Alias này là quy ước đề xuất, không được tự giả định đã tồn tại. Không công bố IP, tài khoản SSH, private key hoặc password trong repo.
3. Xác minh host-key fingerprint qua kênh tin cậy; không tắt host-key checking hoặc tự chấp nhận key đổi. Không suy ra SSH host từ domain web có thể đi qua proxy.
4. Kiểm tra chỉ đọc (sau khi alias đã được xác minh):

```text
ssh reg2 "hostname"
ssh reg2 "systemctl is-active gpt-reg-review.service"
ssh reg2 "curl --fail --silent http://127.0.0.1:8765/api/health"
```

Không in toàn bộ config, environment, database, HTTP header xác thực hoặc log có account/token. Nếu chưa có credential/target đáng tin cậy, agent vẫn có thể sửa/test/push code nhưng phải báo chưa deploy được.

## Quy trình mỗi release

1. **Phạm vi:** chỉ tài liệu/test/AGENTS thì không deploy. Nếu runtime đã được deploy với hash xác minh và không đổi nữa, không restart lại. Đọc [snapshot hiện tại](session_report.md), rồi kiểm chứng lại actual source/service thay vì coi snapshot là hiện trạng vĩnh viễn.
2. **Nguồn:** fetch/kiểm tra remote, test phần liên quan, build frontend từ source và package-lock đã xác minh. Không đổi dependency production ngoài phạm vi. Lưu manifest SHA-256 của input runtime, file định deploy và artifact; đối chiếu source VPS để tránh ghi đè thay đổi từ máy khác. Dừng nếu drift ngoài phạm vi.
3. **Gate:** xác minh tác vụ đăng ký, refresh token, UPI/worker, lease và công việc unresolved bằng API nội bộ/DB chỉ đọc phù hợp với code hiện tại. Backend restart chỉ khi an toàn; không xem số task pending bằng 0 là đủ. Lần trước chỉ miễn trừ nhóm legacy `uncertain` có `control_state=STOPPED` và lease hết hạn sau khi đã đối chiếu code chứng minh không được claim/poll. Không bỏ toàn bộ gate unresolved hoặc tự suy rộng miễn trừ này sang trạng thái khác.
4. **Backup/rollback:** tạo release ID, backup chọn lọc file sẽ đổi dưới `/opt/gpt-reg-review/_ai_workbench/backups/<release-id>`. Nếu backend/deploy có thể tác động DB, sao lưu SQLite nhất quán bằng backup API, không copy riêng `.db` khi WAL đang hoạt động. Chuẩn bị rollback source/entry kèm hash kỳ vọng trước khi apply; rollback phải kiểm drift/gate, không tự restore DB. Không backup toàn cây, không đụng dữ liệu/account/secret ngoài phạm vi.
5. **Stage/apply:** upload vào thư mục stage riêng, xác minh hash; kiểm tra baseline và gate lần nữa ngay trước khi ghi/restart. Ghi file theo cơ chế atomic. Frontend: publish asset hashed trước, `index.html` cuối cùng, giữ chunk cũ cho tab đang mở. Không `rsync --delete` hoặc copy đè toàn project. Backend: chỉ thay file đã xét và restart đúng service khi cần; không kill process/worker hàng loạt.
6. **Verify:** service/health, hash source/asset và entry đang được phục vụ; kiểm tra UI/API liên quan theo cách không làm thay đổi dữ liệu. Nếu có DB liên quan, kiểm tra tính toàn vẹn và dữ liệu cần giữ. Health 200 là smoke, không phải E2E nghiệp vụ. Nếu lỗi, dừng phát hành, dùng rollback đã kiểm tra khi vẫn an toàn; không restore DB để che lỗi.
7. **Bàn giao:** cập nhật `docs/session_report.md` với release/commit nguồn, test, backup/rollback, trạng thái và giới hạn không chứa secret, commit/push rồi xác minh remote. Bằng chứng chi tiết riêng giữ tại `_ai_workbench/reports/` (ignored). Nếu runtime commit đã push trước deploy thì bổ sung commit tài liệu kết quả; không tạo vòng lặp deploy cho commit chỉ có docs.

## Công cụ triển khai hiện có và giới hạn

Các helper trên máy cũ ở `_ai_workbench/tools/` dùng chuỗi helper/cấu hình riêng, không phải API public hoặc công cụ portable trong repo. Không chạy nhầm script lịch sử vì tên giống, không đưa chúng lên Git khi chưa loại hết credential/path máy. Khi thiếu helper, agent có thể dùng SSH/SFTP và công cụ sẵn có theo các gate ở trên; script hỗ trợ mới nếu cần đặt trong `_ai_workbench/tools/`, không thêm dependency toàn máy.

Snapshot gần nhất và đường dẫn backup/rollback ở `docs/session_report.md`. Script rollback của một release chỉ dùng cho đúng release đó và trạng thái hash tương ứng. Chưa có kiểm thử khôi phục production thực tế; không tuyên bố rollback đã được chạy thành công chỉ vì kiểm cú pháp đạt.
