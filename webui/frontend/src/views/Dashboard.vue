<script setup>
import { localeTag } from '@/i18n/locale'
import { computed, onActivated, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useRouter } from 'vue-router'
import { useStatsStore } from '@/stores/stats'
import { useRuntimeStore } from '@/stores/runtime'
import { t } from '@/stores/i18n'
import LogPanel from '@/components/LogPanel.vue'
import { useTasksStore } from '@/stores/tasks'
import { getRegisteredOverview } from '@/api/register'
const router = useRouter(), statsStore = useStatsStore()
const tasks = useTasksStore(), accountOverview = ref(null), overviewError = ref('')
async function reloadOverview() {
  try { accountOverview.value = await getRegisteredOverview(); overviewError.value = '' }
  catch (_) { overviewError.value = 'Chưa tải được số liệu tài khoản.' }
}
function reload() { statsStore.refresh(); tasks.refresh(); reloadOverview() }
onActivated(reloadOverview)
const { stats, refreshing, updatedAt } = storeToRefs(statsStore)
const { autoStatus } = storeToRefs(useRuntimeStore())
const processed = computed(() => (stats.value.done ?? 0) + (stats.value.failed ?? 0))
const rate = computed(() => processed.value ? ((stats.value.done ?? 0) / processed.value * 100).toFixed(1) : '0.0')
const state = computed(() => tasks.activeJobs.length || tasks.runs.length || autoStatus.value?.state === 'running' ? 'running' : tasks.error ? 'unknown' : autoStatus.value?.state || 'stopped')
const autoStateLabel = computed(() => t(({running:'运行中',paused:'已暂停',stopped:'空闲'})[autoStatus.value?.state] || '正在加载'))
const stateLabel = computed(() => t(({ running: '运行中', paused: '已暂停', stopped: '空闲', unknown: '状态未确认' })[state.value] || state.value))
const metrics = computed(() => [
  { label: 'Tổng tài khoản', value: accountOverview.value?.total, icon: 'Users', tone: 'brand', path: '/registered' },
  { label: 'Có lỗi cần xem', value: accountOverview.value?.errors, icon: 'ShieldCheck', tone: 'warning', path: '/registered?view=errors' },
  { label: 'Gói trả phí đã xác minh', value: accountOverview.value?.paid, icon: 'CheckCircle2', tone: 'success', path: '/registered?view=paid' },
  { label: 'Tác vụ tài khoản đang chạy', value: tasks.updatedAt ? tasks.activeJobs.length : null, icon: 'Activity', tone: 'info', path: '/tasks' },
])
const shortcuts = [{ path: '/pool', icon: 'Mail', title: '邮箱列表', sub: '添加邮箱到号池' }, { path: '/registered', icon: 'Users', title: '账户管理', sub: '分组、检查与导出' }, { path: '/proxy', icon: 'Network', title: '代理池', sub: '连接与代理配置' }, { path: '/tasks', icon: 'Activity', title: '任务中心', sub: '查看任务与诊断' }]
</script>
<template>
  <div class="dashboard-page">
    <div class="page-heading"><div><h1>{{ t('总览') }}</h1><p>{{ t('资源、任务与运行状态') }}</p></div><div class="heading-actions"><button class="icon-button" type="button" @click="reload" :disabled="refreshing" :aria-label="t('刷新')"><el-icon :size="17" :class="{ 'is-loading': refreshing }"><Refresh /></el-icon></button><el-button type="primary" @click="router.push('/auto')"><el-icon><Play /></el-icon>Đăng ký</el-button></div></div>
    <el-alert v-if="overviewError" :title="overviewError" type="warning" :closable="false" />
    <section class="overview-banner"><div class="banner-icon"><el-icon :size="24"><Activity /></el-icon></div><div class="banner-copy"><h2>{{ state === 'running' ? t('任务正在运行') : state === 'paused' ? t('任务已暂停') : state === 'unknown' ? stateLabel : t('工作区已就绪') }}</h2><p>{{ t('号池可用') }} <strong>{{ stats.available ?? 0 }}</strong> · {{ t('配置并发') }} <strong>{{ autoStatus.concurrency ?? 1 }}</strong></p></div><span class="update-label">{{ updatedAt ? t('已更新') : t('正在加载') }}<span v-if="updatedAt"> {{ new Date(updatedAt).toLocaleTimeString(localeTag(), { hour: '2-digit', minute: '2-digit', hour12: false }) }}</span></span></section>
    <div class="metric-grid"><button v-for="metric in metrics" :key="metric.label" type="button" class="metric-tile" :class="metric.tone" @click="router.push(metric.path)"><div class="metric-top"><span>{{ metric.label }}</span></div><div class="metric-value">{{ metric.value == null ? '—' : metric.value.toLocaleString(localeTag()) }}</div><span class="metric-link">{{ t('查看详情') }} <span aria-hidden="true">↗</span></span></button></div>
    <div class="overview-grid">
      <section class="surface-panel"><div class="panel-heading"><h2>{{ t('号池处理情况') }}</h2><span class="soft-label">{{ t('总计') }} {{ stats.total ?? 0 }}</span></div><div class="success-overview"><strong>{{ rate }}<small>%</small></strong><span>{{ t('处理成功率') }}</span></div><div class="quality-bar" role="img" :aria-label="`${t('成功')} ${stats.done ?? 0}, ${t('失败')} ${stats.failed ?? 0}`"><span class="done" :style="{ width: processed ? rate + '%' : '0%' }"></span><span class="failed" :style="{ flex: processed && stats.failed ? 1 : 0 }"></span></div><div class="quality-legend"><span><i class="success-dot"></i>{{ t('成功') }} <b>{{ stats.done ?? 0 }}</b></span><span><i class="danger-dot"></i>{{ t('失败') }} <b>{{ stats.failed ?? 0 }}</b></span><span>{{ t('已处理') }} <b>{{ processed }}</b></span></div></section>
      <section class="surface-panel"><div class="panel-heading"><h2>Đăng ký hàng loạt</h2><span class="state-label" :class="autoStatus.state">{{ autoStateLabel }}</span></div><div class="session-metrics"><div><span>{{ t('成功') }}</span><strong>{{ autoStatus.registered_ok ?? 0 }}</strong></div><div><span>{{ t('失败') }}</span><strong>{{ autoStatus.registered_fail ?? 0 }}</strong></div><div><span>{{ t('目标数') }}</span><strong>{{ autoStatus.target_count || '∞' }}</strong></div></div><div class="panel-footer"><span>{{ autoStatus.target_count ? t('按目标数量执行') : t('未设置数量上限') }}</span><router-link to="/auto">{{ t('查看任务') }} <span aria-hidden="true">→</span></router-link></div></section>
    </div>
    <section class="quick-section"><h2>{{ t('快捷操作') }}</h2><div class="shortcut-grid"><router-link v-for="shortcut in shortcuts" :key="shortcut.path" :to="shortcut.path" class="shortcut"><el-icon :size="20"><component :is="shortcut.icon" /></el-icon><div><strong>{{ t(shortcut.title) }}</strong><span>{{ t(shortcut.sub) }}</span></div><span class="shortcut-arrow" aria-hidden="true">↗</span></router-link></div></section>
    <details class="surface-panel log-disclosure"><summary>{{ t('实时日志') }}<span>{{ t('展开查看') }}</span></summary><LogPanel /></details>
  </div>
</template>
<style scoped>
.dashboard-page { display: flex; flex-direction: column; gap: 21px; }
.dashboard-page .page-heading { margin: 0; }
.heading-actions { display: flex; gap: 8px; align-items: center; }
.icon-button { display: grid; place-items: center; width: 36px; height: 36px; border-radius: 8px; background: var(--app-card-bg); border: 1px solid var(--app-border); color: var(--app-text-muted); cursor: pointer; }
.overview-banner { display: flex; align-items: center; gap: 13px; padding: 13px 21px; background: var(--app-card-bg); border: 1px solid var(--app-border); border-radius: 21px; box-shadow: var(--app-shadow-sm); }
.banner-icon { display: grid; place-items: center; width: 36px; height: 36px; color: var(--app-text-muted); flex-shrink: 0; }
.banner-copy h2 { font-size: 14px; font-weight: 500; margin: 0 0 4px; }
.banner-copy p { color: var(--app-text-muted); font-size: 12px; margin: 0; }
.banner-copy strong { color: var(--app-title); font-weight: 500; }
.update-label { margin-left: auto; color: var(--app-text-muted); font-size: 12px; white-space: nowrap; }
.metric-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); border: 1px solid var(--app-border); border-radius: 21px; background: var(--app-card-bg); box-shadow: var(--app-shadow-sm); overflow: hidden; }
.metric-tile { font: inherit; text-align: left; min-width: 0; padding: 21px 34px; background: linear-gradient(145deg, var(--glass-sheen), transparent 70%); border: 0; border-right: 1px solid var(--app-border); color: var(--app-title); cursor: pointer; transition: background-color .25s var(--workspace-ease), box-shadow .25s var(--workspace-ease); }
.metric-tile:last-child { border-right: 0; }
.metric-tile:hover { background-color: var(--app-card-hover); box-shadow: inset 0 2px 0 var(--brand); }
.metric-top { font-size: 12px; line-height: 1.5; color: var(--app-text-muted); min-height: 36px; }
.metric-value { font-size: 32px; font-weight: 500; line-height: 1.2; margin: 8px 0 16px; letter-spacing: -.5px; }
.metric-link { display: flex; justify-content: space-between; color: var(--app-text-muted); font-size: 12px; }
.overview-grid { display: grid; grid-template-columns: minmax(0, 1.618fr) minmax(0, 1fr); gap: 21px; }
.surface-panel { background: var(--app-card-bg); border: 1px solid var(--app-border); border-radius: 21px; padding: 21px; min-width: 0; box-shadow: var(--app-shadow-sm); }
.panel-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
h2 { font-size: 14px; font-weight: 500; margin: 0; }
.soft-label, .state-label { font-size: 12px; color: var(--app-text-muted); }
.state-label { background: var(--app-card-surface); border-radius: 4px; padding: 4px 8px; }
.state-label.running { background: var(--color-success-bg); color: var(--color-success); }
.state-label.paused { color: var(--color-warning); }
.success-overview { display: flex; align-items: baseline; gap: 12px; margin: 32px 0 24px; }
.success-overview > strong { font-size: 40px; font-weight: 500; letter-spacing: -1px; }
.success-overview small { font-size: 20px; margin-left: 4px; color: var(--app-text-muted); }
.success-overview > span { font-size: 12px; color: var(--app-text-muted); }
.quality-bar { height: 8px; display: flex; background: var(--app-card-surface); overflow: hidden; border-radius: 4px; gap: 2px; }
.quality-bar .done { background: var(--color-success); border-radius: 4px; transition: width .5s var(--workspace-ease); }
.quality-bar .failed { background: var(--color-danger); border-radius: 4px; }
.quality-legend { display: flex; flex-wrap: wrap; gap: 16px; margin-top: 20px; color: var(--app-text-muted); font-size: 12px; }
.quality-legend > span { display: flex; gap: 8px; align-items: center; }
.quality-legend b { color: var(--app-title); font-weight: 500; }
.quality-legend i { width: 6px; height: 6px; border-radius: 50%; }
.success-dot { background: var(--color-success); }
.danger-dot { background: var(--color-danger); }
.session-metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 36px 0 28px; }
.session-metrics > div { display: flex; flex-direction: column; gap: 12px; padding-left: 16px; border-left: 1px solid var(--app-border); }
.session-metrics > div:first-child { padding-left: 0; border-left: 0; }
.session-metrics span { font-size: 12px; color: var(--app-text-muted); }
.session-metrics strong { font-size: 28px; font-weight: 500; }
.panel-footer { border-top: 1px solid var(--app-border); padding-top: 16px; display: flex; justify-content: space-between; gap: 8px; font-size: 12px; color: var(--app-text-muted); }
.panel-footer a { color: var(--brand); text-decoration: none; font-weight: 500; }
.quick-section > h2 { margin-bottom: 16px; }
.shortcut-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.shortcut { display: flex; align-items: center; gap: 13px; border: 1px solid var(--app-border); background: var(--glass-panel-bg); border-radius: 13px; padding: 13px; box-shadow: var(--app-shadow-sm); text-decoration: none; color: var(--app-text-muted); transition: transform .35s var(--workspace-spring), border-color .25s var(--workspace-ease), box-shadow .25s var(--workspace-ease); }
.shortcut:hover { border-color: var(--brand-border); box-shadow: 0 8px 21px var(--brand-glow), var(--app-shadow-xs); }
.shortcut > div { display: flex; flex-direction: column; min-width: 0; gap: 4px; }
.shortcut strong { font-size: 13px; font-weight: 500; color: var(--app-title); }
.shortcut div span { font-size: 11px; line-height: 1.5; }
.shortcut-arrow { margin-left: auto; color: var(--app-text-dim); transition: transform .35s var(--workspace-spring), color .25s var(--workspace-ease); }
.shortcut:hover .shortcut-arrow { color: var(--brand); transform: translate(2px, -2px); }
.log-disclosure { padding: 0; overflow: hidden; }
.log-disclosure summary { padding: 16px 20px; cursor: pointer; font-size: 13px; font-weight: 500; }
.log-disclosure summary > span { float: right; color: var(--app-text-muted); font-weight: 400; font-size: 12px; }
@media (hover: hover) and (pointer: fine) { .shortcut:hover { transform: translateY(-2px); } }
@media (max-width: 1200px) { .shortcut-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .metric-tile { padding: 20px; } }
@media (max-width: 680px) {
  .dashboard-page { gap: 20px; }
  .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .metric-tile { padding: 16px; }
  .metric-tile:nth-child(2) { border-right: 0; }
  .metric-tile:nth-child(-n+2) { border-bottom: 1px solid var(--app-border); }
  .metric-top { min-height: 36px; }
  .metric-value { font-size: 28px; margin-bottom: 12px; }
  .overview-grid { grid-template-columns: 1fr; gap: 16px; }
  .overview-banner { padding: 16px; gap: 12px; flex-wrap: wrap; }
  .banner-icon { display: none; }
  .update-label { width: 100%; margin: 0; font-size: 11px; }
  .surface-panel { padding: 20px; }
  .success-overview { margin: 24px 0; }
  .success-overview > strong { font-size: 36px; }
  .session-metrics { margin: 24px 0; }
  .quality-legend { gap: 12px; }
  .shortcut { padding: 16px 12px; gap: 8px; }
  .shortcut-arrow { display: none; }
  .log-disclosure { padding: 0; }
}
</style>
