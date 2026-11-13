<script setup>
import { computed, onActivated, onDeactivated, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ShieldCheck } from 'lucide-vue-next'
import { importRegistered, listRegistered, listRegisteredGroups } from '@/api/register'
import { listSecurityJobs } from '@/api/security'
import { securityActive, securityEmails, securityModeLabel, securityState } from '@/accountSecurity'
import AccountSecurityDialog from '@/components/AccountSecurityDialog.vue'
import AccountSecurityProgress from '@/components/AccountSecurityProgress.vue'

const route = useRoute(), router = useRouter()
const rows = ref([]), total = ref(0), page = ref(1), keyword = ref(''), group = ref('all'), groups = ref([])
const selected = ref([]), loading = ref(false), dialog = ref(false), history = ref([]), error = ref('')
const importOpen = ref(false), importText = ref(''), importBusy = ref(false), importResult = ref('')
const emailsOpen = ref(false), emailText = ref('')
const selectedSet = computed(() => new Set(selected.value))
const jobId = computed(() => typeof route.query.job === 'string' ? route.query.job : '')
const activeHistory = computed(() => history.value.some(securityActive))
let sequence = 0, disposed = false, active = true
async function load(reset = false) {
  if (!active) return
  if (reset && page.value !== 1) { page.value = 1; return }
  const seq = ++sequence
  loading.value = true
  try {
    const result = await listRegistered({ q: keyword.value, group: group.value === 'all' ? '' : group.value, offset: (page.value - 1) * 50, limit: 50, include_summary: false })
    if (seq !== sequence || disposed) return
    rows.value = result.items; total.value = result.total; error.value = ''
  } catch (e) { if (seq === sequence) error.value = e.message }
  finally { if (seq === sequence) loading.value = false }
}
async function loadHistory() {
  if (!active) return
  try {
    const result = await listSecurityJobs()
    if (disposed) return
    history.value = result.jobs
    if (!jobId.value && result.jobs.length) router.replace({ query: { ...route.query, job: result.jobs[0].job_id } })
  } catch (e) { error.value = e.message }
}
function toggle(email, checked) {
  const next = new Set(selected.value)
  if (checked) { if (next.size >= 500) return ElMessage.warning('Tối đa 500 acc mỗi đợt.'); next.add(email) }
  else next.delete(email)
  selected.value = [...next]
}
function selectPage() {
  if (loading.value) return
  const next = new Set([...selected.value, ...rows.value.map(row => row.email)])
  if (next.size > 500) return ElMessage.warning('Tối đa 500 acc mỗi đợt.')
  selected.value = [...next]
}
function useEmails() {
  const emails = securityEmails(emailText.value)
  if (!emails.length || emails.length > 500) return ElMessage.warning('Nhập từ 1–500 email đã có trong kho.')
  selected.value = emails; emailsOpen.value = false; emailText.value = ''
}
async function doImport() {
  importBusy.value = true
  try {
    const lines = importText.value.split(/\r?\n/).filter(line => line.trim())
    if (!lines.length || lines.length > 500) return ElMessage.warning('Nhập từ 1–500 dòng tài khoản.')
    const result = await importRegistered(lines.join('\n'))
    importResult.value = `Thêm ${result.inserted || 0} · cập nhật ${result.updated || 0} · lỗi ${result.failed || 0}`
    const candidates = lines.map(line => line.split(/----|\|/)[0].trim().toLowerCase())
    selected.value = [...new Set(candidates.filter(email => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)))]
    if (!result.failed) { importText.value = ''; importOpen.value = false; ElMessage.success(importResult.value) }
    await load()
  } catch (e) { ElMessage.error(e.message) }
  finally { importBusy.value = false }
}
function created(job) { router.push({ query: { ...route.query, job: job.job_id } }); loadHistory() }
function updated(job) {
  const previous = history.value.find(item => item.job_id === job.job_id)
  const wasActive = previous && securityActive(previous)
  history.value = [job, ...history.value.filter(item => item.job_id !== job.job_id)]
  if (wasActive && !securityActive(job)) load()
}
watch(page, () => load())
onMounted(() => {
  load(); loadHistory()
  listRegisteredGroups().then(result => { if (!disposed) groups.value = result.groups || [] }).catch(() => {})
})
onBeforeUnmount(() => { disposed = true; sequence++ })
onDeactivated(() => { active = false; sequence++; dialog.value = false; importOpen.value = false; importText.value = '' })
onActivated(() => { if (!active) { active = true; load(); loadHistory() } })
</script>
<template>
  <div class="security-page">
    <div class="security-page-heading"><div class="security-title"><span><ShieldCheck :size="22"/></span><div><h1>Bảo mật acc</h1><p>Đổi mật khẩu, xoay 2FA và kick phiên từ kho tài khoản hiện tại.</p></div></div><router-link to="/registered"><el-button>Quản lý acc</el-button></router-link></div>
    <el-alert v-if="error" type="error" :title="error" :closable="false" show-icon/>
    <div class="security-layout">
      <el-card shadow="never" class="security-compose">
        <template #header><div class="security-card-heading"><strong>Chọn tài khoản</strong><span>{{ total.toLocaleString('vi-VN') }} trong phạm vi</span></div></template>
        <div class="security-picker-tools"><el-input v-model="keyword" clearable placeholder="Tìm email…" aria-label="Tìm tài khoản bảo mật" @keyup.enter="load(true)" @clear="load(true)"><template #append><el-button @click="load(true)">Tìm</el-button></template></el-input><el-select v-model="group" aria-label="Thư mục tài khoản" @change="load(true)"><el-option label="Tất cả thư mục" value="all"/><el-option label="Chưa phân thư mục" value="__ungrouped__"/><el-option v-for="item in groups" :key="item.name" :label="item.name" :value="item.name"/></el-select></div>
        <div class="security-pick-actions"><el-button text :disabled="loading || !rows.length" @click="selectPage">Chọn trang này</el-button><el-button text @click="emailsOpen=true">Dán email có sẵn</el-button><el-button text @click="importOpen=true; importResult=''">Nhập acc vào kho</el-button></div>
        <div v-loading="loading" class="security-picker"><div v-for="row in rows" :key="row.email" class="security-picker-row"><el-checkbox :model-value="selectedSet.has(row.email)" :aria-label="`Chọn ${row.email}`" @change="checked => toggle(row.email, checked)"><span class="security-picker-email" translate="no">{{ row.email }}</span><span class="security-picker-folder" translate="no">{{ row.group_name || 'Chưa phân thư mục' }}</span></el-checkbox></div><el-empty v-if="!loading && !rows.length" description="Không có tài khoản trong phạm vi này." :image-size="55"/></div>
        <el-pagination v-model:current-page="page" :page-size="50" :total="total" layout="prev, pager, next" :pager-count="5" small/>
        <div class="security-compose-footer"><div><strong>{{ selected.length }} acc đã chọn</strong><el-button v-if="selected.length" text size="small" @click="selected=[]">Bỏ chọn</el-button></div><el-button type="primary" :disabled="!selected.length || activeHistory" @click="dialog=true">Chọn thao tác…</el-button></div>
        <p class="security-note">Mỗi đợt tối đa 500 acc. Tiến độ lưu trên VPS; có thể đóng tab sau khi bắt đầu.</p>
      </el-card>
      <section class="security-history"><div class="security-history-heading"><strong>Tác vụ bảo mật</strong><el-button text @click="loadHistory">Tải lại</el-button></div><el-select v-if="history.length" :model-value="jobId" class="security-history-select" aria-label="Chọn tác vụ bảo mật" @update:model-value="id => router.push({ query: { ...route.query, job: id } })"><el-option v-for="job in history" :key="job.job_id" :value="job.job_id" :label="`${securityModeLabel(job.mode)} · ${job.total} acc · ${securityState(job.state)}`"/></el-select><AccountSecurityProgress v-if="jobId" :job-id="jobId" @created="created" @updated="updated"/><el-card v-else shadow="never"><el-empty description="Chưa có tác vụ. Chọn acc để bắt đầu." :image-size="80"/></el-card></section>
    </div>
    <AccountSecurityDialog v-model="dialog" :emails="selected" initial-mode="change_2fa" @created="created"/>
    <el-dialog append-to-body v-model="emailsOpen" title="Dán email từ kho" width="540px"><p>Chỉ nhận email đã có trong Quản lý acc, mỗi dòng một email.</p><el-input v-model="emailText" type="textarea" :rows="8" placeholder="email@example.com"/><template #footer><el-button @click="emailsOpen=false">Hủy</el-button><el-button type="primary" @click="useEmails">Chọn các email này</el-button></template></el-dialog>
    <el-dialog append-to-body v-model="importOpen" title="Nhập acc vào Quản lý acc" width="580px" @closed="importText=''"><el-alert type="info" :closable="false" title="Acc trùng email sẽ cập nhật thông tin trong kho."/><p>Định dạng email|mật khẩu|secret_2FA. Chưa thực hiện thay đổi trên ChatGPT.</p><el-input v-model="importText" type="textarea" :rows="8" autocomplete="off" placeholder="email@example.com|password|TOTP_SECRET"/><p v-if="importResult">{{ importResult }}</p><template #footer><el-button :disabled="importBusy" @click="importOpen=false">Đóng</el-button><el-button type="primary" :loading="importBusy" @click="doImport">Nhập và chọn acc</el-button></template></el-dialog>
  </div>
</template>
<style scoped>
.security-page{max-width:1640px;margin:0 auto}.security-page-heading{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:24px}.security-title{display:flex;align-items:center;gap:12px}.security-title>span{display:grid;place-items:center;width:44px;height:44px;border-radius:12px;background:var(--brand-bg);color:var(--brand);flex-shrink:0}.security-title h1{margin:0;font-size:23px;letter-spacing:-.5px;color:var(--app-title)}.security-title p{margin:7px 0 0;font-size:12px;line-height:1.6;color:var(--app-text-muted)}.security-layout{display:grid;grid-template-columns:minmax(300px,.8fr) minmax(0,1.4fr);gap:20px;align-items:start}.security-card-heading,.security-history-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;color:var(--app-title);font-size:14px}.security-card-heading>span{color:var(--app-text-muted);font-size:11px}.security-picker-tools{display:grid;gap:10px}.security-pick-actions{display:flex;flex-wrap:wrap;gap:3px;margin:12px 0}.security-pick-actions :deep(.el-button){margin:0;padding-inline:7px;font-size:11px}.security-picker{max-height:430px;overflow:auto;border:1px solid var(--app-border);border-radius:10px;margin-bottom:14px}.security-picker-row{display:flex;min-width:0;padding:10px 13px;border-bottom:1px solid var(--app-border-subtle)}.security-picker-row:last-child{border:0}.security-picker-row:hover{background:var(--app-card-hover)}.security-picker-row :deep(.el-checkbox){height:auto;width:100%;align-items:flex-start}.security-picker-row :deep(.el-checkbox__input){margin-top:3px}.security-picker-row :deep(.el-checkbox__label){min-width:0;flex:1;display:grid;gap:5px}.security-picker-email{font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.security-picker-folder{font-size:10px;color:var(--app-text-dim)}.security-compose-footer{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;border-top:1px solid var(--app-border);margin-top:18px;padding-top:16px;font-size:12px}.security-compose-footer>div{display:flex;align-items:center;gap:4px}.security-note{font-size:11px;color:var(--app-text-muted);line-height:1.7;margin:13px 0 0}.security-history-heading{margin:0 0 12px;min-height:28px}.security-history-select{width:100%;margin-bottom:12px}@media(max-width:1120px){.security-layout{grid-template-columns:1fr}.security-picker{max-height:320px}}@media(max-width:680px){.security-page-heading{align-items:flex-start;margin-bottom:18px}.security-title>span{display:none}.security-title h1{font-size:21px}.security-title p{font-size:11px}.security-page-heading :deep(.el-button){font-size:11px;padding:8px}.security-compose :deep(.el-card__body){padding:16px}.security-card-heading>span{max-width:45%;text-align:right}.security-picker-row{padding:11px}.security-compose-footer{align-items:stretch}.security-compose-footer>:last-child{flex:1}}
</style>
<style scoped>
.security-page,.security-compose,.security-history{min-width:0}.security-layout>*{min-width:0}
@media(max-width:1120px){.security-layout{grid-template-columns:minmax(0,1fr)}}
</style>
