<script setup>
import { computed, onActivated, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { importAccounts, listPoolGroups } from '@/api/accounts'
import { listRegisteredGroups } from '@/api/register'
import { getMailProviders } from '@/api/settings'
import { useStatsStore } from '@/stores/stats'
import { useRuntimeStore } from '@/stores/runtime'
import { t } from '@/stores/i18n'

const statsStore = useStatsStore()
const runtime = useRuntimeStore()

const providers = ref([])
const kind = ref('')
const groupName = ref('')
const existingGroups = ref([])
const text = ref('')
const loading = ref(false)
const result = ref('')
const errors = ref([])

const current = computed(
  () => providers.value.find((p) => p.kind === kind.value) || null,
)

const lineCount = computed(
  () => text.value.split('\n').filter((l) => l.trim() && !l.trim().startsWith('#')).length,
)

async function loadProviders() {
  try {
    const r = await getMailProviders(true)
    providers.value = r.providers || []
    const cur = r.current
    kind.value = providers.value.some((p) => p.kind === cur)
      ? cur
      : (providers.value[0]?.kind || '')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function loadGroups() {
  try {
    const poolRes = await listPoolGroups()
    const regRes = await listRegisteredGroups()
    const set = new Set()
    if (poolRes?.groups && Array.isArray(poolRes.groups)) {
      poolRes.groups.forEach((g) => { if (g.name) set.add(g.name) })
    }
    if (regRes?.groups && Array.isArray(regRes.groups)) {
      regRes.groups.forEach((g) => { if (g.name) set.add(g.name) })
    }
    existingGroups.value = Array.from(set).sort()
  } catch (_) {}
}

onActivated(() => {
  loadProviders()
  loadGroups()
})

function selectGroup(name) {
  groupName.value = groupName.value === name ? '' : name
}

async function pasteClipboard() {
  try {
    const clip = await navigator.clipboard.readText()
    if (clip) {
      text.value = (text.value ? text.value + '\n' : '') + clip.trim()
      ElMessage.success('Đã dán từ clipboard')
    }
  } catch (_) {
    ElMessage.warning('Không thể đọc clipboard tự động, vui lòng nhấn Ctrl+V / Command+V')
  }
}

function clearText() {
  text.value = ''
  result.value = ''
  errors.value = []
}

async function doImport() {
  if (!text.value.trim()) {
    ElMessage.warning('Vui lòng nhập danh sách mail')
    return
  }
  if (!kind.value) {
    ElMessage.warning('Vui lòng chọn nguồn email')
    return
  }
  loading.value = true
  result.value = ''
  errors.value = []
  try {
    const r = await importAccounts(text.value.trim(), kind.value, groupName.value.trim())
    result.value = `Phân tích ${r.parsed} dòng: Thêm mới ${r.inserted}, Cập nhật ${r.updated}, Bỏ qua ${r.skipped}`
    if (groupName.value.trim()) {
      result.value += ` · Đã gán vào nhóm [${groupName.value.trim()}]`
    }
    ElMessage.success('Nhập email vào kho thành công!')
    text.value = ''
    statsStore.refresh()
    runtime.bumpData()
    loadGroups()
  } catch (e) {
    if (e.status === 422 && e.data?.errors?.length) {
      errors.value = e.data.errors
      result.value = `Có ${e.data.errors.length} dòng không hợp lệ, toàn bộ đợt nhập đã bị từ chối.`
      ElMessage.error('Định dạng không hợp lệ, vui lòng kiểm tra lại')
    } else {
      result.value = 'Lỗi nhập: ' + e.message
      ElMessage.error(e.message)
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="page import-page">
    <div class="page-heading"><div><div class="page-eyebrow">TÀI NGUYÊN</div><h1>Nhập kho mail</h1><p>Thêm nguồn mail để dùng cho các đợt đăng ký.</p></div><router-link to="/pool" class="workspace-back-link">Về kho mail ↗</router-link></div>
    <el-card shadow="never" class="import-card">
      <template #header>
        <div class="import-header">
          <div class="header-left">
            <span class="section-title">
              <el-icon :size="18" style="color: var(--brand)"><Upload /></el-icon>
              Nhập kho mail
            </span>
            <span class="hint"></span>
          </div>
        </div>
      </template>

      <!-- Settings Grid -->
      <div class="config-grid">
        <!-- Mail Provider -->
        <div class="config-item">
          <label class="field-label">
            <span>Nguồn Email</span>
            <span class="field-badge">{{ current?.line_segments || 4 }} đoạn</span>
          </label>
          <el-select v-model="kind" style="width: 100%" placeholder="Chọn nguồn email">
            <el-option
              v-for="p in providers"
              :key="p.kind"
              :label="p.display_name"
              :value="p.kind"
            />
          </el-select>
        </div>

        <!-- Target Group -->
        <div class="config-item">
          <label class="field-label">
            <span>Nhóm · tùy chọn</span>
            <span v-if="groupName" class="active-group-tag">Đang chọn: {{ groupName }}</span>
          </label>
          <el-select
            v-model="groupName"
            filterable
            allow-create
            default-first-option
            clearable
            placeholder="Chọn nhóm có sẵn hoặc gõ tên nhóm mới..."
            style="width: 100%"
          >
            <template #prefix>
              <el-icon><Folder /></el-icon>
            </template>
            <el-option
              v-for="g in existingGroups"
              :key="g"
              :label="g"
              :value="g"
            />
          </el-select>

        </div>
      </div>

      <!-- Format Hint Box -->
      <div v-if="current" class="format-hint-card">
        <div class="hint-icon"><el-icon><InfoFilled /></el-icon></div>
        <div class="hint-text">
          <div class="hint-title">Định dạng (ngăn cách bằng <code>----</code>):</div>
          <code class="format-code">{{ (current.import_hint || '').replaceAll('中转链接', t('Link chuyển tiếp')) }}</code>
        </div>
      </div>

      <!-- Input Area -->
      <div class="editor-wrap">
        <div class="editor-toolbar">
          <div class="toolbar-left">
            <span class="count-badge" :class="{ active: lineCount > 0 }">
              {{ lineCount }} dòng
            </span>
          </div>
          <div class="toolbar-right">
            <el-button size="small" text @click="pasteClipboard">
              <el-icon><DocumentCopy /></el-icon> Dán clipboard
            </el-button>
            <el-button size="small" text :disabled="!text" @click="clearText">
              <el-icon><Delete /></el-icon> Xóa sạch
            </el-button>
          </div>
        </div>

        <el-input
          v-model="text"
          type="textarea"
          :rows="9"
          class="import-textarea mono"
          :placeholder="current?.import_placeholder || 'Dán danh sách mail vào đây...'"
        />
      </div>

      <!-- Action Bar -->
      <div class="action-footer">
        <el-button
          type="primary"
          size="large"
          class="submit-btn"
          :loading="loading"
          :disabled="!lineCount"
          @click="doImport"
        >
          <el-icon v-if="!loading" style="margin-right: 6px"><Check /></el-icon>
          Nhập vào kho
        </el-button>
        <span v-if="result" class="result-feedback">{{ result }}</span>
      </div>

      <!-- Error List -->
      <el-alert
        v-if="errors.length"
        type="error"
        :closable="true"
        show-icon
        class="error-alert-box"
        title="Các dòng lỗi sau cần được chỉnh sửa trước khi nhập:"
        @close="errors = []"
      >
        <ul class="err-list">
          <li v-for="e in errors" :key="e.line">
            <b>Dòng {{ e.line }}:</b> {{ e.error }}
          </li>
        </ul>
      </el-alert>
    </el-card>
  </div>
</template>

<style scoped>
.import-page {
  max-width: 1100px;
}

.import-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.config-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--app-title);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.field-badge {
  font-size: 11px;
  font-weight: 500;
  padding: 2px 7px;
  border-radius: 4px;
  background: var(--el-fill-color-light);
  color: var(--app-text-muted);
}

.active-group-tag {
  font-size: 11px;
  font-weight: 600;
  color: var(--brand);
}

.quick-groups {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  flex-wrap: wrap;
}

.quick-label {
  font-size: 11.5px;
  color: var(--app-text-muted);
}

.pills-scroll {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.group-pill {
  font-size: 11.5px;
  padding: 2px 9px;
  border-radius: 12px;
  background: var(--el-fill-color-light);
  border: 1px solid var(--app-border);
  color: var(--app-title);
  cursor: pointer;
  user-select: none;
  transition: all 0.15s ease;
}

.group-pill:hover {
  border-color: var(--brand);
  color: var(--brand);
}

.group-pill.selected {
  background: var(--brand);
  border-color: var(--brand);
  color: #fff;
  font-weight: 600;
}

.format-hint-card {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
  border: 1px solid var(--app-border);
  margin-bottom: 16px;
}

.hint-icon {
  color: var(--brand);
  font-size: 16px;
  margin-top: 2px;
}

.hint-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--app-title);
  margin-bottom: 3px;
}

.format-code {
  font-size: 12px;
  color: var(--el-color-primary);
  word-break: break-all;
}

.editor-wrap {
  border: 1px solid var(--app-border);
  border-radius: 10px;
  overflow: hidden;
  background: var(--app-card-bg);
}

.editor-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: var(--el-fill-color-lighter);
  border-bottom: 1px solid var(--app-border);
}

.count-badge {
  font-size: 12px;
  font-weight: 600;
  color: var(--app-text-muted);
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--el-fill-color);
}

.count-badge.active {
  color: var(--brand);
  background: var(--el-color-primary-light-9);
}

.import-textarea :deep(.el-textarea__inner) {
  border: none !important;
  box-shadow: none !important;
  padding: 12px;
  font-size: 12.5px;
  line-height: 1.6;
  border-radius: 0;
}

.action-footer {
  margin-top: 16px;
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.submit-btn {
  padding: 0 24px;
  height: 42px;
  font-size: 14px;
  font-weight: 600;
}

.result-feedback {
  font-size: 13px;
  color: var(--app-title);
  font-weight: 500;
}

.error-alert-box {
  margin-top: 16px;
  border-radius: 8px;
}

.err-list {
  margin: 6px 0 0;
  padding-left: 18px;
  max-height: 220px;
  overflow-y: auto;
  line-height: 1.7;
}

@media (max-width: 768px) {
  .config-grid {
    grid-template-columns: 1fr;
  }
  .submit-btn {
    width: 100%;
  }
}
</style>

<style scoped>
.config-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }.format-hint-card { padding: 12px 14px; }.format-code { overflow-wrap: anywhere; }.action-footer { flex-wrap: wrap; gap: 12px; }@media(max-width: 600px) { .config-grid { grid-template-columns: 1fr; }.format-code { font-size: 11px; } }
</style>
