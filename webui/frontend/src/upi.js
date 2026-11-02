export const UPI_LIMIT = 20000
export const UPI_NEW_SCAN_KEY = 'gpt-reg.upi.new-scan.v1'

// This marker contains no account data. It survives reloads until a new batch
// is submitted; retrying the same request must not clear its NEW labels.
export function upiScanBatch(raw, now = Date.now() / 1000) {
  try {
    const value = typeof raw === 'string' ? JSON.parse(raw) : raw
    if (value?.version === 1 && typeof value.requestId === 'string' && value.requestId.length <= 128 &&
      typeof value.startedAt === 'number' && Number.isFinite(value.startedAt) && value.startedAt > 0) {
      return { version: 1, requestId: value.requestId, startedAt: value.startedAt }
    }
  } catch (_) { /* An unavailable/corrupt visual preference cannot block UPI. */ }
  return { version: 1, requestId: '', startedAt: now }
}

export function beginUpiScanBatch(current, requestId, now = Date.now() / 1000) {
  return requestId && requestId !== current.requestId ? { version: 1, requestId, startedAt: now } : current
}

export function isNewUpiScan(task, batch) {
  const scannedAt = task?.scan_succeeded_at
  return task?.phase === 'completed' && typeof scannedAt === 'number' && Number.isFinite(scannedAt) &&
    scannedAt >= batch.startedAt
}

export const upiFilters = [
  ['', 'Tất cả'], ['QUEUED', 'Đang chờ'], ['ACTIVE', 'Đang xử lý'],
  ['SCANNING', 'Đang quét'], ['SUCCEEDED', 'Đã tạo link'], ['COMPLETED', 'Đã quét'],
  ['UNKNOWN', 'Chờ đối chiếu'], ['PAUSED', 'Đã tạm dừng'], ['STOPPED', 'Đã dừng'], ['FAILED', 'Thất bại'],
]
const phases = {
  queued: ['Đang chờ', 'info'], running: ['Đang xử lý', 'primary'], scanning: ['Đang quét', 'primary'],
  link_ready: ['Đã tạo link', 'warning'], completed: ['Đã quét', 'success'],
  uncertain: ['Chờ đối chiếu', 'warning'], paused: ['Đã tạm dừng', 'warning'],
  stopped: ['Đã dừng', 'info'], failed: ['Thất bại', 'danger'],
  awaiting_funds: ['Chờ nạp điểm', 'warning'], unknown: ['Chưa rõ trạng thái', 'info'],
  waiting_proxy: ['Chờ proxy IN riêng', 'warning'],
}
export const upiPhase = phase => ({ label: (phases[phase] || phases.unknown)[0], tone: (phases[phase] || phases.unknown)[1] })

// Preserve unchanged rows so a status poll does not rebuild their account UI.
export function reuseUpiTasks(previous, incoming) {
  const byId = new Map(previous.map(row => [row.id, row]))
  const next = incoming.map(row => {
    const current = byId.get(row.id)
    return current && JSON.stringify(current) === JSON.stringify(row) ? current : row
  })
  return next.length === previous.length && next.every((row, index) => row === previous[index]) ? previous : next
}

export function canControlUpiTask(task, action) {
  if (!task?.id || task.control?.pending || ['completed', 'failed', 'stopped'].includes(task.phase) || task.control?.state?.toUpperCase() === 'STOPPED') return false
  const paused = task.phase === 'paused' || task.control?.state?.toUpperCase() === 'PAUSED'
  return action === 'pause' ? !paused : action === 'resume' ? paused : action === 'stop'
}


export const canRenewUpiTask = task => task?.provider === 'local' && task.phase === 'failed' && task.renewal?.eligible === true


// Read every matching page before changing selection or sending any command.
export async function collectUpiAccounts(load, params, options = {}) {
  try {
    const rows = await collectUpiTasks(async query => {
      const result = await load(query)
      return { ...result, items: result.items?.map(row => ({ ...row, id: row.email })) }
    }, params, options)
    return rows.filter(row => row.usable === true).map(row => row.email)
  } catch (error) {
    throw new Error((error?.message || 'Không tải được danh sách tài khoản.').replaceAll('tác vụ', 'tài khoản'))
  }
}

export async function collectUpiTasks(load, params, { isActive = () => true, onProgress = () => {} } = {}) {
  const items = new Map()
  let total = null
  for (let page = 0; ; page++) {
    if (!isActive()) throw new Error('Đã hủy chọn tất cả tác vụ.')
    const response = await load({ ...params, page, size: 100 })
    if (!isActive()) throw new Error('Đã hủy chọn tất cả tác vụ.')
    if (!Number.isInteger(response?.total) || response.total < 0 || !Array.isArray(response.items)) throw new Error('Danh sách tác vụ chưa đầy đủ; hãy làm mới rồi chọn lại.')
    if (response.total > UPI_LIMIT) throw new Error('Tối đa 20.000 tác vụ mỗi lượt chọn; hãy thu hẹp bộ lọc.')
    if (total !== null && total !== response.total) throw new Error('Danh sách tác vụ đã thay đổi; hãy chọn tất cả lại.')
    total = response.total
    for (const item of response.items) {
      if (!item?.id || items.has(item.id)) throw new Error('Danh sách tác vụ đã thay đổi; hãy chọn tất cả lại.')
      items.set(item.id, item)
    }
    onProgress({ loaded: items.size, total })
    if (items.size === total) return [...items.values()]
    if (!response.items.length || items.size > total) throw new Error('Danh sách tác vụ chưa đầy đủ; hãy làm mới rồi chọn lại.')
  }
}

// Each command is sent once. Stop on transport uncertainty or rate limits so
// later tasks remain untouched until the user reconciles the result.
export async function runUpiControls(tasks, action, send, { isActive = () => true, onProgress = () => {} } = {}) {
  if (!['pause', 'resume', 'stop'].includes(action)) throw new Error('Lệnh UPI không hợp lệ.')
  const targets = [...new Map(tasks.filter(task => canControlUpiTask(task, action)).map(task => [task.id, task])).values()]
  const result = { total: targets.length, accepted: 0, pending: 0, failed: 0, not_sent: targets.length, items: [] }
  for (const task of targets) {
    if (!isActive()) break
    let halt = false, item
    try {
      const response = await send(task.id, action)
      const updated = response?.task
      const expected = { pause: 'PAUSED', resume: 'RUNNING', stop: 'STOPPED' }[action]
      if (updated?.id !== task.id || (!updated.control?.pending && updated.control?.state?.toUpperCase() !== expected)) {
        throw new Error('Phản hồi lệnh chưa rõ; hãy đồng bộ tác vụ trước khi gửi lại.')
      }
      item = { id: task.id, ok: true, task: updated, pending: !!updated.control?.pending }
      result.accepted++
      if (item.pending) result.pending++
    } catch (error) {
      item = { id: task.id, ok: false, message: error?.message || 'Không gửi được lệnh UPI.' }
      result.failed++
      halt = !error?.status || [400, 401, 403, 429].includes(error.status) || error.status >= 500
    }
    result.items.push(item)
    result.not_sent = result.total - result.items.length
    onProgress({ ...result, items: [...result.items] }, item)
    if (halt) break
  }
  return result
}

export function parseUpiTokens(text) {
  const raw = String(text || '').trim()
  if (!raw) return []
  let values
  if (raw.startsWith('[') || raw.startsWith('{')) {
    let value
    try { value = JSON.parse(raw) } catch { throw new Error('JSON nhập AT không hợp lệ.') }
    values = Array.isArray(value) ? value : Array.isArray(value.tokens) ? value.tokens : Array.isArray(value.accounts) ? value.accounts : [value]
    values = values.map(x => typeof x === 'string' ? x : x?.access_token || x?.accessToken || x?.token || '')
  } else {
    values = raw.split(/\r?\n/).filter(x => x.trim()).map(line => {
      const value = line.trim().replace(/^Bearer\s+/i, '')
      return value.includes('----') ? value.split('----').find(x => /^[\w-]+\.[\w-]+\.[\w-]+$/.test(x.trim())) || value : value
    })
  }
  if (values.length > UPI_LIMIT) throw new Error('Mỗi đợt UPI tối đa 20.000 tài khoản.')
  return values.map(x => String(x).trim()).filter(Boolean)
}

export function upiCsv(rows) {
  const cell = value => {
    let text = String(value ?? '')
    if (/^[\s]*[=+@-]|^[\t\r]/.test(text)) text = "'" + text
    return '"' + text.replaceAll('"', '""') + '"'
  }
  return '\ufeff' + [
    ['task_id', 'email', 'status', 'scan_status', 'checkout_succeeded_at', 'scan_succeeded_at'],
    ...rows.map(row => [row.id, row.email, row.status, row.scan_status, row.checkout_succeeded_at, row.scan_succeeded_at]),
  ].map(row => row.map(cell).join(',')).join('\r\n')
}
export function upiAccountEmail(value) {
  const email = typeof value === 'string' ? value.trim().toLowerCase() : ''
  return email.length <= 254 && email.includes('@') && !/[\s\x00-\x1f]/.test(email) ? email : ''
}

export function upiAccountRoute(email, forceRefresh = false) {
  const target = upiAccountEmail(email)
  return target ? { path: '/registered', query: { email: target, ...(forceRefresh ? { refresh: 'force' } : {}) } } : { path: '/registered' }
}

// A login file contains only the explicitly reviewed accounts, once per email.
// Reject ambiguous delimiters rather than changing passwords during export.
export function upiLsExport(records, { require2fa = true } = {}) {
  const seen = new Set(), lines = [], emails = []
  const skipped = { unavailable: 0, password: 0, twofa: 0, unsafe: 0 }
  let duplicates = 0, missing2fa = 0
  for (const { email, info } of records) {
    const target = upiAccountEmail(email), account = info?.account
    if (!target || info?.state !== 'ready' || upiAccountEmail(account?.email) !== target) { skipped.unavailable++; continue }
    if (seen.has(target)) { duplicates++; continue }
    seen.add(target)
    const password = String(account.password || ''), secret = String(account.totp_secret || '')
    if (!password) { skipped.password++; continue }
    if ([target, password, secret].some(value => /[\x00-\x1f\x7f]|---/.test(value))) { skipped.unsafe++; continue }
    if (!secret.trim()) {
      if (require2fa) { skipped.twofa++; continue }
      missing2fa++
    }
    lines.push([target, password, secret].join('---')); emails.push(target)
  }
  return { text: lines.length ? lines.join('\r\n') + '\r\n' : '', count: lines.length, emails,
    skipped, skippedCount: Object.values(skipped).reduce((sum, count) => sum + count, 0), duplicates, missing2fa }
}

export function upiAccountFields(data, email) {
  const target = upiAccountEmail(email)
  if (!target || !data || upiAccountEmail(data.email) !== target) throw new Error('Thông tin tài khoản không khớp email.')
  const plan = data.extra?.plus_check
  const failures = { banned: 'Tài khoản bị khóa', token_invalid: 'AT lỗi', no_at: 'Chưa có AT' }
  return {
    email: data.email, password: String(data.password || ''), totp_secret: String(data.totp_secret || ''),
    group_name: String(data.group_name || ''),
    plan_label: plan?.membership_verified === true ? String(plan.label || 'Chưa xác minh gói') :
      failures[plan?.status] || 'Chưa xác minh gói',
    plan_verified: plan?.membership_verified === true,
    plan_checked_at: Number.isFinite(Number(plan?.checked_at)) && Number(plan?.checked_at) > 0 ? Number(plan.checked_at) : null,
  }
}

// Read only the visible task accounts. Never retain their AT, RT or session data.
export function upiPostScanLabel(task, account) {
  const scanned = Number(task?.scan_succeeded_at), checked = Number(account?.plan_checked_at)
  if (!(scanned > 0 && checked >= scanned)) return 'Chưa kiểm tra gói sau quét'
  return account?.plan_verified ? 'Đã kiểm tra gói sau quét' : 'Đã kiểm tra nhưng chưa xác minh gói'
}

// Read only the visible task accounts. Never retain their AT, RT or session data.
export async function loadUpiAccounts(emails, fetchAccount, { isActive = () => true, onResult = () => {} } = {}) {
  const queue = [...new Set(emails.map(upiAccountEmail).filter(Boolean))].slice(0, 100)
  let index = 0
  await Promise.all(Array.from({ length: Math.min(4, queue.length) }, async () => {
    while (index < queue.length && isActive()) {
      const email = queue[index++]
      let result
      try {
        const response = await fetchAccount(email)
        result = { state: 'ready', account: upiAccountFields(response.data, email) }
      } catch (error) {
        result = { state: error?.status === 404 ? 'missing' : 'error' }
      }
      if (isActive()) onResult(email, result)
    }
  }))
}

