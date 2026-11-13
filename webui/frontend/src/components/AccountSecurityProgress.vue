<script setup>
import { computed, onActivated, onDeactivated, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getSecurityJob, stopSecurityJob, resumeSecurityJob, getSecurityRecovery } from '@/api/security'
import { exportRegistered } from '@/api/register'
import { securityActive, securityModeLabel, securityState, securityRequestId } from '@/accountSecurity'
import { fmtTime } from '@/api/request'

const props = defineProps({ jobId: { type: String, default: '' } })
const emit = defineEmits(['updated', 'created'])
const job = ref(null), page = ref(1), error = ref(''), busy = ref(false)
let timer, sequence = 0, disposed = false, active = true
const running = computed(() => securityActive(job.value))
const succeeded = computed(() => job.value?.counts?.succeeded || 0)
const attention = computed(() => (job.value?.counts?.attention || 0) + (job.value?.counts?.interrupted || 0))
async function load() {
  clearTimeout(timer)
  if (!props.jobId || disposed || !active) return
  const seq = ++sequence
  try {
    const result = await getSecurityJob(props.jobId, { offset: (page.value - 1) * 50, limit: 50 })
    if (seq !== sequence || disposed) return
    job.value = result.job; error.value = ''; emit('updated', result.job)
  } catch (e) { if (seq === sequence) error.value = e.message }
  if (seq === sequence && !disposed && (running.value || error.value)) timer = setTimeout(load, 2000)
}
watch(() => props.jobId, () => { job.value = null; page.value = 1; load() }, { immediate: true })
watch(page, load)
onBeforeUnmount(() => { disposed = true; sequence++; clearTimeout(timer) })
onDeactivated(() => { active = false; sequence++; clearTimeout(timer) })
onActivated(() => { if (!active) { active = true; load() } })
async function stop() {
  busy.value = true
  try { await stopSecurityJob(props.jobId); await load() }
  catch (e) { ElMessage.error(e.message) }
  finally { busy.value = false }
}
async function resume(row) {
  try {
    const { value: proxy } = await ElMessageBox.prompt('Tiếp tục xác minh từ checkpoint. Nhập lại URL proxy nếu lần trước dùng proxy; để trống để kết nối trực tiếp.', 'Tiếp tục xác minh', { inputType: 'password', confirmButtonText: 'Tiếp tục', cancelButtonText: 'Hủy' })
    busy.value = true
    const { job: next } = await resumeSecurityJob(props.jobId, { email: row.email, proxy, confirmed: true, request_id: securityRequestId() })
    emit('created', next)
  } catch (e) { if (e?.message) ElMessage.error(e.message) }
  finally { busy.value = false }
}
function download(text, filename, type) {
  const url = URL.createObjectURL(new Blob([text], { type }))
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = filename; anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
async function exportResult(recovery = false) {
  busy.value = true
  try {
    if (recovery) {
      await ElMessageBox.confirm('File chứa mật khẩu và secret 2FA dự kiến/đã xác nhận. Giữ riêng để khôi phục khi cần.', 'Tải checkpoint bảo mật', { confirmButtonText: 'Tải file', cancelButtonText: 'Hủy', type: 'warning' })
      const data = await getSecurityRecovery(props.jobId)
      download(JSON.stringify(data, null, 2), `security-checkpoint-${props.jobId.slice(0, 8)}.json`, 'application/json')
    } else {
      const emails = []
      for (let offset = 0; offset < job.value.total; offset += 100) {
        const { job: part } = await getSecurityJob(props.jobId, { offset, limit: 100 })
        emails.push(...part.items.filter(row => row.state === 'succeeded').map(row => row.email))
      }
      if (!emails.length) return ElMessage.info('Chưa có tài khoản thành công để xuất.')
      const result = await exportRegistered({ emails, format: 'email_pw_2fa' })
      download(result.text || result.content || '', `security-result-${props.jobId.slice(0, 8)}.txt`, 'text/plain;charset=utf-8')
    }
  } catch (e) { if (e?.message) ElMessage.error(e.message) }
  finally { busy.value = false }
}
</script>
<template>
  <el-card v-if="jobId" shadow="never" class="security-progress">
    <div class="security-progress-heading"><div><strong>{{ securityModeLabel(job?.mode) }}</strong><p v-if="job">{{ fmtTime(job.created_at) }} · {{ securityState(job.state) }}</p></div><el-button :loading="busy" @click="load">Tải lại</el-button><el-button v-if="running" :loading="busy" :disabled="job?.state === 'stopping'" @click="stop">Dừng sau acc đang chạy</el-button></div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon/>
    <template v-if="job">
      <div class="security-counts"><span>{{ job.completed }}/{{ job.total }} đã xử lý</span><span class="security-success">{{ succeeded }} thành công</span><span>{{ job.counts.failed || 0 }} lỗi</span><span v-if="attention" class="security-attention">{{ attention }} cần xác minh</span><span v-if="job.counts.cancelled">{{ job.counts.cancelled }} chưa thực hiện</span></div>
      <el-progress :percentage="job.total ? Math.round(job.completed / job.total * 100) : 0" :show-text="false"/>
      <el-table :data="job.items" row-key="email" max-height="420" class="security-results" :empty-text="'Đang tải kết quả…'"><el-table-column prop="email" label="Tài khoản" min-width="225"/><el-table-column label="Trạng thái" width="140"><template #default="{ row }"><el-tag :type="row.state === 'succeeded' ? 'success' : ['failed','attention','interrupted'].includes(row.state) ? 'warning' : 'info'">{{ securityState(row.state) }}</el-tag></template></el-table-column><el-table-column prop="message" label="Kết quả / bước hiện tại" min-width="240"/><el-table-column label="Thao tác" width="170"><template #default="{ row }"><el-button v-if="row.has_checkpoint && ['attention','interrupted'].includes(row.state)" text :disabled="running || busy" @click="resume(row)">Tiếp tục xác minh</el-button></template></el-table-column></el-table>
      <div class="security-progress-footer"><el-pagination v-model:current-page="page" layout="prev, pager, next" :pager-count="5" :page-size="50" :total="job.total" small/><div><el-button :disabled="running || busy || !succeeded" @click="exportResult()">Xuất acc thành công</el-button><el-button :disabled="running || busy" @click="exportResult(true)">Tải checkpoint</el-button></div></div>
    </template>
  </el-card>
</template>
<style scoped>
.security-progress-heading{display:flex;align-items:center;flex-wrap:wrap;gap:8px}.security-progress-heading>div{flex:1;min-width:180px}.security-progress-heading strong{color:var(--app-title);font-size:15px}.security-progress-heading p{color:var(--app-text-muted);font-size:12px;margin:7px 0 0}.security-counts{display:flex;flex-wrap:wrap;gap:10px 20px;margin:20px 0 12px;font-size:12px;color:var(--app-text-muted)}.security-success{color:var(--color-success)}.security-attention{color:var(--color-warning)}.security-results{margin-top:18px}.security-progress-footer{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:14px;margin-top:16px}.security-progress-footer>div{display:flex;gap:6px;flex-wrap:wrap}.security-progress-footer :deep(.el-button){margin:0}@media(max-width:680px){.security-progress :deep(.el-card__body){padding:16px}.security-progress-heading :deep(.el-button){font-size:11px;padding:7px}.security-progress-footer>div{width:100%}}
</style>
<style scoped>
.security-progress{min-width:0;max-width:100%}
</style>
