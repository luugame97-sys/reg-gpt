export const securityModes = [
  { value: 'check_only', label: 'Kiểm tra đăng nhập / gói' },
  { value: 'change_2fa', label: 'Đổi 2FA' },
  { value: 'change_password', label: 'Đổi mật khẩu' },
  { value: 'change_password_and_2fa', label: 'Đổi mật khẩu + 2FA' },
  { value: 'logout_all', label: 'Kick tất cả phiên' },
]
export const securityActive = job => ['queued', 'running', 'stopping'].includes(job?.state)
export const securityState = state => ({
  queued: 'Đang chờ', running: 'Đang chạy', stopping: 'Đang dừng',
  succeeded: 'Thành công', failed: 'Thất bại', attention: 'Cần xác minh',
  interrupted: 'Bị gián đoạn', cancelled: 'Đã dừng', recovered: 'Đã tiếp tục',
  completed: 'Đã kết thúc',
})[state] || state
export const securityModeLabel = mode => securityModes.find(item => item.value === mode)?.label || mode
export const securityRequestId = () => globalThis.crypto?.randomUUID?.() || `security-${Date.now()}-${Math.random().toString(36).slice(2)}`
export function securityEmails(value) {
  return [...new Set(String(value || '').split(/[\s,;]+/).map(email => email.trim().toLowerCase()).filter(Boolean))]
}
