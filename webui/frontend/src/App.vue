<script setup>
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useI18nStore, t } from '@/stores/i18n'
import { useThemeStore } from '@/stores/theme'
import AdminLayout from '@/layouts/AdminLayout.vue'
import WebLogin from '@/components/WebLogin.vue'
import { AUTH_REQUIRED_EVENT, webAuthRequest } from '@/webAuth'

const i18n = useI18nStore()
const { elLocale } = storeToRefs(i18n)
const theme = useThemeStore()
const checking = ref(true), failed = ref(false), authenticated = ref(false), enabled = ref(false), expired = ref(false)
function signedIn(session) {
  enabled.value = session.enabled
  authenticated.value = session.authenticated
  expired.value = false
}
async function checkSession() {
  checking.value = true
  failed.value = false
  try {
    const session = await webAuthRequest('session')
    if (typeof session.authenticated !== 'boolean' || typeof session.enabled !== 'boolean') throw new Error('Invalid session response')
    signedIn(session)
  } catch (_) {
    failed.value = true
  } finally {
    checking.value = false
  }
}
function requireLogin() { authenticated.value = false; expired.value = true }
watch(() => [authenticated.value, i18n.locale], () => {
  if (!authenticated.value) document.title = `${t('Đăng nhập')} · GPT Reg`
}, { immediate: true })
onMounted(() => { theme.apply(); window.addEventListener(AUTH_REQUIRED_EVENT, requireLogin); checkSession() })
onUnmounted(() => window.removeEventListener(AUTH_REQUIRED_EVENT, requireLogin))
</script>

<template>
  <el-config-provider :locale="elLocale">
    <div v-if="checking || failed" class="session-check" role="status">
      <p>{{ t(failed ? 'Không kết nối được trang đăng nhập. Vui lòng thử lại.' : 'Đang kiểm tra phiên đăng nhập…') }}</p>
      <button v-if="failed" type="button" @click="checkSession">{{ t('Thử lại') }}</button>
    </div>
    <WebLogin v-else-if="!authenticated" :expired="expired" @signed-in="signedIn" />
    <AdminLayout v-else :show-logout="enabled" />
  </el-config-provider>
</template>

<style scoped>
.session-check { min-height: 100dvh; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 24px; text-align: center; color: var(--app-text-regular); }
.session-check button { min-height: 44px; padding: 10px 24px; border: 1px solid var(--app-border-hover); border-radius: 10px; background: var(--brand); color: var(--brand-fg); font: inherit; cursor: pointer; }
.session-check button:focus-visible { outline: 2px solid var(--brand); outline-offset: 3px; }
</style>
