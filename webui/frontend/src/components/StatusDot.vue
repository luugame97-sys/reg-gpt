<script setup>
defineProps({
  type: { type: String, default: 'info' }, // success/warning/danger/primary/info
  text: { type: [String, Number], default: '' },
})
const COLORS = {
  success: 'var(--color-success)',
  warning: 'var(--color-warning)',
  danger: 'var(--color-danger)',
  primary: 'var(--brand)',
  info: 'var(--app-text-muted)',
}
</script>

<template>
  <span class="status-dot">
    <i :style="{ background: COLORS[type] || COLORS.info }" />
    <span class="dot-text">{{ text }}</span>
  </span>
</template>

<style scoped>
.status-dot {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  white-space: nowrap;
}
.status-dot i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
  flex-shrink: 0;
}
.dot-text {
  color: var(--app-text-regular);
  font-size: 12px;
}
</style>
