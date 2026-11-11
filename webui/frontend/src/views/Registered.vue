<script setup>
import { computed, onActivated, onDeactivated, onUnmounted, provide, ref, watch } from 'vue'
import { useMobileView } from '@/useMobileView'

const active = ref(false)
const mobileView = useMobileView()
const credentialNow = ref(Date.now())
// Only the small time-dependent children subscribe; the list never reads this clock.
provide('accountCredentialNow', credentialNow)
let credentialTimer = null
function stopCredentialClock() {
  clearTimeout(credentialTimer)
  credentialTimer = null
}
function updateCredentialClock() {
  stopCredentialClock()
  credentialNow.value = Date.now()
  if (active.value && !document.hidden) {
    credentialTimer = setTimeout(updateCredentialClock, 1000 - Date.now() % 1000 + 5)
  }
}
function releaseCredentialClock() {
  stopCredentialClock()
  document.removeEventListener('visibilitychange', updateCredentialClock)
}
onDeactivated(() => { active.value = false; releaseCredentialClock() })
onUnmounted(releaseCredentialClock)
import { storeToRefs } from 'pinia'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Filter as FilterIcon } from 'lucide-vue-next'
import { useRoute, useRouter } from 'vue-router'
import {
  listRegistered, getRegistered, deleteRegistered, clearRegisteredRefreshError,
  bulkDeleteRegistered, bulkDeleteAccounts,
  listExportFormats, exportRegistered, updateCredentials,
  getRegisteredMeta,
  checkRegisteredAt, getCheckoutSummary,
  importRegistered,
  listRegisteredGroups, createRegisteredGroup, reorderRegisteredGroup,
  assignRegisteredGroup, renameRegisteredGroup, deleteRegisteredGroup,
  listRegisteredCountries,
  findExpiredRefreshCandidates, resolveRegisteredSelection, getRefreshRetryCandidates,
} from '@/api/register'
import { copyText, fmtTime, fmtDate } from '@/api/request'
import { useFormStore, proxyText } from '@/stores/form'
import { useProxyStore } from '@/stores/proxy'
import { useRuntimeStore } from '@/stores/runtime'
import { useTokenRefreshStore } from '@/stores/tokenRefresh'
import { t } from '@/stores/i18n'
import StatusDot from '@/components/StatusDot.vue'
import TaskTraffic from '@/components/TaskTraffic.vue'
import AccountTaskProgress from '@/components/AccountTaskProgress.vue'
import AccountToolbar from '@/components/AccountToolbar.vue'
import AccountFolders from '@/components/AccountFolders.vue'
import AccountFilters from '@/components/AccountFilters.vue'
import AccountCredentials from '@/components/AccountCredentials.vue'
import AccountQuota from '@/components/AccountQuota.vue'
import { readSavedAccountViews } from '@/accountFilters'
const route = useRoute()
const router = useRouter()

const { form } = storeToRefs(useFormStore())
const { list: proxyList } = storeToRefs(useProxyStore())
const proxyOptions = computed(() => proxyList.value.map((p) => ({ label: p, value: p })))
const savedRefreshProxyMode = localStorage.getItem('token_refresh_proxy_mode')
const refreshProxyMode = ref(['pool', 'single', 'direct'].includes(savedRefreshProxyMode) ? savedRefreshProxyMode : 'pool')
watch(refreshProxyMode, mode => localStorage.setItem('token_refresh_proxy_mode', mode))
const checkSkipUsable = ref(localStorage.getItem('token_check_skip_usable') !== '0')
watch(checkSkipUsable, enabled => localStorage.setItem('token_check_skip_usable', enabled ? '1' : '0'))
const runtime = useRuntimeStore()
const { dataVersion } = storeToRefs(runtime)
const tokenRefresh = useTokenRefreshStore()
const { job: refreshJob, running: refreshJobRunning, connectionError: refreshConnectionError, cancelling: submittingStop, stopRequested: refreshStopRequested } = storeToRefs(tokenRefresh)

const PAGE_SIZE_OPTIONS = [20, 50, 100]
const pageSize = ref(
  Math.min(100, Math.max(1, Number(localStorage.getItem('reg.pageSize')) || 50)),
)
const rows = ref([])
const total = ref(0)
const page = ref(1)
const PLAN_FILTERS = ['all', 'plan_paid', 'plan_free', 'plan_go', 'plan_plus', 'plan_pro', 'plan_team', 'plan_business', 'plan_enterprise', 'plan_edu', 'plan_unknown', 'unchecked', 'plus', 'offer_checked', 'plus_activated']
const TOKEN_FILTERS = ['all', 'at_needs_refresh', 'at_usable', 'token_invalid', 'at_missing', 'at_unknown', 'at_banned']
const ERROR_FILTERS = ['all', 'refresh_errors', 'auth_credentials', 'auth_2fa', 'auth_disabled', 'email_otp_hold', 'auth_email_otp', 'refresh_network']
const planFilter = ref('all')
const tokenFilter = ref('all')
const errorFilter = ref('all')
const filter = computed({
  get: () => [planFilter.value, tokenFilter.value, errorFilter.value].filter(value => value !== 'all').join('|') || 'all',
  set: value => {
    const parts = String(value || 'all').split('|')
    if (parts.some(part => ![PLAN_FILTERS,TOKEN_FILTERS,ERROR_FILTERS].some(options => part.split(',').every(value => options.includes(value))))) throw new Error('Bộ lọc không hợp lệ')
    planFilter.value = tokenFilter.value = errorFilter.value = 'all'
    for (const part of parts) {
      if (part === 'all') continue
      if (part.split(',').every(value => PLAN_FILTERS.includes(value))) planFilter.value = part
      else if (part.split(',').every(value => TOKEN_FILTERS.includes(value))) tokenFilter.value = part
      else if (part.split(',').every(value => ERROR_FILTERS.includes(value))) errorFilter.value = part
    }
  },
})
const groupFilter = ref('all') // 'all' | '__ungrouped__' | tên nhóm
const countryFilter = ref('all') // 'all' | mã quốc gia (BR, JP, VN...)
const availableCountries = ref([])
const keyword = ref('')
const groupsSummary = ref({
  total: 0,
  ungrouped: 0,
  grouped: 0,
  groups: [],
})
const dateRange = ref(null)
const filtersVisible = ref(false), foldersVisible = ref(false)
const savingFolderOrder = ref(false)
const savedAccountViews = ref(readSavedAccountViews(localStorage.getItem('registered_saved_views_v1')))
const currentFolderName = computed(() => groupFilter.value === 'all' ? 'Tất cả tài khoản' : groupFilter.value === '__ungrouped__' ? 'Chưa phân thư mục' : groupFilter.value)
const filterDraft = computed(() => ({plans:planFilter.value==='all'?[]:planFilter.value.split(','),tokens:tokenFilter.value==='all'?[]:tokenFilter.value.split(','),errors:errorFilter.value==='all'?[]:errorFilter.value.split(','),group:groupFilter.value,country:countryFilter.value,dates:dateRange.value,keyword:keyword.value}))
function applyAdvancedFilters(value) {
  filter.value=[value.plans.join(','),value.tokens.join(','),value.errors.join(',')].filter(Boolean).join('|') || 'all'
  groupFilter.value=value.group || 'all';countryFilter.value=value.country || 'all';dateRange.value=value.dates;keyword.value=value.keyword || ''
  foldersVisible.value=false;load(true)
}
async function saveAccountView(value) {
  try {
    const {value:name}=await ElMessageBox.prompt('Tên để mở lại bộ lọc trên trình duyệt này.','Lưu bộ lọc',{inputPlaceholder:'Ví dụ: Plus cần làm mới',confirmButtonText:'Lưu',cancelButtonText:'Hủy',inputValidator:value=>Boolean(value?.trim())&&value.trim().length<=64 || 'Nhập tên tối đa 64 ký tự'})
    const saved={...value,id:crypto.randomUUID(),name:name.trim()}
    savedAccountViews.value=[...savedAccountViews.value.filter(item=>item.name!==saved.name),saved].slice(-20)
    localStorage.setItem('registered_saved_views_v1',JSON.stringify(savedAccountViews.value));applyAdvancedFilters(value)
  } catch(error) { if(error?.message) ElMessage.error(error.message) }
}
function removeSavedView(id) { savedAccountViews.value=savedAccountViews.value.filter(view=>view.id!==id);localStorage.setItem('registered_saved_views_v1',JSON.stringify(savedAccountViews.value)) }

const dateShortcuts = computed(() => [
  {
    text: t('今天', 'Hôm nay'),
    value: () => {
      const start = new Date()
      start.setHours(0, 0, 0, 0)
      const end = new Date()
      end.setHours(23, 59, 59, 999)
      return [start, end]
    },
  },
  {
    text: t('昨天', 'Hôm qua'),
    value: () => {
      const start = new Date()
      start.setDate(start.getDate() - 1)
      start.setHours(0, 0, 0, 0)
      const end = new Date()
      end.setDate(end.getDate() - 1)
      end.setHours(23, 59, 59, 999)
      return [start, end]
    },
  },
  {
    text: t('近7天', '7 ngày qua'),
    value: () => {
      const start = new Date()
      start.setDate(start.getDate() - 6)
      start.setHours(0, 0, 0, 0)
      const end = new Date()
      end.setHours(23, 59, 59, 999)
      return [start, end]
    },
  },
  {
    text: t('近30天', '30 ngày qua'),
    value: () => {
      const start = new Date()
      start.setDate(start.getDate() - 29)
      start.setHours(0, 0, 0, 0)
      const end = new Date()
      end.setHours(23, 59, 59, 999)
      return [start, end]
    },
  },
])
const selected = ref([])
const detailedColumns = ref(false)
const toolsOpen = ref(false)
const accountTable = ref(null)
const refreshDialogVisible = ref(false)
const planRetrySource = ref('')
const planRetryEmailOtp = ref(false)
const planRetryInfo = ref(null)
const planRetryLoading = ref(false)
const planRetryError = ref('')
let planRetrySequence = 0
const refreshScope = ref('filter')
const refreshUsable = ref(false)
const singleTaskEmail = ref('')
const tokenJobOperation = ref('token_refresh')
const TOKEN_JOB_LABELS = { token_refresh: 'Làm mới AT', token_check: 'Kiểm tra AT', plus_check: 'Kiểm tra gói', checkout_check: 'Dò checkout', quota_check: 'Kiểm tra quota' }
let savedTaskWorkers = {}
try { savedTaskWorkers = JSON.parse(localStorage.getItem('registered_task_workers') || '{}') || {} } catch (_) {}
const taskWorkerSettings = ref(Object.fromEntries(Object.entries({ token_refresh: 3, token_check: 5, plus_check: 3, checkout_check: 1, quota_check: 1 }).map(([operation, fallback]) => [operation, Math.max(1, Math.min(100, Number(savedTaskWorkers[operation]) || fallback))])))
const tokenTaskWorkers = computed({ get: () => taskWorkerSettings.value[tokenJobOperation.value], set: value => {
  taskWorkerSettings.value = { ...taskWorkerSettings.value, [tokenJobOperation.value]: Math.max(1, Math.min(100, Math.trunc(Number(value) || 1))) }
  localStorage.setItem('registered_task_workers', JSON.stringify(taskWorkerSettings.value))
} })
const tokenDialogIsCheck = computed(() => tokenJobOperation.value !== 'token_refresh')
const tokenDialogTitle = computed(() => TOKEN_JOB_LABELS[tokenJobOperation.value])
const currentJobIsCheck = computed(() => Boolean(refreshJob.value?.operation && refreshJob.value.operation !== 'token_refresh'))
const currentJobIsAt = computed(() => refreshJob.value?.operation === 'token_check')
const currentJobTitle = computed(() => TOKEN_JOB_LABELS[refreshJob.value?.operation] || TOKEN_JOB_LABELS.token_refresh)
const refreshFolderCount = computed(() => groupFilter.value === 'all' ? 0 : groupFilter.value === '__ungrouped__' ? groupsSummary.value.ungrouped : Number(groupsSummary.value.groups.find(group => group.name === groupFilter.value)?.count || 0))
const refreshScopeCount = computed(() => planRetrySource.value ? Number(planRetryInfo.value?.total_candidates || 0) : refreshScope.value === 'single' ? (singleTaskEmail.value ? 1 : 0) : refreshScope.value === 'selected' ? selected.value.length : refreshScope.value === 'page' ? rows.value.length : refreshScope.value === 'folder' ? refreshFolderCount.value : refreshScope.value === 'all' ? groupsSummary.value.total : total.value)
const refreshSpecificScope = computed(() => ['single', 'selected'].includes(refreshScope.value))
const refreshUsableActive = computed(() => !tokenDialogIsCheck.value && refreshSpecificScope.value && refreshUsable.value)
const refreshCandidatesInfo = ref(null)
const refreshCandidatesLoading = ref(false)
const refreshCandidatesError = ref('')
const refreshFilterActive = computed(() => !tokenDialogIsCheck.value)
const refreshTargetCount = computed(() => refreshFilterActive.value ? Number(refreshCandidatesInfo.value?.total_candidates || 0) : refreshScopeCount.value)
function refreshCandidateParams() {
  const params = { ...(refreshScope.value === 'filter' ? accountFilterParams() : { filter: 'all' }), include_missing: true, smart_refresh: true, refresh_usable: refreshUsableActive.value }
  if (refreshScope.value === 'folder') params.group = groupFilter.value
  if (refreshScope.value === 'selected') params.emails = selected.value.map(row => row.email)
  if (refreshScope.value === 'page') params.emails = rows.value.map(row => row.email)
  if (refreshScope.value === 'single') params.emails = [singleTaskEmail.value]
  return params
}
let candidatePreviewSequence = 0
function requestRefreshCandidateInfo() {
  return findExpiredRefreshCandidates(refreshCandidateParams())
}
async function loadRefreshCandidatePreview() {
  const sequence = ++candidatePreviewSequence
  refreshCandidatesInfo.value = null
  refreshCandidatesError.value = ''
  if (!refreshDialogVisible.value || !refreshFilterActive.value) { refreshCandidatesLoading.value = false; return }
  const params = refreshCandidateParams()
  if (params.emails && !params.emails.length) { refreshCandidatesLoading.value = false; return }
  refreshCandidatesLoading.value = true
  try {
    const result = await requestRefreshCandidateInfo()
    if (sequence === candidatePreviewSequence) refreshCandidatesInfo.value = result
  } catch (error) {
    if (sequence === candidatePreviewSequence) refreshCandidatesError.value = 'Chưa lấy được số tài khoản cần làm mới: ' + error.message
  } finally {
    if (sequence === candidatePreviewSequence) refreshCandidatesLoading.value = false
  }
}
function clearAccountSelection() {
  accountTable.value?.clearSelection()
  selected.value = []
}
function toggleAccountSelection(row, checked) {
  const selection = new Map(selected.value.map(item => [item.email, item]))
  if (checked) selection.set(row.email, row)
  else selection.delete(row.email)
  selected.value = [...selection.values()]
}
function togglePageSelection(selection) {
  const checked = new Set(selection.map(row => row.email))
  const next = new Map(selected.value.map(row => [row.email, row]))
  for (const row of rows.value) {
    if (checked.has(row.email)) next.set(row.email, row)
    else next.delete(row.email)
  }
  selected.value = [...next.values()]
}
const selectedEmails = computed(()=>new Set(selected.value.map(row=>row.email)))
watch([accountTable, rows, selected], () => {
  const table = accountTable.value
  if (!table) return
  const checked = new Set(table.getSelectionRows().map(row => row.email))
  for (const row of rows.value) {
    const wanted = selectedEmails.value.has(row.email)
    if (checked.has(row.email) !== wanted) table.toggleRowSelection(row, wanted)
  }
}, { flush: 'post' })
function handleRowAction(command, row) {
  if (command === 'refresh') doSingleRefresh(row)
  if (command === 'check') doSingleCheckLive(row)
  if (command === 'quota') openSingleTask(row, 'quota_check')
  if (command === 'copy_at') copyCell(row.email, 'access_token')
  if (command === 'copy_ls') copyLoginString(row.email)
  if (command === 'clear_auth_error') allowAuthRetry(row)
  if (command === 'edit') openEdit(row)
  if (command === 'delete') deleteOne(row.email)
}
const loading = ref(false)
const checkResult = ref('')

// ── 轻量元数据（国家 / 指纹版本 / 流量 / AT 过期）──
// 由 /api/registered/meta 一次全量返回，本地按 email 映射到表格行。
// 后端没重启（旧版本没有这个接口）时静默降级：列显示「—」，不影响其他功能。
const metaMap = ref({})
const metaReady = ref(false)
const refreshingTokens = ref(false)
const checkingPlus = computed(() => refreshJob.value?.operation === 'plus_check' && refreshJobRunning.value)
const checkingLive = computed(() => currentJobIsAt.value && refreshJobRunning.value)
const refreshingRow = computed(() => {
  if (!refreshJobRunning.value) return {}
  const activeEmails = String(refreshJob.value?.current_email || '').split(',').map(email => email.trim()).filter(Boolean)
  return Object.fromEntries(activeEmails.map(email => [email, true]))
})
const planCheckSummary = computed(() => [
  ['free', 'Free'], ['plus_active', 'Plus'], ['pro_active', 'Pro'], ['go_active', 'Go'],
  ['team_active', 'Team'], ['business_active', 'Business'], ['enterprise_active', 'Enterprise'], ['edu_active', 'Edu'],
  ['multiple_plans', 'Nhiều gói'], ['plus_eligible', 'Free có ưu đãi'], ['banned', 'Khóa'], ['token_invalid', 'AT lỗi'],
].filter(([key]) => refreshJob.value?.counts?.[key]).map(([key, label]) => `${label} ${refreshJob.value.counts[key]}`).join(' · '))
const retryingRefreshErrors = ref(false)
const canRetryRefreshErrors = computed(() => ['token_refresh', 'plus_check'].includes(refreshJob.value?.operation) && !refreshJobRunning.value && refreshJob.value.failed > 0)
async function loadPlanRetryPreview() {
  const source = planRetrySource.value
  if (!source) return
  const sequence = ++planRetrySequence
  planRetryLoading.value = true
  planRetryError.value = ''
  planRetryInfo.value = null
  try {
    const info = await getRefreshRetryCandidates(source, { retry_email_otp: planRetryEmailOtp.value })
    if (sequence === planRetrySequence && source === planRetrySource.value) planRetryInfo.value = info
  } catch (error) {
    if (sequence === planRetrySequence) planRetryError.value = error.message
  } finally {
    if (sequence === planRetrySequence) planRetryLoading.value = false
  }
}
async function openRetryRefreshErrors() {
  if (!canRetryRefreshErrors.value || retryingRefreshErrors.value) return
  const source = refreshJob.value
  if (source.operation === 'plus_check') {
    planRetrySource.value = source.job_id
    planRetryEmailOtp.value = false
    singleTaskEmail.value = ''
    tokenJobOperation.value = 'plus_check'
    refreshProxyMode.value = source.routing?.mode === 'single' ? 'single' : 'pool'
    tokenTaskWorkers.value = Math.min(10, Number(source.routing?.workers) || 3)
    refreshDialogVisible.value = true
    await loadPlanRetryPreview()
    return
  }
  const mode = ['pool', 'single', 'direct'].includes(source.routing?.mode) ? source.routing.mode : refreshProxyMode.value
  if (mode === 'single' && !proxyText(form.value)) {
    ElMessage.warning('Hãy chọn lại proxy riêng của đợt này trước khi thử lại.')
    return
  }
  retryingRefreshErrors.value = true
  try {
    const plan = await getRefreshRetryCandidates(source.job_id)
    if (!plan.emails?.length) {
      ElMessage.info('Không còn acc lỗi có thể thử lại. Acc bị khóa/sai tài khoản/mật khẩu/2FA và AT đã dùng được đã được loại.')
      return
    }
    if (refreshJobRunning.value || refreshJob.value?.job_id !== source.job_id) {
      ElMessage.info('Đã có tác vụ khác. Hãy chờ đợt hiện tại kết thúc.')
      return
    }
    const workers = Math.max(1, Math.min(100, Number(source.routing?.requested_workers || source.routing?.workers || taskWorkerSettings.value.token_refresh) || 3))
    await tokenRefresh.start(plan.emails, proxyText(form.value), Math.max(60, Math.min(600, Number(form.value.otpTimeout) || 180)), mode, false, 'token_refresh', workers, true, false, source.job_id)
    ElMessage.success(`Đã bắt đầu thử lại ${plan.emails.length} acc lỗi có thể cứu.`)
  } catch (error) {
    ElMessage.error('Chưa bắt đầu được đợt thử lại: ' + error.message)
  } finally {
    retryingRefreshErrors.value = false
  }
}
const authFailureSummary = computed(() => {
  const counts = refreshJob.value?.auth_error_counts || {}
  return [
    { label: 'Sai tài khoản / mật khẩu', code: 'invalid_credentials', count: ['invalid_credentials','invalid_password','account_not_found','missing_password'].reduce((n, key) => n + Number(counts[key] || 0), 0) },
    { label: 'Sai hoặc thiếu 2FA', code: 'invalid_2fa', count: ['invalid_2fa','invalid_2fa_secret','missing_2fa'].reduce((n, key) => n + Number(counts[key] || 0), 0) },
    { label: 'Tài khoản bị khóa', code: 'account_disabled', count: Number(counts.account_disabled || 0) },
  ].filter(item => item.count)
})
async function allowAuthRetry(row) {
  try {
    await clearRegisteredRefreshError(row.email)
    row.refresh_error = null
    ElMessage.success('Đã cho phép thử lại. Tài khoản sẽ được xét ở lần làm mới kế tiếp, chưa tự đăng nhập.')
    if (errorFilter.value !== 'all') load(false)
  } catch (error) { ElMessage.error(error.message) }
}
function filterRefreshError(error) {
  const code = error?.error_code || ''
  errorFilter.value = ['invalid_credentials','invalid_password','account_not_found','missing_password'].includes(code) ? 'auth_credentials'
    : ['invalid_2fa','invalid_2fa_secret','missing_2fa'].includes(code) ? 'auth_2fa'
    : code === 'account_disabled' ? 'auth_disabled' : ['email_otp_required','email_mailbox_unavailable','email_otp_timeout'].includes(code) ? 'email_otp_hold' : code === 'email_otp_invalid' ? 'auth_email_otp' : code.startsWith('proxy_') ? 'refresh_network' : 'refresh_errors'
  load(true)
}
watch(refreshJob, (job, previous) => {
  if (!job) return
  for (const item of job.results || []) {
    if (item.skipped) continue
    const isCheck = job.operation && job.operation !== 'token_refresh'
    const row = rows.value.find(row => row.email === item.email)
    if (!row) continue
    if (Object.prototype.hasOwnProperty.call(item, 'refresh_error')) row.refresh_error = item.refresh_error
    if (job.operation === 'token_check') {
      row.token_check = item
      delete row.token_state
      if (Object.prototype.hasOwnProperty.call(item, 'at_exp')) row.at_exp = item.at_exp
    } else if (job.operation === 'quota_check') {
      if (item.quota_check) row.quota_check = item.quota_check
    } else if (isCheck) {
      continue
    } else if (item.ok) {
      row.at_len = item.at_len
      if (item.st_len) row.st_len = item.st_len
      row.at_exp = item.at_exp || 0
      delete row.token_state
      row.token_check = { status: 'valid', checked_at: job.updated_at, at_exp: item.at_exp }
    } else if (item.status === 'banned') {
      row.token_check = { status: 'banned', checked_at: job.updated_at }
      delete row.token_state
    }
  }
  if (job.completed !== previous?.completed && ['queued', 'running', 'stopping'].includes(job.state)) loadMeta()
  if (!['queued', 'running', 'stopping'].includes(job.state) && ['queued', 'running', 'stopping'].includes(previous?.state)) {
    loadMeta(true)
    load()
    if (job.state === 'completed') ElMessage[job.failed ? 'warning' : 'success'](`${TOKEN_JOB_LABELS[job.operation] || 'Tác vụ'}: đã xử lý ${job.completed}/${job.total} tài khoản`)
    else ElMessage.warning(job.error || 'Tác vụ làm mới token đã gián đoạn')
  }
})
let metaLoadedAt = 0
let metaLoadedKey = ''

async function loadMeta(force = false, emails = null) {
  // 只拉当前页需要的行；同一批邮箱 30 秒内不重复拉（翻回上一页也能命中缓存）
  const list = (emails || rows.value.map((r) => r.email) || []).filter(Boolean)
  const key = list.map((e) => String(e).toLowerCase()).sort().join(',')
  if (!force && key && key === metaLoadedKey && Date.now() - metaLoadedAt < 30000) return
  try {
    const { items } = await getRegisteredMeta(list)
    // 增量合并：翻页不会把已经拿到的元数据丢掉
    const map = { ...metaMap.value }
    for (const it of items || []) {
      if (it && it.email) map[String(it.email).toLowerCase()] = it
    }
    metaMap.value = map
    metaReady.value = true
    metaLoadedAt = Date.now()
    metaLoadedKey = key
  } catch (_) {
    // 404 = 后端还没重启到带 meta 接口的版本；保持 metaReady=false 显示占位。
    metaReady.value = false
  }
}

function metaOf(row) {
  return metaMap.value[String(row?.email || '').toLowerCase()] || null
}

function fmtBytes(n) {
  const v = Number(n || 0)
  if (!v) return '0 B'
  if (v < 1024) return `${v} B`
  if (v < 1024 * 1024) return `${(v / 1024).toFixed(1)} KB`
  return `${(v / 1024 / 1024).toFixed(2)} MB`
}

function trafficText(row) {
  const m = metaOf(row)
  if (!m) return ''
  const total = Number(m.traffic_rx || 0) + Number(m.traffic_tx || 0)
  return total ? fmtBytes(total) : ''
}

function accountTaskTraffic(row) {
  const metadata = metaOf(row)
  if (!metadata) return []
  const measurements = []
  if (metadata.registration_traffic) measurements.push({ label: 'Đăng ký', traffic: metadata.registration_traffic })
  else if (metadata.last_run_at && metadata.registration_measured !== false) measurements.push({ label: 'Đăng ký', traffic: { rx: metadata.traffic_rx || 0, tx: metadata.traffic_tx || 0 } })
  for (const [key, label] of [['token_refresh', 'Làm mới token'], ['token_check', 'Quét AT'], ['plus_check', 'Quét gói'], ['checkout_check', 'Dò checkout'], ['quota_check', 'Kiểm tra quota']]) {
    const traffic = metadata.task_traffic?.[key]
    if (traffic) measurements.push({ label, traffic })
  }
  return measurements
}
function accountTrafficTotal(row) {
  const metadata = metaOf(row)
  if (metadata?.traffic_total) return metadata.traffic_total
  const measurements = accountTaskTraffic(row)
  if (!measurements.length) return null
  return { rx: measurements.reduce((n, item) => n + Number(item.traffic.rx || 0), 0), tx: measurements.reduce((n, item) => n + Number(item.traffic.tx || 0), 0), history_limited: true }
}


// The list supplies expiry from the current AT; old page metadata must not replace it.
function atLife(row) {
  const m = metaOf(row)
  const exp = Number(Object.prototype.hasOwnProperty.call(row || {}, 'at_exp') ? row.at_exp : m?.at_exp || row?.token_check?.at_exp || 0)
  if (!exp || !Number.isFinite(exp)) return null
  const date = new Date(exp * 1000)
  if (Number.isNaN(date.getTime())) return null
  const diff = exp - Date.now() / 1000
  const days = Math.abs(diff) / 86400
  return {
    date: date.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' }),
    dateTime: date.toLocaleString('vi-VN', { hour12: false }),
    expired: diff <= 0,
    text: `${diff <= 0 ? 'Quá' : 'Còn'} ${days < 1 ? '<1' : days.toFixed(1).replace('.', ',')} ngày`,
  }
}

// A past API success does not extend the token's actual expiry.
function tokenStatus(row) {
  const state = row?.token_state
  const check = row?.token_check || {}
  const status = state?.status || check.status
  const checked_at = state ? state.checked_at : check.checked_at
  const message = state ? state.message : check.message
  const life = atLife(row)
  if (status === 'banned') return { type: 'danger', text: 'Tài khoản bị khóa', detail: life ? `Hạn ${life.date}` : '', tooltip: message || 'Đã ghi nhận tài khoản bị khóa hoặc vô hiệu hóa', checked_at }
  if (status === 'missing' || row?.at_len === 0) return { type: 'info', text: 'Chưa có AT', tooltip: 'Tài khoản chưa có Access Token', checked_at }
  if (life?.expired || status === 'expired') return { type: 'danger', text: life ? `Hết hạn ${life.date}` : 'AT đã hết hạn', detail: life?.text, tooltip: life ? `Token hết hạn lúc ${life.dateTime}. Kết quả dùng được trước đó không kéo dài thời hạn.` : 'Cần làm mới AT', checked_at }
  if (['rejected', 'expired_401', 'token_invalid'].includes(status)) return { type: 'warning', text: 'AT bị từ chối (401)', detail: life ? `Hạn ${life.date}` : '', tooltip: 'AT đã bị API từ chối; hạn ghi trong token không bảo đảm còn dùng được. ' + (message || ''), checked_at }
  if (life) {
    return { type: 'success', text: `Hạn ${life.date}`, detail: life.text, tooltip: `Thời điểm hết hạn: ${life.dateTime}. ${message || 'Hạn đọc từ AT; chưa xác nhận lại qua API.'}`, checked_at }
  }
  if (['usable', 'valid', 'skipped_usable'].includes(status)) return { type: 'success', text: 'Dùng được · chưa rõ hạn', tooltip: message || 'Đã ghi nhận AT dùng được nhưng chưa đọc được ngày hết hạn', checked_at }
  return { type: 'info', text: 'Chưa rõ hạn', tooltip: message || 'Chưa đọc được ngày hết hạn của AT', checked_at }
}

const PLUS_TYPE = {
  plus_eligible: 'success', plus_active: 'primary', free: 'warning',
  go_active: 'success', pro_active: 'primary', team_active: 'primary', business_active: 'primary',
  enterprise_active: 'primary', edu_active: 'primary', multiple_plans: 'primary',
  // token_invalid（401 且响应体没有封号措辞）仍与 banned 分开显示——判据不同，
  // 不能混成一个。但配色从橙改红：AT 未到期却 401 = 被吊销，实测多半就是封号，
  // 橙色（=号还在）会让主人以为重新登录就能救回来。
  token_invalid: 'danger',
  banned: 'danger', error: 'danger',
}
function plusOf(row) {
  const info = row.plus_check
  if (!info) return null
  if (info.membership_verified) return info
  const labels = { banned: 'Tài khoản bị khóa', token_invalid: 'AT lỗi', no_at: 'Chưa có AT' }
  return { ...info, label: labels[info.status] || (info.membership_verified === false ? 'Chưa xác minh gói' : info.trial_eligible ? 'Có ưu đãi Plus' : info.checked_at ? 'Đã dò ưu đãi' : 'Chưa kiểm tra') }
}
function planEvidenceLabel(row) {
  const info=row.plus_check
  if(!info) return 'Chưa kiểm tra'
  if(info.membership_verified) return info.trial_eligible ? 'Có ưu đãi Plus' : 'Đã xác minh gói'
  if(info.membership_verified===false) return info.label || 'Chưa đủ dữ liệu xác minh'
  return info.trial_eligible ? 'Gói hiện tại chưa xác minh' : info.trial_eligible===false ? 'Không thấy ưu đãi · chưa xác minh gói' : 'Gói hiện tại chưa xác minh'
}
function planTooltip(row) {
  const info = row.plus_check
  if (!info) return 'Chưa quét gói tài khoản'
  const detail = info.membership_verified ? ['Đã xác minh: ' + info.label] : [planEvidenceLabel(row)]
  if (info.checked_at) detail.push('Đã quét: ' + fmtTime(info.checked_at))
  if (info.membership_verified && info.expires_at) detail.push('Hạn thuê bao: ' + new Date(info.expires_at).toLocaleString('vi-VN'))
  if (info.workspaces?.length > 1) detail.push(info.workspaces.length + ' workspace đang có quyền truy cập')
  if (info.trial_eligible) detail.push('Có ghi nhận ưu đãi Plus; ưu đãi khác với gói đang hoạt động')
  return detail.join(' · ')
}

const latestFolderOrder = {revision:0,names:[]}
function applyGroupsSummary(summary) {
  if (!summary || typeof summary !== 'object') return
  const groups=Array.isArray(summary.groups) ? [...summary.groups] : []
  const revision=Number(summary.order_revision || 0)
  if(revision>=latestFolderOrder.revision){latestFolderOrder.revision=revision;latestFolderOrder.names=groups.map(group=>group.name)}
  else {
    const positions=new Map(latestFolderOrder.names.map((name,index)=>[name,index]))
    groups.sort((a,b)=>(positions.get(a.name) ?? positions.size)-(positions.get(b.name) ?? positions.size))
  }
  groupsSummary.value = {
    total: Number(summary.total || 0),
    ungrouped: Number(summary.ungrouped || 0),
    grouped: Number(summary.grouped || 0),
    groups,
  }
}

async function loadGroupsOnly() {
  try {
    const res = await listRegisteredGroups()
    applyGroupsSummary(res)
  } catch (_) {}
}
async function saveFolderOrder(move) {
  if(savingFolderOrder.value)return
  savingFolderOrder.value=true
  try {
    const result=await reorderRegisteredGroup(move.name,move.target,move.position)
    applyGroupsSummary(result)
    ElMessage.success('Đã lưu thứ tự thư mục')
  } catch(error) {
    ElMessage.error('Chưa lưu được thứ tự thư mục: '+error.message)
    await loadGroupsOnly()
  } finally { savingFolderOrder.value=false }
}

function applyCountriesSummary(countries) {
  if (!Array.isArray(countries)) return
  availableCountries.value = countries
}

async function loadCountriesOnly() {
  try {
    const res = await listRegisteredCountries()
    if (res && res.countries) {
      applyCountriesSummary(res.countries)
    }
  } catch (_) {}
}

function rowCountry(row) {
  return (metaOf(row)?.country || row?.country || '').toUpperCase()
}

function quickFilterCountry(c) {
  if (!c) return
  const code = String(c).toUpperCase()
  if (countryFilter.value === code) {
    countryFilter.value = 'all'
  } else {
    countryFilter.value = code
  }
  load(true)
}

function onCountryFilterChange(v) {
  if (!v) countryFilter.value = 'all'
  load(true)
}

let loadSequence = 0
let loadedScopeKey = ''
let summaryLoadedAt = 0
let listRequest = null
onDeactivated(() => { ++loadSequence; listRequest?.abort() })
onUnmounted(() => { ++loadSequence; listRequest?.abort(); clearTimeout(searchTimer) })
async function load(resetPage, refreshSummary = true) {
  const scope = accountFilterParams()
  const scopeKey = JSON.stringify(scope)
  const resetScope = resetPage || scopeKey !== loadedScopeKey
  loadedScopeKey = scopeKey
  const sequence = ++loadSequence
  listRequest?.abort()
  if (refreshSummary) summaryLoadedAt = 0
  if (resetScope) clearAccountSelection()
  if (resetScope && page.value !== 1) { page.value = 1; return }
  loading.value = true
  const request = new AbortController()
  listRequest = request
  const includeSummary = !summaryLoadedAt || Date.now() - summaryLoadedAt >= 30000
  try {
    const params = { ...scope, limit: pageSize.value, offset: (page.value - 1) * pageSize.value, include_summary: includeSummary }
    const { items, total: t, groups_summary, countries_summary } = await listRegistered(params, { signal: request.signal })
    if (sequence !== loadSequence) return
    rows.value = items
    total.value = t
    if (groups_summary) {
      applyGroupsSummary(groups_summary)
    } else if (includeSummary) {
      loadGroupsOnly()
    }
    if (countries_summary) {
      applyCountriesSummary(countries_summary)
    } else if (includeSummary) {
      loadCountriesOnly()
    }
    if (groups_summary && countries_summary) summaryLoadedAt = Date.now()
    loadMeta(false, items.map((r) => r.email))   // 只拉当前页
    if (toolsOpen.value) loadZeroSummary()
  } catch (e) { if (sequence === loadSequence && !request.signal.aborted) ElMessage.error(e.message) }
  finally { if (sequence === loadSequence) loading.value = false }
}

// 勾选了就用勾选的；没勾选就是「全部」——按当前筛选条件跨页把邮箱取全。
async function collectTargetEmails() {
  if (selected.value.length) {
    return { emails: selected.value.map((r) => r.email), scope: 'selected' }
  }
  return { emails: await collectFilteredEmails(null, true), scope: 'all' }
}

// ── Quét trạng thái Token trực tiếp (Live Token Check qua API OpenAI) ──
async function doCheckLive() {
  singleTaskEmail.value = ''
  tokenJobOperation.value = 'token_check'
  refreshScope.value = selected.value.length ? 'selected' : 'filter'
  refreshDialogVisible.value = true
}

// Refreshes run on the server; the page receives progress through short polls.
function openSingleTask(row, operation) {
  if (!row?.email) return
  singleTaskEmail.value = row.email
  tokenJobOperation.value = operation
  refreshUsable.value = operation === 'token_refresh'
  if (operation === 'quota_check' && refreshProxyMode.value === 'direct') refreshProxyMode.value = 'pool'
  refreshScope.value = 'single'
  refreshDialogVisible.value = true
}
function doSingleRefresh(row) { openSingleTask(row, 'token_refresh') }
function doSingleCheckLive(row) { openSingleTask(row, 'token_check') }

async function stopTokenRefresh() {
  try {
    const result = await tokenRefresh.cancel()
    if (result?.state === 'cancelled') ElMessage.success('Đã dừng tác vụ. Kết quả đã xử lý được giữ nguyên.')
    else if (result?.state === 'stopping') ElMessage.info('Đã nhận lệnh dừng. Đang chờ tài khoản hiện tại hoàn tất.')
  } catch (_) {
    ElMessage.warning('Chưa xác nhận được lệnh dừng; hệ thống sẽ tự gửi lại khi có kết nối.')
  }
}

// ── Làm mới hàng loạt Token (Batch 2FA Re-login) ──
function doBatchRefreshTokens() {
  singleTaskEmail.value = ''
  tokenJobOperation.value = 'token_refresh'
  refreshUsable.value = false
  refreshScope.value = selected.value.length ? 'selected' : 'filter'
  refreshDialogVisible.value = true
}

async function submitBatchRefreshTokens() {
  if (tokenJobOperation.value !== 'checkout_check' && refreshProxyMode.value === 'single' && !proxyText(form.value)) {
    ElMessage.warning('Hãy chọn proxy trong cấu hình tác vụ hoặc dùng Kho Proxy.')
    return
  }
  refreshingTokens.value = true
  try {
    if (!refreshScopeCount.value) { ElMessage.info('Phạm vi đã chọn không có tài khoản'); return }
    let emails = []
    const chosen = planRetrySource.value ? null : refreshScope.value === 'single' ? [{email:singleTaskEmail.value}] : refreshScope.value === 'selected' ? selected.value : refreshScope.value === 'page' ? rows.value : null
    if (chosen && !chosen.length) { ElMessage.info('Phạm vi đã chọn không có tài khoản'); return }
    if (planRetrySource.value) {
      const info = await getRefreshRetryCandidates(planRetrySource.value, { retry_email_otp: planRetryEmailOtp.value })
      planRetryInfo.value = info
      emails = info.emails || []
    } else if (refreshFilterActive.value) {
      const candidates = await requestRefreshCandidateInfo()
      refreshCandidatesInfo.value = candidates
      emails = candidates.emails || []
    } else {
      emails = chosen ? chosen.map(row => row.email) : await collectFilteredEmails(null, true)
    }
    if (!emails.length) {
      ElMessage.info(refreshFilterActive.value ? `Không còn acc đủ điều kiện làm mới. Đã có AT dùng được ${(refreshCandidatesInfo.value?.total_unexpired || 0) + (refreshCandidatesInfo.value?.total_usable || 0)}, sai TK/MK/2FA ${refreshCandidatesInfo.value?.total_auth_errors || 0}, bị khóa ${refreshCandidatesInfo.value?.total_banned || 0}, chờ xử lý mail OTP ${refreshCandidatesInfo.value?.total_email_otp_hold || 0}, chưa rõ hạn ${refreshCandidatesInfo.value?.total_unknown || 0}.` : 'Không có tài khoản nào trong phạm vi tác vụ')
      return
    }
    const started = await tokenRefresh.start(emails, proxyText(form.value), Math.max(60, Math.min(600, Number(form.value.otpTimeout) || 180)), refreshProxyMode.value, !tokenDialogIsCheck.value && !refreshUsableActive.value, tokenJobOperation.value, tokenTaskWorkers.value, checkSkipUsable.value, true, planRetrySource.value, true, refreshUsableActive.value, planRetryEmailOtp.value)
    if (planRetrySource.value && started?.job_id) router.replace({ path: '/registered', query: { job: started.job_id } })
    refreshDialogVisible.value = false
    ElMessage.success(`Đã nhận đủ ${emails.length} tài khoản để ${tokenDialogTitle.value.toLowerCase()}.`)
  } catch (error) {
    ElMessage.error('Không khởi động được tác vụ: ' + error.message)
  } finally { refreshingTokens.value = false }
}

// ── Kiểm tra AT theo hạn JWT (nhanh cục bộ) ──
async function doCheckAt() {
  let target
  try { target = await collectTargetEmails() }
  catch (e) { ElMessage.error('Lấy danh sách tài khoản thất bại: ' + e.message); return }
  const { emails, scope } = target
  if (!emails.length) { ElMessage.info('Không có tài khoản nào theo bộ lọc'); return }
  const scopeText = scope === 'selected' ? `${emails.length} tài khoản đã chọn` : `toàn bộ ${emails.length} tài khoản theo bộ lọc`
  if (!(await confirm(
    `Kiểm tra hạn AT theo JWT cho ${scopeText}?\n\n` +
    'Các tài khoản hết hạn JWT sẽ tự động được làm mới bằng Mật khẩu + 2FA.\n' +
    'Thao tác không thay đổi mật khẩu hay 2FA.',
  ))) return

  refreshingTokens.value = true
  const CHUNK = 50
  let checked = 0, validN = 0, expiredN = 0, unknownN = 0, okN = 0, failN = 0
  const failures = []
  try {
    for (let i = 0; i < emails.length; i += CHUNK) {
      const batch = emails.slice(i, i + CHUNK)
      checkResult.value = `Đang kiểm tra AT… ${Math.min(i + batch.length, emails.length)}/${emails.length}`
      const r = await checkRegisteredAt({
        emails: batch,
        proxy: proxyText(form.value),
        otp_timeout: Math.max(60, Math.min(600, Number(form.value.otpTimeout) || 180)),
        refresh_expired: true,
      })
      checked += r.checked || 0
      validN += (r.valid || []).length
      expiredN += (r.expired || []).length
      unknownN += (r.unknown || []).length
      okN += r.refresh?.succeeded || 0
      failN += r.refresh?.failed || 0
      for (const x of r.refresh?.results || []) if (!x.ok) failures.push(x)
    }
    const parts = [`Đã kiểm tra ${checked} acc: Còn hạn ${validN}`]
    if (expiredN) parts.push(`Hết hạn ${expiredN} (Đã làm mới ${okN}${failN ? ` thất bại ${failN}` : ''})`)
    if (unknownN) parts.push(`${unknownN} acc không rõ hạn`)
    checkResult.value = parts.join(' · ')
    if (failN) {
      ElMessage.warning(`Làm mới hoàn tất: Thành công ${okN}, Thất bại ${failN}`)
    } else if (expiredN) {
      ElMessage.success(`Phát hiện ${expiredN} token hết hạn, đã làm mới thành công toàn bộ`)
    } else {
      ElMessage.success('Trạng thái token bình thường, không có tài khoản cần làm mới')
    }
    await loadMeta(true)
    await load()
  } catch (e) {
    checkResult.value = ''
    ElMessage.error('Kiểm tra AT thất bại: ' + (e.response?.data?.detail || e.message))
  } finally { refreshingTokens.value = false }
}

// ── Dò lại quyền nhận Plus (Re-check Plus) ──
function doCheckQuota() {
  singleTaskEmail.value = ''
  if (refreshProxyMode.value === 'direct') refreshProxyMode.value = 'pool'
  tokenJobOperation.value = 'quota_check'
  refreshScope.value = selected.value.length ? 'selected' : 'page'
  refreshDialogVisible.value = true
}

function doCheckPlus() {
  singleTaskEmail.value = ''
  if (refreshProxyMode.value === 'direct') refreshProxyMode.value = 'pool'
  tokenJobOperation.value = 'plus_check'
  refreshScope.value = selected.value.length ? 'selected' : 'filter'
  refreshDialogVisible.value = true
}

// ── 0 元可领汇总 ──
// 全库口径来自后端（扫 extra_json 里的探测结论），本页口径直接数表格里那几行，
// 这样翻页/筛选时顶部提醒跟着变，不会拿全库数字骗人。
const zeroSummary = ref(null)
const pageZeroCount = computed(
  () => rows.value.filter((r) => checkoutLabel(r).text.includes('0đ') || checkoutLabel(r).text.includes('可领')).length,
)

async function loadZeroSummary() {
  try { zeroSummary.value = await getCheckoutSummary() }
  catch (_) { /* 后端还是旧版本时静默降级 */ }
}

// ── UPI 支付金额（来自 int31.space 支付能力探测）──
// 探测结论存在每个号的 plus_check.checkout 里：amount_minor 是最小货币单位
// （分），currency 是币种，payment_method_types 说明支持哪些支付方式。
// 0 元 = 真可领试用；有金额 = 该号发起 checkout 实际要付的钱。
const CHECKOUT_CURRENCY_SYMBOL = { inr: '₹', usd: '$', eur: '€' }

function checkoutOf(row) {
  return row?.plus_check?.checkout || null
}

function fmtCheckoutAmount(checkout) {
  const minor = Number(checkout?.amount_minor)
  if (!Number.isFinite(minor)) return '—'
  const symbol = CHECKOUT_CURRENCY_SYMBOL[String(checkout?.currency || '').toLowerCase()] || ''
  const amount = (minor / 100).toFixed(2)
  return `${symbol}${amount}`
}

function checkoutLabel(row) {
  const checkout = checkoutOf(row)
  if (!checkout) return { text: 'Chưa dò', type: 'info' }
  if (checkout.failure_type === 'CheckoutTransportException') {
    return { text: 'Lỗi mạng', type: 'warning' }
  }
  if (checkout.failure_type) return { text: 'Dò lỗi', type: 'danger' }
  const methods = (checkout.payment_methods || []).map((m) => String(m).toLowerCase())
  if (methods.length && !methods.includes('upi')) {
    return { text: `${fmtCheckoutAmount(checkout)} Không UPI`, type: 'warning' }
  }
  if (Number(checkout.amount_minor) === 0) {
    return { text: '₹0.00 (0đ)', type: 'success' }
  }
  return { text: fmtCheckoutAmount(checkout), type: 'primary' }
}

// 0đ có thể nhận Plus = Dò thành công + hỗ trợ UPI + số tiền 0đ
function isZeroCheckout(row) {
  return checkoutLabel(row).text.includes('0đ') || checkoutLabel(row).text.includes('0.00')
}

// Dò khả năng thanh toán (qua IP tĩnh Ấn Độ)
const capabilityBusy = computed(() => refreshJob.value?.operation === 'checkout_check' && refreshJobRunning.value)

function doCheckoutCapability() {
  singleTaskEmail.value = ''
  tokenJobOperation.value = 'checkout_check'
  refreshScope.value = selected.value.length ? 'selected' : 'filter'
  refreshDialogVisible.value = true
}

// ── 导出勾选的号 ──
// 格式清单来自后端 export_formats.py（账号+密码、+2FA、+AT、+取件url…），
// 以后加格式只改后端那一个文件，前端一行都不用动。
async function doExportSelected(fmt) {
  const emails = selected.value.map((r) => r.email)
  const scope = accountFilterParams()
  if (!emails.length) { ElMessage.info('Vui lòng tích chọn các tài khoản cần xuất trước'); return }
  exporting.value = true
  try {
    const r = await exportRegistered({ format: fmt.id, emails })
    exportedEmails.value = (r.emails || []).filter(Boolean)
    if (r.mode === 'download') {
      saveBlob(b64ToBytes(r.b64), r.filename, r.mime)
      ElMessage.success(`Đã tải xuống ${r.filename} (${r.count} tài khoản)`)
      return
    }
    exportText.value = r.text || ''
    exportCount.value = r.count || 0
    exportFilename.value = r.filename || 'export.txt'
    exportLabel.value = formatLabel(fmt)
    exportVisible.value = true
  } catch (e) { ElMessage.error('Xuất file thất bại: ' + e.message) }
  finally { exporting.value = false }
}


// Shared account toolbar actions.
const groupManagerVisible = ref(false)
function handleAccountCheck(command) {
  if (command === 'at') doCheckLive()
  if (command === 'plan') doCheckPlus()
  if (command === 'quota') doCheckQuota()
  if (command === 'checkout') doCheckoutCapability()
  if (command === 'offers') { toolsOpen.value = !toolsOpen.value; loadZeroSummary() }
}
function handleAccountManage(command) {
  if (command === 'assign') openGroupAssignDialog()
  if (command === 'groups') groupManagerVisible.value = true
  if (command === 'columns') detailedColumns.value = !detailedColumns.value
  if (command === 'delete-all') deleteAll()
}
// End shared account toolbar actions.

// ── Xuất theo bộ lọc / số lượng ──
const scopeVisible = ref(false)
const scopeFormatId = ref('')
const scopeRange = ref('filter')     // filter | selected
const scopeCountMode = ref('all')    // all | limit
const scopeCount = ref(100)
const scopeBusy = ref(false)

const FILTER_LABELS = {
  all: 'Tất cả', unchecked: 'Chưa kiểm tra', free: 'Free (kết quả cũ)', plus: 'Ưu đãi Plus',
  plan_free: 'Free', plan_go: 'Go', plan_plus: 'Plus', plan_pro: 'Pro', plan_team: 'Team', plan_business: 'Business',
  plan_enterprise: 'Enterprise', plan_edu: 'Edu', plan_unknown: 'Chưa xác minh gói',
  plan_paid: 'Gói trả phí', at_needs_refresh: 'Cần làm mới AT',
  offer_checked: 'Đã kiểm tra gói / ưu đãi',
  plus_activated: 'Lịch sử mở Plus', banned: 'Đã khóa', token_invalid: 'AT hết hạn / bị từ chối',
  at_usable: 'Còn hạn / đã dùng được', at_missing: 'Chưa có AT', at_unknown: 'Chưa rõ hạn', at_banned: 'Bị khóa khi quét',
  refresh_errors: 'Có lỗi làm mới', auth_credentials: 'Sai tài khoản / mật khẩu', auth_2fa: 'Sai hoặc thiếu 2FA',
  auth_disabled: 'Bị khóa khi đăng nhập', auth_email_otp: 'Lỗi OTP email', email_otp_hold: 'Chờ xử lý mail OTP', refresh_network: 'Lỗi proxy / mạng',
}
const activeFilters = computed(() => {
  const items = []
  if (groupFilter.value !== 'all') items.push({ key: 'group', label: groupFilter.value === '__ungrouped__' ? 'Chưa phân thư mục' : 'Thư mục: ' + groupFilter.value })
  for (const [key, value, label] of [['plan', planFilter.value, 'Gói'], ['token', tokenFilter.value, 'AT'], ['error', errorFilter.value, 'Lỗi']]) {
    if (value !== 'all') items.push({ key, label: label + ': ' + value.split(',').map(value=>FILTER_LABELS[value]).join(' / ') })
  }
  if (countryFilter.value !== 'all') items.push({ key: 'country', label: 'Quốc gia: ' + countryFilter.value })
  if (keyword.value.trim()) items.push({ key: 'q', label: 'Email: ' + keyword.value.trim() })
  if (dateRange.value?.length === 2) items.push({ key: 'date', label: dateRange.value.map(date => date.split('-').reverse().join('/')).join(' – ') })
  return items
})
const scopeFilterLabel = computed(() => activeFilters.value.map(item => item.label).join(' · ') || 'Tất cả')
const quickView = computed(() => {
  if (planFilter.value === 'all' && tokenFilter.value === 'all' && errorFilter.value === 'all') return 'all'
  if (planFilter.value === 'all' && tokenFilter.value === 'at_needs_refresh' && errorFilter.value === 'all') return 'needs'
  if (planFilter.value === 'all' && tokenFilter.value === 'all' && errorFilter.value === 'refresh_errors') return 'errors'
  if (planFilter.value === 'plan_paid' && tokenFilter.value === 'all' && errorFilter.value === 'all') return 'paid'
  if (planFilter.value === 'plus' && tokenFilter.value === 'all' && errorFilter.value === 'all') return 'offers'
  return ''
})
function applyQuickView(value) {
  filter.value = ({needs:'at_needs_refresh',errors:'refresh_errors',paid:'plan_paid',offers:'plus'})[value] || 'all'
  load(true)
}
function clearFilter(key) {
  if (key === 'group') groupFilter.value = 'all'
  if (key === 'plan') planFilter.value = 'all'
  if (key === 'token') tokenFilter.value = 'all'
  if (key === 'error') errorFilter.value = 'all'
  if (key === 'country') countryFilter.value = 'all'
  if (key === 'q') keyword.value = ''
  if (key === 'date') dateRange.value = null
  load(true)
}
function clearAllFilters() {
  filter.value = 'all'
  groupFilter.value = countryFilter.value = 'all'
  keyword.value = ''
  dateRange.value = null
  load(true)
}

async function openScopeExport(format = '') {
  await loadExportFormats()
  scopeFormatId.value = typeof format === 'string' && format ? format : (scopeFormatId.value || exportFormats.value[0]?.id || '')
  scopeRange.value = selected.value.length ? 'selected' : 'filter'
  scopeCountMode.value = 'all'
  scopeVisible.value = true
}

function accountFilterParams() {
  const params = { filter: filter.value }
  if (groupFilter.value && groupFilter.value !== 'all') {
    params.group = groupFilter.value
  }
  if (countryFilter.value && countryFilter.value !== 'all') {
    params.country = countryFilter.value
  }
  if (keyword.value && keyword.value.trim()) {
    params.q = keyword.value.trim()
  }
  if (dateRange.value && dateRange.value.length === 2 && dateRange.value[0] && dateRange.value[1]) {
    const d0 = new Date(dateRange.value[0])
    d0.setHours(0, 0, 0, 0)
    const d1 = new Date(dateRange.value[1])
    d1.setHours(23, 59, 59, 999)
    params.start_time = Math.floor(d0.getTime() / 1000)
    params.end_time = Math.floor(d1.getTime() / 1000)
  }
  return params
}

async function collectFilteredEmails(limit = null, requireAll = false) {
  const result = await resolveRegisteredSelection({ ...accountFilterParams(), ...(limit ? { limit } : {}) })
  if (requireAll && result.truncated) throw new Error(`Có ${result.total} tài khoản, vượt giới hạn ${limit.toLocaleString('vi-VN')} của tác vụ. Hãy chọn nhóm hoặc thu hẹp bộ lọc.`)
  return result.emails || []
}

async function doScopeExport() {
  const fmt = exportFormats.value.find((f) => f.id === scopeFormatId.value)
  if (!fmt) { ElMessage.warning('Vui lòng chọn định dạng xuất file'); return }
  scopeBusy.value = true
  try {
    let emails = []
    if (scopeRange.value === 'selected') {
      emails = selected.value.map((r) => r.email)
    } else {
      const want = scopeCountMode.value === 'limit'
        ? Math.max(1, Math.floor(Number(scopeCount.value) || 1))
        : null
      emails = await collectFilteredEmails(want, scopeCountMode.value === 'all')
    }
    if (!emails.length) { ElMessage.info('Không có tài khoản nào trong phạm vi xuất'); return }
    exporting.value = true
    const r = await exportRegistered({ format: fmt.id, emails })
    exportedEmails.value = (r.emails || []).filter(Boolean)
    if (r.mode === 'download') {
      saveBlob(b64ToBytes(r.b64), r.filename, r.mime)
      ElMessage.success(`Đã tải xuống ${r.filename} (${r.count} tài khoản)`)
    } else {
      exportText.value = r.text || ''
      exportCount.value = r.count || 0
      exportFilename.value = r.filename || 'export.txt'
      exportLabel.value = formatLabel(fmt)
      exportVisible.value = true
    }
    scopeVisible.value = false
  } catch (e) {
    ElMessage.error('Xuất file thất bại: ' + e.message)
  } finally {
    scopeBusy.value = false
    exporting.value = false
  }
}

// customClass: 'confirm-multiline' để xuống dòng \n trong dialog
async function confirm(msg) {
  try {
    await ElMessageBox.confirm(msg, 'Xác nhận', {
      type: 'warning', confirmButtonText: 'Xác nhận', cancelButtonText: 'Hủy',
      customClass: 'confirm-multiline',
    })
    return true
  }
  catch (_) { return false }
}
async function deleteOne(email) {
  if (!(await confirm(`Xóa thông tin xác thực của ${email}?`))) return
  try { await deleteRegistered(email); ElMessage.success('Đã xóa thành công'); clearAccountSelection(); load() }
  catch (e) { ElMessage.error(e.message) }
}
async function deleteSelected() {
  if (deletingAccounts.value) return
  const emails = selected.value.map((r) => r.email)
  if (!emails.length) return
  if (!(await confirm(`Bạn có chắc chắn muốn xóa ${emails.length} tài khoản đã chọn? (Không thể hoàn tác)`))) return
  deletingAccounts.value = true
  try { const r = await bulkDeleteRegistered({ emails, scope }); reportDeleted(r); load(true) }
  catch (e) { ElMessage.error(e.message) }
  finally { deletingAccounts.value = false }
}
async function deleteAll() {
  if (!(await confirm('Thao tác này sẽ xóa toàn bộ tài khoản trong danh sách Đã đăng ký! Kho mail không bị ảnh hưởng, bạn có chắc chắn?'))) return
  if (!(await confirm('Xác nhận lần 2: Thao tác này KHÔNG THỂ HOÀN TÁC! Bạn có chắc muốn xóa sạch toàn bộ?'))) return
  try { const r = await bulkDeleteRegistered({ all: true }); reportDeleted(r); load(true) }
  catch (e) { ElMessage.error(e.message) }
}
const deletingAccounts = ref(false)
function reportDeleted(result) {
  const held = Number(result.skipped_busy || 0)
  const changed = Number(result.skipped_changed || 0)
  ElMessage[held || changed ? 'warning' : 'success'](`Đã xóa ${result.deleted} tài khoản${held ? `. Giữ lại ${held} acc đang chờ hoặc đang xử lý.` : ''}${changed ? ` Bỏ qua ${changed} acc không còn khớp bộ lọc.` : ''}`)
}
async function deleteFiltered() {
  if (deletingAccounts.value || !activeFilters.value.length) return
  deletingAccounts.value = true
  const scope = scopeFilterLabel.value
  const scopeParams = accountFilterParams()
  const fingerprint = JSON.stringify(scopeParams)
  try {
    const emails = await collectFilteredEmails(null, true)
    if (fingerprint !== JSON.stringify(accountFilterParams())) throw new Error('Điều kiện lọc đã đổi; hãy bấm xóa lại với bộ lọc mới.')
    if (!emails.length) { ElMessage.info('Không có tài khoản khớp bộ lọc'); return }
    if (!(await confirm(`Xóa ${emails.length} tài khoản khớp bộ lọc trên tất cả các trang?\n${scope}\nAcc còn chờ hoặc đang xử lý sẽ được giữ lại. Không thể hoàn tác.`))) return
    const result = await bulkDeleteRegistered({ emails, scope: scopeParams })
    reportDeleted(result)
    await load(true)
  } catch (error) { ElMessage.error(error.message) }
  finally { deletingAccounts.value = false }
}

// ──────────── 批量导出 ────────────
// 格式清单来自后端 export_formats.py，下拉菜单是 v-for 出来的：
// 以后加格式只改后端那一个文件，这里一行都不用动。
const exportFormats = ref([])
function formatLabel(format) {
  return ({ at: 'Chỉ Access Token (AT)', email_pw: 'Email · Mật khẩu', email_pw_2fa: 'Email · Mật khẩu · 2FA', email_pw_2fa_relay: 'Email · Mật khẩu · 2FA · Link nhận mã', email_pw_2fa_at: 'Email · Mật khẩu · 2FA · AT' })[format?.id] || format?.label || ''
}
const exporting = ref(false)
const exportVisible = ref(false)
const exportText = ref('')
const exportCount = ref(0)
const exportFilename = ref('')
const exportLabel = ref('')
// 这一批导出的到底是哪些号 —— 「下载并删除」照着它删，来自后端 r.emails。
// 为什么要后端给、为什么在导出那一刻就存下来：
//   · 「导出全部」是跨页的，前端手里只有当前页 20 行，自己凑必漏；
//   · 弹窗开着的时候主人可能改勾选、翻页，后台自动跑号还会插进新号进来，
//     那时再去读 selected/表格，删的就不是刚下载的那批了。
const exportedEmails = ref([])
const deletingExported = ref(false)

async function loadExportFormats() {
  if (exportFormats.value.length) return
  try {
    const { formats } = await listExportFormats()
    exportFormats.value = formats || []
  } catch (e) { ElMessage.error('Tải danh sách định dạng xuất thất bại: ' + e.message) }
}

function b64ToBytes(b64) {
  const bin = atob(b64 || '')
  const bytes = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
  return bytes
}

function saveBlob(data, filename, mime) {
  const blob = data instanceof Blob ? data : new Blob([data], { type: mime || 'application/octet-stream' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

function downloadExport() {
  saveBlob(exportText.value, exportFilename.value, 'text/plain;charset=utf-8')
}

// ──────────── 下载并删除 ────────────
// 主人的原话：「不然分不清楚越堆越多」。导出的 txt 里邮箱/密码/2FA/取件url 都齐了，
// 这两张表就没有留存价值了，一起清掉。
//
// ⚠️ 顺序**必须**是「先下载、再确认、最后删」：
//    删库是不可恢复的，而浏览器下载可能被拦（弹窗拦截 / 用户点了取消 / 磁盘满）。
//    先把文件落盘再问，主人是在**手里已经有 txt** 的前提下点的确认。
//    确认框里再报一遍将要删的两张表各多少条，删完之前还有最后一次反悔机会。
async function downloadAndDelete() {
  downloadExport()

  const emails = exportedEmails.value
  if (!emails.length) {
    ElMessage.warning('Đợt xuất này không lấy được danh sách email, chỉ tải file chứ không xóa dữ liệu')
    return
  }

  const ok = await confirm(
    `Đã tải xuống file ${exportFilename.value}.\n\n` +
    `Tiến hành xóa ${emails.length} tài khoản này khỏi hệ thống:\n` +
    `  • Xóa toàn bộ thông tin tài khoản (Mật khẩu, 2FA secret, Token)\n` +
    `  • Xóa tài khoản tương ứng trong Kho Email\n\n` +
    `Sau khi xóa, dữ liệu chỉ còn lưu trong file .txt bạn vừa tải về. Thao tác không thể hoàn tác, bạn có chắc chắn?`,
  )
  if (!ok) return

  deletingExported.value = true
  try {
    const r1 = await bulkDeleteRegistered({ emails })
    let poolDeleted = 0
    try {
      const r2 = await bulkDeleteAccounts({ emails })
      poolDeleted = r2.deleted || 0
    } catch (e) {
      ElMessage.warning('Đã xóa trong danh sách Đã đăng ký, nhưng xóa trong Kho email thất bại: ' + e.message)
    }
    ElMessage.success(`Đã xóa: Đã đăng ký ${r1.deleted} acc / Kho email ${poolDeleted} acc`)
    exportVisible.value = false
    exportedEmails.value = []
    selected.value = []
    load(true)          // 回第一页：这一批没了，停在旧页码多半是空页
    runtime.bumpData()  // 通知「邮箱列表」那一页也刷新，否则主人切过去还看得到已删的号
  } catch (e) {
    ElMessage.error('删除失败: ' + e.message)
  } finally {
    deletingExported.value = false
  }
}

// ── Quản lý Nhóm tài khoản (Phân nhóm & Lọc theo nhóm) ──
const groupAssignVisible = ref(false)
const groupAssignBusy = ref(false)
const groupAssignRange = ref('selected') // 'selected' | 'filter_limit' | 'filter_all'
const groupAssignLimit = ref(50)
const groupAssignTarget = ref('')

const groupNamesList = computed(() =>
  (groupsSummary.value.groups || []).map((g) => g.name).filter(Boolean),
)

function selectGroup(g) {
  groupFilter.value = g || 'all'
  foldersVisible.value=false
  load(true, false)
}

async function promptCreateGroup(assignEmailsAfter = []) {
  try {
    const { value } = await ElMessageBox.prompt(
      'Tên thư mục để sắp xếp tài khoản.',
      'Tạo thư mục',
      {
        confirmButtonText: 'Tạo thư mục',
        cancelButtonText: 'Hủy',
        inputPlaceholder: 'Nhập tên thư mục…',
        inputValidator: (v) => {
          const s = (v || '').trim()
          if (!s) return 'Tên thư mục không được để trống'
          if (s === 'all' || s === '__ungrouped__') return 'Tên thư mục không hợp lệ'
          return true
        },
      },
    )
    const name = (value || '').trim()
    if (!name) return
    const res = await createRegisteredGroup(name)
    applyGroupsSummary(res)
    if (assignEmailsAfter && assignEmailsAfter.length) {
      await assignEmailsToGroup(assignEmailsAfter, name)
    } else {
      ElMessage.success(`Đã tạo thư mục «${name}»`)
    }
  } catch (error) { if(error?.message) ElMessage.error(error.message) }
}

async function promptRenameGroup(oldName) {
  try {
    const { value } = await ElMessageBox.prompt(
      `Đổi tên thư mục «${oldName}» thành:`,
      'Đổi tên thư mục',
      {
        confirmButtonText: 'Lưu',
        cancelButtonText: 'Hủy',
        inputValue: oldName,
        inputValidator: (v) => {
          const s = (v || '').trim()
          if (!s) return 'Tên thư mục không được để trống'
          if (s === 'all' || s === '__ungrouped__') return 'Tên thư mục không hợp lệ'
          return true
        },
      },
    )
    const newName = (value || '').trim()
    if (!newName || newName === oldName) return
    const res = await renameRegisteredGroup(oldName, newName)
    applyGroupsSummary(res)
    if (groupFilter.value === oldName) {
      groupFilter.value = newName
    }
    ElMessage.success(`Đã đổi tên thư mục thành «${newName}»`)
    await load(false)
  } catch (e) {
    if (e && e !== 'cancel' && e.message) ElMessage.error(e.message)
  }
}

async function handleDeleteGroup(name) {
  const grp = (groupsSummary.value.groups || []).find((g) => g.name === name)
  const cnt = grp ? grp.count : 0
  const ok = await confirm(
    `Xóa thư mục «${name}» (${cnt} tài khoản)?\n\n` +
    `Tài khoản được giữ lại và chuyển về «Chưa phân thư mục».`,
  )
  if (!ok) return
  try {
    const res = await deleteRegisteredGroup(name, false)
    applyGroupsSummary(res)
    if (groupFilter.value === name) {
      groupFilter.value = 'all'
    }
    ElMessage.success(`Đã xóa thư mục «${name}»`)
    await load(true)
  } catch (e) {
    ElMessage.error('Xóa thư mục thất bại: ' + e.message)
  }
}

async function assignEmailsToGroup(emails, targetGroup, scope = null) {
  if (!emails || !emails.length) {
    ElMessage.warning('Chưa có tài khoản nào được chọn')
    return
  }
  try {
    const res = await assignRegisteredGroup(emails, targetGroup, scope)
    applyGroupsSummary(res)
    if (targetGroup) {
      ElMessage.success(`Đã chuyển ${res.updated} tài khoản vào thư mục «${targetGroup}»`)
    } else {
      ElMessage.success(`Đã đưa ${res.updated} tài khoản về Chưa phân thư mục`)
    }
    if(res.skipped_changed) ElMessage.warning(`Bỏ qua ${res.skipped_changed} tài khoản đã thay đổi hoặc không còn trong phạm vi.`)
    clearAccountSelection();await load(false)
    return true
  } catch (e) {
    ElMessage.error('Chuyển thư mục thất bại: ' + e.message)
    return false
  }
}

function handleBulkGroupCommand(cmd) {
  const emails = selected.value.map((r) => r.email)
  if (cmd === '__advanced__') {
    openGroupAssignDialog()
    return
  }
  if (!emails.length) {
    ElMessage.warning('Vui lòng tích chọn tài khoản trên bảng trước')
    return
  }
  if (cmd === '__new__') {
    promptCreateGroup(emails)
    return
  }
  if (cmd === '__clear__') {
    assignEmailsToGroup(emails, '')
    return
  }
  if (cmd && cmd.startsWith('group:')) {
    assignEmailsToGroup(emails, cmd.slice(6))
  }
}

function handleRowGroupCommand(row, cmd) {
  if (!row || !row.email) return
  if (cmd === '__new__') {
    promptCreateGroup([row.email])
    return
  }
  if (cmd === '__clear__') {
    assignEmailsToGroup([row.email], '')
    return
  }
  if (cmd && cmd.startsWith('group:')) {
    assignEmailsToGroup([row.email], cmd.slice(6))
  }
}

function openGroupAssignDialog() {
  if (selected.value.length > 0) {
    groupAssignRange.value = 'selected'
  } else {
    groupAssignRange.value = 'filter_all'
  }
  groupAssignTarget.value = ''
  groupAssignVisible.value = true
}

async function doGroupAssignDialog() {
  const targetGroup = (groupAssignTarget.value || '').trim()
  if (targetGroup === '__clear__') {
    // Bỏ khỏi nhóm
  } else if (!targetGroup) {
    ElMessage.warning('Vui lòng chọn hoặc nhập tên thư mục đích')
    return
  }
  groupAssignBusy.value = true
  const scope=accountFilterParams()
  try {
    let emails = []
    if (groupAssignRange.value === 'selected') {
      emails = selected.value.map((r) => r.email)
    } else if (groupAssignRange.value === 'filter_limit') {
      const want = Math.max(1, Math.floor(Number(groupAssignLimit.value) || 50))
      emails = await collectFilteredEmails(want)
    } else {
      emails = await collectFilteredEmails(null, true)
    }
    if (!emails.length) {
      ElMessage.warning('Không có tài khoản nào trong phạm vi đã chọn')
      return
    }
    if(JSON.stringify(scope)!==JSON.stringify(accountFilterParams())) throw new Error('Bộ lọc đã thay đổi. Mở lại thao tác chuyển để kiểm tra phạm vi.')
    if(await assignEmailsToGroup(emails, targetGroup === '__clear__' ? '' : targetGroup,scope)) groupAssignVisible.value = false
  } catch (e) {
    ElMessage.error('Chuyển thư mục thất bại: ' + e.message)
  } finally {
    groupAssignBusy.value = false
  }
}
async function moveFolderAccounts(name) {
  groupFilter.value=name;filter.value='all';keyword.value='';countryFilter.value='all';dateRange.value=null
  await load(true);clearAccountSelection();groupAssignRange.value='filter_all';groupAssignTarget.value='';groupAssignVisible.value=true;foldersVisible.value=false
}

// ── 导入已注册账号 ──
const importDialogVisible = ref(false)
const importText = ref('')
const importGroup = ref('')
const importLoading = ref(false)
const importResult = ref('')

function openImportDialog() {
  importText.value = ''
  importResult.value = ''
  importGroup.value = (groupFilter.value && groupFilter.value !== 'all' && groupFilter.value !== '__ungrouped__')
    ? groupFilter.value
    : ''
  importDialogVisible.value = true
}

function handleFileUpload(file) {
  const rawFile = file.raw || file
  if (!rawFile) return false
  const reader = new FileReader()
  reader.onload = (e) => {
    importText.value = e.target.result || ''
    ElMessage.success('Đã tải nội dung file')
  }
  reader.readAsText(rawFile)
  return false
}

async function doImportRegistered() {
  if (!importText.value.trim()) {
    ElMessage.warning('Vui lòng nhập nội dung hoặc chọn file')
    return
  }
  importLoading.value = true
  importResult.value = ''
  try {
    const res = await importRegistered(importText.value.trim(), (importGroup.value || '').trim())
    importResult.value = `Tổng cộng: ${res.total} | Thêm mới: ${res.inserted} | Cập nhật: ${res.updated} | Thất bại: ${res.failed}`
    if (res.errors && res.errors.length) {
      importResult.value += '\n\n' + res.errors.slice(0, 10).join('\n')
    }
    if (res.groups_summary) applyGroupsSummary(res.groups_summary)
    ElMessage.success(`Nhập hoàn tất: Thêm mới ${res.inserted}, Cập nhật ${res.updated}`)
    filter.value = 'all'
    countryFilter.value = 'all'
    if ((importGroup.value || '').trim()) {
      groupFilter.value = importGroup.value.trim()
    }
    await load(true)
    if (res.failed === 0) {
      setTimeout(() => {
        importDialogVisible.value = false
      }, 1200)
    }
  } catch (e) {
    ElMessage.error('Nhập thất bại: ' + e.message)
  } finally {
    importLoading.value = false
  }
}

// 凭证弹窗
const credVisible = ref(false)
const tokenDetailVisible = ref(false), tokenDetailRow = ref(null)
function viewTokenStatus(row) { tokenDetailRow.value = row; tokenDetailVisible.value = true }
const credEmail = ref('')
const credData = ref(null)
// totp_secret 放最前：它是唯一「服务端取不回」的字段，弹窗一打开就要能看到
const CRED_KEYS = ['totp_secret', 'totp_factor_id', 'access_token', 'session_token', 'id_token', 'device_id', 'csrf_token', 'cookie_header', 'password']
const credRows = computed(() => {
  if (!credData.value) return []
  return CRED_KEYS.filter((k) => credData.value[k]).map((k) => ({ key: k, val: credData.value[k] }))
})
async function viewCred(email) {
  try {
    const { data } = await getRegistered(email)
    credData.value = data
    credEmail.value = email
    credVisible.value = true
  } catch (e) { ElMessage.error('Tải thông tin thất bại: ' + e.message) }
}
async function copyLoginString(email) {
  try {
    const { data } = await getRegistered(email)
    await copyText([data.email || email, data.password || '', data.totp_secret || ''].join('---'))
  } catch (e) { ElMessage.error('Sao chép LS thất bại: ' + e.message) }
}

async function copyCell(email, field) {
  try {
    const { data } = await getRegistered(email)
    const val = data[field] || ''
    if (!val) { ElMessage.warning(`Trường ${field} trống`); return }
    await copyText(val)
  } catch (e) { ElMessage.error('Tải thông tin thất bại: ' + e.message) }
}
function copyAllJson() {
  if (credData.value) copyText(JSON.stringify(credData.value, null, 2))
}

// ── 手动编辑凭证 ──
// 只改本地库，不同步 OpenAI。改完的值会被登录流程直接用上
// （registrar 的 account_callback 走 db.get_registered，不区分数据来源）。
const editVisible = ref(false)
const editSaving = ref(false)
const editEmail = ref('')
const editPassword = ref('')
const editSecret = ref('')
// 打开弹窗时的原值，用来判断哪些字段真被改过（没改的不传，后端就不碰）
const editOrigPassword = ref('')
const editOrigSecret = ref('')

function openEdit(row) {
  editEmail.value = row.email
  editPassword.value = row.password || ''
  editSecret.value = row.totp_secret || ''
  editOrigPassword.value = row.password || ''
  editOrigSecret.value = row.totp_secret || ''
  editVisible.value = true
}

async function saveEdit() {
  const pw = editPassword.value
  const sec = editSecret.value.trim()
  const payload = { email: editEmail.value }
  // 只把真正改动过的字段传给后端 —— 没动的字段不传，后端就不会碰它
  if (pw !== editOrigPassword.value) payload.password = pw
  if (sec !== editOrigSecret.value) payload.totp_secret = sec
  if (payload.password === undefined && payload.totp_secret === undefined) {
    ElMessage.info('Không có thay đổi nào')
    editVisible.value = false
    return
  }
  if (payload.totp_secret !== undefined && editOrigSecret.value) {
    try {
      await ElMessageBox.confirm(
        `Tài khoản này đã có mã 2FA secret:\n${editOrigSecret.value}\n\n` +
        'Nếu ghi đè, mã secret cũ sẽ bị mất vĩnh viễn.\n' +
        'Nếu mã cũ vẫn đang hiệu lực trên OpenAI, việc ghi đè sai sẽ khiến tài khoản không đăng nhập được.',
        'Xác nhận ghi đè mã 2FA secret?',
        { type: 'warning', confirmButtonText: 'Xác nhận ghi đè', cancelButtonText: 'Hủy' },
      )
    } catch { return }
  }
  editSaving.value = true
  try {
    const r = await updateCredentials(payload)
    ElMessage.success(`Đã lưu thành công: ${(r.changed || []).join(' + ') || 'Không thay đổi'}`)
    editVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error('Lưu thất bại: ' + (e.response?.data?.detail || e.message))
  } finally { editSaving.value = false }
}

let searchTimer = null
watch(planRetryEmailOtp, () => { if (planRetrySource.value) loadPlanRetryPreview() })
watch(refreshDialogVisible, open => {
  if (!open) { planRetrySource.value = ''; planRetryInfo.value = null; ++planRetrySequence; planRetryLoading.value = false; planRetryError.value = '' }
})
watch(refreshScope, () => { if (!refreshSpecificScope.value) refreshUsable.value = false })
watch(() => refreshDialogVisible.value && refreshFilterActive.value ? JSON.stringify({ ...refreshCandidateParams(), scope: refreshScope.value }) : '', loadRefreshCandidatePreview)
watch(keyword, () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => load(true, false), 350)
})

watch(page, () => load(false, false))
watch(pageSize, (v) => {
  localStorage.setItem('reg.pageSize', String(v))
  load(true, false)
})
// 自动跑号期间 run_started/run_finished 事件很密（20 并发），每次都重拉整页
// 会让页面发卡 —— 这里节流到最多 5 秒一次。
let lastAutoReload = 0
watch(dataVersion, () => {
  if (!active.value) return
  const now = Date.now()
  if (now - lastAutoReload < 10000) return
  lastAutoReload = now
  load()
})
function openRouteContext() {
  const email = typeof route.query.email === 'string' ? route.query.email.trim().toLowerCase() : ''
  const targetAccount = email.length <= 254 && email.includes('@') && !/[\s\x00-\x1f]/.test(email)
  const view = route.query.view
  if (targetAccount) {
    filter.value = 'all'; groupFilter.value = 'all'; countryFilter.value = 'all'; dateRange.value = null; keyword.value = email
    if (route.query.refresh === 'force') doSingleRefresh({ email })
  } else {
    if (['needs','errors','paid'].includes(view)) filter.value = ({needs:'at_needs_refresh',errors:'refresh_errors',paid:'plan_paid'})[view]
    if (view === 'errors' && ERROR_FILTERS.includes(route.query.error)) errorFilter.value = route.query.error
  }
  if (route.query.job) {
    const jobId = String(route.query.job)
    tokenRefresh.follow(jobId).then(() => {
      if (active.value && route.query.job === jobId && route.query.retry === 'plan' && refreshJob.value?.job_id === jobId) {
        openRetryRefreshErrors()
        router.replace({ path: '/registered', query: { job: jobId } })
      }
    }).catch(error => ElMessage.error(error.message))
  }
  else tokenRefresh.restore()
  return targetAccount
}
watch(() => route.query, () => { if (active.value) { openRouteContext(); load(true) } })
onActivated(() => {
  active.value = true
  document.addEventListener('visibilitychange', updateCredentialClock)
  updateCredentialClock()
  load(openRouteContext())
})
</script>
<template>
  <div class="page registered-page">
    <div class="page-heading accounts-heading"><div><h1>Tài khoản</h1><p>Tìm kiếm, phân nhóm và quản lý tài khoản.</p></div><div class="heading-actions"><el-button @click="load(false)" :loading="loading"><el-icon><Refresh /></el-icon>Tải danh sách</el-button><el-button type="primary" @click="openImportDialog"><el-icon><Plus /></el-icon>Nhập tài khoản</el-button></div></div>
    <el-dialog append-to-body v-model="tokenDetailVisible" title="Trạng thái Access Token" width="460px"><div v-if="tokenDetailRow" class="token-details"><strong class="mono">{{ tokenDetailRow.email }}</strong><el-tag :type="tokenStatus(tokenDetailRow).type">{{ tokenStatus(tokenDetailRow).text }}</el-tag><span>{{ tokenStatus(tokenDetailRow).detail }}</span><p>{{ tokenStatus(tokenDetailRow).tooltip }}</p><small v-if="tokenStatus(tokenDetailRow).checked_at">Đã kiểm tra: {{ fmtTime(tokenStatus(tokenDetailRow).checked_at) }}</small></div><template #footer><el-button :disabled="refreshJobRunning" @click="tokenDetailVisible = false; doSingleCheckLive(tokenDetailRow)">Kiểm tra AT…</el-button><el-button type="primary" :disabled="refreshJobRunning" @click="tokenDetailVisible = false; doSingleRefresh(tokenDetailRow)">Làm mới AT…</el-button></template></el-dialog>
    <el-dialog append-to-body v-model="refreshDialogVisible" :title="refreshUsableActive ? 'Cưỡng chế làm mới AT' : tokenDialogTitle" width="560px" top="4vh" class="account-scope-dialog token-task-dialog" :close-on-click-modal="!refreshingTokens" :show-close="!refreshingTokens">
      <el-form label-position="top">
        <template v-if="planRetrySource">
          <p>Quét lại tài khoản lỗi của đợt đã chọn, bao gồm mọi trang kết quả.</p>
          <el-checkbox v-model="planRetryEmailOtp" :disabled="refreshingTokens">Kiểm tra lại lỗi OTP mail đã lưu</el-checkbox>
          <p class="hint">Cho phép thử đăng nhập lại một lần trong đợt này. Nếu máy chủ thực sự yêu cầu OTP email, vẫn cần đường nhận mã hợp lệ.</p>
          <p v-if="planRetryInfo" class="hint">Tổng lỗi {{ planRetryInfo.total_failed }} · Đã kiểm tra gói thành công {{ planRetryInfo.excluded_usable }} · Khóa hoặc sai thông tin {{ planRetryInfo.excluded_terminal }} · Chờ OTP {{ planRetryInfo.excluded_email_otp }} · Không còn trong kho {{ planRetryInfo.excluded_missing }}<template v-if="planRetryInfo.email_otp_rechecks"> · Kiểm tra lại OTP {{ planRetryInfo.email_otp_rechecks }}</template></p>
          <p v-if="planRetryLoading" class="hint">Đang lấy toàn bộ tài khoản lỗi…</p>
          <el-alert v-if="planRetryError" :title="planRetryError" type="error" :closable="false" />
        </template>
        <el-form-item v-else label="Phạm vi tài khoản">
          <el-radio-group v-model="refreshScope" class="scope-choices" :class="{ 'refresh-scope-choices': !tokenDialogIsCheck }" :disabled="refreshingTokens">
            <el-radio v-if="singleTaskEmail" value="single">Tài khoản này <b>1</b><span class="mono">{{ singleTaskEmail }}</span></el-radio>
            <el-radio value="selected" :disabled="!selected.length">Đã chọn <b>{{ selected.length }}</b><span>Giữ lựa chọn qua các trang</span></el-radio>
            <el-radio v-if="!tokenDialogIsCheck" value="folder" :disabled="groupFilter === 'all'">Cả thư mục <b>{{ refreshFolderCount }}</b><span translate="no">{{ groupFilter === 'all' ? '—' : currentFolderName }}</span><span>Không áp dụng các bộ lọc khác</span></el-radio>
            <el-radio value="filter">Toàn bộ kết quả lọc <b>{{ total }}</b><span>Bao gồm tất cả các trang</span></el-radio>
            <el-radio v-if="!tokenDialogIsCheck" value="all">Tất cả tài khoản <b>{{ groupsSummary.total }}</b><span>Toàn bộ kho, không áp dụng bộ lọc</span></el-radio>
            <el-radio value="page">Trang hiện tại <b>{{ rows.length }}</b><span>Chỉ các tài khoản đang hiển thị</span></el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="tokenJobOperation !== 'checkout_check'" label="Kết nối">
          <el-select v-model="refreshProxyMode" :disabled="refreshingTokens" aria-label="Proxy tác vụ token" style="width: 100%">
            <el-option :label="`Tự động từ Kho Proxy (${proxyList.length})`" value="pool" />
            <el-option label="Dùng proxy riêng" value="single" />
            <el-option v-if="!['plus_check','quota_check'].includes(tokenJobOperation)" label="Trực tiếp từ VPS" value="direct" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="tokenJobOperation !== 'checkout_check' && refreshProxyMode === 'single'" label="Proxy riêng">
          <el-select-v2 v-model="form.proxy" :options="proxyOptions" filterable clearable allow-create default-first-option :reserve-keyword="false" placeholder="Chọn hoặc nhập proxy" style="width: 100%" />
        </el-form-item>
        <el-form-item label="Số worker đồng thời">
          <el-input-number v-model="tokenTaskWorkers" :min="1" :max="100" :step="1" :disabled="refreshingTokens" controls-position="right" aria-label="Số worker đồng thời" />
          <span class="hint" style="margin-left: 12px">1–100 · Lưu riêng cho từng tác vụ</span>
        </el-form-item>
        <p class="hint">{{ ['token_refresh','plus_check','quota_check'].includes(tokenJobOperation) ? 'Dùng Kho Proxy để chạy song song; mỗi tài khoản giữ riêng một proxy trong suốt lượt xử lý. Proxy riêng/trực tiếp chạy 1 worker.' : tokenJobOperation === 'checkout_check' ? 'Worker thực tế không vượt mức đồng thời trong cấu hình checkout.' : 'Số worker được giới hạn theo số tài khoản trong đợt.' }}</p>
        <el-checkbox v-if="!tokenDialogIsCheck" v-model="refreshUsable" :disabled="refreshingTokens || !refreshSpecificScope">Cưỡng chế làm mới AT, kể cả khi chưa hết hạn</el-checkbox>
        <p v-if="!tokenDialogIsCheck" class="hint">{{ refreshUsableActive ? 'Làm mới tài khoản đã chọn dù AT còn hạn; vẫn giữ trạng thái khóa và chờ xử lý mail OTP.' : 'Chỉ làm mới AT cần cứu; bỏ qua AT dùng được, tài khoản khóa và chờ xử lý mail OTP.' }}</p>
        <details v-if="!tokenDialogIsCheck" class="help-details task-explanation"><summary>Cách làm mới AT</summary><p class="hint">Ưu tiên RT → AT. Chưa có RT hoặc RT mất hiệu lực mới đăng nhập và thử bổ sung RT; lỗi mạng/429 không đăng nhập lại.</p></details>
        <p v-if="!tokenDialogIsCheck && !refreshSpecificScope" class="hint">Muốn làm mới AT còn hạn, chọn tài khoản cụ thể hoặc tích chọn các tài khoản cần làm mới.</p>
        <el-checkbox v-if="tokenJobOperation === 'token_check'" v-model="checkSkipUsable" :disabled="refreshingTokens">Bỏ qua AT còn hạn hoặc đã kiểm tra dùng được</el-checkbox>
        <p v-if="tokenJobOperation === 'token_check'" class="hint">{{ checkSkipUsable ? 'Dùng hạn JWT và kết quả đã lưu; không gọi proxy cho AT được bỏ qua. Kết quả 401/khóa đã biết vẫn được ưu tiên.' : 'Quét API lại các AT chưa hết hạn. AT hết hạn hoặc chưa có token vẫn được phân loại tại VPS.' }}</p>
        <p v-if="tokenDialogIsCheck" class="hint">{{ tokenJobOperation === 'token_check' ? 'Token hết hạn theo JWT hoặc chưa có AT được phân loại tại VPS, không cần gọi mạng.' : tokenJobOperation === 'quota_check' ? 'Đọc quota Codex / Work bằng AT hiện có; không tự đăng nhập hay làm mới token. Chưa có AT hoặc AT hết hạn cần làm mới trước.' : tokenJobOperation === 'plus_check' ? 'Token hết hạn có thể được làm mới bằng luồng đăng nhập hiện có.' : 'Dò bằng cấu hình proxy checkout hiện có; tạo phiên để đọc giá, không xác nhận thanh toán.' }}</p>
      </el-form>
      <div class="scope-receipt">
        <strong v-if="refreshFilterActive && refreshCandidatesLoading">Đang lọc tài khoản cần làm mới…</strong>
        <strong v-else>{{ refreshTargetCount.toLocaleString('vi-VN') }}<template v-if="refreshFilterActive">/{{ refreshScopeCount.toLocaleString('vi-VN') }}</template> tài khoản{{ refreshFilterActive ? ' có thể xử lý' : '' }} · {{ tokenTaskWorkers }} worker yêu cầu</strong>
        <template v-if="refreshFilterActive && refreshCandidatesInfo">
          <span>Cần AT: chưa có {{ refreshCandidatesInfo.total_missing }} · Hết hạn/401 {{ refreshCandidatesInfo.total_expired }}<template v-if="refreshCandidatesInfo.total_retryable"> · Lỗi khác có thể thử lại {{ refreshCandidatesInfo.total_retryable }}</template></span>
          <span>Có RT: {{ refreshCandidatesInfo.total_with_rt || 0 }} · Cần đăng nhập: {{ refreshCandidatesInfo.total_without_rt || 0 }}</span>
          <span v-if="refreshUsableActive">Làm mới thêm: AT còn hạn/dùng được {{ (refreshCandidatesInfo.total_unexpired || 0) + (refreshCandidatesInfo.total_usable || 0) }} · Chưa rõ hạn {{ refreshCandidatesInfo.total_unknown || 0 }}</span>
          <span v-if="refreshUsableActive">Bỏ qua: Sai TK/MK/2FA {{ refreshCandidatesInfo.total_auth_errors || 0 }} · Bị khóa {{ refreshCandidatesInfo.total_banned }}<template v-if="refreshCandidatesInfo.total_email_otp_hold"> · Chờ xử lý mail OTP {{ refreshCandidatesInfo.total_email_otp_hold }}</template></span>
          <span v-else>Bỏ qua: AT dùng được {{ (refreshCandidatesInfo.total_unexpired || 0) + (refreshCandidatesInfo.total_usable || 0) }} · Sai TK/MK/2FA {{ refreshCandidatesInfo.total_auth_errors || 0 }} · Bị khóa {{ refreshCandidatesInfo.total_banned }}<template v-if="refreshCandidatesInfo.total_email_otp_hold"> · Chờ xử lý mail OTP {{ refreshCandidatesInfo.total_email_otp_hold }}</template><template v-if="refreshCandidatesInfo.total_unknown"> · Chưa rõ hạn {{ refreshCandidatesInfo.total_unknown }}</template></span>
        </template>
        <span v-else>{{ tokenDialogIsCheck ? 'Chạy trên VPS, có thể đóng tab hoặc dừng quét' : 'Lưu tiến độ và kết quả trên VPS' }}</span>
        <span v-if="refreshCandidatesError">{{ refreshCandidatesError }}</span>
      </div>
      <template #footer><el-button :disabled="refreshingTokens" @click="refreshDialogVisible = false">Hủy</el-button><el-button type="primary" :loading="refreshingTokens" :disabled="!refreshScopeCount || refreshJobRunning || refreshCandidatesLoading || planRetryLoading || !!planRetryError" @click="submitBatchRefreshTokens">{{ tokenDialogIsCheck ? 'Bắt đầu quét' : 'Bắt đầu làm mới' }}</el-button></template>
    </el-dialog>
    <AccountTaskProgress v-if="refreshJob || refreshConnectionError"
      initially-collapsed
      :job="refreshJob" :title="currentJobTitle" :running="refreshJobRunning"
      :cancelling="submittingStop" :stop-requested="refreshStopRequested"
      :can-retry="canRetryRefreshErrors" :retrying="retryingRefreshErrors" :retry-label="refreshJob?.operation === 'plus_check' ? 'Quét lại tài khoản lỗi' : 'Thử lại acc có thể cứu'"
      :connection-error="refreshConnectionError" :auth-failures="authFailureSummary" :plan-summary="planCheckSummary"
      @reload="tokenRefresh.restore" @stop="stopTokenRefresh" @retry="openRetryRefreshErrors" @filter="filterRefreshError"
    />
    <div class="account-workspace"><aside class="account-folder-sidebar"><AccountFolders :saving-order="savingFolderOrder" @reorder="saveFolderOrder" :summary="groupsSummary" :current="groupFilter" :saved="savedAccountViews" @select="selectGroup" @create="promptCreateGroup([])" @rename="promptRenameGroup" @delete="handleDeleteGroup" @move="moveFolderAccounts" @saved="applyAdvancedFilters" @remove-saved="removeSavedView" /></aside><div class="account-workspace-content">
    <el-card shadow="never" class="account-list-card" aria-label="Danh sách tài khoản">
      <AccountToolbar v-model:keyword="keyword" :filters="activeFilters" :total="groupsSummary.total" :filtered="total" :selected="selected.length"
        :running="refreshJobRunning" :refreshing="refreshingTokens || (refreshJobRunning &amp;&amp; !currentJobIsCheck)" :deleting="deletingAccounts" :exporting="exporting" :loading="loading" :show-columns="detailedColumns" :allow-filtered-delete="true" :quick-view="quickView" :folder-name="currentFolderName" :custom-folder="groupFilter !== 'all' &amp;&amp; groupFilter !== '__ungrouped__'"
        @open-filters="filtersVisible=true" @open-folders="foldersVisible=true"
        @quick-view="applyQuickView" @apply="load(true)" @clear-filter="clearFilter" @reset-filters="clearAllFilters" @clear-selection="clearAccountSelection" @check="handleAccountCheck" @refresh="doBatchRefreshTokens" @export="openScopeExport($event === 'custom' ? '' : $event)" @manage="handleAccountManage" @delete-selected="deleteSelected" @delete-filtered="deleteFiltered">



        <template #extra><section v-if="toolsOpen" class="account-config-panel">
          <div class="account-config-heading"><strong>Theo dõi ưu đãi</strong><el-button text size="small" aria-label="Đóng thiết lập" @click="toolsOpen = false"><el-icon><Close /></el-icon></el-button></div>
          <div v-if="zeroSummary" class="account-offer-summary"><div><span>Có ưu đãi 0đ</span><strong>{{ zeroSummary.free ?? 0 }}</strong></div><div><span>Đã dò</span><strong>{{ zeroSummary.probed ?? 0 }}</strong></div><div><span>Chưa dò</span><strong>{{ zeroSummary.unchecked ?? 0 }}</strong></div><div><span>Trong trang này</span><strong>{{ pageZeroCount }}</strong></div><p>Không hỗ trợ UPI: {{ zeroSummary.no_upi ?? 0 }} · Lỗi: {{ zeroSummary.failed ?? 0 }}</p></div>
        </section></template>
      </AccountToolbar>
      <el-skeleton v-if="loading && !rows.length" :rows="6" animated style="padding: 8px 0" />
      <el-table
        v-else-if="!mobileView"
        class="account-desktop-table"
        :max-height="640"
        ref="accountTable"
        v-loading="loading" :data="rows" size="default"
        row-key="email"
        @select="(selection, row) => toggleAccountSelection(row, selection.some(item => item.email === row.email))"
        @select-all="togglePageSelection"
      >
        <el-table-column type="selection" width="44" :reserve-selection="true" />
        <el-table-column prop="email" label="Tài khoản / Thư mục" min-width="308">
<template #header>
            <div class="column-filter-heading"><span>Tài khoản / Thư mục</span><el-button text size="small" aria-label="Lọc nhóm tài khoản" @click="filtersVisible=true"><FilterIcon :size="14"/></el-button></div>
          </template>
          <template #default="{ row }">
            <div class="account-identity"><button type="button" class="mono account-email account-email-copy" :aria-label="`Sao chép email ${row.email}`" title="Bấm để sao chép email" @click.stop="copyText(row.email)"><span translate="no">{{ row.email }}</span></button>
            <AccountCredentials :password="row.password || ''" :secret="row.totp_secret || ''" />
            <div class="account-identity-meta account-meta-badges">
            <el-dropdown :persistent="false" trigger="click" @command="(cmd) => handleRowGroupCommand(row, cmd)">
              <el-tag
                v-if="row.group_name"
                size="small"
                type="primary"
                effect="light"
                class="row-group-tag account-meta-badge" translate="no"
                :title="row.group_name"
              >
                <el-icon><Folder /></el-icon>
                <span class="account-meta-label">{{ row.group_name }}</span>
              </el-tag>
              <el-button v-else size="small" text class="row-group-empty account-meta-badge">
                + Nhóm
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="__new__">
                    <el-icon><Plus /></el-icon> Tạo nhóm mới &amp; gán…
                  </el-dropdown-item>
                  <el-dropdown-item
                    v-for="g in groupsSummary.groups"
                    :key="g.name"
                    :command="`group:${g.name}`"
                    :disabled="row.group_name === g.name"
                  >
                    <el-icon><Folder /></el-icon> <span translate="no">{{ g.name }}</span> ({{ g.count }})
                  </el-dropdown-item>
                  <el-dropdown-item v-if="row.group_name" divided command="__clear__">
                    <el-icon><FolderRemove /></el-icon> Bỏ khỏi nhóm
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown><span class="account-country account-meta-badge" :title="rowCountry(row) || 'Chưa có'">{{ rowCountry(row) || '—' }}</span>
            <el-popover :persistent="false" trigger="click" placement="top-start" :width="280" popper-class="account-plan-popover">
              <template #reference><button type="button" class="account-plan-badge account-meta-badge" :class="row.plus_check?.membership_verified ? row.plus_check.status : 'unverified'" :title="plusOf(row)?.label || 'Chưa kiểm tra'" :aria-label="`Gói tài khoản: ${plusOf(row)?.label || 'Chưa kiểm tra'}`">
                <StatusDot v-if="plusOf(row)" :type="row.plus_check.membership_verified ? PLUS_TYPE[plusOf(row).status] || 'info' : row.plus_check.trial_eligible ? 'success' : 'info'" :text="plusOf(row).label" />
                <span v-else>Chưa kiểm tra</span>
              </button></template>
              <div class="account-plan-detail"><strong>{{ plusOf(row)?.label || 'Chưa kiểm tra' }}</strong><p>{{ planTooltip(row) }}</p></div>
            </el-popover></div></div>
          </template>
        </el-table-column>
        <!-- Quốc gia đăng ký: từ IP xuất exit_country -->
        <el-table-column v-if="detailedColumns" label="Quốc gia" width="84" align="center">
          <template #default="{ row }">
            <el-tooltip
              v-if="rowCountry(row)"
              :content="`IP xuất ${metaOf(row)?.exit_ip || '?'}${metaOf(row)?.version ? ' · ' + metaOf(row).version : ''} (Nhấp để lọc)`"
              placement="top"
            >
              <el-tag
                size="small"
                :effect="countryFilter === rowCountry(row) ? 'dark' : 'plain'"
                style="cursor: pointer"
                @click.stop="quickFilterCountry(rowCountry(row))"
              >
                {{ rowCountry(row) }}
              </el-tag>
            </el-tooltip>
            <span v-else class="hint">—</span>
          </template>
        </el-table-column>
        <!-- 密码直接明文列出：随机 16 位，是登录账号的必需品，
             藏进「查看凭证」弹窗每次都要多点两下。列表接口本来就在返回它。
             图标放在文字**后面**：放前面会把值整体右推 27px（见 .cell-copy 注释）。 -->
        <el-table-column v-if="detailedColumns" label="Mật khẩu" min-width="160">
          <template #default="{ row }">
            <el-button
              v-if="row.password" size="small" text type="primary"
              class="cell-copy mono" @click="copyText(row.password)"
            >
              ••••••••<el-icon class="ico"><CopyDocument /></el-icon>
            </el-button>
            <span v-else class="hint">—</span>
          </template>
        </el-table-column>
        <el-table-column v-if="detailedColumns" label="Mã 2FA (Secret)" min-width="260">
          <template #default="{ row }">
            <el-button
              v-if="row.totp_secret" size="small" text type="warning"
              class="cell-copy mono" @click="copyText(row.totp_secret)"
            >
              Sao chép 2FA<el-icon class="ico"><CopyDocument /></el-icon>
            </el-button>
            <span v-else class="hint">—</span>
          </template>
        </el-table-column>

        <el-table-column label="Quota Codex / Work" min-width="190"><template #default="{ row }"><AccountQuota :check="row.quota_check" :plan="row.plus_check" :disabled="refreshJobRunning" @check="openSingleTask(row, 'quota_check')" /></template></el-table-column>
        <!-- UPI 支付金额：int31.space 支付能力探测的真实结论（印度出口实测） -->
        <el-table-column v-if="detailedColumns" label="Số tiền UPI" width="116" align="center">
          <template #default="{ row }">
            <el-tooltip
              v-if="checkoutOf(row)"
              :content="`Nguồn ${checkoutOf(row).source || 'int31'} · Trạng thái ${checkoutOf(row).status || '-'} · ${checkoutOf(row).failure_type || 'OK'} · Phương thức ${(checkoutOf(row).payment_methods || []).join('/') || '-'} · Đơn vị ${checkoutOf(row).processor_entity || '-'} · Xuất ${checkoutOf(row).provider_country || '-'}`"
              placement="top"
            >
              <el-tag
                size="small"
                :type="checkoutLabel(row).type"
                :effect="isZeroCheckout(row) ? 'dark' : 'plain'"
                :class="isZeroCheckout(row) ? 'zero-hit' : ''"
              >
                {{ checkoutLabel(row).text }}
              </el-tag>
            </el-tooltip>
            <span v-else class="hint">{{ checkoutLabel(row).text }}</span>
          </template>
        </el-table-column>
        <!-- Trạng thái Token: hiển thị Live status (200 / 401 / 403) và hạn JWT, nhấp để kiểm tra -->
        <el-table-column label="Token / Làm mới" min-width="160">
<template #header>
            <div class="column-filter-heading"><span>Token / Làm mới</span><el-button text size="small" aria-label="Lọc AT và lỗi" @click="filtersVisible=true"><FilterIcon :size="14"/></el-button></div>
          </template>
          <template #default="{ row }">
            <div class="account-token-state">
            <el-tooltip
              :content="`${tokenStatus(row).tooltip || ''} · Nhấp để xem chi tiết`"
              placement="top"
            >
              <button type="button" class="token-status-button" :aria-label="`Xem trạng thái AT của ${row.email}`" @click.stop="viewTokenStatus(row)"><el-tag
                class="token-status-tag"
                size="small"
                :type="tokenStatus(row).type"
                effect="plain"
                style="cursor: pointer; font-weight: 500"
              >
                {{ tokenStatus(row).text }}
              </el-tag></button>
            </el-tooltip>
            <small v-if="tokenStatus(row).detail" class="token-expiry-detail">{{ tokenStatus(row).detail }}</small>
            <el-tooltip :persistent="false" v-if="row.refresh_error" :content="`${row.refresh_error.message || row.refresh_error.label} · ${fmtTime(row.refresh_error.checked_at)}${row.refresh_error.manual_retry_required ? ' · Tạm dừng. Kiểm tra/bổ sung đường nhận mail, sau đó chọn Đã xử lý mail · cho phép thử lại.' : row.refresh_error.terminal_auth_error ? ' · Không tự thử lại; sửa thông tin hoặc chọn Cho phép thử lại.' : ''} · Nhấp để lọc`" placement="top">
              <el-tag size="small" :type="row.refresh_error.terminal_auth_error ? 'danger' : 'warning'" effect="light" class="refresh-error-tag" @click.stop="filterRefreshError(row.refresh_error)">{{ row.refresh_error.label || 'Lỗi làm mới' }}</el-tag>
            </el-tooltip>
            </div>
          </template>
        </el-table-column>
        <el-table-column v-if="detailedColumns" label="Access Token" width="110" align="center">
          <template #default="{ row }">
            <el-button v-if="row.at_len > 0" size="small" text type="primary" @click="copyCell(row.email, 'access_token')">
              <el-icon><CopyDocument /></el-icon>{{ row.at_len }}
            </el-button>
            <span v-else class="hint">—</span>
          </template>
        </el-table-column>
        <el-table-column v-if="detailedColumns" label="Session Token" width="110" align="center">
          <template #default="{ row }">
            <el-button v-if="row.st_len > 0" size="small" text type="primary" @click="copyCell(row.email, 'session_token')">
              <el-icon><CopyDocument /></el-icon>{{ row.st_len }}
            </el-button>
            <span v-else class="hint">—</span>
          </template>
        </el-table-column>
        <el-table-column label="Lưu lượng" min-width="105">
          <template #default="{ row }">
            <el-popover :persistent="false" placement="left" :width="350" trigger="hover" :disabled="!accountTaskTraffic(row).length">
              <template #reference><div class="account-traffic-cell"><strong v-if="accountTrafficTotal(row)">{{ fmtBytes(Number(accountTrafficTotal(row).rx || 0) + Number(accountTrafficTotal(row).tx || 0)) }}</strong><span v-else>Chưa đo</span><small v-if="accountTrafficTotal(row)">Tổng đã dùng</small></div></template>
              <strong class="traffic-popover-title">Lưu lượng cộng dồn</strong><TaskTraffic v-if="accountTrafficTotal(row)" :traffic="accountTrafficTotal(row)" label="Tổng đã dùng" /><div v-for="item in accountTaskTraffic(row)" :key="item.label" class="account-task-traffic"><TaskTraffic :traffic="item.traffic" :label="item.label" /></div><p class="hint">Cộng dồn các lượt đã đo, gồm lỗi và thử lại. Ước tính nội dung HTTP, chưa gồm header/TLS.<template v-if="accountTrafficTotal(row)?.history_limited"> Các lượt cũ không còn số đo có thể bị thiếu.</template></p>
            </el-popover>
          </template>
        </el-table-column>
        <el-table-column label="Ngày tạo" width="132">
<template #header>
            <div class="column-filter-heading"><span>Ngày tạo</span><el-button text size="small" aria-label="Lọc ngày tạo" @click="filtersVisible=true"><FilterIcon :size="14"/></el-button></div>
          </template>
          <template #default="{ row }">
            <time v-if="row.created_at" class="account-created" :datetime="new Date(row.created_at * 1000).toISOString()"><strong>{{ fmtTime(row.created_at).split(' ')[0] }}</strong><span>{{ fmtTime(row.created_at).split(' ')[1] }}</span></time><span v-else class="hint">Chưa có</span>
          </template>
        </el-table-column>
        <el-table-column label="Thao tác" width="100" fixed="right" align="center">
          <template #default="{ row }">
            <div class="account-row-actions">
              <el-button size="small" text @click="viewCred(row.email)">Chi tiết</el-button>
              <el-dropdown :persistent="false" trigger="click" @command="command => handleRowAction(command, row)">
                <el-button size="small" text :loading="!!refreshingRow[row.email]" :aria-label="`Thao tác với ${row.email}`"><el-icon><ChevronDown /></el-icon></el-button>
                <template #dropdown><el-dropdown-menu>
                  <el-dropdown-item command="copy_ls"><el-icon><CopyDocument /></el-icon>Sao chép LS</el-dropdown-item>
                  <el-dropdown-item command="copy_at" :disabled="!row.at_len"><el-icon><CopyDocument /></el-icon>Sao chép AT</el-dropdown-item>
                  <el-dropdown-item command="check"><el-icon><Odometer /></el-icon>Kiểm tra AT…</el-dropdown-item>
                  <el-dropdown-item command="quota" :disabled="refreshJobRunning">Kiểm tra quota</el-dropdown-item>
                  <el-dropdown-item command="refresh" :disabled="refreshJobRunning"><el-icon><Refresh /></el-icon>Làm mới AT…</el-dropdown-item>
                  <el-dropdown-item v-if="row.refresh_error?.terminal_auth_error" command="clear_auth_error" :disabled="refreshJobRunning">Cho phép thử lại</el-dropdown-item>
                  <el-dropdown-item v-if="row.refresh_error?.manual_retry_required" command="clear_auth_error" :disabled="refreshJobRunning">Đã xử lý mail · cho phép thử lại</el-dropdown-item>
                  <el-dropdown-item command="edit" divided><el-icon><EditPen /></el-icon>Sửa tài khoản</el-dropdown-item>
                  <el-dropdown-item command="delete" divided class="row-delete-action"><el-icon><Delete /></el-icon>Xóa tài khoản</el-dropdown-item>
                </el-dropdown-menu></template>
              </el-dropdown>
            </div>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty :description="activeFilters.length ? 'Không có tài khoản khớp bộ lọc' : 'Chưa có tài khoản. Hãy nhập hoặc đăng ký mới.'" :image-size="70" />
        </template>
      </el-table>
      <div v-if="mobileView" class="account-mobile-list" v-loading="loading"><article v-for="row in rows" :key="row.email" class="account-mobile-card" :class="{selected:selectedEmails.has(row.email)}"><div class="mobile-account-heading"><el-checkbox :model-value="selectedEmails.has(row.email)" :aria-label="`Chọn ${row.email}`" @change="checked=>toggleAccountSelection(row,checked)"/><div><button type="button" class="account-email-copy" :aria-label="`Sao chép email ${row.email}`" title="Bấm để sao chép email" @click.stop="copyText(row.email)"><span translate="no">{{ row.email }}</span></button></div><el-dropdown :persistent="false" trigger="click" @command="command=>handleRowAction(command,row)"><el-button text :aria-label="`Thao tác mobile với ${row.email}`">•••</el-button><template #dropdown><el-dropdown-menu><el-dropdown-item command="copy_ls">Sao chép LS</el-dropdown-item><el-dropdown-item command="copy_at" :disabled="!row.at_len">Sao chép AT</el-dropdown-item><el-dropdown-item command="check" :disabled="refreshJobRunning">Kiểm tra AT…</el-dropdown-item><el-dropdown-item command="quota" :disabled="refreshJobRunning">Kiểm tra quota</el-dropdown-item><el-dropdown-item command="refresh" :disabled="refreshJobRunning">Làm mới AT…</el-dropdown-item><el-dropdown-item command="edit" divided>Sửa tài khoản</el-dropdown-item><el-dropdown-item command="delete" class="danger-menu-item">Xóa tài khoản…</el-dropdown-item></el-dropdown-menu></template></el-dropdown></div>
            <div class="mobile-account-meta account-meta-badges">
              <el-tooltip :persistent="false" :content="row.group_name || 'Chưa phân thư mục'" trigger="click"><button type="button" class="account-folder-badge account-meta-badge" :title="row.group_name || 'Chưa phân thư mục'"><el-icon><Folder /></el-icon><span v-if="row.group_name" class="account-meta-label" translate="no">{{ row.group_name }}</span><span v-else class="account-meta-label">Chưa phân thư mục</span></button></el-tooltip>
              <span class="account-country account-meta-badge" :title="rowCountry(row) || 'Chưa có'">{{ rowCountry(row) || '—' }}</span>
              <el-popover :persistent="false" trigger="click" placement="top-start" :width="280" popper-class="account-plan-popover">
              <template #reference><button type="button" class="account-plan-badge account-meta-badge" :class="row.plus_check?.membership_verified ? row.plus_check.status : 'unverified'" :title="plusOf(row)?.label || 'Chưa kiểm tra'" :aria-label="`Gói tài khoản: ${plusOf(row)?.label || 'Chưa kiểm tra'}`">
                <StatusDot v-if="plusOf(row)" :type="row.plus_check.membership_verified ? PLUS_TYPE[plusOf(row).status] || 'info' : row.plus_check.trial_eligible ? 'success' : 'info'" :text="plusOf(row).label" />
                <span v-else>Chưa kiểm tra</span>
              </button></template>
              <div class="account-plan-detail"><strong>{{ plusOf(row)?.label || 'Chưa kiểm tra' }}</strong><p>{{ planTooltip(row) }}</p></div>
            </el-popover></div><AccountCredentials :password="row.password || ''" :secret="row.totp_secret || ''" /><div class="mobile-account-status"><div><small>Access Token</small><button type="button" @click="viewTokenStatus(row)"><el-tag :type="tokenStatus(row).type">{{ tokenStatus(row).text }}</el-tag></button><span>{{ tokenStatus(row).detail }}</span></div></div><AccountQuota :check="row.quota_check" :plan="row.plus_check" :disabled="refreshJobRunning" @check="openSingleTask(row, 'quota_check')" /><button v-if="row.refresh_error" type="button" class="mobile-account-error" @click="filterRefreshError(row.refresh_error)">{{ row.refresh_error.label || 'Có lỗi làm mới' }}</button><div v-if="detailedColumns" class="mobile-account-extra"><el-button text size="small" @click="copyLoginString(row.email)">Sao chép LS</el-button><el-button text size="small" :disabled="!row.at_len" @click="copyCell(row.email, 'access_token')">Sao chép AT</el-button><el-button text size="small" @click="copyCell(row.email, 'totp_secret')">Sao chép 2FA</el-button></div><div class="mobile-account-footer"><span>{{ row.created_at ? fmtDate(row.created_at) : 'Chưa rõ ngày' }}</span><span>{{ accountTrafficTotal(row) ? fmtBytes(Number(accountTrafficTotal(row).rx||0)+Number(accountTrafficTotal(row).tx||0)) : 'Chưa đo' }}</span><el-button text size="small" @click="viewCred(row.email)">Chi tiết</el-button></div></article><el-empty v-if="!rows.length && !loading" description="Không có tài khoản khớp bộ lọc" :image-size="60"/></div>
      <div style="display: flex; justify-content: center; margin-top: 14px">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="PAGE_SIZE_OPTIONS"
          :total="total"
          layout="prev, pager, next, sizes, total, jumper" background
        />
      </div>

      <!-- Hộp thoại Phân nhóm tài khoản (theo tích chọn hoặc theo số lượng N acc) -->

      <el-dialog append-to-body v-model="groupManagerVisible" title="Thư mục tài khoản" width="560px" class="account-group-manager">
        <div class="account-group-manager-heading"><span>{{ groupsSummary.groups.length }} thư mục · {{ groupsSummary.ungrouped }} acc chưa phân thư mục</span><el-button type="primary" plain @click="promptCreateGroup([])">Tạo thư mục</el-button></div>
        <div class="account-group-list"><div v-for="g in groupsSummary.groups" :key="g.name"><div><strong translate="no">{{ g.name }}</strong><span>{{ g.count }} tài khoản</span></div><div><el-button text :aria-label="`Đổi tên nhóm ${g.name}`" @click="promptRenameGroup(g.name)"><el-icon><EditPen /></el-icon></el-button><el-button text type="danger" :aria-label="`Xóa nhóm ${g.name}`" @click="handleDeleteGroup(g.name)"><el-icon><Delete /></el-icon></el-button></div></div><el-empty v-if="!groupsSummary.groups.length" description="Chưa có nhóm" :image-size="60" /></div>
        <template #footer><el-button @click="groupManagerVisible = false">Đóng</el-button></template>
      </el-dialog>
      <el-dialog append-to-body v-model="groupAssignVisible" title="Chuyển tài khoản" width="540px" top="10vh">
        <el-form label-position="top">
          <el-form-item label="Phạm vi chuyển">
            <el-radio-group v-model="groupAssignRange" style="display: flex; flex-direction: column; align-items: flex-start; gap: 8px">
              <el-radio value="selected" :disabled="!selected.length">
                Các tài khoản đang tích chọn trên bảng ({{ selected.length }} acc)
              </el-radio>
              <el-radio value="filter_limit">
                Lấy N tài khoản đầu tiên theo bộ lọc hiện tại ({{ scopeFilterLabel }})
              </el-radio>
              <el-radio value="filter_all">
                Tất cả tài khoản theo bộ lọc hiện tại ({{ total }} acc)
              </el-radio>
            </el-radio-group>
          </el-form-item>

          <el-form-item v-if="groupAssignRange === 'filter_limit'" label="Số lượng tài khoản muốn lấy">
            <el-input-number v-model="groupAssignLimit" :min="1" :step="10" style="width: 200px" />
            <span class="hint" style="margin-left: 10px">tài khoản đầu tiên trong bộ lọc hiện tại</span>
          </el-form-item>

          <el-form-item label="Thư mục đích">
            <el-select
              v-model="groupAssignTarget"
              filterable
              allow-create
              default-first-option
              clearable
              placeholder="Chọn hoặc nhập tên thư mục mới…"
              style="width: 100%"
            >
              <template #label="{ label, value }"><span :translate="value === '__clear__' ? undefined : 'no'">{{ label }}</span></template>
              <el-option translate="no"
                v-for="g in groupsSummary.groups"
                :key="g.name"
                :label="`${g.name} (${g.count})`"
                :value="g.name"
              />
              <el-option label="Chưa phân thư mục" value="__clear__" />
            </el-select>
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="groupAssignVisible = false">Hủy</el-button>
          <el-button type="primary" :loading="groupAssignBusy" @click="doGroupAssignDialog">
            Chuyển tài khoản
          </el-button>
        </template>
      </el-dialog>

      <!-- Xuất theo bộ lọc hoặc theo số lượng -->
      <el-dialog append-to-body v-model="scopeVisible" :title="scopeFormatId === 'at' ? 'Xuất riêng Access Token' : 'Xuất tài khoản'" width="560px" top="10vh" class="account-scope-dialog">
        <el-form label-position="top">
          <el-form-item label="Phạm vi xuất">
            <el-radio-group v-model="scopeRange">
              <el-radio value="filter">Toàn bộ kết quả lọc · {{ total }} tài khoản (mọi trang)</el-radio>
              <el-radio value="selected" :disabled="!selected.length">
                Chỉ acc đã chọn ({{ selected.length }})
              </el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item v-if="scopeRange === 'filter'" label="Số lượng tài khoản">
            <el-radio-group v-model="scopeCountMode">
              <el-radio value="all">Toàn bộ (tất cả các trang)</el-radio>
              <el-radio value="limit">Lấy N tài khoản đầu tiên</el-radio>
            </el-radio-group>
            <el-input-number
              v-if="scopeCountMode === 'limit'"
              v-model="scopeCount" :min="1" :step="10"
              style="margin-left: 12px"
            />
          </el-form-item>
          <el-form-item label="Định dạng xuất file">
            <el-select v-model="scopeFormatId" style="width: 100%">
              <el-option
                v-for="f in exportFormats" :key="f.id"
                :label="formatLabel(f)" :value="f.id"
              />
            </el-select>
          </el-form-item>
        </el-form>
        <div class="scope-receipt"><strong>{{ scopeFormatId === 'at' ? 'AT.txt' : 'Tệp tài khoản' }}</strong><span>{{ scopeFormatId === 'at' ? 'Mỗi dòng một Access Token, không kèm email hay mật khẩu.' : scopeFilterLabel }}</span></div>
        <template #footer>
          <el-button @click="scopeVisible = false">Hủy</el-button>
          <el-button type="primary" :loading="scopeBusy" @click="doScopeExport">Xuất file</el-button>
        </template>
      </el-dialog>

      <el-dialog append-to-body v-model="exportVisible" width="720px" top="8vh">
        <template #header>
          <div style="display: flex; align-items: center; gap: 12px">
            <span style="font-weight: 600">Xuất file · {{ exportLabel }}</span>
            <el-tag size="small" type="info">Tổng cộng {{ exportCount }} dòng</el-tag>
          </div>
        </template>
        <el-input
          :model-value="exportText" type="textarea" :rows="14" readonly
          class="mono export-area"
        />
        <template #footer>
          <el-button @click="copyText(exportText)">
            <el-icon><CopyDocument /></el-icon>Sao chép toàn bộ
          </el-button>
          <el-button type="primary" @click="downloadExport">
            <el-icon><Download /></el-icon>Tải file {{ exportFilename }}
          </el-button>
          <!-- Nút nguy hiểm: Tải file & Xóa tài khoản -->
          <el-button
            type="danger" plain
            :loading="deletingExported"
            :disabled="!exportedEmails.length"
            @click="downloadAndDelete"
          >
            <el-icon><Delete /></el-icon>Tải file &amp; Xóa {{ exportedEmails.length }} acc này
          </el-button>
        </template>
      </el-dialog>

      <el-dialog append-to-body v-model="credVisible" :title="credEmail" width="760px" top="6vh">
        <template #header>
          <div style="display: flex; align-items: center; gap: 12px">
            <span class="mono" style="font-weight: 600">{{ credEmail }}</span>
            <el-button size="small" @click="copyAllJson">Sao chép toàn bộ JSON</el-button>
          </div>
        </template>
        <div v-for="r in credRows" :key="r.key" style="margin-bottom: 12px">
          <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 4px">
            <span class="mono" style="font-weight: 600; color: var(--dango-pink-dark)">{{ r.key }}</span>
            <el-tag size="small" type="info">độ dài={{ r.val.length }}</el-tag>
            <el-button size="small" @click="copyText(r.val)">Sao chép</el-button>
          </div>
          <el-input :model-value="r.val" type="textarea" :rows="2" readonly class="mono" />
        </div>
        <el-empty v-if="!credRows.length" description="Không có dữ liệu xác thực" />
      </el-dialog>

      <!-- Chỉnh sửa thông tin đăng nhập -->
      <el-dialog append-to-body v-model="editVisible" title="Chỉnh sửa thông tin đăng nhập" width="560px" top="10vh">
        <el-alert
          type="warning" :closable="false" show-icon style="margin-bottom: 16px"
          title="Lưu ý: Chỉ cập nhật dữ liệu trong hệ thống, không thay đổi trên OpenAI"
          description="Mật khẩu và 2FA Secret tại đây sẽ được sử dụng trực tiếp khi tự động đăng nhập lại."
        />
        <el-form label-position="top">
          <el-form-item label="Email">
            <el-input :model-value="editEmail" class="mono" disabled />
          </el-form-item>
          <el-form-item label="Mật khẩu">
            <el-input v-model="editPassword" class="mono" placeholder="Để trống nếu tài khoản không có mật khẩu" />
          </el-form-item>
          <el-form-item label="Mã 2FA Secret (TOTP)">
            <el-input
              v-model="editSecret" class="mono"
              placeholder="Chuỗi base32, hỗ trợ khoảng trắng hoặc link otpauth://"
            />
            <div class="hint" style="margin-top: 6px; line-height: 1.6">
              Mã 2FA Secret là duy nhất do OpenAI cấp ban đầu. Nếu ghi đè sẽ mất mã cũ.
            </div>
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="editVisible = false">Hủy</el-button>
          <el-button type="primary" :loading="editSaving" @click="saveEdit">Lưu thay đổi</el-button>
        </template>
      </el-dialog>

      <!-- 批量导入已注册账号 -->
      <el-dialog append-to-body v-model="importDialogVisible" title="Nhập tài khoản đã đăng ký" width="650px" top="8vh">
        <el-alert
          type="info" :closable="false" show-icon style="margin-bottom: 14px"
          title="Định dạng hỗ trợ"
          description="Mỗi dòng một tài khoản. Hỗ trợ: email----password hoặc email----password----2FA hoặc email:password. Sau khi nhập có thể quản lý, kiểm tra AT hoặc dò Plus trial."
        />
        <div style="margin-bottom: 12px; display: flex; gap: 12px; align-items: center; flex-wrap: wrap">
          <span style="font-weight: 500">Gán vào nhóm (tùy chọn):</span>
          <el-select
            v-model="importGroup"
            filterable
            allow-create
            default-first-option
            clearable
            placeholder="Để trống = Chưa phân nhóm, hoặc chọn/nhập tên nhóm..."
            style="flex: 1; min-width: 240px"
          >
            <template #label="{ label }"><span translate="no">{{ label }}</span></template>
            <el-option translate="no"
              v-for="g in groupsSummary.groups"
              :key="g.name"
              :label="`${g.name} (${g.count})`"
              :value="g.name"
            />
          </el-select>
        </div>
        <div style="margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center">
          <span style="font-weight: 500">Dán danh sách hoặc tải file .txt:</span>
          <el-upload
            action="#"
            :auto-upload="false"
            :show-file-list="false"
            accept=".txt"
            :on-change="handleFileUpload"
          >
            <el-button size="small" type="primary">
              <el-icon><Upload /></el-icon> Chọn file .txt
            </el-button>
          </el-upload>
        </div>
        <el-input
          v-model="importText"
          type="textarea"
          :rows="10"
          class="mono"
          placeholder="user1@example.com----password123&#10;user2@example.com----pass456----TOTP_SECRET"
        />
        <div v-if="importResult" style="margin-top: 12px; white-space: pre-wrap; font-size: 13px; color: var(--el-color-success); font-family: monospace;">
          {{ importResult }}
        </div>
        <template #footer>
          <el-button @click="importDialogVisible = false">Đóng</el-button>
          <el-button type="primary" :loading="importLoading" @click="doImportRegistered">
            Bắt đầu nhập
          </el-button>
        </template>
      </el-dialog>

    </el-card></div></div>
    <AccountFilters v-model="filtersVisible" :value="filterDraft" :groups="groupsSummary.groups" :countries="availableCountries" @apply="applyAdvancedFilters" @save="saveAccountView"/>
    <el-drawer v-model="foldersVisible" title="Thư mục tài khoản" direction="ltr" size="min(320px, 90vw)" class="folders-drawer"><AccountFolders :saving-order="savingFolderOrder" @reorder="saveFolderOrder" :summary="groupsSummary" :current="groupFilter" :saved="savedAccountViews" @select="selectGroup" @create="promptCreateGroup([])" @rename="promptRenameGroup" @delete="handleDeleteGroup" @move="moveFolderAccounts" @saved="applyAdvancedFilters" @remove-saved="removeSavedView"/></el-drawer>
  </div>
</template>

<style>
.confirm-multiline .el-message-box__message { white-space: pre-line; }
</style>

<style scoped>
.account-workspace{display:grid;grid-template-columns:226px minmax(0,1fr);border:1px solid var(--app-border);border-radius:16px;background:var(--app-card-bg);overflow:hidden;box-shadow:var(--app-shadow-sm)}.account-folder-sidebar{position:relative;background:var(--app-sidebar-bg);border-right:1px solid var(--app-border)}.account-workspace-content{min-width:0}.account-workspace .account-list-card{border:0!important;border-radius:0!important;box-shadow:none!important}.account-workspace :deep(.account-list-card>.el-card__body){padding:0!important}.account-workspace :deep(.el-table){border-inline:0;border-radius:0!important}.account-workspace .account-list-card :deep(.el-pagination){padding-bottom:18px}.account-plan-state .plan-evidence-label{font-size:10px;white-space:normal;line-height:1.5;max-width:160px}.account-traffic-cell small{font-size:10px;color:var(--app-text-dim)}.account-mobile-list{display:none}
@media(max-width:1320px){.account-workspace{grid-template-columns:minmax(0,1fr)}.account-folder-sidebar{display:none}}
@media(max-width:680px){.account-desktop-table{display:none}.account-mobile-list{display:block;padding:0 12px 12px}.account-mobile-card{border:1px solid var(--app-border);border-radius:12px;padding:13px;margin-bottom:10px;background:var(--app-card-bg)}.account-mobile-card.selected{border-color:var(--brand);background:var(--brand-bg)}.mobile-account-heading{display:flex;align-items:center;gap:8px}.mobile-account-heading>div{min-width:0;flex:1;display:flex;flex-direction:column;gap:4px}.mobile-account-heading>div>strong{font-size:12px;overflow-wrap:anywhere;font-weight:550}.mobile-account-heading>div>span{font-size:10px;color:var(--app-text-muted)}.mobile-account-heading i{font-style:normal}.mobile-account-heading>.el-dropdown{flex:0 0 auto}.mobile-account-heading .el-checkbox{height:24px}.mobile-account-heading :deep(.el-button){padding:3px;width:26px;min-height:28px}.mobile-account-status{display:grid;grid-template-columns:1fr 1fr;gap:15px;padding:14px 0 12px}.mobile-account-status>div{display:flex;flex-direction:column;align-items:flex-start;gap:5px;min-width:0}.mobile-account-status small{font-size:9px;color:var(--app-text-dim)}.mobile-account-status strong{font-size:12px;font-weight:550}.mobile-account-status span{font-size:10px;color:var(--app-text-muted);line-height:1.5}.mobile-account-status button{border:0;background:none;padding:0}.mobile-account-footer{display:flex;align-items:center;gap:12px;border-top:1px solid var(--app-border);padding-top:7px;font-size:10px;color:var(--app-text-muted)}.mobile-account-footer>.el-button{margin-left:auto;min-height:27px}.mobile-account-error{display:block;width:100%;font:inherit;font-size:10px;color:var(--color-danger);background:var(--color-danger-bg);border:0;text-align:left;padding:8px;border-radius:6px;margin-bottom:9px}}

.account-config-panel { margin-top:14px; padding:14px; border:1px solid var(--app-border); border-radius:10px; background:var(--app-card-surface); }
.account-config-heading,.account-group-manager-heading { display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:12px; font-size:12px; }
.account-config-heading strong { font-size:13px; color:var(--app-title); }.account-quick-proxy { display:flex; flex-direction:column; gap:8px; }
.account-offer-summary { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; }.account-offer-summary > div { display:flex; flex-direction:column; gap:7px; font-size:11px; color:var(--app-text-muted); }.account-offer-summary strong { font-size:20px; font-weight:600; color:var(--app-title); }.account-offer-summary p { grid-column:1/-1; font-size:11px; color:var(--app-text-muted); margin:0; }
.account-group-manager-heading > span { color:var(--app-text-muted); }.account-group-list { max-height:420px; overflow:auto; }.account-group-list > div { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:12px 0; border-bottom:1px solid var(--app-border); }.account-group-list > div > div:first-child { display:flex; flex-direction:column; gap:5px; min-width:0; }.account-group-list strong { overflow-wrap:anywhere; color:var(--app-title); font-size:13px; font-weight:550; }.account-group-list span { font-size:11px; color:var(--app-text-muted); }
@media(max-width:680px) { .column-filter-heading :deep(.el-button) { display:none; }.account-offer-summary { grid-template-columns:repeat(2,minmax(0,1fr)); }.account-list-card :deep(.el-card__body) { padding:14px; } }

.column-filter-heading { display: inline-flex; align-items: center; justify-content: flex-start; gap: 6px; min-height: 28px; max-width: 100%; vertical-align: middle; }
.column-filter-heading > span { min-width: 0; white-space: nowrap; }
.column-filter-heading :deep(.el-button) { flex: 0 0 28px; width: 28px; height: 28px; min-width: 28px; padding: 0; border-radius: 6px; color: var(--app-text-muted) !important; }
.column-filter-heading :deep(.el-button svg) { display: block; }
.column-filter-heading :deep(.el-button.el-button--primary) { color: var(--brand) !important; background: var(--brand-bg) !important; }
.column-filter-heading :deep(.el-button:hover) { color: var(--brand) !important; background: var(--brand-bg) !important; }
.column-filter-panel { display: flex; flex-direction: column; gap: 10px; font-size: 12px; }
.column-filter-panel :deep(.el-select) { width: 100%; }
.column-filter-panel :deep(.el-button) { align-self: flex-start; margin-left: 0; }
.active-account-filters { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: 0 0 12px; }
.active-account-filters :deep(.el-tag) { max-width: 100%; height: auto; white-space: normal; line-height: 1.5; padding-top: 3px; padding-bottom: 3px; }
.account-delete-scope { display: flex; justify-content: flex-end; margin: -4px 0 14px; }
.account-token-state { display: flex; flex-direction: column; align-items: flex-start; gap: 6px; }
.token-status-tag { height: auto; white-space: normal; line-height: 1.4; padding: 3px 6px; }
.token-expiry-detail { color: var(--app-text-muted); font-size: 11px; }
.token-status-button{background:none;border:0;padding:0;color:inherit;cursor:pointer;max-width:100%;text-align:left}.token-details{display:flex;flex-direction:column;align-items:flex-start;gap:12px;font-size:12px}.token-details>strong{overflow-wrap:anywhere}.token-details p{color:var(--app-text-muted);line-height:1.7;margin:0}.token-details small{color:var(--app-text-muted)}
.account-plan-state { display: flex; flex-direction: column; align-items: flex-start; gap: 5px; }
.account-plan-state small { color: var(--app-text-muted); font-size: 10px; }
.auth-failure-summary { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 10px; }.auth-failure-summary :deep(.el-tag) { cursor: pointer; }
.refresh-error-tag { cursor: pointer; max-width: 100%; height: auto; white-space: normal; line-height: 1.4; padding: 3px 6px; }
.account-command-bar { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; padding: 14px 0; margin-bottom: 12px; border-top: 1px solid var(--app-border); }
.account-scope-status, .account-primary-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.account-scope-status { font-size: 12px; color: var(--app-text-muted); gap: 12px; }
.account-scope-status strong { font-weight: 600; color: var(--app-title); }
.account-primary-actions :deep(.el-button + .el-button) { margin-left: 0; }
.account-traffic-cell { display: flex; flex-direction: column; gap: 3px; padding: 3px 0; font-size: 11px; font-variant-numeric: tabular-nums; }
.account-traffic-cell > div { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.account-traffic-cell span { color: var(--app-text-muted); }
.account-traffic-cell strong { color: var(--app-title); font-size: 12px; font-weight: 600; white-space: nowrap; }
.account-traffic-total { border-bottom: 1px solid var(--app-border); padding-bottom: 4px; margin-bottom: 2px; }
.account-traffic-total strong { color: var(--app-accent, var(--app-title)); }
.traffic-popover-title { display: block; margin-bottom: 12px; font-size: 13px; color: var(--app-title); }
.account-created { display: flex; flex-direction: column; line-height: 1.7; font-variant-numeric: tabular-nums; }
.account-created strong { font-size: 12px; font-weight: 500; color: var(--app-title); }
.account-created span { font-size: 11px; color: var(--app-text-muted); }
.account-identity { min-width: 0; padding: 2px 0; }
.account-email { display: block; overflow: hidden; text-overflow: ellipsis; font-weight: 500; }
.account-email-copy { border:0;background:transparent;color:var(--app-title);padding:0;font:inherit;font-weight:500;text-align:left;cursor:pointer;max-width:100%; }
.account-email-copy:hover { color:var(--brand); }
.account-email-copy:focus-visible { outline:2px solid var(--brand);outline-offset:3px;border-radius:3px; }
.account-email.account-email-copy { width:100%;white-space:nowrap; }
.mobile-account-heading .account-email-copy { font-size:12px;overflow-wrap:anywhere;line-height:1.5; }
.account-identity-meta { display: flex; align-items: center; gap: 7px; margin-top: 5px; }
.account-identity-meta :deep(.el-tag) { max-width: 165px; height: 20px; line-height: 18px; font-size: 10px; border: 0; background: var(--brand-bg); color: var(--brand); }
.account-country { font-size: 10px; color: var(--app-text-muted); }
.scope-choices { display: flex; flex-direction: column; width: 100%; gap: 8px; }
.scope-choices :deep(.el-radio) { width: 100%; margin: 0; box-sizing: border-box; padding: 12px 14px; border: 1px solid var(--app-border); border-radius: 10px; align-items: flex-start; }
.scope-choices :deep(.el-radio.is-checked) { background: var(--brand-bg); border-color: var(--brand-border); }
.scope-choices :deep(.el-radio__input) { margin-top: 4px; }
.scope-choices :deep(.el-radio__label) { flex: 1; min-width: 0; }
.scope-choices b { float: right; margin-left: 8px; color: var(--app-title); font-variant-numeric: tabular-nums; }
.scope-choices span { display: block; margin-top: 3px; font-size: 12px; color: var(--app-text-muted); }
.refresh-scope-choices { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }
.refresh-scope-choices :deep(.el-radio) { height: auto; }
.refresh-scope-choices :deep(.el-radio__label) { white-space: normal; overflow-wrap: anywhere; line-height: 1.45; }
:global(.token-task-dialog) { display: flex; flex-direction: column; max-height: 92vh; }
:global(.token-task-dialog > .el-dialog__body) { min-height: 0; overflow-y: auto; }
:global(.token-task-dialog > .el-dialog__header), :global(.token-task-dialog > .el-dialog__footer) { flex-shrink: 0; }
.scope-receipt { display: flex; flex-direction: column; gap: 4px; padding: 12px 14px; margin-top: 16px; background: var(--app-card-surface); border: 1px solid var(--app-border); border-radius: 10px; font-size: 12px; color: var(--app-text-muted); }
.scope-receipt strong { color: var(--app-title); font-size: 13px; }
.refresh-progress > summary { margin-bottom: 0; cursor: pointer; }
.refresh-progress[open] > summary { padding-bottom: 12px; border-bottom: 1px solid var(--app-border); margin-bottom: 10px; }
@media (max-width: 680px) { .account-command-bar { align-items: flex-start; gap: 10px; }.account-primary-actions { width: 100%; }.account-primary-actions > .el-button { flex: 1; padding-left: 10px; padding-right: 10px; }.account-scope-status { width: 100%; }.scope-choices :deep(.el-radio) { padding: 10px; } }
.traffic-summary-line { margin-top: 12px; }
.traffic-account-row { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 5px 16px; padding: 8px 0; border-bottom: 1px solid var(--app-border); }
.traffic-account-row > .mono { font-size: 12px; overflow-wrap: anywhere; }
.account-task-traffic { margin: 4px 0; text-align: left; }

.refresh-proxy-control { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 16px; margin-bottom: 18px; padding: 12px 16px; background: var(--app-card-bg); border: 1px solid var(--app-border); border-radius: 10px; }
.refresh-proxy-label { display: inline-flex; align-items: center; gap: 7px; font-size: 12px; color: var(--app-text-muted); }
.refresh-proxy-control > .el-select { width: 275px; max-width: 100%; }
@media (max-width: 680px) { .refresh-proxy-control { padding: 12px; gap: 8px; }.refresh-proxy-control > .el-select { width: 100%; }.refresh-proxy-control > .hint { line-height: 1.5; } }
.refresh-job-panel { padding: 18px 20px; border: 1px solid var(--brand-border); border-radius: 12px; background: var(--app-card-bg); margin-bottom: 20px; }
.refresh-job-heading { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-bottom: 12px; font-size: 13px; }
.refresh-job-heading > span { color: var(--app-text-muted); margin-left: auto; }
.refresh-job-panel p { margin: 8px 0 0; overflow-wrap: anywhere; }
.refresh-job-error { color: var(--color-warning); font-size: 12px; line-height: 1.6; }
.refresh-failure { display: flex; flex-direction: column; padding: 8px 0; overflow-wrap: anywhere; }
.refresh-failure > strong { font-weight: 500; color: var(--app-title); }

.reg-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
}
.reg-stats-badges {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.stat-pill b {
  font-weight: 700;
  margin-left: 2px;
}

.group-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
  padding: 10px 14px;
  margin-bottom: 14px;
  border-radius: 8px;
  background: var(--app-card-surface);
  border: 1px solid var(--app-border);
}
.group-bar-left {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  flex: 1;
}
.group-bar-label {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--app-text-muted);
  display: inline-flex;
  align-items: center;
  gap: 5px;
  margin-right: 4px;
}
.group-pills {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}
.group-pill-wrap {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  background: var(--app-card-bg);
  border: 1px solid var(--app-border);
  transition: all 0.15s ease;
  overflow: hidden;
}
.group-pill-wrap.active {
  border-color: var(--brand);
  box-shadow: 0 0 0 1px var(--brand);
}
.group-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 11px;
  border-radius: 999px;
  border: 1px solid var(--app-border);
  background: var(--app-card-bg);
  color: var(--app-text-muted);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}
.group-pill-custom {
  border: none !important;
  border-radius: 0 !important;
  padding-right: 6px;
}
.group-pill:hover {
  color: var(--app-title);
  background: var(--app-card-surface);
  border-color: var(--app-border-hover);
}
.group-pill.active {
  background: var(--brand-bg);
  color: var(--brand);
  font-weight: 600;
  border-color: var(--brand);
}
.group-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 17px;
  padding: 0 5px;
  border-radius: 999px;
  font-size: 10.5px;
  font-weight: 600;
  font-family: ui-monospace, monospace;
  background: var(--app-card-surface);
  color: var(--app-text-muted);
}
.group-pill.active .group-count {
  background: var(--brand);
  color: var(--brand-fg);
}
.group-mini-act {
  border: none;
  background: transparent;
  color: var(--el-text-color-secondary);
  cursor: pointer;
  padding: 4px 5px;
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  transition: color 0.15s;
}
.group-mini-act:hover {
  color: var(--el-color-primary);
}
.group-mini-act.danger:hover {
  color: var(--el-color-danger);
}
.group-bar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.row-group-tag {
  cursor: pointer;
  max-width: 118px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.row-group-empty {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}
.row-group-empty:hover {
  color: var(--el-color-primary);
}

:deep(.el-button.cell-copy.el-button--small) {
  padding: 0 6px 0 0;
  height: 20px;
  font-size: 12px;
}
:deep(.cell-copy .ico) {
  margin-left: 5px;
  opacity: 0;
  transition: opacity 0.12s;
}
:deep(.cell-copy:hover .ico) { opacity: 0.65; }

.zero-hit {
  font-weight: 700;
  letter-spacing: 0.2px;
}

.checkout-summary { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; font-size: 12px; padding: 12px 14px; background: var(--brand-bg); border: 1px solid var(--brand-border); border-radius: 8px; margin-bottom: 18px; color: var(--app-text-muted); }.checkout-summary > .el-icon, .checkout-summary b { color: var(--brand); }.checkout-summary b { font-weight: 600; }.checkout-summary details { margin-left: auto; }.checkout-summary summary { cursor: pointer; }.registered-page :deep(.reg-stats-badges) { gap: 6px; }.registered-page :deep(.stat-pill) { font-size: 11px; }.registered-page :deep(.group-bar) { background: transparent; border: 0; border-bottom: 1px solid var(--app-border); border-radius: 0; padding: 0 0 16px; }.registered-page :deep(.group-pill-wrap) { max-width: 100%; }.registered-page :deep(.group-pills) { gap: 6px; }
@media (max-width: 680px) { .checkout-summary { gap: 8px; }.checkout-summary > span { flex-basis: 100%; }.checkout-summary details { margin-left: 0; }.registered-page :deep(.group-bar-right) { width: 100%; }.result-filters :deep(.el-space__item) { max-width: 100%; }.registered-page :deep(.reg-header-row) { gap: 12px; } }

.toolbar-disclosure .group-bar-right { margin-bottom: 14px; }.registered-page :deep(.result-filters) { display: flex; }.registered-page :deep(.group-bar-left) { min-width: 0; flex-wrap: nowrap; }.registered-page :deep(.group-bar-label) { flex-shrink: 0; }.registered-page :deep(.group-pills) { flex-wrap: nowrap; overflow-x: auto; padding-bottom: 3px; max-width: 100%; }.registered-page :deep(.group-pill), .registered-page :deep(.group-pill-wrap) { flex-shrink: 0; }@media(max-width: 680px) { .registered-page :deep(.group-bar) { margin-bottom: 14px; }.registered-page :deep(.group-bar-left) { width: 100%; }.registered-page :deep(.reg-stats-badges) { flex-wrap: wrap; }.registered-page :deep(.stat-pill) { height: auto; padding: 4px 7px; } }

.reg-header-row { gap: 16px; align-items: center; }
.accounts-heading { margin-bottom: 24px; }
.heading-actions { display: flex; align-items: center; gap: 8px; }
.reg-header-row .section-title { font-size: 14px; letter-spacing: 0; }
.account-row-actions { display: flex; align-items: center; justify-content: center; gap: 4px; }
.group-pill, .group-pill-wrap { border-radius: 8px; }
.group-pill-wrap.active { box-shadow: none; border-color: var(--brand-border); }
@media (hover: hover) { .group-mini-act { opacity: 0; }.group-pill-wrap:hover .group-mini-act, .group-pill-wrap:focus-within .group-mini-act, .group-pill-wrap.active .group-mini-act { opacity: 1; } }
.reg-stats-badges :deep(.el-tag) { background: transparent; border: 0; color: var(--app-text-muted); padding: 0 8px; font-size: 12px; }
.reg-stats-badges :deep(.el-tag b) { color: var(--app-title); font-size: 14px; }
.checkout-summary { background: var(--app-card-surface); border-color: var(--app-border); padding: 11px 14px; }
.result-filters { padding: 4px 0 12px; gap: 8px !important; }
.column-toggle { margin: 0 6px; color: var(--app-text-muted); }
.mobile-column-toggle { display: none; }
.toolbar-disclosure { margin: 0 0 20px; border: 1px solid var(--app-border); border-radius: 12px; background: var(--app-card-surface); }
.toolbar-disclosure > summary { padding: 13px 16px; font-size: 13px; font-weight: 600; color: var(--app-title); cursor: pointer; }
.toolbar-disclosure { padding: 0; }
.toolbar-disclosure[open] > summary { border-bottom: 1px solid var(--app-border); margin-bottom: 16px; }
.toolbar-disclosure > .group-bar-right, .toolbar-disclosure > :deep(.el-space) { margin-left: 16px; margin-right: 16px; }
.toolbar-disclosure > :deep(.el-space) { margin-bottom: 16px; }
.toolbar-disclosure :deep(.el-button:not(.el-button--danger)) { --el-button-bg-color: var(--app-card-bg); --el-button-text-color: var(--app-title); --el-button-border-color: var(--app-border); --el-button-hover-bg-color: var(--brand-bg); --el-button-hover-text-color: var(--brand); --el-button-hover-border-color: var(--brand-border); }
.registered-page :deep(.el-table) { border: 1px solid var(--app-border); border-radius: 12px; }
.registered-page :deep(.el-table th.el-table__cell) { height: 46px; font-size: 11px; color: var(--app-text-muted); background: var(--app-card-surface); }
.registered-page :deep(.el-table td.el-table__cell) { height: 58px; font-size: 12px; }
.registered-page :deep(.el-table .mono) { font-size: 12px; }
@media (max-width: 680px) {
 .accounts-heading { align-items: flex-start; flex-direction: column; gap: 12px; margin-bottom: 18px; }.accounts-heading p { display: none; }.heading-actions { width: 100%; }.heading-actions > .el-button { flex: 1; }
 .checkout-summary { gap: 8px; padding: 9px 10px; }.checkout-summary > span { display: none; }.checkout-summary details { margin-left: auto; }.checkout-summary details[open] { flex-basis: 100%; }
 .desktop-column-toggle { display: none; }.mobile-column-toggle { display: inline-flex; }.group-bar-right { flex-wrap: wrap; }
 .reg-header-row { align-items: flex-start; flex-direction: column; }
 .reg-stats-badges { gap: 4px; }
 .result-filters :deep(.el-input), .result-filters :deep(.el-select) { max-width: 100%; }
 .toolbar-disclosure > summary { padding: 12px; }
 .registered-page :deep(.el-pagination) { flex-wrap: wrap; justify-content: center; gap: 8px; }
}
.accounts-heading { margin-bottom: 18px; }
.refresh-progress { padding: 12px 16px; margin-bottom: 12px; }
.registered-page :deep(.group-bar) { margin-bottom: 12px; padding-bottom: 12px; }
.checkout-summary { padding: 7px 12px; margin-bottom: 12px; }
.result-filters { padding: 0; }
.account-command-bar { padding: 11px 0; margin-bottom: 8px; }
.toolbar-disclosure { margin-bottom: 12px; }
.toolbar-disclosure > summary { padding: 10px 14px; }
.account-more-tools { padding-top: 16px; }
</style>
