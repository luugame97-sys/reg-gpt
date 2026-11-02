import viDict from '@/locales/vi'
import enDict from '@/locales/en'
import zhDict from '@/locales/zh'
import uiPhrases from '@/locales/ui'
import { readStoredLocale, validLocale } from './locale'

const normalize = text => text.replace(/\s+/g, ' ').trim()
const entries = Object.keys({...zhDict, ...viDict, ...enDict}).map(source => ({source, vi:viDict[source] ?? source, en:enDict[source] ?? source, zh:zhDict[source] ?? source}))
entries.push(...uiPhrases)
const exact = new Map()
const aliases = new Map()
const patterns = []
const escapeRegex = text => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
for (const entry of entries) {
  exact.set(normalize(entry.source), entry)
  for (const lang of ['vi','en','zh']) aliases.set(normalize(entry[lang]), entry)
}
for (const entry of uiPhrases) {
  for (const text of new Set([entry.source, entry.vi, entry.en, entry.zh])) {
    if (!/\{\d+\}/.test(text)) continue
    const slots = []
    const parts = normalize(text).split(/(\{\d+\})/g).map(part => {
      if (/^\{\d+\}$/.test(part)) { slots.push(part); return entry.numericSlots?.includes(Number(part.slice(1,-1))) ? '([\\d.,+−-]+)' : '(.*?)' }
      return escapeRegex(part).replace(/ +/g, '\\s+')
    })
    patterns.push({regex:new RegExp('^'+parts.join('')+'$', 'u'),slots,entry,weight:normalize(text).replace(/\{\d+\}/g,'').length})
  }
}
patterns.sort((a,b)=>b.weight-a.weight)
// Only replace catalogued phrases, respecting word boundaries for Latin text.
const fragments = [...new Set(entries.flatMap(entry=>[entry.source,entry.vi,entry.en,entry.zh]))]
  .filter(text=>text.length>=2&&!/\{\d+\}/.test(text))
  .sort((a,b)=>b.length-a.length)
const fragmentTree = new Map()
for (const phrase of fragments) {
  let node = fragmentTree
  for (const character of phrase) {
    if (!node.has(character)) node.set(character, new Map())
    node = node.get(character)
  }
  node.phrase = phrase
}
const wordCharacter = character => !!character && /[\p{L}\p{N}_@-]/u.test(character)
function translateFragments(text, lang) {
  let result = ''
  for (let index = 0; index < text.length;) {
    let node = fragmentTree, match, end = index
    for (let offset = index; offset < text.length && node.has(text[offset]); offset++) {
      node = node.get(text[offset])
      const phrase = node.phrase
      if (!phrase) continue
      const latinStart = /^[\p{L}\p{N}]/u.test(phrase) && !/^\p{Script=Han}/u.test(phrase)
      const latinEnd = /[\p{L}\p{N}]$/u.test(phrase) && !/\p{Script=Han}$/u.test(phrase)
      if ((latinStart && wordCharacter(text[index-1])) || (latinEnd && wordCharacter(text[offset+1]))) continue
      match = phrase; end = offset+1
    }
    if (match) {
      const entry = exact.get(normalize(match)) || aliases.get(normalize(match))
      result += entry?.[lang] || match
      index = end
    } else result += text[index++]
  }
  return result
}
const cache = new Map()
const dynamicOrigins = new Map()

const dynamicPatterns = [
  // 1. Counts, Rows & Selection
  { pattern: /共\s*(\d+)\s*行/g, vi: 'Tổng cộng $1 dòng', en: 'Total $1 rows' },
  { pattern: /共\s*(\d+)\s*条/g, vi: 'Tổng cộng $1 mục', en: 'Total $1 items' },
  { pattern: /待导入\s*(\d+)\s*行/g, vi: 'Chờ nhập $1 dòng', en: 'Pending import $1 rows' },
  { pattern: /，已选\s*(\d+)\s*条/g, vi: ', Đã chọn $1 mục', en: ', Selected $1 items' },
  { pattern: /已选\s*(\d+)\s*条/g, vi: 'Đã chọn $1 mục', en: 'Selected $1 items' },
  { pattern: /已选\s*(\d+)\s*个国家/g, vi: 'Đã chọn $1 quốc gia', en: 'Selected $1 countries' },
  { pattern: /第\s*(\d+)\s*行/g, vi: 'Dòng $1', en: 'Line $1' },
  { pattern: /前\s*N\s*条/g, vi: 'N mục đầu', en: 'First N items' },
  { pattern: /全部（跨页）/g, vi: 'Tất cả (toàn bộ trang)', en: 'All (across pages)' },
  { pattern: /仅选中\s*[（\(]\s*(\d+)\s*[）\)]/g, vi: 'Chỉ mục đã chọn ($1)', en: 'Selected only ($1)' },
  { pattern: /当前筛选\s*[（\(]\s*([^）\)]+)\s*[）\)]/g, vi: 'Bộ lọc hiện tại ($1)', en: 'Current filter ($1)' },
  { pattern: /（搜索：\s*([^）\)]*)\s*）/g, vi: '(Tìm kiếm: $1)', en: '(Search: $1)' },
  { pattern: /搜索：\s*([^）\)]+)/g, vi: 'Tìm kiếm: $1', en: 'Search: $1' },
  { pattern: /(\d+)\s*个格式异常/g, vi: '$1 mục định dạng bất thường', en: '$1 invalid format items' },
  { pattern: /(\d+)\s*\/\s*(\d+)\s*通过/g, vi: '$1 / $2 Đạt', en: '$1 / $2 Passed' },

  // 2. Probe & Trial
  {
    pattern: /0\s*元可领：全库\s*(\d+)\s*个\s*·\s*本页\s*(\d+)\s*个/g,
    vi: '0đ Có thể nhận: Toàn bộ $1 acc · Trang này $2 acc',
    en: 'Free trial: Total $1 · This page $2',
  },
  {
    pattern: /已探测\s*(\d+)\s*个\s*｜\s*未探测\s*(\d+)\s*个\s*——\s*勾选号点「支付能力探测」后会在这里汇总。/g,
    vi: 'Đã kiểm tra $1 acc | Chưa kiểm tra $2 acc —— Chọn tài khoản và bấm "Dò khả năng thanh toán" để xem tổng kết tại đây.',
    en: 'Probed $1 | Unprobed $2 —— Select accounts and click "Probe Payment" to summarize here.',
  },
  {
    pattern: /已探测\s*(\d+)\s*个\s*｜\s*未探测\s*(\d+)\s*个/g,
    vi: 'Đã kiểm tra $1 acc | Chưa kiểm tra $2 acc',
    en: 'Probed $1 | Unprobed $2',
  },
  {
    pattern: /已探测\s*(\d+)\s*｜\s*无\s*UPI\s*(\d+)\s*｜\s*探测失败\s*(\d+)\s*｜\s*未探测\s*(\d+)/g,
    vi: 'Đã kiểm tra $1 | Không có UPI $2 | Lỗi $3 | Chưa kiểm tra $4',
    en: 'Probed $1 | No UPI $2 | Failed $3 | Unprobed $4',
  },
  {
    pattern: /探测完成：成功\s*(\d+)\s*\/\s*(\d+)(?:[，,]\s*(\d+)\s*个出口不通)?/g,
    vi: 'Dò hoàn tất: Thành công $1 / $2$3',
    en: 'Probe complete: Success $1 / $2$3',
  },
  { pattern: /[，,]\s*(\d+)\s*个出口不通/g, vi: ', $1 proxy mất kết nối lối ra', en: ', $1 exit unreachable' },
  {
    pattern: /出口不通，未取得任何金额（(\d+)\s*个号）。先确认印度出口可用再重试/g,
    vi: 'Mất kết nối proxy lối ra, không lấy được số tiền ($1 tài khoản). Vui lòng kiểm tra proxy Ấn Độ trước khi thử lại',
    en: 'Exit unreachable, failed to get amount ($1 accounts). Please verify India exit before retrying',
  },
  { pattern: /探测失败：(.+)/g, vi: 'Dò thanh toán thất bại: $1', en: 'Probe failed: $1' },
  { pattern: /支付能力探测中…\s*(\d+)\s*\/\s*(\d+)/g, vi: 'Đang dò khả năng thanh toán… $1/$2', en: 'Probing payment capability… $1/$2' },
  { pattern: /对\s*([^号\n]+)\s*号跑支付能力探测？/g, vi: 'Chạy dò khả năng thanh toán cho $1 tài khoản?', en: 'Run payment capability probe for $1 accounts?' },

  // 3. AT & Token Life
  { pattern: /检测\s*AT\s*状态…\s*(\d+)\s*\/\s*(\d+)/g, vi: 'Kiểm tra trạng thái AT… $1/$2', en: 'Checking AT status… $1/$2' },
  { pattern: /检测\s*(\d+)\s*个[：:]\s*正常\s*(\d+)/g, vi: 'Đã kiểm tra $1: Bình thường $2', en: 'Checked $1: Normal $2' },
  { pattern: /正常\s*(\d+)\s*ms/g, vi: 'Bình thường $1ms', en: 'Normal $1ms' },
  { pattern: /正常\s*(\d+)/g, vi: 'Bình thường $1', en: 'Normal $1' },
  { pattern: /无\s*UPI/g, vi: 'Không có UPI', en: 'No UPI' },
  {
    pattern: /过期\s*(\d+)\s*（已刷新\s*(\d+)[，,]\s*失败\s*(\d+)\s*）/g,
    vi: 'Hết hạn $1 (Đã làm mới $2, Thất bại $3)',
    en: 'Expired $1 (Refreshed $2, Failed $3)',
  },
  {
    pattern: /过期\s*(\d+)\s*（已刷新\s*(\d+)\s*）/g,
    vi: 'Hết hạn $1 (Đã làm mới $2)',
    en: 'Expired $1 (Refreshed $2)',
  },
  {
    pattern: /刷新完成：成功\s*(\d+)[，,]\s*失败\s*(\d+)/g,
    vi: 'Làm mới hoàn tất: Thành công $1, Thất bại $2',
    en: 'Refresh complete: Success $1, Failed $2',
  },
  {
    pattern: /检测到\s*(\d+)\s*个已过期的号，已全部刷新/g,
    vi: 'Phát hiện $1 tài khoản hết hạn AT, đã làm mới toàn bộ',
    en: 'Detected $1 expired accounts, all refreshed',
  },
  {
    pattern: /这\s*(\d+)\s*个号的\s*AT\s*不是\s*JWT，无法本地判断是否过期/g,
    vi: 'AT của $1 tài khoản này không phải JWT, không thể kiểm tra hết hạn cục bộ',
    en: 'AT of these $1 accounts is not JWT, cannot check expiration locally',
  },
  { pattern: /检测\s*([^号\n]+)\s*号的\s*AT\s*状态？/g, vi: 'Kiểm tra trạng thái AT của $1 tài khoản?', en: 'Check AT status for $1 accounts?' },
  { pattern: /剩\s*([\d\.<>]+)\s*天/g, vi: 'Còn $1 ngày', en: 'Remaining $1 days' },
  { pattern: /已过期\s*([\d\.<>]+)\s*天/g, vi: 'Đã hết hạn $1 ngày', en: 'Expired $1 days' },
  { pattern: /[；;]\s*首个失败\s*([^:]+):\s*(.+)/g, vi: '; Lỗi đầu tiên $1: $2', en: '; First failure $1: $2' },
  { pattern: /首个失败\s*([^:]+):\s*(.+)/g, vi: 'Lỗi đầu tiên $1: $2', en: 'First failure $1: $2' },

  // 4. Proxy & Pool
  { pattern: /当前\s*(\d+)\s*个代理/g, vi: 'Hiện tại $1 proxy', en: 'Current $1 proxies' },
  { pattern: /已保存\s*(\d+)\s*个代理/g, vi: 'Đã lưu $1 proxy', en: 'Saved $1 proxies' },
  { pattern: /已追加\s*(\d+)\s*个新代理/g, vi: 'Đã bổ sung $1 proxy mới', en: 'Appended $1 new proxies' },
  { pattern: /确定清空全部\s*(\d+)\s*个代理？/g, vi: 'Xác nhận xóa toàn bộ $1 proxy?', en: 'Confirm clearing all $1 proxies?' },
  {
    pattern: /代理池有\s*(\d+)\s*个，单次最多测\s*(\d+)\s*个（每批\s*(\d+)\s*并发）。只测前\s*(\d+)\s*个？/g,
    vi: 'Kho Proxy có $1 proxy, tối đa đo $2 proxy một lần ($3 luồng mỗi đợt). Chỉ đo top $4 proxy?',
    en: 'Proxy pool has $1, max $2 per test ($3 concurrent). Only test top $4?',
  },
  { pattern: /测试前\s*(\d+)/g, vi: 'Đo top $1', en: 'Test top $1' },
  { pattern: /已从服务端同步（\s*(\d+)\s*个）/g, vi: 'Đã đồng bộ từ máy chủ ($1 proxy)', en: 'Synced from server ($1 proxies)' },

  // 5. Account Actions & Dialogs
  {
    pattern: /确定删除选中的\s*(\d+)\s*个号？\(不可恢复\)/g,
    vi: 'Xác nhận xóa $1 tài khoản đã chọn? (Không thể khôi phục)',
    en: 'Confirm deleting selected $1 accounts? (Irreversible)',
  },
  {
    pattern: /确定删除选中的\s*(\d+)\s*条凭证？\(不可恢复\)/g,
    vi: 'Xác nhận xóa $1 thông tin đăng nhập đã chọn? (Không thể khôi phục)',
    en: 'Confirm deleting selected $1 credentials? (Irreversible)',
  },
  {
    pattern: /确定删除全部\s*([a-zA-Z0-9_\-]+)\s*状态的号？/g,
    vi: 'Xác nhận xóa tất cả tài khoản trạng thái $1?',
    en: 'Confirm deleting all accounts with status $1?',
  },
  {
    pattern: /重置选中的\s*(\d+)\s*个号为\s*available？（已保存凭证不变）/g,
    vi: 'Đặt lại $1 tài khoản đã chọn thành khả dụng (available)? (Thông tin đã lưu giữ nguyên)',
    en: 'Reset selected $1 accounts to available? (Saved credentials unchanged)',
  },
  {
    pattern: /重置选中的\s*(\d+)\s*个号为\s*available？/g,
    vi: 'Đặt lại $1 tài khoản đã chọn thành khả dụng (available)?',
    en: 'Reset selected $1 accounts to available?',
  },
  { pattern: /重置\s*([^ ]+)\s*为\s*available？/g, vi: 'Đặt lại $1 thành khả dụng (available)?', en: 'Reset $1 to available?' },
  { pattern: /删除\s*([^ ?]+)\s*的凭证？/g, vi: 'Xóa thông tin đăng nhập của $1?', en: 'Delete credentials for $1?' },
  { pattern: /删除\s*([^ ?]+)？/g, vi: 'Xóa $1?', en: 'Delete $1?' },
  { pattern: /选中的\s*(\d+)\s*个/g, vi: 'Đã chọn $1 tài khoản', en: 'Selected $1 accounts' },
  { pattern: /全部\s*(\d+)\s*个/g, vi: 'Tất cả $1 tài khoản', en: 'All $1 accounts' },
  { pattern: /(?:已)?重置\s*(\d+)\s*个/g, vi: 'Đặt lại $1 tài khoản', en: 'Reset $1 accounts' },
  { pattern: /已删除\s*(\d+)\s*个\s*([a-zA-Z0-9_\-]+)\s*号/g, vi: 'Đã xóa $1 tài khoản $2', en: 'Deleted $1 $2 accounts' },
  { pattern: /已删除\s*(\d+)\s*个/g, vi: 'Đã xóa $1', en: 'Deleted $1' },
  { pattern: /已删除\s*(\d+)\s*条/g, vi: 'Đã xóa $1 mục', en: 'Deleted $1 items' },
  { pattern: /已清空\s*(\d+)\s*条/g, vi: 'Đã xóa $1 mục', en: 'Cleared $1 items' },
  { pattern: /释放\s*(\d+)\s*个卡死号/g, vi: 'Đã giải phóng $1 tài khoản bị kẹt', en: 'Released $1 stuck accounts' },
  { pattern: /已复制\s*(.+)/g, vi: 'Đã sao chép $1', en: 'Copied $1' },
  { pattern: /已保存：(.+)/g, vi: 'Đã lưu: $1', en: 'Saved: $1' },

  // 6. Export & Download
  { pattern: /下载并删除这\s*(\d+)\s*个号/g, vi: 'Tải xuống và xóa $1 tài khoản này', en: 'Download and delete these $1 accounts' },
  { pattern: /现在删除这\s*(\d+)\s*个号[：:]/g, vi: 'Hiện tại xóa $1 tài khoản này:', en: 'Now delete these $1 accounts:' },
  {
    pattern: /已下载\s*([^\n]+)。\s*现在删除这\s*(\d+)\s*个号：/g,
    vi: 'Đã tải xuống $1.\nHiện tại xóa $2 tài khoản này:',
    en: 'Downloaded $1.\nNow delete these $2 accounts:',
  },
  { pattern: /已下载\s*([^\(（\n]+)[（\(](\d+)\s*个号[）\)]/g, vi: 'Đã tải xuống $1 ($2 tài khoản)', en: 'Downloaded $1 ($2 accounts)' },
  { pattern: /已下载\s*([^\n。]+)[。.]?/g, vi: 'Đã tải xuống $1.', en: 'Downloaded $1.' },
  { pattern: /(?<!已)下载\s*([^（\(\n]+)/g, vi: 'Tải xuống $1', en: 'Download $1' },
  { pattern: /·\s*注册结果（凭证、2FA secret）/g, vi: '· Kết quả đăng ký (thông tin đăng nhập, secret 2FA)', en: '· Registration results (credentials, 2FA secret)' },
  { pattern: /·\s*邮箱列表（号池那一行，含取件链接）/g, vi: '· Danh sách email (hàng trong kho, kèm link lấy OTP)', en: '· Email pool (account row, including retrieval link)' },
  {
    pattern: /已删除：注册结果\s*(\d+)\s*条\s*\/\s*邮箱列表\s*(\d+)\s*条/g,
    vi: 'Đã xóa: Kết quả đăng ký $1 mục / Danh sách email $2 mục',
    en: 'Deleted: Registration results $1 items / Email pool $2 items',
  },
  { pattern: /导出选中\s*[（\(]\s*([^）\)]+)\s*[）\)]/g, vi: 'Xuất đã chọn ($1)', en: 'Export Selected ($1)' },
  { pattern: /删除选中\s*[（\(]\s*([^）\)]+)\s*[）\)]/g, vi: 'Xóa đã chọn ($1)', en: 'Delete Selected ($1)' },
  { pattern: /重置选中\s*[（\(]\s*([^）\)]+)\s*[）\)]/g, vi: 'Đặt lại đã chọn ($1)', en: 'Reset Selected ($1)' },
  { pattern: /\[协议:\/\/(.+)/g, vi: '[giao thức://$1', en: '[protocol://$1' },

  // 7. Import & Parse
  {
    pattern: /解析总数:\s*(\d+)\s*\|\s*新增:\s*(\d+)\s*\|\s*更新:\s*(\d+)\s*\|\s*失败:\s*(\d+)/g,
    vi: 'Tổng cộng: $1 | Mới: $2 | Cập nhật: $3 | Lỗi: $4',
    en: 'Total: $1 | Added: $2 | Updated: $3 | Failed: $4',
  },
  {
    pattern: /解析\s*(\d+)\s*行，新增\s*(\d+)，更新\s*(\d+)，跳过\s*(\d+)/g,
    vi: 'Phân tích $1 dòng, Thêm $2, Cập nhật $3, Bỏ qua $4',
    en: 'Parsed $1 lines, Added $2, Updated $3, Skipped $4',
  },
  { pattern: /导入完成：新增\s*(\d+)，更新\s*(\d+)/g, vi: 'Nhập hoàn tất: Thêm mới $1, Cập nhật $2', en: 'Import completed: Added $1, Updated $2' },
  {
    pattern: /有\s*(\d+)\s*行不合法，已全部拒绝，一个都没导入/g,
    vi: 'Có $1 dòng không hợp lệ, đã từ chối tất cả, không dòng nào được nhập',
    en: '$1 lines are invalid, all rejected, none imported',
  },
  { pattern: /已购订单导入：新增\s*(\d+)\s*个，可用\s*(\d+|\?)/g, vi: 'Nhập đơn mua: Thêm $1, Khả dụng $2', en: 'Purchased order import: Added $1, Available $2' },
  { pattern: /补货完成：买入\s*(\d+)\s*个，可用\s*(\d+)/g, vi: 'Bổ sung hoàn tất: Mua $1 tài khoản, Khả dụng $2', en: 'Restock complete: Bought $1, Available $2' },

  // 8. SMS & Metadata
  { pattern: /允许国家\s*(\d+)\s*个/g, vi: 'Quốc gia cho phép: $1', en: 'Allowed countries: $1' },
  { pattern: /·\s*允许国家\s*(\d+)\s*个/g, vi: '· Quốc gia cho phép: $1', en: '· Allowed countries: $1' },
  { pattern: /探针详情\s*·\s*([a-zA-Z0-9_\-]+)/g, vi: 'Chi tiết Probe · $1', en: 'Probe Details · $1' },
  { pattern: /`?收\s*([^/]+?)\s*\/\s*发\s*([^（\(]+?)\s*[（\(]近似口径[）\)]`?/g, vi: 'Nhận $1 / Gửi $2 (ước lượng)', en: 'Recv $1 / Sent $2 (approx)' },
  { pattern: /`?收\s*([^/]+?)\s*\/\s*发\s*([^`\n]+?)`?/g, vi: 'Nhận $1 / Gửi $2', en: 'Recv $1 / Sent $2' },
  { pattern: /出口\s*([0-9\.]+)/g, vi: 'Lối ra $1', en: 'Exit $1' },

  // 9. Runtime Logs
  { pattern: /\[auto\]\s*([^ ]+)\s*([^ ]+)\s*完成/g, vi: '[auto] $1 $2 hoàn tất', en: '[auto] $1 $2 completed' },
  { pattern: /\[auto\]\s*开始注册\s*([^ ]+)\s*\(run=([^)]+)\)/g, vi: '[auto] Bắt đầu đăng ký $1 (run=$2)', en: '[auto] Start registering $1 (run=$2)' },
  { pattern: /\[auto\]\s*熔断:\s*(.+)/g, vi: '[auto] Ngắt mạch khẩn cấp: $1', en: '[auto] Circuit break: $1' },
  { pattern: /\[client\]\s*启动注册\s*run_id=([^\s]+)\s*email=([^\s]+)/g, vi: '[client] Bắt đầu đăng ký run_id=$1 email=$2', en: '[client] Launch registering run_id=$1 email=$2' },
  { pattern: /注册完成:\s*([^\s]+)(?:\s*\/\s*(.+))?/g, vi: 'Đăng ký hoàn tất: $1', en: 'Registration complete: $1' },
]

let currentLang = readStoredLocale()
let observer = null
let isTranslating = false

export function getOrigText(text) {
  const entry = exact.get(normalize(text)) || aliases.get(normalize(text))
  return entry?.source || null
}

export function translateString(text, lang = currentLang) {
  if (!text || typeof text !== 'string') return text
  lang = validLocale(lang)
  const key = lang+'\0'+text
  if (cache.has(key)) return cache.get(key)
  const trimmed = text.trim(), normalized = normalize(text)
  const entry = exact.get(normalized) || aliases.get(normalized)
  let result
  if (entry && !/\{\d+\}/.test(normalized)) result = entry[lang]
  if (result === undefined) {
    for (const rule of patterns) {
      const match = normalized.match(rule.regex)
      if (!match) continue
      const values = Object.fromEntries(rule.slots.map((slot,index)=>[slot,rule.entry.translateSlots?.includes(Number(slot.slice(1,-1))) ? translateString(match[index+1], lang) : match[index+1]]))
      result = rule.entry[lang].replace(/\{\d+\}/g, slot=>values[slot] ?? slot)
      break
    }
  }
  if (result === undefined && dynamicOrigins.has(normalized) && normalize(dynamicOrigins.get(normalized)) !== normalized) {
    const source = dynamicOrigins.get(normalized)
    result = translateString(source,lang).trim()
  }
  if (result === undefined) {
    result = text
    if (lang !== 'zh') {
      for (const rule of dynamicPatterns) {
        rule.pattern.lastIndex = 0
        result = result.replace(rule.pattern, rule[lang])
      }
    }
    result = translateFragments(result, lang)
  } else result = text.replace(trimmed,result.trim())
  if (cache.size >= 3000) cache.clear()
  cache.set(key,result)
  if (result !== text && !entry) {
    if (dynamicOrigins.size >= 3000) dynamicOrigins.clear()
    const original = dynamicOrigins.get(normalized) || text
    if (normalize(result) !== normalize(original)) dynamicOrigins.set(normalize(result), original)
  }
  return result
}

const translatedAttributes = ['placeholder','title','aria-label','label','description','content','alt']
function protectedData(node) {
  const element = node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement
  return element?.closest?.('[translate="no"], [data-no-translate], code, pre, script, style')
}

function translateNode(node, lang, deep = true) {
  if (!node || protectedData(node)) return
  if (node.nodeType === Node.TEXT_NODE) {
    const val = node.nodeValue
    if (node.parentElement?.closest?.('.mono,textarea')) return
    if (val && val.trim()) {
      // Vue can update a Vietnamese label or a number in an existing text
      // node. Retain the source only while this is still our own output.
      if (val === node._translatedText && node._translationLang === lang) return
      if (val !== node._translatedText) {
        node._origText = val
      }

      const sourceText = node._origText || val
      const trans = translateString(sourceText, lang)
      if (trans && trans !== node.nodeValue) {
        node.nodeValue = trans
      }
      node._translatedText = node.nodeValue
      node._translationLang = lang
    }
  } else if (node.nodeType === Node.ELEMENT_NODE) {
    // Avoid translating code blocks, scripts, styles, or mono font elements
    const tag = node.tagName?.toLowerCase()
    if (tag === 'script' || tag === 'style' || tag === 'code') {
      return
    }

    // Attributes
    const attrs = translatedAttributes
    for (const attr of attrs) {
      if (attr === 'title' && node.hasAttribute?.('data-i18n-skip-title')) continue
      const val = node.getAttribute(attr)
      if (val && val.trim()) {
        const origKey = `_orig_${attr}`
        const outputKey = `_translated_${attr}`
        const langKey = `_translationLang_${attr}`
        if (val === node[outputKey] && node[langKey] === lang) continue
        if (val !== node[outputKey]) {
          node[origKey] = val
        }

        const sourceAttr = node[origKey] || val
        const trans = translateString(sourceAttr, lang)
        if (trans && trans !== val) {
          node.setAttribute(attr, trans)
        }
        node[outputKey] = node.getAttribute(attr)
        node[langKey] = lang
      }
    }

    // Child nodes
    if (deep) for (const child of node.childNodes) {
      translateNode(child, lang)
    }
  }
}

export function applyTranslations(lang = currentLang) {
  currentLang = lang
  if (isTranslating || typeof document === 'undefined') return
  isTranslating = true
  try {
    if (document.body) {
      translateNode(document.body, lang)
    }
  } finally {
    isTranslating = false
  }
}

export function installMessageInterceptor(ElMessage, ElMessageBox, i18nStore) {
  if (!ElMessage) return

  // Intercept ElMessage methods
  for (const type of ['success', 'warning', 'info', 'error']) {
    const orig = ElMessage[type]
    if (typeof orig === 'function') {
      ElMessage[type] = (options) => {
        const lang = i18nStore?.locale || currentLang
        if (typeof options === 'string') {
          return orig(translateString(options, lang))
        } else if (options && typeof options.message === 'string') {
          return orig({ ...options, message: translateString(options.message, lang) })
        }
        return orig(options)
      }
    }
  }

  for (const method of ['confirm', 'prompt', 'alert']) {
    const original = ElMessageBox?.[method]
    if (typeof original !== 'function') continue
    ElMessageBox[method] = (message, titleOrOptions, maybeOptions) => {
      const lang = i18nStore?.locale || currentLang
      const transMsg = typeof message === 'string' ? translateString(message, lang) : message
      const objectOptions = titleOrOptions && typeof titleOrOptions === 'object' && maybeOptions === undefined
      const options = { ...(objectOptions ? titleOrOptions : maybeOptions || {}) }
      for (const key of ['confirmButtonText', 'cancelButtonText', 'inputPlaceholder', 'inputErrorMessage']) {
        if (typeof options[key] === 'string') options[key] = translateString(options[key], lang)
      }
      if (typeof options.title === 'string') options.title = translateString(options.title, lang)
      if (typeof titleOrOptions === 'string') return original(transMsg, translateString(titleOrOptions, lang), options)
      return original(transMsg, options)
    }
  }
}

export function initDomTranslator(i18nStore, ElMessage, ElMessageBox) {
  if (typeof window === 'undefined' || typeof document === 'undefined') return

  if (ElMessage) {
    installMessageInterceptor(ElMessage, ElMessageBox, i18nStore)
  }

  applyTranslations(i18nStore.locale)

  if (observer) observer.disconnect()

  observer = new MutationObserver((mutations) => {
    if (isTranslating) return
    isTranslating = true
    try {
      // A render can report both a new subtree and its descendants.
      // Visit each tree once; title changes do not require walking its children.
      const added = new Set(mutations.filter(m => m.type === 'childList').flatMap(m => [...m.addedNodes]))
      const covered = node => {
        for (let parent = node.parentNode; parent; parent = parent.parentNode) {
          if (added.has(parent)) return true
        }
        return false
      }
      for (const node of added) {
        if (node.isConnected && !covered(node)) translateNode(node, i18nStore.locale)
      }
      const updated = new Set()
      for (const m of mutations) {
        if (m.type === 'characterData' || m.type === 'attributes') {
          const node = m.target
          if (!node.isConnected || added.has(node) || covered(node) || updated.has(node)) continue
          updated.add(node)
          translateNode(node, i18nStore.locale, false)
        }
      }
    } finally {
      isTranslating = false
    }
  })

  observer.observe(document.body, {
    childList: true,
    subtree: true,
    characterData: true,
    attributes: true,
    attributeFilter: translatedAttributes,
  })

  // Watch locale changes from the store
  i18nStore.$subscribe((mutation, state) => {
    if (state.locale) {
      applyTranslations(state.locale)
    }
  })
}
