// UI phrases and templates. Keep placeholders identical in all three languages.
const upiPhrases = [
  ['Bảo mật acc','Account security','账号安全'],
  ['Đổi 2FA','Rotate 2FA','更换 2FA'],
  ['Đổi 2FA…','Rotate 2FA…','更换 2FA…'],
  ['Đổi mật khẩu','Change password','修改密码'],
  ['Đổi mật khẩu…','Change password…','修改密码…'],
  ['Đổi mật khẩu + 2FA','Change password + 2FA','修改密码和 2FA'],
  ['Kick tất cả phiên','Sign out all sessions','退出所有会话'],
  ['Kick tất cả phiên…','Sign out all sessions…','退出所有会话…'],
  ['Kiểm tra đăng nhập / gói','Check sign-in / plan','检查登录和套餐'],
  ['Tiếp tục xác minh','Continue verification','继续验证'],
  ['Tải checkpoint','Download checkpoint','下载恢复检查点'],
  ['Xuất acc thành công','Export successful accounts','导出成功账号'],
  ['Đăng nhập workspace','Sign in to your workspace','登录工作区'],
  ['Dùng tài khoản quản trị để tiếp tục.','Use your administrator account to continue.','使用管理员账号继续。'],
  ['Tên đăng nhập','Username','用户名'],
  ['Đăng nhập','Sign in','登录'],
  ['Đang đăng nhập…','Signing in…','正在登录…'],
  ['Đăng xuất','Sign out','退出登录'],
  ['Ẩn mật khẩu','Hide password','隐藏密码'],
  ['Hiện mật khẩu','Show password','显示密码'],
  ['Dùng tài khoản và mật khẩu bạn đang dùng cho trang web.','Use your existing website username and password.','使用您现有的网站用户名和密码。'],
  ['Quản lý tài khoản và tác vụ trong một workspace.','Manage accounts and tasks in one workspace.','在同一工作区管理账号和任务。'],
  ['Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.','Your session has expired. Please sign in again.','登录会话已过期，请重新登录。'],
  ['Đang kiểm tra phiên đăng nhập…','Checking your session…','正在检查登录会话…'],
  ['Tài khoản hoặc mật khẩu chưa đúng.','The username or password is incorrect.','用户名或密码不正确。'],
  ['Vui lòng nhập đầy đủ tài khoản và mật khẩu hợp lệ.','Enter a valid username and password.','请输入有效的用户名和密码。'],
  ['Bạn đã thử đăng nhập quá nhiều lần. Vui lòng chờ rồi thử lại.','Too many sign-in attempts. Please wait and try again.','登录尝试次数过多，请稍后重试。'],
  ['Thử lại sau {0} giây.','Try again in {0} seconds.','请在 {0} 秒后重试。'],
  ['Hãy mở trang bằng HTTPS để đăng nhập.','Open this page using HTTPS to sign in.','请使用 HTTPS 打开此页面以登录。'],
  ['Hãy tải lại trang rồi thử đăng nhập lại.','Reload this page and try signing in again.','请刷新页面后重新登录。'],
  ['Trình duyệt chưa lưu được phiên đăng nhập. Hãy cho phép cookie cho trang này rồi thử lại.','Your browser could not save the session. Allow cookies for this site and try again.','浏览器无法保存登录会话，请允许此网站使用 Cookie 后重试。'],
  ['Không kết nối được trang đăng nhập. Vui lòng thử lại.','Could not connect to sign-in. Please try again.','无法连接登录服务，请重试。'],
  ['Quét lại tài khoản lỗi','Retry failed accounts','重试失败账号'],
  ['Kiểm tra lại lỗi OTP mail đã lưu','Recheck saved email OTP errors','重新检查已保存的邮箱验证码错误'],
  ['Quét lại tài khoản lỗi của đợt đã chọn, bao gồm mọi trang kết quả.','Retry failed accounts from this batch across all result pages.','重试该批次所有结果页面中的失败账号。'],
  ['Cho phép thử đăng nhập lại một lần trong đợt này. Nếu máy chủ thực sự yêu cầu OTP email, vẫn cần đường nhận mã hợp lệ.','Allow one new login attempt in this batch. If the server requires email verification, a working mailbox is still needed.','允许在该批次中重新登录一次。如果服务器要求邮箱验证，仍需要可用的收码邮箱。'],
  ['Đang lấy toàn bộ tài khoản lỗi…','Loading all failed accounts…','正在加载所有失败账号…'],
  ['Tổng lỗi {0} · Đã kiểm tra gói thành công {1} · Khóa hoặc sai thông tin {2} · Chờ OTP {3} · Không còn trong kho {4}','Failed {0} · Plan already verified {1} · Locked or invalid credentials {2} · Waiting for OTP {3} · Removed {4}','失败 {0} · 套餐已验证 {1} · 已锁定或凭据错误 {2} · 等待验证码 {3} · 已移除 {4}'],
  ['· Kiểm tra lại OTP {0}','· Recheck OTP {0}','· 重新检查验证码 {0}'],
  ['Che khóa/OTP','Hide keys/OTP','隐藏密钥/OTP'],
  ['Hiện khóa/OTP','Show keys/OTP','显示密钥/OTP'],
  ['Che khóa/OTP trong danh sách và API UPI. Không che ô nhập, chi tiết hoặc dữ liệu xuất.','Mask list credentials and the UPI API key. Input fields, details and exports are not masked.','隐藏列表凭据和 UPI API 密钥，不隐藏输入、详情或导出内容。'],
  ['Che thông tin nhạy cảm','Hide sensitive information','隐藏敏感信息'],
  ['Hiện thông tin nhạy cảm','Show sensitive information','显示敏感信息'],
  ['Mở nhập proxy','Import proxies','导入代理'],
  ['Mở tạo đợt','Create a batch','创建批次'],
  ['Thu gọn','Collapse','收起'],
  ['tài khoản trong bản nháp','accounts in draft','个草稿账号'],
  ['Đã xong — có lỗi','Finished — with errors','已结束 — 存在错误'],
  ['cần xử lý','need attention','需处理'],
  ['Gói gần nhất','Last checked plan','最近检查的套餐'],
  ['Chưa có mốc kiểm tra','No check timestamp','无检查时间'],
  ['Chưa kiểm tra gói sau quét','Plan not checked after payment','支付后尚未检查套餐'],
  ['Đã kiểm tra gói sau quét','Plan checked after payment','支付后已检查套餐'],
  ['Đã kiểm tra nhưng chưa xác minh gói','Checked, plan not verified','已检查但套餐未验证'],
  ['Phiên bản trình duyệt nhất quán','Browser version is consistent','浏览器版本一致'],
  ['Múi giờ khớp quốc gia','Timezone matches country','时区与国家一致'],
  ['Ngôn ngữ khớp quốc gia','Language matches country','语言与国家一致'],
  ['Link chuyển tiếp','Relay URL','中转链接'],
  ['Sao chép link','Copy link','复制链接'],
  ['Mã lượt','Run ID','运行编号'],
  ['bản ghi','records','条记录'],
  ['Lượt đăng ký','Registration run','注册运行'],
  ['Thông tin môi trường','Environment details','环境信息'],
  ['Đúng định dạng','Valid format','格式正确'],
  ['Chưa kiểm tra kết nối','Connection not tested','尚未测试连接'],
  ['Kết nối tốt','Connected','连接正常'],
  ['Chưa đầy đủ','Partial','部分完成'],
  ['Xem nhật ký ({0})','View logs ({0})','查看日志（{0}）'],
  ['Chưa có proxy. Mở phần Nhập hàng loạt để thêm.','No proxies. Open bulk import to add some.','暂无代理，请展开批量导入添加。'],
  ['Tạo link mới','Create new link','创建新链接'],
  ['Xem lượt mới','View new attempt','查看新尝试'],
  ['Lượt tạo link','Link attempt','链接尝试次数'],
  ['Tạo link mới và gửi quét lại','Create new link and resubmit','创建新链接并重新提交扫码'],
  ['Tạo link mới và gửi','Create and send new link','创建并发送新链接'],
  ['Giữ lịch sử đơn cũ. Tạo checkout mới, kiểm tra link mới rồi tự gửi AT và link sang Camellia.','Keep the old order history. Create a new checkout, verify the new link, then send AT and link to Camellia automatically.','保留旧订单记录。创建新结账，验证新链接后自动将 AT 和链接发送至 Camellia。'],
  ['Chỉ tạo lại khi Camellia xác nhận đơn gốc đã thất bại, hết hạn hoặc bị hủy. Đơn chưa rõ kết quả cần đối chiếu trước.','Retry only after Camellia confirms the original order failed, expired or was cancelled. Reconcile uncertain orders first.','仅在 Camellia 确认原订单失败、过期或取消后重试。结果不明的订单应先核对。'],
  ['AT mới của tài khoản','New account AT','账号的新 AT'],
  ['Kho chưa có AT còn hạn đúng tài khoản. Nhập AT mới để tiếp tục.','No valid AT for this account is stored. Enter a new AT to continue.','账号库中没有该账号的有效 AT，请输入新 AT 以继续。'],
  ['Tự dùng AT còn hạn của tài khoản trong kho.','Use the account’s valid AT from storage automatically.','自动使用账号库中该账号的有效 AT。'],
  ['Tôi đồng ý tạo checkout mới và gửi AT/link mới sang Camellia.','I agree to create a new checkout and send AT/new link to Camellia.','我同意创建新结账并将 AT 和新链接发送至 Camellia。'],
  ['Đã xếp hàng tạo link mới; chỉ gửi Camellia khi có link mới hợp lệ.','New link attempt queued; Camellia receives it only after a valid new link is available.','已排队创建新链接，仅在获得有效新链接后发送至 Camellia。'],
  ['Trích xuất vẫn trả link cũ; chưa gửi lại Camellia.','Extraction returned an old link; it has not been resubmitted to Camellia.','提取仍返回旧链接，尚未重新发送至 Camellia。'],
  ['Tạo link mới chỉ áp dụng cho Tự trích xuất + Camellia.','New link attempts are only available for Self extraction + Camellia.','创建新链接仅适用于自行提取 + Camellia。'],
  ['Chỉ tạo link mới cho đơn Camellia đã kết thúc thất bại, hết hạn hoặc bị hủy.','New links require a failed, expired or cancelled Camellia order.','仅能为已失败、过期或取消的 Camellia 订单创建新链接。'],
  ['Cần xác nhận tạo checkout mới và gửi AT/link mới đến Camellia.','Confirm creating a new checkout and sending AT/new link to Camellia.','请确认创建新结账并将 AT 和新链接发送至 Camellia。'],
  ['Đơn gốc chưa được xác nhận kết thúc thất bại; chưa tạo link mới.','The original order has not been confirmed as failed; no new link was created.','原订单尚未确认失败，未创建新链接。'],
  ['Cần AT còn hạn thuộc đúng tài khoản; hãy cập nhật trong kho hoặc nhập AT mới.','A valid AT for the same account is required; update storage or enter a new AT.','需要该账号的有效 AT，请更新账号库或输入新 AT。'],
  ['Kho Proxy chưa có proxy hợp lệ để tạo link mới.','No valid proxy is stored for creating a new link.','代理库中没有可用于创建新链接的有效代理。'],
  ['Đơn giá Camellia đã thay đổi; mở lại xác nhận trước khi tạo link mới.','Camellia pricing changed; reopen confirmation before creating a new link.','Camellia 单价已变更，请重新打开确认后创建新链接。'],
  ['Camellia chưa xác nhận đơn gốc kết thúc thất bại; giữ đơn gốc để đối chiếu.','Camellia has not confirmed the original order failed; keep it for reconciliation.','Camellia 尚未确认原订单失败，请保留原订单以核对。'],
  ['Khóa hoặc tác vụ đã thay đổi; mở lại xác nhận.','The key or task changed; reopen confirmation.','密钥或任务已变更，请重新打开确认。'],
  ['Mã yêu cầu đã dùng cho tác vụ khác.','The request ID was used for another task.','请求 ID 已用于其他任务。'],
  ['Trạng thái đơn gốc đã thay đổi; chưa tạo link mới.','The original order status changed; no new link was created.','原订单状态已变更，未创建新链接。'],
  ['Tài khoản đang có tác vụ khác; chờ kết quả trước khi tạo link mới.','This account has another active task; wait for its result before creating a new link.','该账号有其他进行中的任务，请等待结果后再创建新链接。'],
  ['Phương thức UPI','UPI method','UPI 方式'],
  ['YTC trọn gói','YTC full service','YTC 全包'],
  ['Tự trích xuất + Camellia','Self extraction + Camellia','自行提取 + Camellia'],
  ['Đổi phương thức cho đợt mới; tác vụ cũ tiếp tục theo phương thức đã gửi.','Changes apply to new batches; existing tasks keep their original method.','切换仅用于新批次，已有任务继续使用原方式。'],
  ['Nhập API key Camellia Standard trong Cấu hình API.','Enter a Camellia Standard API key in API settings.','请在 API 设置中输入 Camellia Standard 密钥。'],
  ['Tự lấy link qua ChatGPT / Stripe, gửi AT và link đến Camellia sau xác nhận.','Extract via ChatGPT / Stripe; send AT and link to Camellia after confirmation.','通过 ChatGPT / Stripe 提取，确认后将 AT 和链接发送至 Camellia。'],
  ['Trích xuất lần lượt bằng proxy cố định. Không tự tạo checkout mới khi kết quả chưa rõ.','Extract sequentially with a fixed proxy. Ambiguous results never create a new checkout automatically.','使用固定代理依次提取，结果不明时不会自动新建结账会话。'],
  ['Cài đặt trích xuất','Extraction settings','提取设置'],
  ['Luồng trích xuất','Extraction workers','提取并发数'],
  ['Luồng đang chạy','Active extraction workers','正在提取的线程'],
  ['Đã cập nhật số luồng trích xuất.','Extraction worker limit updated.','已更新提取并发数。'],
  ['1–100 luồng. Giảm luồng sẽ chờ tác vụ đang chạy hoàn tất. Số lượt quét do Camellia điều phối.','1–100 workers. Lowering the limit lets active tasks finish. Camellia schedules scans.','1–100 个线程。降低并发会等待正在运行的任务完成。扫码由 Camellia 调度。'],
  ['Chọn tất cả kết quả','Select all results','选择全部结果'],
  ['Đang chọn','Selecting','正在选择'],
  ['Chọn tất cả kết quả gồm mọi trang theo bộ lọc hiện tại; giữ lựa chọn khi chuyển trang. Dừng hẳn không thể tiếp tục; đơn đã có link vẫn có thể quét và trừ điểm.','Select all results across every page with the current filters; selections survive page changes. Stopped tasks cannot resume; existing links may still be scanned and charged.','按当前筛选选择所有页面的结果，切换页面时保留选择。彻底停止后无法恢复；已出链订单仍可扫码和扣费。'],
  ['Tự lọc proxy IN từ Kho Proxy, giữ proxy theo từng tác vụ. Tên và địa chỉ thanh toán được tự sinh.','Automatically select IN proxies from the pool and pin each task. Billing names and addresses are generated.','从代理池自动筛选印度代理并绑定每个任务。账单姓名和地址为自动生成。'],
  ['Trích xuất tự động · Proxy IN và thông tin tự sinh','Automatic extraction · IN proxies and generated details','自动提取 · 印度代理与生成信息'],
  ['Mỗi tài khoản một proxy/IP IN riêng từ Kho Proxy. Tự xác minh IP đầu ra; thiếu proxy phù hợp thì chờ.','Each account gets its own IN proxy/exit IP from the pool. Verify the egress; wait if no suitable proxy is available.','每个账户绑定代理池中独立的印度代理及出口 IP。自动验证出口，无可用代理则等待。'],
  ['proxy trong kho; chưa phải số proxy IN đã xác minh.','proxies in the pool; this is not the verified IN count.','个池内代理；并非已验证的印度代理数量。'],
  ['Tên và số nhà được tự sinh theo dữ liệu địa phương/mã bưu chính IN, không phải hồ sơ thanh toán thật. Thông tin được giữ nguyên theo từng tác vụ.','Names and house numbers are generated using IN locality/PIN data, not real billing profiles. Details remain fixed per task.','姓名和门牌号基于印度地区及邮编数据生成，并非真实账单资料。每个任务的信息保持不变。'],
  ['Tên/địa chỉ thanh toán tự sinh, không phải hồ sơ thật.','Billing names/addresses are generated, not real profiles.','账单姓名及地址为自动生成，并非真实资料。'],
  ['Chờ proxy IN riêng','Waiting for a dedicated IN proxy','等待独立印度代理'],
  ['Chỉ nhận checkout 0; phí quét tính riêng. Ưu đãi có thể kèm mandate gia hạn thuê bao.','Only zero-amount checkouts; scan fees apply separately. Promotions may include a subscription renewal mandate.','仅接受零金额结账，扫码另行收费。优惠可能包含订阅续费授权。'],
  ['Hai API độc lập. Nhập khóa tương ứng; để trống để giữ khóa đã lưu.','Two independent APIs. Enter each key; leave blank to keep a saved key.','两套 API 相互独立，分别填写密钥；留空保留已存密钥。'],
  ['API key Camellia Standard','Camellia Standard API key','Camellia Standard API 密钥'],
  ['Nhập khóa Camellia Standard','Enter Camellia Standard key','输入 Camellia Standard 密钥'],
  ['Xóa khóa Camellia đã lưu','Delete saved Camellia key','删除已保存的 Camellia 密钥'],
  ['Cài đặt trích xuất · Proxy và thanh toán','Extraction settings · Proxy and billing','提取设置 · 代理与账单'],
  ['Chỉ dùng cho Tự trích xuất + Camellia. Dùng proxy ổn định và thông tin thanh toán thực, quốc gia IN.','For self extraction + Camellia. Use a stable proxy and real billing details, country IN.','用于自行提取 + Camellia。请使用稳定代理与真实账单信息，国家为 IN。'],
  ['Proxy trích xuất','Extraction proxy','提取代理'],
  ['Tên thanh toán','Billing name','账单姓名'],
  ['Địa chỉ thanh toán','Billing address','账单地址'],
  ['Thành phố thanh toán','Billing city','账单城市'],
  ['Bang thanh toán','Billing state','账单邦'],
  ['Mã bưu chính IN','IN postal code','印度邮政编码'],
  ['Quốc gia thanh toán','Billing country','账单国家'],
  ['Tôi đồng ý tự trích xuất qua ChatGPT / Stripe, gửi AT và link đến Camellia để quét và tính phí khi thành công.','I agree to extract via ChatGPT / Stripe and send AT and link to Camellia for scanning, with fees on success.','我同意通过 ChatGPT / Stripe 提取，将 AT 和链接发送至 Camellia 扫码，并在成功后收取费用。'],
  ['UPI có thể xác minh 1 INR và tạo mandate gia hạn. Kiểm tra hoặc hủy gia hạn nếu không muốn tiếp tục thuê bao.','UPI may verify 1 INR and create a renewal mandate. Review or cancel renewal if you do not want to continue the subscription.','UPI 可能验证 1 印度卢比并创建续费授权。如不续订，请检查或取消自动续费。'],
  ['Tự động & chuông','Automation & sounds','自动处理与提示音'],
  ['Tự động & chuông UPI','UPI automation & sounds','UPI 自动处理与提示音'],
  ['Áp dụng cho tài khoản quét thành công từ lúc bật. Không xử lý lại lịch sử cũ.','Applies to scans completed after enabling. Earlier results are not processed.','仅处理启用后扫码成功的账户，不处理旧记录。'],
  ['1. Xử lý sau quét','1. After scanning','1. 扫码后处理'],
  ['Làm mới AT mới','Refresh Access Token','刷新 Access Token'],
  ['Ưu tiên RT; vẫn làm mới khi AT còn hạn.','Prefer RT; refresh even if the AT is still valid.','优先使用 RT，AT 未过期也会刷新。'],
  ['Kiểm tra gói mới','Check current plan','检查当前套餐'],
  ['Lấy trạng thái thuê bao hiện tại.','Read current subscription status.','读取当前订阅状态。'],
  ['Cập nhật quota','Update quota','更新额度'],
  ['Đọc hạn mức bằng AT sau bước làm mới.','Read limits using the AT after the refresh step.','刷新步骤后使用 AT 读取额度。'],
  ['Tự động làm mới AT sau quét','Automatically refresh AT after scanning','扫码后自动刷新 AT'],
  ['Tự động kiểm tra gói sau quét','Automatically check the plan after scanning','扫码后自动检查套餐'],
  ['Tự động cập nhật quota sau quét','Automatically update quota after scanning','扫码后自动更新额度'],
  ['Chạy trên VPS bằng Kho Proxy. Chờ tác vụ tài khoản đang chạy; tắt sẽ bỏ các bước chưa bắt đầu.','Runs on the VPS using the proxy pool. Waits for active account jobs; disabling skips steps that have not started.','使用代理池在 VPS 上运行。等待正在执行的账户任务；关闭后跳过未开始的步骤。'],
  ['2. Thư mục tài khoản','2. Account folder','2. 账户分组'],
  ['Chuyển vào PLUS','Move to PLUS','移入 PLUS'],
  ['Luôn xác minh gói Plus trước khi chuyển. Giữ thay đổi thư mục do bạn thực hiện.','Verify Plus before moving. Preserve folder changes you make.','移动前验证 Plus，并保留您手动更改的分组。'],
  ['Tự động chuyển thư mục PLUS','Automatically move to PLUS','自动移入 PLUS 分组'],
  ['3. Âm báo','3. Sounds','3. 提示音'],
  ['Có đơn đang quét','Scan started','开始扫码'],
  ['Hai tiếng ngắn tăng dần.','Two short rising tones.','两个短促上升音。'],
  ['Bốn nốt hoàn tất, khác chuông đang quét.','Four completion notes, distinct from the scan sound.','四音完成提示，与扫码提示音不同。'],
  ['Nghe thử đang quét','Preview scan sound','试听扫码提示音'],
  ['Nghe thử thành công','Preview success sound','试听成功提示音'],
  ['Chuông đang quét','Scan sound','扫码提示音'],
  ['Chuông quét thành công','Scan success sound','扫码成功提示音'],
  ['Chuông phát theo cài đặt đã lưu khi tab UPI đang mở; không lặp lại khi đồng bộ.','Sounds follow your saved preferences while the UPI tab is open, without replaying on sync.','UPI 页面打开时按已保存的设置播放提示音，同步时不会重复播放。'],
  ['Bật âm thanh trong tab này','Enable sounds in this tab','启用此页面的声音'],
  ['Tự động UPI đang bật','UPI automation enabled','UPI 自动处理已开启'],
  ['Đã lưu cài đặt tự động UPI.','UPI automation settings saved.','UPI 自动处理设置已保存。'],
  ['Trình duyệt chưa cho phép âm thanh. Hãy bấm bật lại âm thanh.','The browser has not allowed audio. Enable sounds again.','浏览器尚未允许音频，请重新启用声音。'],
  ['Khóa API Yitiaochong đang dùng','Current Yitiaochong API key','当前一条虫 API 密钥'],
  ['Dùng khóa chuyên dụng Yitiaochong API. Khóa đang dùng hiển thị đầy đủ để xem và sao chép.','Use a dedicated Yitiaochong API key. The current key is shown in full for viewing and copying.','使用一条虫专用 API 密钥。当前密钥完整显示，可查看和复制。'],
  ['Chờ xử lý sau quét','Waiting for post-scan processing','等待扫码后处理'],
  ['Đang xử lý sau quét','Processing after scanning','正在扫码后处理'],
  ['Đã xử lý sau quét.','Post-scan processing finished.','扫码后处理已完成。'],
  ['Có bước chưa thành công.','Some steps did not succeed.','部分步骤未成功。'],
  ['Làm mới AT thất bại; dừng các bước sau.','AT refresh failed; later steps stopped.','AT 刷新失败，后续步骤已停止。'],
  ['Chờ tác vụ tài khoản đang chạy.','Waiting for the active account job.','等待正在运行的账户任务。'],
  ['Đã tắt tính năng.','Feature disabled.','功能已关闭。'],
  ['Chưa xác nhận gói Plus; giữ thư mục hiện tại.','Plus is unverified; keeping the current folder.','尚未验证 Plus，保留当前分组。'],
  ['Gói hiện tại chưa xác nhận Plus.','The current plan is not verified as Plus.','当前套餐尚未验证为 Plus。'],
  ['Thư mục đã được đổi; giữ thay đổi của bạn.','The folder changed; preserving your change.','分组已更改，保留您的修改。'],
  ['Đã chuyển vào PLUS.','Moved to PLUS.','已移入 PLUS。'],
  ['Đã ở thư mục PLUS.','Already in PLUS.','已在 PLUS 分组中。'],
  ['Không khởi chạy được; kiểm tra kho proxy và cấu hình tác vụ.','Could not start; check the proxy pool and job settings.','无法启动，请检查代理池和任务设置。'],
  ['Tác vụ lỗi, bị dừng hoặc chưa có kết quả; không tự thử lại.','Job failed, stopped or has no result; no automatic retry.','任务失败、停止或无结果，不会自动重试。'],
  ['Chưa đồng bộ được tự động UPI; hệ thống sẽ kiểm tra lại.','UPI automation sync failed; the system will check again.','UPI 自动同步失败，系统将再次检查。'],
  ['Cài đặt đã thay đổi ở tab khác. Hãy tải lại trước khi lưu.','Settings changed in another tab. Reload before saving.','设置已在其他页面更改，请重新加载后再保存。'],
  ['Vừa quét thành công; giữ NEW đến đợt UPI mới.','Newly scanned; NEW stays until the next UPI batch.','刚刚扫码成功；NEW 保留至下一批 UPI 开始。'],
  ['Cưỡng chế làm mới AT','Force refresh AT','强制刷新 AT'],
  ['Cưỡng chế AT…','Force refresh AT…','强制刷新 AT…'],
  ['Cưỡng chế làm mới AT, kể cả khi chưa hết hạn','Force refresh AT, even before expiry','强制刷新 AT，包括未过期的令牌'],
  ['Xuất LS','Export logins','导出登录资料'],
  ['Xuất CSV','Export CSV','导出 CSV'],
  ['Xuất LS nhanh','Quick login export','快速导出登录资料'],
  ['Phạm vi xuất LS','Login export scope','登录资料导出范围'],
  ['Bỏ qua tài khoản thiếu 2FA','Skip accounts without 2FA','跳过缺少 2FA 的账户'],
  ['Sẵn sàng xuất','Ready to export','可导出'],
  ['Trùng email','Duplicate emails','重复邮箱'],
  ['Chưa có / không tải được tài khoản','Account missing / unavailable','账户不存在或无法加载'],
  ['Thiếu 2FA','Missing 2FA','缺少 2FA'],
  ['Dữ liệu chứa dấu phân cách hoặc ký tự xuống dòng','Data contains a separator or line break','数据包含分隔符或换行符'],
  ['Sẽ xuất với ô 2FA trống','Will export with an empty 2FA field','将导出空 2FA 字段'],
  ['Tệp chứa mật khẩu và 2FA dạng văn bản. Kết quả UPI không xác nhận gói Plus.','The file contains passwords and 2FA in plain text. UPI results do not confirm Plus membership.','文件包含明文密码和 2FA。UPI 结果不代表已验证 Plus 套餐。'],
  ['Tải tệp LS','Download login file','下载登录资料'],
  ['Sao chép email','Copy email','复制邮箱'],
  ['Đang tải tài khoản…','Loading account…','正在加载账户…'],
  ['Tài khoản chưa có trong kho.','Account is not in the local store.','账户不在本地账户库中。'],
  ['Không tải được thông tin tài khoản.','Could not load account details.','无法加载账户信息。'],
  ['Thử lại','Retry','重试'], ['Đang tải thư mục…','Loading folders…','正在加载分组…'],
  ['Không tải được thư mục.','Could not load folders.','无法加载分组。'],
  ['Đã chuyển thư mục tài khoản.','Account moved to the folder.','账户分组已更新。'],
  ['Tài khoản đã thay đổi. Hãy kiểm tra thư mục hiện tại.','The account changed. Check its current folder.','账户已发生变化，请核对当前分组。'],
  ['Đã gửi chuyển thư mục; cần tải lại để xác nhận.','Folder change sent; reload to confirm.','分组变更已发送，请重新加载确认。'],
  ['Thông tin tài khoản không khớp email.','Account details do not match the email.','账户信息与邮箱不匹配。'],
  ['Dừng hẳn','Stop','彻底停止'], ['Điều khiển tác vụ đã chọn','Control selected tasks','控制所选任务'],
  ['Chọn tác vụ trong trang','Select tasks on this page','选择当前页任务'], ['Chọn tác vụ','Select task','选择任务'],
  ['Chọn tác vụ trong trang để điều khiển. Dừng hẳn không thể tiếp tục; đơn đã có link vẫn có thể quét và trừ điểm.','Select tasks on this page. Stopped tasks cannot resume; existing links may still be scanned and charged.','选择当前页任务进行控制。彻底停止后无法恢复；已出链订单仍可扫码和扣费。'],
  ['Tạm dừng {0} tác vụ đã chọn?','Pause {0} selected tasks?','暂停所选的 {0} 个任务？'],
  ['Tiếp tục {0} tác vụ đã chọn?','Resume {0} selected tasks?','继续所选的 {0} 个任务？'],
  ['Dừng hẳn {0} tác vụ đã chọn? Không thể tiếp tục sau khi dừng hẳn.','Permanently stop {0} selected tasks? Stopped tasks cannot resume.','彻底停止所选的 {0} 个任务？停止后无法恢复。'],
  ['Đơn đã có link vẫn có thể tiếp tục quét và trừ điểm.','Orders with links may continue scanning and incur charges.','已出链订单仍可能继续扫码并扣费。'],
  ['Dịch vụ đã nhận lệnh điều khiển.','The service accepted the commands.','服务已受理控制命令。'],
  ['Có lệnh chưa được xác nhận; hãy xem kết quả trước khi gửi lại.','Some commands are unconfirmed; review results before retrying.','部分命令尚未确认，请核对结果后再尝试。'],
  ['Đang gửi lệnh','Sending commands','正在发送命令'], ['Đã nhận lệnh','Commands accepted','已受理命令'], ['Chờ áp dụng','Pending application','待生效'],
  ['Các lệnh còn lại chưa gửi. Hãy đồng bộ và kiểm tra trước khi thử lại.','Remaining commands were not sent. Refresh and review before retrying.','其余命令未发送，请同步核对后再尝试。'],
  ['Xem lệnh chưa được xác nhận','View unconfirmed commands','查看未确认命令'],
  ['Lệnh UPI không hợp lệ.','Invalid UPI command.','无效的 UPI 命令。'],
  ['Phản hồi lệnh chưa rõ; hãy đồng bộ tác vụ trước khi gửi lại.','Command result is unclear; refresh the task before retrying.','命令结果不明，请同步任务后再尝试。'],
  ['Không gửi được lệnh UPI.','Could not send the UPI command.','无法发送 UPI 命令。'],
  ['Tìm kiếm','Search','搜索'], ['kết quả','results','条结果'],
  ['AT gửi UPI','ATs for UPI','提交至 UPI 的 AT'], ['Chế độ UPI','UPI mode','UPI 模式'],
  ['Lọc tác vụ UPI','Filter UPI tasks','筛选 UPI 任务'], ['Tìm tác vụ UPI','Search UPI tasks','搜索 UPI 任务'],
  ['Ngày tạo tác vụ UPI','UPI task creation date','UPI 任务创建日期'],
  ['Tìm email trong kho UPI','Search stored UPI accounts','搜索 UPI 账户库'],
  ['Thư mục tài khoản UPI','UPI account folder','UPI 账户分组'],
  ['Đã tạm dừng','Paused','已暂停'],
  ['Cấu hình API','API settings','API 设置'], ['Cấu hình UPI','UPI settings','UPI 设置'],
  ['Gửi tài khoản, quét UPI và theo dõi kết quả trong một nơi.','Submit accounts, scan UPI and track results in one place.','提交账户、自动扫码并集中跟踪结果。'],
  ['Cần khóa Yitiaochong API để kết nối dịch vụ UPI.','A dedicated Yitiaochong API key is required.','需要专用的一条虫 API 密钥。'],
  ['Tổng quan UPI','UPI overview','UPI 概览'], ['Điểm khả dụng','Available points','可用积分'],
  ['Đang giữ','Reserved','冻结积分'], ['Phí API','API fee','API 费用'],
  ['điểm / lượt thành công','points / successful scan','积分 / 扫码成功'],
  ['Song song tài khoản','Account concurrency','账户并发'], ['Giới hạn dịch vụ','Service limit','全局并发上限'],
  ['Đang chờ','Queued','排队中'], ['Đang xử lý','Processing','执行中'], ['Đang quét','Scanning','扫码中'],
  ['Đã tạo link','Link created','已出链'], ['Đã quét','Scan completed','扫码完成'],
  ['Chờ đối chiếu','Needs reconciliation','待核对'], ['Chờ nạp điểm','Awaiting funds','等待积分'],
  ['Chưa rõ trạng thái','Unknown status','状态未知'], ['Chưa gửi','Not submitted','尚未提交'],
  ['Đang gửi','Submitting','正在提交'], ['Chờ thử lại','Waiting to retry','等待重试'],
  ['Tạo đợt UPI','New UPI batch','新建 UPI 任务'],
  ['AT chỉ được gửi đến ytc.xxsyun.xyz sau bước xác nhận.','ATs are sent to ytc.xxsyun.xyz only after confirmation.','确认后才会将 AT 发送至 ytc.xxsyun.xyz。'],
  ['Dịch vụ sẵn sàng','Service ready','服务可用'], ['Dịch vụ đang bận','Service unavailable','服务暂不可用'],
  ['Chọn từ kho','Choose accounts','从账户库选择'], ['Xóa ô nhập','Clear input','清空输入'],
  ['Mỗi dòng một AT, hoặc dán JSON tài khoản.','One AT per line, or paste account JSON.','每行一个 AT，或粘贴账户 JSON。'],
  ['Đã chọn từ kho','Selected accounts','已选账户'], ['Gói đăng ký','Subscription','订阅套餐'],
  ['Chế độ xử lý','Processing mode','提链模式'], ['Tự thử lại khi quét thất bại','Retry failed scans','扫码失败后自动重提'],
  ['Tối đa 3 lần bổ sung, giữ nguyên tác vụ gốc.','Up to 3 retries using the original task.','最多补提 3 次，沿用原任务。'],
  ['Ước tính nếu tất cả thành công','Estimate if all succeed','全部成功的预计费用'], ['điểm','points','积分'],
  ['Xem trước và gửi','Review and submit','预览并提交'],
  ['Dịch vụ tự quét; chỉ nhận checkout có số tiền bằng 0. Phí API theo tài liệu nhà cung cấp.','Automatic scanning; only zero-amount checkouts. API fees follow the provider documentation.','自动扫码，仅接受零金额订单。API 费用以服务文档为准。'],
  ['Yêu cầu cần xử lý','Pending requests','待处理请求'],
  ['Giữ cùng mã yêu cầu khi đối chiếu; không tạo đợt mới cho phản hồi chưa rõ.','Reconcile with the same request ID; do not create a new batch for uncertain responses.','结果不明确时，使用原请求 ID 核对，请勿新建任务。'],
  ['Xem lại','Review','查看'], ['Tác vụ UPI','UPI tasks','UPI 任务'],
  ['Quét thành công cần được kiểm tra gói lại trong mục Tài khoản.','Verify membership in Accounts after a successful scan.','扫码成功后，请到账户页面验证套餐。'],
  ['Xuất trang','Export page','导出当前页'], ['Email hoặc mã tác vụ','Email or task ID','邮箱或任务 ID'],
  ['Chưa có tác vụ UPI.','No UPI tasks.','暂无 UPI 任务。'],
  ['Tài khoản / Mã tác vụ','Account / Task ID','账户 / 任务 ID'], ['Quét thành công','Scan completed at','扫码成功时间'],
  ['Chưa xác nhận Plus','Plus not verified','尚未验证 Plus'], ['Lệnh đang chờ áp dụng','Control pending','控制命令待生效'],
  ['Số lần bổ sung','Retry count','补提次数'], ['Điều khiển tác vụ UPI','UPI task controls','UPI 任务控制'],
  ['Đồng bộ tác vụ','Refresh task','同步任务'], ['Đối chiếu đơn quét','Reconcile scan','核对扫码订单'],
  ['Đối chiếu UPI','Reconcile UPI','核对 UPI'], ['Dừng tác vụ','Stop task','停止任务'],
  ['Dùng khóa chuyên dụng Yitiaochong API. Khóa được lưu phía máy chủ và không trả lại trình duyệt.','Use a dedicated Yitiaochong API key. It is stored server-side and never returned to the browser.','请使用一条虫 API 专用密钥。密钥仅保存在服务端，不回传浏览器。'],
  ['Đã lưu khóa; để trống để giữ nguyên','Key saved; leave blank to keep it','已保存密钥，留空保留原值'],
  ['Nhập khóa API','Enter API key','输入 API 密钥'], ['Xóa khóa đã lưu','Remove saved key','删除已保存的密钥'],
  ['Lưu và kiểm tra','Save and check','保存并检查'], ['Xác nhận gửi UPI','Confirm UPI submission','确认提交 UPI'],
  ['Tài khoản hợp lệ','Valid accounts','有效账户'], ['Điểm nếu tất cả thành công','Points if all succeed','全部成功的积分费用'],
  ['AT hết hạn','Expired ATs','AT 已过期'], ['AT không hợp lệ','Invalid ATs','AT 无效'], ['trùng AT','duplicate ATs','重复 AT'],
  ['Mã yêu cầu','Request ID','请求 ID'],
  ['Tôi đồng ý gửi AT đến ytc.xxsyun.xyz để tự quét UPI và trừ điểm dịch vụ khi thành công.','I agree to send ATs to ytc.xxsyun.xyz for automatic UPI scanning and success-based service charges.','我同意将 AT 发送至 ytc.xxsyun.xyz 自动扫码，并在成功后扣除服务积分。'],
  ['Checkout bắt buộc 0; phí dịch vụ UPI vẫn được tính. Bản xem trước chưa gửi thanh toán.','Checkout must be zero; UPI service fees still apply. This preview has not submitted payment.','订单金额必须为 0，仍收取 UPI 服务费。当前预览尚未提交支付。'],
  ['Gửi và tự quét UPI','Submit and auto-scan UPI','提交并自动扫码'], ['Đối chiếu cùng yêu cầu','Reconcile original request','核对原请求'],
  ['Chọn tài khoản từ kho','Choose stored accounts','选择账户库中的账户'], ['Tìm email','Search email','搜索邮箱'],
  ['Chọn trang','Select page','选择当前页'], ['Dùng tài khoản đã chọn','Use selected accounts','使用已选账户'],
  ['AT hết hạn / lỗi','Expired / invalid AT','AT 过期 / 错误'], ['Không có tài khoản phù hợp.','No matching accounts.','没有匹配的账户。'],
  ['Chi tiết tác vụ UPI','UPI task details','UPI 任务详情'], ['Trạng thái tạo link','Checkout status','提链状态'],
  ['Trạng thái quét','Scan status','扫码状态'], ['Tạo link thành công','Checkout completed at','出链成功时间'],
  ['Đơn đã có link vẫn tiếp tục quét.','Orders with links continue scanning.','已出链订单仍会继续扫码。'],
  ['Kiểm tra gói trong Tài khoản','Verify plan in Accounts','到账户页面验证套餐'], ['Mở link thanh toán gốc ↗','Open original payment link ↗','打开原支付链接 ↗'],
  ['Đã lưu cấu hình UPI.','UPI settings saved.','UPI 配置已保存。'], ['Dịch vụ đã nhận yêu cầu UPI.','UPI request received.','UPI 请求已受理。'],
  ['Không tải được dữ liệu UPI.','Could not load UPI data.','无法加载 UPI 数据。'], ['Cần đối chiếu yêu cầu UPI.','Reconcile the UPI request.','需要核对 UPI 请求。'],
  ['Tệp AT tối đa 40 MB.','AT files are limited to 40 MB.','AT 文件最大 40 MB。'],
  ['JSON nhập AT không hợp lệ.','Invalid AT JSON.','AT JSON 格式无效。'],
  ['Mỗi đợt UPI tối đa 20.000 tài khoản.','Each UPI batch supports up to 20,000 accounts.','每批 UPI 最多 20,000 个账户。'],
  ['Chọn từ 1 đến 20.000 tài khoản.','Choose 1 to 20,000 accounts.','请选择 1 至 20,000 个账户。'],
  ['Đối chiếu đơn quét gốc bằng cùng khóa chống trùng. Đơn đã được nhận vẫn có thể hoàn tất thanh toán và trừ điểm.','Reconcile the original scan using the same idempotency key. Accepted orders may still complete and incur charges.','使用原幂等键核对扫码订单。已受理订单仍可能完成支付并扣费。'],
  ['Tạm dừng hoặc dừng chỉ chặn bước lấy link mới. Đơn đã có link vẫn có thể quét và trừ điểm. Dừng không thể khôi phục.','Pause or stop blocks new checkout extraction only. Existing links may still be scanned and charged. Stop is irreversible.','暂停或停止仅阻止新的提链。已出链订单仍可扫码和扣费；停止不可恢复。'],
].map(([source, en, zh]) => ({ source, vi: source, en, zh }))
export default [
  ...upiPhrases,
  { source: 'Cách làm mới AT', vi: 'Cách làm mới AT', en: 'How AT refresh works', zh: 'AT 刷新方式' },
  { source: 'Gói tài khoản: {0}', vi: 'Gói tài khoản: {0}', en: 'Account plan: {0}', zh: '账户套餐：{0}' },
  { source: 'Lỗi mạng khi đổi RT; giữ token cũ, chưa đăng nhập lại', vi: 'Lỗi mạng khi đổi RT; giữ token cũ, chưa đăng nhập lại', en: 'RT exchange network failure; credentials kept, login not retried', zh: 'RT 交换网络失败；保留凭据，未重新登录' },
  { source: 'Đổi RT bị giới hạn; chờ rồi thử lại', vi: 'Đổi RT bị giới hạn; chờ rồi thử lại', en: 'RT exchange rate limited; wait before retrying', zh: 'RT 交换受到限流；请稍后重试' },
  { source: 'Máy chủ đổi RT tạm lỗi; giữ token cũ', vi: 'Máy chủ đổi RT tạm lỗi; giữ token cũ', en: 'RT exchange server temporarily unavailable; credentials kept', zh: 'RT 交换服务器暂时不可用；保留凭据' },
  { source: 'Client của RT không hợp lệ; cần kiểm tra nguồn cấp RT', vi: 'Client của RT không hợp lệ; cần kiểm tra nguồn cấp RT', en: 'Invalid RT client; check the original authorization client', zh: 'RT 客户端无效；请检查原始授权客户端' },
  { source: 'Phản hồi đổi RT không hợp lệ; chưa thay AT', vi: 'Phản hồi đổi RT không hợp lệ; chưa thay AT', en: 'Invalid RT exchange response; AT not replaced', zh: 'RT 交换响应无效；未替换 AT' },
  { source: 'Yêu cầu đổi RT bị từ chối; chưa đăng nhập lại', vi: 'Yêu cầu đổi RT bị từ chối; chưa đăng nhập lại', en: 'RT exchange rejected; login not retried', zh: 'RT 交换被拒绝；未重新登录' },
  { source: 'Tài khoản đang được làm mới ở tác vụ khác', vi: 'Tài khoản đang được làm mới ở tác vụ khác', en: 'This account is being refreshed by another task', zh: '其他任务正在刷新此账户' },
  { source: 'Thông tin tài khoản đã đổi trong khi làm mới; không ghi đè', vi: 'Thông tin tài khoản đã đổi trong khi làm mới; không ghi đè', en: 'Account changed during refresh; saved data was not overwritten', zh: '刷新期间账户信息已更改；未覆盖已保存的数据' },
  { source: 'Đã đổi AT qua RT; chưa kiểm tra API', vi: 'Đã đổi AT qua RT; chưa kiểm tra API', en: 'AT renewed through RT; API access not checked yet', zh: '已通过 RT 更新 AT；尚未检查 API 访问' },
  { source: 'Làm mới tài khoản đã chọn dù AT còn hạn; vẫn giữ trạng thái khóa và chờ xử lý mail OTP.', vi: 'Làm mới tài khoản đã chọn dù AT còn hạn; vẫn giữ trạng thái khóa và chờ xử lý mail OTP.', en: 'Refresh selected accounts even with unexpired ATs; keep banned accounts and email OTP holds on hold.', zh: '刷新已选账户，即使 AT 未过期；保留封禁和邮件 OTP 暂停状态。' },
  { source: 'Chỉ làm mới AT cần cứu; bỏ qua AT dùng được, tài khoản khóa và chờ xử lý mail OTP.', vi: 'Chỉ làm mới AT cần cứu; bỏ qua AT dùng được, tài khoản khóa và chờ xử lý mail OTP.', en: 'Refresh only ATs needing recovery; skip usable ATs, banned accounts and email OTP holds.', zh: '仅刷新需要恢复的 AT；跳过可用 AT、封禁账户和邮件 OTP 暂停账户。' },
  { source: 'Ưu tiên RT → AT. Chưa có RT hoặc RT mất hiệu lực mới đăng nhập và thử bổ sung RT; lỗi mạng/429 không đăng nhập lại.', vi: 'Ưu tiên RT → AT. Chưa có RT hoặc RT mất hiệu lực mới đăng nhập và thử bổ sung RT; lỗi mạng/429 không đăng nhập lại.', en: 'Use RT → AT first. Log in and try to obtain RT only when RT is missing or unusable; network/429 failures do not trigger login.', zh: '优先 RT → AT。仅在 RT 缺失或失效时登录并尝试获取 RT；网络/429 错误不触发重新登录。' },
  { source: 'Có RT: {0} · Cần đăng nhập: {1}', vi: 'Có RT: {0} · Cần đăng nhập: {1}', en: 'With RT: {0} · Login needed: {1}', zh: '有 RT：{0} · 需登录：{1}' },
  { source: 'Đang tải từ server…', vi: 'Đang tải từ server…', en: 'Loading from server…', zh: '正在从服务器加载…' },
  { source: 'Có thay đổi chưa lưu', vi: 'Có thay đổi chưa lưu', en: 'Unsaved changes', zh: '有尚未保存的更改' },
  { source: 'Đang lưu lên server…', vi: 'Đang lưu lên server…', en: 'Saving to server…', zh: '正在保存到服务器…' },
  { source: 'Đã lưu và xác nhận trên server', vi: 'Đã lưu và xác nhận trên server', en: 'Saved and confirmed on server', zh: '已保存并在服务器确认' },
  { source: 'Chưa đồng bộ với server', vi: 'Chưa đồng bộ với server', en: 'Not synchronized with server', zh: '尚未与服务器同步' },
  { source: 'Thử lưu lại', vi: 'Thử lưu lại', en: 'Retry saving', zh: '重试保存' },
  { source: 'Tải lại từ server', vi: 'Tải lại từ server', en: 'Reload from server', zh: '从服务器重新加载' },
  { source: 'Chưa kết nối được kho proxy trên server. Hãy tải lại.', vi: 'Chưa kết nối được kho proxy trên server. Hãy tải lại.', en: 'The server proxy pool is unavailable. Reload to retry.', zh: '无法连接服务器代理池，请重新加载。' },
  { source: 'Chưa lưu được lên server. Danh sách trên máy được giữ để thử lại.', vi: 'Chưa lưu được lên server. Danh sách trên máy được giữ để thử lại.', en: 'Saving failed. Your local list is kept for retry.', zh: '保存失败。本机列表已保留，可重试。' },
  { source: 'Không đọc được kho proxy từ server. Hãy thử lại.', vi: 'Không đọc được kho proxy từ server. Hãy thử lại.', en: 'Could not read the server proxy pool. Please retry.', zh: '无法读取服务器代理池，请重试。' },
  { source: 'Có thay đổi chưa lưu. Hãy thử lưu lại trước khi tải từ server.', vi: 'Có thay đổi chưa lưu. Hãy thử lưu lại trước khi tải từ server.', en: 'Unsaved changes exist. Retry saving before reloading from server.', zh: '有未保存的更改，请先重试保存再从服务器加载。' },
  { source: 'Đã lưu khóa · để trống để giữ nguyên', vi: 'Đã lưu khóa · để trống để giữ nguyên', en: 'Key saved · leave blank to keep it', zh: '已保存密钥 · 留空保持不变' },
  { source: 'Chưa cấu hình ReMail API Key', vi: 'Chưa cấu hình ReMail API Key', en: 'ReMail API key is not configured', zh: '尚未配置 ReMail API 密钥' },
  { source: 'Mục tiêu', vi: 'Mục tiêu', en: 'Target', zh: '目标' },
  { source: 'Mục tiêu đăng ký', vi: 'Mục tiêu đăng ký', en: 'Registration target', zh: '注册目标' },
  { source: '0 = không giới hạn', vi: '0 = không giới hạn', en: '0 = unlimited', zh: '0 = 不限' },
  { source: 'Giữ lại {0} mail đang xử lý', vi: 'Giữ lại {0} mail đang xử lý', en: 'Kept {0} mailboxes being processed', zh: '保留 {0} 个正在处理的邮箱', numericSlots: [0] },
  { source: 'Mail đang được worker sử dụng; chưa xóa.', vi: 'Mail đang được worker sử dụng; chưa xóa.', en: 'A worker is using this mailbox; it was kept.', zh: '工作线程正在使用此邮箱，已保留。' },
  { source: 'Mail đang được worker sử dụng; chưa reset.', vi: 'Mail đang được worker sử dụng; chưa reset.', en: 'A worker is using this mailbox; it was not reset.', zh: '工作线程正在使用此邮箱，未重置。' },
  { source: 'Còn tác vụ đang chạy; chưa giải phóng mail.', vi: 'Còn tác vụ đang chạy; chưa giải phóng mail.', en: 'Tasks are still running; mailboxes were not released.', zh: '仍有任务正在运行，未释放邮箱。' },
  { source: 'Yêu cầu thay đổi dữ liệu phải đến từ cùng nguồn với trang web.', vi: 'Yêu cầu thay đổi dữ liệu phải đến từ cùng nguồn với trang web.', en: 'Data changes must originate from this website.', zh: '数据更改请求必须来自此网站。' },
  { source: 'Cả thư mục', vi: 'Cả thư mục', en: 'Entire folder', zh: '整个文件夹' },
  { source: 'Bỏ qua: Sai TK/MK/2FA {0} · Bị khóa {1}', vi: 'Bỏ qua: Sai TK/MK/2FA {0} · Bị khóa {1}', en: 'Skip: credential errors {0} · Banned {1}', zh: '跳过：凭据错误 {0} · 已封禁 {1}' },
  { source: 'Không áp dụng các bộ lọc khác', vi: 'Không áp dụng các bộ lọc khác', en: 'Ignore other filters', zh: '忽略其他筛选条件' },
  { source: 'Toàn bộ kho, không áp dụng bộ lọc', vi: 'Toàn bộ kho, không áp dụng bộ lọc', en: 'All accounts, ignoring filters', zh: '全部账户，忽略筛选条件' },
  { source: 'Làm mới chủ động, kể cả AT còn hạn', vi: 'Làm mới chủ động, kể cả AT còn hạn', en: 'Refresh explicitly, including unexpired ATs', zh: '主动刷新，包括未过期的 AT' },
  { source: 'Làm mới các tài khoản cụ thể đã chọn dù AT còn hạn hoặc chưa rõ hạn; vẫn bỏ qua tài khoản khóa, sai TK/MK/2FA và chờ xử lý mail OTP.', vi: 'Làm mới các tài khoản cụ thể đã chọn dù AT còn hạn hoặc chưa rõ hạn; vẫn bỏ qua tài khoản khóa, sai TK/MK/2FA và chờ xử lý mail OTP.', en: 'Refresh the specific selected accounts even if ATs are unexpired or expiry is unknown. Still skip banned accounts, credential errors and email OTP holds.', zh: '刷新指定账户，即使 AT 未过期或有效期未知。仍跳过封禁、凭据错误及等待邮件 OTP 处理的账户。' },
  { source: 'Muốn làm mới AT còn hạn, chọn tài khoản cụ thể hoặc tích chọn các tài khoản cần làm mới.', vi: 'Muốn làm mới AT còn hạn, chọn tài khoản cụ thể hoặc tích chọn các tài khoản cần làm mới.', en: 'To refresh unexpired ATs, open a specific account or select the accounts to refresh.', zh: '如需刷新未过期的 AT，请打开指定账户或勾选需要刷新的账户。' },
  { source: 'Làm mới thêm: AT còn hạn/dùng được {0} · Chưa rõ hạn {1}', vi: 'Làm mới thêm: AT còn hạn/dùng được {0} · Chưa rõ hạn {1}', en: 'Also refresh: unexpired/usable ATs {0} · Unknown expiry {1}', zh: '额外刷新：未过期/可用 AT {0} · 有效期未知 {1}' },
  { source: 'Tuần', vi: 'Tuần', en: 'Weekly', zh: '每周' },
  { source: 'Chưa rõ mốc reset', vi: 'Chưa rõ mốc reset', en: 'Reset time unknown', zh: '重置时间未知' },
  { source: 'Hạn thuê bao', vi: 'Hạn thuê bao', en: 'Subscription expires', zh: '订阅到期时间' },
  { source: 'Hạn gói còn {days} ngày', vi: 'Hạn gói còn {days} ngày', en: 'Plan expires in {days} days', zh: '套餐将在 {days} 天后到期' },
  { source: 'Gói đã hết hạn', vi: 'Gói đã hết hạn', en: 'Plan expired', zh: '套餐已过期' },
  { source: 'Chưa rõ hạn gói', vi: 'Chưa rõ hạn gói', en: 'Plan expiry unknown', zh: '套餐到期时间未知' },
  { source: 'Kiểm tra quota', vi: 'Kiểm tra quota', en: 'Check quota', zh: '检查额度' },
  { source: 'Xem chi tiết quota', vi: 'Xem chi tiết quota', en: 'View quota details', zh: '查看额度详情' },
  { source: 'Quota Codex / Work', vi: 'Quota Codex / Work', en: 'Codex / Work quota', zh: 'Codex / Work 额度' },
  { source: 'Còn', vi: 'Còn', en: 'Remaining', zh: '剩余' },
  { source: 'Đã dùng', vi: 'Đã dùng', en: 'Used', zh: '已使用' },
  { source: 'Chưa rõ chu kỳ', vi: 'Chưa rõ chu kỳ', en: 'Unknown window', zh: '周期未知' },
  { source: 'Cần kiểm tra lại', vi: 'Cần kiểm tra lại', en: 'Recheck needed', zh: '需要重新检查' },
  { source: 'Kết quả lần trước', vi: 'Kết quả lần trước', en: 'Previous result', zh: '上次结果' },
  { source: 'Chưa đọc được quota', vi: 'Chưa đọc được quota', en: 'Quota unavailable', zh: '暂无法读取额度' },
  { source: 'Có hạn mức đã chạm giới hạn', vi: 'Có hạn mức đã chạm giới hạn', en: 'A usage limit has been reached', zh: '某项额度已达上限' },
  { source: 'Có hạn mức đã chạm giới hạn: {count}', vi: 'Có hạn mức đã chạm giới hạn: {count}', en: 'A usage limit reached: {count}', zh: '达到额度上限：{count}' },
  { source: 'Đọc được quota: {count}', vi: 'Đọc được quota: {count}', en: 'Quota retrieved: {count}', zh: '已读取额度：{count}' },
  { source: 'Lần kiểm tra gần nhất chưa thành công', vi: 'Lần kiểm tra gần nhất chưa thành công', en: 'The latest check failed', zh: '最近一次检查失败' },
  { source: 'Reset theo API', vi: 'Reset theo API', en: 'Reset reported by API', zh: 'API 返回的重置时间' },
  { source: 'Thời điểm reset là dữ liệu tại lần kiểm tra.', vi: 'Thời điểm reset là dữ liệu tại lần kiểm tra.', en: 'Reset time is a snapshot from the last check.', zh: '重置时间是上次检查时的快照。' },
  { source: 'Chỉ các hạn mức endpoint trả về; không đại diện mọi model ChatGPT.', vi: 'Chỉ các hạn mức endpoint trả về; không đại diện mọi model ChatGPT.', en: 'Only limits returned by the endpoint; does not cover every ChatGPT model.', zh: '仅显示接口返回的额度，不代表所有 ChatGPT 模型。' },
  { source: 'AT đã đổi hoặc mốc reset đã qua; cần kiểm tra lại.', vi: 'AT đã đổi hoặc mốc reset đã qua; cần kiểm tra lại.', en: 'The AT changed or the reset time passed; check again.', zh: 'AT 已更改或重置时间已过，请重新检查。' },
  { source: 'Đọc quota Codex / Work bằng AT hiện có; không tự đăng nhập hay làm mới token. Chưa có AT hoặc AT hết hạn cần làm mới trước.', vi: 'Đọc quota Codex / Work bằng AT hiện có; không tự đăng nhập hay làm mới token. Chưa có AT hoặc AT hết hạn cần làm mới trước.', en: 'Read Codex / Work quota with the existing AT. No automatic login or token refresh. Refresh missing or expired ATs first.', zh: '使用现有 AT 读取 Codex / Work 额度，不会自动登录或刷新令牌。AT 缺失或过期时请先刷新。' },
  { source: 'Chưa có AT; cần làm mới AT trước khi kiểm tra quota', vi: 'Chưa có AT; cần làm mới AT trước khi kiểm tra quota', en: 'No AT; refresh the AT before checking quota', zh: '没有 AT，请先刷新 AT 再检查额度' },
  { source: 'AT đã hết hạn; cần làm mới AT trước khi kiểm tra quota', vi: 'AT đã hết hạn; cần làm mới AT trước khi kiểm tra quota', en: 'AT expired; refresh it before checking quota', zh: 'AT 已过期，请先刷新后再检查额度' },
  { source: 'API quota trả HTTP {code}', vi: 'API quota trả HTTP {code}', en: 'Quota API returned HTTP {code}', zh: '额度 API 返回 HTTP {code}' },
  { source: 'Chưa đọc được quota: JSON, workspace hoặc cấu trúc phản hồi chưa được xác nhận', vi: 'Chưa đọc được quota: JSON, workspace hoặc cấu trúc phản hồi chưa được xác nhận', en: 'Quota unavailable: JSON, workspace or response format could not be verified', zh: '无法读取额度：JSON、工作区或响应格式尚未验证' },
  { source: 'Không đọc được quota qua proxy: {type}', vi: 'Không đọc được quota qua proxy: {type}', en: 'Could not read quota through proxy: {type}', zh: '无法通过代理读取额度：{type}' },
  { source: 'Tài khoản hoặc AT đã đổi trong lúc kiểm tra; cần kiểm tra lại', vi: 'Tài khoản hoặc AT đã đổi trong lúc kiểm tra; cần kiểm tra lại', en: 'The account or AT changed during the check; check again', zh: '检查期间账户或 AT 已更改，请重新检查' },
  { source: 'ngày', vi: 'ngày', en: 'days', zh: '天' },
  { source: 'giờ', vi: 'giờ', en: 'hours', zh: '小时' },
  { source: 'phút', vi: 'phút', en: 'minutes', zh: '分钟' },
  { source: 'giây', vi: 'giây', en: 'seconds', zh: '秒' },
  {
    "source": "Tên thư mục",
    "vi": "Tên thư mục",
    "en": "Folder name",
    "zh": "文件夹名称"
  },
  {
    "source": "Gói trả phí",
    "vi": "Gói trả phí",
    "en": "Paid plans",
    "zh": "付费套餐"
  },
  {
    "source": "Chưa xác minh gói",
    "vi": "Chưa xác minh gói",
    "en": "Plan not verified",
    "zh": "套餐未验证"
  },
  {
    "source": "Chưa từng kiểm tra",
    "vi": "Chưa từng kiểm tra",
    "en": "Never checked",
    "zh": "从未检查"
  },
  {
    "source": "Đã kiểm tra gói / ưu đãi",
    "vi": "Đã kiểm tra gói / ưu đãi",
    "en": "Plan / offer checked",
    "zh": "已检查套餐／优惠"
  },
  {
    "source": "Cần làm mới AT",
    "vi": "Cần làm mới AT",
    "en": "AT needs refresh",
    "zh": "AT需要刷新"
  },
  {
    "source": "Còn hạn / đã dùng được",
    "vi": "Còn hạn / đã dùng được",
    "en": "Unexpired / usable",
    "zh": "未过期／可用"
  },
  {
    "source": "Hết hạn / bị từ chối",
    "vi": "Hết hạn / bị từ chối",
    "en": "Expired / rejected",
    "zh": "已过期／被拒绝"
  },
  {
    "source": "Chưa có AT",
    "vi": "Chưa có AT",
    "en": "No AT",
    "zh": "无AT"
  },
  {
    "source": "Chưa rõ hạn",
    "vi": "Chưa rõ hạn",
    "en": "Expiry unknown",
    "zh": "到期时间未知"
  },
  {
    "source": "Bị khóa khi quét",
    "vi": "Bị khóa khi quét",
    "en": "Blocked during check",
    "zh": "检查时被封禁"
  },
  {
    "source": "Có lỗi làm mới",
    "vi": "Có lỗi làm mới",
    "en": "Refresh errors",
    "zh": "刷新错误"
  },
  {
    "source": "Sai tài khoản / mật khẩu",
    "vi": "Sai tài khoản / mật khẩu",
    "en": "Incorrect account / password",
    "zh": "账号／密码错误"
  },
  {
    "source": "Sai hoặc thiếu 2FA",
    "vi": "Sai hoặc thiếu 2FA",
    "en": "Incorrect or missing 2FA",
    "zh": "2FA错误或缺失"
  },
  {
    "source": "Tài khoản bị khóa",
    "vi": "Tài khoản bị khóa",
    "en": "Account blocked",
    "zh": "账号已封禁"
  },
  {
    "source": "Chờ xử lý mail OTP",
    "vi": "Chờ xử lý mail OTP",
    "en": "Email OTP needs attention",
    "zh": "邮箱验证码待处理"
  },
  {
    "source": "Lỗi OTP email",
    "vi": "Lỗi OTP email",
    "en": "Email OTP error",
    "zh": "邮箱验证码错误"
  },
  {
    "source": "Lỗi proxy / mạng",
    "vi": "Lỗi proxy / mạng",
    "en": "Proxy / network error",
    "zh": "代理／网络错误"
  },
  {
    "source": "Bấm để sao chép mật khẩu",
    "vi": "Bấm để sao chép mật khẩu",
    "en": "Click to copy password",
    "zh": "点击复制密码"
  },
  {
    "source": "Sao chép mật khẩu",
    "vi": "Sao chép mật khẩu",
    "en": "Copy password",
    "zh": "复制密码"
  },
  {
    "source": "Ẩn mật khẩu",
    "vi": "Ẩn mật khẩu",
    "en": "Hide password",
    "zh": "隐藏密码"
  },
  {
    "source": "Hiển thị mật khẩu",
    "vi": "Hiển thị mật khẩu",
    "en": "Show password",
    "zh": "显示密码"
  },
  {
    "source": "Chưa có",
    "vi": "Chưa có",
    "en": "Not available",
    "zh": "暂无"
  },
  {
    "source": "Sao chép khóa 2FA",
    "vi": "Sao chép khóa 2FA",
    "en": "Copy 2FA secret",
    "zh": "复制2FA密钥"
  },
  {
    "source": "Bấm để sao chép mã OTP 2FA",
    "vi": "Bấm để sao chép mã OTP 2FA",
    "en": "Click to copy 2FA OTP",
    "zh": "点击复制2FA验证码"
  },
  {
    "source": "Sao chép OTP 2FA",
    "vi": "Sao chép OTP 2FA",
    "en": "Copy 2FA OTP",
    "zh": "复制2FA验证码"
  },
  {
    "source": "Đang tạo OTP",
    "vi": "Đang tạo OTP",
    "en": "Generating OTP",
    "zh": "正在生成验证码"
  },
  {
    "source": "Chưa có khóa 2FA",
    "vi": "Chưa có khóa 2FA",
    "en": "No 2FA secret",
    "zh": "无2FA密钥"
  },
  {
    "source": "Lỗi OTP",
    "vi": "Lỗi OTP",
    "en": "OTP error",
    "zh": "验证码错误"
  },
  {
    "source": "OTP đổi sau {0} giây",
    "vi": "OTP đổi sau {0} giây",
    "en": "OTP changes in {0} seconds",
    "zh": "验证码将在{0}秒后更新"
  },
  {
    "source": "Lọc tài khoản",
    "vi": "Lọc tài khoản",
    "en": "Filter accounts",
    "zh": "筛选账号"
  },
  {
    "source": "Chọn nhiều giá trị trong một mục. Các mục khác nhau được kết hợp với nhau.",
    "vi": "Chọn nhiều giá trị trong một mục. Các mục khác nhau được kết hợp với nhau.",
    "en": "Select multiple values in each section. Different sections are combined.",
    "zh": "每项可选择多个值，不同项目的条件同时生效。"
  },
  {
    "source": "Thư mục",
    "vi": "Thư mục",
    "en": "Folder",
    "zh": "文件夹"
  },
  {
    "source": "Lọc theo thư mục",
    "vi": "Lọc theo thư mục",
    "en": "Filter by folder",
    "zh": "按文件夹筛选"
  },
  {
    "source": "Tất cả thư mục",
    "vi": "Tất cả thư mục",
    "en": "All folders",
    "zh": "所有文件夹"
  },
  {
    "source": "Chưa phân thư mục",
    "vi": "Chưa phân thư mục",
    "en": "Unfiled",
    "zh": "未分类"
  },
  {
    "source": "Gói tài khoản / Ưu đãi",
    "vi": "Gói tài khoản / Ưu đãi",
    "en": "Account plan / offers",
    "zh": "账号套餐／优惠"
  },
  {
    "source": "Trạng thái AT",
    "vi": "Trạng thái AT",
    "en": "AT status",
    "zh": "AT状态"
  },
  {
    "source": "Lỗi cần xử lý",
    "vi": "Lỗi cần xử lý",
    "en": "Errors needing attention",
    "zh": "待处理错误"
  },
  {
    "source": "Quốc gia trong bộ lọc",
    "vi": "Quốc gia trong bộ lọc",
    "en": "Country filter",
    "zh": "国家筛选"
  },
  {
    "source": "Tất cả quốc gia",
    "vi": "Tất cả quốc gia",
    "en": "All countries",
    "zh": "所有国家"
  },
  {
    "source": "Ngày tạo",
    "vi": "Ngày tạo",
    "en": "Created date",
    "zh": "创建日期"
  },
  {
    "source": "Xóa điều kiện",
    "vi": "Xóa điều kiện",
    "en": "Clear conditions",
    "zh": "清除条件"
  },
  {
    "source": "Lưu bộ lọc…",
    "vi": "Lưu bộ lọc…",
    "en": "Save filter…",
    "zh": "保存筛选…"
  },
  {
    "source": "Áp dụng",
    "vi": "Áp dụng",
    "en": "Apply",
    "zh": "应用"
  },
  {
    "source": "Thư mục tài khoản",
    "vi": "Thư mục tài khoản",
    "en": "Account folders",
    "zh": "账号文件夹"
  },
  {
    "source": "THƯ MỤC",
    "vi": "THƯ MỤC",
    "en": "FOLDERS",
    "zh": "文件夹"
  },
  {
    "source": "Tạo thư mục",
    "vi": "Tạo thư mục",
    "en": "Create folder",
    "zh": "新建文件夹"
  },
  {
    "source": "Tất cả tài khoản",
    "vi": "Tất cả tài khoản",
    "en": "All accounts",
    "zh": "所有账号"
  },
  {
    "source": "Tìm thư mục…",
    "vi": "Tìm thư mục…",
    "en": "Search folders…",
    "zh": "搜索文件夹…"
  },
  {
    "source": "Tìm thư mục",
    "vi": "Tìm thư mục",
    "en": "Search folders",
    "zh": "搜索文件夹"
  },
  {
    "source": "Sắp xếp thư mục {0}",
    "vi": "Sắp xếp thư mục {0}",
    "en": "Reorder folder {0}",
    "zh": "调整文件夹{0}的顺序"
  },
  {
    "source": "Kéo để sắp xếp · Alt + ↑ / ↓",
    "vi": "Kéo để sắp xếp · Alt + ↑ / ↓",
    "en": "Drag to reorder · Alt + ↑ / ↓",
    "zh": "拖动排序 · Alt + ↑ / ↓"
  },
  {
    "source": "Mở thư mục {0}",
    "vi": "Mở thư mục {0}",
    "en": "Open folder {0}",
    "zh": "打开文件夹{0}"
  },
  {
    "source": "Thao tác thư mục {0}",
    "vi": "Thao tác thư mục {0}",
    "en": "Actions for folder {0}",
    "zh": "文件夹{0}的操作"
  },
  {
    "source": "Đưa lên",
    "vi": "Đưa lên",
    "en": "Move up",
    "zh": "上移"
  },
  {
    "source": "Đưa xuống",
    "vi": "Đưa xuống",
    "en": "Move down",
    "zh": "下移"
  },
  {
    "source": "Đổi tên thư mục",
    "vi": "Đổi tên thư mục",
    "en": "Rename folder",
    "zh": "重命名文件夹"
  },
  {
    "source": "Chuyển tài khoản trong thư mục…",
    "vi": "Chuyển tài khoản trong thư mục…",
    "en": "Move accounts in this folder…",
    "zh": "移动此文件夹中的账号…"
  },
  {
    "source": "Xóa thư mục…",
    "vi": "Xóa thư mục…",
    "en": "Delete folder…",
    "zh": "删除文件夹…"
  },
  {
    "source": "Không tìm thấy thư mục",
    "vi": "Không tìm thấy thư mục",
    "en": "No folders found",
    "zh": "未找到文件夹"
  },
  {
    "source": "Tạo thư mục đầu tiên để sắp xếp tài khoản.",
    "vi": "Tạo thư mục đầu tiên để sắp xếp tài khoản.",
    "en": "Create your first folder to organize accounts.",
    "zh": "创建第一个文件夹来整理账号。"
  },
  {
    "source": "Đang lưu thứ tự…",
    "vi": "Đang lưu thứ tự…",
    "en": "Saving order…",
    "zh": "正在保存顺序…"
  },
  {
    "source": "BỘ LỌC ĐÃ LƯU",
    "vi": "BỘ LỌC ĐÃ LƯU",
    "en": "SAVED FILTERS",
    "zh": "已保存的筛选"
  },
  {
    "source": "Bỏ bộ lọc đã lưu {0}",
    "vi": "Bỏ bộ lọc đã lưu {0}",
    "en": "Remove saved filter {0}",
    "zh": "移除已保存的筛选{0}"
  },
  {
    "source": "thư mục",
    "vi": "thư mục",
    "en": "folders",
    "zh": "个文件夹"
  },
  {
    "source": "tài khoản đã sắp xếp",
    "vi": "tài khoản đã sắp xếp",
    "en": "filed accounts",
    "zh": "个已分类账号"
  },
  {
    "source": "Theo dõi tác vụ tài khoản",
    "vi": "Theo dõi tác vụ tài khoản",
    "en": "Account task progress",
    "zh": "账号任务进度"
  },
  {
    "source": "Thu gọn tiến độ",
    "vi": "Thu gọn tiến độ",
    "en": "Collapse progress",
    "zh": "收起进度"
  },
  {
    "source": "Mở tiến độ",
    "vi": "Mở tiến độ",
    "en": "Expand progress",
    "zh": "展开进度"
  },
  {
    "source": "tài khoản ·",
    "vi": "tài khoản ·",
    "en": "accounts ·",
    "zh": "个账号 ·"
  },
  {
    "source": "Thử lại acc có thể cứu",
    "vi": "Thử lại acc có thể cứu",
    "en": "Retry eligible failed accounts",
    "zh": "重试可恢复的失败账号"
  },
  {
    "source": "Tải lại tiến độ",
    "vi": "Tải lại tiến độ",
    "en": "Reload progress",
    "zh": "重新加载进度"
  },
  {
    "source": "Tải lại",
    "vi": "Tải lại",
    "en": "Reload",
    "zh": "重新加载"
  },
  {
    "source": "Đang dừng",
    "vi": "Đang dừng",
    "en": "Stopping",
    "zh": "正在停止"
  },
  {
    "source": "Đang gửi lệnh dừng",
    "vi": "Đang gửi lệnh dừng",
    "en": "Sending stop request",
    "zh": "正在发送停止请求"
  },
  {
    "source": "Dừng tác vụ",
    "vi": "Dừng tác vụ",
    "en": "Stop task",
    "zh": "停止任务"
  },
  {
    "source": "{0}: {1} trên {2}",
    "vi": "{0}: {1} trên {2}",
    "en": "{0}: {1} of {2}",
    "zh": "{0}：{1}／{2}",
    "numericSlots": [
      1,
      2
    ],
    "translateSlots": [
      0
    ]
  },
  {
    "source": "Xem kết quả cần chú ý",
    "vi": "Xem kết quả cần chú ý",
    "en": "View results needing attention",
    "zh": "查看需要处理的结果"
  },
  {
    "source": "Cần xử lý",
    "vi": "Cần xử lý",
    "en": "Needs attention",
    "zh": "待处理"
  },
  {
    "source": "Còn lại",
    "vi": "Còn lại",
    "en": "Remaining",
    "zh": "剩余"
  },
  {
    "source": "Chưa xử lý",
    "vi": "Chưa xử lý",
    "en": "Unprocessed",
    "zh": "未处理"
  },
  {
    "source": "Bỏ qua:",
    "vi": "Bỏ qua:",
    "en": "Skipped:",
    "zh": "已跳过："
  },
  {
    "source": "Chưa có kết quả xác minh gói",
    "vi": "Chưa có kết quả xác minh gói",
    "en": "No verified plan results yet",
    "zh": "暂无已验证的套餐结果"
  },
  {
    "source": "Yêu cầu",
    "vi": "Yêu cầu",
    "en": "Requested",
    "zh": "请求数"
  },
  {
    "source": "Kết nối",
    "vi": "Kết nối",
    "en": "Connection",
    "zh": "连接"
  },
  {
    "source": "proxy lỗi đã bỏ qua",
    "vi": "proxy lỗi đã bỏ qua",
    "en": "failed proxies skipped",
    "zh": "个失败代理已跳过"
  },
  {
    "source": "Luân phiên theo tài khoản",
    "vi": "Luân phiên theo tài khoản",
    "en": "Rotate per account",
    "zh": "按账号轮换"
  },
  {
    "source": "Lưu lượng riêng của đợt này, ước tính nội dung HTTP. Chưa gồm header/TCP/TLS.",
    "vi": "Lưu lượng riêng của đợt này, ước tính nội dung HTTP. Chưa gồm header/TCP/TLS.",
    "en": "Traffic for this batch only, estimated from HTTP content. Excludes headers, TCP and TLS.",
    "zh": "仅统计本批次流量，按HTTP内容估算，不含请求头、TCP和TLS。"
  },
  {
    "source": "Lưu lượng đợt này",
    "vi": "Lưu lượng đợt này",
    "en": "Batch traffic",
    "zh": "本批次流量"
  },
  {
    "source": "Chưa đo",
    "vi": "Chưa đo",
    "en": "Not measured",
    "zh": "未测量"
  },
  {
    "source": "· đo một phần",
    "vi": "· đo một phần",
    "en": "· partially measured",
    "zh": "· 部分测量"
  },
  {
    "source": "Chờ mail OTP",
    "vi": "Chờ mail OTP",
    "en": "Waiting for email OTP",
    "zh": "等待邮箱验证码"
  },
  {
    "source": "Lọc acc lỗi",
    "vi": "Lọc acc lỗi",
    "en": "Filter failed accounts",
    "zh": "筛选失败账号"
  },
  {
    "source": "Đã nhận lệnh dừng. Đợi các acc đang xử lý hoàn tất; các acc tiếp theo sẽ được giữ lại.",
    "vi": "Đã nhận lệnh dừng. Đợi các acc đang xử lý hoàn tất; các acc tiếp theo sẽ được giữ lại.",
    "en": "Stop request received. Waiting for active accounts to finish; remaining accounts will be kept.",
    "zh": "已收到停止请求，等待当前账号处理完成，其余账号将保留。"
  },
  {
    "source": "Đang gửi lệnh dừng, chờ máy chủ xác nhận.",
    "vi": "Đang gửi lệnh dừng, chờ máy chủ xác nhận.",
    "en": "Sending stop request; waiting for server confirmation.",
    "zh": "正在发送停止请求，等待服务器确认。"
  },
  {
    "source": "Ẩn chi tiết",
    "vi": "Ẩn chi tiết",
    "en": "Hide details",
    "zh": "隐藏详情"
  },
  {
    "source": "Chi tiết tác vụ",
    "vi": "Chi tiết tác vụ",
    "en": "Task details",
    "zh": "任务详情"
  },
  {
    "source": "Chạy trên VPS · Có thể đóng tab",
    "vi": "Chạy trên VPS · Có thể đóng tab",
    "en": "Runs on VPS · You may close this tab",
    "zh": "在VPS上运行 · 可关闭此标签页"
  },
  {
    "source": "Đang chạy ({0})",
    "vi": "Đang chạy ({0})",
    "en": "Running ({0})",
    "zh": "正在运行（{0}）"
  },
  {
    "source": "Đang chờ lượt xử lý tiếp theo.",
    "vi": "Đang chờ lượt xử lý tiếp theo.",
    "en": "Waiting for the next account.",
    "zh": "等待处理下一个账号。"
  },
  {
    "source": "Không còn tài khoản đang xử lý.",
    "vi": "Không còn tài khoản đang xử lý.",
    "en": "No accounts are being processed.",
    "zh": "当前没有正在处理的账号。"
  },
  {
    "source": "Kết nối hiện tại:",
    "vi": "Kết nối hiện tại:",
    "en": "Current connection:",
    "zh": "当前连接："
  },
  {
    "source": "Lỗi gần nhất ({0})",
    "vi": "Lỗi gần nhất ({0})",
    "en": "Recent errors ({0})",
    "zh": "最近的错误（{0}）"
  },
  {
    "source": "kết quả cần chú ý trong",
    "vi": "kết quả cần chú ý trong",
    "en": "results needing attention among",
    "zh": "个待处理结果，范围为"
  },
  {
    "source": "acc gần nhất.",
    "vi": "acc gần nhất.",
    "en": "recent accounts.",
    "zh": "个最近处理的账号。"
  },
  {
    "source": "Chưa xác định được kết quả",
    "vi": "Chưa xác định được kết quả",
    "en": "Result not determined",
    "zh": "尚无法确定结果"
  },
  {
    "source": "Chưa có kết quả cần chú ý.",
    "vi": "Chưa có kết quả cần chú ý.",
    "en": "No results need attention.",
    "zh": "暂无需要处理的结果。"
  },
  {
    "source": "Lưu lượng ({0})",
    "vi": "Lưu lượng ({0})",
    "en": "Traffic ({0})",
    "zh": "流量（{0}）"
  },
  {
    "source": "Số đo của",
    "vi": "Số đo của",
    "en": "Measurements for",
    "zh": "测量范围："
  },
  {
    "source": "tài khoản gần nhất trong đợt này.",
    "vi": "tài khoản gần nhất trong đợt này.",
    "en": "recent accounts in this batch.",
    "zh": "个本批次最近处理的账号。"
  },
  {
    "source": "· bỏ qua",
    "vi": "· bỏ qua",
    "en": "· skipped",
    "zh": "· 已跳过"
  },
  {
    "source": "Đợt này chưa có số đo lưu lượng.",
    "vi": "Đợt này chưa có số đo lưu lượng.",
    "en": "No traffic measurements for this batch yet.",
    "zh": "本批次暂无流量数据。"
  },
  {
    "source": "Tác vụ tài khoản",
    "vi": "Tác vụ tài khoản",
    "en": "Account task",
    "zh": "账号任务"
  },
  {
    "source": "Đang chờ",
    "vi": "Đang chờ",
    "en": "Queued",
    "zh": "排队中"
  },
  {
    "source": "Đã dừng",
    "vi": "Đã dừng",
    "en": "Stopped",
    "zh": "已停止"
  },
  {
    "source": "Dừng do lỗi",
    "vi": "Dừng do lỗi",
    "en": "Stopped on error",
    "zh": "因错误停止"
  },
  {
    "source": "Bị gián đoạn",
    "vi": "Bị gián đoạn",
    "en": "Interrupted",
    "zh": "已中断"
  },
  {
    "source": "Chưa kết nối",
    "vi": "Chưa kết nối",
    "en": "Not connected",
    "zh": "未连接"
  },
  {
    "source": "Trực tiếp",
    "vi": "Trực tiếp",
    "en": "Direct",
    "zh": "直连"
  },
  {
    "source": "Proxy checkout",
    "vi": "Proxy checkout",
    "en": "Checkout proxy",
    "zh": "结账代理"
  },
  {
    "source": "Proxy riêng",
    "vi": "Proxy riêng",
    "en": "Custom proxy",
    "zh": "自定义代理"
  },
  {
    "source": "Dùng được",
    "vi": "Dùng được",
    "en": "Usable",
    "zh": "可用"
  },
  {
    "source": "Hết hạn",
    "vi": "Hết hạn",
    "en": "Expired",
    "zh": "已过期"
  },
  {
    "source": "Bị khóa",
    "vi": "Bị khóa",
    "en": "Blocked",
    "zh": "已封禁"
  },
  {
    "source": "Chưa rõ",
    "vi": "Chưa rõ",
    "en": "Unknown",
    "zh": "未知"
  },
  {
    "source": "Bỏ qua còn hạn",
    "vi": "Bỏ qua còn hạn",
    "en": "Skipped unexpired",
    "zh": "已跳过未过期项"
  },
  {
    "source": "Bỏ qua đã dùng được",
    "vi": "Bỏ qua đã dùng được",
    "en": "Skipped usable",
    "zh": "已跳过可用项"
  },
  {
    "source": "Thiết lập bảng",
    "vi": "Thiết lập bảng",
    "en": "Table settings",
    "zh": "表格设置"
  },
  {
    "source": "Ẩn cột bổ sung",
    "vi": "Ẩn cột bổ sung",
    "en": "Hide extra columns",
    "zh": "隐藏附加列"
  },
  {
    "source": "Hiện cột bổ sung",
    "vi": "Hiện cột bổ sung",
    "en": "Show extra columns",
    "zh": "显示附加列"
  },
  {
    "source": "Quản lý thư mục…",
    "vi": "Quản lý thư mục…",
    "en": "Manage folders…",
    "zh": "管理文件夹…"
  },
  {
    "source": "Dọn toàn bộ kho…",
    "vi": "Dọn toàn bộ kho…",
    "en": "Clear entire account store…",
    "zh": "清空所有账号…"
  },
  {
    "source": "Tìm tài khoản",
    "vi": "Tìm tài khoản",
    "en": "Search accounts",
    "zh": "搜索账号"
  },
  {
    "source": "Tìm email hoặc tên miền…",
    "vi": "Tìm email hoặc tên miền…",
    "en": "Search email or domain…",
    "zh": "搜索邮箱或域名…"
  },
  {
    "source": "Tìm theo email",
    "vi": "Tìm theo email",
    "en": "Search by email",
    "zh": "按邮箱搜索"
  },
  {
    "source": "Bộ lọc",
    "vi": "Bộ lọc",
    "en": "Filters",
    "zh": "筛选"
  },
  {
    "source": "Lọc nhanh",
    "vi": "Lọc nhanh",
    "en": "Quick filters",
    "zh": "快捷筛选"
  },
  {
    "source": "Ưu đãi Plus",
    "vi": "Ưu đãi Plus",
    "en": "Plus offers",
    "zh": "Plus优惠"
  },
  {
    "source": "Điều kiện đang lọc",
    "vi": "Điều kiện đang lọc",
    "en": "Active filters",
    "zh": "当前筛选条件"
  },
  {
    "source": "Xóa bộ lọc",
    "vi": "Xóa bộ lọc",
    "en": "Clear filters",
    "zh": "清除筛选"
  },
  {
    "source": "{0} đã chọn",
    "vi": "{0} đã chọn",
    "en": "{0} selected",
    "zh": "已选{0}项",
    "numericSlots": [
      0
    ]
  },
  {
    "source": "{0} kết quả",
    "vi": "{0} kết quả",
    "en": "{0} results",
    "zh": "{0}个结果",
    "numericSlots": [
      0
    ]
  },
  {
    "source": "Bỏ chọn tài khoản",
    "vi": "Bỏ chọn tài khoản",
    "en": "Deselect accounts",
    "zh": "取消选择账号"
  },
  {
    "source": "Bỏ chọn",
    "vi": "Bỏ chọn",
    "en": "Deselect",
    "zh": "取消选择"
  },
  {
    "source": "Chuyển thư mục",
    "vi": "Chuyển thư mục",
    "en": "Move to folder",
    "zh": "移动到文件夹"
  },
  {
    "source": "Kiểm tra AT",
    "vi": "Kiểm tra AT",
    "en": "Check AT",
    "zh": "检查AT"
  },
  {
    "source": "Kiểm tra gói",
    "vi": "Kiểm tra gói",
    "en": "Check plan",
    "zh": "检查套餐"
  },
  {
    "source": "Nâng cao",
    "vi": "Nâng cao",
    "en": "Advanced",
    "zh": "高级"
  },
  {
    "source": "Dò checkout…",
    "vi": "Dò checkout…",
    "en": "Probe checkout…",
    "zh": "探测结账…"
  },
  {
    "source": "Theo dõi ưu đãi…",
    "vi": "Theo dõi ưu đãi…",
    "en": "Track offers…",
    "zh": "查看优惠…"
  },
  {
    "source": "Làm mới AT",
    "vi": "Làm mới AT",
    "en": "Refresh AT",
    "zh": "刷新AT"
  },
  {
    "source": "Xuất",
    "vi": "Xuất",
    "en": "Export",
    "zh": "导出"
  },
  {
    "source": "Chỉ Access Token (AT)",
    "vi": "Chỉ Access Token (AT)",
    "en": "Access Token (AT) only",
    "zh": "仅Access Token（AT）"
  },
  {
    "source": "Email · Mật khẩu · 2FA",
    "vi": "Email · Mật khẩu · 2FA",
    "en": "Email · Password · 2FA",
    "zh": "邮箱 · 密码 · 2FA"
  },
  {
    "source": "Định dạng và phạm vi…",
    "vi": "Định dạng và phạm vi…",
    "en": "Format and scope…",
    "zh": "格式和范围…"
  },
  {
    "source": "Thao tác thêm với phạm vi",
    "vi": "Thao tác thêm với phạm vi",
    "en": "More actions for this scope",
    "zh": "此范围的更多操作"
  },
  {
    "source": "Chuyển kết quả lọc…",
    "vi": "Chuyển kết quả lọc…",
    "en": "Move filtered results…",
    "zh": "移动筛选结果…"
  },
  {
    "source": "tài khoản đã chọn…",
    "vi": "tài khoản đã chọn…",
    "en": "selected accounts…",
    "zh": "个已选账号…"
  },
  {
    "source": "kết quả lọc…",
    "vi": "kết quả lọc…",
    "en": "filtered results…",
    "zh": "个筛选结果…"
  },
  {
    "source": "Nhật ký Hoạt động Thời gian thực",
    "vi": "Nhật ký Hoạt động Thời gian thực",
    "en": "Live activity log",
    "zh": "实时活动日志"
  },
  {
    "source": "清空日志",
    "vi": "Xóa nhật ký",
    "en": "Clear log",
    "zh": "清空日志"
  },
  {
    "source": "Xóa nhật ký",
    "vi": "Xóa nhật ký",
    "en": "Clear log",
    "zh": "清空日志"
  },
  {
    "source": "Đang chờ luồng worker xuất nhật ký hoạt động…",
    "vi": "Đang chờ luồng worker xuất nhật ký hoạt động…",
    "en": "Waiting for worker activity logs…",
    "zh": "等待工作线程输出活动日志…"
  },
  {
    "source": "Ước tính dung lượng nội dung HTTP, gồm kiểm tra proxy và các lần thử lại được đo. Không gồm header, TCP/TLS; có thể khác lưu lượng tính cước proxy.",
    "vi": "Ước tính dung lượng nội dung HTTP, gồm kiểm tra proxy và các lần thử lại được đo. Không gồm header, TCP/TLS; có thể khác lưu lượng tính cước proxy.",
    "en": "Estimated HTTP content size, including measured proxy checks and retries. Excludes headers, TCP and TLS; may differ from billed proxy traffic.",
    "zh": "估算HTTP内容大小，包含已测量的代理检查和重试，不含请求头、TCP和TLS，可能与代理计费流量不同。"
  },
  {
    "source": "Lưu lượng ước tính",
    "vi": "Lưu lượng ước tính",
    "en": "Estimated traffic",
    "zh": "估算流量"
  },
  {
    "source": "Workspace",
    "vi": "Không gian làm việc",
    "en": "Workspace",
    "zh": "工作区"
  },
  {
    "source": "Thiết lập dùng chung cho các tác vụ trong workspace.",
    "vi": "Thiết lập dùng chung cho các tác vụ trong không gian làm việc.",
    "en": "Shared settings for workspace tasks.",
    "zh": "工作区任务的通用设置。"
  },
  {
    "source": "Nhóm cài đặt",
    "vi": "Nhóm cài đặt",
    "en": "Settings sections",
    "zh": "设置分类"
  },
  {
    "source": "Môi trường",
    "vi": "Môi trường",
    "en": "Environment",
    "zh": "环境"
  },
  {
    "source": "注册完成: {0}",
    "vi": "Đăng ký hoàn tất: {0}",
    "en": "Registration complete: {0}",
    "zh": "注册完成：{0}"
  },
  {
    "source": "· 0元试用={0}",
    "vi": "· Dùng thử miễn phí={0}",
    "en": "· Free trial={0}",
    "zh": "· 免费试用={0}"
  },
  {
    "source": "[auto] 开始注册 {0} (run={1})",
    "vi": "[auto] Bắt đầu đăng ký {0} (run={1})",
    "en": "[auto] Start registering {0} (run={1})",
    "zh": "[auto] 开始注册{0}（run={1}）"
  },
  {
    "source": "[auto] {0} {1} 完成",
    "vi": "[auto] {0} {1} hoàn tất",
    "en": "[auto] {0} {1} completed",
    "zh": "[auto] {0} {1} 完成"
  },
  {
    "source": "[auto] 熔断: {0}",
    "vi": "[auto] Ngắt mạch: {0}",
    "en": "[auto] Circuit break: {0}",
    "zh": "[auto] 熔断：{0}"
  },
  {
    "source": "Chưa cập nhật được đầy đủ trạng thái tác vụ.",
    "vi": "Chưa cập nhật được đầy đủ trạng thái tác vụ.",
    "en": "Could not update all task states.",
    "zh": "无法更新完整任务状态。"
  },
  {
    "source": "Chưa xác nhận được lệnh dừng. Hệ thống đang tự gửi lại; tác vụ có thể vẫn chạy.",
    "vi": "Chưa xác nhận được lệnh dừng. Hệ thống đang tự gửi lại; tác vụ có thể vẫn chạy.",
    "en": "Stop request not confirmed. Retrying automatically; the task may still be running.",
    "zh": "停止请求尚未确认，正在自动重试；任务可能仍在运行。"
  },
  {
    "source": "Chưa xác nhận được lệnh dừng. Hệ thống sẽ gửi lại khi có kết nối; tác vụ có thể vẫn chạy.",
    "vi": "Chưa xác nhận được lệnh dừng. Hệ thống sẽ gửi lại khi có kết nối; tác vụ có thể vẫn chạy.",
    "en": "Stop request not confirmed. Will retry when connected; the task may still be running.",
    "zh": "停止请求尚未确认，连接恢复后将重试；任务可能仍在运行。"
  },
  {
    "source": "Chưa kết nối được để lấy tiến độ. Tác vụ trên máy chủ vẫn tiếp tục; hệ thống sẽ tự kết nối lại.",
    "vi": "Chưa kết nối được để lấy tiến độ. Tác vụ trên máy chủ vẫn tiếp tục; hệ thống sẽ tự kết nối lại.",
    "en": "Could not connect to retrieve progress. The server task continues; reconnecting automatically.",
    "zh": "无法连接以获取进度。服务器任务仍在继续，系统将自动重连。"
  },
  {
    "source": "Chưa lấy được trạng thái làm mới token. Có thể tải lại tiến độ khi kết nối ổn định.",
    "vi": "Chưa lấy được trạng thái làm mới token. Có thể tải lại tiến độ khi kết nối ổn định.",
    "en": "Could not retrieve token refresh status. Reload progress when the connection is stable.",
    "zh": "无法获取令牌刷新状态，连接稳定后可重新加载进度。"
  },
  {
    "source": "Đang xác nhận lệnh dừng. Hãy chờ xác nhận trước khi đổi tác vụ.",
    "vi": "Đang xác nhận lệnh dừng. Hãy chờ xác nhận trước khi đổi tác vụ.",
    "en": "Confirming stop request. Wait for confirmation before switching tasks.",
    "zh": "正在确认停止请求，请等待确认后再切换任务。"
  },
  {
    "source": "Khóa 2FA không hợp lệ",
    "vi": "Khóa 2FA không hợp lệ",
    "en": "Invalid 2FA secret",
    "zh": "2FA密钥无效"
  },
  {
    "source": "Khóa 2FA quá ngắn",
    "vi": "Khóa 2FA quá ngắn",
    "en": "2FA secret is too short",
    "zh": "2FA密钥过短"
  },
  {
    "source": "Cần HTTPS để tạo OTP",
    "vi": "Cần HTTPS để tạo OTP",
    "en": "HTTPS is required to generate OTP",
    "zh": "生成验证码需要HTTPS"
  },
  {
    "source": "Thời gian OTP không hợp lệ",
    "vi": "Thời gian OTP không hợp lệ",
    "en": "Invalid OTP time",
    "zh": "验证码时间无效"
  },
  {
    "source": "ĐĂNG KÝ",
    "vi": "ĐĂNG KÝ",
    "en": "REGISTRATION",
    "zh": "注册"
  },
  {
    "source": "Đăng ký hàng loạt",
    "vi": "Đăng ký hàng loạt",
    "en": "Batch registration",
    "zh": "批量注册"
  },
  {
    "source": "Thiết lập đợt chạy và thư mục lưu tài khoản.",
    "vi": "Thiết lập đợt chạy và thư mục lưu tài khoản.",
    "en": "Configure the batch and the destination account folder.",
    "zh": "设置本批次及账号目标文件夹。"
  },
  {
    "source": "Số worker đăng ký",
    "vi": "Số worker đăng ký",
    "en": "Registration workers",
    "zh": "注册工作线程"
  },
  {
    "source": "1–20 · Trình duyệt dùng nhiều RAM, nên bắt đầu với 5 luồng.",
    "vi": "1–20 · Trình duyệt dùng nhiều RAM, nên bắt đầu với 5 luồng.",
    "en": "1–20 · Browsers use more RAM; start with 5 workers.",
    "zh": "1–20 · 浏览器模式占用较多内存，建议从5个线程开始。"
  },
  {
    "source": "1–100 · Tăng dần theo khả năng proxy và VPS.",
    "vi": "1–100 · Tăng dần theo khả năng proxy và VPS.",
    "en": "1–100 · Increase gradually based on proxy and VPS capacity.",
    "zh": "1–100 · 根据代理和VPS性能逐步增加。"
  },
  {
    "source": "Mục tiêu · 0 = không giới hạn",
    "vi": "Mục tiêu · 0 = không giới hạn",
    "en": "Target · 0 = unlimited",
    "zh": "目标数 · 0表示不限"
  },
  {
    "source": "Tất cả nhóm",
    "vi": "Tất cả nhóm",
    "en": "All groups",
    "zh": "所有分组"
  },
  {
    "source": "Chưa phân nhóm",
    "vi": "Chưa phân nhóm",
    "en": "Ungrouped",
    "zh": "未分组"
  },
  {
    "source": "Kế thừa nhóm nguồn",
    "vi": "Kế thừa nhóm nguồn",
    "en": "Inherit source group",
    "zh": "继承来源分组"
  },
  {
    "source": "Chế độ trình duyệt dùng nhiều RAM. Nên chạy tối đa 5 luồng.",
    "vi": "Chế độ trình duyệt dùng nhiều RAM. Nên chạy tối đa 5 luồng.",
    "en": "Browser mode uses more RAM. Up to 5 workers is recommended.",
    "zh": "浏览器模式占用较多内存，建议最多运行5个线程。"
  },
  {
    "source": "Tự động gắn TOTP",
    "vi": "Tự động gắn TOTP",
    "en": "Automatically bind TOTP",
    "zh": "自动绑定TOTP"
  },
  {
    "source": "Refresh token",
    "vi": "Token làm mới",
    "en": "Refresh token",
    "zh": "刷新令牌"
  },
  {
    "source": "ReMail · Tự động bổ sung mail",
    "vi": "ReMail · Tự động bổ sung mail",
    "en": "ReMail · Automatic mail restocking",
    "zh": "ReMail · 自动补充邮箱"
  },
  {
    "source": "Tự mua: Bật",
    "vi": "Tự mua: Bật",
    "en": "Auto-purchase: On",
    "zh": "自动购买：开启"
  },
  {
    "source": "Tự mua: Tắt",
    "vi": "Tự mua: Tắt",
    "en": "Auto-purchase: Off",
    "zh": "自动购买：关闭"
  },
  {
    "source": "Số lượng mỗi đợt",
    "vi": "Số lượng mỗi đợt",
    "en": "Quantity per batch",
    "zh": "每批数量"
  },
  {
    "source": "Bổ sung khi còn ít hơn",
    "vi": "Bổ sung khi còn ít hơn",
    "en": "Restock below",
    "zh": "低于此数量时补货"
  },
  {
    "source": "Tự động mua",
    "vi": "Tự động mua",
    "en": "Auto-purchase",
    "zh": "自动购买"
  },
  {
    "source": "Bật sẽ tự trừ số dư khi bổ sung.",
    "vi": "Bật sẽ tự trừ số dư khi bổ sung.",
    "en": "Enabling this deducts your balance when restocking.",
    "zh": "开启后，补货时将自动扣除余额。"
  },
  {
    "source": "Số dư:",
    "vi": "Số dư:",
    "en": "Balance:",
    "zh": "余额："
  },
  {
    "source": "· Khả dụng:",
    "vi": "· Khả dụng:",
    "en": "· Available:",
    "zh": "· 可用："
  },
  {
    "source": "· Đơn dùng được:",
    "vi": "· Đơn dùng được:",
    "en": "· Usable orders:",
    "zh": "· 可用订单："
  },
  {
    "source": "Nhập đơn đã mua",
    "vi": "Nhập đơn đã mua",
    "en": "Import purchased order",
    "zh": "导入已购订单"
  },
  {
    "source": "Mua bổ sung · trừ số dư",
    "vi": "Mua bổ sung · trừ số dư",
    "en": "Purchase restock · Deducts balance",
    "zh": "购买补货 · 将扣除余额"
  },
  {
    "source": "Mail đã mua cần sử dụng trong thời hạn nhận thư của nhà cung cấp.",
    "vi": "Mail đã mua cần sử dụng trong thời hạn nhận thư của nhà cung cấp.",
    "en": "Purchased mailboxes must be used within the provider's receiving window.",
    "zh": "已购买的邮箱须在供应商规定的收信期限内使用。"
  },
  {
    "source": "补货完成：买入 {0} 个，可用 {1}",
    "vi": "Bổ sung hoàn tất: Mua {0}, khả dụng {1}",
    "en": "Restock complete: Bought {0}, available {1}",
    "zh": "补货完成：买入{0}个，可用{1}"
  },
  {
    "source": "已购订单导入：新增 {0} 个，可用 {1}",
    "vi": "Đã nhập đơn mua: Thêm {0}, khả dụng {1}",
    "en": "Purchased order imported: Added {0}, available {1}",
    "zh": "已购订单导入：新增{0}个，可用{1}"
  },
  {
    "source": "WORKSPACE",
    "vi": "KHÔNG GIAN LÀM VIỆC",
    "en": "WORKSPACE",
    "zh": "工作区"
  },
  {
    "source": "Chưa tải được số liệu tài khoản.",
    "vi": "Chưa tải được số liệu tài khoản.",
    "en": "Could not load account statistics.",
    "zh": "无法加载账号统计。"
  },
  {
    "source": "Tổng tài khoản",
    "vi": "Tổng tài khoản",
    "en": "Total accounts",
    "zh": "账号总数"
  },
  {
    "source": "Có lỗi cần xem",
    "vi": "Có lỗi cần xem",
    "en": "Errors to review",
    "zh": "待查看错误"
  },
  {
    "source": "Gói trả phí đã xác minh",
    "vi": "Gói trả phí đã xác minh",
    "en": "Verified paid plans",
    "zh": "已验证的付费套餐"
  },
  {
    "source": "Tác vụ tài khoản đang chạy",
    "vi": "Tác vụ tài khoản đang chạy",
    "en": "Active account tasks",
    "zh": "正在运行的账号任务"
  },
  {
    "source": "Hướng dẫn và yêu cầu token",
    "vi": "Hướng dẫn và yêu cầu token",
    "en": "Instructions and token requirements",
    "zh": "说明与令牌要求"
  },
  {
    "source": "启用 CPA 自动导出",
    "vi": "Bật tự động xuất CPA",
    "en": "Enable CPA auto-export",
    "zh": "启用CPA自动导出"
  },
  {
    "source": "启用 SUB2API 自动导出",
    "vi": "Bật tự động xuất SUB2API",
    "en": "Enable SUB2API auto-export",
    "zh": "启用SUB2API自动导出"
  },
  {
    "source": "TÀI NGUYÊN",
    "vi": "TÀI NGUYÊN",
    "en": "RESOURCES",
    "zh": "资源"
  },
  {
    "source": "Nhập kho mail",
    "vi": "Nhập kho mail",
    "en": "Import to mail pool",
    "zh": "导入邮箱池"
  },
  {
    "source": "Thêm nguồn mail để dùng cho các đợt đăng ký.",
    "vi": "Thêm nguồn mail để dùng cho các đợt đăng ký.",
    "en": "Add mail sources for registration batches.",
    "zh": "添加用于批量注册的邮箱来源。"
  },
  {
    "source": "Về kho mail ↗",
    "vi": "Về kho mail ↗",
    "en": "Back to mail pool ↗",
    "zh": "返回邮箱池 ↗"
  },
  {
    "source": "Nguồn Email",
    "vi": "Nguồn Email",
    "en": "Email source",
    "zh": "邮箱来源"
  },
  {
    "source": "đoạn",
    "vi": "đoạn",
    "en": "parts",
    "zh": "段"
  },
  {
    "source": "Chọn nguồn email",
    "vi": "Chọn nguồn email",
    "en": "Select email source",
    "zh": "选择邮箱来源"
  },
  {
    "source": "Nhóm · tùy chọn",
    "vi": "Nhóm · tùy chọn",
    "en": "Group · optional",
    "zh": "分组 · 可选"
  },
  {
    "source": "Đang chọn:",
    "vi": "Đang chọn:",
    "en": "Selected:",
    "zh": "当前选择："
  },
  {
    "source": "Chọn nhóm có sẵn hoặc gõ tên nhóm mới...",
    "vi": "Chọn nhóm có sẵn hoặc gõ tên nhóm mới...",
    "en": "Select an existing group or type a new name...",
    "zh": "选择已有分组或输入新分组名称…"
  },
  {
    "source": "Định dạng (ngăn cách bằng",
    "vi": "Định dạng (ngăn cách bằng",
    "en": "Format (separated by",
    "zh": "格式（分隔符为"
  },
  {
    "source": "Dán clipboard",
    "vi": "Dán clipboard",
    "en": "Paste clipboard",
    "zh": "粘贴剪贴板"
  },
  {
    "source": "Xóa sạch",
    "vi": "Xóa sạch",
    "en": "Clear all",
    "zh": "全部清空"
  },
  {
    "source": "Dán danh sách mail vào đây...",
    "vi": "Dán danh sách mail vào đây...",
    "en": "Paste the mail list here...",
    "zh": "在此粘贴邮箱列表…"
  },
  {
    "source": "Nhập vào kho",
    "vi": "Nhập vào kho",
    "en": "Import to pool",
    "zh": "导入邮箱池"
  },
  {
    "source": "Các dòng lỗi sau cần được chỉnh sửa trước khi nhập:",
    "vi": "Các dòng lỗi sau cần được chỉnh sửa trước khi nhập:",
    "en": "Fix these invalid lines before importing:",
    "zh": "导入前请修正以下错误行："
  },
  {
    "source": "Dòng",
    "vi": "Dòng",
    "en": "Line",
    "zh": "行"
  },
  {
    "source": "Đã dán từ clipboard",
    "vi": "Đã dán từ clipboard",
    "en": "Pasted from clipboard",
    "zh": "已从剪贴板粘贴"
  },
  {
    "source": "Không thể đọc clipboard tự động, vui lòng nhấn Ctrl+V / Command+V",
    "vi": "Không thể đọc clipboard tự động, vui lòng nhấn Ctrl+V / Command+V",
    "en": "Cannot read clipboard automatically. Press Ctrl+V / Command+V.",
    "zh": "无法自动读取剪贴板，请按Ctrl+V／Command+V。"
  },
  {
    "source": "Vui lòng nhập danh sách mail",
    "vi": "Vui lòng nhập danh sách mail",
    "en": "Enter a mail list",
    "zh": "请输入邮箱列表"
  },
  {
    "source": "Vui lòng chọn nguồn email",
    "vi": "Vui lòng chọn nguồn email",
    "en": "Select an email source",
    "zh": "请选择邮箱来源"
  },
  {
    "source": "Phân tích {0} dòng: Thêm mới {1}, Cập nhật {2}, Bỏ qua {3}",
    "vi": "Phân tích {0} dòng: Thêm mới {1}, Cập nhật {2}, Bỏ qua {3}",
    "en": "Parsed {0} lines: Added {1}, updated {2}, skipped {3}",
    "zh": "解析{0}行：新增{1}，更新{2}，跳过{3}"
  },
  {
    "source": "· Đã gán vào nhóm [{0}]",
    "vi": "· Đã gán vào nhóm [{0}]",
    "en": "· Assigned to group [{0}]",
    "zh": "· 已分配到分组[{0}]"
  },
  {
    "source": "Nhập email vào kho thành công!",
    "vi": "Nhập email vào kho thành công!",
    "en": "Mail imported successfully!",
    "zh": "邮箱导入成功！"
  },
  {
    "source": "Có {0} dòng không hợp lệ, toàn bộ đợt nhập đã bị từ chối.",
    "vi": "Có {0} dòng không hợp lệ, toàn bộ đợt nhập đã bị từ chối.",
    "en": "{0} lines are invalid. The entire import was rejected.",
    "zh": "有{0}行无效，本次导入已全部拒绝。"
  },
  {
    "source": "Định dạng không hợp lệ, vui lòng kiểm tra lại",
    "vi": "Định dạng không hợp lệ, vui lòng kiểm tra lại",
    "en": "Invalid format. Please check the input.",
    "zh": "格式无效，请检查输入。"
  },
  {
    "source": "Lỗi nhập:",
    "vi": "Lỗi nhập:",
    "en": "Import error:",
    "zh": "导入错误："
  },
  {
    "source": "导入格式",
    "vi": "Định dạng nhập",
    "en": "Import format",
    "zh": "导入格式"
  },
  {
    "source": "段",
    "vi": "đoạn",
    "en": "parts",
    "zh": "段"
  },
  {
    "source": "{0} 不需要在这里配置，去「导入邮箱」页把号导进来即可。",
    "vi": "{0} không cần cấu hình ở đây. Hãy nhập tài khoản ở trang Nhập mail.",
    "en": "{0} needs no configuration here. Import its accounts on the Import Mail page.",
    "zh": "{0}无需在此配置，请前往导入邮箱页面导入账号。",
    "translateSlots": [
      0
    ]
  },
  {
    "source": "邮箱来源：",
    "vi": "Nguồn email:",
    "en": "Email source:",
    "zh": "邮箱来源："
  },
  {
    "source": "Quản lý nguồn mail và trạng thái sử dụng.",
    "vi": "Quản lý nguồn mail và trạng thái sử dụng.",
    "en": "Manage mail sources and usage status.",
    "zh": "管理邮箱来源及使用状态。"
  },
  {
    "source": "Nhập mail",
    "vi": "Nhập mail",
    "en": "Import mail",
    "zh": "导入邮箱"
  },
  {
    "source": "Tất cả nhóm mail",
    "vi": "Tất cả nhóm mail",
    "en": "All mail groups",
    "zh": "所有邮箱分组"
  },
  {
    "source": "Quản lý hàng loạt ·",
    "vi": "Quản lý hàng loạt ·",
    "en": "Bulk actions ·",
    "zh": "批量操作 ·"
  },
  {
    "source": "đã chọn",
    "vi": "đã chọn",
    "en": "selected",
    "zh": "已选"
  },
  {
    "source": "重置选中 (",
    "vi": "Đặt lại đã chọn (",
    "en": "Reset selected (",
    "zh": "重置选中（"
  },
  {
    "source": "删除选中 (",
    "vi": "Xóa đã chọn (",
    "en": "Delete selected (",
    "zh": "删除选中（"
  },
  {
    "source": "（搜索：",
    "vi": "(Tìm kiếm:",
    "en": "(Search:",
    "zh": "（搜索："
  },
  {
    "source": "，已选",
    "vi": ", đã chọn",
    "en": ", selected",
    "zh": "，已选"
  },
  {
    "source": "分组",
    "vi": "Nhóm",
    "en": "Group",
    "zh": "分组"
  },
  {
    "source": "{0}为空",
    "vi": "{0} trống",
    "en": "{0} is empty",
    "zh": "{0}为空",
    "translateSlots": [
      0
    ]
  },
  {
    "source": "已复制{0}",
    "vi": "Đã sao chép {0}",
    "en": "Copied {0}",
    "zh": "已复制{0}"
  },
  {
    "source": "重置 {0} 个",
    "vi": "Đặt lại {0} tài khoản",
    "en": "Reset {0} accounts",
    "zh": "重置{0}个"
  },
  {
    "source": "释放 {0} 个卡死号",
    "vi": "Đã giải phóng {0} tài khoản bị kẹt",
    "en": "Released {0} stuck accounts",
    "zh": "释放{0}个卡死号"
  },
  {
    "source": "重置选中的 {0} 个号为 available？（已保存凭证不变）",
    "vi": "Đặt lại {0} tài khoản đã chọn về khả dụng? Thông tin đã lưu được giữ nguyên.",
    "en": "Reset {0} selected accounts to available? Saved credentials are unchanged.",
    "zh": "重置选中的{0}个号为可用？已保存凭证不变。"
  },
  {
    "source": "已重置 {0} 个",
    "vi": "Đã đặt lại {0} tài khoản",
    "en": "Reset {0} accounts",
    "zh": "已重置{0}个"
  },
  {
    "source": "确定删除选中的 {0} 个号？(不可恢复)",
    "vi": "Xóa {0} tài khoản đã chọn? Không thể hoàn tác.",
    "en": "Delete {0} selected accounts? This cannot be undone.",
    "zh": "确定删除选中的{0}个账号？此操作不可恢复。"
  },
  {
    "source": "已删除 {0} 个",
    "vi": "Đã xóa {0} tài khoản",
    "en": "Deleted {0} accounts",
    "zh": "已删除{0}个"
  },
  {
    "source": "确定删除全部 {0} 状态的号？",
    "vi": "Xóa tất cả tài khoản có trạng thái {0}?",
    "en": "Delete all accounts with status {0}?",
    "zh": "确定删除全部{0}状态的账号？"
  },
  {
    "source": "已删除 {0} 个 {1} 号",
    "vi": "Đã xóa {0} tài khoản có trạng thái {1}",
    "en": "Deleted {0} accounts with status {1}",
    "zh": "已删除{0}个{1}状态的账号"
  },
  {
    "source": "重置 {0} 为 available？",
    "vi": "Đặt lại {0} về khả dụng?",
    "en": "Reset {0} to available?",
    "zh": "将{0}重置为可用？"
  },
  {
    "source": "删除 {0}？",
    "vi": "Xóa {0}?",
    "en": "Delete {0}?",
    "zh": "删除{0}？"
  },
  {
    "source": "Kho proxy",
    "vi": "Kho proxy",
    "en": "Proxy pool",
    "zh": "代理池"
  },
  {
    "source": "Quản lý kết nối dùng cho đăng ký và tác vụ tài khoản.",
    "vi": "Quản lý kết nối dùng cho đăng ký và tác vụ tài khoản.",
    "en": "Manage connections for registration and account tasks.",
    "zh": "管理注册和账号任务使用的连接。"
  },
  {
    "source": "Định dạng proxy",
    "vi": "Định dạng proxy",
    "en": "Proxy format",
    "zh": "代理格式"
  },
  {
    "source": "[协议://][user:pass@]host:port",
    "vi": "[giao thức://][user:pass@]host:port",
    "en": "[protocol://][user:pass@]host:port",
    "zh": "[协议://][用户:密码@]主机:端口"
  },
  {
    "source": "不写协议默认按",
    "vi": "Không ghi giao thức sẽ mặc định dùng",
    "en": "If no protocol is specified, defaults to",
    "zh": "未填写协议时默认使用"
  },
  {
    "source": "Thêm vào kho",
    "vi": "Thêm vào kho",
    "en": "Add to pool",
    "zh": "添加到代理池"
  },
  {
    "source": "Thay toàn bộ kho…",
    "vi": "Thay toàn bộ kho…",
    "en": "Replace entire pool…",
    "zh": "替换整个代理池…"
  },
  {
    "source": "Sửa danh sách hiện tại",
    "vi": "Sửa danh sách hiện tại",
    "en": "Edit current list",
    "zh": "编辑当前列表"
  },
  {
    "source": "Danh sách proxy ·",
    "vi": "Danh sách proxy ·",
    "en": "Proxy list ·",
    "zh": "代理列表 ·"
  },
  {
    "source": "sai định dạng",
    "vi": "sai định dạng",
    "en": "invalid format",
    "zh": "格式错误"
  },
  {
    "source": "Proxy được lưu để chọn trong các tác vụ. Bấm Kiểm tra khi cần xác nhận kết nối.",
    "vi": "Proxy được lưu để chọn trong các tác vụ. Bấm Kiểm tra khi cần xác nhận kết nối.",
    "en": "Proxies are saved for use in tasks. Click Check when you need to verify the connection.",
    "zh": "代理将保存供任务选择。需要验证连接时，请点击检查。"
  },
  {
    "source": "代理池有 {0} 个，单次最多测 {1} 个（每批 20 并发）。只测前 {2} 个？",
    "vi": "Kho có {0} proxy, mỗi lần kiểm tra tối đa {1} (20 luồng). Kiểm tra {2} proxy đầu?",
    "en": "The pool has {0} proxies. Each test supports {1} (20 concurrent). Test the first {2}?",
    "zh": "代理池有{0}个，单次最多测{1}个（每批20并发）。只测前{2}个？"
  },
  {
    "source": "测试前 {0}",
    "vi": "Kiểm tra {0} proxy đầu",
    "en": "Test first {0}",
    "zh": "测试前{0}个"
  },
  {
    "source": "已从服务端同步（{0} 个）",
    "vi": "Đã đồng bộ từ máy chủ ({0} proxy)",
    "en": "Synced from server ({0} proxies)",
    "zh": "已从服务端同步（{0}个）"
  },
  {
    "source": "Thay toàn bộ {0} proxy hiện tại bằng danh sách vừa nhập?",
    "vi": "Thay toàn bộ {0} proxy hiện tại bằng danh sách vừa nhập?",
    "en": "Replace all {0} existing proxies with the entered list?",
    "zh": "用输入的列表替换现有的全部{0}个代理？"
  },
  {
    "source": "Thay kho proxy",
    "vi": "Thay kho proxy",
    "en": "Replace proxy pool",
    "zh": "替换代理池"
  },
  {
    "source": "Thay danh sách",
    "vi": "Thay danh sách",
    "en": "Replace list",
    "zh": "替换列表"
  },
  {
    "source": "Hủy",
    "vi": "Hủy",
    "en": "Cancel",
    "zh": "取消"
  },
  {
    "source": "已保存 {0} 个代理{1}",
    "vi": "Đã lưu {0} proxy{1}",
    "en": "Saved {0} proxies{1}",
    "zh": "已保存{0}个代理{1}"
  },
  {
    "source": "（去重 {0} 个）",
    "vi": "(Đã bỏ {0} mục trùng)",
    "en": "({0} duplicates removed)",
    "zh": "（已去重{0}个）"
  },
  {
    "source": "已追加 {0} 个新代理",
    "vi": "Đã thêm {0} proxy mới",
    "en": "Added {0} new proxies",
    "zh": "已追加{0}个新代理"
  },
  {
    "source": "确定清空全部 {0} 个代理？",
    "vi": "Xóa toàn bộ {0} proxy?",
    "en": "Clear all {0} proxies?",
    "zh": "确定清空全部{0}个代理？"
  },
  {
    "source": "Tạo tài khoản, lưu thông tin và xác minh gói sau đăng ký.",
    "vi": "Tạo tài khoản, lưu thông tin và xác minh gói sau đăng ký.",
    "en": "Create accounts, save credentials and verify plans after registration.",
    "zh": "创建账号、保存凭证并在注册后验证套餐。"
  },
  {
    "source": "Bật 2FA: hãy xuất và giữ mã bí mật để đăng nhập sau này.",
    "vi": "Bật 2FA: hãy xuất và giữ mã bí mật để đăng nhập sau này.",
    "en": "When 2FA is enabled, export and keep the secret for future logins.",
    "zh": "启用2FA后，请导出并保管密钥，以便后续登录。"
  },
  {
    "source": "注册完成",
    "vi": "Đăng ký hoàn tất",
    "en": "Registration complete",
    "zh": "注册完成"
  },
  {
    "source": "[client] 启动注册 run_id={0} email={1}",
    "vi": "[client] Bắt đầu đăng ký run_id={0} email={1}",
    "en": "[client] Registration started run_id={0} email={1}",
    "zh": "[client] 开始注册 run_id={0} email={1}"
  },
  {
    "source": "{0} 为空",
    "vi": "{0} trống",
    "en": "{0} is empty",
    "zh": "{0}为空",
    "translateSlots": [
      0
    ]
  },
  {
    "source": "Tìm kiếm, phân nhóm và quản lý tài khoản.",
    "vi": "Tìm kiếm, phân nhóm và quản lý tài khoản.",
    "en": "Search, organize and manage accounts.",
    "zh": "搜索、分类和管理账号。"
  },
  {
    "source": "Tải danh sách",
    "vi": "Tải danh sách",
    "en": "Reload list",
    "zh": "重新加载列表"
  },
  {
    "source": "Trạng thái Access Token",
    "vi": "Trạng thái Access Token",
    "en": "Access Token status",
    "zh": "Access Token状态"
  },
  {
    "source": "Đã kiểm tra:",
    "vi": "Đã kiểm tra:",
    "en": "Checked:",
    "zh": "已检查："
  },
  {
    "source": "Kiểm tra AT…",
    "vi": "Kiểm tra AT…",
    "en": "Check AT…",
    "zh": "检查AT…"
  },
  {
    "source": "Làm mới AT…",
    "vi": "Làm mới AT…",
    "en": "Refresh AT…",
    "zh": "刷新AT…"
  },
  {
    "source": "Phạm vi tài khoản",
    "vi": "Phạm vi tài khoản",
    "en": "Account scope",
    "zh": "账号范围"
  },
  {
    "source": "Tài khoản này",
    "vi": "Tài khoản này",
    "en": "This account",
    "zh": "此账号"
  },
  {
    "source": "Giữ lựa chọn qua các trang",
    "vi": "Giữ lựa chọn qua các trang",
    "en": "Keep selection across pages",
    "zh": "跨页保留选择"
  },
  {
    "source": "Toàn bộ kết quả lọc",
    "vi": "Toàn bộ kết quả lọc",
    "en": "All filtered results",
    "zh": "全部筛选结果"
  },
  {
    "source": "Bao gồm tất cả các trang",
    "vi": "Bao gồm tất cả các trang",
    "en": "Includes all pages",
    "zh": "包含所有页面"
  },
  {
    "source": "Trang hiện tại",
    "vi": "Trang hiện tại",
    "en": "Current page",
    "zh": "当前页"
  },
  {
    "source": "Chỉ các tài khoản đang hiển thị",
    "vi": "Chỉ các tài khoản đang hiển thị",
    "en": "Only accounts currently displayed",
    "zh": "仅当前显示的账号"
  },
  {
    "source": "Proxy tác vụ token",
    "vi": "Proxy tác vụ token",
    "en": "Token task proxy",
    "zh": "令牌任务代理"
  },
  {
    "source": "Tự động từ Kho Proxy ({0})",
    "vi": "Tự động từ Kho Proxy ({0})",
    "en": "Automatic from proxy pool ({0})",
    "zh": "自动使用代理池（{0}）"
  },
  {
    "source": "Dùng proxy riêng",
    "vi": "Dùng proxy riêng",
    "en": "Use custom proxy",
    "zh": "使用自定义代理"
  },
  {
    "source": "Trực tiếp từ VPS",
    "vi": "Trực tiếp từ VPS",
    "en": "Direct from VPS",
    "zh": "VPS直连"
  },
  {
    "source": "Chọn hoặc nhập proxy",
    "vi": "Chọn hoặc nhập proxy",
    "en": "Select or enter a proxy",
    "zh": "选择或输入代理"
  },
  {
    "source": "Số worker đồng thời",
    "vi": "Số worker đồng thời",
    "en": "Concurrent workers",
    "zh": "并发工作线程"
  },
  {
    "source": "1–100 · Lưu riêng cho từng tác vụ",
    "vi": "1–100 · Lưu riêng cho từng tác vụ",
    "en": "1–100 · Saved separately for each task",
    "zh": "1–100 · 每种任务分别保存"
  },
  {
    "source": "Dùng Kho Proxy để chạy song song; mỗi tài khoản giữ riêng một proxy trong suốt lượt xử lý. Proxy riêng/trực tiếp chạy 1 worker.",
    "vi": "Dùng Kho Proxy để chạy song song; mỗi tài khoản giữ riêng một proxy trong suốt lượt xử lý. Proxy riêng/trực tiếp chạy 1 worker.",
    "en": "Use the proxy pool for parallel processing. Each account keeps its proxy throughout the attempt. Custom proxy / direct mode uses one worker.",
    "zh": "使用代理池可并行处理，每个账号在整个处理过程中保持同一代理。自定义代理／直连模式使用一个线程。"
  },
  {
    "source": "Worker thực tế không vượt mức đồng thời trong cấu hình checkout.",
    "vi": "Worker thực tế không vượt mức đồng thời trong cấu hình checkout.",
    "en": "Actual workers cannot exceed checkout concurrency settings.",
    "zh": "实际线程数不会超过结账配置中的并发上限。"
  },
  {
    "source": "Số worker được giới hạn theo số tài khoản trong đợt.",
    "vi": "Số worker được giới hạn theo số tài khoản trong đợt.",
    "en": "Workers are limited to the number of accounts in the batch.",
    "zh": "工作线程数不会超过本批次账号数量。"
  },
  {
    "source": "Tự lọc acc cần AT hoặc còn khả năng thử lại; bỏ acc đã có AT dùng được, bị khóa, sai TK/MK/2FA hoặc đang chờ xử lý mail OTP.",
    "vi": "Tự lọc acc cần AT hoặc còn khả năng thử lại; bỏ acc đã có AT dùng được, bị khóa, sai TK/MK/2FA hoặc đang chờ xử lý mail OTP.",
    "en": "Select accounts needing AT or eligible for retry. Skip usable AT, blocked accounts, incorrect credentials / 2FA and email OTP holds.",
    "zh": "自动筛选需要AT或可重试的账号，跳过AT可用、已封禁、账号密码／2FA错误及等待邮箱验证码处理的账号。"
  },
  {
    "source": "Bỏ qua AT còn hạn hoặc đã kiểm tra dùng được",
    "vi": "Bỏ qua AT còn hạn hoặc đã kiểm tra dùng được",
    "en": "Skip unexpired or verified usable AT",
    "zh": "跳过未过期或已验证可用的AT"
  },
  {
    "source": "Dùng hạn JWT và kết quả đã lưu; không gọi proxy cho AT được bỏ qua. Kết quả 401/khóa đã biết vẫn được ưu tiên.",
    "vi": "Dùng hạn JWT và kết quả đã lưu; không gọi proxy cho AT được bỏ qua. Kết quả 401/khóa đã biết vẫn được ưu tiên.",
    "en": "Uses JWT expiry and saved results; no proxy calls for skipped AT. Known 401 / blocked results take priority.",
    "zh": "使用JWT到期时间和已保存结果，跳过的AT不会调用代理。已知401／封禁结果优先。"
  },
  {
    "source": "Quét API lại các AT chưa hết hạn. AT hết hạn hoặc chưa có token vẫn được phân loại tại VPS.",
    "vi": "Quét API lại các AT chưa hết hạn. AT hết hạn hoặc chưa có token vẫn được phân loại tại VPS.",
    "en": "Recheck unexpired AT through the API. Expired or missing tokens are still classified on the VPS.",
    "zh": "通过API复查未过期AT，已过期或缺失的令牌仍在VPS上分类。"
  },
  {
    "source": "Token hết hạn theo JWT hoặc chưa có AT được phân loại tại VPS, không cần gọi mạng.",
    "vi": "Token hết hạn theo JWT hoặc chưa có AT được phân loại tại VPS, không cần gọi mạng.",
    "en": "JWT-expired or missing AT is classified on the VPS without network calls.",
    "zh": "JWT已过期或缺失的AT将在VPS上分类，无需网络请求。"
  },
  {
    "source": "Token hết hạn có thể được làm mới bằng luồng đăng nhập hiện có.",
    "vi": "Token hết hạn có thể được làm mới bằng luồng đăng nhập hiện có.",
    "en": "Expired tokens can be refreshed using the existing login flow.",
    "zh": "过期令牌可通过现有登录流程刷新。"
  },
  {
    "source": "Dò bằng cấu hình proxy checkout hiện có; tạo phiên để đọc giá, không xác nhận thanh toán.",
    "vi": "Dò bằng cấu hình proxy checkout hiện có; tạo phiên để đọc giá, không xác nhận thanh toán.",
    "en": "Uses existing checkout proxy settings to read prices; does not confirm payment.",
    "zh": "使用现有结账代理配置创建会话并读取价格，不确认付款。"
  },
  {
    "source": "Đang lọc tài khoản cần làm mới…",
    "vi": "Đang lọc tài khoản cần làm mới…",
    "en": "Finding accounts needing refresh…",
    "zh": "正在筛选需要刷新的账号…"
  },
  {
    "source": "có thể xử lý",
    "vi": "có thể xử lý",
    "en": "eligible",
    "zh": "个可处理"
  },
  {
    "source": "worker yêu cầu",
    "vi": "worker yêu cầu",
    "en": "workers requested",
    "zh": "个请求线程"
  },
  {
    "source": "Cần AT: chưa có",
    "vi": "Cần AT: chưa có",
    "en": "AT needed: missing",
    "zh": "需要AT：缺失"
  },
  {
    "source": "· Hết hạn/401",
    "vi": "· Hết hạn/401",
    "en": "· Expired / 401",
    "zh": "· 已过期／401"
  },
  {
    "source": "· Lỗi khác có thể thử lại",
    "vi": "· Lỗi khác có thể thử lại",
    "en": "· Other retryable errors",
    "zh": "· 其他可重试错误"
  },
  {
    "source": "Bỏ qua: AT dùng được",
    "vi": "Bỏ qua: AT dùng được",
    "en": "Skipped: usable AT",
    "zh": "跳过：AT可用"
  },
  {
    "source": "· Bị khóa",
    "vi": "· Bị khóa",
    "en": "· Blocked",
    "zh": "· 已封禁"
  },
  {
    "source": "· Chờ xử lý mail OTP",
    "vi": "· Chờ xử lý mail OTP",
    "en": "· Email OTP needs attention",
    "zh": "· 邮箱验证码待处理"
  },
  {
    "source": "· Chưa rõ hạn",
    "vi": "· Chưa rõ hạn",
    "en": "· Expiry unknown",
    "zh": "· 到期时间未知"
  },
  {
    "source": "Chạy trên VPS, có thể đóng tab hoặc dừng quét",
    "vi": "Chạy trên VPS, có thể đóng tab hoặc dừng quét",
    "en": "Runs on VPS; you may close the tab or stop the check",
    "zh": "在VPS上运行，可关闭标签页或停止检查"
  },
  {
    "source": "Lưu tiến độ và kết quả trên VPS",
    "vi": "Lưu tiến độ và kết quả trên VPS",
    "en": "Progress and results are saved on the VPS",
    "zh": "进度和结果保存在VPS上"
  },
  {
    "source": "Bắt đầu quét",
    "vi": "Bắt đầu quét",
    "en": "Start check",
    "zh": "开始检查"
  },
  {
    "source": "Bắt đầu làm mới",
    "vi": "Bắt đầu làm mới",
    "en": "Start refresh",
    "zh": "开始刷新"
  },
  {
    "source": "Danh sách tài khoản",
    "vi": "Danh sách tài khoản",
    "en": "Account list",
    "zh": "账号列表"
  },
  {
    "source": "Theo dõi ưu đãi",
    "vi": "Theo dõi ưu đãi",
    "en": "Track offers",
    "zh": "查看优惠"
  },
  {
    "source": "Đóng thiết lập",
    "vi": "Đóng thiết lập",
    "en": "Close settings",
    "zh": "关闭设置"
  },
  {
    "source": "Có ưu đãi 0đ",
    "vi": "Có ưu đãi 0đ",
    "en": "Free offer available",
    "zh": "有免费优惠"
  },
  {
    "source": "Đã dò",
    "vi": "Đã dò",
    "en": "Checked",
    "zh": "已检查"
  },
  {
    "source": "Chưa dò",
    "vi": "Chưa dò",
    "en": "Not checked",
    "zh": "未检查"
  },
  {
    "source": "Trong trang này",
    "vi": "Trong trang này",
    "en": "On this page",
    "zh": "在此页"
  },
  {
    "source": "Không hỗ trợ UPI:",
    "vi": "Không hỗ trợ UPI:",
    "en": "UPI unsupported:",
    "zh": "不支持UPI："
  },
  {
    "source": "· Lỗi:",
    "vi": "· Lỗi:",
    "en": "· Errors:",
    "zh": "· 错误："
  },
  {
    "source": "Tài khoản / Thư mục",
    "vi": "Tài khoản / Thư mục",
    "en": "Account / Folder",
    "zh": "账号／文件夹"
  },
  {
    "source": "Lọc nhóm tài khoản",
    "vi": "Lọc nhóm tài khoản",
    "en": "Filter account groups",
    "zh": "筛选账号分组"
  },
  {
    "source": "Sao chép email {0}",
    "vi": "Sao chép email {0}",
    "en": "Copy email {0}",
    "zh": "复制邮箱{0}"
  },
  {
    "source": "Bấm để sao chép email",
    "vi": "Bấm để sao chép email",
    "en": "Click to copy email",
    "zh": "点击复制邮箱"
  },
  {
    "source": "+ Nhóm",
    "vi": "+ Nhóm",
    "en": "+ Group",
    "zh": "+ 分组"
  },
  {
    "source": "Tạo nhóm mới & gán…",
    "vi": "Tạo nhóm mới & gán…",
    "en": "Create and assign a new group…",
    "zh": "新建分组并分配…"
  },
  {
    "source": "Bỏ khỏi nhóm",
    "vi": "Bỏ khỏi nhóm",
    "en": "Remove from group",
    "zh": "移出分组"
  },
  {
    "source": "IP xuất {0}{1} (Nhấp để lọc)",
    "vi": "IP xuất {0}{1} (Nhấp để lọc)",
    "en": "Exit IP {0}{1} (click to filter)",
    "zh": "出口IP {0}{1}（点击筛选）"
  },
  {
    "source": "Mã 2FA (Secret)",
    "vi": "Mã 2FA (Secret)",
    "en": "2FA secret",
    "zh": "2FA密钥"
  },
  {
    "source": "Sao chép 2FA",
    "vi": "Sao chép 2FA",
    "en": "Copy 2FA",
    "zh": "复制2FA"
  },
  {
    "source": "Gói tài khoản",
    "vi": "Gói tài khoản",
    "en": "Account plan",
    "zh": "账号套餐"
  },
  {
    "source": "Lọc gói tài khoản",
    "vi": "Lọc gói tài khoản",
    "en": "Filter account plans",
    "zh": "筛选账号套餐"
  },
  {
    "source": "Nguồn {0} · Trạng thái {1} · {2} · Phương thức {3} · Đơn vị {4} · Xuất {5}",
    "vi": "Nguồn {0} · Trạng thái {1} · {2} · Phương thức {3} · Đơn vị {4} · Xuất {5}",
    "en": "Source {0} · Status {1} · {2} · Method {3} · Provider {4} · Exit {5}",
    "zh": "来源{0} · 状态{1} · {2} · 方式{3} · 提供方{4} · 出口{5}"
  },
  {
    "source": "Token / Làm mới",
    "vi": "Token / Làm mới",
    "en": "Token / Refresh",
    "zh": "令牌／刷新"
  },
  {
    "source": "Lọc AT và lỗi",
    "vi": "Lọc AT và lỗi",
    "en": "Filter AT and errors",
    "zh": "筛选AT与错误"
  },
  {
    "source": "{0} · Nhấp để xem chi tiết",
    "vi": "{0} · Nhấp để xem chi tiết",
    "en": "{0} · Click for details",
    "zh": "{0} · 点击查看详情"
  },
  {
    "source": "Xem trạng thái AT của {0}",
    "vi": "Xem trạng thái AT của {0}",
    "en": "View AT status for {0}",
    "zh": "查看{0}的AT状态"
  },
  {
    "source": "{0} · {1}{2} · Nhấp để lọc",
    "vi": "{0} · {1}{2} · Nhấp để lọc",
    "en": "{0} · {1}{2} · Click to filter",
    "zh": "{0} · {1}{2} · 点击筛选"
  },
  {
    "source": "· Tạm dừng. Kiểm tra/bổ sung đường nhận mail, sau đó chọn Đã xử lý mail · cho phép thử lại.",
    "vi": "· Tạm dừng. Kiểm tra/bổ sung đường nhận mail, sau đó chọn Đã xử lý mail · cho phép thử lại.",
    "en": "· On hold. Check the email receiving method, then select Email resolved · allow retry.",
    "zh": "· 已暂停。检查并补充收信方式后，选择邮箱问题已解决 · 允许重试。"
  },
  {
    "source": "· Không tự thử lại; sửa thông tin hoặc chọn Cho phép thử lại.",
    "vi": "· Không tự thử lại; sửa thông tin hoặc chọn Cho phép thử lại.",
    "en": "· No automatic retry. Edit credentials or select Allow retry.",
    "zh": "· 不会自动重试，请修改凭证或选择允许重试。"
  },
  {
    "source": "Lỗi làm mới",
    "vi": "Lỗi làm mới",
    "en": "Refresh error",
    "zh": "刷新错误"
  },
  {
    "source": "Access Token",
    "vi": "Access Token",
    "en": "Access Token",
    "zh": "Access Token"
  },
  {
    "source": "Session Token",
    "vi": "Session Token",
    "en": "Session Token",
    "zh": "Session Token"
  },
  {
    "source": "Tổng đã dùng",
    "vi": "Tổng đã dùng",
    "en": "Total used",
    "zh": "累计用量"
  },
  {
    "source": "Lưu lượng cộng dồn",
    "vi": "Lưu lượng cộng dồn",
    "en": "Cumulative traffic",
    "zh": "累计流量"
  },
  {
    "source": "Cộng dồn các lượt đã đo, gồm lỗi và thử lại. Ước tính nội dung HTTP, chưa gồm header/TLS.",
    "vi": "Cộng dồn các lượt đã đo, gồm lỗi và thử lại. Ước tính nội dung HTTP, chưa gồm header/TLS.",
    "en": "Total of measured attempts, including errors and retries. Estimated HTTP content; excludes headers and TLS.",
    "zh": "累计所有已测量的尝试，包含错误和重试，按HTTP内容估算，不含请求头和TLS。"
  },
  {
    "source": "Các lượt cũ không còn số đo có thể bị thiếu.",
    "vi": "Các lượt cũ không còn số đo có thể bị thiếu.",
    "en": "Older attempts without measurements may be missing.",
    "zh": "较早且未保存测量数据的尝试可能未计入。"
  },
  {
    "source": "Lọc ngày tạo",
    "vi": "Lọc ngày tạo",
    "en": "Filter created dates",
    "zh": "筛选创建日期"
  },
  {
    "source": "Thao tác với {0}",
    "vi": "Thao tác với {0}",
    "en": "Actions for {0}",
    "zh": "{0}的操作"
  },
  {
    "source": "Sao chép LS",
    "vi": "Sao chép LS",
    "en": "Copy login string",
    "zh": "复制登录信息"
  },
  {
    "source": "Sao chép AT",
    "vi": "Sao chép AT",
    "en": "Copy AT",
    "zh": "复制AT"
  },
  {
    "source": "Cho phép thử lại",
    "vi": "Cho phép thử lại",
    "en": "Allow retry",
    "zh": "允许重试"
  },
  {
    "source": "Đã xử lý mail · cho phép thử lại",
    "vi": "Đã xử lý mail · cho phép thử lại",
    "en": "Email resolved · allow retry",
    "zh": "邮箱问题已解决 · 允许重试"
  },
  {
    "source": "Sửa tài khoản",
    "vi": "Sửa tài khoản",
    "en": "Edit account",
    "zh": "编辑账号"
  },
  {
    "source": "Xóa tài khoản",
    "vi": "Xóa tài khoản",
    "en": "Delete account",
    "zh": "删除账号"
  },
  {
    "source": "Không có tài khoản khớp bộ lọc",
    "vi": "Không có tài khoản khớp bộ lọc",
    "en": "No accounts match the filters",
    "zh": "没有符合筛选条件的账号"
  },
  {
    "source": "Chưa có tài khoản. Hãy nhập hoặc đăng ký mới.",
    "vi": "Chưa có tài khoản. Hãy nhập hoặc đăng ký mới.",
    "en": "No accounts yet. Import or register accounts first.",
    "zh": "暂无账号，请先导入或注册。"
  },
  {
    "source": "Chọn {0}",
    "vi": "Chọn {0}",
    "en": "Select {0}",
    "zh": "选择{0}"
  },
  {
    "source": "Thao tác mobile với {0}",
    "vi": "Thao tác mobile với {0}",
    "en": "Mobile actions for {0}",
    "zh": "{0}的移动端操作"
  },
  {
    "source": "Xóa tài khoản…",
    "vi": "Xóa tài khoản…",
    "en": "Delete account…",
    "zh": "删除账号…"
  },
  {
    "source": "Chưa rõ ngày",
    "vi": "Chưa rõ ngày",
    "en": "Date unknown",
    "zh": "日期未知"
  },
  {
    "source": "thư mục ·",
    "vi": "thư mục ·",
    "en": "folders ·",
    "zh": "个文件夹 ·"
  },
  {
    "source": "acc chưa phân thư mục",
    "vi": "acc chưa phân thư mục",
    "en": "unfiled accounts",
    "zh": "个未分类账号"
  },
  {
    "source": "Đổi tên nhóm {0}",
    "vi": "Đổi tên nhóm {0}",
    "en": "Rename group {0}",
    "zh": "重命名分组{0}"
  },
  {
    "source": "Xóa nhóm {0}",
    "vi": "Xóa nhóm {0}",
    "en": "Delete group {0}",
    "zh": "删除分组{0}"
  },
  {
    "source": "Chưa có nhóm",
    "vi": "Chưa có nhóm",
    "en": "No groups yet",
    "zh": "暂无分组"
  },
  {
    "source": "Chuyển tài khoản",
    "vi": "Chuyển tài khoản",
    "en": "Move accounts",
    "zh": "移动账号"
  },
  {
    "source": "Phạm vi chuyển",
    "vi": "Phạm vi chuyển",
    "en": "Move scope",
    "zh": "移动范围"
  },
  {
    "source": "Các tài khoản đang tích chọn trên bảng (",
    "vi": "Các tài khoản đang tích chọn trên bảng (",
    "en": "Accounts selected in the table (",
    "zh": "表格中已选账号（"
  },
  {
    "source": "Lấy N tài khoản đầu tiên theo bộ lọc hiện tại (",
    "vi": "Lấy N tài khoản đầu tiên theo bộ lọc hiện tại (",
    "en": "First N accounts matching the current filters (",
    "zh": "当前筛选结果中的前N个账号（"
  },
  {
    "source": "Tất cả tài khoản theo bộ lọc hiện tại (",
    "vi": "Tất cả tài khoản theo bộ lọc hiện tại (",
    "en": "All accounts matching the current filters (",
    "zh": "所有符合当前筛选条件的账号（"
  },
  {
    "source": "Số lượng tài khoản muốn lấy",
    "vi": "Số lượng tài khoản muốn lấy",
    "en": "Number of accounts to select",
    "zh": "选择账号数量"
  },
  {
    "source": "tài khoản đầu tiên trong bộ lọc hiện tại",
    "vi": "tài khoản đầu tiên trong bộ lọc hiện tại",
    "en": "first accounts in the current filter",
    "zh": "个当前筛选结果中的首批账号"
  },
  {
    "source": "Thư mục đích",
    "vi": "Thư mục đích",
    "en": "Destination folder",
    "zh": "目标文件夹"
  },
  {
    "source": "Chọn hoặc nhập tên thư mục mới…",
    "vi": "Chọn hoặc nhập tên thư mục mới…",
    "en": "Select or enter a new folder name…",
    "zh": "选择或输入新文件夹名称…"
  },
  {
    "source": "Xuất riêng Access Token",
    "vi": "Xuất riêng Access Token",
    "en": "Export Access Tokens only",
    "zh": "仅导出Access Token"
  },
  {
    "source": "Xuất tài khoản",
    "vi": "Xuất tài khoản",
    "en": "Export accounts",
    "zh": "导出账号"
  },
  {
    "source": "Phạm vi xuất",
    "vi": "Phạm vi xuất",
    "en": "Export scope",
    "zh": "导出范围"
  },
  {
    "source": "Toàn bộ kết quả lọc ·",
    "vi": "Toàn bộ kết quả lọc ·",
    "en": "All filtered results ·",
    "zh": "全部筛选结果 ·"
  },
  {
    "source": "tài khoản (mọi trang)",
    "vi": "tài khoản (mọi trang)",
    "en": "accounts (all pages)",
    "zh": "个账号（所有页面）"
  },
  {
    "source": "Chỉ acc đã chọn (",
    "vi": "Chỉ acc đã chọn (",
    "en": "Selected accounts only (",
    "zh": "仅已选账号（"
  },
  {
    "source": "Số lượng tài khoản",
    "vi": "Số lượng tài khoản",
    "en": "Account count",
    "zh": "账号数量"
  },
  {
    "source": "Toàn bộ (tất cả các trang)",
    "vi": "Toàn bộ (tất cả các trang)",
    "en": "All (across all pages)",
    "zh": "全部（所有页面）"
  },
  {
    "source": "Lấy N tài khoản đầu tiên",
    "vi": "Lấy N tài khoản đầu tiên",
    "en": "First N accounts",
    "zh": "前N个账号"
  },
  {
    "source": "Định dạng xuất file",
    "vi": "Định dạng xuất file",
    "en": "Export file format",
    "zh": "导出文件格式"
  },
  {
    "source": "Tệp tài khoản",
    "vi": "Tệp tài khoản",
    "en": "Account file",
    "zh": "账号文件"
  },
  {
    "source": "Mỗi dòng một Access Token, không kèm email hay mật khẩu.",
    "vi": "Mỗi dòng một Access Token, không kèm email hay mật khẩu.",
    "en": "One Access Token per line, without email or password.",
    "zh": "每行一个Access Token，不含邮箱或密码。"
  },
  {
    "source": "Xuất file ·",
    "vi": "Xuất file ·",
    "en": "Export file ·",
    "zh": "导出文件 ·"
  },
  {
    "source": "Tải file",
    "vi": "Tải file",
    "en": "Download file",
    "zh": "下载文件"
  },
  {
    "source": "Tải file & Xóa",
    "vi": "Tải file & Xóa",
    "en": "Download & Delete",
    "zh": "下载并删除"
  },
  {
    "source": "acc này",
    "vi": "acc này",
    "en": "these accounts",
    "zh": "个账号"
  },
  {
    "source": "độ dài=",
    "vi": "độ dài=",
    "en": "length=",
    "zh": "长度="
  },
  {
    "source": "Không có dữ liệu xác thực",
    "vi": "Không có dữ liệu xác thực",
    "en": "No authentication data",
    "zh": "无认证数据"
  },
  {
    "source": "Chỉnh sửa thông tin đăng nhập",
    "vi": "Chỉnh sửa thông tin đăng nhập",
    "en": "Edit login credentials",
    "zh": "编辑登录凭证"
  },
  {
    "source": "Lưu ý: Chỉ cập nhật dữ liệu trong hệ thống, không thay đổi trên OpenAI",
    "vi": "Lưu ý: Chỉ cập nhật dữ liệu trong hệ thống, không thay đổi trên OpenAI",
    "en": "Note: Updates local records only; does not change credentials on OpenAI",
    "zh": "注意：仅更新系统中的记录，不会修改OpenAI上的凭证"
  },
  {
    "source": "Mật khẩu và 2FA Secret tại đây sẽ được sử dụng trực tiếp khi tự động đăng nhập lại.",
    "vi": "Mật khẩu và 2FA Secret tại đây sẽ được sử dụng trực tiếp khi tự động đăng nhập lại.",
    "en": "This password and 2FA secret will be used directly for automatic login.",
    "zh": "这里的密码和2FA密钥将直接用于自动重新登录。"
  },
  {
    "source": "Mã 2FA Secret (TOTP)",
    "vi": "Mã 2FA Secret (TOTP)",
    "en": "2FA secret (TOTP)",
    "zh": "2FA密钥（TOTP）"
  },
  {
    "source": "Chuỗi base32, hỗ trợ khoảng trắng hoặc link otpauth://",
    "vi": "Chuỗi base32, hỗ trợ khoảng trắng hoặc link otpauth://",
    "en": "Base32 string; spaces and otpauth:// links are supported",
    "zh": "Base32字符串，支持空格或otpauth://链接"
  },
  {
    "source": "Mã 2FA Secret là duy nhất do OpenAI cấp ban đầu. Nếu ghi đè sẽ mất mã cũ.",
    "vi": "Mã 2FA Secret là duy nhất do OpenAI cấp ban đầu. Nếu ghi đè sẽ mất mã cũ.",
    "en": "The 2FA secret was originally issued once by OpenAI. Overwriting it loses the old secret.",
    "zh": "2FA密钥由OpenAI首次绑定时发放，覆盖后将丢失原密钥。"
  },
  {
    "source": "Lưu thay đổi",
    "vi": "Lưu thay đổi",
    "en": "Save changes",
    "zh": "保存更改"
  },
  {
    "source": "Mỗi dòng một tài khoản. Hỗ trợ: email----password hoặc email----password----2FA hoặc email:password. Sau khi nhập có thể quản lý, kiểm tra AT hoặc dò Plus trial.",
    "vi": "Mỗi dòng một tài khoản. Hỗ trợ: email----password hoặc email----password----2FA hoặc email:password. Sau khi nhập có thể quản lý, kiểm tra AT hoặc dò Plus trial.",
    "en": "One account per line. Supported: email----password, email----password----2FA or email:password. After importing, manage accounts, check AT or probe Plus trials.",
    "zh": "每行一个账号，支持email----password、email----password----2FA或email:password。导入后可管理账号、检查AT或探测Plus试用。"
  },
  {
    "source": "Gán vào nhóm (tùy chọn):",
    "vi": "Gán vào nhóm (tùy chọn):",
    "en": "Assign to group (optional):",
    "zh": "分配到分组（可选）："
  },
  {
    "source": "Để trống = Chưa phân nhóm, hoặc chọn/nhập tên nhóm...",
    "vi": "Để trống = Chưa phân nhóm, hoặc chọn/nhập tên nhóm...",
    "en": "Leave blank for Ungrouped, or select / enter a group name...",
    "zh": "留空为未分组，或选择／输入分组名称…"
  },
  {
    "source": "Dán danh sách hoặc tải file .txt:",
    "vi": "Dán danh sách hoặc tải file .txt:",
    "en": "Paste a list or upload a .txt file:",
    "zh": "粘贴列表或上传.txt文件："
  },
  {
    "source": "Chọn file .txt",
    "vi": "Chọn file .txt",
    "en": "Select .txt file",
    "zh": "选择.txt文件"
  },
  {
    "source": "Bộ lọc không hợp lệ",
    "vi": "Bộ lọc không hợp lệ",
    "en": "Invalid filter",
    "zh": "筛选条件无效"
  },
  {
    "source": "Tên để mở lại bộ lọc trên trình duyệt này.",
    "vi": "Tên để mở lại bộ lọc trên trình duyệt này.",
    "en": "Name for reopening this filter in this browser.",
    "zh": "输入名称，以便在此浏览器中再次使用该筛选。"
  },
  {
    "source": "Lưu bộ lọc",
    "vi": "Lưu bộ lọc",
    "en": "Save filter",
    "zh": "保存筛选"
  },
  {
    "source": "Ví dụ: Plus cần làm mới",
    "vi": "Ví dụ: Plus cần làm mới",
    "en": "Example: Plus needing refresh",
    "zh": "例如：需要刷新的Plus账号"
  },
  {
    "source": "Nhập tên tối đa 64 ký tự",
    "vi": "Nhập tên tối đa 64 ký tự",
    "en": "Enter a name with up to 64 characters",
    "zh": "名称最多64个字符"
  },
  {
    "source": "Dò checkout",
    "vi": "Dò checkout",
    "en": "Probe checkout",
    "zh": "探测结账"
  },
  {
    "source": "Chưa lấy được số tài khoản cần làm mới:",
    "vi": "Chưa lấy được số tài khoản cần làm mới:",
    "en": "Could not count accounts needing refresh:",
    "zh": "无法获取需要刷新的账号数量："
  },
  {
    "source": "Nhiều gói",
    "vi": "Nhiều gói",
    "en": "Multiple plans",
    "zh": "多个套餐"
  },
  {
    "source": "Free có ưu đãi",
    "vi": "Free có ưu đãi",
    "en": "Free with offer",
    "zh": "Free及优惠"
  },
  {
    "source": "Khóa",
    "vi": "Khóa",
    "en": "Blocked",
    "zh": "已封禁"
  },
  {
    "source": "AT lỗi",
    "vi": "AT lỗi",
    "en": "AT error",
    "zh": "AT错误"
  },
  {
    "source": "Hãy chọn lại proxy riêng của đợt này trước khi thử lại.",
    "vi": "Hãy chọn lại proxy riêng của đợt này trước khi thử lại.",
    "en": "Select this batch's custom proxy again before retrying.",
    "zh": "重试前请重新选择本批次的自定义代理。"
  },
  {
    "source": "Không còn acc lỗi có thể thử lại. Acc bị khóa/sai tài khoản/mật khẩu/2FA và AT đã dùng được đã được loại.",
    "vi": "Không còn acc lỗi có thể thử lại. Acc bị khóa/sai tài khoản/mật khẩu/2FA và AT đã dùng được đã được loại.",
    "en": "No failed accounts are eligible for retry. Blocked accounts, invalid credentials / 2FA and usable AT have been excluded.",
    "zh": "没有可重试的失败账号。已排除封禁、账号密码／2FA错误以及AT可用的账号。"
  },
  {
    "source": "Đã có tác vụ khác. Hãy chờ đợt hiện tại kết thúc.",
    "vi": "Đã có tác vụ khác. Hãy chờ đợt hiện tại kết thúc.",
    "en": "Another task is active. Wait for the current batch to finish.",
    "zh": "已有其他任务，请等待当前批次结束。"
  },
  {
    "source": "Đã bắt đầu thử lại {0} acc lỗi có thể cứu.",
    "vi": "Đã bắt đầu thử lại {0} acc lỗi có thể cứu.",
    "en": "Started retrying {0} eligible failed accounts.",
    "zh": "已开始重试{0}个可恢复的失败账号。"
  },
  {
    "source": "Chưa bắt đầu được đợt thử lại:",
    "vi": "Chưa bắt đầu được đợt thử lại:",
    "en": "Could not start retry batch:",
    "zh": "无法启动重试批次："
  },
  {
    "source": "Đã cho phép thử lại. Tài khoản sẽ được xét ở lần làm mới kế tiếp, chưa tự đăng nhập.",
    "vi": "Đã cho phép thử lại. Tài khoản sẽ được xét ở lần làm mới kế tiếp, chưa tự đăng nhập.",
    "en": "Retry allowed. The account will be considered in the next refresh; no login has started.",
    "zh": "已允许重试，将在下次刷新时重新评估此账号，尚未开始登录。"
  },
  {
    "source": "{0}: đã xử lý {1}/{2} tài khoản",
    "vi": "{0}: đã xử lý {1}/{2} tài khoản",
    "en": "{0}: processed {1}/{2} accounts",
    "zh": "{0}：已处理{1}/{2}个账号"
  },
  {
    "source": "Tác vụ làm mới token đã gián đoạn",
    "vi": "Tác vụ làm mới token đã gián đoạn",
    "en": "Token refresh task was interrupted",
    "zh": "令牌刷新任务已中断"
  },
  {
    "source": "Làm mới token",
    "vi": "Làm mới token",
    "en": "Refresh tokens",
    "zh": "刷新令牌"
  },
  {
    "source": "Quét AT",
    "vi": "Quét AT",
    "en": "Check AT",
    "zh": "检查AT"
  },
  {
    "source": "Quét gói",
    "vi": "Quét gói",
    "en": "Check plans",
    "zh": "检查套餐"
  },
  {
    "source": "{0} {1} ngày",
    "vi": "{0} {1} ngày",
    "en": "{0} {1} days",
    "zh": "{0}{1}天",
    "numericSlots": [
      1
    ],
    "translateSlots": [
      0
    ]
  },
  {
    "source": "Quá",
    "vi": "Quá",
    "en": "Overdue",
    "zh": "已超过"
  },
  {
    "source": "Hạn {0}",
    "vi": "Hạn {0}",
    "en": "Expires {0}",
    "zh": "到期{0}"
  },
  {
    "source": "Đã ghi nhận tài khoản bị khóa hoặc vô hiệu hóa",
    "vi": "Đã ghi nhận tài khoản bị khóa hoặc vô hiệu hóa",
    "en": "Account was reported blocked or disabled",
    "zh": "已记录账号封禁或停用"
  },
  {
    "source": "Tài khoản chưa có Access Token",
    "vi": "Tài khoản chưa có Access Token",
    "en": "Account has no Access Token",
    "zh": "账号没有Access Token"
  },
  {
    "source": "Hết hạn {0}",
    "vi": "Hết hạn {0}",
    "en": "Expired {0}",
    "zh": "已过期{0}"
  },
  {
    "source": "AT đã hết hạn",
    "vi": "AT đã hết hạn",
    "en": "AT has expired",
    "zh": "AT已过期"
  },
  {
    "source": "Token hết hạn lúc {0}. Kết quả dùng được trước đó không kéo dài thời hạn.",
    "vi": "Token hết hạn lúc {0}. Kết quả dùng được trước đó không kéo dài thời hạn.",
    "en": "Token expired at {0}. An earlier usable result does not extend its validity.",
    "zh": "令牌于{0}过期，先前可用的检查结果不会延长有效期。"
  },
  {
    "source": "AT bị từ chối (401)",
    "vi": "AT bị từ chối (401)",
    "en": "AT rejected (401)",
    "zh": "AT被拒绝（401）"
  },
  {
    "source": "AT đã bị API từ chối; hạn ghi trong token không bảo đảm còn dùng được.",
    "vi": "AT đã bị API từ chối; hạn ghi trong token không bảo đảm còn dùng được.",
    "en": "The API rejected this AT. The token's expiry date does not guarantee it remains usable.",
    "zh": "此AT已被API拒绝，令牌中的到期时间不保证它仍可使用。"
  },
  {
    "source": "Thời điểm hết hạn: {0}. {1}",
    "vi": "Thời điểm hết hạn: {0}. {1}",
    "en": "Expiry time: {0}. {1}",
    "zh": "到期时间：{0}。{1}",
    "translateSlots": [
      1
    ]
  },
  {
    "source": "Hạn đọc từ AT; chưa xác nhận lại qua API.",
    "vi": "Hạn đọc từ AT; chưa xác nhận lại qua API.",
    "en": "Expiry read from AT; not reverified through the API.",
    "zh": "到期时间从AT中读取，尚未通过API复查。"
  },
  {
    "source": "Dùng được · chưa rõ hạn",
    "vi": "Dùng được · chưa rõ hạn",
    "en": "Usable · expiry unknown",
    "zh": "可用 · 到期时间未知"
  },
  {
    "source": "Đã ghi nhận AT dùng được nhưng chưa đọc được ngày hết hạn",
    "vi": "Đã ghi nhận AT dùng được nhưng chưa đọc được ngày hết hạn",
    "en": "AT was usable, but its expiry date could not be read",
    "zh": "已记录AT可用，但无法读取到期日期"
  },
  {
    "source": "Chưa đọc được ngày hết hạn của AT",
    "vi": "Chưa đọc được ngày hết hạn của AT",
    "en": "Could not read AT expiry date",
    "zh": "无法读取AT到期日期"
  },
  {
    "source": "Đã dò ưu đãi",
    "vi": "Đã dò ưu đãi",
    "en": "Offer checked",
    "zh": "已检查优惠"
  },
  {
    "source": "Đã xác minh gói",
    "vi": "Đã xác minh gói",
    "en": "Plan verified",
    "zh": "套餐已验证"
  },
  {
    "source": "Chưa đủ dữ liệu xác minh",
    "vi": "Chưa đủ dữ liệu xác minh",
    "en": "Insufficient verification data",
    "zh": "验证数据不足"
  },
  {
    "source": "Gói hiện tại chưa xác minh",
    "vi": "Gói hiện tại chưa xác minh",
    "en": "Current plan not verified",
    "zh": "当前套餐未验证"
  },
  {
    "source": "Không thấy ưu đãi · chưa xác minh gói",
    "vi": "Không thấy ưu đãi · chưa xác minh gói",
    "en": "No offer found · plan not verified",
    "zh": "未发现优惠 · 套餐未验证"
  },
  {
    "source": "Chưa quét gói tài khoản",
    "vi": "Chưa quét gói tài khoản",
    "en": "Account plan not checked yet",
    "zh": "尚未检查账号套餐"
  },
  {
    "source": "Đã xác minh:",
    "vi": "Đã xác minh:",
    "en": "Verified:",
    "zh": "已验证："
  },
  {
    "source": "Đã quét:",
    "vi": "Đã quét:",
    "en": "Checked:",
    "zh": "已检查："
  },
  {
    "source": "Hạn thuê bao:",
    "vi": "Hạn thuê bao:",
    "en": "Subscription expires:",
    "zh": "订阅到期："
  },
  {
    "source": "workspace đang có quyền truy cập",
    "vi": "workspace đang có quyền truy cập",
    "en": "accessible workspaces",
    "zh": "个可访问的工作区"
  },
  {
    "source": "Có ghi nhận ưu đãi Plus; ưu đãi khác với gói đang hoạt động",
    "vi": "Có ghi nhận ưu đãi Plus; ưu đãi khác với gói đang hoạt động",
    "en": "A Plus offer was recorded; an offer is different from an active plan",
    "zh": "已记录Plus优惠，优惠与正在生效的套餐不同"
  },
  {
    "source": "Đã lưu thứ tự thư mục",
    "vi": "Đã lưu thứ tự thư mục",
    "en": "Folder order saved",
    "zh": "文件夹顺序已保存"
  },
  {
    "source": "Chưa lưu được thứ tự thư mục:",
    "vi": "Chưa lưu được thứ tự thư mục:",
    "en": "Could not save folder order:",
    "zh": "无法保存文件夹顺序："
  },
  {
    "source": "Đã dừng tác vụ. Kết quả đã xử lý được giữ nguyên.",
    "vi": "Đã dừng tác vụ. Kết quả đã xử lý được giữ nguyên.",
    "en": "Task stopped. Processed results were preserved.",
    "zh": "任务已停止，已处理结果已保留。"
  },
  {
    "source": "Đã nhận lệnh dừng. Đang chờ tài khoản hiện tại hoàn tất.",
    "vi": "Đã nhận lệnh dừng. Đang chờ tài khoản hiện tại hoàn tất.",
    "en": "Stop request received. Waiting for the current account to finish.",
    "zh": "已收到停止请求，正在等待当前账号处理完成。"
  },
  {
    "source": "Chưa xác nhận được lệnh dừng; hệ thống sẽ tự gửi lại khi có kết nối.",
    "vi": "Chưa xác nhận được lệnh dừng; hệ thống sẽ tự gửi lại khi có kết nối.",
    "en": "Stop request not confirmed; will retry automatically when connected.",
    "zh": "停止请求尚未确认，连接恢复后将自动重试。"
  },
  {
    "source": "Hãy chọn proxy trong cấu hình tác vụ hoặc dùng Kho Proxy.",
    "vi": "Hãy chọn proxy trong cấu hình tác vụ hoặc dùng Kho Proxy.",
    "en": "Select a proxy in task settings or use the proxy pool.",
    "zh": "请在任务设置中选择代理，或使用代理池。"
  },
  {
    "source": "Phạm vi đã chọn không có tài khoản",
    "vi": "Phạm vi đã chọn không có tài khoản",
    "en": "No accounts in the selected scope",
    "zh": "所选范围内没有账号"
  },
  {
    "source": "Không còn acc đủ điều kiện làm mới. Đã có AT dùng được {0}, sai TK/MK/2FA {1}, bị khóa {2}, chờ xử lý mail OTP {3}, chưa rõ hạn {4}.",
    "vi": "Không còn acc đủ điều kiện làm mới. Đã có AT dùng được {0}, sai TK/MK/2FA {1}, bị khóa {2}, chờ xử lý mail OTP {3}, chưa rõ hạn {4}.",
    "en": "No accounts remain eligible for refresh. Usable AT: {0}, invalid credentials / 2FA: {1}, blocked: {2}, email OTP holds: {3}, expiry unknown: {4}.",
    "zh": "没有符合刷新条件的账号。AT可用{0}，账号密码／2FA错误{1}，封禁{2}，邮箱验证码待处理{3}，到期时间未知{4}。"
  },
  {
    "source": "Không có tài khoản nào trong phạm vi tác vụ",
    "vi": "Không có tài khoản nào trong phạm vi tác vụ",
    "en": "No accounts in the task scope",
    "zh": "任务范围内没有账号"
  },
  {
    "source": "Đã nhận đủ {0} tài khoản để {1}.",
    "vi": "Đã nhận đủ {0} tài khoản để {1}.",
    "en": "Received all {0} accounts for {1}.",
    "zh": "已接收全部{0}个账号以进行{1}。",
    "translateSlots": [
      1
    ]
  },
  {
    "source": "Không khởi động được tác vụ:",
    "vi": "Không khởi động được tác vụ:",
    "en": "Could not start task:",
    "zh": "无法启动任务："
  },
  {
    "source": "Lấy danh sách tài khoản thất bại:",
    "vi": "Lấy danh sách tài khoản thất bại:",
    "en": "Failed to load account list:",
    "zh": "加载账号列表失败："
  },
  {
    "source": "Không có tài khoản nào theo bộ lọc",
    "vi": "Không có tài khoản nào theo bộ lọc",
    "en": "No accounts match the filter",
    "zh": "没有符合筛选条件的账号"
  },
  {
    "source": "{0} tài khoản đã chọn",
    "vi": "{0} tài khoản đã chọn",
    "en": "{0} selected accounts",
    "zh": "{0}个已选账号",
    "numericSlots": [
      0
    ]
  },
  {
    "source": "toàn bộ {0} tài khoản theo bộ lọc",
    "vi": "toàn bộ {0} tài khoản theo bộ lọc",
    "en": "all {0} accounts matching the filter",
    "zh": "全部{0}个符合筛选条件的账号"
  },
  {
    "source": "Kiểm tra hạn AT theo JWT cho {0}?",
    "vi": "Kiểm tra hạn AT theo JWT cho {0}?",
    "en": "Check JWT AT expiry for {0}?",
    "zh": "检查{0}的JWT中AT到期时间？",
    "translateSlots": [
      0
    ]
  },
  {
    "source": "Các tài khoản hết hạn JWT sẽ tự động được làm mới bằng Mật khẩu + 2FA.",
    "vi": "Các tài khoản hết hạn JWT sẽ tự động được làm mới bằng Mật khẩu + 2FA.",
    "en": "JWT-expired accounts will be refreshed automatically using Password + 2FA.",
    "zh": "JWT已过期的账号将使用密码和2FA自动刷新。"
  },
  {
    "source": "Thao tác không thay đổi mật khẩu hay 2FA.",
    "vi": "Thao tác không thay đổi mật khẩu hay 2FA.",
    "en": "This does not change passwords or 2FA.",
    "zh": "此操作不会修改密码或2FA。"
  },
  {
    "source": "Đang kiểm tra AT… {0}/{1}",
    "vi": "Đang kiểm tra AT… {0}/{1}",
    "en": "Checking AT… {0}/{1}",
    "zh": "正在检查AT… {0}/{1}"
  },
  {
    "source": "Đã kiểm tra {0} acc: Còn hạn {1}",
    "vi": "Đã kiểm tra {0} acc: Còn hạn {1}",
    "en": "Checked {0} accounts: {1} unexpired",
    "zh": "已检查{0}个账号：{1}个未过期"
  },
  {
    "source": "Hết hạn {0} (Đã làm mới {1}{2})",
    "vi": "Hết hạn {0} (Đã làm mới {1}{2})",
    "en": "Expired {0} (refreshed {1}{2})",
    "zh": "已过期{0}（已刷新{1}{2}）",
    "translateSlots": [
      2
    ]
  },
  {
    "source": "thất bại {0}",
    "vi": "thất bại {0}",
    "en": "failed {0}",
    "zh": "失败{0}"
  },
  {
    "source": "{0} acc không rõ hạn",
    "vi": "{0} acc không rõ hạn",
    "en": "{0} accounts with unknown expiry",
    "zh": "{0}个账号到期时间未知"
  },
  {
    "source": "Làm mới hoàn tất: Thành công {0}, Thất bại {1}",
    "vi": "Làm mới hoàn tất: Thành công {0}, Thất bại {1}",
    "en": "Refresh complete: {0} succeeded, {1} failed",
    "zh": "刷新完成：成功{0}，失败{1}"
  },
  {
    "source": "Phát hiện {0} token hết hạn, đã làm mới thành công toàn bộ",
    "vi": "Phát hiện {0} token hết hạn, đã làm mới thành công toàn bộ",
    "en": "Found {0} expired tokens; all refreshed successfully",
    "zh": "发现{0}个过期令牌，已全部刷新成功"
  },
  {
    "source": "Trạng thái token bình thường, không có tài khoản cần làm mới",
    "vi": "Trạng thái token bình thường, không có tài khoản cần làm mới",
    "en": "Tokens are normal; no accounts need refresh",
    "zh": "令牌状态正常，没有需要刷新的账号"
  },
  {
    "source": "0đ",
    "vi": "0đ",
    "en": "No charge",
    "zh": "免费"
  },
  {
    "source": "Lỗi mạng",
    "vi": "Lỗi mạng",
    "en": "Network error",
    "zh": "网络错误"
  },
  {
    "source": "Dò lỗi",
    "vi": "Dò lỗi",
    "en": "Probe error",
    "zh": "探测错误"
  },
  {
    "source": "{0} Không UPI",
    "vi": "{0} Không UPI",
    "en": "{0} No UPI",
    "zh": "{0} 不支持UPI",
    "numericSlots": [
      0
    ]
  },
  {
    "source": "₹0.00 (0đ)",
    "vi": "₹0.00 (0đ)",
    "en": "₹0.00 (free)",
    "zh": "₹0.00（免费）"
  },
  {
    "source": "Vui lòng tích chọn các tài khoản cần xuất trước",
    "vi": "Vui lòng tích chọn các tài khoản cần xuất trước",
    "en": "Select accounts to export first",
    "zh": "请先选择要导出的账号"
  },
  {
    "source": "Đã tải xuống {0} ({1} tài khoản)",
    "vi": "Đã tải xuống {0} ({1} tài khoản)",
    "en": "Downloaded {0} ({1} accounts)",
    "zh": "已下载{0}（{1}个账号）"
  },
  {
    "source": "Xuất file thất bại:",
    "vi": "Xuất file thất bại:",
    "en": "File export failed:",
    "zh": "导出文件失败："
  },
  {
    "source": "Free (kết quả cũ)",
    "vi": "Free (kết quả cũ)",
    "en": "Free (legacy result)",
    "zh": "Free（旧结果）"
  },
  {
    "source": "Lịch sử mở Plus",
    "vi": "Lịch sử mở Plus",
    "en": "Plus activation history",
    "zh": "Plus开通记录"
  },
  {
    "source": "Đã khóa",
    "vi": "Đã khóa",
    "en": "Blocked",
    "zh": "已封禁"
  },
  {
    "source": "AT hết hạn / bị từ chối",
    "vi": "AT hết hạn / bị từ chối",
    "en": "AT expired / rejected",
    "zh": "AT已过期／被拒绝"
  },
  {
    "source": "Bị khóa khi đăng nhập",
    "vi": "Bị khóa khi đăng nhập",
    "en": "Blocked during login",
    "zh": "登录时被封禁"
  },
  {
    "source": "Thư mục:",
    "vi": "Thư mục:",
    "en": "Folder:",
    "zh": "文件夹："
  },
  {
    "source": "Gói",
    "vi": "Gói",
    "en": "Plan",
    "zh": "套餐"
  },
  {
    "source": "Quốc gia:",
    "vi": "Quốc gia:",
    "en": "Country:",
    "zh": "国家："
  },
  {
    "source": "Có {0} tài khoản, vượt giới hạn {1} của tác vụ. Hãy chọn nhóm hoặc thu hẹp bộ lọc.",
    "vi": "Có {0} tài khoản, vượt giới hạn {1} của tác vụ. Hãy chọn nhóm hoặc thu hẹp bộ lọc.",
    "en": "{0} accounts exceed this task's limit of {1}. Choose a group or narrow the filters.",
    "zh": "共{0}个账号，超过此任务的{1}个上限，请选择分组或缩小筛选范围。"
  },
  {
    "source": "Vui lòng chọn định dạng xuất file",
    "vi": "Vui lòng chọn định dạng xuất file",
    "en": "Select an export format",
    "zh": "请选择导出格式"
  },
  {
    "source": "Không có tài khoản nào trong phạm vi xuất",
    "vi": "Không có tài khoản nào trong phạm vi xuất",
    "en": "No accounts in the export scope",
    "zh": "导出范围内没有账号"
  },
  {
    "source": "Xóa thông tin xác thực của {0}?",
    "vi": "Xóa thông tin xác thực của {0}?",
    "en": "Delete credentials for {0}?",
    "zh": "删除{0}的凭证？"
  },
  {
    "source": "Đã xóa thành công",
    "vi": "Đã xóa thành công",
    "en": "Deleted successfully",
    "zh": "删除成功"
  },
  {
    "source": "Bạn có chắc chắn muốn xóa {0} tài khoản đã chọn? (Không thể hoàn tác)",
    "vi": "Bạn có chắc chắn muốn xóa {0} tài khoản đã chọn? (Không thể hoàn tác)",
    "en": "Delete {0} selected accounts? This cannot be undone.",
    "zh": "确定删除{0}个已选账号？此操作不可恢复。"
  },
  {
    "source": "Thao tác này sẽ xóa toàn bộ tài khoản trong danh sách Đã đăng ký! Kho mail không bị ảnh hưởng, bạn có chắc chắn?",
    "vi": "Thao tác này sẽ xóa toàn bộ tài khoản trong danh sách Đã đăng ký! Kho mail không bị ảnh hưởng, bạn có chắc chắn?",
    "en": "This deletes all registered accounts. The mail pool is unaffected. Continue?",
    "zh": "此操作将删除全部已注册账号，邮箱池不受影响。确定继续？"
  },
  {
    "source": "Xác nhận lần 2: Thao tác này KHÔNG THỂ HOÀN TÁC! Bạn có chắc muốn xóa sạch toàn bộ?",
    "vi": "Xác nhận lần 2: Thao tác này KHÔNG THỂ HOÀN TÁC! Bạn có chắc muốn xóa sạch toàn bộ?",
    "en": "Second confirmation: This CANNOT BE UNDONE. Delete everything?",
    "zh": "再次确认：此操作不可恢复！确定全部删除？"
  },
  {
    "source": "Đã xóa {0} tài khoản{1}{2}",
    "vi": "Đã xóa {0} tài khoản{1}{2}",
    "en": "Deleted {0} accounts{1}{2}",
    "zh": "已删除{0}个账号{1}{2}",
    "translateSlots": [
      1,
      2
    ]
  },
  {
    "source": ". Giữ lại {0} acc đang chờ hoặc đang xử lý.",
    "vi": ". Giữ lại {0} acc đang chờ hoặc đang xử lý.",
    "en": ". Kept {0} queued or active accounts.",
    "zh": "。已保留{0}个排队或处理中的账号。"
  },
  {
    "source": "Bỏ qua {0} acc không còn khớp bộ lọc.",
    "vi": "Bỏ qua {0} acc không còn khớp bộ lọc.",
    "en": "Skipped {0} accounts that no longer match the filters.",
    "zh": "已跳过{0}个不再符合筛选条件的账号。"
  },
  {
    "source": "Điều kiện lọc đã đổi; hãy bấm xóa lại với bộ lọc mới.",
    "vi": "Điều kiện lọc đã đổi; hãy bấm xóa lại với bộ lọc mới.",
    "en": "Filters changed. Click delete again with the new filters.",
    "zh": "筛选条件已更改，请按新条件重新点击删除。"
  },
  {
    "source": "Xóa {0} tài khoản khớp bộ lọc trên tất cả các trang? {1} Acc còn chờ hoặc đang xử lý sẽ được giữ lại. Không thể hoàn tác.",
    "vi": "Xóa {0} tài khoản khớp bộ lọc trên tất cả các trang? {1} Acc còn chờ hoặc đang xử lý sẽ được giữ lại. Không thể hoàn tác.",
    "en": "Delete {0} matching accounts across all pages? {1} Queued or active accounts will be kept. This cannot be undone.",
    "zh": "删除所有页面中符合条件的{0}个账号？{1}排队或处理中的账号将保留。此操作不可恢复。",
    "translateSlots": [
      1
    ]
  },
  {
    "source": "Email · Mật khẩu",
    "vi": "Email · Mật khẩu",
    "en": "Email · Password",
    "zh": "邮箱 · 密码"
  },
  {
    "source": "Email · Mật khẩu · 2FA · Link nhận mã",
    "vi": "Email · Mật khẩu · 2FA · Link nhận mã",
    "en": "Email · Password · 2FA · Code retrieval link",
    "zh": "邮箱 · 密码 · 2FA · 验证码获取链接"
  },
  {
    "source": "Email · Mật khẩu · 2FA · AT",
    "vi": "Email · Mật khẩu · 2FA · AT",
    "en": "Email · Password · 2FA · AT",
    "zh": "邮箱 · 密码 · 2FA · AT"
  },
  {
    "source": "Tải danh sách định dạng xuất thất bại:",
    "vi": "Tải danh sách định dạng xuất thất bại:",
    "en": "Failed to load export formats:",
    "zh": "加载导出格式失败："
  },
  {
    "source": "Đợt xuất này không lấy được danh sách email, chỉ tải file chứ không xóa dữ liệu",
    "vi": "Đợt xuất này không lấy được danh sách email, chỉ tải file chứ không xóa dữ liệu",
    "en": "Could not retrieve the email list for this export. The file was downloaded; no data was deleted.",
    "zh": "本次导出无法获取邮箱列表，仅下载文件，未删除数据。"
  },
  {
    "source": "Đã tải xuống file {0}.",
    "vi": "Đã tải xuống file {0}.",
    "en": "Downloaded file {0}.",
    "zh": "已下载文件{0}。"
  },
  {
    "source": "Tiến hành xóa {0} tài khoản này khỏi hệ thống:",
    "vi": "Tiến hành xóa {0} tài khoản này khỏi hệ thống:",
    "en": "Delete these {0} accounts from the system:",
    "zh": "从系统中删除这{0}个账号："
  },
  {
    "source": "• Xóa toàn bộ thông tin tài khoản (Mật khẩu, 2FA secret, Token)",
    "vi": "• Xóa toàn bộ thông tin tài khoản (Mật khẩu, 2FA secret, Token)",
    "en": "• Delete all account credentials (password, 2FA secret, tokens)",
    "zh": "• 删除全部账号凭证（密码、2FA密钥、令牌）"
  },
  {
    "source": "• Xóa tài khoản tương ứng trong Kho Email",
    "vi": "• Xóa tài khoản tương ứng trong Kho Email",
    "en": "• Delete corresponding accounts from the mail pool",
    "zh": "• 删除邮箱池中的对应账号"
  },
  {
    "source": "Sau khi xóa, dữ liệu chỉ còn lưu trong file .txt bạn vừa tải về. Thao tác không thể hoàn tác, bạn có chắc chắn?",
    "vi": "Sau khi xóa, dữ liệu chỉ còn lưu trong file .txt bạn vừa tải về. Thao tác không thể hoàn tác, bạn có chắc chắn?",
    "en": "After deletion, only the downloaded .txt file retains this data. This cannot be undone. Continue?",
    "zh": "删除后，数据仅保留在刚下载的.txt文件中。此操作不可恢复，确定继续？"
  },
  {
    "source": "Đã xóa trong danh sách Đã đăng ký, nhưng xóa trong Kho email thất bại:",
    "vi": "Đã xóa trong danh sách Đã đăng ký, nhưng xóa trong Kho email thất bại:",
    "en": "Deleted registered accounts, but deleting from the mail pool failed:",
    "zh": "已删除已注册账号，但从邮箱池删除失败："
  },
  {
    "source": "Đã xóa: Đã đăng ký {0} acc / Kho email {1} acc",
    "vi": "Đã xóa: Đã đăng ký {0} acc / Kho email {1} acc",
    "en": "Deleted: {0} registered accounts / {1} mail pool accounts",
    "zh": "已删除：已注册账号{0}个／邮箱池账号{1}个"
  },
  {
    "source": "Tên thư mục để sắp xếp tài khoản.",
    "vi": "Tên thư mục để sắp xếp tài khoản.",
    "en": "Folder name for organizing accounts.",
    "zh": "用于整理账号的文件夹名称。"
  },
  {
    "source": "Nhập tên thư mục…",
    "vi": "Nhập tên thư mục…",
    "en": "Enter folder name…",
    "zh": "输入文件夹名称…"
  },
  {
    "source": "Tên thư mục không được để trống",
    "vi": "Tên thư mục không được để trống",
    "en": "Folder name cannot be empty",
    "zh": "文件夹名称不能为空"
  },
  {
    "source": "Tên thư mục không hợp lệ",
    "vi": "Tên thư mục không hợp lệ",
    "en": "Invalid folder name",
    "zh": "文件夹名称无效"
  },
  {
    "source": "Đã tạo thư mục «{0}»",
    "vi": "Đã tạo thư mục «{0}»",
    "en": "Created folder «{0}»",
    "zh": "已创建文件夹«{0}»"
  },
  {
    "source": "Đổi tên thư mục «{0}» thành:",
    "vi": "Đổi tên thư mục «{0}» thành:",
    "en": "Rename folder «{0}» to:",
    "zh": "将文件夹«{0}»重命名为："
  },
  {
    "source": "Đã đổi tên thư mục thành «{0}»",
    "vi": "Đã đổi tên thư mục thành «{0}»",
    "en": "Folder renamed to «{0}»",
    "zh": "文件夹已重命名为«{0}»"
  },
  {
    "source": "Xóa thư mục «{0}» ({1} tài khoản)?",
    "vi": "Xóa thư mục «{0}» ({1} tài khoản)?",
    "en": "Delete folder «{0}» ({1} accounts)?",
    "zh": "删除文件夹«{0}»（{1}个账号）？"
  },
  {
    "source": "Tài khoản được giữ lại và chuyển về «Chưa phân thư mục».",
    "vi": "Tài khoản được giữ lại và chuyển về «Chưa phân thư mục».",
    "en": "Accounts will be kept and moved to Unfiled.",
    "zh": "账号将保留并移至未分类。"
  },
  {
    "source": "Đã xóa thư mục «{0}»",
    "vi": "Đã xóa thư mục «{0}»",
    "en": "Deleted folder «{0}»",
    "zh": "已删除文件夹«{0}»"
  },
  {
    "source": "Xóa thư mục thất bại:",
    "vi": "Xóa thư mục thất bại:",
    "en": "Failed to delete folder:",
    "zh": "删除文件夹失败："
  },
  {
    "source": "Chưa có tài khoản nào được chọn",
    "vi": "Chưa có tài khoản nào được chọn",
    "en": "No accounts selected",
    "zh": "尚未选择账号"
  },
  {
    "source": "Đã chuyển {0} tài khoản vào thư mục «{1}»",
    "vi": "Đã chuyển {0} tài khoản vào thư mục «{1}»",
    "en": "Moved {0} accounts to folder «{1}»",
    "zh": "已将{0}个账号移至文件夹«{1}»"
  },
  {
    "source": "Đã đưa {0} tài khoản về Chưa phân thư mục",
    "vi": "Đã đưa {0} tài khoản về Chưa phân thư mục",
    "en": "Moved {0} accounts to Unfiled",
    "zh": "已将{0}个账号移至未分类"
  },
  {
    "source": "Bỏ qua {0} tài khoản đã thay đổi hoặc không còn trong phạm vi.",
    "vi": "Bỏ qua {0} tài khoản đã thay đổi hoặc không còn trong phạm vi.",
    "en": "Skipped {0} accounts that changed or left the scope.",
    "zh": "已跳过{0}个已更改或不再属于此范围的账号。"
  },
  {
    "source": "Chuyển thư mục thất bại:",
    "vi": "Chuyển thư mục thất bại:",
    "en": "Failed to move accounts:",
    "zh": "移动账号失败："
  },
  {
    "source": "Vui lòng tích chọn tài khoản trên bảng trước",
    "vi": "Vui lòng tích chọn tài khoản trên bảng trước",
    "en": "Select accounts in the table first",
    "zh": "请先在表格中选择账号"
  },
  {
    "source": "Vui lòng chọn hoặc nhập tên thư mục đích",
    "vi": "Vui lòng chọn hoặc nhập tên thư mục đích",
    "en": "Select or enter the destination folder name",
    "zh": "请选择或输入目标文件夹名称"
  },
  {
    "source": "Không có tài khoản nào trong phạm vi đã chọn",
    "vi": "Không có tài khoản nào trong phạm vi đã chọn",
    "en": "No accounts in the chosen scope",
    "zh": "选定范围内没有账号"
  },
  {
    "source": "Bộ lọc đã thay đổi. Mở lại thao tác chuyển để kiểm tra phạm vi.",
    "vi": "Bộ lọc đã thay đổi. Mở lại thao tác chuyển để kiểm tra phạm vi.",
    "en": "Filters changed. Reopen the move action to review the scope.",
    "zh": "筛选条件已更改，请重新打开移动操作以检查范围。"
  },
  {
    "source": "Đã tải nội dung file",
    "vi": "Đã tải nội dung file",
    "en": "File content loaded",
    "zh": "已读取文件内容"
  },
  {
    "source": "Tổng cộng: {0} | Thêm mới: {1} | Cập nhật: {2} | Thất bại: {3}",
    "vi": "Tổng cộng: {0} | Thêm mới: {1} | Cập nhật: {2} | Thất bại: {3}",
    "en": "Total: {0} | Added: {1} | Updated: {2} | Failed: {3}",
    "zh": "总计：{0} | 新增：{1} | 更新：{2} | 失败：{3}"
  },
  {
    "source": "Nhập hoàn tất: Thêm mới {0}, Cập nhật {1}",
    "vi": "Nhập hoàn tất: Thêm mới {0}, Cập nhật {1}",
    "en": "Import complete: Added {0}, updated {1}",
    "zh": "导入完成：新增{0}，更新{1}"
  },
  {
    "source": "Sao chép LS thất bại:",
    "vi": "Sao chép LS thất bại:",
    "en": "Failed to copy login string:",
    "zh": "复制登录信息失败："
  },
  {
    "source": "Trường {0} trống",
    "vi": "Trường {0} trống",
    "en": "Field {0} is empty",
    "zh": "字段{0}为空",
    "translateSlots": [
      0
    ]
  },
  {
    "source": "Không có thay đổi nào",
    "vi": "Không có thay đổi nào",
    "en": "No changes",
    "zh": "没有更改"
  },
  {
    "source": "Tài khoản này đã có mã 2FA secret: {0}",
    "vi": "Tài khoản này đã có mã 2FA secret: {0}",
    "en": "This account already has a 2FA secret: {0}",
    "zh": "此账号已有2FA密钥：{0}"
  },
  {
    "source": "Nếu ghi đè, mã secret cũ sẽ bị mất vĩnh viễn.",
    "vi": "Nếu ghi đè, mã secret cũ sẽ bị mất vĩnh viễn.",
    "en": "Overwriting will permanently lose the old secret.",
    "zh": "覆盖后将永久丢失原密钥。"
  },
  {
    "source": "Nếu mã cũ vẫn đang hiệu lực trên OpenAI, việc ghi đè sai sẽ khiến tài khoản không đăng nhập được.",
    "vi": "Nếu mã cũ vẫn đang hiệu lực trên OpenAI, việc ghi đè sai sẽ khiến tài khoản không đăng nhập được.",
    "en": "If the old secret is still active on OpenAI, an incorrect replacement will prevent login.",
    "zh": "如果原密钥仍在OpenAI上生效，覆盖为错误密钥将导致无法登录。"
  },
  {
    "source": "Xác nhận ghi đè mã 2FA secret?",
    "vi": "Xác nhận ghi đè mã 2FA secret?",
    "en": "Overwrite the 2FA secret?",
    "zh": "确认覆盖2FA密钥？"
  },
  {
    "source": "Đã lưu thành công: {0}",
    "vi": "Đã lưu thành công: {0}",
    "en": "Saved successfully: {0}",
    "zh": "保存成功：{0}"
  },
  {
    "source": "Không thay đổi",
    "vi": "Không thay đổi",
    "en": "Unchanged",
    "zh": "未更改"
  },
  {
    "source": "LỊCH SỬ",
    "vi": "LỊCH SỬ",
    "en": "HISTORY",
    "zh": "历史"
  },
  {
    "source": "Nhật ký đăng ký",
    "vi": "Nhật ký đăng ký",
    "en": "Registration log",
    "zh": "注册日志"
  },
  {
    "source": "Kết quả và thông tin chẩn đoán của từng lượt chạy.",
    "vi": "Kết quả và thông tin chẩn đoán của từng lượt chạy.",
    "en": "Results and diagnostics for each run.",
    "zh": "每次运行的结果和诊断信息。"
  },
  {
    "source": "Về tác vụ ↗",
    "vi": "Về tác vụ ↗",
    "en": "Back to tasks ↗",
    "zh": "返回任务 ↗"
  },
  {
    "source": "探针详情 · {0}",
    "vi": "Chi tiết thăm dò · {0}",
    "en": "Probe details · {0}",
    "zh": "探针详情 · {0}"
  },
  {
    "source": "Tự thuê số khi luồng đăng ký yêu cầu xác minh điện thoại.",
    "vi": "Tự thuê số khi luồng đăng ký yêu cầu xác minh điện thoại.",
    "en": "Automatically rent a number when registration requests phone verification.",
    "zh": "注册流程要求手机验证时自动租用号码。"
  },
  {
    "source": "个国家 · 留空 = 全平台自动挑最便宜的；只勾 1 个 = 锁死用这个国家",
    "vi": "quốc gia · Để trống = tự chọn rẻ nhất; chỉ chọn một = cố định quốc gia đó",
    "en": "countries · Blank = automatically choose the cheapest; select one to fix the country",
    "zh": "个国家 · 留空则自动选择全平台最便宜的；仅选一个则固定使用该国家"
  },
  {
    "source": "Dán API Key từ sàn nhận SMS",
    "vi": "Dán API Key từ sàn nhận SMS",
    "en": "Paste the SMS provider API key",
    "zh": "粘贴接码平台API密钥"
  },
  {
    "source": "Theo dõi đăng ký, làm mới AT và kiểm tra tài khoản.",
    "vi": "Theo dõi đăng ký, làm mới AT và kiểm tra tài khoản.",
    "en": "Track registration, AT refresh and account checks.",
    "zh": "跟踪注册、AT刷新和账号检查。"
  },
  {
    "source": "Đăng ký đang xử lý",
    "vi": "Đăng ký đang xử lý",
    "en": "Active registrations",
    "zh": "正在处理的注册"
  },
  {
    "source": "Cập nhật lúc",
    "vi": "Cập nhật lúc",
    "en": "Updated at",
    "zh": "更新于"
  },
  {
    "source": "Đang tải…",
    "vi": "Đang tải…",
    "en": "Loading…",
    "zh": "正在加载…"
  },
  {
    "source": "Đã tạm dừng nhận thêm",
    "vi": "Đã tạm dừng nhận thêm",
    "en": "Paused new intake",
    "zh": "已暂停接收新账号"
  },
  {
    "source": "Đang hoạt động",
    "vi": "Đang hoạt động",
    "en": "Active",
    "zh": "运行中"
  },
  {
    "source": "Xem và điều khiển",
    "vi": "Xem và điều khiển",
    "en": "View and control",
    "zh": "查看与控制"
  },
  {
    "source": "Mở trong Tài khoản",
    "vi": "Mở trong Tài khoản",
    "en": "Open in Accounts",
    "zh": "在账号页面中打开"
  },
  {
    "source": "Đóng chi tiết",
    "vi": "Đóng chi tiết",
    "en": "Close details",
    "zh": "关闭详情"
  },
  {
    "source": "Phạm vi tác vụ",
    "vi": "Phạm vi tác vụ",
    "en": "Task scope",
    "zh": "任务范围"
  },
  {
    "source": "Gần đây",
    "vi": "Gần đây",
    "en": "Recent",
    "zh": "最近"
  },
  {
    "source": "đợt gần nhất",
    "vi": "đợt gần nhất",
    "en": "recent batches",
    "zh": "个最近批次"
  },
  {
    "source": "Đang tải tác vụ…",
    "vi": "Đang tải tác vụ…",
    "en": "Loading tasks…",
    "zh": "正在加载任务…"
  },
  {
    "source": "Chưa lấy được tác vụ",
    "vi": "Chưa lấy được tác vụ",
    "en": "Could not load tasks",
    "zh": "无法加载任务"
  },
  {
    "source": "Không có tác vụ tài khoản đang chạy",
    "vi": "Không có tác vụ tài khoản đang chạy",
    "en": "No active account tasks",
    "zh": "没有正在运行的账号任务"
  },
  {
    "source": "Chưa có tác vụ",
    "vi": "Chưa có tác vụ",
    "en": "No tasks yet",
    "zh": "暂无任务"
  },
  {
    "source": "thành công ·",
    "vi": "thành công ·",
    "en": "succeeded ·",
    "zh": "成功 ·"
  },
  {
    "source": "lỗi",
    "vi": "lỗi",
    "en": "errors",
    "zh": "错误"
  },
  {
    "source": "Tác vụ đăng ký",
    "vi": "Tác vụ đăng ký",
    "en": "Registration tasks",
    "zh": "注册任务"
  },
  {
    "source": "Đăng ký tài khoản",
    "vi": "Đăng ký tài khoản",
    "en": "Account registration",
    "zh": "账号注册"
  },
  {
    "source": "50 lượt gần nhất",
    "vi": "50 lượt gần nhất",
    "en": "50 most recent runs",
    "zh": "最近50次运行"
  },
  {
    "source": "{0} đang chạy",
    "vi": "{0} đang chạy",
    "en": "{0} running",
    "zh": "{0}个正在运行",
    "numericSlots": [
      0
    ]
  },
  {
    "source": "Không có tài khoản đang đăng ký",
    "vi": "Không có tài khoản đang đăng ký",
    "en": "No accounts are being registered",
    "zh": "没有正在注册的账号"
  },
  {
    "source": "Chưa có lượt đăng ký",
    "vi": "Chưa có lượt đăng ký",
    "en": "No registration runs yet",
    "zh": "暂无注册记录"
  },
  {
    "source": "Gián đoạn",
    "vi": "Gián đoạn",
    "en": "Interrupted",
    "zh": "已中断"
  },
  {
    "source": "Sai mật khẩu",
    "vi": "Sai mật khẩu",
    "en": "Incorrect password",
    "zh": "密码错误"
  },
  {
    "source": "Lỗi kiểm tra",
    "vi": "Lỗi kiểm tra",
    "en": "Check error",
    "zh": "检查错误"
  },
  {
    "source": "Dừng nhận tài khoản tiếp theo và chờ các tài khoản đang xử lý hoàn tất. Kết quả đã lưu được giữ nguyên.",
    "vi": "Dừng nhận tài khoản tiếp theo và chờ các tài khoản đang xử lý hoàn tất. Kết quả đã lưu được giữ nguyên.",
    "en": "Stop accepting new accounts and wait for active accounts to finish. Saved results are kept.",
    "zh": "停止接收后续账号并等待当前账号处理完成，已保存结果将保留。"
  },
  {
    "source": "Dừng tác vụ?",
    "vi": "Dừng tác vụ?",
    "en": "Stop task?",
    "zh": "停止任务？"
  },
  {
    "source": "Tiếp tục chạy",
    "vi": "Tiếp tục chạy",
    "en": "Keep running",
    "zh": "继续运行"
  },
  {
    "source": "Outlook 接码池",
    "vi": "Kho Outlook nhận mã",
    "en": "Outlook OTP pool",
    "zh": "Outlook 接码池"
  },
  {
    "source": "Quản lý hàng loạt · {0} đã chọn",
    "vi": "Quản lý hàng loạt · {0} đã chọn",
    "en": "Bulk management · {0} selected",
    "zh": "批量管理 · 已选择 {0} 项",
    "numericSlots": [
      0
    ]
  },
  {
    "source": "CF Worker 临时邮箱",
    "vi": "Email tạm CF Worker",
    "en": "CF Worker temporary mail",
    "zh": "CF Worker 临时邮箱"
  },
  {
    "source": "iCloud 隐藏邮箱（中转）",
    "vi": "Ẩn email iCloud (chuyển tiếp)",
    "en": "iCloud Hide My Email (relay)",
    "zh": "iCloud 隐藏邮箱（中转）"
  },
  {
    "source": "mail.com 母号（别名域名）",
    "vi": "Tài khoản gốc mail.com (tên miền bí danh)",
    "en": "mail.com parent account (alias domain)",
    "zh": "mail.com 母号（别名域名）"
  },
  {
    "source": "Worker 地址",
    "vi": "Địa chỉ Worker",
    "en": "Worker URL",
    "zh": "Worker 地址"
  },
  {
    "source": "Admin Token",
    "vi": "Token quản trị",
    "en": "Admin Token",
    "zh": "Admin Token"
  },
  {
    "source": "Cloudflare Worker 的 HTTPS 地址，末尾不带斜杠",
    "vi": "Địa chỉ HTTPS của Cloudflare Worker, không có dấu gạch chéo cuối",
    "en": "Cloudflare Worker HTTPS URL, without a trailing slash",
    "zh": "Cloudflare Worker 的 HTTPS 地址，末尾不带斜杠"
  },
  {
    "source": "Worker 环境变量 ADMIN_PASSWORDS 的值",
    "vi": "Giá trị biến môi trường ADMIN_PASSWORDS của Worker",
    "en": "Value of the Worker ADMIN_PASSWORDS environment variable",
    "zh": "Worker 环境变量 ADMIN_PASSWORDS 的值"
  },
  {
    "source": "收件域名",
    "vi": "Tên miền nhận thư",
    "en": "Receiving domain",
    "zh": "收件域名"
  },
  {
    "source": "已配置 catch-all 的域名",
    "vi": "Tên miền đã cấu hình nhận toàn bộ thư (catch-all)",
    "en": "Domain configured for catch-all mail",
    "zh": "已配置 catch-all 的域名"
  },
  {
    "source": "email----中转链接",
    "vi": "email----liên kết chuyển tiếp",
    "en": "email----relay URL",
    "zh": "email----中转链接"
  },
  {
    "source": "每行一个：email----password（mail.com 母号 + 密码）",
    "vi": "Mỗi dòng: email----password (tài khoản gốc mail.com + mật khẩu)",
    "en": "One per line: email----password (mail.com parent account + password)",
    "zh": "每行一个：email----password（mail.com 母号 + 密码）"
  },
  {
    "source": "别名域名",
    "vi": "Tên miền bí danh",
    "en": "Alias domain",
    "zh": "别名域名"
  },
  {
    "source": "目标别名使用的 mail.com 域名，实测通过 OpenAI 的域名为 usa.com, teachers.org（可填 auto 自动轮换）",
    "vi": "Tên miền mail.com dùng cho bí danh; usa.com, teachers.org đã được thử với OpenAI (nhập auto để luân phiên)",
    "en": "mail.com domain used for aliases; usa.com and teachers.org have been tested with OpenAI (enter auto to rotate)",
    "zh": "目标别名使用的 mail.com 域名，实测通过 OpenAI 的域名为 usa.com, teachers.org（可填 auto 自动轮换）"
  },
  {
    "source": "每行一个：email----password----client_id----refresh_token",
    "vi": "Mỗi dòng: email----password----client_id----refresh_token",
    "en": "One per line: email----password----client_id----refresh_token",
    "zh": "每行一个：email----password----client_id----refresh_token"
  },
  {
    "source": "导入格式 {0} 段",
    "vi": "Định dạng nhập {0} phần",
    "en": "Import format: {0} fields",
    "zh": "导入格式 {0} 段"
  },
  {
    "source": "Kiểm tra",
    "vi": "Kiểm tra",
    "en": "Check",
    "zh": "检查"
  },
  {
    "source": "Kho {0}",
    "vi": "Kho {0}",
    "en": "Pool {0}",
    "zh": "代理池 {0}",
    "numericSlots": [
      0
    ]
  },
  {
    "source": "Sai tài khoản hoặc mật khẩu",
    "vi": "Sai tài khoản hoặc mật khẩu",
    "en": "Incorrect account or password",
    "zh": "账号或密码错误"
  },
  {
    "source": "Tài khoản không tồn tại",
    "vi": "Tài khoản không tồn tại",
    "en": "Account does not exist",
    "zh": "账号不存在"
  },
  {
    "source": "Thiếu mật khẩu",
    "vi": "Thiếu mật khẩu",
    "en": "Password missing",
    "zh": "缺少密码"
  },
  {
    "source": "Mã 2FA bị từ chối; kiểm tra Secret và giờ hệ thống",
    "vi": "Mã 2FA bị từ chối; kiểm tra Secret và giờ hệ thống",
    "en": "2FA code rejected; check the secret and system clock",
    "zh": "2FA验证码被拒绝；请检查密钥和系统时间"
  },
  {
    "source": "2FA Secret sai định dạng",
    "vi": "2FA Secret sai định dạng",
    "en": "Invalid 2FA secret format",
    "zh": "2FA密钥格式错误"
  },
  {
    "source": "Thiếu 2FA Secret",
    "vi": "Thiếu 2FA Secret",
    "en": "2FA secret missing",
    "zh": "缺少2FA密钥"
  },
  {
    "source": "Tài khoản bị khóa hoặc vô hiệu hóa",
    "vi": "Tài khoản bị khóa hoặc vô hiệu hóa",
    "en": "Account blocked or deactivated",
    "zh": "账号已被封禁或停用"
  },
  {
    "source": "Mã OTP email không hợp lệ",
    "vi": "Mã OTP email không hợp lệ",
    "en": "Invalid email OTP",
    "zh": "邮箱验证码无效"
  },
  {
    "source": "Cần OTP email để đăng nhập",
    "vi": "Cần OTP email để đăng nhập",
    "en": "Email OTP required to sign in",
    "zh": "登录需要邮箱验证码"
  },
  {
    "source": "Đường nhận OTP email không dùng được; cần sửa mail/link",
    "vi": "Đường nhận OTP email không dùng được; cần sửa mail/link",
    "en": "Email OTP delivery unavailable; fix the mailbox or relay URL",
    "zh": "无法接收邮箱验证码；请修复邮箱或中转链接"
  },
  {
    "source": "Chưa nhận được OTP email trong thời gian chờ; cần kiểm tra mail",
    "vi": "Chưa nhận được OTP email trong thời gian chờ; cần kiểm tra mail",
    "en": "Email OTP not received within the timeout; check the mailbox",
    "zh": "等待超时仍未收到邮箱验证码；请检查邮箱"
  },
  {
    "source": "Proxy từ chối kết nối",
    "vi": "Proxy từ chối kết nối",
    "en": "Proxy refused the connection",
    "zh": "代理拒绝连接"
  },
  {
    "source": "Không kết nối được qua proxy",
    "vi": "Không kết nối được qua proxy",
    "en": "Unable to connect through the proxy",
    "zh": "无法通过代理连接"
  },
  {
    "source": "Không làm mới được token",
    "vi": "Không làm mới được token",
    "en": "Unable to refresh the token",
    "zh": "无法刷新令牌"
  },
  {
    "source": "Đăng nhập xong nhưng chưa nhận được token",
    "vi": "Đăng nhập xong nhưng chưa nhận được token",
    "en": "Signed in but no token was received",
    "zh": "登录成功但未收到令牌"
  },
  {
    "source": "Sai mã 2FA",
    "vi": "Sai mã 2FA",
    "en": "Incorrect 2FA code",
    "zh": "2FA验证码错误"
  },
  {
    "source": "2FA sai định dạng",
    "vi": "2FA sai định dạng",
    "en": "Invalid 2FA format",
    "zh": "2FA格式错误"
  },
  {
    "source": "Thiếu đường nhận OTP email",
    "vi": "Thiếu đường nhận OTP email",
    "en": "Email OTP delivery not configured",
    "zh": "尚未配置邮箱验证码接收方式"
  },
  {
    "source": "Mail/link nhận OTP không dùng được",
    "vi": "Mail/link nhận OTP không dùng được",
    "en": "Email OTP mailbox or relay URL unavailable",
    "zh": "邮箱验证码的邮箱或中转链接不可用"
  },
  {
    "source": "Chờ xử lý mail OTP (timeout)",
    "vi": "Chờ xử lý mail OTP (timeout)",
    "en": "Email OTP needs attention (timeout)",
    "zh": "邮箱验证码待处理（超时）"
  },
  {
    "source": "Chưa đọc được danh sách workspace hiện tại",
    "vi": "Chưa đọc được danh sách workspace hiện tại",
    "en": "Unable to read current workspaces",
    "zh": "无法读取当前工作区列表"
  },
  {
    "source": "Danh sách workspace chưa đầy đủ; chưa xác minh gói",
    "vi": "Danh sách workspace chưa đầy đủ; chưa xác minh gói",
    "en": "Workspace list incomplete; plan not verified",
    "zh": "工作区列表不完整；套餐尚未验证"
  },
  {
    "source": "Chưa xác nhận được quyền truy cập workspace hiện tại",
    "vi": "Chưa xác nhận được quyền truy cập workspace hiện tại",
    "en": "Current workspace access not confirmed",
    "zh": "尚未确认当前工作区访问权限"
  },
  {
    "source": "API không trả dữ liệu thuê bao",
    "vi": "API không trả dữ liệu thuê bao",
    "en": "API returned no subscription data",
    "zh": "API未返回订阅数据"
  },
  {
    "source": "Chưa đọc đủ thuê bao của các workspace hiện tại",
    "vi": "Chưa đọc đủ thuê bao của các workspace hiện tại",
    "en": "Subscription data incomplete for current workspaces",
    "zh": "当前工作区的订阅数据不完整"
  },
  {
    "source": "Workspace thiếu bằng chứng thành viên hiện tại",
    "vi": "Workspace thiếu bằng chứng thành viên hiện tại",
    "en": "Workspace is missing current membership evidence",
    "zh": "工作区缺少当前成员身份依据"
  },
  {
    "source": "Danh sách thành viên workspace có dữ liệu mâu thuẫn",
    "vi": "Danh sách thành viên workspace có dữ liệu mâu thuẫn",
    "en": "Conflicting workspace membership data",
    "zh": "工作区成员数据存在冲突"
  },
  {
    "source": "Quyền truy cập workspace và dữ liệu thuê bao chưa khớp",
    "vi": "Quyền truy cập workspace và dữ liệu thuê bao chưa khớp",
    "en": "Workspace access and subscription data do not match",
    "zh": "工作区访问权限与订阅数据不一致"
  },
  {
    "source": "Workspace chưa có dữ liệu thuê bao",
    "vi": "Workspace chưa có dữ liệu thuê bao",
    "en": "Workspace has no subscription data",
    "zh": "工作区尚无订阅数据"
  },
  {
    "source": "API trả loại thuê bao chưa nhận diện được",
    "vi": "API trả loại thuê bao chưa nhận diện được",
    "en": "API returned an unrecognized subscription type",
    "zh": "API返回了无法识别的订阅类型"
  },
  {
    "source": "API trả loại gói chưa nhận diện được",
    "vi": "API trả loại gói chưa nhận diện được",
    "en": "API returned an unrecognized plan type",
    "zh": "API返回了无法识别的套餐类型"
  },
  {
    "source": "Trạng thái thuê bao không hợp lệ",
    "vi": "Trạng thái thuê bao không hợp lệ",
    "en": "Invalid subscription status",
    "zh": "订阅状态无效"
  },
  {
    "source": "API báo thuê bao hoạt động nhưng hạn đã qua; cần kiểm tra lại",
    "vi": "API báo thuê bao hoạt động nhưng hạn đã qua; cần kiểm tra lại",
    "en": "API reports an active subscription past its expiry; recheck required",
    "zh": "API报告订阅有效但已过期；需要重新检查"
  },
  {
    "source": "API trả gói mâu thuẫn cho cùng workspace",
    "vi": "API trả gói mâu thuẫn cho cùng workspace",
    "en": "API returned conflicting plans for the same workspace",
    "zh": "API为同一工作区返回了冲突的套餐"
  },
  {
    "source": "Chưa đọc được ưu đãi; gói tài khoản đã xác minh riêng",
    "vi": "Chưa đọc được ưu đãi; gói tài khoản đã xác minh riêng",
    "en": "Offers unavailable; account plan verified separately",
    "zh": "无法读取优惠；账号套餐已单独验证"
  },
  {
    "source": "Gói và trạng thái thuê bao chưa khớp; chưa thể kết luận",
    "vi": "Gói và trạng thái thuê bao chưa khớp; chưa thể kết luận",
    "en": "Plan and subscription status do not match; no conclusion yet",
    "zh": "套餐与订阅状态不一致；暂时无法判断"
  },
  {
    "source": "API gói trả nội dung không phải JSON",
    "vi": "API gói trả nội dung không phải JSON",
    "en": "Plan API returned a non-JSON response",
    "zh": "套餐API返回的内容不是JSON"
  },
  {
    "source": "AT không còn dùng được",
    "vi": "AT không còn dùng được",
    "en": "AT is no longer usable",
    "zh": "AT已不可用"
  },
  {
    "source": "API {0} trả HTTP {1}",
    "vi": "API {0} trả HTTP {1}",
    "en": "API {0} returned HTTP {1}",
    "zh": "API {0} 返回HTTP {1}"
  },
  {
    "source": "Không đọc được gói qua proxy: ",
    "vi": "Không đọc được gói qua proxy: ",
    "en": "Unable to read the plan through the proxy: ",
    "zh": "无法通过代理读取套餐："
  },
  {
    "source": "thuê bao",
    "vi": "thuê bao",
    "en": "subscription",
    "zh": "订阅"
  },
  {
    "source": "Tài khoản nhập ngoài",
    "vi": "Tài khoản nhập ngoài",
    "en": "Imported external account",
    "zh": "外部导入的账号"
  },
  {
    "source": "Proxy từ chối kết nối. Kiểm tra IP/cổng, tài khoản/mật khẩu và quyền truy cập proxy.",
    "vi": "Proxy từ chối kết nối. Kiểm tra IP/cổng, tài khoản/mật khẩu và quyền truy cập proxy.",
    "en": "Proxy refused the connection. Check its host, port, credentials and access permissions.",
    "zh": "代理拒绝连接。请检查地址、端口、账号密码和访问权限。"
  },
  {
    "source": "Không kết nối được qua proxy hoặc kết nối bị ngắt. Kiểm tra trạng thái và đường truyền proxy.",
    "vi": "Không kết nối được qua proxy hoặc kết nối bị ngắt. Kiểm tra trạng thái và đường truyền proxy.",
    "en": "Proxy connection failed or was interrupted. Check the proxy status and network.",
    "zh": "代理连接失败或中断。请检查代理状态和网络。"
  },
  {
    "source": "Tài khoản {0} không có cấu hình hòm thư nhận OTP email. Nếu tài khoản yêu cầu xác nhận email, vui lòng kiểm tra hòm thư thủ công.",
    "vi": "Tài khoản {0} không có cấu hình hòm thư nhận OTP email. Nếu tài khoản yêu cầu xác nhận email, vui lòng kiểm tra hòm thư thủ công.",
    "en": "Account {0} has no mailbox configured for email OTP. Check the mailbox manually if email verification is required.",
    "zh": "账号 {0} 未配置接收邮箱验证码的邮箱。如需邮箱验证，请手动检查邮箱。"
  },
  {
    "source": "Bỏ qua: AT còn hạn theo JWT; chưa quét API lại",
    "vi": "Bỏ qua: AT còn hạn theo JWT; chưa quét API lại",
    "en": "Skipped: AT is unexpired by JWT; API not rechecked",
    "zh": "已跳过：JWT显示AT未过期；未重新调用API"
  },
  {
    "source": "Chưa có Access Token",
    "vi": "Chưa có Access Token",
    "en": "No Access Token",
    "zh": "没有Access Token"
  },
  {
    "source": "Token đã hết hạn (JWT exp)",
    "vi": "Token đã hết hạn (JWT exp)",
    "en": "Token expired (JWT exp)",
    "zh": "令牌已过期（JWT exp）"
  },
  {
    "source": "Kiểm tra mạng trả HTTP {0}; chưa thực hiện đăng nhập.",
    "vi": "Kiểm tra mạng trả HTTP {0}; chưa thực hiện đăng nhập.",
    "en": "Network check returned HTTP {0}; sign-in was not attempted.",
    "zh": "网络检查返回HTTP {0}；尚未尝试登录。"
  },
  {
    "source": "Bỏ qua: AT đã được ghi nhận dùng được; chưa quét API lại",
    "vi": "Bỏ qua: AT đã được ghi nhận dùng được; chưa quét API lại",
    "en": "Skipped: AT was previously verified usable; API not rechecked",
    "zh": "已跳过：AT此前已验证可用；未重新调用API"
  },
  {
    "source": "Token hoạt động (HTTP 200)",
    "vi": "Token hoạt động (HTTP 200)",
    "en": "Token works (HTTP 200)",
    "zh": "令牌可用（HTTP 200）"
  },
  {
    "source": "Lỗi kiểm tra mạng: {0}",
    "vi": "Lỗi kiểm tra mạng: {0}",
    "en": "Network check failed: {0}",
    "zh": "网络检查失败：{0}",
    "translateSlots": [
      0
    ]
  },
  {
    "source": "Token hết hạn hoặc bị thu hồi (HTTP 401)",
    "vi": "Token hết hạn hoặc bị thu hồi (HTTP 401)",
    "en": "Token expired or revoked (HTTP 401)",
    "zh": "令牌已过期或被撤销（HTTP 401）"
  },
  {
    "source": "Tài khoản bị khóa hoặc vô hiệu hóa (HTTP 403)",
    "vi": "Tài khoản bị khóa hoặc vô hiệu hóa (HTTP 403)",
    "en": "Account blocked or deactivated (HTTP 403)",
    "zh": "账号已被封禁或停用（HTTP 403）"
  },
  {
    "source": "Máy chủ phản hồi HTTP {0}",
    "vi": "Máy chủ phản hồi HTTP {0}",
    "en": "Server returned HTTP {0}",
    "zh": "服务器返回HTTP {0}"
  },
  {
    "source": "Làm mới thành công qua 2FA",
    "vi": "Làm mới thành công qua 2FA",
    "en": "Refreshed successfully using 2FA",
    "zh": "通过2FA刷新成功"
  },
  {
    "source": "Làm mới thành công qua Refresh Token",
    "vi": "Làm mới thành công qua Refresh Token",
    "en": "Refreshed successfully using a Refresh Token",
    "zh": "通过Refresh Token刷新成功"
  },
  {
    "source": "Đang có tác vụ quét/làm mới token. Hãy chờ hoàn tất hoặc dừng tác vụ hiện tại.",
    "vi": "Đang có tác vụ quét/làm mới token. Hãy chờ hoàn tất hoặc dừng tác vụ hiện tại.",
    "en": "A token check or refresh is running. Wait for it to finish or stop the current task.",
    "zh": "令牌检查或刷新正在运行。请等待完成或停止当前任务。"
  },
  {
    "source": "Loại tác vụ token không hợp lệ.",
    "vi": "Loại tác vụ token không hợp lệ.",
    "en": "Invalid token task type.",
    "zh": "令牌任务类型无效。"
  },
  {
    "source": "Số worker phải từ 1 đến {0}.",
    "vi": "Số worker phải từ 1 đến {0}.",
    "en": "Worker count must be between 1 and {0}.",
    "zh": "并发数必须在1到 {0} 之间。"
  },
  {
    "source": "Chế độ proxy không hợp lệ.",
    "vi": "Chế độ proxy không hợp lệ.",
    "en": "Invalid proxy mode.",
    "zh": "代理模式无效。"
  },
  {
    "source": "Dò Plus dùng Kho Proxy hoặc proxy riêng như cấu hình hiện có.",
    "vi": "Dò Plus dùng Kho Proxy hoặc proxy riêng như cấu hình hiện có.",
    "en": "Plus checks use the proxy pool or custom proxy from the current configuration.",
    "zh": "Plus检查使用当前配置的代理池或自定义代理。"
  },
  {
    "source": "Chọn ít nhất một tài khoản cho tác vụ.",
    "vi": "Chọn ít nhất một tài khoản cho tác vụ.",
    "en": "Select at least one account for the task.",
    "zh": "请为任务选择至少一个账号。"
  },
  {
    "source": "Đã dừng theo yêu cầu. Các kết quả đã hoàn tất vẫn được giữ; phần còn lại chưa được xử lý.",
    "vi": "Đã dừng theo yêu cầu. Các kết quả đã hoàn tất vẫn được giữ; phần còn lại chưa được xử lý.",
    "en": "Stopped as requested. Completed results are saved; remaining accounts were not processed.",
    "zh": "已按要求停止。已完成的结果已保存，其余账号尚未处理。"
  },
  {
    "source": "Chức năng này dành cho lỗi làm mới token.",
    "vi": "Chức năng này dành cho lỗi làm mới token.",
    "en": "This feature is for token refresh failures.",
    "zh": "此功能适用于令牌刷新失败的账号。"
  },
  {
    "source": "Hãy chờ đợt hiện tại kết thúc hoặc dừng an toàn trước khi thử lại.",
    "vi": "Hãy chờ đợt hiện tại kết thúc hoặc dừng an toàn trước khi thử lại.",
    "en": "Wait for the current batch to finish or stop it safely before retrying.",
    "zh": "请等待当前批次完成或安全停止后再重试。"
  },
  {
    "source": "Chỉ thử lại các lỗi làm mới token bằng chế độ này.",
    "vi": "Chỉ thử lại các lỗi làm mới token bằng chế độ này.",
    "en": "This mode retries token refresh failures only.",
    "zh": "此模式仅重试令牌刷新失败的账号。"
  },
  {
    "source": "Danh sách thử lại có tài khoản thành công hoặc lỗi xác thực không được phép thử lại.",
    "vi": "Danh sách thử lại có tài khoản thành công hoặc lỗi xác thực không được phép thử lại.",
    "en": "The retry list includes successful accounts or authentication failures that cannot be retried.",
    "zh": "重试列表包含已成功账号或不允许重试的身份验证失败账号。"
  },
  {
    "source": "Dò checkout đang tắt trong cấu hình.",
    "vi": "Dò checkout đang tắt trong cấu hình.",
    "en": "Checkout probing is disabled in settings.",
    "zh": "配置中已关闭结账探测。"
  },
  {
    "source": "Không quét được tài khoản: {0}",
    "vi": "Không quét được tài khoản: {0}",
    "en": "Unable to check account: {0}",
    "zh": "无法检查账号：{0}",
    "translateSlots": [
      0
    ]
  },
  {
    "source": "Dịch vụ đã khởi động lại. Các kết quả đã hoàn tất vẫn được giữ; hãy kiểm tra trước khi chạy lại.",
    "vi": "Dịch vụ đã khởi động lại. Các kết quả đã hoàn tất vẫn được giữ; hãy kiểm tra trước khi chạy lại.",
    "en": "The service restarted. Completed results are saved; check before running again.",
    "zh": "服务已重启。已完成的结果已保存，请检查后再运行。"
  },
  {
    "source": "Mã yêu cầu này đã được dùng cho danh sách hoặc cấu hình khác.",
    "vi": "Mã yêu cầu này đã được dùng cho danh sách hoặc cấu hình khác.",
    "en": "This request ID was already used for a different list or configuration.",
    "zh": "此请求编号已用于其他列表或配置。"
  },
  {
    "source": "Tác vụ bị gián đoạn. Các kết quả đã hoàn tất vẫn được giữ.",
    "vi": "Tác vụ bị gián đoạn. Các kết quả đã hoàn tất vẫn được giữ.",
    "en": "Task interrupted. Completed results are saved.",
    "zh": "任务已中断。已完成的结果已保存。"
  },
  {
    "source": "Không nhận được kết quả dò Plus",
    "vi": "Không nhận được kết quả dò Plus",
    "en": "No Plus probe result was received",
    "zh": "未收到Plus探测结果"
  },
  {
    "source": "Quét AT bị gián đoạn. Các kết quả đã hoàn tất vẫn được giữ.",
    "vi": "Quét AT bị gián đoạn. Các kết quả đã hoàn tất vẫn được giữ.",
    "en": "AT check interrupted. Completed results are saved.",
    "zh": "AT检查已中断。已完成的结果已保存。"
  },
  {
    "source": "Kho Proxy đang trống. Hãy thêm proxy hoặc chọn chế độ proxy riêng/trực tiếp.",
    "vi": "Kho Proxy đang trống. Hãy thêm proxy hoặc chọn chế độ proxy riêng/trực tiếp.",
    "en": "The proxy pool is empty. Add proxies or choose custom proxy / direct mode.",
    "zh": "代理池为空。请添加代理或选择自定义代理／直连模式。"
  },
  {
    "source": "Không khởi động được tác vụ. Vui lòng thử lại.",
    "vi": "Không khởi động được tác vụ. Vui lòng thử lại.",
    "en": "Unable to start the task. Please retry.",
    "zh": "无法启动任务，请重试。"
  },
  {
    "source": "Đã dừng theo yêu cầu. Các tài khoản chưa xử lý được giữ lại.",
    "vi": "Đã dừng theo yêu cầu. Các tài khoản chưa xử lý được giữ lại.",
    "en": "Stopped as requested. Unprocessed accounts are kept.",
    "zh": "已按要求停止，未处理账号已保留。"
  },
  {
    "source": "Không còn proxy kết nối được trong đợt này.",
    "vi": "Không còn proxy kết nối được trong đợt này.",
    "en": "No working proxy remains in this batch.",
    "zh": "本批次已无可连接的代理。"
  },
  {
    "source": "Đã thử {0}/{1} proxy trong kho nhưng không kết nối được. ",
    "vi": "Đã thử {0}/{1} proxy trong kho nhưng không kết nối được. ",
    "en": "Tried {0}/{1} proxies in the pool without a connection. ",
    "zh": "已尝试代理池中的 {0}/{1} 个代理，均无法连接。"
  },
  {
    "source": "Proxy riêng đang chọn không kết nối được. ",
    "vi": "Proxy riêng đang chọn không kết nối được. ",
    "en": "The selected custom proxy is unavailable. ",
    "zh": "所选自定义代理无法连接。"
  },
  {
    "source": "Không còn proxy kết nối được trong kho. Các tài khoản còn lại chưa được chạy.",
    "vi": "Không còn proxy kết nối được trong kho. Các tài khoản còn lại chưa được chạy.",
    "en": "No working proxy remains in the pool. Remaining accounts were not started.",
    "zh": "代理池已无可连接的代理，其余账号尚未运行。"
  },
  {
    "source": "Dịch vụ đang giới hạn tốc độ. Các tài khoản còn lại chưa được chạy.",
    "vi": "Dịch vụ đang giới hạn tốc độ. Các tài khoản còn lại chưa được chạy.",
    "en": "Service rate limit reached. Remaining accounts were not started.",
    "zh": "服务正在限速，其余账号尚未运行。"
  },
  {
    "source": "Dò checkout hoàn tất",
    "vi": "Dò checkout hoàn tất",
    "en": "Checkout probing complete",
    "zh": "结账探测完成"
  },
  {
    "source": "Dịch vụ đang giới hạn tốc độ. Đã giữ kết quả; các tài khoản còn lại chưa được chạy.",
    "vi": "Dịch vụ đang giới hạn tốc độ. Đã giữ kết quả; các tài khoản còn lại chưa được chạy.",
    "en": "Service rate limit reached. Results are saved; remaining accounts were not started.",
    "zh": "服务正在限速。结果已保存，其余账号尚未运行。"
  },
  {
    "source": "Các tài khoản còn lại chưa được xử lý.",
    "vi": "Các tài khoản còn lại chưa được xử lý.",
    "en": "Remaining accounts have not been processed.",
    "zh": "其余账号尚未处理。"
  },
  {
    "source": "Đã dừng theo yêu cầu. Các kết quả đã có vẫn được giữ.",
    "vi": "Đã dừng theo yêu cầu. Các kết quả đã có vẫn được giữ.",
    "en": "Stopped as requested. Existing results are saved.",
    "zh": "已按要求停止，已有结果已保存。"
  },
  {
    "source": "印度",
    "vi": "Ấn Độ",
    "en": "India",
    "zh": "印度"
  },
  {
    "source": "美国",
    "vi": "Hoa Kỳ",
    "en": "United States",
    "zh": "美国"
  },
  {
    "source": "印尼",
    "vi": "Indonesia",
    "en": "Indonesia",
    "zh": "印尼"
  },
  {
    "source": "巴西",
    "vi": "Brazil",
    "en": "Brazil",
    "zh": "巴西"
  },
  {
    "source": "土耳其",
    "vi": "Thổ Nhĩ Kỳ",
    "en": "Turkey",
    "zh": "土耳其"
  },
  {
    "source": "菲律宾",
    "vi": "Philippines",
    "en": "Philippines",
    "zh": "菲律宾"
  },
  {
    "source": "泰国",
    "vi": "Thái Lan",
    "en": "Thailand",
    "zh": "泰国"
  },
  {
    "source": "越南",
    "vi": "Việt Nam",
    "en": "Vietnam",
    "zh": "越南"
  },
  {
    "source": "日本",
    "vi": "Nhật Bản",
    "en": "Japan",
    "zh": "日本"
  },
  {
    "source": "新加坡",
    "vi": "Singapore",
    "en": "Singapore",
    "zh": "新加坡"
  },
  {
    "source": "英国",
    "vi": "Vương quốc Anh",
    "en": "United Kingdom",
    "zh": "英国"
  },
  {
    "source": "德国",
    "vi": "Đức",
    "en": "Germany",
    "zh": "德国"
  },
  {
    "source": "韩国",
    "vi": "Hàn Quốc",
    "en": "South Korea",
    "zh": "韩国"
  },
  {
    "source": "马来西亚",
    "vi": "Malaysia",
    "en": "Malaysia",
    "zh": "马来西亚"
  },
  {
    "source": "台湾",
    "vi": "Đài Loan",
    "en": "Taiwan",
    "zh": "台湾"
  },
  {
    "source": "香港",
    "vi": "Hồng Kông",
    "en": "Hong Kong",
    "zh": "香港"
  },
  {
    "source": "澳大利亚",
    "vi": "Úc",
    "en": "Australia",
    "zh": "澳大利亚"
  },
  {
    "source": "加拿大",
    "vi": "Canada",
    "en": "Canada",
    "zh": "加拿大"
  },
  {
    "source": "法国",
    "vi": "Pháp",
    "en": "France",
    "zh": "法国"
  },
  {
    "source": "荷兰",
    "vi": "Hà Lan",
    "en": "Netherlands",
    "zh": "荷兰"
  },
  {
    "source": "需要 status 或 emails",
    "vi": "Cần cung cấp status hoặc emails",
    "en": "Provide status or emails",
    "zh": "需要status或emails"
  },
  {
    "source": "需要 emails 或 all=true",
    "vi": "Cần cung cấp emails hoặc all=true",
    "en": "Provide emails or all=true",
    "zh": "需要emails或all=true"
  },
  {
    "source": "不支持的浏览器家族策略: {0}",
    "vi": "Chính sách dòng trình duyệt không được hỗ trợ: {0}",
    "en": "Unsupported browser family policy: {0}",
    "zh": "不支持的浏览器家族策略：{0}"
  },
  {
    "source": "不支持的浏览器引擎: {0}",
    "vi": "Động cơ trình duyệt không được hỗ trợ: {0}",
    "en": "Unsupported browser engine: {0}",
    "zh": "不支持的浏览器引擎：{0}"
  },
  {
    "source": "Camoufox 只能配 Firefox 家族画像",
    "vi": "Camoufox cần hồ sơ Firefox",
    "en": "Camoufox requires a Firefox profile",
    "zh": "Camoufox只能使用Firefox画像"
  },
  {
    "source": "支付能力探测已在设置里关闭",
    "vi": "Dò khả năng thanh toán đang tắt trong cài đặt",
    "en": "Payment probing is disabled in settings",
    "zh": "支付能力探测已在设置中关闭"
  },
  {
    "source": "邮箱 {0} 不存在",
    "vi": "Hòm thư {0} không tồn tại",
    "en": "Mailbox {0} does not exist",
    "zh": "邮箱 {0} 不存在"
  },
  {
    "source": "emails 不能为空",
    "vi": "Danh sách emails không được trống",
    "en": "emails cannot be empty",
    "zh": "emails不能为空"
  },
  {
    "source": "proxies 不能为空",
    "vi": "Danh sách proxies không được trống",
    "en": "proxies cannot be empty",
    "zh": "proxies不能为空"
  },
  {
    "source": "不支持的注册引擎: {0}",
    "vi": "Động cơ đăng ký không được hỗ trợ: {0}",
    "en": "Unsupported registration engine: {0}",
    "zh": "不支持的注册引擎：{0}"
  },
  {
    "source": "Không tìm thấy tác vụ làm mới token.",
    "vi": "Không tìm thấy tác vụ làm mới token.",
    "en": "Token refresh task not found.",
    "zh": "找不到令牌刷新任务。"
  },
  {
    "source": "Không tìm thấy tài khoản.",
    "vi": "Không tìm thấy tài khoản.",
    "en": "Account not found.",
    "zh": "找不到账号。"
  },
  {
    "source": "Tài khoản đang chờ hoặc đang được xử lý; hãy xóa sau khi lượt này kết thúc.",
    "vi": "Tài khoản đang chờ hoặc đang được xử lý; hãy xóa sau khi lượt này kết thúc.",
    "en": "Account is queued or processing; delete it after this batch ends.",
    "zh": "账号正在排队或处理中，请在本批次结束后再删除。"
  },
  {
    "source": "未知导出格式: {0}",
    "vi": "Định dạng xuất không xác định: {0}",
    "en": "Unknown export format: {0}",
    "zh": "未知导出格式：{0}"
  },
  {
    "source": "{0} 是号池类型，不需要单独测试；导入时会校验格式",
    "vi": "{0} dùng kho mail, không cần kiểm tra riêng; định dạng được kiểm tra khi nhập",
    "en": "{0} uses the mail pool and needs no separate test; import validates the format",
    "zh": "{0}使用邮箱池，无需单独测试；导入时会校验格式",
    "translateSlots": [
      0
    ]
  },
  {
    "source": "连接成功",
    "vi": "Kết nối thành công",
    "en": "Connected successfully",
    "zh": "连接成功"
  },
  {
    "source": "未配置 sms_api_key",
    "vi": "Chưa cấu hình sms_api_key",
    "en": "sms_api_key is not configured",
    "zh": "未配置sms_api_key"
  },
  {
    "source": "连接成功，余额: {0}",
    "vi": "Kết nối thành công; số dư: {0}",
    "en": "Connected successfully; balance: {0}",
    "zh": "连接成功，余额：{0}"
  },
  {
    "source": "未知 target: {0}",
    "vi": "Đích không xác định: {0}",
    "en": "Unknown target: {0}",
    "zh": "未知目标：{0}"
  },
  {
    "source": "未找到已注册账号: {0}",
    "vi": "Không tìm thấy tài khoản đã đăng ký: {0}",
    "en": "Registered account not found: {0}",
    "zh": "未找到已注册账号：{0}"
  },
  {
    "source": "email 不能为空",
    "vi": "Email không được trống",
    "en": "email cannot be empty",
    "zh": "email不能为空"
  },
  {
    "source": "没有要修改的字段",
    "vi": "Không có trường cần sửa",
    "en": "No fields to update",
    "zh": "没有需要修改的字段"
  },
  {
    "source": "countries 不能为空",
    "vi": "Danh sách quốc gia không được trống",
    "en": "countries cannot be empty",
    "zh": "countries不能为空"
  },
  {
    "source": "{0}0元试用",
    "vi": "{0}dùng thử miễn phí",
    "en": "{0}free trial",
    "zh": "{0}免费试用"
  },
  {
    "source": "补货失败: {0}",
    "vi": "Bổ sung thất bại: {0}",
    "en": "Restock failed: {0}",
    "zh": "补货失败：{0}",
    "translateSlots": [
      0
    ]
  },
  {
    "source": "导入已购邮箱失败: {0}",
    "vi": "Nhập email đã mua thất bại: {0}",
    "en": "Purchased mail import failed: {0}",
    "zh": "导入已购邮箱失败：{0}",
    "translateSlots": [
      0
    ]
  },
  {
    "source": "加载 http_client 失败: {0}",
    "vi": "Không tải được http_client: {0}",
    "en": "Failed to load http_client: {0}",
    "zh": "加载http_client失败：{0}",
    "translateSlots": [
      0
    ]
  },
  {
    "source": "Không tìm thấy đợt làm mới token gốc.",
    "vi": "Không tìm thấy đợt làm mới token gốc.",
    "en": "Original token refresh batch not found.",
    "zh": "找不到原令牌刷新批次。"
  },
  {
    "source": "Không tìm thấy đợt làm mới token.",
    "vi": "Không tìm thấy đợt làm mới token.",
    "en": "Token refresh batch not found.",
    "zh": "找不到令牌刷新批次。"
  },
  {
    "source": "提交失败: {0}",
    "vi": "Gửi thất bại: {0}",
    "en": "Submission failed: {0}",
    "zh": "提交失败：{0}",
    "translateSlots": [
      0
    ]
  },
  {
    "source": "同步失败: {0}",
    "vi": "Đồng bộ thất bại: {0}",
    "en": "Sync failed: {0}",
    "zh": "同步失败：{0}",
    "translateSlots": [
      0
    ]
  },
  {
    "source": "授权提交失败: {0}",
    "vi": "Gửi ủy quyền thất bại: {0}",
    "en": "Authorization submission failed: {0}",
    "zh": "授权提交失败：{0}",
    "translateSlots": [
      0
    ]
  },
  {
    "source": "构造 {0} 失败: {1}",
    "vi": "Không khởi tạo được {0}: {1}",
    "en": "Failed to initialize {0}: {1}",
    "zh": "初始化 {0} 失败：{1}",
    "translateSlots": [
      0,
      1
    ]
  },
  {
    "source": "连接失败: {0}",
    "vi": "Kết nối thất bại: {0}",
    "en": "Connection failed: {0}",
    "zh": "连接失败：{0}",
    "translateSlots": [
      0
    ]
  },
  {
    "source": "查询失败: {0}",
    "vi": "Truy vấn thất bại: {0}",
    "en": "Query failed: {0}",
    "zh": "查询失败：{0}",
    "translateSlots": [
      0
    ]
  },
  {
    "source": "测试失败: {0}",
    "vi": "Kiểm tra thất bại: {0}",
    "en": "Test failed: {0}",
    "zh": "测试失败：{0}",
    "translateSlots": [
      0
    ]
  },
  {
    "source": "福利国均未命中",
    "vi": "Không có quốc gia đủ điều kiện ưu đãi",
    "en": "No eligible offer country found",
    "zh": "福利国家均未命中"
  },
  {
    "source": "未检出",
    "vi": "Chưa phát hiện",
    "en": "Not detected",
    "zh": "未检出"
  },
  {
    "source": "启动失败",
    "vi": "Khởi chạy thất bại",
    "en": "Start failed",
    "zh": "启动失败"
  },
  {
    "source": "暂停失败",
    "vi": "Tạm dừng thất bại",
    "en": "Pause failed",
    "zh": "暂停失败"
  },
  {
    "source": "恢复失败",
    "vi": "Tiếp tục thất bại",
    "en": "Resume failed",
    "zh": "恢复失败"
  },
  {
    "source": "停止失败",
    "vi": "Dừng thất bại",
    "en": "Stop failed",
    "zh": "停止失败"
  },
  {
    "source": "邮箱 {0} 不可用 (不存在 / 已 in_use / 已完成)",
    "vi": "Hòm thư {0} không khả dụng (không tồn tại, đang dùng hoặc đã hoàn tất)",
    "en": "Mailbox {0} is unavailable (missing, in use or completed)",
    "zh": "邮箱 {0} 不可用（不存在、使用中或已完成）"
  },
  {
    "source": "{0} 是 {1} 的号，当前邮箱来源是 {2}，请先切换来源",
    "vi": "{0} thuộc nguồn {1}; nguồn mail hiện tại là {2}. Hãy chuyển nguồn trước.",
    "en": "{0} belongs to {1}; the current mail source is {2}. Switch the source first.",
    "zh": "{0}属于 {1}，当前邮箱来源是 {2}，请先切换来源。",
    "translateSlots": [
      1,
      2
    ]
  },
  {
    "source": "号池里没有 available 的 {0} 账号；请先批量导入",
    "vi": "Kho mail không có tài khoản {0} khả dụng; hãy nhập trước",
    "en": "No available {0} accounts in the pool; import accounts first",
    "zh": "邮箱池没有可用的 {0} 账号，请先导入",
    "translateSlots": [
      0
    ]
  },
  {
    "source": "可领Plus试用",
    "vi": "Đủ điều kiện dùng thử Plus",
    "en": "Plus trial eligible",
    "zh": "可领取Plus试用"
  },
  {
    "source": "Không tìm thấy tài khoản",
    "vi": "Không tìm thấy tài khoản",
    "en": "Account not found",
    "zh": "找不到账号"
  },
  {
    "source": "国家{0}",
    "vi": "Quốc gia {0}",
    "en": "Country {0}",
    "zh": "国家 {0}"
  },
  {
    "source": "Cần làm mới AT trước khi quét gói",
    "vi": "Cần làm mới AT trước khi quét gói",
    "en": "Refresh AT before checking the plan",
    "zh": "请先刷新AT再检查套餐"
  },
  {
    "source": "AT bị từ chối; không làm mới được: ",
    "vi": "AT bị từ chối; không làm mới được: ",
    "en": "AT rejected; refresh failed: ",
    "zh": "AT被拒绝，刷新失败："
  },
  {
    "source": "Không làm mới được AT: ",
    "vi": "Không làm mới được AT: ",
    "en": "Unable to refresh AT: ",
    "zh": "无法刷新AT："
  },
  {
    "source": "AT bị từ chối; ",
    "vi": "AT bị từ chối; ",
    "en": "AT rejected; ",
    "zh": "AT被拒绝；"
  },
  {
    "source": "Cập nhật",
    "vi": "Cập nhật",
    "en": "Update",
    "zh": "更新"
  },
  {
    "source": "Đang chạy",
    "vi": "Đang chạy",
    "en": "Running",
    "zh": "正在运行"
  },
  {
    "source": "Network Error",
    "vi": "Lỗi kết nối mạng",
    "en": "Network error",
    "zh": "网络连接错误"
  },
  {
    "source": "Request failed with status code {0}",
    "vi": "Yêu cầu thất bại, mã HTTP {0}",
    "en": "Request failed with HTTP status {0}",
    "zh": "请求失败，HTTP状态码 {0}"
  },
  {
    "source": "timeout of {0}ms exceeded",
    "vi": "Quá thời gian chờ {0}ms",
    "en": "Request timed out after {0}ms",
    "zh": "请求等待超过 {0}ms"
  }
]
