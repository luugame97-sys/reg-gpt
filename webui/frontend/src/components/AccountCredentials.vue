<script setup>
import { computed, inject, onDeactivated, ref, watch } from 'vue'
import { Eye, EyeOff } from 'lucide-vue-next'
import { copyText } from '@/api/request'
import { createTotpGenerator, TOTP_PERIOD_MS } from '@/totp'
import { usePrivacyStore } from '@/stores/privacy'
const privacy = usePrivacyStore()

const props = defineProps({
  password: { type: String, default: '' },
  secret: { type: String, default: '' },
  now: { type: Number, default: undefined },
})
const clock = inject('accountCredentialNow', null) ?? inject('upiCredentialNow', ref(Date.now()))
const now = computed(() => props.now ?? clock.value)
const otp = ref('')
const otpError = ref('')
const passwordVisible = ref(false)
watch(() => props.password, () => { passwordVisible.value = false })
watch(() => privacy.hidden, () => { passwordVisible.value = false })
onDeactivated(() => { passwordVisible.value = false })
const remaining = computed(() => Math.ceil((TOTP_PERIOD_MS - now.value % TOTP_PERIOD_MS) / 1000))
let generatorSecret, generatorPromise

watch([() => props.secret, () => Math.floor(now.value / TOTP_PERIOD_MS)], async ([secret, counter], _, onCleanup) => {
  let cancelled = false
  onCleanup(() => { cancelled = true })
  otp.value = ''
  otpError.value = ''
  if (!secret.trim()) {
    generatorSecret = undefined
    generatorPromise = undefined
    return
  }
  try {
    if (generatorSecret !== secret) {
      generatorSecret = secret
      generatorPromise = createTotpGenerator(secret)
    }
    const generate = await generatorPromise
    const code = await generate(counter * TOTP_PERIOD_MS)
    if (!cancelled) otp.value = code
  } catch (error) {
    if (!cancelled) otpError.value = error.message
  }
}, { immediate: true })

async function copyOtp() {
  const secret = props.secret
  try {
    const generate = await generatorPromise
    // Recalculate at the click, including when a throttled browser timer just expired.
    const code = await generate()
    if (props.secret !== secret) return
    otp.value = code
    await copyText(code)
  } catch (error) {
    otpError.value = error.message
  }
}
</script>

<template>
  <div class="account-credentials">
    <div class="credential-line">
      <span class="credential-label">Mật khẩu</span>
      <div v-if="password" class="credential-password">
        <button type="button" class="credential-copy credential-value" :data-i18n-skip-title="passwordVisible || undefined" :title="passwordVisible ? password : 'Bấm để sao chép mật khẩu'" aria-label="Sao chép mật khẩu" @click.stop="copyText(password)"><span translate="no">{{ passwordVisible ? password : '••••••••' }}</span></button>
        <button type="button" class="credential-visibility" :aria-label="passwordVisible ? 'Ẩn mật khẩu' : 'Hiển thị mật khẩu'" :title="passwordVisible ? 'Ẩn mật khẩu' : 'Hiển thị mật khẩu'" :aria-pressed="passwordVisible" @click.stop="passwordVisible = !passwordVisible"><EyeOff v-if="passwordVisible" :size="13" /><Eye v-else :size="13" /></button>
      </div>
      <span v-else class="credential-empty">Chưa có</span>
    </div>
    <div class="credential-line">
      <span class="credential-label">2FA</span>
      <div class="credential-twofa">
        <button v-if="secret" type="button" class="credential-copy credential-value" data-i18n-skip-title="true" :title="privacy.hidden ? 'Sao chép khóa 2FA' : secret" aria-label="Sao chép khóa 2FA" @click.stop="copyText(secret)"><span translate="no">{{ privacy.hidden ? '••••••••' : secret }}</span></button>
        <span v-else class="credential-empty credential-value">Chưa có</span>
        <span class="credential-divider" aria-hidden="true">|</span>
        <button v-if="otp" type="button" class="credential-copy credential-otp" title="Bấm để sao chép mã OTP 2FA" aria-label="Sao chép OTP 2FA" @click.stop="copyOtp">{{ privacy.hidden ? '••••••' : otp }}</button>
        <span v-else class="credential-empty" :class="{ 'credential-error': otpError }" :title="otpError || (secret ? 'Đang tạo OTP' : 'Chưa có khóa 2FA')">{{ otpError ? 'Lỗi OTP' : '—' }}</span>
        <small v-if="otp" class="credential-countdown" :title="`OTP đổi sau ${remaining} giây`">{{ remaining }}s</small>
      </div>
    </div>
  </div>
</template>

<style scoped>
.account-credentials { display: grid; gap: 3px; min-width: 0; margin-top: 6px; font-size: 11px; line-height: 20px; }
.credential-line { display: grid; grid-template-columns: 49px minmax(0, 1fr); align-items: center; gap: 5px; min-width: 0; }
.credential-label, .credential-empty, .credential-countdown, .credential-divider { color: var(--app-text-muted); }
.credential-label { white-space: nowrap; }
.credential-copy { min-width: 0; padding: 0; border: 0; border-radius: 3px; background: transparent; color: var(--app-title); font: inherit; font-family: var(--font-mono, monospace); text-align: left; cursor: pointer; }
.credential-copy:hover { color: var(--brand); background: var(--brand-bg); }
.credential-copy:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
.credential-password { display: flex; align-items: center; gap: 6px; min-width: 0; }
.credential-password > .credential-value { flex: 1; }
.credential-visibility { display: inline-flex; align-items: center; justify-content: center; flex: none; width: 22px; height: 22px; border: 0; border-radius: 4px; padding: 0; background: transparent; color: var(--app-text-muted); cursor: pointer; }
.credential-visibility:hover { color: var(--brand); background: var(--brand-bg); }
.credential-visibility:focus-visible { outline: 2px solid var(--brand); outline-offset: 1px; }
.credential-value { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.credential-twofa { display: flex; align-items: center; gap: 6px; min-width: 0; }
.credential-twofa > .credential-value { flex: 1; }
.credential-divider { flex: none; opacity: .5; }
.credential-otp { flex: none; color: var(--brand); font-weight: 600; font-variant-numeric: tabular-nums; letter-spacing: .5px; }
.credential-countdown { flex: none; width: 21px; font-size: 10px; font-variant-numeric: tabular-nums; text-align: right; }
.credential-error { color: var(--color-warning); white-space: nowrap; }
@media (max-width: 680px) { .account-credentials { font-size: 12px; line-height: 22px; margin-top: 8px; }.credential-line { grid-template-columns: 56px minmax(0, 1fr); } }
</style>
