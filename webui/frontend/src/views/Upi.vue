<script setup>
import { computed, onActivated, onDeactivated, onUnmounted, provide, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Copy, Pause, Square, SlidersHorizontal } from 'lucide-vue-next'
import { copyText, fmtTime } from '@/api/request'
import { getRegistered, listRegisteredGroups, assignRegisteredGroup } from '@/api/register'
import UpiAccount from '@/components/UpiAccount.vue'
import { createUpiSounds } from '@/upiAudio'
import { useRuntimeStore } from '@/stores/runtime'
import { usePrivacyStore } from '@/stores/privacy'
import { upiPostScanLabel } from '@/upi'
import { useI18nStore } from '@/stores/i18n'
import { localeTag } from '@/i18n/locale'
import { UPI_LIMIT, UPI_NEW_SCAN_KEY, upiScanBatch, beginUpiScanBatch, isNewUpiScan, upiFilters, upiPhase, parseUpiTokens, upiCsv, upiLsExport, reuseUpiTasks, canControlUpiTask, canRenewUpiTask, collectUpiTasks, collectUpiAccounts, runUpiControls, upiAccountEmail, upiAccountFields, loadUpiAccounts } from '@/upi'
import { getUpiConfig, saveUpiConfig, getUpiAutomation, saveUpiAutomation, getUpiSummary, getUpiAccounts, prepareUpi, submitUpi,
  getUpiRequests, getUpiTasks, getUpiTask, refreshUpiTask, controlUpiTask, controlUpiTasks, reconcileUpiScan, previewUpiNewLink, createUpiNewLink } from '@/api/upi'

const i18n = useI18nStore()
const runtime = useRuntimeStore()
const privacy = usePrivacyStore(), composeExpanded = ref(false)
const t = text => i18n.t(text)
const config = ref({ api_key_set: false, unit_points: 6 })
const provider = ref('ytc')
const methodLabel = value => value === 'local' ? 'Tự trích xuất + Camellia' : 'YTC trọn gói'
const configured = computed(() => provider.value === 'local' ? config.value.camellia_api_key_set : config.value.api_key_set)
const unitPoints = computed(() => provider.value === 'local' ? summary.value.unit_points : config.value.unit_points)
const summary = ref({ account: null, service: null, errors: [] })
const keyInput = ref(''), clearKey = ref(false), configOpen = ref(false), saving = ref(false)
const camelliaKeyInput = ref(''), clearCamelliaKey = ref(false)
const workerDraft = ref(10), workerSaving = ref(false)
const tokenText = ref(''), selectedEmails = ref([]), mode = ref('STANDARD'), autoRetry = ref(false)
const requestId = ref(''), batch = ref(null), lastBatch = ref(null), pending = ref([])
const confirming = ref(false), consent = ref(false), preparing = ref(false), submitting = ref(false)
const rows = ref([]), total = ref(0), counts = ref({}), loading = ref(false), taskError = ref('')
const selectedTaskIds = ref([]), controlBusy = ref(''), controlResult = ref(null), controlProgress = ref(null)
const selectedTaskCache = ref({}), selectionProgress = ref(null)
const filter = ref(''), search = ref(''), date = ref(''), page = ref(1), pageSize = ref(25)
const detail = ref(null), detailOpen = ref(false), rowBusy = ref(''), updatedAt = ref(0)
const renewalOpen = ref(false), renewalQuote = ref(null), renewalToken = ref(''), renewalConsent = ref(false), renewalSending = ref(false), renewalRequest = ref('')
watch(renewalOpen, open => { if (!open) { renewalToken.value = ''; renewalConsent.value = false; renewalQuote.value = null; renewalRequest.value = '' } })
const pickerOpen = ref(false), pickerRows = ref([]), pickerGroups = ref([]), pickerTotal = ref(0)
const pickerSelecting = ref(false), pickerProgress = ref({ loaded: 0, total: 0 })
let pickerAllSequence = 0, pickerSearchTimer
watch(pickerOpen, open => { if (!open) { clearTimeout(pickerSearchTimer); ++pickerSequence; ++pickerAllSequence; pickerLoading.value = false; pickerSelecting.value = false } })
const pickerPage = ref(1), pickerSearch = ref(''), pickerGroup = ref(''), pickerLoading = ref(false), picked = ref([])
const fileInput = ref(null)
const accountInfo = ref({}), accountGroups = ref([]), groupsLoading = ref(false), groupsError = ref(false), accountMoving = ref('')
const credentialNow = ref(Date.now())
// Only account widgets subscribe to the second hand, not the table/page render.
provide('upiCredentialNow', credentialNow)
const mobileQuery = window.matchMedia('(max-width: 680px)'), mobileView = ref(mobileQuery.matches)
const syncing = ref(false)
const newScanBatch = ref(readScanBatch())
const autoFields = ['refresh_at', 'check_plan', 'check_quota', 'move_plus', 'sound_scanning', 'sound_completed']
const automation = ref({ settings: Object.fromEntries(autoFields.map(name => [name, false])), recent: [], monitor: {} })
const autoOpen = ref(false), autoSaving = ref(false), autoDraft = ref({}), autoLoading = ref(false), autoError = ref('')
const sounds = createUpiSounds()
let stopAudioUnlock = () => {}
let notificationCursor = -1
const automationEnabled = computed(() => autoFields.some(name => automation.value.settings[name]))
const soundWanted = computed(() => automation.value.settings.sound_scanning || automation.value.settings.sound_completed)
watch(soundWanted, wanted => { if (wanted && active) void sounds.enable(); else if (!wanted) sounds.close() })
const autoRecords = computed(() => {
  const result = {}
  for (const item of automation.value.recent) if (!result[item.task_id]) result[item.task_id] = item
  return result
})
const autoFor = id => autoRecords.value[id]
const stepLabel = name => ({ refresh_at: 'Làm mới AT', check_plan: 'Kiểm tra gói', check_quota: 'Cập nhật quota', move_plus: 'Chuyển thư mục PLUS' })[name] || name
const stepState = state => ({ pending: 'Đang chờ', running: 'Đang xử lý', done: 'Hoàn tất', failed: 'Thất bại', skipped: 'Bỏ qua' })[state] || state
const followupLabel = item => !item ? '' : item.state === 'pending' ? 'Chờ xử lý sau quét' : item.state === 'running' ? item.message || 'Đang xử lý sau quét' : item.message
const lsOpen = ref(false), lsScope = ref('page'), lsRequire2fa = ref(true), lsRecords = ref([])
const lsCopying = ref(false)
let active = false, timer, credentialTimer, accountSequence = 0, taskSequence = 0, pickerSequence = 0, refreshing = null

function readScanBatch(fallback) {
  let raw
  try { raw = localStorage.getItem(UPI_NEW_SCAN_KEY) } catch (_) { /* Optional visual preference. */ }
  const marker = raw ? upiScanBatch(raw) : fallback || upiScanBatch(null)
  try { localStorage.setItem(UPI_NEW_SCAN_KEY, JSON.stringify(marker)) } catch (_) { /* Keep the in-memory marker. */ }
  return marker
}
function startScanBatch(requestId) {
  newScanBatch.value = beginUpiScanBatch(newScanBatch.value, requestId)
  try { localStorage.setItem(UPI_NEW_SCAN_KEY, JSON.stringify(newScanBatch.value)) } catch (_) { /* Keep the in-memory marker. */ }
}
function syncScanBatch(event) {
  if (event.key === UPI_NEW_SCAN_KEY) newScanBatch.value = upiScanBatch(event.newValue)
}

const accountFor = email => accountInfo.value[upiAccountEmail(email)]
async function loadAccounts(force = false) {
  const emails = [...new Set([...rows.value.map(row => row.email), ...(detailOpen.value ? [detail.value?.email] : [])].map(upiAccountEmail).filter(Boolean))]
  const next = Object.fromEntries(emails.filter(email => accountInfo.value[email]).map(email => [email, accountInfo.value[email]]))
  if (Object.keys(next).length !== Object.keys(accountInfo.value).length) accountInfo.value = next
  if (!force && emails.every(email => next[email])) return
  const needed = emails.filter(email => email !== accountMoving.value && (force || !next[email] || next[email].state === 'loading'))
  const seq = ++accountSequence
  for (const email of needed) if (accountInfo.value[email]?.state !== 'ready') accountInfo.value[email] = { state: 'loading' }
  await loadUpiAccounts(needed, getRegistered, {
    isActive: () => active && seq === accountSequence,
    onResult: (email, result) => { if (accountMoving.value !== email) accountInfo.value[email] = result },
  })
}
async function loadAccountGroups() {
  if (groupsLoading.value) return
  groupsLoading.value = true; groupsError.value = false
  try { const result = await listRegisteredGroups(); if (active) accountGroups.value = result.groups || [] }
  catch (_) { groupsError.value = true }
  finally { groupsLoading.value = false }
}
async function moveAccount(email, group) {
  const key = upiAccountEmail(email), current = accountInfo.value[key]
  if (accountMoving.value || controlBusy.value || current?.state !== 'ready' || group === current.account.group_name) return
  accountMoving.value = key
  let changed = false
  try {
    const result = await assignRegisteredGroup([key], group, { filter: 'all', group: current.account.group_name || '__ungrouped__' })
    changed = result.updated === 1
    accountGroups.value = result.groups || accountGroups.value
    const response = await getRegistered(key)
    const account = upiAccountFields(response.data, key)
    if (active) accountInfo.value[key] = { state: 'ready', account }
    if (!changed || account.group_name !== group) throw new Error(t('Tài khoản đã thay đổi. Hãy kiểm tra thư mục hiện tại.'))
    ElMessage.success(t('Đã chuyển thư mục tài khoản.'))
  } catch (error) {
    if (changed) {
      if (active) accountInfo.value[key] = { state: 'error' }
      ElMessage.warning(t('Đã gửi chuyển thư mục; cần tải lại để xác nhận.'))
    } else ElMessage.error(errorText(error))
  } finally {
    if (changed) runtime.bumpData()
    accountMoving.value = ''
  }
}
function credentialClock() {
  clearTimeout(credentialTimer)
  credentialNow.value = Date.now()
  if (active && !document.hidden) credentialTimer = setTimeout(credentialClock, 1000 - Date.now() % 1000 + 5)
}

const tokenInput = computed(() => {
  try { return { tokens: parseUpiTokens(tokenText.value), error: '' } }
  catch (error) { return { tokens: [], error: error.message } }
})
const inputCount = computed(() => tokenInput.value.tokens.length + selectedEmails.value.length)
const ambiguous = computed(() => pending.value.some(x => ['sending', 'uncertain', 'retryable'].includes(x.state)))
const activeTasks = computed(() => rows.value.some(x => x.control.pending || ['queued', 'running', 'scanning', 'awaiting_funds'].includes(x.phase)) ||
  ['QUEUED', 'ACTIVE', 'SCANNING'].some(x => Number(counts.value[x]) > 0))
const selectableTasks = computed(() => rows.value.filter(row => row.id))
const selectedTasks = computed(() => selectedTaskIds.value.map(id => rows.value.find(row => row.id === id) || selectedTaskCache.value[id]).filter(Boolean))
const controlTargets = action => selectedTasks.value.filter(row => canControlUpiTask(row, action))
const allPageSelected = computed(() => selectableTasks.value.length > 0 && selectableTasks.value.every(row => selectedTaskIds.value.includes(row.id)))
const lsBusy = computed(() => loading.value || !!controlBusy.value || !!accountMoving.value || !!taskError.value || rows.value.some(row => upiAccountEmail(row.email) && (!accountFor(row.email) || accountFor(row.email).state === 'loading')))
const lsSelectedCount = computed(() => lsRecords.value.filter(row => row.selected).length)
const lsResult = computed(() => upiLsExport(lsRecords.value.filter(row => lsScope.value === 'page' || row.selected), { require2fa: lsRequire2fa.value }))
const controlLabel = action => ({ pause: 'Tạm dừng', resume: 'Tiếp tục', stop: 'Dừng hẳn' })[action]
const stat = key => counts.value[key] ?? null
const format = value => value == null ? '—' : new Intl.NumberFormat(localeTag(i18n.locale), { maximumFractionDigits: 2 }).format(value)
const stamp = value => value ? fmtTime(value) : '—'
const errorText = error => error?.message || t('Không tải được dữ liệu UPI.')
const draftLabel = state => ({ prepared: 'Chưa gửi', sending: 'Đang gửi', uncertain: 'Chờ đối chiếu', retryable: 'Chờ thử lại' })[state] || state
watch([tokenText, selectedEmails, mode, autoRetry], () => { requestId.value = '' }, { deep: true })
watch(filter, () => { clearTaskSelection(); controlResult.value = null })
watch(provider, async () => {
  ++taskSequence; ++accountSequence
  rows.value = []; counts.value = {}; total.value = 0; clearTaskSelection(); accountInfo.value = {}; renewalOpen.value = false
  pending.value = []; batch.value = null; lastBatch.value = null; requestId.value = ''; detailOpen.value = false
  page.value = 1; filter.value = ''; taskError.value = ''; controlResult.value = null
  loading.value = false; syncing.value = false; updatedAt.value = 0; notificationCursor = -1
  summary.value = { account: null, service: null, errors: [] }
  automation.value = { ...automation.value, recent: [], events: [], monitor: {} }
  await refresh()
})

async function loadTasks({ reloadAccounts = false, background = false } = {}) {
  if (background && (loading.value || syncing.value || controlBusy.value || rowBusy.value)) return
  if (!configured.value) { rows.value = []; total.value = 0; selectedTaskIds.value = []; return }
  const seq = ++taskSequence
  if (!background) loading.value = true
  syncing.value = true
  try {
    const response = await getUpiTasks({ provider: provider.value, page: page.value - 1, size: pageSize.value, status: filter.value, query: search.value.trim(), date: date.value || '' })
    if (seq !== taskSequence || !active || (background && (controlBusy.value || rowBusy.value))) return
    rows.value = reuseUpiTasks(rows.value, response.items); total.value = response.total; counts.value = response.filter_counts
    await loadAccounts(reloadAccounts)
    if (seq !== taskSequence || !active) return
    for (const row of rows.value) if (selectedTaskIds.value.includes(row.id)) selectedTaskCache.value[row.id] = row
    if (controlResult.value) {
      for (const item of controlResult.value.items.filter(item => item.ok)) {
        const current = rows.value.find(row => row.id === item.id)
        if (current) item.pending = !!current.control.pending
      }
      controlResult.value.pending = controlResult.value.items.filter(item => item.ok && item.pending).length
    }
    updatedAt.value = Date.now() / 1000; taskError.value = ''
  } catch (error) { if (seq === taskSequence) taskError.value = errorText(error) }
  finally { if (seq === taskSequence) { loading.value = false; syncing.value = false } }
}
async function loadSummary() {
  const scope = provider.value
  try { const result = await getUpiSummary(scope); if (active && provider.value === scope) summary.value = result }
  catch (error) { if (active && provider.value === scope) summary.value.errors = [{ message: errorText(error) }] }
}
async function loadPending() {
  const scope = provider.value
  try { const result = await getUpiRequests(scope); if (active && provider.value === scope) pending.value = result.items }
  catch (error) { if (active && provider.value === scope) taskError.value = errorText(error) }
}
async function refresh(all = true, { background = false } = {}) {
  if (refreshing) {
    if (background) return
    await refreshing
    return refresh(all)
  }
  if (!active) return
  const request = Promise.all([loadTasks({ reloadAccounts: all, background }), loadPending(), loadAutomation(), ...(all ? [loadSummary()] : [])])
  refreshing = request
  try { await request }
  finally { if (refreshing === request) refreshing = null }
}
async function loadAutomation() {
  if (autoLoading.value) return
  autoLoading.value = true
  const scope = provider.value
  try {
    const result = await getUpiAutomation({ after: notificationCursor, provider: scope })
    if (!active || provider.value !== scope) return
    const previous = autoRecords.value
    automation.value = result
    notificationCursor = result.cursor
    autoError.value = ''
    if (!document.hidden) {
      for (const kind of ['scanning', 'completed']) {
        if (result.settings[`sound_${kind}`] && result.events.some(event => event.kind === kind)) {
          void sounds.notify(kind, () => active && !document.hidden && provider.value === scope && automation.value.settings[`sound_${kind}`])
        }
      }
    }
    const changed = result.recent.filter(item => item.account_changed_at && item.account_changed_at !== previous[item.task_id]?.account_changed_at)
    if (changed.length) {
      for (const item of changed) delete accountInfo.value[upiAccountEmail(item.email)]
      await loadAccounts()
      runtime.bumpData()
    }
  } catch (error) { if (active && provider.value === scope) autoError.value = errorText(error) }
  finally { autoLoading.value = false }
}
async function openAutomation() {
  await loadAutomation()
  autoDraft.value = { revision: automation.value.settings.revision || 0, ...Object.fromEntries(autoFields.map(name => [name, !!automation.value.settings[name]])) }
  autoOpen.value = true
}
async function enableSounds(kind) {
  if (await sounds.enable() && active && kind) sounds.play(kind)
}
async function saveAutomation() {
  autoSaving.value = true
  try {
    if (autoDraft.value.sound_scanning || autoDraft.value.sound_completed) void sounds.enable()
    const result = await saveUpiAutomation(autoDraft.value, provider.value)
    automation.value = result; notificationCursor = result.cursor; autoOpen.value = false
    ElMessage.success(t('Đã lưu cài đặt tự động UPI.'))
  } catch (error) { ElMessage.error(errorText(error)) }
  finally { autoSaving.value = false }
}
function openConfig() {
  keyInput.value = config.value.api_key || ''; clearKey.value = false
  camelliaKeyInput.value = config.value.camellia_api_key || ''; clearCamelliaKey.value = false
  configOpen.value = true
}
function clearConfigInputs() { keyInput.value = ''; camelliaKeyInput.value = ''; clearKey.value = false; clearCamelliaKey.value = false }
async function saveKey() {
  saving.value = true
  try {
    config.value = await saveUpiConfig({ api_key: clearKey.value ? '' : keyInput.value.trim(), clear_key: clearKey.value })
    notificationCursor = -1
    clearConfigInputs(); configOpen.value = false
    ElMessage.success(t('Đã lưu cấu hình UPI.'))
    await refresh()
  } catch (error) { ElMessage.error(errorText(error)) }
  finally { saving.value = false }
}
async function readFile(event) {
  const file = event.target.files?.[0]
  if (!file) return
  try {
    if (file.size > 40 * 1024 * 1024) throw new Error(t('Tệp AT tối đa 40 MB.'))
    const text = await file.text()
    parseUpiTokens(text)
    tokenText.value = text
  } catch (error) { ElMessage.error(errorText(error)) }
  event.target.value = ''
}
async function preview() {
  if (tokenInput.value.error) return ElMessage.error(t(tokenInput.value.error))
  if (!inputCount.value || inputCount.value > UPI_LIMIT) return ElMessage.warning(t('Chọn từ 1 đến 20.000 tài khoản.'))
  preparing.value = true
  try {
    if (!requestId.value) requestId.value = crypto.randomUUID()
    const result = await prepareUpi({ request_id: requestId.value, tokens: tokenInput.value.tokens,
      emails: selectedEmails.value, provider: provider.value, processing_mode: mode.value, auto_retry: provider.value === 'ytc' && autoRetry.value })
    batch.value = result.batch; consent.value = false; confirming.value = true
    await loadPending()
  } catch (error) { ElMessage.error(errorText(error)) }
  finally { preparing.value = false }
}
function resumeBatch(item) { batch.value = item; consent.value = false; confirming.value = true }
async function send() {
  if (!consent.value || !batch.value || submitting.value) return
  submitting.value = true
  startScanBatch(batch.value.request_id)
  try {
    const result = await submitUpi(batch.value.request_id, batch.value.provider || 'ytc')
    batch.value = result.batch; lastBatch.value = result.batch
    if (result.batch.state === 'accepted') {
      confirming.value = false; tokenText.value = ''; selectedEmails.value = []; requestId.value = ''
      ElMessage.success(t('Dịch vụ đã nhận yêu cầu UPI.'))
    } else ElMessage.warning(t(result.batch.message || 'Cần đối chiếu yêu cầu UPI.'))
    await refresh()
  } catch (error) { ElMessage.error(errorText(error)); await loadPending() }
  finally { submitting.value = false }
}
function clearTaskSelection() { selectedTaskIds.value = []; selectedTaskCache.value = {} }
function setFilter(value) { if (controlBusy.value) return; filter.value = value; page.value = 1; clearTaskSelection(); loadTasks() }
function applySearch() { if (controlBusy.value) return; page.value = 1; clearTaskSelection(); controlResult.value = null; loadTasks() }
function selectTask(id, checked) {
  if (checked) selectedTaskCache.value[id] = rows.value.find(row => row.id === id)
  else delete selectedTaskCache.value[id]
  selectedTaskIds.value = checked ? [...new Set([...selectedTaskIds.value, id])] : selectedTaskIds.value.filter(value => value !== id)
}
function selectTaskPage(checked) { for (const row of selectableTasks.value) selectTask(row.id, checked) }
async function selectAllTasks() {
  if (controlBusy.value || loading.value || rowBusy.value || !configured.value) return
  controlBusy.value = 'select'
  const scope = provider.value
  try {
    const tasks = await collectUpiTasks(getUpiTasks, { provider: scope, status: filter.value, query: search.value.trim(), date: date.value || '' },
      { isActive: () => active && provider.value === scope, onProgress: value => { selectionProgress.value = value } })
    selectedTaskCache.value = Object.fromEntries(tasks.map(task => [task.id, task]))
    selectedTaskIds.value = tasks.map(task => task.id)
    controlResult.value = null
  } catch (error) { if (active) ElMessage.error(errorText(error)) }
  finally { controlBusy.value = ''; selectionProgress.value = null }
}
async function saveWorkers() {
  if (workerSaving.value || !Number.isInteger(workerDraft.value) || workerDraft.value < 1 || workerDraft.value > 100) return
  workerSaving.value = true
  try {
    config.value = await saveUpiConfig({ local_workers: workerDraft.value })
    workerDraft.value = config.value.local_workers
    await loadSummary()
    ElMessage.success(t('Đã cập nhật số luồng trích xuất.'))
  } catch (error) { ElMessage.error(errorText(error)) }
  finally { workerSaving.value = false }
}
function applyControlProgress(progress, item) {
  controlProgress.value = progress
  if (item.ok) {
    if (selectedTaskIds.value.includes(item.id)) selectedTaskCache.value[item.id] = item.task
    rows.value = rows.value.map(row => row.id === item.id ? item.task : row)
    if (detail.value?.id === item.id) detail.value = item.task
  }
}
async function controlTasks(tasks, action) {
  if (controlBusy.value || rowBusy.value || loading.value || !active) return
  const targets = tasks.filter(row => canControlUpiTask(row, action))
  if (!targets.length) return
  controlBusy.value = action
  ++taskSequence; syncing.value = false
  try {
    const question = { pause: 'Tạm dừng {0} tác vụ đã chọn?', resume: 'Tiếp tục {0} tác vụ đã chọn?', stop: 'Dừng hẳn {0} tác vụ đã chọn? Không thể tiếp tục sau khi dừng hẳn.' }[action]
    await ElMessageBox.confirm(t(question).replace('{0}', format(targets.length)) + ' ' + t('Đơn đã có link vẫn có thể tiếp tục quét và trừ điểm.'),
      t(controlLabel(action)), { confirmButtonText: t(controlLabel(action)), cancelButtonText: t('Hủy'), type: 'warning' })
    if (!active) return
    controlResult.value = null
    controlProgress.value = { total: targets.length, items: [] }
    const scope = provider.value
    const result = scope === 'local' ? await controlUpiTasks(targets.map(task => task.id), action) :
      await runUpiControls(targets, action, (id, command) => controlUpiTask(id, command, scope), { isActive: () => active && provider.value === scope, onProgress: applyControlProgress })
    if (!active || provider.value !== scope) return
    if (scope === 'local') for (const item of result.items) applyControlProgress(result, item)
    controlResult.value = result
    const acceptedIds = new Set(result.items.filter(item => item.ok).map(item => item.id))
    selectedTaskIds.value = selectedTaskIds.value.filter(id => !acceptedIds.has(id))
    for (const id of acceptedIds) delete selectedTaskCache.value[id]
    if (result.failed || result.not_sent) ElMessage.warning(t('Có lệnh chưa được xác nhận; hãy xem kết quả trước khi gửi lại.'))
    else ElMessage.success(t('Dịch vụ đã nhận lệnh điều khiển.'))
    await refresh()
  } catch (error) { if (error !== 'cancel' && error !== 'close') ElMessage.error(errorText(error)) }
  finally { controlBusy.value = ''; controlProgress.value = null }
}
async function showDetail(row) {
  if (controlBusy.value || rowBusy.value) return
  rowBusy.value = row.id
  try { const response = await getUpiTask(row.id, row.provider || provider.value); detail.value = response.task; detailOpen.value = true; loadAccounts() }
  catch (error) { ElMessage.error(errorText(error)) }
  finally { rowBusy.value = '' }
}
async function openRenewal(row) {
  if (controlBusy.value || rowBusy.value || renewalSending.value || provider.value !== 'local') return
  if (row.renewal?.task_id) return showDetail({ id: row.renewal.task_id, provider: 'local' })
  if (!canRenewUpiTask(row)) return
  rowBusy.value = row.id
  try {
    const quote = await previewUpiNewLink(row.id)
    if (!active || provider.value !== 'local') return
    if (quote.existing_task_id) {
      detail.value = (await getUpiTask(quote.existing_task_id, 'local')).task; detailOpen.value = true
      return
    }
    renewalQuote.value = quote; renewalRequest.value = crypto.randomUUID()
    renewalToken.value = ''; renewalConsent.value = false; renewalOpen.value = true
  } catch (error) { ElMessage.error(errorText(error)) }
  finally { rowBusy.value = '' }
}
async function submitRenewal() {
  if (renewalSending.value || !renewalConsent.value || !renewalQuote.value || provider.value !== 'local') return
  renewalSending.value = true
  try {
    const response = await createUpiNewLink(renewalQuote.value.source_task_id, { request_id: renewalRequest.value, confirmed: true,
      access_token: renewalToken.value.trim(), unit_points: renewalQuote.value.unit_points })
    if (!active || provider.value !== 'local') return
    renewalOpen.value = false
    filter.value = ''; page.value = 1; clearTaskSelection()
    detail.value = response.task; detailOpen.value = true
    ElMessage.success(t('Đã xếp hàng tạo link mới; chỉ gửi Camellia khi có link mới hợp lệ.'))
    await refresh()
  } catch (error) { ElMessage.error(errorText(error)) }
  finally { renewalSending.value = false }
}
async function act(row, action) {
  if (['pause', 'resume', 'stop'].includes(action)) return controlTasks([row], action)
  if (controlBusy.value || rowBusy.value) return
  try {
    if (action !== 'refresh') {
      const message = action === 'reconcile' ? t('Đối chiếu đơn quét gốc bằng cùng khóa chống trùng. Đơn đã được nhận vẫn có thể hoàn tất thanh toán và trừ điểm.') :
        t('Tạm dừng hoặc dừng chỉ chặn bước lấy link mới. Đơn đã có link vẫn có thể quét và trừ điểm. Dừng không thể khôi phục.')
      await ElMessageBox.confirm(message, t(action === 'reconcile' ? 'Đối chiếu UPI' : 'Điều khiển tác vụ UPI'),
        { confirmButtonText: t('Xác nhận'), cancelButtonText: t('Hủy'), type: 'warning' })
    }
    rowBusy.value = row.id
    const scope = row.provider || provider.value
    if (action === 'refresh') await refreshUpiTask(row.id, scope)
    else if (action === 'reconcile') await reconcileUpiScan(row.id, scope)
    if (detailOpen.value && detail.value?.id === row.id) detail.value = (await getUpiTask(row.id, scope)).task
    await refresh()
  } catch (error) { if (error !== 'cancel' && error !== 'close') ElMessage.error(errorText(error)) }
  finally { rowBusy.value = '' }
}
function exportPage() {
  const url = URL.createObjectURL(new Blob([upiCsv(rows.value)], { type: 'text/csv;charset=utf-8' }))
  const link = document.createElement('a'); link.href = url; link.download = `upi-${new Date().toISOString().slice(0, 10)}.csv`
  link.click(); URL.revokeObjectURL(url)
}
function openLsExport() {
  if (lsBusy.value || !rows.value.length) return
  lsRecords.value = rows.value.map(row => {
    const info = accountFor(row.email)
    return { email: row.email, selected: selectedTaskIds.value.includes(row.id),
      info: info ? { state: info.state, account: info.account ? { ...info.account } : null } : null }
  })
  lsScope.value = lsSelectedCount.value ? 'selected' : 'page'
  lsRequire2fa.value = true
  lsOpen.value = true
}
async function copyLs() {
  if (!lsOpen.value || !lsResult.value.count || lsCopying.value) return
  lsCopying.value = true
  try { await copyText(lsResult.value.text) }
  finally { lsCopying.value = false }
}
function downloadLs() {
  if (!lsOpen.value || !lsResult.value.count) return
  const url = URL.createObjectURL(new Blob([lsResult.value.text], { type: 'text/plain;charset=utf-8' }))
  const link = document.createElement('a'); link.href = url
  link.download = `upi-ls-${lsResult.value.count}-${new Date().toISOString().slice(0, 10)}.txt`
  link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
  lsOpen.value = false; lsRecords.value = []
}
async function loadPicker() {
  clearTimeout(pickerSearchTimer)
  const seq = ++pickerSequence
  pickerLoading.value = true
  try {
    const result = await getUpiAccounts({ page: pickerPage.value - 1, size: 50, query: pickerSearch.value.trim(), group: pickerGroup.value })
    if (seq !== pickerSequence || !active || !pickerOpen.value) return
    pickerRows.value = result.items; pickerTotal.value = result.total; pickerGroups.value = result.groups
  } catch (error) { if (seq === pickerSequence && active && pickerOpen.value) ElMessage.error(errorText(error)) }
  finally { if (seq === pickerSequence) pickerLoading.value = false }
}
function openPicker() { picked.value = [...selectedEmails.value]; pickerOpen.value = true; loadPicker() }
function pick(email, checked) {
  picked.value = checked ? [...new Set([...picked.value, email])] : picked.value.filter(x => x !== email)
}
function pickPage() { picked.value = [...new Set([...picked.value, ...pickerRows.value.filter(x => x.usable).map(x => x.email)])] }
async function pickAllAccounts() {
  if (pickerSelecting.value) return
  const seq = ++pickerAllSequence
  const params = { query: pickerSearch.value.trim(), group: pickerGroup.value }
  const current = () => active && pickerOpen.value && seq === pickerAllSequence && params.query === pickerSearch.value.trim() && params.group === pickerGroup.value
  pickerSelecting.value = true
  pickerProgress.value = { loaded: 0, total: pickerTotal.value }
  try {
    const emails = await collectUpiAccounts(getUpiAccounts, params, { isActive: current, onProgress: value => { pickerProgress.value = value } })
    if (!current()) return
    const next = [...new Set([...picked.value, ...emails])]
    if (next.length + tokenInput.value.tokens.length > UPI_LIMIT) throw new Error('Tối đa 20.000 tài khoản mỗi đợt; hãy thu hẹp bộ lọc.')
    picked.value = next
  } catch (error) { if (current()) ElMessage.error(errorText(error)) }
  finally { if (seq === pickerAllSequence) pickerSelecting.value = false }
}
function schedulePickerSearch() {
  clearTimeout(pickerSearchTimer)
  ++pickerSequence
  pickerLoading.value = true
  pickerSearchTimer = setTimeout(() => {
    if (active && pickerOpen.value) pickerSearchChanged()
  }, 300)
}
function pickerSearchChanged() { pickerPage.value = 1; loadPicker() }
function applyPicker() { selectedEmails.value = [...picked.value]; pickerOpen.value = false }
function updateMobileView(event) { mobileView.value = event.matches }
function visibilityChanged() { credentialClock(); if (active && !document.hidden) refresh(false, { background: true }) }
function stop() { clearTimeout(pickerSearchTimer); ++pickerSequence; pickerOpen.value = false; pickerLoading.value = false; active = false; refreshing = null; ++taskSequence; ++accountSequence; loading.value = false; syncing.value = false; accountInfo.value = {}; lsOpen.value = false; lsRecords.value = []; renewalOpen.value = false; renewalToken.value = ''; stopAudioUnlock(); sounds.close(); clearTimeout(credentialTimer); clearInterval(timer); document.removeEventListener('visibilitychange', visibilityChanged); window.removeEventListener('storage', syncScanBatch); mobileQuery.removeEventListener('change', updateMobileView) }
onActivated(async () => {
  active = true
  stopAudioUnlock = sounds.listen(document, () => active && soundWanted.value)
  notificationCursor = -1
  newScanBatch.value = readScanBatch(newScanBatch.value)
  window.addEventListener('storage', syncScanBatch)
  mobileView.value = mobileQuery.matches
  mobileQuery.addEventListener('change', updateMobileView)
  credentialClock()
  document.addEventListener('visibilitychange', visibilityChanged)
  timer = setInterval(() => { if (active && !document.hidden && !controlBusy.value && (activeTasks.value || automationEnabled.value)) refresh(false, { background: true }) }, 10000)
  try { config.value = await getUpiConfig(); workerDraft.value = config.value.local_workers || 10; await refresh() }
  catch (error) { taskError.value = errorText(error) }
})
onDeactivated(stop)
onUnmounted(stop)
</script>

<template>
  <div class="page upi-page">
    <div class="page-heading">
      <div><h1>UPI / Plus</h1><p>Gửi tài khoản, quét UPI và theo dõi kết quả trong một nơi.</p></div>
      <div class="heading-actions"><el-button :loading="loading" :disabled="!!controlBusy" @click="refresh()"><el-icon><Refresh /></el-icon>Làm mới</el-button><el-button :disabled="!!controlBusy" @click="openConfig"><el-icon><Key /></el-icon>Cấu hình API</el-button><el-button @click="openAutomation"><SlidersHorizontal :size="14" />Tự động &amp; chuông</el-button></div>
    </div>

    <el-alert v-if="!configured" :title="t(provider === 'local' ? 'Nhập API key Camellia Standard trong Cấu hình API.' : 'Cần khóa Yitiaochong API để kết nối dịch vụ UPI.')" type="info" :closable="false" show-icon />
    <el-alert v-for="(error, index) in summary.errors" :key="index" :title="error.message" type="warning" :closable="false" show-icon />

    <section class="upi-metrics surface-panel" aria-label="Tổng quan UPI">
      <div><span>Điểm khả dụng</span><strong class="upi-balance">{{ format(summary.account?.available_points) }}</strong><small><span>Đang giữ</span> {{ format(summary.account?.reserved_points) }} · <span>Phí API</span> {{ format(unitPoints) }} <span>điểm / lượt thành công</span></small></div>
      <div><span>Đang chờ</span><strong>{{ format(stat('QUEUED')) }}</strong><small><span>{{ t(provider === 'local' ? 'Luồng trích xuất' : 'Song song tài khoản') }}</span> {{ format(provider === 'local' ? summary.service?.limit : summary.account?.concurrency_limit) }}</small></div>
      <div><span>Đang xử lý</span><strong>{{ format(stat('ACTIVE')) }}</strong><small><span>Đang quét</span> {{ format(stat('SCANNING')) }}</small></div>
      <div><span>Đã quét</span><strong>{{ format(stat('COMPLETED')) }}</strong><small><span>{{ t(provider === 'local' ? 'Luồng đang chạy' : 'Giới hạn dịch vụ') }}</span> {{ format(provider === 'local' ? summary.service?.running : summary.service?.limit) }} · <span>UPI</span></small></div>
    </section>

    <section class="surface-panel upi-compose">
      <div class="upi-section-heading"><div><h2>Tạo đợt UPI</h2><p v-if="composeExpanded">{{ t(provider === 'local' ? 'Tự lấy link qua ChatGPT / Stripe, gửi AT và link đến Camellia sau xác nhận.' : 'AT chỉ được gửi đến ytc.xxsyun.xyz sau bước xác nhận.') }}</p><p v-else-if="inputCount">{{ inputCount }} <span>tài khoản trong bản nháp</span></p></div><div class="resource-card-actions"><el-tag v-if="summary.service" :type="summary.service.available ? 'success' : 'warning'">{{ t(summary.service.available ? 'Dịch vụ sẵn sàng' : 'Dịch vụ đang bận') }}</el-tag><el-button :aria-expanded="composeExpanded" aria-controls="upi-compose-body" @click="composeExpanded = !composeExpanded">{{ t(composeExpanded ? 'Thu gọn' : 'Mở tạo đợt') }}</el-button></div></div>
      <div v-show="composeExpanded" id="upi-compose-body" class="upi-compose-grid">
        <div class="upi-token-panel">
          <div class="upi-token-heading"><label for="upi-at-input">Access Token</label><div class="upi-inline-actions"><el-button text @click="openPicker"><el-icon><Users /></el-icon>Chọn từ kho</el-button><el-button text @click="fileInput?.click()"><el-icon><Upload /></el-icon>TXT / JSON</el-button><el-button text :disabled="!tokenText" @click="tokenText = ''">Xóa ô nhập</el-button></div></div>
          <input ref="fileInput" class="upi-file-input" type="file" accept=".txt,.json,text/plain,application/json" aria-label="Nhập tệp AT UPI" @change="readFile" />
          <el-input id="upi-at-input" v-model="tokenText" type="textarea" :rows="7" autocomplete="off" spellcheck="false" placeholder="Mỗi dòng một AT, hoặc dán JSON tài khoản." aria-label="AT gửi UPI" />
          <div class="upi-input-caption"><span>{{ format(inputCount) }} / 20.000 <span>tài khoản</span></span><el-button v-if="selectedEmails.length" text @click="openPicker"><span>Đã chọn từ kho</span> {{ selectedEmails.length }}</el-button></div>
          <p v-if="tokenInput.error" class="upi-error">{{ t(tokenInput.error) }}</p>
        </div>
        <div class="upi-options">
          <div><span class="upi-field-label">Gói đăng ký</span><div class="upi-plan"><el-icon><Sparkles /></el-icon>ChatGPT Plus<el-tag size="small">UPI</el-tag></div></div>
          <template v-if="provider === 'ytc'"><div><span class="upi-field-label">Chế độ xử lý</span><el-radio-group v-model="mode" class="upi-mode" aria-label="Chế độ UPI"><el-radio-button value="STANDARD">Standard · 流光</el-radio-button><el-radio-button value="STRICT">Strict · sea</el-radio-button></el-radio-group></div>
          <el-checkbox v-model="autoRetry">Tự thử lại khi quét thất bại</el-checkbox><p class="upi-hint">Tối đa 3 lần bổ sung, giữ nguyên tác vụ gốc.</p></template>

          <div class="upi-price"><span>Ước tính nếu tất cả thành công</span><strong>{{ format(unitPoints == null ? null : inputCount * unitPoints) }} <span>điểm</span></strong></div>
          <el-button type="primary" :loading="preparing" :disabled="!configured || !inputCount || inputCount > UPI_LIMIT || !!tokenInput.error || ambiguous" @click="preview"><el-icon><ScanSearch /></el-icon>Xem trước và gửi</el-button>
          <p class="upi-hint">Chỉ nhận checkout 0; phí quét tính riêng. Ưu đãi có thể kèm mandate gia hạn thuê bao.</p>
        </div>
      </div>
    </section>

    <section v-if="pending.length" class="surface-panel upi-pending">
      <div class="upi-section-heading"><div><h2>Yêu cầu cần xử lý</h2><p>Giữ cùng mã yêu cầu khi đối chiếu; không tạo đợt mới cho phản hồi chưa rõ.</p></div></div>
      <div v-for="item in pending" :key="item.request_id" class="upi-pending-row"><div><strong>{{ item.count }} <span>tài khoản</span> · {{ t(draftLabel(item.state)) }}</strong><code>{{ item.request_id }}</code><small v-if="item.message">{{ item.message }}</small></div><el-button @click="resumeBatch(item)">Xem lại</el-button></div>
    </section>

    <el-alert v-if="lastBatch?.result" type="info" :closable="false" show-icon><template #title><span>Đã nhận</span> {{ lastBatch.result.accepted }} · <span>Bỏ qua</span> {{ lastBatch.result.skipped }} · <span>Chờ đối chiếu</span> {{ lastBatch.result.unknown }} · <span>Từ chối</span> {{ lastBatch.result.rejected }}</template></el-alert>

    <section class="surface-panel upi-history">
      <div class="upi-section-heading"><div><h2>Tác vụ UPI</h2><p>Quét thành công cần được kiểm tra gói lại trong mục Tài khoản.</p></div><div class="upi-export-actions"><el-button type="primary" plain :disabled="!rows.length || lsBusy" @click="openLsExport"><el-icon><Download /></el-icon>Xuất LS</el-button><el-button :disabled="!rows.length" @click="exportPage">Xuất CSV</el-button></div></div>
      <nav class="upi-filters" aria-label="Lọc tác vụ UPI"><button v-for="[value, label] in upiFilters" :key="value" type="button" :class="{active: filter === value}" :aria-pressed="filter === value" :disabled="!!controlBusy" @click="setFilter(value)">{{ t(label) }}<span v-if="value && stat(value) != null">{{ format(stat(value)) }}</span></button></nav>
      <div class="upi-search-row"><el-input v-model="search" :disabled="!!controlBusy" clearable placeholder="Email hoặc mã tác vụ" aria-label="Tìm tác vụ UPI" @keyup.enter="applySearch" @clear="applySearch"><template #prefix><el-icon><Search /></el-icon></template></el-input><el-date-picker v-model="date" :disabled="!!controlBusy" type="date" value-format="YYYY-MM-DD" placeholder="Ngày tạo" aria-label="Ngày tạo tác vụ UPI" @change="applySearch" /><el-button :disabled="!!controlBusy" @click="applySearch">Tìm kiếm</el-button><span class="upi-updated" v-if="updatedAt" :aria-busy="syncing"><span>Cập nhật</span> {{ new Date(updatedAt * 1000).toLocaleTimeString(localeTag(), {hour:'2-digit',minute:'2-digit'}) }}</span></div>
      <div v-if="automationEnabled || autoError" class="upi-automation-status"><span v-if="automationEnabled">Tự động UPI đang bật</span><span v-if="automation.monitor.error || autoError" class="upi-error">{{ t(automation.monitor.error || autoError) }}</span></div>
      <el-alert v-if="taskError" :title="taskError" type="error" :closable="false" show-icon />
      <div class="upi-control-toolbar" role="group" :aria-label="t('Điều khiển tác vụ đã chọn')">
        <div class="upi-task-selection"><el-checkbox :model-value="allPageSelected" :indeterminate="rows.some(row => selectedTaskIds.includes(row.id)) && !allPageSelected" :disabled="!selectableTasks.length || !!controlBusy || loading || !!taskError" :aria-label="t('Chọn tác vụ trong trang')" @change="selectTaskPage">Chọn trang</el-checkbox><el-button type="primary" plain :loading="controlBusy === 'select'" :disabled="!total || !!controlBusy || !!rowBusy || loading || !!taskError" @click="selectAllTasks">Chọn tất cả kết quả</el-button><span><span>Đã chọn</span> {{ selectedTasks.length }} / {{ total }}</span><el-button text :disabled="!selectedTasks.length || !!controlBusy" @click="clearTaskSelection">Bỏ chọn</el-button></div>
        <div class="upi-control-buttons"><el-button type="warning" plain :loading="controlBusy === 'pause'" :disabled="!!controlBusy || !!rowBusy || loading || !!taskError || !controlTargets('pause').length" @click="controlTasks(selectedTasks, 'pause')"><el-icon><Pause /></el-icon>Tạm dừng<span class="upi-button-count">{{ controlTargets('pause').length }}</span></el-button><el-button type="primary" plain :loading="controlBusy === 'resume'" :disabled="!!controlBusy || !!rowBusy || loading || !!taskError || !controlTargets('resume').length" @click="controlTasks(selectedTasks, 'resume')"><el-icon><Play /></el-icon>Tiếp tục<span class="upi-button-count">{{ controlTargets('resume').length }}</span></el-button><el-button type="danger" plain :loading="controlBusy === 'stop'" :disabled="!!controlBusy || !!rowBusy || loading || !!taskError || !controlTargets('stop').length" @click="controlTasks(selectedTasks, 'stop')"><el-icon><Square /></el-icon>Dừng hẳn<span class="upi-button-count">{{ controlTargets('stop').length }}</span></el-button></div>
        <p v-if="selectionProgress" class="upi-control-note"><span>Đang chọn</span> {{ selectionProgress.loaded }} / {{ selectionProgress.total }}</p>
        <p class="upi-control-note">Chọn tất cả kết quả gồm mọi trang theo bộ lọc hiện tại; giữ lựa chọn khi chuyển trang. Dừng hẳn không thể tiếp tục; đơn đã có link vẫn có thể quét và trừ điểm.</p>
      </div>
      <div v-if="controlProgress || controlResult" class="upi-control-result" role="status" aria-live="polite"><p v-if="controlProgress"><span>Đang gửi lệnh</span> {{ controlProgress.items.length }} / {{ controlProgress.total }}</p><template v-else><p><span>Đã nhận lệnh</span> {{ controlResult.accepted }} · <span>Chờ áp dụng</span> {{ controlResult.pending }} · <span>Lỗi</span> {{ controlResult.failed }} · <span>Chưa gửi</span> {{ controlResult.not_sent }}</p><p v-if="controlResult.not_sent" class="upi-hint">Các lệnh còn lại chưa gửi. Hãy đồng bộ và kiểm tra trước khi thử lại.</p><details v-if="controlResult.failed"><summary>Xem lệnh chưa được xác nhận</summary><ul><li v-for="item in controlResult.items.filter(x => !x.ok)" :key="item.id"><code>{{ item.id }}</code> · {{ t(item.message) }}</li></ul></details></template></div>
      <el-table v-if="!mobileView" v-loading="loading" :data="rows" class="upi-desktop-table" row-key="id" empty-text="Chưa có tác vụ UPI.">
        <el-table-column width="46" align="center"><template #default="{row}"><el-checkbox class="upi-task-checkbox" :model-value="selectedTaskIds.includes(row.id)" :disabled="!!controlBusy || loading || !!taskError || !row.id" :aria-label="`${t('Chọn tác vụ')} ${row.email || row.id}`" @change="checked => selectTask(row.id, checked)" /></template></el-table-column>
        <el-table-column label="Tài khoản / Mã tác vụ" min-width="350"><template #default="{row}"><div class="upi-account-cell"><UpiAccount :new-scan="isNewUpiScan(row, newScanBatch)" :email="row.email" :info="accountFor(row.email)" :groups="accountGroups" :groups-loading="groupsLoading" :groups-error="groupsError" :moving="!!accountMoving || !!controlBusy" @folders-open="loadAccountGroups" @move="group => moveAccount(row.email, group)" @reload="loadAccounts(true)" @navigate="detailOpen = false" /><code>{{ row.id }}</code></div></template></el-table-column>
        <el-table-column label="Trạng thái" min-width="175"><template #default="{row}"><div class="upi-state-cell"><el-tag :type="upiPhase(row.phase).tone">{{ t(upiPhase(row.phase).label) }}</el-tag><small>{{ t(methodLabel(row.provider)) }}</small><small v-if="row.phase === 'completed'">{{ t(upiPostScanLabel(row, accountFor(row.email)?.account)) }}</small><small v-if="autoFor(row.id)" class="upi-followup-state">{{ t(followupLabel(autoFor(row.id))) }}</small><el-button v-if="canRenewUpiTask(row) || row.renewal?.task_id" size="small" type="warning" plain :disabled="!!controlBusy || !!rowBusy || renewalSending" @click="openRenewal(row)">{{ t(row.renewal?.task_id ? 'Xem lượt mới' : 'Tạo link mới') }}</el-button><small v-if="row.control.pending">Lệnh đang chờ áp dụng</small><small v-if="row.retry.count"><span>Số lần bổ sung</span> {{ row.retry.count }}</small></div></template></el-table-column>
        <el-table-column label="Quét thành công" min-width="155"><template #default="{row}">{{ stamp(row.scan_succeeded_at) }}</template></el-table-column>
        <el-table-column label="Thao tác" width="165" align="right"><template #default="{row}"><div class="upi-row-actions"><el-button size="small" :loading="rowBusy === row.id" :disabled="!row.id || !!controlBusy || !!rowBusy" @click="showDetail(row)">Chi tiết</el-button><el-dropdown trigger="click" @command="action => act(row, action)"><el-button size="small" :disabled="!row.id || !!controlBusy || !!rowBusy" :aria-label="t('Điều khiển tác vụ UPI')">···</el-button><template #dropdown><el-dropdown-menu><el-dropdown-item command="refresh">Đồng bộ tác vụ</el-dropdown-item><el-dropdown-item v-if="row.scan_status === 'UNKNOWN'" command="reconcile">Đối chiếu đơn quét</el-dropdown-item><el-dropdown-item v-if="canControlUpiTask(row, 'resume')" command="resume">Tiếp tục</el-dropdown-item><el-dropdown-item v-if="canControlUpiTask(row, 'pause')" command="pause">Tạm dừng</el-dropdown-item><el-dropdown-item v-if="canControlUpiTask(row, 'stop')" command="stop" class="danger-menu-item">Dừng hẳn</el-dropdown-item></el-dropdown-menu></template></el-dropdown></div></template></el-table-column>
      </el-table>
      <div v-else v-loading="loading" class="upi-mobile-tasks"><article v-for="row in rows" :key="row.id"><div class="upi-mobile-heading"><el-checkbox class="upi-task-checkbox" :model-value="selectedTaskIds.includes(row.id)" :disabled="!!controlBusy || loading || !!taskError || !row.id" :aria-label="`${t('Chọn tác vụ')} ${row.email || row.id}`" @change="checked => selectTask(row.id, checked)" /><el-tag :type="upiPhase(row.phase).tone">{{ t(upiPhase(row.phase).label) }}</el-tag></div><UpiAccount :new-scan="isNewUpiScan(row, newScanBatch)" :email="row.email" :info="accountFor(row.email)" :groups="accountGroups" :groups-loading="groupsLoading" :groups-error="groupsError" :moving="!!accountMoving || !!controlBusy" @folders-open="loadAccountGroups" @move="group => moveAccount(row.email, group)" @reload="loadAccounts(true)" @navigate="detailOpen = false" /><code>{{ row.id }}</code><p v-if="row.phase === 'completed'" class="upi-hint">{{ t(upiPostScanLabel(row, accountFor(row.email)?.account)) }}</p><p v-if="autoFor(row.id)" class="upi-hint">{{ t(followupLabel(autoFor(row.id))) }}</p><el-button v-if="canRenewUpiTask(row) || row.renewal?.task_id" type="warning" plain :disabled="!!controlBusy || !!rowBusy || renewalSending" @click="openRenewal(row)">{{ t(row.renewal?.task_id ? 'Xem lượt mới' : 'Tạo link mới') }}</el-button><div class="upi-mobile-footer"><span><span>Quét thành công</span> {{ stamp(row.scan_succeeded_at) }}</span><el-button :loading="rowBusy === row.id" :disabled="!!controlBusy || !!rowBusy" @click="showDetail(row)">Chi tiết</el-button></div></article><el-empty v-if="!rows.length" description="Chưa có tác vụ UPI." :image-size="55" /></div>
      <div class="upi-pagination"><span>{{ format(total) }} <span>kết quả</span></span><el-pagination :disabled="!!controlBusy" v-model:current-page="page" :page-size="pageSize" :total="total" layout="prev, pager, next" :pager-count="5" @current-change="loadTasks" /></div>
    </section>

    <el-dialog append-to-body v-model="lsOpen" title="Xuất LS nhanh" width="520px" @closed="lsRecords = []">
      <p class="upi-dialog-copy">Email---Mật khẩu---2FA · TXT</p>
      <el-radio-group v-model="lsScope" class="upi-ls-scope" aria-label="Phạm vi xuất LS">
        <el-radio value="selected" :disabled="!lsSelectedCount"><span>Đã chọn</span> · {{ lsSelectedCount }}</el-radio>
        <el-radio value="page"><span>Trang hiện tại</span> · {{ lsRecords.length }}</el-radio>
      </el-radio-group>
      <el-checkbox v-model="lsRequire2fa" class="upi-ls-twofa">Bỏ qua tài khoản thiếu 2FA</el-checkbox>
      <div class="upi-ls-summary" role="status" aria-live="polite"><strong><span>Sẵn sàng xuất</span> {{ lsResult.count }} <span>tài khoản</span></strong><span><span>Bỏ qua</span> {{ lsResult.skippedCount }} · <span>Trùng email</span> {{ lsResult.duplicates }}</span></div>
      <ul v-if="lsResult.skippedCount || lsResult.missing2fa" class="upi-ls-reasons">
        <li v-if="lsResult.skipped.unavailable"><span>Chưa có / không tải được tài khoản</span>: {{ lsResult.skipped.unavailable }}</li>
        <li v-if="lsResult.skipped.password"><span>Thiếu mật khẩu</span>: {{ lsResult.skipped.password }}</li>
        <li v-if="lsResult.skipped.twofa"><span>Thiếu 2FA</span>: {{ lsResult.skipped.twofa }}</li>
        <li v-if="lsResult.skipped.unsafe"><span>Dữ liệu chứa dấu phân cách hoặc ký tự xuống dòng</span>: {{ lsResult.skipped.unsafe }}</li>
        <li v-if="lsResult.missing2fa"><span>Sẽ xuất với ô 2FA trống</span>: {{ lsResult.missing2fa }}</li>
      </ul>
      <p class="upi-hint">Tệp chứa mật khẩu và 2FA dạng văn bản. Kết quả UPI không xác nhận gói Plus.</p>
      <template #footer><div class="upi-ls-actions"><el-button @click="lsOpen = false">Hủy</el-button><el-button :loading="lsCopying" :disabled="!lsResult.count" @click="copyLs"><el-icon><Copy /></el-icon>Sao chép LS</el-button><el-button type="primary" :disabled="!lsResult.count" @click="downloadLs"><el-icon><Download /></el-icon>Tải tệp LS</el-button></div></template>
    </el-dialog>

    <el-dialog append-to-body v-model="autoOpen" title="Tự động & chuông UPI" class="upi-automation-dialog" width="600px" :close-on-click-modal="false">
      <p class="upi-dialog-copy">Áp dụng cho tài khoản quét thành công từ lúc bật. Không xử lý lại lịch sử cũ.</p>
      <p class="upi-dialog-copy">YTC báo thanh toán thành công sẽ tự chuyển tài khoản vào PLUS. Không tự làm mới AT, kiểm tra gói hoặc quota; giữ thay đổi thư mục do bạn thực hiện.</p>
      <section class="upi-settings-section">
        <h3>Âm báo</h3>
        <div class="upi-setting-row"><div><strong>Có đơn đang quét</strong><small>Hai tiếng ngắn tăng dần.</small></div><el-button size="small" @click="enableSounds('scanning')">Nghe thử đang quét</el-button><el-switch v-model="autoDraft.sound_scanning" aria-label="Chuông đang quét" /></div>
        <div class="upi-setting-row"><div><strong>Quét thành công</strong><small>Bốn nốt hoàn tất, khác chuông đang quét.</small></div><el-button size="small" @click="enableSounds('completed')">Nghe thử thành công</el-button><el-switch v-model="autoDraft.sound_completed" aria-label="Chuông quét thành công" /></div>
        <p class="upi-hint">Chuông phát theo cài đặt đã lưu khi tab UPI đang mở; không lặp lại khi đồng bộ.</p>
      </section>
      <template #footer><el-button :disabled="autoSaving" @click="autoOpen = false">Hủy</el-button><el-button type="primary" :loading="autoSaving" @click="saveAutomation">Lưu cài đặt</el-button></template>
    </el-dialog>

    <el-dialog append-to-body v-model="configOpen" title="Cấu hình UPI" width="540px" class="upi-config-dialog" :close-on-click-modal="false" @closed="clearConfigInputs">
      <p class="upi-dialog-copy">Nhập khóa API YTC; để trống để giữ khóa đã lưu.</p>
      <label for="upi-api-key" class="upi-field-label">Khóa API Yitiaochong đang dùng</label><el-input id="upi-api-key" v-model="keyInput" :key="String(privacy.hidden)" :type="privacy.hidden ? 'password' : 'text'" :show-password="privacy.hidden" :disabled="clearKey" autocomplete="off" :placeholder="config.api_key_set ? t('Đã lưu khóa; để trống để giữ nguyên') : t('Nhập khóa API')" aria-label="Khóa 一条虫 API" />
      <el-checkbox v-if="config.api_key_set" v-model="clearKey" class="upi-clear-key">Xóa khóa đã lưu</el-checkbox>
      <template #footer><el-button :disabled="saving" @click="configOpen = false">Hủy</el-button><el-button type="primary" :loading="saving" @click="saveKey">Lưu và kiểm tra</el-button></template>
    </el-dialog>

    <el-dialog append-to-body v-model="confirming" title="Xác nhận gửi UPI" width="520px" :close-on-click-modal="false" :show-close="!submitting" :close-on-press-escape="!submitting" :before-close="done => { if (!submitting) done() }">
      <template v-if="batch"><div class="upi-confirm-stats"><div><span>Tài khoản hợp lệ</span><strong>{{ format(batch.count) }}</strong></div><div><span>Điểm nếu tất cả thành công</span><strong>{{ format(batch.estimated_points) }}</strong></div></div><p class="upi-dialog-copy"><b>ChatGPT Plus</b> · {{ t(methodLabel(batch.provider)) }}<template v-if="batch.provider !== 'local'"> · {{ batch.mode === 'STRICT' ? 'Strict · sea' : 'Standard · 流光' }}</template> · <span>Phí API</span> {{ batch.unit_points }} <span>điểm / lượt thành công</span></p><p class="upi-dialog-copy"><span>Bỏ qua</span>: {{ batch.skipped.expired }} <span>AT hết hạn</span>, {{ batch.skipped.invalid }} <span>AT không hợp lệ</span>, {{ batch.skipped.duplicates }} <span>trùng AT</span>.</p><el-alert v-if="batch.message" :title="batch.message" type="warning" :closable="false" /><p class="upi-dialog-copy"><span>Mã yêu cầu</span><code class="upi-request-id">{{ batch.request_id }}</code></p><el-checkbox v-model="consent" class="upi-consent">{{ t(batch.provider === 'local' ? 'Tôi đồng ý tự trích xuất qua ChatGPT / Stripe, gửi AT và link đến Camellia để quét và tính phí khi thành công.' : 'Tôi đồng ý gửi AT đến ytc.xxsyun.xyz để tự quét UPI và trừ điểm dịch vụ khi thành công.') }}</el-checkbox><p class="upi-hint">Checkout bắt buộc 0; phí dịch vụ UPI vẫn được tính. Bản xem trước chưa gửi thanh toán.</p><p v-if="batch.billing_source === 'generated'" class="upi-hint">Tên/địa chỉ thanh toán tự sinh, không phải hồ sơ thật.</p><p v-if="batch.provider === 'local'" class="upi-hint">UPI có thể xác minh 1 INR và tạo mandate gia hạn. Kiểm tra hoặc hủy gia hạn nếu không muốn tiếp tục thuê bao.</p></template>
      <template #footer><el-button :disabled="submitting" @click="confirming = false">Hủy</el-button><el-button type="primary" :loading="submitting" :disabled="!consent || ['accepted','expired','rejected'].includes(batch?.state)" @click="send">{{ t(batch?.state === 'prepared' ? 'Gửi và tự quét UPI' : 'Đối chiếu cùng yêu cầu') }}</el-button></template>
    </el-dialog>

    <el-dialog append-to-body v-model="pickerOpen" title="Chọn tài khoản từ kho" width="680px" class="upi-picker-dialog">
      <div class="upi-picker-search"><el-input v-model="pickerSearch" :disabled="pickerSelecting" clearable placeholder="Tìm email" aria-label="Tìm email trong kho UPI" @input="schedulePickerSearch" @keyup.enter="pickerSearchChanged" @clear="pickerSearchChanged" /><el-select v-model="pickerGroup" :disabled="pickerSelecting" clearable placeholder="Tất cả thư mục" aria-label="Thư mục tài khoản UPI" @change="pickerSearchChanged"><el-option v-for="name in pickerGroups" :key="name" :value="name" :label="name" /></el-select><el-button :disabled="pickerSelecting" @click="pickerSearchChanged">Tìm kiếm</el-button></div>
      <div class="upi-picker-toolbar"><span><span>Đã chọn</span> {{ picked.length }}</span><div><el-button text :disabled="pickerLoading || pickerSelecting" @click="pickPage">Chọn trang</el-button><el-button type="primary" plain :loading="pickerSelecting" :disabled="pickerLoading" @click="pickAllAccounts">Chọn tất cả kết quả</el-button><el-button text :disabled="pickerSelecting" @click="picked = []">Bỏ chọn</el-button></div></div>
      <p class="upi-hint">Chọn tất cả tài khoản có AT hợp lệ theo thư mục và từ khóa đang lọc, trên mọi trang.</p>
      <p v-if="pickerSelecting" class="upi-hint">Đang tải {{ pickerProgress.loaded }} / {{ pickerProgress.total }}</p>
      <div v-loading="pickerLoading" class="upi-picker-list"><el-checkbox v-for="row in pickerRows" :key="row.email" class="upi-picker-account" :model-value="picked.includes(row.email)" :disabled="!row.usable || pickerSelecting || pickerLoading" :aria-label="`${t('Chọn')} ${row.email}`" @change="checked => pick(row.email, checked)"><span class="upi-picker-identity"><strong>{{ row.email }}</strong><small>{{ row.group || '—' }}</small></span><el-tag v-if="!row.usable" type="warning">AT hết hạn / lỗi</el-tag></el-checkbox><el-empty v-if="!pickerRows.length" description="Không có tài khoản phù hợp." :image-size="55" /></div><el-pagination v-model:current-page="pickerPage" :disabled="pickerSelecting || pickerLoading" :page-size="50" :total="pickerTotal" layout="prev, pager, next" :pager-count="5" @current-change="loadPicker" />
      <template #footer><el-button @click="pickerOpen = false">Hủy</el-button><el-button type="primary" :disabled="pickerSelecting || picked.length + tokenInput.tokens.length > UPI_LIMIT" @click="applyPicker">Dùng tài khoản đã chọn</el-button></template>
    </el-dialog>

    <el-dialog append-to-body v-model="renewalOpen" title="Tạo link mới và gửi quét lại" width="520px" :close-on-click-modal="false" :close-on-press-escape="!renewalSending" :show-close="!renewalSending" :before-close="done => { if (!renewalSending) done() }">
      <template v-if="renewalQuote"><p class="upi-dialog-copy"><strong>{{ renewalQuote.email }}</strong> · {{ t('Lượt tạo link') }} {{ renewalQuote.attempt }}</p><p class="upi-dialog-copy">Giữ lịch sử đơn cũ. Tạo checkout mới, kiểm tra link mới rồi tự gửi AT và link sang Camellia.</p><p class="upi-dialog-copy"><span>Phí API</span> {{ format(renewalQuote.unit_points) }} <span>điểm / lượt thành công</span></p><p class="upi-hint">Chỉ tạo lại khi Camellia xác nhận đơn gốc đã thất bại, hết hạn hoặc bị hủy. Đơn chưa rõ kết quả cần đối chiếu trước.</p><template v-if="renewalQuote.needs_token"><label class="upi-field-label" for="upi-renewal-at">AT mới của tài khoản</label><el-input id="upi-renewal-at" v-model="renewalToken" type="password" show-password autocomplete="off" :disabled="renewalSending" aria-label="AT mới của tài khoản" /><p class="upi-hint">Kho chưa có AT còn hạn đúng tài khoản. Nhập AT mới để tiếp tục.</p></template><p v-else class="upi-hint">Tự dùng AT còn hạn của tài khoản trong kho.</p><el-checkbox v-model="renewalConsent" :disabled="renewalSending" class="upi-consent">Tôi đồng ý tạo checkout mới và gửi AT/link mới sang Camellia.</el-checkbox></template>
      <template #footer><el-button :disabled="renewalSending" @click="renewalOpen = false">Hủy</el-button><el-button type="primary" :loading="renewalSending" :disabled="!renewalConsent || !renewalQuote || (renewalQuote.needs_token && !renewalToken.trim())" @click="submitRenewal">Tạo link mới và gửi</el-button></template>
    </el-dialog>

    <el-dialog append-to-body v-model="detailOpen" title="Chi tiết tác vụ UPI" width="560px">
      <template v-if="detail"><div class="upi-detail-heading"><UpiAccount :new-scan="isNewUpiScan(detail, newScanBatch)" :email="detail.email" :info="accountFor(detail.email)" :groups="accountGroups" :groups-loading="groupsLoading" :groups-error="groupsError" :moving="!!accountMoving || !!controlBusy" @folders-open="loadAccountGroups" @move="group => moveAccount(detail.email, group)" @reload="loadAccounts(true)" @navigate="detailOpen = false" /><el-tag :type="upiPhase(detail.phase).tone">{{ t(upiPhase(detail.phase).label) }}</el-tag></div><code class="upi-request-id">{{ detail.id }}</code><dl class="upi-detail-grid"><dt>Trạng thái tạo link</dt><dd>{{ detail.status || '—' }}</dd><dt>Trạng thái quét</dt><dd>{{ detail.scan_status || '—' }}</dd><dt>Tạo link thành công</dt><dd>{{ stamp(detail.checkout_succeeded_at) }}</dd><dt>Quét thành công</dt><dd>{{ stamp(detail.scan_succeeded_at) }}</dd><dt>Số lần bổ sung</dt><dd>{{ detail.retry.count }} · {{ detail.retry.status || '—' }}</dd></dl><p v-if="detail.control.pending" class="upi-hint">Lệnh đang chờ áp dụng</p><p v-if="detail.control.scan_continues" class="upi-hint">Đơn đã có link vẫn tiếp tục quét.</p><div v-if="autoFor(detail.id)" class="upi-followup-detail"><strong>{{ t(followupLabel(autoFor(detail.id))) }}</strong><ul><li v-for="(step, name) in autoFor(detail.id).steps" :key="name"><span>{{ t(stepLabel(name)) }} · {{ t(stepState(step.state)) }}</span><small v-if="step.message">{{ t(step.message) }}</small></li></ul></div><p v-if="detail.message" class="upi-error">{{ detail.message }}</p><div class="upi-detail-actions"><el-button v-if="canRenewUpiTask(detail) || detail.renewal?.task_id" type="warning" :disabled="!!controlBusy || !!rowBusy || renewalSending" @click="openRenewal(detail)">{{ t(detail.renewal?.task_id ? 'Xem lượt mới' : 'Tạo link mới') }}</el-button><el-button :loading="rowBusy === detail.id" @click="act(detail, 'refresh')">Đồng bộ tác vụ</el-button><el-button v-if="detail.scan_status === 'UNKNOWN'" @click="act(detail, 'reconcile')">Đối chiếu đơn quét</el-button><el-button v-if="canControlUpiTask(detail, 'resume')" :disabled="!!controlBusy || !!rowBusy" @click="act(detail, 'resume')">Tiếp tục</el-button><el-button v-if="canControlUpiTask(detail, 'pause')" :disabled="!!controlBusy || !!rowBusy" @click="act(detail, 'pause')">Tạm dừng</el-button><el-button v-if="canControlUpiTask(detail, 'stop')" :disabled="!!controlBusy || !!rowBusy" type="danger" plain @click="act(detail, 'stop')">Dừng hẳn</el-button></div><a v-if="detail.payment_url" :href="detail.payment_url" target="_blank" rel="noopener noreferrer" class="upi-payment-link">Mở link thanh toán gốc ↗</a></template>
      <template #footer><el-button @click="detailOpen = false">Đóng</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
:global(.upi-config-dialog){display:flex;flex-direction:column;margin:16px auto!important;max-width:calc(100vw - 32px);max-height:calc(100dvh - 32px)}:global(.upi-config-dialog .el-dialog__header),:global(.upi-config-dialog .el-dialog__footer){flex:none}:global(.upi-config-dialog .el-dialog__body){min-height:0;overflow-y:auto}
.upi-ls-actions{display:flex;justify-content:flex-end;flex-wrap:wrap;gap:8px}.upi-ls-actions>.el-button{margin:0}
:global(.upi-automation-dialog){display:flex;flex-direction:column;margin:16px auto!important;max-width:calc(100vw - 32px);max-height:calc(100dvh - 32px)}:global(.upi-automation-dialog .el-dialog__header),:global(.upi-automation-dialog .el-dialog__footer){flex:none}:global(.upi-automation-dialog .el-dialog__body){min-height:0;overflow-y:auto}
.upi-settings-section{padding:13px 0;border-top:1px solid var(--app-border)}.upi-settings-section h3{font-size:13px;margin:0 0 8px;color:var(--app-title)}.upi-setting-row{display:flex;align-items:center;gap:13px;padding:8px 0;min-width:0}.upi-setting-row>div:first-child{display:flex;flex:1;flex-direction:column;gap:3px;min-width:0}.upi-setting-row strong{font-size:12px;font-weight:600}.upi-setting-row small{font-size:11px;line-height:1.5;color:var(--app-text-muted)}.upi-setting-row>.el-switch{flex:none}.upi-automation-status{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:0 0 13px;font-size:11px;color:var(--brand)}.upi-followup-detail{margin:13px 0;padding:13px;border:1px solid var(--app-border);border-radius:8px;font-size:12px}.upi-followup-detail ul{padding-left:16px;margin:8px 0 0}.upi-followup-detail li{margin-top:6px}.upi-followup-detail small{display:block;color:var(--app-text-muted);margin-top:3px}.upi-followup-state{color:var(--brand)}
@media(max-width:680px){.upi-setting-row{gap:8px;flex-wrap:wrap}.upi-setting-row>div:first-child{flex-basis:calc(100% - 56px);order:0}.upi-setting-row>.el-switch{order:1}.upi-setting-row>.el-button{order:2;margin:0;min-height:36px}.upi-page>.page-heading>.heading-actions>.el-button:last-child{grid-column:1/-1}}
.upi-export-actions{display:flex;gap:8px;flex-wrap:wrap;flex-shrink:0}.upi-export-actions>.el-button{margin:0}.upi-ls-scope{display:flex;gap:8px 21px;flex-wrap:wrap;margin-bottom:13px}.upi-ls-scope>.el-radio{margin:0;min-height:36px}.upi-ls-twofa{max-width:100%;height:auto;min-height:36px;margin:0 0 13px}.upi-ls-twofa :deep(.el-checkbox__label){white-space:normal;line-height:1.6}.upi-ls-summary{display:flex;flex-direction:column;gap:8px;padding:13px;border:1px solid var(--brand-border);border-radius:10px;background:var(--brand-bg);font-size:12px;margin-bottom:13px}.upi-ls-summary>strong{color:var(--brand);font-size:16px}.upi-ls-summary>span,.upi-ls-reasons{color:var(--app-text-muted)}.upi-ls-reasons{font-size:12px;line-height:1.7;padding-left:18px;margin:0 0 13px}@media(max-width:680px){.upi-export-actions{width:100%;display:grid;grid-template-columns:1.618fr 1fr}.upi-export-actions>.el-button{min-height:44px}.upi-ls-scope>.el-radio,.upi-ls-twofa{min-height:44px}}
.upi-page{display:flex;flex-direction:column;gap:21px}.upi-page>.page-heading{margin-bottom:0!important;display:flex;justify-content:space-between;gap:13px}.upi-page>.el-alert{border-radius:13px}.surface-panel{padding:21px;border:1px solid var(--app-border);min-width:0}.upi-metrics{display:grid;grid-template-columns:1.618fr 1fr 1fr 1fr;padding:21px 0}.upi-metrics>div{display:flex;flex-direction:column;gap:8px;padding:0 21px;border-right:1px solid var(--app-border)}.upi-metrics>div:last-child{border:0}.upi-metrics span,.upi-metrics small{font-size:11px;color:var(--app-text-muted);line-height:1.5}.upi-metrics strong{font-size:28px;line-height:1.25;font-weight:550}.upi-metrics .upi-balance{color:var(--brand)}.upi-section-heading{display:flex;align-items:center;justify-content:space-between;gap:13px;margin-bottom:21px}.upi-section-heading h2{font-size:15px;line-height:1.4;font-weight:550;margin:0}.upi-section-heading p{font-size:12px;color:var(--app-text-muted);margin:6px 0 0;line-height:1.5}.upi-compose-grid{display:grid;grid-template-columns:minmax(0,1.618fr) minmax(245px,1fr);gap:21px}.upi-token-panel{min-width:0;border:1px solid var(--app-border);border-radius:13px;overflow:hidden;background:var(--app-card-surface)}.upi-token-heading{min-height:47px;display:flex;align-items:center;justify-content:space-between;gap:8px;padding:6px 13px;border-bottom:1px solid var(--app-border)}.upi-token-heading label{font-size:12px;font-weight:550;white-space:nowrap}.upi-inline-actions{display:flex;flex-wrap:wrap;gap:4px;justify-content:flex-end}.upi-inline-actions .el-button{padding:6px 8px;font-size:11px;min-height:32px;box-shadow:none}.upi-token-panel :deep(.el-textarea__inner){resize:vertical;border:0;border-radius:0!important;box-shadow:none!important;background:transparent;min-height:200px;padding:13px;font:11px/1.6 ui-monospace,SFMono-Regular,Consolas,monospace}.upi-file-input{display:none}.upi-input-caption{display:flex;justify-content:space-between;align-items:center;gap:8px;border-top:1px solid var(--app-border);padding:8px 13px;min-height:40px;color:var(--app-text-muted);font-size:11px}.upi-input-caption .el-button{padding:2px 0;min-height:24px;font-size:11px;box-shadow:none}.upi-options{display:flex;flex-direction:column;gap:13px;min-width:0}.upi-field-label{display:block;font-size:12px;color:var(--app-text-regular);font-weight:500;margin:0 0 8px}.upi-plan{display:flex;align-items:center;gap:8px;min-height:34px;border:1px solid var(--app-border);border-radius:10px;padding:8px 13px;font-size:13px}.upi-plan .el-icon{color:var(--brand)}.upi-plan .el-tag{margin-left:auto}.upi-mode{display:flex}.upi-mode :deep(.el-radio-button){flex:1}.upi-mode :deep(.el-radio-button__inner){width:100%;padding:10px 8px;font-size:12px}.upi-mode :deep(.is-active .el-radio-button__inner){color:var(--brand-fg)}.upi-hint{font-size:11px;line-height:1.6;color:var(--app-text-muted);margin:0}.upi-options>.el-checkbox{margin:0}.upi-options>.el-checkbox+.upi-hint{margin-top:-8px}.upi-price{display:flex;justify-content:space-between;gap:8px;align-items:center;border-top:1px solid var(--app-border);padding-top:13px}.upi-price>span{font-size:11px;color:var(--app-text-muted)}.upi-price strong{font-size:14px;color:var(--brand);white-space:nowrap}.upi-price strong span{font-size:11px;font-weight:400}.upi-options>.el-button{width:100%;min-height:40px}.upi-pending-row{display:flex;justify-content:space-between;gap:13px;padding:13px 0;border-top:1px solid var(--app-border)}.upi-pending-row>div{min-width:0;display:flex;flex-direction:column;gap:6px}.upi-pending-row strong{font-size:12px}.upi-pending-row code,.upi-pending-row small{font-size:11px;overflow-wrap:anywhere;color:var(--app-text-muted)}.upi-pending-row .el-button{align-self:center;flex-shrink:0}.upi-filters{display:flex;gap:16px;overflow-x:auto;border-bottom:1px solid var(--app-border);margin-bottom:16px;scrollbar-width:thin}.upi-filters button{display:flex;align-items:center;gap:6px;white-space:nowrap;padding:10px 0;border:0;border-bottom:2px solid transparent;background:none;color:var(--app-text-muted);font:inherit;font-size:12px;cursor:pointer}.upi-filters button.active{color:var(--brand);border-bottom-color:var(--brand)}.upi-filters button span{font-size:10px;opacity:.8}.upi-search-row{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:13px}.upi-search-row>.el-input{max-width:340px}.upi-search-row :deep(.el-date-editor){max-width:185px;width:185px}.upi-updated{font-size:11px;color:var(--app-text-muted);margin-left:auto}.upi-account-cell,.upi-state-cell{display:flex;flex-direction:column;align-items:flex-start;gap:6px;min-width:0}.upi-account-cell strong{font-size:12px;font-weight:500;overflow-wrap:anywhere}.upi-account-cell code{font-size:10px;color:var(--app-text-dim);word-break:break-all}.upi-state-cell small{font-size:10px;color:var(--app-text-muted)}.upi-row-actions{display:flex;justify-content:flex-end;gap:8px}.upi-row-actions>.el-dropdown .el-button{min-width:34px;font-size:15px}.upi-pagination{display:flex;justify-content:space-between;align-items:center;gap:13px;flex-wrap:wrap;padding-top:16px}.upi-pagination>span{font-size:11px;color:var(--app-text-muted)}.upi-mobile-tasks{display:none}.upi-dialog-copy{font-size:12px;line-height:1.65;margin:0 0 16px;color:var(--app-text-muted);overflow-wrap:anywhere}.upi-clear-key{margin-top:16px}.upi-confirm-stats{display:grid;grid-template-columns:1fr 1fr;gap:13px;margin-bottom:21px}.upi-confirm-stats>div{display:flex;flex-direction:column;gap:8px;padding:13px;background:var(--brand-bg);border:1px solid var(--brand-border);border-radius:13px}.upi-confirm-stats span{font-size:11px;color:var(--app-text-muted)}.upi-confirm-stats strong{font-size:24px;color:var(--brand);font-weight:550}.upi-request-id{display:block;font-size:11px;overflow-wrap:anywhere;margin:8px 0 13px;color:var(--app-text-muted)}.upi-consent{display:flex;align-items:flex-start;margin:0 0 13px}.upi-consent :deep(.el-checkbox__input){margin-top:3px}.upi-consent :deep(.el-checkbox__label){font-size:12px;line-height:1.6;white-space:normal}.upi-picker-search{display:flex;gap:8px;flex-wrap:wrap}.upi-picker-search>.el-input{flex:1;min-width:170px}.upi-picker-search>.el-select{width:180px}.upi-picker-toolbar{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px;margin:13px 0;font-size:12px}.upi-picker-toolbar>div{display:flex;flex-wrap:wrap;gap:8px}.upi-picker-list{max-height:44vh;overflow:auto;min-height:90px;margin-bottom:13px}.upi-picker-account{display:flex;align-items:center;gap:8px;padding:10px 0;border-bottom:1px solid var(--app-border-subtle);cursor:pointer;min-width:0}.upi-picker-account>.el-checkbox{margin:0}.upi-picker-account>span{display:flex;flex-direction:column;gap:4px;min-width:0;flex:1}.upi-picker-account strong{font-size:12px;overflow-wrap:anywhere;font-weight:500}.upi-picker-account small{font-size:11px;color:var(--app-text-muted)}.upi-picker-account>.el-tag{font-size:10px;flex-shrink:0}.upi-detail-heading{display:flex;justify-content:space-between;gap:13px;align-items:center;flex-wrap:wrap}.upi-detail-heading strong{font-size:14px;overflow-wrap:anywhere}.upi-detail-grid{display:grid;grid-template-columns:minmax(120px,.618fr) minmax(0,1fr);gap:13px;font-size:12px;line-height:1.6;margin:21px 0}.upi-detail-grid dt{color:var(--app-text-muted)}.upi-detail-grid dd{margin:0;overflow-wrap:anywhere}.upi-detail-actions{display:flex;gap:8px;flex-wrap:wrap;margin:21px 0}.upi-payment-link,.upi-dialog-copy a{color:var(--brand);font-size:12px;line-height:1.6}.upi-error{font-size:12px;color:var(--color-danger);line-height:1.6;margin:8px 13px;overflow-wrap:anywhere}
@media(max-width:1100px){.upi-compose-grid{grid-template-columns:minmax(0,1fr)}.upi-options{display:grid;grid-template-columns:1fr 1fr;align-items:start}.upi-options>.upi-price,.upi-options>.el-button,.upi-options>.upi-hint:last-child{grid-column:1/-1}.upi-options>.el-checkbox+.upi-hint{margin:0;align-self:center}.upi-options>.el-button{min-height:44px}}
@media(max-width:680px){.upi-page{gap:16px}.upi-page>.page-heading{align-items:flex-start;flex-direction:column}.upi-page>.page-heading>.heading-actions{width:100%;display:grid;grid-template-columns:1fr 1fr}.surface-panel{padding:16px}.upi-metrics{grid-template-columns:1fr 1fr;padding:0}.upi-metrics>div{padding:16px;border-bottom:1px solid var(--app-border)}.upi-metrics>div:nth-child(2){border-right:0}.upi-metrics>div:nth-child(3){border-bottom:0}.upi-metrics>div:nth-child(4){border-bottom:0}.upi-metrics strong{font-size:25px}.upi-metrics small{font-size:10px}.upi-section-heading{align-items:flex-start;margin-bottom:16px;flex-wrap:wrap}.upi-token-heading{flex-wrap:wrap;padding:8px 12px}.upi-inline-actions{gap:4px}.upi-inline-actions .el-button{min-height:44px}.upi-options{display:flex;gap:13px}.upi-mode{width:100%}.upi-mode :deep(.el-radio-button__inner){min-height:44px;display:flex;align-items:center;justify-content:center}.upi-options>div{width:100%}.upi-plan{min-height:44px}.upi-search-row>.el-input{max-width:none;width:100%}.upi-search-row :deep(.el-date-editor){flex:1;max-width:none;min-width:140px}.upi-updated{width:100%;margin:4px 0 0}.upi-desktop-table{display:none}.upi-mobile-tasks{display:block}.upi-mobile-tasks>article{border:1px solid var(--app-border);border-radius:13px;padding:13px;margin-bottom:13px;background:var(--app-card-surface)}.upi-mobile-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:8px;margin-bottom:8px}.upi-mobile-heading>strong{min-width:0;overflow-wrap:anywhere;font-size:12px;font-weight:500}.upi-mobile-tasks code{display:block;font-size:10px;overflow-wrap:anywhere;color:var(--app-text-muted)}.upi-mobile-footer{display:flex;align-items:center;justify-content:space-between;gap:8px;border-top:1px solid var(--app-border);padding-top:8px;margin-top:13px}.upi-mobile-footer>span{font-size:10px;color:var(--app-text-muted);line-height:1.6}.upi-mobile-footer .el-button{flex-shrink:0}.upi-pagination{gap:8px}.upi-picker-search>.el-input,.upi-picker-search>.el-select{flex:auto;width:100%}.upi-picker-toolbar .el-button{padding:6px 8px}.upi-picker-account>.el-tag{max-width:85px;white-space:normal;line-height:1.4;height:auto}.upi-detail-grid{grid-template-columns:minmax(100px,.618fr) minmax(0,1fr);gap:8px}.upi-pending-row{gap:8px}.upi-pending-row code{font-size:10px}.upi-confirm-stats{gap:8px}.upi-confirm-stats>div{padding:10px}}
.upi-control-toolbar{display:flex;align-items:center;justify-content:space-between;gap:8px 16px;flex-wrap:wrap;padding:13px 0;border-top:1px solid var(--app-border);border-bottom:1px solid var(--app-border);margin:0 0 13px}.upi-task-selection{display:flex;align-items:center;gap:13px;min-height:34px;font-size:11px;color:var(--app-text-muted)}.upi-task-selection>.el-checkbox{margin:0}.upi-task-selection :deep(.el-checkbox__label){font-size:12px}.upi-task-selection>.el-button{padding:4px 6px;font-size:11px;min-height:30px}.upi-control-buttons{display:flex;gap:8px}.upi-control-buttons>.el-button{gap:6px;margin:0;padding:8px 10px;min-height:34px;font-size:12px}.upi-button-count{font-size:10px;opacity:.8;margin-left:5px}.upi-control-note{flex-basis:100%;font-size:11px;line-height:1.6;color:var(--app-text-muted);margin:0}.upi-task-checkbox{margin:0;min-height:32px}.upi-control-result{border:1px solid var(--app-border);border-radius:10px;padding:10px 13px;margin:0 0 13px;font-size:12px;line-height:1.6;overflow-wrap:anywhere;background:var(--brand-bg)}.upi-control-result p{margin:0 0 5px}.upi-control-result p:last-child{margin-bottom:0}.upi-control-result summary{cursor:pointer;color:var(--brand)}.upi-control-result ul{padding-left:18px;max-height:180px;overflow:auto;margin:8px 0 0}.upi-control-result code{font-size:10px}.upi-filters button:disabled{cursor:wait;opacity:.55}
@media(max-width:680px){.upi-control-toolbar{gap:8px}.upi-task-selection{width:100%;justify-content:space-between;gap:8px}.upi-control-buttons{width:100%;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}.upi-control-buttons>.el-button{min-height:44px;padding:8px 6px;font-size:11px;gap:4px}.upi-button-count{margin-left:3px}.upi-control-note{font-size:10px}.upi-mobile-heading>.upi-task-checkbox{flex-shrink:0;align-self:flex-start;min-height:20px;height:20px}.upi-mobile-heading>strong{flex:1}.upi-mobile-heading>.el-tag{flex-shrink:0}.upi-mobile-tasks>article:has(.upi-task-checkbox.is-checked){border-color:var(--brand-border);background:var(--brand-bg)}.upi-task-selection>.el-checkbox{min-height:44px}.upi-task-selection>.el-button{min-height:44px}}
.upi-detail-heading{align-items:flex-start}.upi-detail-heading>.upi-account{flex:1;min-width:0}.upi-account-cell>code{margin-top:8px;font-size:10px;color:var(--app-text-muted);overflow-wrap:anywhere}.upi-mobile-heading>.el-tag{margin-left:auto}.upi-mobile-tasks>article>.upi-account{margin:5px 0 13px}
.upi-provider-bar{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:16px 20px}.upi-provider-bar>div:first-child{display:flex;flex-direction:column;gap:5px}.upi-provider-bar small{font-size:11px;color:var(--app-text-muted)}.upi-provider-bar .el-radio-group{flex-shrink:0}.upi-local-info{padding:12px;border:1px solid var(--app-border);border-radius:8px}.upi-config-dialog .upi-field-label{margin-top:14px}.upi-extract-settings{margin-top:18px;border-top:1px solid var(--app-border);padding-top:14px}.upi-extract-settings>summary{cursor:pointer;font-weight:600;font-size:12px}.upi-billing-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:12px}.upi-config-dialog .el-dialog__body{max-height:65vh;overflow-y:auto}.upi-extract-settings>.upi-hint{margin:10px 0}.upi-config-dialog .upi-clear-key{margin-top:6px}@media(max-width:800px){.upi-provider-bar{align-items:stretch;flex-direction:column}.upi-provider-bar .el-radio-group{display:flex}.upi-provider-bar .el-radio-button{flex:1}.upi-provider-bar .el-radio-button__inner{width:100%;padding:10px 8px;font-size:11px;white-space:normal}.upi-billing-grid{grid-template-columns:minmax(0,1fr)}}
.upi-workers{display:flex;gap:8px;align-items:center;margin-top:8px}.upi-workers .el-input-number{min-width:0;width:140px}.upi-workers>.el-button{margin:0}.upi-task-selection{flex-wrap:wrap}.upi-task-selection>.el-button.is-plain{padding:6px 10px;font-size:12px}
</style>
