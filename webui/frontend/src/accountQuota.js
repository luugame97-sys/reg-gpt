// Presentation only: opening the account list never requests account usage.
const finite = value => typeof value === 'number' && Number.isFinite(value) && value >= 0
export function quotaWindows(check) {
  return (Array.isArray(check?.buckets) ? check.buckets : []).flatMap(bucket =>
    (Array.isArray(bucket.windows) ? bucket.windows : []).map(window => ({ ...window, bucketKey: bucket.key, bucketLabel: bucket.label })))
}
export function quotaNeedsCheck(check, now = Date.now()) {
  return Boolean(check?.stale || quotaWindows(check).some(window => finite(window.reset_at) && window.reset_at > 0 && window.reset_at * 1000 <= now))
}
export function quotaSummary(check, now = Date.now()) {
  const windows = quotaWindows(check).filter(window => window.bucketKey === 'rate_limit' && finite(window.used_percent))
  const success = ['quota_ok', 'quota_limited'].includes(check?.status) && windows.length > 0
  return { windows, success, stale: quotaNeedsCheck(check, now), limited: success && check.status === 'quota_limited',
    previous: success && Boolean(check.last_error), error: check?.last_error || (!success && check ? check : null) }
}
export function quotaPercent(value) {
  return finite(value) ? `${Math.round(value * 10) / 10}%` : '—'
}
export function quotaDuration(seconds) {
  if (!finite(seconds) || seconds === 0) return null
  for (const [size, unit] of [[86400, 'ngày'], [3600, 'giờ'], [60, 'phút']]) {
    if (seconds >= size) return { value: Math.round(seconds / size * 10) / 10, unit }
  }
  return { value: seconds, unit: 'giây' }
}

export function quotaBar(window) {
  const value = window?.remaining_percent
  const known = finite(value)
  const width = known ? Math.min(100, value) : 0
  return { known, width, tone: !known ? 'unknown' : width <= 10 ? 'danger' : width <= 30 ? 'warning' : 'good' }
}

export function quotaResetCountdown(resetAt, now = Date.now()) {
  if (!finite(resetAt) || !resetAt) return { state: 'unknown', text: '—' }
  const seconds = (resetAt * 1000 - now) / 1000
  if (seconds <= 0) return { state: 'passed', text: '' }
  if (seconds < 60) return { state: 'soon', text: '<1m' }
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  return { state: 'future', text: hours >= 24 ? `${Math.floor(hours / 24)}d ${hours % 24}h` : hours ? `${hours}h ${minutes % 60}m` : `${minutes}m` }
}

export function quotaSubscriptionExpiry(plan, now = Date.now()) {
  // A quota reset is not evidence of a subscription expiration date.
  if (plan?.membership_verified !== true || !plan.plan_type || plan.plan_type === 'free' || !plan.expires_at) return null
  const raw = plan.expires_at
  const numeric = typeof raw === 'number' || (typeof raw === 'string' && /^\d+(\.\d+)?$/.test(raw))
  const number = numeric ? Number(raw) : null
  const millis = numeric ? number * (number < 1e12 ? 1000 : 1) : Date.parse(raw)
  if (!Number.isFinite(millis) || millis <= 0 || millis > 8.64e15) return null
  return { expiresAt: millis / 1000, days: Math.max(0, Math.ceil((millis - now) / 86400000)), expired: millis <= now }
}
