<script setup>
import { computed, onActivated, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { ElMessage } from 'element-plus'
import { autoStart, autoPause, autoResume, autoStop } from '@/api/register'
import {
  mailSupplyStatus, saveMailSupply, refillMailSupply, importMailOrders,
  listRegisteredGroups,
} from '@/api/register'
import { listPoolGroups } from '@/api/accounts'
import { useFormStore, proxyText } from '@/stores/form'
import { useProxyStore } from '@/stores/proxy'
import { useRuntimeStore } from '@/stores/runtime'
import LogPanel from '@/components/LogPanel.vue'
import StatusDot from '@/components/StatusDot.vue'
import { t } from '@/stores/i18n'

const router = useRouter()
const { form } = storeToRefs(useFormStore())
const proxyStore = useProxyStore()
const { count: proxyCount } = storeToRefs(proxyStore)
const runtime = useRuntimeStore()
const { autoStatus } = storeToRefs(runtime)
const workerLimit = computed(() => form.value.autoEngine === 'browser' ? 20 : 100)
watch(workerLimit, limit => { form.value.autoConcurrency = Math.max(1, Math.min(limit, Number(form.value.autoConcurrency) || 1)) })

const filterGroup = ref('all')
const targetGroup = ref('')
const availableGroups = ref([])

// ── 自动供号（ReMail）：池子低于阈值时自动下单买新邮箱 ──
const supply = ref({ config: {}, available: 0, balance: '', active_orders: 0, usable_orders: 0 })
const supplyBusy = ref(false)

async function loadGroups() {
  try {
    const p = await listPoolGroups()
    const r = await listRegisteredGroups()
    const set = new Set()
    if (p?.groups && Array.isArray(p.groups)) p.groups.forEach((g) => { if (g.name) set.add(g.name) })
    if (r?.groups && Array.isArray(r.groups)) r.groups.forEach((g) => { if (g.name) set.add(g.name) })
    availableGroups.value = Array.from(set).sort()
  } catch (_) {}
}

async function loadSupply() {
  try {
    supply.value = await mailSupplyStatus()
  } catch (_) { /* 后端没起或没配置时静默 */ }
}

async function saveSupply() {
  supplyBusy.value = true
  try {
    const cfg = supply.value.config || {}
    supply.value = await saveMailSupply({
      api_key: cfg.api_key,
      project_id: cfg.project_id,
      email_suffix: cfg.email_suffix,
      auto_buy: cfg.auto_buy,
      batch_size: cfg.batch_size,
      min_available: cfg.min_available,
    })
    ElMessage.success('自动供号配置已保存')
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.response?.data?.detail || e.message))
  } finally { supplyBusy.value = false }
}

async function doRefill() {
  supplyBusy.value = true
  try {
    const r = await refillMailSupply()
    ElMessage.success(`补货完成：买入 ${r.bought || 0} 个，可用 ${r.available}`)
    await loadSupply()
  } catch (e) {
    ElMessage.error('补货失败: ' + (e.response?.data?.detail || e.message))
  } finally { supplyBusy.value = false }
}

async function doImportOrders() {
  supplyBusy.value = true
  try {
    const r = await importMailOrders()
    ElMessage.success(`已购订单导入：新增 ${r.inserted || 0} 个，可用 ${r.stats?.available ?? '?'}`)
    await loadSupply()
  } catch (e) {
    ElMessage.error('导入失败: ' + (e.response?.data?.detail || e.message))
  } finally { supplyBusy.value = false }
}

onActivated(() => {
  loadSupply()
  loadGroups()
})

const st = computed(() => autoStatus.value.state || 'stopped')
const canStart = computed(() => st.value === 'stopped')
const canPause = computed(() => st.value === 'running')
const canResume = computed(() => st.value === 'paused')
const canStop = computed(() => st.value !== 'stopped')

const stateLabel = computed(() => ({
  stopped: '未运行', running: '运行中', paused: '已暂停',
}[st.value] || st.value))
const stateType = computed(() => ({
  stopped: 'info', running: 'success', paused: 'warning',
}[st.value] || 'info'))

const workers = computed(() => Array.isArray(autoStatus.value.workers) ? autoStatus.value.workers : [])

async function start() {
  try {
    await autoStart({
      proxy: proxyText(form.value),
      proxy_pool: proxyStore.text,
      concurrency: parseInt(form.value.autoConcurrency, 10) || 1,
      otp_timeout: Math.max(180, parseInt(form.value.otpTimeout, 10) || 180),
      want_access_token: true,
      want_session_token: true,
      want_refresh_token: form.value.wantRefreshToken,
      cool_down_seconds: parseFloat(form.value.autoCoolDown) || 0,
      target_count: parseInt(form.value.autoTargetCount, 10) || 0,
      filter_group: filterGroup.value === 'all' ? '' : filterGroup.value,
      target_group: targetGroup.value.trim(),
      // 批量默认绑 2FA（后端默认是 false，这个字段以前压根没传，
      // 所以批量跑出来的号一个都没 2FA）。留开关是因为绑定不可逆。
      want_2fa: form.value.autoWant2fa,
      engine: form.value.autoEngine,
    })
    ElMessage.success('自动跑号已启动')
  } catch (e) { ElMessage.error('启动失败: ' + e.message) }
}
async function call(fn, name) {
  try { await fn(); ElMessage.success(name + ' 成功') }
  catch (e) { ElMessage.error(name + ' 失败: ' + e.message) }
}
</script>

<template>
  <div class="page auto-page">
    <div class="page-heading"><div><div class="page-eyebrow">ĐĂNG KÝ</div><h1>Đăng ký hàng loạt</h1><p>Thiết lập đợt chạy và thư mục lưu tài khoản.</p></div><StatusDot :type="stateType" :text="stateLabel" /></div>
    <div class="auto-grid">
      <el-card shadow="never" class="task-card">
        <template #header><span class="section-title" style="margin: 0">{{ t('任务设置') }}</span></template>
        <div class="task-fields">
          <el-form-item :label="t('并发')"><el-input-number v-model="form.autoConcurrency" :min="1" :max="workerLimit" aria-label="Số worker đăng ký" /><span class="hint">{{ form.autoEngine === 'browser' ? '1–20 · Trình duyệt dùng nhiều RAM, nên bắt đầu với 5 luồng.' : '1–100 · Tăng dần theo khả năng proxy và VPS.' }}</span></el-form-item>
          <el-form-item label="Mục tiêu"><el-input-number v-model="form.autoTargetCount" :min="0" :max="100000" aria-label="Mục tiêu đăng ký" /><span class="hint">0 = không giới hạn</span></el-form-item>
          <el-form-item :label="t('源分组')"><el-select v-model="filterGroup"><el-option label="Tất cả nhóm" value="all" /><el-option label="Chưa phân nhóm" value="__ungrouped__" /><el-option v-for="g in availableGroups" :key="g" :label="g" :value="g" /></el-select></el-form-item>
          <el-form-item :label="t('目标分组')"><el-select v-model="targetGroup" filterable allow-create default-first-option clearable placeholder="Kế thừa nhóm nguồn"><el-option v-for="g in availableGroups" :key="g" :label="g" :value="g" /></el-select></el-form-item>
        </div>
        <div class="proxy-summary"><span><el-icon><Network /></el-icon>{{ proxyCount }} proxy</span><el-button text @click="router.push('/proxy')">{{ t('管理代理池') }} ↗</el-button></div>
        <details class="help-details advanced-settings"><summary>{{ t('高级选项') }}</summary>
          <el-form label-position="top">
            <el-form-item :label="t('注册引擎')"><el-radio-group v-model="form.autoEngine"><el-radio value="protocol">{{ t('协议模式') }}</el-radio><el-radio value="browser">{{ t('浏览器模式') }}</el-radio></el-radio-group></el-form-item>
            <el-alert v-if="form.autoEngine === 'browser'" type="warning" :closable="false" title="Chế độ trình duyệt dùng nhiều RAM. Nên chạy tối đa 5 luồng." style="margin-bottom: 16px" />
            <div class="task-fields"><el-form-item :label="t('冷却(秒)')"><el-input-number v-model="form.autoCoolDown" :min="0" :max="120" /></el-form-item><el-form-item :label="t('OTP 等待(秒)')"><el-input-number v-model="form.otpTimeout" :min="180" :max="600" /></el-form-item></div>
            <el-form-item label="2FA"><el-switch v-model="form.autoWant2fa" /><span style="margin-left: 10px">Tự động gắn TOTP</span><p class="hint">{{ t('绑定后请导出保存 2FA 密钥。后续登录需要动态码。') }}</p></el-form-item>
            <el-form-item label="Refresh token"><el-switch v-model="form.wantRefreshToken" /><span class="hint" style="margin-left: 10px">{{ t('开启后作为完成必需项') }}</span></el-form-item>
          </el-form>
        </details>
        <div class="task-actions"><el-button type="primary" :disabled="!canStart" @click="start"><el-icon><Play /></el-icon>{{ t('开始') }}</el-button><el-button v-if="canPause" @click="call(autoPause, '暂停')">{{ t('暂停') }}</el-button><el-button v-if="canResume" @click="call(autoResume, '恢复')">{{ t('恢复') }}</el-button><el-button type="danger" :disabled="!canStop" @click="call(autoStop, '停止')">{{ t('停止') }}</el-button></div>
      </el-card>
      <el-card shadow="never" class="session-card">
        <template #header><span class="section-title" style="margin: 0">{{ t('当前会话') }}</span></template>
        <div class="session-stats"><div><span>{{ t('成功') }}</span><strong class="success">{{ autoStatus.registered_ok ?? 0 }}</strong></div><div><span>{{ t('失败') }}</span><strong>{{ autoStatus.registered_fail ?? 0 }}</strong></div><div><span>{{ t('并发') }}</span><strong>{{ autoStatus.concurrency ?? 1 }}</strong></div></div>
        <div v-if="workers.length" class="worker-list"><el-tag v-for="w in workers" :key="w.id" type="info" effect="plain">#{{ w.id }} · {{ w.email }}</el-tag></div>
        <p v-if="autoStatus.last_message" class="hint">{{ autoStatus.last_message }}</p>
        <p v-else class="hint">{{ t('未运行') }}</p>
      </el-card>
    </div>
    <details class="supply-disclosure">
      <summary><span>ReMail · Tự động bổ sung mail</span><el-tag :type="supply.config?.auto_buy ? 'warning' : 'info'" size="small">{{ supply.config?.auto_buy ? 'Tự mua: Bật' : 'Tự mua: Tắt' }}</el-tag></summary>
      <div class="supply-body"><el-form label-position="top">
        <el-form-item label="API Key"><el-input v-model="supply.config.api_key" type="password" show-password class="mono" :placeholder="supply.config.api_key_set ? 'Đã lưu khóa · để trống để giữ nguyên' : 'Chưa cấu hình ReMail API Key'" autocomplete="new-password" /></el-form-item>
        <div class="task-fields"><el-form-item label="Số lượng mỗi đợt"><el-input-number v-model="supply.config.batch_size" :min="2" :max="100" /></el-form-item><el-form-item label="Bổ sung khi còn ít hơn"><el-input-number v-model="supply.config.min_available" :min="0" :max="1000" /></el-form-item></div>
        <el-form-item label="Tự động mua"><el-switch v-model="supply.config.auto_buy" /><span class="hint" style="margin-left: 12px">Bật sẽ tự trừ số dư khi bổ sung.</span></el-form-item>
        <div class="supply-summary">Số dư: <b>{{ supply.balance ?? '—' }}</b> · Khả dụng: <b>{{ supply.available ?? 0 }}</b> · Đơn dùng được: <b>{{ supply.usable_orders ?? 0 }} / {{ supply.active_orders ?? 0 }}</b></div>
        <div class="toolbar-block"><el-button type="primary" :loading="supplyBusy" @click="saveSupply">{{ t('保存') }}</el-button><el-button :loading="supplyBusy" @click="doImportOrders">Nhập đơn đã mua</el-button><el-button type="warning" :loading="supplyBusy" @click="doRefill">Mua bổ sung · trừ số dư</el-button><el-button @click="loadSupply">{{ t('刷新') }}</el-button></div>
        <p class="hint">Mail đã mua cần sử dụng trong thời hạn nhận thư của nhà cung cấp.</p>
      </el-form></div>
    </details>
    <el-card shadow="never"><LogPanel /></el-card>
  </div>
</template>
<style scoped>
.task-fields :deep(.el-form-item__content) { display:flex; flex-direction:column; align-items:stretch; justify-content:flex-start; gap:6px; }
.page-heading { margin-bottom: 24px; }.auto-grid { display: grid; grid-template-columns: 1.4fr 1fr; gap: 20px; align-items: start; }.task-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 20px; }.task-fields :deep(.el-form-item) { display: flex; flex-direction: column; align-items: stretch; }.task-fields :deep(.el-form-item__label) { justify-content: flex-start; }.task-fields :deep(.el-input-number) { width: 100%; }.proxy-summary { display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: var(--app-text-muted); border-top: 1px solid var(--app-border); padding-top: 12px; }.proxy-summary > span { display: flex; align-items: center; gap: 8px; }.task-actions { display: flex; gap: 10px; padding-top: 12px; }.advanced-settings { background: var(--app-card-surface); }.session-stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 15px; padding: 4px 0 16px; border-bottom: 1px solid var(--app-border); }.session-stats > div { display: flex; flex-direction: column; gap: 14px; }.session-stats span { font-size: 12px; color: var(--app-text-muted); }.session-stats strong { font-size: 30px; font-weight: 600; }.session-stats .success { color: var(--color-success); }.worker-list { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 16px; }.supply-disclosure { margin: 0 0 20px; background: var(--app-card-bg); border: 1px solid var(--app-border); border-radius: 12px; }.supply-disclosure summary { cursor: pointer; padding: 18px; font-size: 13px; font-weight: 550; }.supply-disclosure summary > .el-tag { margin-left: 12px; }.supply-body { padding: 0 20px 20px; max-width: 800px; }.supply-summary { font-size: 12px; color: var(--app-text-muted); margin-bottom: 16px; }
@media (max-width: 1100px) { .auto-grid { grid-template-columns: 1fr; gap: 0; } }@media (max-width: 480px) { .task-fields { gap: 0 12px; }.supply-disclosure summary > .el-tag { margin-top: 8px; }.supply-body { padding: 0 14px 14px; } }
</style>
