<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useThemeStore } from '@/stores/theme'
import { usePrivacyStore } from '@/stores/privacy'
import { Eye, EyeOff } from 'lucide-vue-next'
import { useStatsStore } from '@/stores/stats'
import { useRuntimeStore } from '@/stores/runtime'
import { useI18nStore, LOCALES, t } from '@/stores/i18n'
import AppNavigation from '@/components/AppNavigation.vue'
import { mobileNavigation, matchesNavigation } from '@/navigation'
import { useTasksStore } from '@/stores/tasks'
const route = useRoute(), theme = useThemeStore(), statsStore = useStatsStore(), runtime = useRuntimeStore(), i18n = useI18nStore()
const { banner, autoStatus, streamConnected } = storeToRefs(runtime)
const collapse = ref(localStorage.getItem('nav_collapsed') === '1'), mobileDrawer = ref(false)
const currentLocale = computed(() => LOCALES.find((l) => l.code === i18n.locale) || LOCALES[0])
const tasks = useTasksStore()
const privacy = usePrivacyStore()
const state = computed(() => tasks.activeJobs.length || tasks.runs.length || runtime.runningSingle || autoStatus.value?.state === 'running' ? 'running' : tasks.error ? 'unknown' : autoStatus.value?.state === 'paused' ? 'paused' : tasks.updatedAt ? 'stopped' : 'loading')
const statusLabel = computed(() => t(({ running: '任务正在运行', unknown: '状态未确认', paused: '已暂停', stopped: '空闲', loading: '正在加载' })[state.value]))
const registrationPage = computed(() => ['/auto','/register'].includes(route.path))
const settingsPage = computed(() => route.path.startsWith('/settings/'))
const settingsTabs = [{path:'/settings/mail',label:'Email'},{path:'/settings/sms',label:'SMS'},{path:'/settings/export',label:'Tự động xuất'},{path:'/settings/fingerprint',label:'Môi trường'}]
watch(() => [i18n.locale, route.meta.title], () => { document.title = `${t(route.meta.title || '账户管理')} · GPT Reg` }, { immediate: true })
function focusContent() { document.getElementById('main-content')?.focus() }
function toggleSidebar() { collapse.value = !collapse.value; localStorage.setItem('nav_collapsed', collapse.value ? '1' : '0') }
onMounted(() => { theme.apply(); statsStore.startPolling(); runtime.connectAutoStream(); tasks.start() })
onUnmounted(() => { statsStore.stopPolling(); runtime.disconnectStreams(); tasks.stop() })
</script>

<template>
  <div class="app-frame" :class="{ 'sidebar-mini': collapse }">
    <a href="#main-content" class="skip-link" @click.prevent="focusContent">{{ t('跳转到内容') }}</a>
    <aside class="app-sidebar desktop-only">
      <router-link to="/" class="brand" aria-label="GPT Reg"><span class="brand-mark"><el-icon :size="18"><Database /></el-icon></span><span v-if="!collapse" class="brand-name">GPT Reg<span>Workspace</span></span></router-link>
      <AppNavigation :compact="collapse" @expand="toggleSidebar" />
      <div class="sidebar-foot" :title="streamConnected ? t('实时连接') : t('正在重连')"><span class="connection-dot" :class="{ connected: streamConnected }"></span><span v-if="!collapse">{{ streamConnected ? t('实时连接') : t('正在重连') }}</span></div>
    </aside>
    <div class="app-body">
      <header class="app-header">
        <div class="header-left">
          <button class="icon-button desktop-only" type="button" @click="toggleSidebar" :aria-label="collapse ? t('展开侧边栏') : t('收起侧边栏')" :aria-expanded="!collapse"><el-icon :size="18"><PanelLeftOpen v-if="collapse" /><PanelLeftClose v-else /></el-icon></button>
          <button class="icon-button mobile-only" type="button" @click="mobileDrawer = true" :aria-label="t('打开菜单')"><el-icon :size="20"><Menu /></el-icon></button>
          <span class="header-title">{{ t(route.meta.title) }}</span>
        </div>
        <div class="header-tools">
          <router-link to="/tasks" class="status-pill" :class="state" :title="t('任务中心')"><span class="connection-dot" :class="{ connected: state === 'running' }"></span>{{ statusLabel }}</router-link>
          <button class="icon-button" type="button" @click="theme.toggle" :aria-label="theme.dark ? t('浅色模式') : t('深色模式')"><el-icon :size="18"><Sun v-if="theme.dark" /><Moon v-else /></el-icon></button>
          <button class="icon-button privacy-toggle" type="button" @click="privacy.toggle" :aria-label="t(privacy.hidden ? 'Hiện khóa/OTP' : 'Che khóa/OTP')" :title="t('Che khóa/OTP trong danh sách và API UPI. Không che ô nhập, chi tiết hoặc dữ liệu xuất.')" :aria-pressed="privacy.hidden"><EyeOff v-if="privacy.hidden" :size="18" /><Eye v-else :size="18" /></button>
          <el-dropdown trigger="click" @command="i18n.setLocale">
            <button type="button" class="language-button" translate="no" :aria-label="currentLocale.label"><span>{{ currentLocale.code.toUpperCase() }}</span><el-icon :size="13"><ChevronDown /></el-icon></button>
            <template #dropdown><el-dropdown-menu translate="no"><el-dropdown-item v-for="locale in LOCALES" :key="locale.code" :command="locale.code" :disabled="locale.code === i18n.locale">{{ locale.label }}</el-dropdown-item></el-dropdown-menu></template>
          </el-dropdown>
        </div>
      </header>
      <main id="main-content" class="app-content" tabindex="-1">
        <el-alert v-if="banner" :title="banner" type="error" show-icon class="system-alert-banner" @close="runtime.dismissBanner" />
        <template v-if="settingsPage"><header class="workspace-page-heading"><h1>{{ t(route.meta.title) }}</h1><p>Thiết lập dùng chung cho các tác vụ trong workspace.</p></header><nav class="settings-section-tabs" aria-label="Nhóm cài đặt"><router-link v-for="tab in settingsTabs" :key="tab.path" :to="tab.path" :class="{active:route.path===tab.path}">{{ tab.label }}</router-link></nav></template>
        <nav v-if="registrationPage" class="workspace-mode-tabs" :aria-label="t('注册方式')"><router-link to="/auto" :class="{active:route.path === '/auto'}">{{ t('批量注册') }}</router-link><router-link to="/register" :class="{active:route.path === '/register'}">{{ t('单次注册') }}</router-link></nav>
        <router-view v-slot="{ Component }"><keep-alive><component :is="Component" /></keep-alive></router-view>
      </main>
    </div>
    <el-drawer v-model="mobileDrawer" direction="ltr" size="min(300px, 88vw)" :with-header="false" :aria-label="t('主导航')">
      <div class="drawer-content">
        <div class="drawer-header"><span class="brand-name">GPT Reg<span>Workspace</span></span><button class="icon-button" type="button" @click="mobileDrawer = false" :aria-label="t('关闭菜单')"><el-icon :size="20"><X /></el-icon></button></div>
        <AppNavigation @navigate="mobileDrawer = false" />
      </div>
    </el-drawer>
    <nav class="mobile-tabs mobile-only" :aria-label="t('快捷导航')">
      <router-link v-for="tab in mobileNavigation" :key="tab.path" :to="tab.path" class="mobile-tab" :class="{ active: matchesNavigation(tab,route.path) }" :aria-current="matchesNavigation(tab,route.path) ? 'page' : undefined"><el-icon :size="20"><component :is="tab.icon" /></el-icon><span>{{ t(tab.label) }}</span></router-link>
      <button type="button" class="mobile-tab" @click="mobileDrawer = true" :aria-expanded="mobileDrawer"><el-icon :size="20"><Menu /></el-icon><span>{{ t('菜单') }}</span></button>
    </nav>
  </div>
</template>

<style scoped>
.app-frame { min-height: 100dvh; color: var(--app-title); }
.app-sidebar { position: fixed; inset: 13px auto 13px 13px; z-index: 50; width: 233px; padding: 21px 13px; background: var(--app-sidebar-bg); border: 1px solid var(--app-border); border-radius: 21px; box-shadow: var(--app-shadow-md); -webkit-backdrop-filter: var(--glass-blur); backdrop-filter: var(--glass-blur); display: flex; flex-direction: column; }
.brand { display: flex; align-items: center; gap: 13px; padding: 0 8px 34px; text-decoration: none; }
.brand-mark { display: grid; place-items: center; width: 34px; height: 34px; border: 1px solid var(--app-border-hover); border-radius: 10px; color: var(--brand); background: linear-gradient(145deg, var(--glass-sheen), var(--brand-bg)); box-shadow: var(--app-shadow-xs); flex-shrink: 0; }
.brand-name { color: var(--app-title); font-size: 18px; font-weight: 600; letter-spacing: 0; white-space: nowrap; }
.brand-name > span { display: block; margin-top: 4px; font-size: 12px; font-weight: 400; letter-spacing: 0; color: var(--app-text-muted); }
.app-nav { display: flex; flex-direction: column; gap: 25px; flex: 1; overflow-y: auto; }
.nav-section { display: flex; flex-direction: column; gap: 4px; }
.nav-label { font-size: 10px; font-weight: 650; letter-spacing: .8px; text-transform: uppercase; color: var(--app-text-dim); padding: 0 12px 6px; }
.nav-link { min-height: 43px; padding: 9px 12px; display: flex; align-items: center; gap: 11px; font-size: 13px; font-weight: 500; text-decoration: none; color: var(--app-text-muted); border-radius: 10px; transition: background .15s, color .15s; white-space: nowrap; }
.nav-link:hover { background: var(--app-card-surface); color: var(--app-title); }.nav-link.active { background: var(--brand-bg); color: var(--brand); font-weight: 650; }.nav-link .el-icon { flex-shrink: 0; }
.sidebar-foot { display: flex; align-items: center; gap: 8px; padding: 16px 12px 0; margin-top: 20px; border-top: 1px solid var(--app-border); font-size: 11px; color: var(--app-text-muted); }
.connection-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--app-text-dim); flex-shrink: 0; }.connection-dot.connected { background: var(--color-success); }
.app-body { margin-left: 259px; min-width: 0; padding: 13px 13px 0 0; }
.app-header { position: sticky; top: 13px; z-index: 40; height: 55px; padding: 0 21px; display: flex; align-items: center; justify-content: space-between; gap: 13px; background: var(--app-header-bg); border: 1px solid var(--app-border); border-radius: 13px; box-shadow: var(--app-shadow-md); -webkit-backdrop-filter: var(--glass-blur); backdrop-filter: var(--glass-blur); }
.header-left, .header-tools { display: flex; align-items: center; gap: 12px; min-width: 0; }.header-title { font-size: 13px; font-weight: 550; color: var(--app-text-regular); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.icon-button { width: 34px; height: 34px; display: inline-flex; justify-content: center; align-items: center; flex-shrink: 0; border: 1px solid var(--app-border-subtle); border-radius: 13px; background: var(--app-card-surface); box-shadow: var(--app-shadow-xs); color: var(--app-text-muted); cursor: pointer; transition: transform .35s var(--workspace-spring), background .25s var(--workspace-ease), color .25s var(--workspace-ease), box-shadow .25s var(--workspace-ease); }.icon-button:hover { color: var(--app-title); background: var(--app-card-hover); border-color: var(--app-border-hover); }.icon-button:active { transform: translateY(1px) scale(.96); }
.status-pill { display: flex; align-items: center; gap: 7px; min-height: 34px; border: 1px solid var(--app-border); padding: 6px 10px; border-radius: 10px; font-size: 11px; color: var(--app-text-muted); text-decoration: none; white-space: nowrap; }.status-pill.running { color: var(--color-success); background: var(--color-success-bg); border-color: var(--color-success-border); }.status-pill.paused { color: var(--color-warning); }
.language-button { display: flex; align-items: center; gap: 6px; min-height: 34px; background: var(--app-card-surface); border: 1px solid var(--app-border); border-radius: 10px; font-size: 11px; font-weight: 600; color: var(--app-text-muted); cursor: pointer; padding: 8px; box-shadow: var(--app-shadow-xs); transition: background .25s var(--workspace-ease), color .25s var(--workspace-ease); }.language-button:hover { background: var(--app-card-hover); color: var(--app-title); }
.app-content { padding: 21px 21px 55px; max-width: 1600px; margin: 0 auto; outline: none; }.app-content:has(.registered-page) { max-width: none; padding: 21px; }.system-alert-banner { margin-bottom: 21px; }
.sidebar-mini .app-sidebar { width: 72px; padding-inline: 12px; }.sidebar-mini .app-body { margin-left: 98px; }.sidebar-mini .brand { padding-inline: 6px; }.sidebar-mini .nav-link { justify-content: center; padding-inline: 8px; }.sidebar-mini .sidebar-foot { justify-content: center; padding-inline: 0; }
.drawer-content { height: 100%; display: flex; flex-direction: column; }.drawer-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 28px; }.mobile-only { display: none; }
.skip-link { position: fixed; top: -80px; left: 16px; z-index: 3000; background: var(--brand); color: var(--brand-fg); padding: 12px; border-radius: 8px; }.skip-link:focus { top: 12px; }
.workspace-mode-tabs { display:flex;gap:4px;padding:4px;width:fit-content;max-width:100%;background:var(--app-card-surface);border:1px solid var(--app-border);border-radius:16px;margin-bottom:24px; }.workspace-mode-tabs a { padding:8px 16px;border:1px solid transparent;border-radius:12px;text-decoration:none;font-size:13px;color:var(--app-text-muted);transition:background .25s var(--workspace-ease),color .25s var(--workspace-ease),box-shadow .25s var(--workspace-ease); }.workspace-mode-tabs a.active { background:var(--app-card-hover);border-color:var(--app-border);box-shadow:var(--app-shadow-sm);color:var(--app-title);font-weight:500; }
@media (max-width: 900px) {
  .desktop-only { display: none; }.mobile-only { display: flex; }.app-body, .sidebar-mini .app-body { margin-left: 0; padding: 8px 8px 0; }.app-header { top: 8px; height: 56px; padding: 0 13px; }.app-content, .app-content:has(.registered-page) { padding: 24px 12px calc(100px + env(safe-area-inset-bottom, 0px)); }
  .mobile-tabs { position: fixed; inset: auto 8px 8px; z-index: 100; height: calc(64px + env(safe-area-inset-bottom, 0px)); padding: 5px 8px env(safe-area-inset-bottom, 0px); background: var(--app-sidebar-bg); border: 1px solid var(--app-border); border-radius: 21px; box-shadow: var(--app-shadow-md); -webkit-backdrop-filter: var(--glass-blur); backdrop-filter: var(--glass-blur); align-items: stretch; }
  .mobile-tab { flex: 1; display: flex; align-items: center; justify-content: center; flex-direction: column; gap: 5px; font: inherit; font-size: 10px; color: var(--app-text-muted); text-decoration: none; border: 0; background: transparent; cursor: pointer; }.mobile-tab.active { color: var(--brand); }
  .app-header .icon-button, .app-header .language-button, .app-header .status-pill { min-height: 44px; }
  .app-header .icon-button { width: 44px; height: 44px; }
}
@media (max-width: 480px) { .app-content, .app-content:has(.registered-page) { padding: 21px 4px calc(100px + env(safe-area-inset-bottom, 0px)); }.app-header { padding: 0 8px; }.header-left, .header-tools { gap: 4px; }.status-pill { padding: 4px 8px; font-size: 11px; }.header-title { max-width: 120px; font-size: 12px; } }
</style>
