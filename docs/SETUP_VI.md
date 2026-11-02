# Cài đặt và tiếp tục làm việc trên máy khác

## 1. Chuẩn bị

Cài Git, Python và Node.js (kèm npm). Môi trường dùng để kiểm chứng bản xuất ngày 02/11/2026 là Python 3.14.4 và Node.js 24.21.0 trên Windows. Các dependency được khai báo trong `requirements.txt` và `webui/frontend/package-lock.json`.

GitHub lưu các thay đổi đã commit và push. File còn đang sửa trên máy cũ chưa tự xuất hiện trên máy mới.

## 2. Lấy mã nguồn

```powershell
git clone https://github.com/luugame97-sys/reg-gpt.git
cd reg-gpt
```

Mở thư mục này bằng trình soạn thảo hoặc công cụ hỗ trợ lập trình. Đọc `docs/DEVELOPMENT.md` trước khi tiếp tục.

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
git push
```

Thay `<cac-file-ma-nguon-da-kiem-tra>` bằng đường dẫn thật. Chỉ chuyển sang máy khác sau khi push thành công. Nếu hai máy cùng sửa, cần xử lý xung đột trước khi đồng bộ tiếp; không dùng force push để bỏ qua thay đổi.

Khi mã frontend hoặc dependency thay đổi, chạy lại bước cài/build tương ứng. Có thể phát triển giao diện bằng `npm --prefix webui/frontend run dev` cùng backend ở cổng 8765.

## 6. Dữ liệu và VPS

- Clone mới khởi tạo database rỗng ở `webui/webui.db`. Nhập tài khoản, proxy và khóa dịch vụ qua giao diện khi cần.
- Database chứa mật khẩu, token, 2FA và cấu hình nhạy cảm. Để giữ dữ liệu cũ, chuyển bản backup SQLite nhất quán qua kênh riêng. Dừng ứng dụng và tác vụ liên quan trước khi thay database; nếu sao lưu khi đang chạy, dùng SQLite backup API, không chép riêng file `.db` trong lúc còn WAL.
- Không commit database, file xuất tài khoản, khóa API, credential SSH, `.env`, log hoặc backup lên GitHub, kể cả repo private. Kiểm tra `git diff --cached` trước mỗi lần push.
- Push GitHub không cập nhật hoặc khôi phục VPS. Dịch vụ, domain, TLS, Basic Auth, firewall và dữ liệu production được quản lý riêng. Chỉ triển khai khi đã xác định đúng máy đích, có ủy quyền và phương án khôi phục.
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
