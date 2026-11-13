<script setup>
import { computed, onDeactivated, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useProxyStore } from '@/stores/proxy'
import { createSecurityJob } from '@/api/security'
import { securityModes, securityRequestId } from '@/accountSecurity'

const props = defineProps({ modelValue: Boolean, emails: { type: Array, default: () => [] }, initialMode: { type: String, default: 'change_2fa' } })
const emit = defineEmits(['update:modelValue', 'created'])
const proxyStore = useProxyStore()
const mode = ref('change_2fa'), workers = ref(1), proxy = ref('__direct__'), newPassword = ref(''), logoutAfter = ref(false)
const confirmed = ref(false), busy = ref(false), requestId = ref('')
const changesPassword = computed(() => ['change_password', 'change_password_and_2fa'].includes(mode.value))
const changing = computed(() => mode.value !== 'check_only')
watch(() => props.modelValue, open => {
  if (!open) { newPassword.value = ''; return }
  mode.value = props.initialMode; confirmed.value = false; requestId.value = securityRequestId()
  workers.value = 1; logoutAfter.value = false; newPassword.value = ''
  proxyStore.loadFromServer().catch(() => {})
})
watch(mode, () => { confirmed.value = false })
onDeactivated(() => { emit('update:modelValue', false); newPassword.value = '' })
async function submit() {
  if (busy.value) return
  busy.value = true
  try {
    const { job } = await createSecurityJob({
      emails: props.emails, mode: mode.value, workers: workers.value, proxy: proxy.value === '__direct__' ? '' : proxy.value,
      new_password: changesPassword.value ? newPassword.value : '',
      logout_after: changing.value && mode.value !== 'logout_all' && logoutAfter.value,
      confirmed: !changing.value || confirmed.value, request_id: requestId.value,
    })
    emit('update:modelValue', false)
    emit('created', job)
  } catch (error) { ElMessage.error(error.message) }
  finally { busy.value = false }
}
</script>
<template>
  <el-dialog append-to-body :model-value="modelValue" title="Bảo mật acc" width="540px" :close-on-click-modal="!busy" :close-on-press-escape="!busy" :show-close="!busy" @update:model-value="emit('update:modelValue', $event)">
    <p class="security-scope">Phạm vi: <strong>{{ emails.length }} tài khoản đã chọn</strong></p>
    <el-form label-position="top" @submit.prevent="submit">
      <el-form-item label="Thao tác"><el-select v-model="mode" class="full-width" :disabled="busy"><el-option v-for="item in securityModes" :key="item.value" :label="item.label" :value="item.value"/></el-select></el-form-item>
      <el-form-item v-if="changesPassword" label="Mật khẩu mới"><el-input v-model="newPassword" type="password" show-password autocomplete="new-password" placeholder="Để trống: tạo mật khẩu riêng cho mỗi acc" :maxlength="256" :disabled="busy"/><span class="security-hint">Nếu tự nhập, dùng 12–256 ký tự và cùng mật khẩu cho các acc đã chọn.</span></el-form-item>
      <div class="security-form-row"><el-form-item label="Luồng"><el-input-number v-model="workers" :min="1" :max="10" :disabled="busy"/></el-form-item><el-form-item label="Kết nối"><el-select v-model="proxy" filterable allow-create default-first-option class="full-width" :disabled="busy"><el-option label="Trực tiếp" value="__direct__"/><el-option v-for="item in proxyStore.list" :key="item" :label="item.replace(/\/\/[^/@]+@/, '//•••@')" :value="item"/></el-select></el-form-item></div>
      <el-checkbox v-if="changing && mode !== 'logout_all'" v-model="logoutAfter" :disabled="busy">Kick tất cả phiên sau khi đổi và xác minh</el-checkbox>
      <el-alert v-if="changing" type="warning" :closable="false" show-icon class="security-warning" :title="mode === 'logout_all' ? 'Các phiên ChatGPT đang đăng nhập sẽ bị đăng xuất.' : 'Thao tác thay đổi thông tin bảo mật trên tài khoản ChatGPT.'" description="Thông tin đã xác nhận được đồng bộ vào Quản lý acc. Nếu xác minh lỗi, giữ checkpoint để tiếp tục."/>
      <el-checkbox v-if="changing" v-model="confirmed" class="security-confirm" :disabled="busy">Tôi xác nhận thực hiện với {{ emails.length }} acc đã chọn</el-checkbox>
    </el-form>
    <template #footer><el-button :disabled="busy" @click="emit('update:modelValue', false)">Hủy</el-button><el-button type="primary" :loading="busy" :disabled="!emails.length || emails.length > 500 || (changing && !confirmed)" @click="submit">Bắt đầu</el-button></template>
  </el-dialog>
</template>
<style scoped>
.security-scope{margin:0 0 18px;color:var(--app-text-muted)}.security-scope strong{color:var(--app-title)}.full-width{width:100%}.security-form-row{display:grid;grid-template-columns:145px minmax(0,1fr);gap:16px}.security-hint{color:var(--app-text-muted);font-size:12px;line-height:1.6;margin-top:6px}.security-warning{margin-top:16px}.security-confirm{height:auto;margin-top:18px;white-space:normal}.security-confirm :deep(.el-checkbox__label){white-space:normal;line-height:1.6}@media(max-width:480px){.security-form-row{grid-template-columns:1fr;gap:0}}
</style>
