<script setup>
import { computed, nextTick, onUnmounted, ref } from 'vue'
import { ArrowRight, Eye, EyeOff, LoaderCircle, ShieldCheck, Sun, Moon } from 'lucide-vue-next'
import { useI18nStore, LOCALES, t } from '@/stores/i18n'
import { useThemeStore } from '@/stores/theme'
import { webAuthRequest } from '@/webAuth'

defineProps({ expired: Boolean })
const emit = defineEmits(['signed-in'])
const i18n = useI18nStore(), theme = useThemeStore()
const username = ref(''), password = ref(''), visible = ref(false), busy = ref(false)
const error = ref(''), errorBox = ref(null), retryAt = ref(0), now = ref(Date.now())
const remaining = computed(() => Math.max(0, Math.ceil((retryAt.value - now.value) / 1000)))
let timer
const messages = {
  web_auth_invalid_credentials: 'Tài khoản hoặc mật khẩu chưa đúng.',
  web_auth_invalid_input: 'Vui lòng nhập đầy đủ tài khoản và mật khẩu hợp lệ.',
  web_auth_rate_limited: 'Bạn đã thử đăng nhập quá nhiều lần. Vui lòng chờ rồi thử lại.',
  web_auth_https_required: 'Hãy mở trang bằng HTTPS để đăng nhập.',
  web_auth_cross_origin: 'Hãy tải lại trang rồi thử đăng nhập lại.',
}
async function submit() {
  if (busy.value || remaining.value) return
  busy.value = true
  error.value = ''
  try {
    await webAuthRequest('login', { username: username.value, password: password.value })
    const session = await webAuthRequest('session')
    if (!session.authenticated) {
      error.value = 'Trình duyệt chưa lưu được phiên đăng nhập. Hãy cho phép cookie cho trang này rồi thử lại.'
      return
    }
    password.value = ''
    emit('signed-in', session)
  } catch (failure) {
    error.value = messages[failure.code] || 'Không kết nối được trang đăng nhập. Vui lòng thử lại.'
    if (failure.retryAfter > 0) {
      retryAt.value = Date.now() + failure.retryAfter * 1000
      now.value = Date.now()
      clearInterval(timer)
      timer = setInterval(() => {
        now.value = Date.now()
        if (!remaining.value) clearInterval(timer)
      }, 1000)
    }
  } finally {
    busy.value = false
    if (error.value) { await nextTick(); errorBox.value?.focus() }
  }
}
onUnmounted(() => { clearInterval(timer); password.value = '' })
</script>

<template>
  <main class="login-page">
    <div class="login-preferences">
      <select :value="i18n.locale" @change="i18n.setLocale($event.target.value)" aria-label="Language" translate="no"><option v-for="locale in LOCALES" :key="locale.code" :value="locale.code">{{ locale.label }}</option></select>
      <button class="login-icon" type="button" @click="theme.toggle" :aria-label="theme.dark ? t('浅色模式') : t('深色模式')"><Sun v-if="theme.dark" :size="19" aria-hidden="true" /><Moon v-else :size="19" aria-hidden="true" /></button>
    </div>
    <section class="login-card" aria-labelledby="login-heading">
      <div class="login-brand"><span class="login-mark"><ShieldCheck :size="23" aria-hidden="true" /></span><span>GPT Reg<small>Workspace</small></span></div>
      <header><h1 id="login-heading">{{ t('Đăng nhập workspace') }}</h1><p>{{ t('Dùng tài khoản quản trị để tiếp tục.') }}</p></header>
      <p v-if="expired && !error" class="login-notice" role="status">{{ t('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.') }}</p>
      <form @submit.prevent="submit" :aria-busy="busy">
        <div class="login-field"><label for="login-username">{{ t('Tên đăng nhập') }}</label><input id="login-username" v-model="username" name="username" autocomplete="username" autocapitalize="none" spellcheck="false" translate="no" required maxlength="256" :disabled="busy" :aria-describedby="error ? 'login-error' : undefined" /></div>
        <div class="login-field"><label for="login-password">{{ t('Mật khẩu') }}</label><div class="login-password"><input id="login-password" v-model="password" name="password" :type="visible ? 'text' : 'password'" autocomplete="current-password" translate="no" required maxlength="1024" :disabled="busy" :aria-describedby="error ? 'login-error' : undefined" /><button class="login-icon" type="button" @click="visible = !visible" :aria-label="t(visible ? 'Ẩn mật khẩu' : 'Hiện mật khẩu')" :aria-pressed="visible"><EyeOff v-if="visible" :size="19" aria-hidden="true" /><Eye v-else :size="19" aria-hidden="true" /></button></div></div>
        <div v-if="error" id="login-error" ref="errorBox" class="login-error" role="alert" tabindex="-1"><p>{{ t(error) }}</p><p v-if="remaining">{{ t('Thử lại sau {0} giây.').replace('{0}', remaining) }}</p></div>
        <button class="login-submit" type="submit" :disabled="busy || remaining > 0"><LoaderCircle v-if="busy" class="login-spinner" :size="18" aria-hidden="true" /><span>{{ t(busy ? 'Đang đăng nhập…' : 'Đăng nhập') }}</span><ArrowRight v-if="!busy" :size="18" aria-hidden="true" /></button>
      </form>
      <p class="login-hint">{{ t('Dùng tài khoản và mật khẩu bạn đang dùng cho trang web.') }}</p>
    </section>
    <p class="login-footer">{{ t('Quản lý tài khoản và tác vụ trong một workspace.') }}</p>
  </main>
</template>

<style scoped>
.login-page { min-height: 100dvh; padding: 100px 24px 32px; display: flex; flex-direction: column; align-items: center; justify-content: center; color: var(--app-title); background: radial-gradient(ellipse at 50% 10%, var(--brand-bg), transparent 65%), var(--app-content-bg); }
.login-preferences { position: absolute; top: 24px; right: 24px; display: flex; gap: 8px; }
.login-preferences select, .login-icon { min-height: 44px; border: 1px solid var(--app-border); border-radius: 10px; background: var(--app-card-bg); color: var(--app-text-regular); cursor: pointer; }
.login-preferences select { padding: 0 12px; font: inherit; font-size: 13px; }
.login-icon { width: 44px; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; }
.login-icon:hover { background: var(--app-card-hover); color: var(--brand); }
.login-card { width: 100%; max-width: 424px; padding: 36px; border: 1px solid var(--app-border); border-radius: 20px; background: var(--app-card-bg); box-shadow: var(--app-shadow-md); }
.login-brand { display: flex; gap: 12px; align-items: center; margin-bottom: 32px; font-size: 18px; font-weight: 650; }
.login-mark { display: grid; place-items: center; width: 46px; height: 46px; border: 1px solid var(--app-border); border-radius: 13px; background: var(--brand-bg); color: var(--brand); }
.login-brand small { display: block; margin-top: 3px; font-size: 12px; font-weight: 400; color: var(--app-text-muted); }
h1 { margin: 0 0 10px; font-size: 26px; line-height: 1.25; font-weight: 650; letter-spacing: -.5px; }
header p { margin: 0 0 28px; color: var(--app-text-muted); font-size: 14px; line-height: 1.6; }
.login-field { display: grid; gap: 9px; margin-bottom: 20px; }
label { font-size: 13px; font-weight: 550; }
input { width: 100%; min-width: 0; height: 48px; padding: 0 13px; border: 1px solid var(--app-border-hover); border-radius: 10px; background: var(--app-content-bg); color: var(--app-title); font: inherit; font-size: 16px; transition: border-color .15s, box-shadow .15s; }
input:focus-visible, button:focus-visible, select:focus-visible { outline: 2px solid var(--brand); outline-offset: 3px; }
input:focus-visible { outline-offset: 1px; }
.login-password { position: relative; }
.login-password input { padding-right: 52px; }
.login-password .login-icon { position: absolute; top: 2px; right: 2px; border: 0; background: transparent; }
.login-submit { margin-top: 6px; width: 100%; min-height: 48px; padding: 12px 16px; display: flex; gap: 10px; align-items: center; justify-content: center; border: 1px solid transparent; border-radius: 10px; background: var(--brand); color: var(--brand-fg); font: inherit; font-size: 14px; font-weight: 600; cursor: pointer; transition: background .15s, opacity .15s; }
.login-submit:hover:not(:disabled) { background: var(--brand-hover); }
.login-submit:disabled { opacity: .65; cursor: not-allowed; }
.login-hint, .login-footer { color: var(--app-text-muted); font-size: 12px; line-height: 1.7; text-align: center; }
.login-hint { margin: 22px 0 0; }
.login-footer { margin: 24px 0 0; }
.login-error, .login-notice { padding: 12px; margin: 0 0 18px; border: 1px solid var(--color-danger-border); border-radius: 10px; background: var(--color-danger-bg); color: var(--color-danger); font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; }
.login-error p { margin: 0; }
.login-error p + p { margin-top: 5px; }
.login-notice { color: var(--app-text-regular); background: var(--brand-bg); border-color: var(--app-border-hover); }
.login-spinner { animation: login-spin 1s linear infinite; }
@keyframes login-spin { to { transform: rotate(360deg); } }
@media (max-width: 480px) { .login-page { padding: 90px 16px 28px; } .login-card { padding: 28px 24px; } .login-preferences { top: 16px; right: 16px; } h1 { font-size: 24px; } }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation: none !important; transition: none !important; } }
</style>
