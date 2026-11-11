<script setup>
import { computed, ref, watch } from 'vue'
import { taskDisplayState, taskAttentionCount } from '@/taskPresentation'
import { Activity, ArrowDown, ArrowUp, CheckCircle2, ChevronDown, Network, RotateCw, Square, Users } from 'lucide-vue-next'

const props = defineProps({
  job: { type: Object, default: null }, title: { type: String, default: 'Tác vụ tài khoản' },
  running: Boolean, cancelling: Boolean, stopRequested: Boolean, canRetry: Boolean, retrying: Boolean,
  connectionError: { type: String, default: '' }, authFailures: { type: Array, default: () => [] },
  planSummary: { type: String, default: '' },
  initiallyCollapsed: Boolean,
  retryLabel: { type: String, default: 'Thử lại acc có thể cứu' },
})
const emit = defineEmits(['reload', 'stop', 'retry', 'filter'])
const expanded = ref(!props.initiallyCollapsed && (props.running || !props.job))
const detailsOpen = ref(false)
const detailTab = ref(props.running ? 'activity' : 'errors')
watch(() => props.job?.job_id, () => { expanded.value = !props.initiallyCollapsed && (props.running || !props.job); detailsOpen.value = false; detailTab.value = props.running ? 'activity' : 'errors' })
const number = value => Math.max(0, Number(value) || 0)
const fmt = value => number(value).toLocaleString('vi-VN')
function bytes(value) {
  const n = number(value)
  if (n < 1024) return `${n} B`
  if (n < 1048576) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1048576).toFixed(2)} MB`
}
const state = computed(() => taskDisplayState(props.job))
const stateLabel = computed(() => ({ queued: 'Đang chờ', running: 'Đang xử lý', stopping: 'Đang dừng', completed: 'Đã hoàn tất', completed_errors: 'Đã xong — có lỗi', cancelled: 'Đã dừng', failed: 'Dừng do lỗi', interrupted: 'Bị gián đoạn', connecting: 'Chưa kết nối' }[state.value] || state.value))
const total = computed(() => number(props.job?.total))
const completed = computed(() => number(props.job?.completed))
const remaining = computed(() => props.job?.remaining == null ? Math.max(0, total.value - completed.value) : number(props.job.remaining))
const percent = computed(() => total.value ? Math.min(100, Math.round(completed.value / total.value * 100)) : 0)
const succeeded = computed(() => number(props.job?.succeeded))
const skipped = computed(() => number(props.job?.skipped))
const attention = computed(() => taskAttentionCount(props.job))
const segments = computed(() => {
  let available = 100
  return [['success', succeeded.value], ['attention', attention.value], ['skipped', skipped.value]].map(([kind, count]) => {
    const width = Math.min(available, total.value ? count / total.value * 100 : 0)
    available -= width
    return { kind, width }
  })
})
const activeEmails = computed(() => (props.job?.current_email || '').split(',').map(email => email.trim()).filter(Boolean))
const routing = computed(() => props.job?.routing || {})
const workers = computed(() => number(routing.value.workers))
const activeWorkers = computed(() => routing.value.active_workers == null ? activeEmails.value.length : number(routing.value.active_workers))
const proxyFailures = computed(() => routing.value.failed_proxies?.length || 0)
const proxyLabel = computed(() => routing.value.mode === 'pool' ? `Kho ${fmt(routing.value.pool_size)}` : routing.value.mode === 'direct' ? 'Trực tiếp' : routing.value.mode === 'checkout' ? 'Proxy checkout' : 'Proxy riêng')
const traffic = computed(() => props.job?.traffic || null)
const trafficTotal = computed(() => traffic.value ? number(traffic.value.rx) + number(traffic.value.tx) : null)
const recentResults = computed(() => props.job?.results || [])
const failures = computed(() => recentResults.value.filter(item => !item.ok).slice().reverse())
const trafficRows = computed(() => recentResults.value.filter(item => item.traffic).slice().reverse())
const isRefresh = computed(() => !props.job?.operation || props.job.operation === 'token_refresh')
const atSummary = computed(() => [['valid', 'Dùng được'], ['expired_401', 'Hết hạn'], ['banned', 'Bị khóa'], ['missing', 'Chưa có AT'], ['unknown', 'Chưa rõ'], ['skipped_unexpired', 'Bỏ qua còn hạn'], ['skipped_usable', 'Bỏ qua đã dùng được']]
  .filter(([key]) => props.job?.counts?.[key]).map(([key, label]) => `${label}: ${fmt(props.job.counts[key])}`))
function openDetails(tab) { detailTab.value = tab; detailsOpen.value = true }
function toggleDetails() {
  if (!detailsOpen.value && !props.running && detailTab.value === 'activity') detailTab.value = failures.value.length ? 'errors' : 'traffic'
  detailsOpen.value = !detailsOpen.value
}
</script>

<template>
  <section class="account-task-progress" :class="`task-state-${state}`" aria-label="Theo dõi tác vụ tài khoản">
    <header class="task-topline">
      <button type="button" class="task-heading" :aria-label="expanded ? 'Thu gọn tiến độ' : 'Mở tiến độ'" :aria-expanded="expanded" @click="expanded = !expanded">
        <span class="task-symbol"><Activity :size="20" /></span>
        <span class="task-heading-copy"><strong>{{ title }}</strong><span v-if="!expanded && job">{{ fmt(completed) }} / {{ fmt(total) }} tài khoản · {{ percent }}% · {{ stateLabel }}<template v-if="attention"> · {{ fmt(attention) }} <span>cần xử lý</span></template></span><span v-else class="task-state-label"><i :class="{ pulsing: running && !stopRequested }" />{{ stateLabel }}</span></span>
        <ChevronDown :size="16" class="task-expand-icon" :class="{ expanded }" />
      </button>
      <div v-if="expanded || running" class="task-actions">
        <el-button v-if="canRetry" type="warning" plain :loading="retrying" @click="emit('retry')">{{ retryLabel }}</el-button>
        <el-button text aria-label="Tải lại tiến độ" @click="emit('reload')"><RotateCw :size="15" /><span>Tải lại</span></el-button>
        <el-button v-if="running" type="danger" plain :loading="cancelling" :disabled="stopRequested" @click="emit('stop')"><Square v-if="!cancelling" :size="13" /><span>{{ job?.cancel_requested ? 'Đang dừng' : stopRequested ? 'Đang gửi lệnh dừng' : 'Dừng tác vụ' }}</span></el-button>
      </div>
    </header>

    <div v-if="expanded" class="task-expanded">
      <template v-if="job">
        <div class="task-progress-caption"><div><strong>{{ fmt(completed) }}</strong><span> / {{ fmt(total) }} tài khoản</span></div><span class="task-percent">{{ percent }}%</span></div>
        <div class="task-progress-track" role="progressbar" :aria-valuenow="completed" :aria-valuemax="total" :aria-valuemin="0" :aria-label="`${title}: ${fmt(completed)} trên ${fmt(total)}`"><span v-for="segment in segments" :key="segment.kind" :class="segment.kind" :style="{ width: segment.width + '%' }" /></div>
        <div class="task-stat-grid">
          <div class="task-stat success"><span><CheckCircle2 :size="14" />Thành công</span><strong>{{ fmt(succeeded) }}</strong></div>
          <button type="button" class="task-stat attention" :disabled="!failures.length" aria-label="Xem kết quả cần chú ý" @click="openDetails('errors')"><span>{{ isRefresh ? 'Thất bại' : 'Cần xử lý' }}</span><strong>{{ fmt(attention) }}</strong></button>
          <div class="task-stat pending"><span>{{ running ? 'Còn lại' : 'Chưa xử lý' }}</span><strong>{{ fmt(remaining) }}</strong></div>
        </div>
        <div v-if="skipped || job.operation === 'token_check' || job.operation === 'plus_check' || job.operation === 'quota_check'" class="task-result-notes">
          <span v-if="skipped && job.operation !== 'token_check'">Bỏ qua: {{ fmt(skipped) }}</span>
          <template v-if="job.operation === 'token_check'"><span v-for="label in atSummary" :key="label">{{ label }}</span></template>
          <span v-if="job.operation === 'plus_check'">{{ planSummary || 'Chưa có kết quả xác minh gói' }}</span>
          <template v-if="job.operation === 'quota_check'"><span>Đọc được quota: {{ fmt(succeeded) }}</span><span v-if="job.counts?.quota_limited">Có hạn mức đã chạm giới hạn: {{ fmt(job.counts.quota_limited) }}</span></template>
        </div>
        <div class="task-resource-grid">
          <div class="task-resource"><Users :size="16" /><div><span>Worker</span><strong>{{ running ? `${fmt(activeWorkers)} / ${fmt(workers)}` : fmt(workers) }}</strong><small v-if="routing.requested_workers && routing.requested_workers !== workers">Yêu cầu {{ fmt(routing.requested_workers) }}</small></div></div>
          <div class="task-resource"><Network :size="16" /><div><span>Kết nối</span><strong>{{ proxyLabel }}</strong><small v-if="proxyFailures">{{ fmt(proxyFailures) }} proxy lỗi đã bỏ qua</small><small v-else-if="routing.mode === 'pool'">Luân phiên theo tài khoản</small></div></div>
          <el-tooltip content="Lưu lượng riêng của đợt này, ước tính nội dung HTTP. Chưa gồm header/TCP/TLS." placement="top"><div class="task-resource task-usage"><ArrowDown :size="16" /><div><span>Lưu lượng đợt này</span><strong>{{ trafficTotal == null ? 'Chưa đo' : bytes(trafficTotal) }}</strong><small v-if="traffic"><span><ArrowDown :size="11" />{{ bytes(traffic.rx) }}</span><span><ArrowUp :size="11" />{{ bytes(traffic.tx) }}</span><span v-if="traffic.partial">· đo một phần</span></small></div></div></el-tooltip>
        </div>
        <div v-if="authFailures.length || job.email_otp_hold_count || (isRefresh && job.failed)" class="task-error-shortcuts">
          <el-button v-for="item in authFailures" :key="item.code" size="small" type="danger" plain @click="emit('filter', {error_code:item.code})">{{ item.label }} <b>{{ fmt(item.count) }}</b></el-button>
          <el-button v-if="job.email_otp_hold_count" size="small" type="warning" plain @click="emit('filter', {error_code:'email_otp_timeout'})">Chờ mail OTP <b>{{ fmt(job.email_otp_hold_count) }}</b></el-button>
          <el-button v-if="isRefresh && job.failed" text size="small" @click="emit('filter', {error_code:''})">Lọc acc lỗi</el-button>
        </div>
        <p v-if="state === 'stopping'" class="task-notice">Đã nhận lệnh dừng. Đợi các acc đang xử lý hoàn tất; các acc tiếp theo sẽ được giữ lại.</p>
        <p v-else-if="stopRequested && running" class="task-notice">Đang gửi lệnh dừng, chờ máy chủ xác nhận.</p>
        <p v-if="job.error" class="task-notice danger">{{ job.error }}</p>
        <div class="task-detail-toolbar"><el-button text :aria-expanded="detailsOpen" @click="toggleDetails">{{ detailsOpen ? 'Ẩn chi tiết' : 'Chi tiết tác vụ' }}<ChevronDown :size="14" :class="{ 'detail-open': detailsOpen }" /></el-button><span v-if="running && !stopRequested">Chạy trên VPS · Có thể đóng tab</span></div>
        <div v-if="detailsOpen" class="task-detail-content">
          <el-tabs v-model="detailTab">
            <el-tab-pane :label="`Đang chạy (${activeEmails.length})`" name="activity">
              <p v-if="!activeEmails.length" class="task-empty">{{ running ? 'Đang chờ lượt xử lý tiếp theo.' : 'Không còn tài khoản đang xử lý.' }}</p>
              <div v-else class="task-email-list"><div v-for="email in activeEmails" :key="email"><i /><span translate="no">{{ email }}</span></div></div>
              <p v-if="routing.current_proxy" class="task-route-detail">Kết nối hiện tại: <span translate="no">{{ routing.current_proxy }}</span></p>
            </el-tab-pane>
            <el-tab-pane :label="`Lỗi gần nhất (${failures.length})`" name="errors">
              <p v-if="job.results_truncated && failures.length" class="task-detail-note">{{ failures.length }} kết quả cần chú ý trong {{ recentResults.length }} acc gần nhất.</p>
              <div v-if="failures.length" class="task-error-list"><article v-for="item in failures" :key="item.email"><strong translate="no">{{ item.email }}</strong><span>{{ item.error || item.message || 'Chưa xác định được kết quả' }}</span></article></div>
              <p v-else class="task-empty">Chưa có kết quả cần chú ý.</p>
            </el-tab-pane>
            <el-tab-pane :label="`Lưu lượng (${trafficRows.length})`" name="traffic">
              <p v-if="job.results_truncated && trafficRows.length" class="task-detail-note">Số đo của {{ trafficRows.length }} tài khoản gần nhất trong đợt này.</p>
              <div v-if="trafficRows.length" class="task-traffic-list"><article v-for="item in trafficRows" :key="item.email"><span class="task-traffic-email"><span translate="no">{{ item.email }}</span><small v-if="item.skipped"> · bỏ qua</small></span><span class="task-traffic-parts">↓ {{ bytes(item.traffic.rx) }} · ↑ {{ bytes(item.traffic.tx) }}</span><strong>{{ bytes(number(item.traffic.rx) + number(item.traffic.tx)) }}</strong></article></div>
              <p v-else class="task-empty">Đợt này chưa có số đo lưu lượng.</p>
            </el-tab-pane>
          </el-tabs>
        </div>
      </template>
      <p v-if="connectionError" class="task-notice">{{ connectionError }}</p>
    </div>
  </section>
</template>

<style scoped>
.account-task-progress { margin: 0 0 20px; border: 1px solid var(--app-border); border-radius: var(--app-card-radius,14px); background: var(--app-card-bg); overflow: hidden; color: var(--app-text-regular); }
.task-topline { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 17px 20px; }
.task-heading { display: flex; align-items: center; gap: 11px; min-width: 0; padding: 0; background: none; color: inherit; border: 0; cursor: pointer; text-align: left; font: inherit; }
.task-symbol { display: grid; place-items: center; width: 38px; height: 38px; flex: 0 0 auto; border-radius: 11px; background: var(--brand-bg); color: var(--brand); }
.task-heading-copy { min-width: 0; display: flex; flex-direction: column; gap: 5px; }
.task-heading-copy > strong { font-size: 14px; font-weight: 650; color: var(--app-title); }
.task-heading-copy > span { font-size: 11px; color: var(--app-text-muted); }
.task-state-label { display: flex; align-items: center; gap: 6px; }
.task-state-label i, .task-email-list i { height: 6px; width: 6px; border-radius: 50%; background: var(--brand); flex-shrink: 0; }
.task-state-failed .task-state-label i, .task-state-interrupted .task-state-label i { background: var(--color-danger); }.task-state-stopping .task-state-label i, .task-state-cancelled .task-state-label i { background: var(--color-warning); }
.pulsing { animation: task-pulse 1.8s ease-in-out infinite; }@keyframes task-pulse { 50% { opacity: .4; } }
.task-expand-icon { color: var(--app-text-muted); transition: transform .18s ease; flex-shrink: 0; }.task-expand-icon.expanded { transform: rotate(180deg); }
.task-actions { display: flex; align-items: center; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }.task-actions :deep(.el-button + .el-button) { margin-left: 0; }.task-actions :deep(.el-button > span) { display: inline-flex; align-items: center; gap: 6px; }
.task-expanded { padding: 0 20px 4px; border-top: 1px solid var(--app-border-subtle); }
.task-progress-caption { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 18px 0 12px; color: var(--app-text-muted); font-size: 12px; font-variant-numeric: tabular-nums; }.task-progress-caption strong { color: var(--app-title); font-size: 24px; font-weight: 650; letter-spacing: -.5px; }.task-percent { color: var(--brand); font-size: 20px; font-weight: 650; }
.task-progress-track { display: flex; height: 7px; border-radius: 10px; overflow: hidden; background: var(--app-card-surface); }.task-progress-track > span { transition: width .25s ease; }.task-progress-track .success { background: var(--brand); }.task-progress-track .attention { background: var(--color-danger); }.task-progress-track .skipped { background: var(--color-info); }
.task-stat-grid { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 10px; margin: 17px 0; }.task-stat { display: flex; flex-direction: column; gap: 10px; border: 1px solid var(--app-border-subtle); border-radius: 10px; padding: 13px 15px; background: var(--app-card-surface); color: var(--app-text-regular); text-align: left; font: inherit; min-width: 0; }.task-stat > span { display: flex; align-items: center; gap: 6px; color: var(--app-text-muted); font-size: 12px; }.task-stat > strong { color: var(--app-title); font-size: 26px; line-height: 1; font-weight: 650; font-variant-numeric: tabular-nums; }.task-stat.success strong { color: var(--brand); }.task-stat.attention strong { color: var(--color-danger); }.task-stat.attention { cursor: pointer; }.task-stat.attention:disabled { cursor: default; }.task-stat.attention:not(:disabled):hover { border-color: var(--color-danger-border); }
.task-result-notes { display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: 11px; color: var(--app-text-muted); margin: -2px 0 15px; }
.task-resource-grid { display: grid; grid-template-columns: 1fr 1.2fr 1.3fr; gap: 18px; padding: 2px 0 17px; }.task-resource { display: flex; gap: 9px; min-width: 0; color: var(--app-text-muted); }.task-resource > svg { margin-top: 2px; flex-shrink: 0; }.task-resource > div { display: flex; flex-direction: column; gap: 5px; min-width: 0; }.task-resource div > span { font-size: 11px; }.task-resource strong { font-size: 13px; font-weight: 600; color: var(--app-title); font-variant-numeric: tabular-nums; }.task-resource small { display: flex; flex-wrap: wrap; gap: 4px 10px; font-size: 10px; line-height: 1.4; }.task-usage small > span { display: flex; align-items: center; gap: 3px; }
.task-error-shortcuts { display: flex; align-items: center; flex-wrap: wrap; gap: 7px; padding: 12px 0 14px; border-top: 1px solid var(--app-border-subtle); }.task-error-shortcuts :deep(.el-button) { margin-left: 0; height: auto; min-height: 28px; padding: 5px 9px; white-space: normal; }.task-error-shortcuts :deep(b) { margin-left: 6px; font-variant-numeric: tabular-nums; }
.task-notice { margin: 0 0 12px; padding: 10px 12px; border-radius: 8px; font-size: 12px; line-height: 1.6; background: var(--color-warning-bg); color: var(--app-text-regular); overflow-wrap: anywhere; }.task-notice.danger { background: var(--color-danger-bg); }
.task-detail-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 43px; border-top: 1px solid var(--app-border-subtle); }.task-detail-toolbar > span { font-size: 10px; color: var(--app-text-dim); }.task-detail-toolbar :deep(.el-button) { padding-left: 0; }.task-detail-toolbar :deep(.el-button > span) { display: flex; align-items: center; gap: 7px; }.detail-open { transform: rotate(180deg); }
.task-detail-content { border-top: 1px solid var(--app-border-subtle); padding: 0 0 14px; }.task-detail-content :deep(.el-tabs__item) { font-size: 12px; }.task-detail-content :deep(.el-tabs__nav-wrap::after) { height: 1px; background: var(--app-border); }.task-detail-note, .task-empty, .task-route-detail { font-size: 11px; color: var(--app-text-muted); line-height: 1.6; margin: 4px 0 12px; overflow-wrap: anywhere; }
.task-email-list, .task-error-list, .task-traffic-list { max-height: 250px; overflow: auto; scrollbar-width: thin; }.task-email-list { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 1px 14px; }.task-email-list > div { display: flex; align-items: center; gap: 8px; min-width: 0; padding: 9px 0; font-size: 12px; overflow-wrap: anywhere; }
.task-error-list article { display: flex; flex-direction: column; gap: 5px; padding: 11px 0; border-bottom: 1px solid var(--app-border-subtle); }.task-error-list strong { color: var(--app-title); font-size: 12px; font-weight: 550; overflow-wrap: anywhere; }.task-error-list article > span { color: var(--app-text-muted); font-size: 11px; line-height: 1.6; overflow-wrap: anywhere; }
.task-traffic-list article { display: grid; grid-template-columns: minmax(0,1fr) auto 90px; gap: 8px 18px; align-items: center; padding: 12px 0; border-bottom: 1px solid var(--app-border-subtle); font-size: 12px; }.task-traffic-email { overflow-wrap: anywhere; }.task-traffic-email small { color: var(--app-text-muted); }.task-traffic-parts { color: var(--app-text-muted); font-size: 11px; white-space: nowrap; }.task-traffic-list strong { text-align: right; color: var(--app-title); font-variant-numeric: tabular-nums; }
@media(max-width:680px) { .task-topline { padding: 14px; flex-wrap: wrap; gap: 12px; }.task-heading { width: 100%; }.task-expand-icon { margin-left: auto; }.task-actions { width: 100%; justify-content: stretch; }.task-actions :deep(.el-button) { flex: 1; min-height: 38px; }.task-actions :deep(.el-button--warning) { flex-basis: 100%; }.task-expanded { padding: 0 14px 3px; }.task-progress-caption { padding-top: 15px; }.task-progress-caption strong { font-size: 22px; }.task-percent { font-size: 19px; }.task-stat-grid { gap: 7px; margin: 14px 0; }.task-stat { padding: 12px 9px; gap: 9px; }.task-stat > span { font-size: 10px; gap: 4px; }.task-stat > strong { font-size: 23px; }.task-resource-grid { grid-template-columns: 1fr 1fr; gap: 16px 10px; padding-bottom: 14px; }.task-usage { grid-column: 1 / -1; padding-top: 13px; border-top: 1px solid var(--app-border-subtle); }.task-usage > div { flex: 1; display: grid; grid-template-columns: 1fr auto; gap: 5px 12px; }.task-usage strong { grid-column: 2; grid-row: 1 / 3; align-self: center; font-size: 20px; }.task-usage small { grid-column: 1; }.task-detail-toolbar { flex-wrap: wrap; gap: 0 8px; padding: 5px 0; }.task-detail-toolbar > span { font-size: 9px; }.task-email-list { grid-template-columns: 1fr; }.task-traffic-list article { grid-template-columns: minmax(0,1fr) auto; gap: 5px 12px; }.task-traffic-parts { grid-column: 1; grid-row: 2; }.task-traffic-list strong { grid-column: 2; grid-row: 1 / 3; }.task-error-shortcuts :deep(.el-button) { min-height: 32px; } }
@media(prefers-reduced-motion:reduce) { .pulsing { animation: none; }.task-progress-track > span, .task-expand-icon { transition: none; } }
</style>
