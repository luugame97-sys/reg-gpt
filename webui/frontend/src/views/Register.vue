<script setup>
import { computed, onActivated, ref } from 'vue'
import { useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import { ElMessage } from 'element-plus'
import { startRegister, getRegistered, listRegisteredGroups } from '@/api/register'
import { listPoolGroups } from '@/api/accounts'
import { copyText } from '@/api/request'
import { useFormStore, proxyText } from '@/stores/form'
import { useProxyStore } from '@/stores/proxy'
import { useRuntimeStore } from '@/stores/runtime'
import { t } from '@/stores/i18n'
import LogPanel from '@/components/LogPanel.vue'

const route = useRoute()
const { form } = storeToRefs(useFormStore())
const { list: proxyList } = storeToRefs(useProxyStore())
// 同「注册结果」页：代理池上万条时 el-select 会把选项全量实例化，拖垮页面，
// 这里用虚拟滚动的 el-select-v2，只渲染可视区。
const proxyOptions = computed(() => proxyList.value.map((p) => ({ label: p, value: p })))
const runtime = useRuntimeStore()
const { runningSingle, lastRunResult } = storeToRefs(runtime)

const starting = ref(false)
const regEmail = ref('')
const targetGroup = ref('')
const availableGroups = ref([])

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

// 从「邮箱列表 → 使用」跳转过来时，带上指定邮箱
onActivated(() => {
  if (route.query.email) regEmail.value = String(route.query.email)
  loadGroups()
})

async function run() {
  starting.value = true
  runtime.clearLogs()
  lastRunResult.value = null
  try {
    const r = await startRegister({
      email: regEmail.value.trim() || null,
      proxy: proxyText(form.value),
      otp_timeout: Math.max(180, parseInt(form.value.otpTimeout, 10) || 180),
      want_access_token: true,
      want_session_token: true,
      want_refresh_token: form.value.wantRefreshToken,
      want_2fa: form.value.want2fa,
      target_group: targetGroup.value.trim(),
      engine: form.value.engine,
      browser_headless: form.value.browserHeadless,
    })
    runtime.addLog(`[client] 启动注册 run_id=${r.run_id} email=${r.email}`, 'evt')
    runtime.streamRun(r.run_id)
  } catch (e) {
    ElMessage.error(e.message)
    lastRunResult.value = { error: e.message }
  } finally {
    starting.value = false
  }
}

async function copyField(email, field) {
  try {
    const { data } = await getRegistered(email)
    const val = data[field] || ''
    if (!val) { ElMessage.warning(`${field} 为空`); return }
    await copyText(val)
  } catch (e) {
    ElMessage.error('加载凭证失败: ' + e.message)
  }
}
</script>

<template>
  <div class="page">
    <div class="page-heading"><div><div class="page-eyebrow">ĐĂNG KÝ</div><h1>Đăng ký đơn lẻ</h1><p>Tạo tài khoản, lưu thông tin và xác minh gói sau đăng ký.</p></div></div>
    <el-row :gutter="16">
      <el-col :md="10" style="margin-bottom: 16px">
        <el-card shadow="never">
          <template #header><span class="section-title" style="margin: 0">单次注册</span></template>
          <el-form label-position="top">
            <el-form-item label="注册引擎">
              <el-radio-group v-model="form.engine">
                <el-radio value="protocol">协议模式</el-radio>
                <el-radio value="browser">浏览器模式</el-radio>
              </el-radio-group>
              <div v-if="form.engine === 'browser'" style="margin-top: 8px; display: flex; align-items: center; gap: 10px">
                <el-switch v-model="form.browserHeadless" />
                <span>无头模式（不显示浏览器窗口）</span>
              </div>
            </el-form-item>
            <el-form-item label="邮箱">
              <el-input v-model="regEmail" placeholder="留空 = 自动选号 / 或填指定邮箱" clearable />
            </el-form-item>
            <el-form-item label="Nhóm · tùy chọn">
              <el-select
                v-model="targetGroup"
                filterable
                allow-create
                default-first-option
                clearable
                placeholder="Chọn nhóm có sẵn hoặc gõ tên nhóm mới..."
                style="width: 100%"
              >
                <el-option
                  v-for="g in availableGroups"
                  :key="g"
                  :label="g"
                  :value="g"
                />
              </el-select>

            </el-form-item>
            <el-form-item label="代理">
              <el-select-v2
                v-model="form.proxy" :options="proxyOptions" filterable clearable allow-create
                default-first-option :reserve-keyword="false"
                placeholder="socks5://user:pass@host:1080"
                style="width: 100%"
              />

            </el-form-item>
            <details class="help-details"><summary>Tùy chọn nâng cao</summary>
            <el-form-item label="OTP 等待秒数">
              <el-input-number v-model="form.otpTimeout" :min="180" :max="600" />
            </el-form-item>
            <el-form-item>
              <div style="display: flex; align-items: center; gap: 8px">
                <el-switch v-model="form.wantRefreshToken" />
                <span>要求获取 refresh token</span>
              </div>
            </el-form-item>
            <el-form-item>
              <div style="display: flex; align-items: center; gap: 10px">
                <el-switch v-model="form.want2fa" />
                <span>注册成功后自动绑定 2FA（TOTP）</span>
              </div>
              <p class="hint">Bật 2FA: hãy xuất và giữ mã bí mật để đăng nhập sau này.</p>
            </el-form-item>
            </details>
            <el-button type="primary" :loading="starting || runningSingle" @click="run">
              开始注册
            </el-button>
          </el-form>

          <el-alert
            v-if="lastRunResult && !lastRunResult.error"
            type="success" :closable="false" style="margin-top: 14px"
          >
            注册完成 {{ lastRunResult.email }}
            (access_token len={{ lastRunResult.access_token_len }}{{ lastRunResult.partial ? ', 部分凭证' : '' }})
            <div v-if="lastRunResult.password" class="cred-line">
              <span class="cred-label">密码</span><code class="cred-val">{{ lastRunResult.password }}</code>
            </div>
            <div v-else class="cred-line hint">本地未保存密码，请在官网确认或重置后更新凭证</div>
            <div v-if="lastRunResult.totp_secret" class="cred-line">
              <span class="cred-label">2FA</span><code class="cred-val">{{ lastRunResult.totp_secret }}</code>
              <span class="hint" style="margin-left: 6px">仅此一次！务必复制录入验证器</span>
            </div>
            <div v-if="lastRunResult.plus_trial_label" class="cred-line">
              <span class="cred-label">0元试用</span>
              <el-tag
                size="small"
                effect="plain"
                :type="lastRunResult.plus_trial_status === 'plus_eligible' ? 'success' : lastRunResult.plus_trial_status === 'plus_active' ? 'primary' : 'warning'"
              >
                {{ lastRunResult.plus_trial_label }}
              </el-tag>
            </div>
            <div style="margin-top: 8px">
              <el-button size="small" @click="copyText(lastRunResult.email)">复制邮箱</el-button>
              <template v-if="lastRunResult.password">
                <el-button size="small" type="primary" @click="copyText(lastRunResult.password)">复制密码</el-button>
                <el-button size="small" @click="copyText(lastRunResult.email + '----' + lastRunResult.password)">
                  复制 邮箱----密码
                </el-button>
              </template>
              <el-button v-if="lastRunResult.access_token_len > 0" size="small"
                         @click="copyField(lastRunResult.email, 'access_token')">复制 access_token</el-button>
              <el-button v-if="lastRunResult.totp_secret" size="small" type="warning"
                         @click="copyText(lastRunResult.totp_secret)">复制 2FA secret</el-button>
            </div>
          </el-alert>
          <el-alert
            v-else-if="lastRunResult && lastRunResult.error"
            type="error" :closable="false" style="margin-top: 14px" :title="lastRunResult.error"
          />
        </el-card>
      </el-col>

      <el-col :md="14" style="margin-bottom: 16px">
        <el-card shadow="never">
          <LogPanel />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>
