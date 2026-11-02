<script setup>
import { inject } from 'vue'
import { Copy, Folder, FolderInput, RotateCw } from 'lucide-vue-next'
import AccountCredentials from '@/components/AccountCredentials.vue'
import { copyText, fmtTime } from '@/api/request'
import { useI18nStore } from '@/stores/i18n'
import { upiAccountRoute } from '@/upi'

const props = defineProps({
  email: { type: String, default: '' },
  info: { type: Object, default: null },
  groups: { type: Array, default: () => [] },
  groupsLoading: Boolean,
  groupsError: Boolean,
  moving: Boolean,
  newScan: Boolean,
})
const emit = defineEmits(['move', 'folders-open', 'reload', 'navigate'])
const i18n = useI18nStore()
const credentialNow = inject('upiCredentialNow')
const t = text => i18n.t(text)
function copyLogin() {
  const account = props.info?.account
  if (account) copyText([account.email, account.password, account.totp_secret].join('---'))
}
function move(command) { emit('move', command === 'clear' ? '' : command.slice(6)) }
</script>

<template>
  <div class="upi-account" :aria-busy="info?.state === 'loading' || moving">
    <div class="upi-account-heading">
      <button type="button" class="upi-email-copy" :disabled="!email" :aria-label="`${t('Sao chép email')} ${email}`" title="Bấm để sao chép email" @click.stop="copyText(email)"><span translate="no">{{ email || '—' }}</span><span v-if="newScan" class="upi-new-badge" translate="no" :title="t('Vừa quét thành công; giữ NEW đến đợt UPI mới.')" :aria-label="t('Vừa quét thành công; giữ NEW đến đợt UPI mới.')">NEW</span></button>
      <button v-if="info?.state === 'ready'" type="button" class="upi-copy-login" title="Email---Mật khẩu---2FA" aria-label="Sao chép LS" @click.stop="copyLogin"><Copy :size="14" /></button>
      <router-link v-if="info?.state === 'ready'" class="upi-copy-login" :to="upiAccountRoute(email, true)" :title="t('Cưỡng chế làm mới AT')" :aria-label="`${t('Cưỡng chế làm mới AT')} ${email}`" @click="emit('navigate')"><RotateCw :size="14" /></router-link>
    </div>
    <template v-if="info?.state === 'ready'">
      <AccountCredentials :password="info.account.password" :secret="info.account.totp_secret" :now="credentialNow" />
      <div class="upi-account-meta account-meta-badges">
        <el-dropdown trigger="click" :disabled="moving" @visible-change="visible => { if (visible) emit('folders-open') }" @command="move">
          <button type="button" class="upi-folder account-meta-badge" :disabled="moving" :aria-label="`${t('Chuyển thư mục')} ${email}`" :title="`${t('Chuyển thư mục')}: ${info.account.group_name || t('Chưa phân thư mục')}`"><FolderInput v-if="moving" :size="13" /><Folder v-else :size="13" /><span v-if="info.account.group_name" class="account-meta-label" translate="no">{{ info.account.group_name }}</span><span v-else class="account-meta-label">Chưa phân thư mục</span></button>
          <template #dropdown><el-dropdown-menu>
            <el-dropdown-item v-if="groupsLoading" disabled>Đang tải thư mục…</el-dropdown-item>
            <el-dropdown-item v-else-if="groupsError" disabled>Không tải được thư mục.</el-dropdown-item>
            <el-dropdown-item command="clear" :disabled="moving || !info.account.group_name">Chưa phân thư mục</el-dropdown-item>
            <el-dropdown-item v-for="group in groups" :key="group.name" :command="`group:${group.name}`" :disabled="moving || group.name === info.account.group_name"><span translate="no">{{ group.name }}</span></el-dropdown-item>
          </el-dropdown-menu></template>
        </el-dropdown>
        <el-tag class="account-meta-badge" size="small" :type="info.account.plan_verified ? 'success' : 'info'" :title="`${t('Gói gần nhất')}: ${t(info.account.plan_label)}`"><span class="account-meta-label"><span>Gói gần nhất</span>: {{ t(info.account.plan_label) }}</span></el-tag>
      </div>
      <p class="upi-account-note"><span>Kiểm tra gói</span>: {{ info.account.plan_checked_at ? fmtTime(info.account.plan_checked_at) : t('Chưa có mốc kiểm tra') }}</p>
    </template>
    <p v-else-if="info?.state === 'missing'" class="upi-account-note">Tài khoản chưa có trong kho.</p>
    <p v-else-if="info?.state === 'error'" class="upi-account-note"><span>Không tải được thông tin tài khoản.</span><button type="button" @click="emit('reload')">Thử lại</button></p>
    <p v-else class="upi-account-note">Đang tải tài khoản…</p>
    <router-link v-if="email" class="upi-account-link" :to="upiAccountRoute(email)" @click="emit('navigate')">Kiểm tra gói trong Tài khoản</router-link>
  </div>
</template>

<style scoped>
.upi-account { width: 100%; }
.upi-new-badge{display:inline-flex;align-items:center;margin-inline-start:6px;padding:0 5px;border:1px solid var(--brand-border);border-radius:5px;background:var(--brand-bg);color:var(--brand);font-size:9px;font-weight:700;line-height:16px;letter-spacing:.04em;vertical-align:middle;white-space:nowrap}
.upi-account{min-width:0;max-width:100%;font-size:12px;line-height:1.6}.upi-account-heading{display:flex;align-items:flex-start;gap:8px;min-width:0}.upi-email-copy{flex:1;min-width:0;text-align:left;overflow-wrap:anywhere;font-size:12px;font-weight:650;line-height:1.6;color:var(--app-title)}.upi-email-copy,.upi-copy-login,.upi-folder{border:0;background:transparent;font-family:inherit;cursor:pointer;padding:0;border-radius:5px}.upi-email-copy:hover,.upi-copy-login:hover,.upi-folder:hover{color:var(--brand);background:var(--brand-bg)}.upi-email-copy:focus-visible,.upi-copy-login:focus-visible,.upi-folder:focus-visible{outline:2px solid var(--brand);outline-offset:2px}.upi-copy-login{display:grid;place-items:center;flex:none;width:26px;height:26px;color:var(--app-text-muted);margin-top:-3px}.upi-account-meta{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:8px}.upi-account-meta>.el-dropdown{min-width:0;max-width:100%}.upi-folder{display:flex;align-items:center;gap:5px;max-width:100%;min-height:24px;padding:2px 6px;color:var(--app-text-muted);background:var(--app-card-hover);font-size:11px}.upi-folder>span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0}.upi-folder>svg{flex:none}.upi-account-meta>.el-tag{max-width:100%;height:auto;white-space:normal;line-height:1.5}.upi-account-link{display:inline-block;margin-top:8px;color:var(--brand);font-size:11px;text-decoration:underline;text-underline-offset:3px}.upi-account-note{font-size:11px;color:var(--app-text-muted);margin:5px 0}.upi-account-note>button{border:0;background:none;color:var(--brand);font:inherit;cursor:pointer;text-decoration:underline;margin-left:6px}.upi-folder:disabled{cursor:wait;opacity:.6}
@media(max-width:680px){.upi-email-copy{padding:7px 0;min-height:36px}.upi-copy-login{width:36px;height:36px;margin-top:0}.upi-folder{min-height:36px;padding:6px 8px}.upi-account-link{min-height:36px;padding:7px 0}.upi-account-meta{gap:8px}.upi-account :deep(.account-credentials){margin-top:3px}}
</style>
