<script setup>
defineProps({ traffic: { type: Object, default: null }, label: { type: String, default: 'Lưu lượng ước tính' } })
function bytes(value) {
  const n = Math.max(0, Number(value) || 0)
  if (n < 1024) return `${n} B`
  if (n < 1048576) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1048576).toFixed(2)} MB`
}
</script>
<template>
  <el-tooltip v-if="traffic" content="Ước tính dung lượng nội dung HTTP, gồm kiểm tra proxy và các lần thử lại được đo. Không gồm header, TCP/TLS; có thể khác lưu lượng tính cước proxy." placement="top">
    <span class="task-traffic"><span>{{ label }}:</span><strong>{{ bytes(Number(traffic.rx || 0) + Number(traffic.tx || 0)) }}</strong><span>↓ {{ bytes(traffic.rx) }}</span><span>↑ {{ bytes(traffic.tx) }}</span><span v-if="traffic.partial">· đo một phần</span></span>
  </el-tooltip>
</template>
<style scoped>
.task-traffic { display: inline-flex; align-items: center; gap: 5px 10px; flex-wrap: wrap; font-size: 12px; line-height: 1.6; color: var(--app-text-muted); font-variant-numeric: tabular-nums; }
.task-traffic strong { color: var(--app-title); font-weight: 600; }
</style>
