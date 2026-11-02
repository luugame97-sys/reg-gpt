# Cài đặt và tiếp tục làm việc trên máy khác

## 1. Chuẩn bị

Cài Git, Python và Node.js (kèm npm). Môi trường dùng để kiểm chứng bản xuất ngày 02/11/2026 là Python 3.14.4 và Node.js 24.21.0 trên Windows. Các dependency được khai báo trong `requirements.txt` và `webui/frontend/package-lock.json`.

GitHub lưu các thay đổi đã commit và push. [AGENTS.md](../AGENTS.md) yêu cầu agent tự kiểm tra/commit/push sau công việc và deploy runtime khi đủ điều kiện; file còn chưa push trên máy cũ chưa xuất hiện trên máy mới. Đây không phải tiến trình chạy nền khi tắt máy.

## 2. Lấy mã nguồn

```powershell
git clone https://github.com/luugame97-sys/reg-gpt.git
cd reg-gpt
```

Mở thư mục này làm project trong Codex/trình soạn thảo. Đọc `AGENTS.md`, `docs/session_report.md` rồi `docs/DEVELOPMENT.md` trước khi tiếp tục. Chỉ cần nói: “Tiếp tục dự án theo AGENTS.md và báo cáo bàn giao, kiểm tra hiện trạng trước khi sửa.” Không cần lịch sử chat cũ để biết trạng thái đã ghi nhận.

Codex đọc chỉ dẫn dự án từ `AGENTS.md`; file ở root được dùng cho project, nhưng cấu hình/override khác trên máy có thể thay đổi chỉ dẫn hiệu lực. Sau khi clone, mở phiên mới và kiểm tra agent đã nhận file này. Tham khảo [hướng dẫn AGENTS.md của OpenAI](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

## 3. Cài và chạy trên Windows

Chạy tại thư mục vừa clone:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm ci --prefix webui/frontend
npm --prefix webui/frontend run build
.\.venv\Scripts\python.exe start_webui.py --no-browser
```

Mở `http://127.0.0.1:8765/`. Giữ cửa sổ lệnh đang chạy; nhấn Ctrl+C để dừng. Các lần sau có thể dùng `run_webui.cmd`, script ưu tiên Python trong `.venv`.

Chỉ khi cần tính năng dùng trình duyệt, tải thêm engine tương ứng:

```powershell
.\.venv\Scripts\python.exe -m camoufox fetch
.\.venv\Scripts\python.exe -m playwright install chromium
```

## 4. Linux / macOS

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm ci --prefix webui/frontend
npm --prefix webui/frontend run build
.venv/bin/python start_webui.py --no-browser
```

Các bước này chưa được chạy thực tế trên Linux/macOS trong phiên xuất bản. Engine trình duyệt có thể cần thêm thư viện hệ thống theo nền tảng.

## 5. Đồng bộ giữa các máy

Trước khi bắt đầu trên một máy đã clone:

```powershell
git status
git pull --ff-only
```

Nếu đang có thay đổi chưa lưu, commit hoặc xử lý chúng trước khi pull. Sau khi sửa và kiểm tra:

```powershell
git status
git add <cac-file-ma-nguon-da-kiem-tra>
git diff --cached
git commit -m "Mo ta thay doi"
git push origin HEAD:main
```

Thay `<cac-file-ma-nguon-da-kiem-tra>` bằng đường dẫn thật; trước push kiểm tra nhánh hiện tại thuộc lịch sử sạch và remote main vẫn là tổ tiên của HEAD. Lệnh push trên chỉ dành cho thay đổi đã được kiểm tra để đưa lên main, không dùng với nhánh còn dở. Chỉ chuyển sang máy khác sau khi push thành công và SHA remote khớp local. Nếu hai máy cùng sửa, cần xử lý xung đột trước khi đồng bộ tiếp; không dùng force push để bỏ qua thay đổi.

Agent thực hiện các bước này theo `AGENTS.md`, không cần nhắc lại mỗi lần. Hướng dẫn lệnh ở đây cũng dùng được khi làm thủ công. Cập nhật `docs/session_report.md` trước bàn giao; nếu còn dở, ghi rõ file, kiểm thử, điểm chặn và bước tiếp theo. Không đẩy bí mật/workbench private để thay cho bản bàn giao.

Khi mã frontend hoặc dependency thay đổi, chạy lại bước cài/build tương ứng. Có thể phát triển giao diện bằng `npm --prefix webui/frontend run dev` cùng backend ở cổng 8765.

## 6. Dữ liệu và VPS

- Clone mới khởi tạo database rỗng ở `webui/webui.db`. Nhập tài khoản, proxy và khóa dịch vụ qua giao diện khi cần.
- Database chứa mật khẩu, token, 2FA và cấu hình nhạy cảm. Để giữ dữ liệu cũ, chuyển bản backup SQLite nhất quán qua kênh riêng. Dừng ứng dụng và tác vụ liên quan trước khi thay database; nếu sao lưu khi đang chạy, dùng SQLite backup API, không chép riêng file `.db` trong lúc còn WAL.
- Không commit database, file xuất tài khoản, khóa API, credential SSH, `.env`, log hoặc backup lên GitHub, kể cả repo private. Kiểm tra `git diff --cached` trước mỗi lần push.
- Push GitHub không tự kích hoạt CI cập nhật/khôi phục VPS. Agent được ủy quyền deploy runtime theo `AGENTS.md` và [DEPLOYMENT.md](DEPLOYMENT.md) khi có quyền SSH, đúng đích, gate an toàn và rollback. Máy mới cần thiết lập quyền GitHub/SSH qua kênh riêng một lần; docs-only hoặc runtime đã deploy thì không restart lại. Dịch vụ, TLS, Basic Auth, firewall và dữ liệu production vẫn được quản lý riêng.
- Backend mặc định chỉ nghe `127.0.0.1`. Khi triển khai qua mạng, cần thiết lập lớp xác thực và bảo vệ mạng phù hợp; bản source không chứa cấu hình bảo vệ của VPS hiện tại.

## 7. Kiểm tra khi tiếp tục phát triển

Build frontend trước để tạo `webui/static/` (thư mục này không nằm trong Git):

```powershell
npm --prefix webui/frontend run build
.\.venv\Scripts\python.exe -m pip install pytest httpx pytz
.\.venv\Scripts\python.exe -m pytest -q
$nodeTests = (Get-ChildItem tests -Filter *.cjs -File).FullName
node --test $nodeTests
```

`pytest`/`httpx`/`pytz` là dependency kiểm thử, cài trong `.venv`. Các test Python dùng database riêng và chặn mạng thật qua `tests/conftest.py`. Sáu test dành cho helper triển khai riêng được skip khi clone không có `_ai_workbench/tools/deploy_cumulative_traffic.py`. Test/build đạt không chứng minh đăng ký, thanh toán hay provider thật hoạt động.
