<script setup>
import { computed, onActivated, onDeactivated, onBeforeUnmount, ref, watch } from 'vue'

const active = ref(false)
onDeactivated(() => { active.value = false })
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listAccounts, deleteAccount, bulkDeleteAccounts, resetFailed,
  resetAccount, bulkResetAccounts, releaseStale,
} from '@/api/accounts'
import { getMailProviders } from '@/api/settings'
import { copyText, fmtTime } from '@/api/request'
import { useStatsStore } from '@/stores/stats'
import { useRuntimeStore } from '@/stores/runtime'
import StatusDot from '@/components/StatusDot.vue'
import { useMobileView } from '@/useMobileView'
import { usePrivacyStore } from '@/stores/privacy'
const mobileView = useMobileView(), privacy = usePrivacyStore()

const router = useRouter()
const statsStore = useStatsStore()
const runtime = useRuntimeStore()
const { dataVersion } = storeToRefs(runtime)
const { stats } = storeToRefs(statsStore)

const PAGE_SIZES = [20, 50, 100, 200]
const pageSize = ref(20)
const rows = ref([])
const total = ref(0)
const page = ref(1)
const statusFilter = ref('')
const kindFilter = ref('')
const groupFilter = ref('all')
const poolGroups = ref([])
const keyword = ref('')
const bulkStatus = ref('')
const selected = ref([])
const loading = ref(false)
// 号池现在可以混放多种邮箱，这两个用来显示「来源」列和按来源过滤
const providers = ref([])
const byKind = ref({})

const STATUS_TYPE = { available: 'success', in_use: 'warning', done: 'primary', failed: 'danger' }
const STATUS_LABEL = {
  available: '可用', in_use: '进行中', done: '已完成', failed: '失败',
}

const summary = computed(() => [
  { label: '总计', value: stats.value.total, type: 'info' },
  { label: '可用', value: stats.value.available, type: 'success' },
  { label: '进行中', value: stats.value.in_use, type: 'warning' },
  { label: '已完成', value: stats.value.done, type: 'primary' },
  { label: '失败', value: stats.value.failed, type: 'danger' },
])

// 列表里只列池子里真有号的来源，免得下拉框塞一堆空选项
const kindOptions = computed(() =>
  providers.value
    .filter((p) => p.pooled && (byKind.value[p.kind]?.total || 0) > 0)
    .map((p) => ({
      kind: p.kind,
      label: p.display_name,
      count: byKind.value[p.kind]?.total || 0,
    })),
)

// 当前页没有失败/完成记录时就不占列宽，窄窗口也能把关键列排下
const hasFailReason = computed(() => rows.value.some((r) => (r.fail_reason || '').trim()))

function kindLabel(k) {
  return providers.value.find((p) => p.kind === k)?.display_name || k || 'outlook'
}

async function loadProviders() {
  try {
    providers.value = (await getMailProviders()).providers || []
  } catch (_) { /* 拿不到就退化成显示原始 kind 字符串 */ }
}

let loadSequence = 0
async function load(resetPage) {
  const sequence = ++loadSequence
  if (resetPage && page.value !== 1) { page.value = 1; return }
  loading.value = true
  try {
    const { items, total: t, by_kind, groups_summary } = await listAccounts({
      status: statusFilter.value,
      kind: kindFilter.value,
      group: groupFilter.value === 'all' ? '' : groupFilter.value,
      q: keyword.value.trim(),
      limit: pageSize.value,
      offset: (page.value - 1) * pageSize.value,
    })
    if (sequence !== loadSequence) return
    rows.value = items
    total.value = t
    byKind.value = by_kind || {}
    if (groups_summary?.groups) {
      poolGroups.value = groups_summary.groups
    }
  } catch (e) {
    if (sequence === loadSequence) ElMessage.error(e.message)
  } finally {
    if (sequence === loadSequence) loading.value = false
  }
}

function afterMutate() { load(); statsStore.refresh() }

function poolResult(result, message) {
  if (result.skipped_busy) ElMessage.warning(`${message} · Giữ lại ${result.skipped_busy} mail đang xử lý`)
  else ElMessage.success(message)
}

async function confirm(msg, title = '确认') {
  try { await ElMessageBox.confirm(msg, title, { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' }); return true }
  catch (_) { return false }
}

async function copyValue(text, label) {
  if (!text) { ElMessage.warning(`${label}为空`); return }
  try { await copyText(text); ElMessage.success(`已复制${label}`) }
  catch (_) { ElMessage.error('复制失败') }
}

async function resetFailedAll() {
  if (!(await confirm('把所有 failed 号重置为 available？'))) return
  try { const r = await resetFailed(); ElMessage.success(`重置 ${r.reset} 个`); afterMutate() }
  catch (e) { ElMessage.error(e.message) }
}
async function releaseStaleAll() {
  try { const r = await releaseStale(); ElMessage.success(`释放 ${r.released} 个卡死号`); afterMutate() }
  catch (e) { ElMessage.error(e.message) }
}
async function resetSelected() {
  const emails = selected.value.map((r) => r.email)
  if (!emails.length) return
  if (!(await confirm(`重置选中的 ${emails.length} 个号为 available？（已保存凭证不变）`))) return
  try { const r = await bulkResetAccounts(emails); poolResult(r, `已重置 ${r.reset} 个`); afterMutate() }
  catch (e) { ElMessage.error(e.message) }
}
async function deleteSelected() {
  const emails = selected.value.map((r) => r.email)
  if (!emails.length) return
  if (!(await confirm(`确定删除选中的 ${emails.length} 个号？(不可恢复)`))) return
  try { const r = await bulkDeleteAccounts({ emails }); poolResult(r, `已删除 ${r.deleted} 个`); afterMutate() }
  catch (e) { ElMessage.error(e.message) }
}
async function bulkDeleteByStatus() {
  if (!bulkStatus.value) { ElMessage.warning('请先选择要删除的状态'); return }
  const tip = bulkStatus.value === 'all'
    ? '这会删除邮箱列表里所有号（含未注册的），确定？'
    : `确定删除全部 ${bulkStatus.value} 状态的号？`
  if (!(await confirm(tip))) return
  try {
    const r = await bulkDeleteAccounts({ status: bulkStatus.value })
    poolResult(r, `已删除 ${r.deleted} 个 ${bulkStatus.value} 号`)
    bulkStatus.value = ''
    afterMutate()
  } catch (e) { ElMessage.error(e.message) }
}
function useAccount(row) {
  const email = typeof row === 'string' ? row : row.email
  router.push({ path: '/register', query: { email, kind: row.kind || undefined } })
}
async function resetOne(email) {
  if (!(await confirm(`重置 ${email} 为 available？`))) return
  try { await resetAccount(email); ElMessage.success('已重置'); afterMutate() }
  catch (e) { ElMessage.error(e.message) }
}
async function deleteOne(email) {
  if (!(await confirm(`删除 ${email}？`))) return
  try { await deleteAccount(email); ElMessage.success('已删除'); afterMutate() }
  catch (e) { ElMessage.error(e.message) }
}

let searchTimer = null
watch(keyword, () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => load(true), 350)
})
watch(page, () => load())
watch(pageSize, () => load(true))
watch(dataVersion, () => { if (active.value) load() })
onActivated(() => { active.value = true; load() })
onBeforeUnmount(() => { if (searchTimer) clearTimeout(searchTimer) })
loadProviders()
</script>
<template>
  <div class="page pool-page">
    <div class="page-heading"><div><h1>Kho mail</h1><p>Quản lý nguồn mail và trạng thái sử dụng.</p></div><el-button type="primary" @click="router.push('/import')"><el-icon><Plus /></el-icon>Nhập mail</el-button></div>
    <el-card shadow="never">
      <template #header>
        <div class="pool-head">
          <span class="section-title" style="margin: 0">邮箱列表</span>
          <span v-for="s in summary" :key="s.label" class="pool-count">{{ s.label }} <b>{{ s.value }}</b></span>
        </div>
      </template>

      <div class="toolbar">
        <el-input
          v-model="keyword" clearable placeholder="搜索邮箱或中转链接" class="kw"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="statusFilter" placeholder="全部状态" style="width: 132px" @change="load(true)">
          <el-option label="全部状态" value="" />
          <el-option label="可用 available" value="available" />
          <el-option label="进行中 in_use" value="in_use" />
          <el-option label="已完成 done" value="done" />
          <el-option label="失败 failed" value="failed" />
        </el-select>
        <!-- 号池混放多种邮箱时才有意义，只有一种来源就不显示 -->
        <el-select
          v-if="kindOptions.length > 1"
          v-model="kindFilter" placeholder="全部来源" style="width: 200px" @change="load(true)"
        >
          <el-option label="全部来源" value="" />
          <el-option
            v-for="o in kindOptions" :key="o.kind"
            :label="`${o.label} (${o.count})`" :value="o.kind"
          />
        </el-select>
        <!-- 分组筛选 -->
        <el-select v-model="groupFilter" placeholder="Tất cả nhóm mail" style="width: 150px" @change="load(true)">
          <el-option label="Tất cả nhóm mail" value="all" />
          <el-option label="Chưa phân nhóm" value="__ungrouped__" />
          <el-option
            v-for="g in poolGroups" :key="g.name"
            :label="`${g.name} (${g.total})`" :value="g.name"
          />
        </el-select>
        <el-button @click="load(false)"><el-icon><Refresh /></el-icon>刷新</el-button>
      </div>

      <details class="toolbar-disclosure"><summary>Quản lý hàng loạt · {{ selected.length }} đã chọn</summary><div class="toolbar">
        <el-button @click="resetFailedAll">重试 failed</el-button>
        <el-button @click="releaseStaleAll">释放卡死号</el-button>
        <el-button type="primary" plain :disabled="!selected.length" @click="resetSelected">
          重置选中 ({{ selected.length }})
        </el-button>
        <el-button type="danger" plain :disabled="!selected.length" @click="deleteSelected">
          删除选中 ({{ selected.length }})
        </el-button>
        <el-select v-model="bulkStatus" placeholder="— 按状态批量删 —" style="width: 176px">
          <el-option label="删全部 failed" value="failed" />
          <el-option label="删全部 done" value="done" />
          <el-option label="删全部 available" value="available" />
          <el-option label="删全部 in_use" value="in_use" />
          <el-option label="删全部（危险）" value="all" />
        </el-select>
        <el-button @click="bulkDeleteByStatus">执行</el-button>
        <div class="toolbar-gap" />
        <span class="hint">
          共 {{ total }} 条<span v-if="keyword.trim()">（搜索：{{ keyword.trim() }}）</span>
          <span v-if="selected.length">，已选 {{ selected.length }} 条</span>
        </span>
      </div></details>

      <el-skeleton v-if="loading && !rows.length" :rows="6" animated style="padding: 8px 0" />
      <el-table
        v-else
        v-loading="loading" :data="rows" size="small" stripe class="resource-table"
        row-key="email"
        @selection-change="(v) => (selected = v)"
      >
        <el-table-column type="selection" width="44" />
        <el-table-column v-if="mobileView" label="Tài khoản" min-width="210">
          <template #default="{ row }"><article class="resource-mobile-card">
            <strong class="mono" translate="no">{{ row.email }}</strong>
            <div class="resource-card-meta"><StatusDot :type="STATUS_TYPE[row.status] || 'info'" :text="STATUS_LABEL[row.status] || row.status" /><span>{{ kindLabel(row.kind) }}</span><el-button v-if="row.group_name" text @click="groupFilter = row.group_name; load(true)">{{ row.group_name }}</el-button></div>
            <p v-if="row.fail_reason" class="resource-card-error">{{ row.fail_reason }}</p>
            <p>Nhập {{ fmtTime(row.imported_at) }}<br v-if="row.finished_at" /><span v-if="row.finished_at">Hoàn tất {{ fmtTime(row.finished_at) }}</span></p>
            <details v-if="row.relay_url" class="resource-card-details"><summary>Link chuyển tiếp</summary><p class="mono" translate="no">{{ privacy.hidden ? '••••••••' : row.relay_url }}</p><el-button @click="copyValue(row.relay_url, '中转链接')">Sao chép link</el-button></details>
            <div class="resource-card-actions"><el-button @click="copyValue(row.email, '邮箱')">Sao chép</el-button><el-button @click="useAccount(row)">Sử dụng</el-button><el-button v-if="['done','failed','in_use'].includes(row.status)" @click="resetOne(row.email)">Đặt lại</el-button><el-button type="danger" plain @click="deleteOne(row.email)">Xóa</el-button></div>
          </article></template>
        </el-table-column>
        <template v-else>
        <el-table-column label="邮箱" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="mono">{{ row.email }}</span>
            <el-button size="small" text class="row-act" @click="copyValue(row.email, '邮箱')">复制</el-button>
          </template>
        </el-table-column>
        <el-table-column label="中转链接" min-width="190" show-overflow-tooltip>
          <template #default="{ row }">
            <template v-if="row.relay_url">
              <span class="mono dim">{{ privacy.hidden ? '••••••••' : row.relay_url }}</span>
              <el-button size="small" text class="row-act" @click="copyValue(row.relay_url, '中转链接')">复制</el-button>
            </template>
            <span v-else class="dim">-</span>
          </template>
        </el-table-column>
        <el-table-column v-if="kindOptions.length > 1" label="来源" width="130">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ kindLabel(row.kind) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="分组" min-width="130" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tag
              v-if="row.group_name"
              size="small"
              effect="plain"
              style="cursor: pointer"
              @click="groupFilter = row.group_name; load(true)"
            >
              {{ row.group_name }}
            </el-tag>
            <span v-else class="dim">—</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <StatusDot :type="STATUS_TYPE[row.status] || 'info'" :text="STATUS_LABEL[row.status] || row.status" />
          </template>
        </el-table-column>
        <el-table-column
          v-if="hasFailReason"
          prop="fail_reason" label="失败原因" min-width="150" show-overflow-tooltip
        >
          <template #default="{ row }">
            <span v-if="row.fail_reason">{{ row.fail_reason }}</span>
            <span v-else class="dim">-</span>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="152">
          <template #default="{ row }">
            <div class="time-cell">
              <span>导入 {{ fmtTime(row.imported_at) }}</span>
              <span v-if="row.finished_at" class="dim">完成 {{ fmtTime(row.finished_at) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text @click="useAccount(row)">使用</el-button>
            <el-button
              v-if="row.status === 'done' || row.status === 'failed' || row.status === 'in_use'"
              size="small" text type="primary" @click="resetOne(row.email)"
            >重置</el-button>
            <el-button size="small" text type="danger" @click="deleteOne(row.email)">删除</el-button>
          </template>
        </el-table-column>
        </template>
        <template #empty>
          <el-empty
            :description="keyword.trim() ? '没有匹配的邮箱，换个关键字试试' : '暂无数据，去「导入邮箱」添加接码号'"
            :image-size="70"
          />
        </template>
      </el-table>

      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="PAGE_SIZES"
          :total="total"
          :layout="mobileView ? 'total, prev, pager, next' : 'total, sizes, prev, pager, next, jumper'"
          :pager-count="5"
          background
        />
      </div>
    </el-card>
  </div>
</template>
<style scoped>
.pool-page :deep(.el-card__body) { padding-top: 12px; }
.page-heading { margin-bottom: 24px; }
.pool-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.pool-head .section-title { margin-right: auto !important; }
.pool-count { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; font-size: 12px; color: var(--app-text-muted); border-left: 1px solid var(--app-border); }
.pool-count b { color: var(--app-title); font-weight: 600; font-variant-numeric: tabular-nums; }
.toolbar {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  margin-bottom: 10px;
}
.toolbar-gap { flex: 1 1 auto; }
.kw { flex: 1 1 250px; max-width: 420px; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
.dim { color: var(--el-text-color-secondary); }
.time-cell { display: flex; flex-direction: column; line-height: 1.35; font-size: 12px; }
.time-cell .dim { font-size: 11px; }
.row-act { margin-left: 6px; padding: 0 4px; height: 18px; }
.pager {
  display: flex; justify-content: flex-end;
  margin-top: 12px; padding: 8px 0;
  background: var(--app-card-bg);
  border-top: 1px solid var(--el-border-color-lighter);
}
@media (max-width: 900px) {
  .kw { flex-basis: 100%; max-width: none; }
  .pager { justify-content: center; }
}
</style>
