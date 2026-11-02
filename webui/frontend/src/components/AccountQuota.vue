<script setup>
import { computed, inject, ref } from 'vue'
import { fmtTime } from '@/api/request'
import { quotaSummary, quotaWindows, quotaPercent, quotaDuration, quotaBar, quotaResetCountdown, quotaSubscriptionExpiry } from '@/accountQuota'
import { useI18nStore } from '@/stores/i18n'
import { localeTag } from '@/i18n/locale'
const props = defineProps({ check: { type: Object, default: null }, plan: { type: Object, default: null }, now: { type: Number, default: undefined }, disabled: Boolean })
const clock = inject('accountCredentialNow', ref(Date.now()))
const now = computed(() => props.now ?? clock.value)
const emit = defineEmits(['check'])
const i18n = useI18nStore()
const state = computed(() => quotaSummary(props.check, now.value))
const windows = computed(() => quotaWindows(props.check))
const expiry = computed(() => quotaSubscriptionExpiry(props.plan, now.value))
const expiryUnknown = computed(() => props.plan?.membership_verified === true && props.plan?.plan_type && props.plan.plan_type !== 'free' && !expiry.value)
function duration(seconds) {
  const value = quotaDuration(seconds)
  return value ? `${value.value} ${i18n.t(value.unit)}` : i18n.t('Chưa rõ chu kỳ')
}
function windowLabel(window) {
  const period = quotaDuration(window.limit_window_seconds)
  const label = window.limit_window_seconds === 604800 ? i18n.t('Tuần') : period ? `${period.value}${({ngày:'d',giờ:'h',phút:'m',giây:'s'})[period.unit]}` : i18n.t('Chưa rõ chu kỳ')
  return window.bucketKey === 'rate_limit' ? label : `${i18n.t(window.bucketLabel)} · ${label}`
}
const shortFormatters = computed(() => [false, true].map(withYear => new Intl.DateTimeFormat(localeTag(i18n.locale), {day:'2-digit',month:'2-digit',...(withYear ? {year:'numeric'} : {}),hour:'2-digit',minute:'2-digit',hour12:false})))
function shortTime(value, withYear = false) {
  if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) return ''
  const date = new Date(value * 1000)
  if (!Number.isFinite(date.getTime())) return ''
  return shortFormatters.value[withYear ? 1 : 0].format(date)
}
function resetLabel(window) {
  const result = quotaResetCountdown(window.reset_at, now.value)
  return result.state === 'passed' ? i18n.t('Cần kiểm tra lại') : result.state === 'unknown' ? i18n.t('Chưa rõ mốc reset') : result.text
}
function progressLabel(window) {
  return `${windowLabel(window)} · ${i18n.t('Còn')} ${quotaPercent(window.remaining_percent)} · ${i18n.t('Đã dùng')} ${quotaPercent(window.used_percent)}`
}
</script>

<template>
  <div class="account-quota" :class="{ warning: state.stale || state.previous || state.limited, stale: state.stale || state.previous }">
    <el-popover :persistent="false" v-if="check" trigger="click" :width="330" placement="bottom-start">
      <template #reference>
        <button type="button" class="quota-summary" aria-label="Xem chi tiết quota">
          <template v-if="state.success">
            <span v-for="window in windows" :key="`${window.bucketKey}:${window.key}`" class="quota-window" :class="quotaBar(window).tone">
              <span class="quota-window-heading"><b>{{ windowLabel(window) }}</b><strong><span class="quota-remaining-label">Còn</span> <span translate="no">{{ quotaPercent(window.remaining_percent) }}</span></strong></span>
              <span class="quota-track" role="progressbar" :aria-label="progressLabel(window)" :aria-valuemin="0" :aria-valuemax="100" :aria-valuenow="quotaBar(window).known ? quotaBar(window).width : undefined" :aria-valuetext="progressLabel(window)" :title="progressLabel(window)"><span class="quota-fill" :style="{width: `${quotaBar(window).width}%`}" /></span>
              <span class="quota-reset" :title="window.reset_at ? `${i18n.t('Reset theo API')}: ${fmtTime(window.reset_at)}` : i18n.t('Chưa rõ mốc reset')"><span>{{ resetLabel(window) }}</span><time v-if="shortTime(window.reset_at)" translate="no" :datetime="new Date(window.reset_at * 1000).toISOString()">{{ shortTime(window.reset_at) }}</time></span>
            </span>
            <span v-if="state.stale" class="quota-notice">Cần kiểm tra lại</span>
            <span v-else-if="state.previous" class="quota-notice">Kết quả lần trước</span>
            <span v-else-if="state.limited" class="quota-notice">Có hạn mức đã chạm giới hạn</span>
          </template>
          <span v-else>Chưa đọc được quota</span>
          <span v-if="expiry" class="quota-expiry" :class="{expired:expiry.expired}" :title="`${i18n.t('Hạn thuê bao')}: ${fmtTime(expiry.expiresAt)}`"><span>{{ expiry.expired ? i18n.t('Gói đã hết hạn') : i18n.t('Hạn gói còn {days} ngày').replace('{days}', expiry.days) }}</span><time translate="no" :datetime="new Date(expiry.expiresAt * 1000).toISOString()">{{ shortTime(expiry.expiresAt, true) }}</time></span>
          <span v-else-if="expiryUnknown" class="quota-notice">Chưa rõ hạn gói</span>
          <span class="quota-meta"><span>Codex / Work</span><time v-if="check.checked_at" :title="`${i18n.t('Đã kiểm tra')}: ${fmtTime(check.checked_at)}`" translate="no">{{ shortTime(check.checked_at) }}</time></span>
        </button>
      </template>
      <div class="quota-detail">
        <strong>Quota Codex / Work</strong>
        <p>Chỉ các hạn mức endpoint trả về; không đại diện mọi model ChatGPT.</p>
        <p v-if="state.stale" class="quota-warning">AT đã đổi hoặc mốc reset đã qua; cần kiểm tra lại.</p>
        <p v-if="state.error" class="quota-warning"><span>Lần kiểm tra gần nhất chưa thành công</span><br><span>{{ state.error.message }}</span><br><small>{{ fmtTime(state.error.checked_at) }}</small></p>
        <div v-for="window in windows" :key="`${window.bucketKey}:${window.key}`" class="quota-detail-window">
          <b>{{ window.bucketLabel }} · {{ duration(window.limit_window_seconds) }}</b>
          <span><span>Đã dùng</span> <span translate="no">{{ quotaPercent(window.used_percent) }}</span> · <span>Còn</span> <span translate="no">{{ quotaPercent(window.remaining_percent) }}</span></span>
          <small v-if="window.reset_at"><span>Reset theo API</span>: {{ fmtTime(window.reset_at) }}</small>
        </div>
        <small v-if="windows.length">Thời điểm reset là dữ liệu tại lần kiểm tra.</small>
        <small v-if="expiry"><span>Hạn thuê bao</span>: {{ fmtTime(expiry.expiresAt) }}</small>
        <small v-else-if="expiryUnknown">Chưa rõ hạn gói</small>
        <small v-if="check.checked_at"><span>Đã kiểm tra</span>: {{ fmtTime(check.checked_at) }}</small>
        <el-button size="small" type="primary" plain :disabled="disabled" @click="emit('check')">Kiểm tra quota</el-button>
      </div>
    </el-popover>
    <el-button v-else text size="small" :disabled="disabled" @click="emit('check')">Kiểm tra quota</el-button>
  </div>
</template>

<style scoped>
.account-quota{min-width:0;width:100%}
.quota-summary{display:flex;flex-direction:column;align-items:stretch;gap:7px;width:100%;padding:3px 0;background:none;border:0;text-align:left;color:var(--app-text);font:inherit;cursor:pointer;min-width:0}
.quota-summary:focus-visible{outline:2px solid var(--brand);outline-offset:4px;border-radius:3px}
.quota-window{display:flex;flex-direction:column;gap:3px;min-width:0;--quota-color:var(--brand)}
.quota-window.warning{--quota-color:var(--el-color-warning)}
.quota-window.danger{--quota-color:var(--el-color-danger)}
.quota-window.unknown{--quota-color:var(--app-text-muted)}
.quota-window-heading{display:flex;align-items:baseline;justify-content:space-between;gap:8px;font-size:10px;line-height:1.3}
.quota-window-heading b{font-weight:600;color:var(--app-text-muted);overflow-wrap:anywhere}
.quota-window-heading strong{font-size:10px;font-weight:650;color:var(--quota-color);white-space:nowrap;font-variant-numeric:tabular-nums}
.quota-remaining-label{font-size:9px;font-weight:400}
.quota-track{display:block;height:4px;border-radius:4px;background:var(--app-border);overflow:hidden}
.quota-fill{display:block;height:100%;background:var(--quota-color);border-radius:inherit}
.unknown .quota-track{background:repeating-linear-gradient(135deg,var(--app-border) 0 4px,transparent 4px 8px)}
.stale .quota-track{opacity:.55}
.quota-reset{display:flex;justify-content:space-between;gap:6px;flex-wrap:wrap;font-size:9px;line-height:1.3;color:var(--app-text-dim);font-variant-numeric:tabular-nums}
.quota-reset time{white-space:nowrap}
.quota-notice{font-size:10px;line-height:1.4;color:var(--el-color-warning)}
.quota-meta{display:flex;justify-content:space-between;gap:6px;flex-wrap:wrap;font-size:9px;line-height:1.4;color:var(--app-text-dim)}
.quota-expiry{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:4px 8px;padding:5px 6px;border:1px solid var(--brand-border);border-radius:5px;background:var(--brand-bg);font-size:9px;line-height:1.4;color:var(--brand)}
.quota-expiry time{color:var(--app-text-muted);font-variant-numeric:tabular-nums}
.quota-expiry.expired{border-color:var(--el-color-danger-light-7);background:var(--el-color-danger-light-9);color:var(--el-color-danger)}
.quota-detail{display:flex;flex-direction:column;gap:9px;font-size:12px;overflow-wrap:anywhere;max-height:65vh;overflow-y:auto}
.quota-detail p{margin:0;color:var(--app-text-muted);line-height:1.6}
.quota-detail .quota-warning{color:var(--el-color-warning)}
.quota-detail-window{display:flex;flex-direction:column;gap:4px;border-top:1px solid var(--app-border);padding-top:9px}
.quota-detail>small{color:var(--app-text-muted);line-height:1.5}
.quota-detail>.el-button{align-self:flex-start;margin:3px 0 0}
.account-quota>.el-button{padding-inline:0}
</style>
