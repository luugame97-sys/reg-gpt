<script setup>
import { computed, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useProxyStore, isValidProxy, proxyScheme } from '@/stores/proxy'
import { testProxies } from '@/api/proxy'
import { copyText } from '@/api/request'
import { useMobileView } from '@/useMobileView'
import { usePrivacyStore } from '@/stores/privacy'
const mobileView = useMobileView(), privacy = usePrivacyStore()
const importExpanded = ref(false)

const proxyStore = useProxyStore()
const { list, count, serverReady, saveState, saveError } = storeToRefs(proxyStore)
const syncBusy = computed(() => ['loading', 'saving'].includes(saveState.value))
const syncLabel = computed(() => ({loading:'Đang tải từ server…',pending:'Có thay đổi chưa lưu',saving:'Đang lưu lên server…',saved:'Đã lưu và xác nhận trên server',error:'Chưa đồng bộ với server'})[saveState.value])

const draft = ref('')
const testResults = ref({}) // proxy -> { status:'testing'|'ok'|'fail', latency_ms, ip, error }
const testingAll = ref(false)

// 代理池可能上万条，列表只渲染当前页，避免几千行 DOM 卡死页面
const page = ref(1)
const pageSize = ref(50)
const keyword = ref('')
const PAGE_SIZES = [50, 100, 200, 500]
const MAX_BULK_TEST = 200

const rows = computed(() =>
  list.value.map((p, i) => ({
    index: i + 1, proxy: p, valid: isValidProxy(p), result: testResults.value[p] || null,
  })),
)
const filteredRows = computed(() => {
  const kw = keyword.value.trim()
  return kw ? rows.value.filter((r) => r.proxy.includes(kw)) : rows.value
})
const pagedRows = computed(() =>
  filteredRows.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value),
)
const invalidCount = computed(() => rows.value.filter((r) => !r.valid).length)
watch([keyword, pageSize], () => { page.value = 1 })

async function runTest(targets) {
  if (!targets.length) return
  for (const p of targets) testResults.value[p] = { status: 'testing' }
  try {
    const { results } = await testProxies(targets)
    for (const [proxy, res] of Object.entries(results)) {
      testResults.value[proxy] = { status: res.ok ? 'ok' : 'fail', ...res }
    }
  } catch (e) {
    for (const p of targets) testResults.value[p] = { status: 'fail', error: e.message }
    ElMessage.error('测试失败: ' + e.message)
  }
}
async function testOne(proxy) {
  await runTest([proxy])
}
async function testAll() {
  if (!count.value) return
  let targets = [...list.value]
  if (targets.length > MAX_BULK_TEST) {
    try {
      await ElMessageBox.confirm(
        `代理池有 ${targets.length} 个，单次最多测 ${MAX_BULK_TEST} 个（每批 20 并发）。只测前 ${MAX_BULK_TEST} 个？`,
        '确认', { type: 'warning', confirmButtonText: `测试前 ${MAX_BULK_TEST}`, cancelButtonText: '取消' },
      )
    } catch (_) { return }
    targets = targets.slice(0, MAX_BULK_TEST)
  }
  testingAll.value = true
  try { await runTest(targets) }
  finally { testingAll.value = false }
}

async function reloadFromServer() {
  try {
    await proxyStore.loadFromServer()
    ElMessage.success(`已从服务端同步（${count.value} 个）`)
  } catch (e) { ElMessage.error(e.message) }
}

async function retrySave() {
  try { await proxyStore.persist(); ElMessage.success('Đã lưu và xác nhận trên server') }
  catch (e) { ElMessage.error(e.message) }
}

async function save() {
  if (!draft.value.trim()) { ElMessage.warning('请先粘贴代理'); return }
  if (count.value) {
    try { await ElMessageBox.confirm(`Thay toàn bộ ${count.value} proxy hiện tại bằng danh sách vừa nhập?`, 'Thay kho proxy', {type:'warning',confirmButtonText:'Thay danh sách',cancelButtonText:'Hủy'}) }
    catch { return }
  }
  const r = proxyStore.setFromText(draft.value)
  try {
    await proxyStore.persist()
    draft.value = ''
    ElMessage.success(`已保存 ${r.kept} 个代理${r.duplicated ? `（去重 ${r.duplicated} 个）` : ''}`)
  } catch (e) { ElMessage.error(e.message) }
}
async function append() {
  if (!draft.value.trim()) { ElMessage.warning('请先粘贴代理'); return }
  const r = proxyStore.append(draft.value)
  try {
    await proxyStore.persist()
    draft.value = ''
    ElMessage.success(`已追加 ${r.added} 个新代理`)
  } catch (e) { ElMessage.error(e.message) }
}
async function clearAll() {
  if (!count.value) return
  try {
    await ElMessageBox.confirm(`确定清空全部 ${count.value} 个代理？`, '确认', { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' })
    proxyStore.clear()
    await proxyStore.persist()
    ElMessage.success('已清空')
  } catch (e) { if (e instanceof Error) ElMessage.error(e.message) }
}
async function removeOne(proxy) {
  proxyStore.remove(proxy)
  try { await proxyStore.persist(); ElMessage.success('Đã lưu và xác nhận trên server') }
  catch (e) { ElMessage.error(e.message) }
}
function editInDraft() {
  importExpanded.value = true
  draft.value = proxyStore.text
  ElMessage.info('已把当前代理池载入编辑框，改完点「覆盖保存」')
}
</script>

<template>
  <div class="page proxy-page">
    <div class="page-heading"><div><div class="page-eyebrow">TÀI NGUYÊN</div><h1>Kho proxy</h1><p>Quản lý kết nối dùng cho đăng ký và tác vụ tài khoản.</p></div><el-tag effect="plain">{{ count.toLocaleString('vi-VN') }} proxy</el-tag></div>
    <div class="proxy-sync-status" role="status" style="margin-bottom:16px;display:flex;align-items:center;gap:10px;flex-wrap:wrap">
      <el-tag :type="saveState === 'saved' ? 'success' : saveState === 'error' ? 'danger' : 'warning'">{{ syncLabel }}</el-tag>
      <span v-if="saveError" class="hint">{{ saveError }}</span>
      <el-button v-if="serverReady && ['error','pending'].includes(saveState)" size="small" @click="retrySave">Thử lưu lại</el-button>
      <el-button v-if="!serverReady && saveState === 'error'" size="small" @click="reloadFromServer">Tải lại từ server</el-button>
    </div>
    <el-row :gutter="16">
      <el-col :md="importExpanded || !count ? 10 : 24" style="margin-bottom: 16px">
        <el-card shadow="never" :class="{ 'resource-import-collapsed': count && !importExpanded }">
          <template #header><div class="resource-section-heading"><span class="section-title" style="margin: 0">批量导入</span><el-button :disabled="!count" :aria-expanded="importExpanded || !count" aria-controls="proxy-import-body" @click="importExpanded = !importExpanded">{{ importExpanded || !count ? 'Thu gọn' : 'Mở nhập proxy' }}</el-button></div></template>
          <div v-show="importExpanded || !count" id="proxy-import-body">
          <details class="help-details"><summary>Định dạng proxy</summary>
          <p class="hint">
            每行一个：<span class="mono">[协议://][user:pass@]host:port</span>，也支持 <span class="mono">host:port:user:pass</span><br />
            不写协议默认按 <b>HTTP 代理</b>；SOCKS5 必须写 <span class="mono">socks5://</span>。<br />
            四段供应商格式会自动规范化为 <span class="mono">socks5h://user:pass@host:port</span>。
          </p>          </details>

          <el-input
            v-model="draft" type="textarea" :rows="9" class="mono"
            placeholder="socks5://127.0.0.1:7890&#10;socks5://user:pass@1.2.3.4:1080&#10;http://5.6.7.8:8080"
          />
          <div style="margin-top: 12px; display: flex; gap: 8px; flex-wrap: wrap">
            <el-button type="primary" :disabled="!serverReady || syncBusy" @click="append">Thêm vào kho</el-button>
            <el-button :disabled="!serverReady || syncBusy" @click="save">Thay toàn bộ kho…</el-button>
            <el-button text @click="editInDraft">Sửa danh sách hiện tại</el-button>
          </div>
          </div>
        </el-card>
      </el-col>

      <el-col :md="importExpanded || !count ? 14 : 24" style="margin-bottom: 16px">
        <el-card shadow="never">
          <template #header>
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap">
              <span class="section-title" style="margin: 0">
                Danh sách proxy · {{ count }}<template v-if="invalidCount"> · <span style="color: var(--el-color-danger)">{{ invalidCount }} sai định dạng</span></template>
              </span>
              <div style="display: flex; gap: 6px; flex-wrap: wrap">
                <el-button size="small" type="primary" plain :loading="testingAll" :disabled="!count" @click="testAll">测试全部</el-button>
                <el-button size="small" :disabled="!count" @click="copyText(proxyStore.text)">复制全部</el-button>
                <el-button size="small" :disabled="syncBusy" @click="reloadFromServer">同步服务端</el-button>
                <el-button size="small" type="danger" plain :disabled="!count || !serverReady || syncBusy" @click="clearAll">清空</el-button>
              </div>
            </div>
          </template>

          <el-input
            v-model="keyword" clearable placeholder="搜索代理（域名 / sid / 出口）" size="small"
            style="margin-bottom: 10px; max-width: 320px"
          />

          <el-table :data="pagedRows" size="small" stripe :max-height="mobileView ? undefined : 440" class="resource-table">
            <el-table-column v-if="mobileView" label="Proxy" min-width="220">
              <template #default="{ row }"><article class="resource-mobile-card">
                <strong class="mono" translate="no">{{ privacy.hidden ? '••••••••' : row.proxy }}</strong>
                <div class="resource-card-meta"><span>#{{ row.index }} · {{ proxyScheme(row.proxy) }}</span><el-tag :type="row.valid ? 'success' : 'danger'">{{ row.valid ? 'Đúng định dạng' : 'Sai định dạng' }}</el-tag></div>
                <p v-if="!row.result">Chưa kiểm tra kết nối</p><p v-else-if="row.result.status === 'testing'">Đang kiểm tra…</p><p v-else-if="row.result.status === 'ok'">Kết nối tốt · {{ row.result.latency_ms }}ms · <span translate="no">{{ row.result.ip }}</span></p><p v-else class="resource-card-error">{{ row.result.error || 'Kết nối thất bại' }}</p>
                <div class="resource-card-actions"><el-button :loading="row.result?.status === 'testing'" @click="testOne(row.proxy)">Kiểm tra</el-button><el-button type="danger" plain :disabled="!serverReady || syncBusy" @click="removeOne(row.proxy)">Xóa</el-button></div>
              </article></template>
            </el-table-column>
            <template v-else>
            <el-table-column prop="index" label="#" width="48" />
            <el-table-column prop="proxy" label="代理地址" min-width="200" show-overflow-tooltip>
              <template #default="{ row }"><span class="mono">{{ privacy.hidden ? '••••••••' : row.proxy }}</span></template>
            </el-table-column>
            <el-table-column label="格式" width="70">
              <template #default="{ row }">
                <el-tag :type="row.valid ? 'success' : 'danger'" size="small" effect="light">
                  {{ row.valid ? '正常' : '异常' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="生效协议" width="110">
              <template #default="{ row }">
                <span class="mono" style="font-size: 12px">{{ proxyScheme(row.proxy) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="连通性" min-width="150">
              <template #default="{ row }">
                <template v-if="!row.result">
                  <span class="hint">未测</span>
                </template>
                <el-tag v-else-if="row.result.status === 'testing'" type="warning" size="small">测试中…</el-tag>
                <template v-else-if="row.result.status === 'ok'">
                  <el-tag type="success" size="small">正常 {{ row.result.latency_ms }}ms</el-tag>
                  <span v-if="row.result.ip" class="hint mono" style="margin-left: 6px">{{ row.result.ip }}</span>
                </template>
                <el-tooltip v-else :content="row.result.error || '连接失败'" placement="top">
                  <el-tag type="danger" size="small">失败</el-tag>
                </el-tooltip>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button
                  size="small" text type="primary"
                  :loading="row.result && row.result.status === 'testing'"
                  @click="testOne(row.proxy)"
                >测试</el-button>
                <el-button size="small" text type="danger" :disabled="!serverReady || syncBusy" @click="removeOne(row.proxy)">删除</el-button>
              </template>
            </el-table-column>
            </template>
            <template #empty>Chưa có proxy. Mở phần Nhập hàng loạt để thêm.</template>
          </el-table>

          <div style="display: flex; justify-content: flex-end; margin-top: 10px">
            <el-pagination
              v-model:current-page="page"
              v-model:page-size="pageSize"
              :page-sizes="PAGE_SIZES"
              :total="filteredRows.length"
              :layout="mobileView ? 'total, prev, pager, next' : 'total, sizes, prev, pager, next, jumper'"
              :pager-count="5"
              background
              small
            />
          </div>

          <el-alert
            type="info" :closable="false" show-icon style="margin-top: 12px"
            title="Proxy được lưu để chọn trong các tác vụ. Bấm Kiểm tra khi cần xác nhận kết nối."
          />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>
