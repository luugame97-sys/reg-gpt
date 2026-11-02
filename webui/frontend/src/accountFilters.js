export const filterOptions = {
  plans: [
    ['plan_paid','Gói trả phí'],['plan_free','Free'],['plan_go','Go'],['plan_plus','Plus'],['plan_pro','Pro'],
    ['plan_team','Team'],['plan_business','Business'],['plan_enterprise','Enterprise'],['plan_edu','Edu'],
    ['plan_unknown','Chưa xác minh gói'],['unchecked','Chưa từng kiểm tra'],['plus','Có ưu đãi Plus'],['offer_checked','Đã kiểm tra gói / ưu đãi'],
  ],
  tokens: [['at_needs_refresh','Cần làm mới AT'],['at_usable','Còn hạn / đã dùng được'],['token_invalid','Hết hạn / bị từ chối'],['at_missing','Chưa có AT'],['at_unknown','Chưa rõ hạn'],['at_banned','Bị khóa khi quét']],
  errors: [['refresh_errors','Có lỗi làm mới'],['auth_credentials','Sai tài khoản / mật khẩu'],['auth_2fa','Sai hoặc thiếu 2FA'],['auth_disabled','Tài khoản bị khóa'],['email_otp_hold','Chờ xử lý mail OTP'],['auth_email_otp','Lỗi OTP email'],['refresh_network','Lỗi proxy / mạng']],
}
export function validFilterSelection(values, options) {
  return Array.isArray(values) && values.length <= 16 && values.every(value => options.some(([key]) => key === value))
}
export function readSavedAccountViews(raw) {
  try {
    const items = JSON.parse(raw || '[]')
    if (!Array.isArray(items)) return []
    return items.filter(item => item && typeof item.id === 'string' && typeof item.name === 'string' && item.name.trim() && item.name.length <= 64
      && validFilterSelection(item.plans,filterOptions.plans) && validFilterSelection(item.tokens,filterOptions.tokens) && validFilterSelection(item.errors,filterOptions.errors)
      && typeof item.group === 'string' && typeof item.country === 'string' && typeof item.keyword === 'string'
      && (item.dates == null || (Array.isArray(item.dates) && item.dates.length === 2 && item.dates.every(date => /^\d{4}-\d{2}-\d{2}$/.test(date)))))
      .slice(0,20)
  } catch { return [] }
}
