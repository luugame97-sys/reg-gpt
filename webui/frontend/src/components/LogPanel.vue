<script setup>
import { nextTick, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRuntimeStore } from '@/stores/runtime'
import { t } from '@/stores/i18n'

const runtime = useRuntimeStore()
const { logs } = storeToRefs(runtime)
const boxRef = ref(null)
const follow = ref(true)
function onScroll() {
  const el = boxRef.value
  if (el) follow.value = el.scrollHeight - el.scrollTop - el.clientHeight < 48
}

// Tự động cuộn xuống cuối khi có log mới
watch(
  () => logs.value.at(-1)?.id,
  async () => {
    await nextTick()
    const el = boxRef.value
    if (el && follow.value) el.scrollTop = el.scrollHeight
  },
)
</script>

<template>
  <div class="log-wrap">
    <div class="log-head">
      <div class="log-title-wrap">
        <el-icon :size="15" style="color: var(--brand)"><Terminal /></el-icon>
        <span class="log-title">{{ t('实时日志', 'Nhật ký Hoạt động Thời gian thực') }}</span>
      </div>
      <div class="log-actions">
        <button type="button" class="log-btn" @click="runtime.clearLogs" :title="t('清空日志', 'Xóa nhật ký')">
          <el-icon :size="12"><Trash2 /></el-icon>
          <span>{{ t('清空', 'Xóa nhật ký') }}</span>
        </button>
      </div>
    </div>
    <div ref="boxRef" class="log-box" @scroll="onScroll">
      <div v-for="l in logs" :key="l.id" class="line" :class="l.kind">{{ l.text }}</div>
      <div v-if="!logs.length" class="line empty-log">
        {{ t('等待日志输出…', 'Đang chờ luồng worker xuất nhật ký hoạt động…') }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.log-wrap {
  padding: 14px 16px;
}
.log-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.log-title-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}
.log-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--app-title);
}
.log-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}
.log-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 24px;
  padding: 0 8px;
  border-radius: 5px;
  font-size: 11px;
  font-weight: 500;
  border: 1px solid var(--app-border);
  background: var(--app-card-surface);
  color: var(--app-text-muted);
  cursor: pointer;
  transition: all 0.15s ease;
}
.log-btn:hover {
  background: var(--app-card-hover);
  border-color: var(--app-border-hover);
  color: var(--app-title);
}
.empty-log {
  color: var(--app-text-dim);
  font-style: italic;
}
</style>
