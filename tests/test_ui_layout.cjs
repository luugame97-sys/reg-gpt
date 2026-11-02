const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { pathToFileURL } = require('node:url')
const base = path.join(__dirname, '../webui/frontend/src')
const read = name => fs.readFileSync(path.join(base, name), 'utf8')
const load = name => import(pathToFileURL(path.join(base, name)).href)

test('completion with errors is not rendered as successful, including AT check counts', async () => {
  const { taskDisplayState, taskAttentionCount } = await load('taskPresentation.js')
  assert.equal(taskDisplayState({state:'completed', failed:1}), 'completed_errors')
  assert.equal(taskDisplayState({state:'completed', failed:0}), 'completed')
  assert.equal(taskDisplayState({state:'running', failed:1}), 'running')
  assert.equal(taskDisplayState(null), 'connecting')
  const checked = {state:'completed',operation:'token_check',failed:1,counts:{missing:3,expired_401:2}}
  assert.equal(taskAttentionCount(checked),5)
  assert.equal(taskDisplayState(checked),'completed_errors')
  assert.equal(taskDisplayState({state:'failed',failed:3}), 'failed')
})
test('a pre-payment membership check is not presented as post-payment verification', async () => {
  const { upiPostScanLabel, upiAccountFields } = await load('upi.js')
  const task = {scan_succeeded_at:200}
  assert.equal(upiPostScanLabel(task,{plan_checked_at:100,plan_verified:true}), 'Chưa kiểm tra gói sau quét')
  assert.equal(upiPostScanLabel(task,{plan_checked_at:201,plan_verified:true}), 'Đã kiểm tra gói sau quét')
  assert.equal(upiPostScanLabel(task,{plan_checked_at:201,plan_verified:false}), 'Đã kiểm tra nhưng chưa xác minh gói')
  assert.equal(upiPostScanLabel(task,null), 'Chưa kiểm tra gói sau quét')
  const row = upiAccountFields({email:'qa@example.test',extra:{plus_check:{checked_at:123}}},'qa@example.test')
  assert.equal(row.plan_checked_at,123)
  assert.equal(upiAccountFields({email:'qa@example.test',extra:{plus_check:{checked_at:'bad'}}},'qa@example.test').plan_checked_at,null)
})
test('all page dialogs escape glass containing blocks', () => {
  for (const name of ['Registered','Upi','Runs']) {
    const dialogs = [...read(`views/${name}.vue`).matchAll(/<el-dialog\b([^>]*)/g)]
    assert(dialogs.length)
    assert(dialogs.every(match => match[1].includes('append-to-body')),name)
  }
  assert.match(read('styles/workspace.css'), /max-height: calc\(100dvh - 32px\)/)
  assert.match(read('styles/workspace.css'), /\.el-dialog > \.el-dialog__body.*overflow-y: auto/)
})
test('picker full row is the native checkbox label; old duplicate click surface is removed', () => {
  const source = read('views/Upi.vue')
  assert.match(source, /<el-checkbox v-for="row in pickerRows"/)
  assert.doesNotMatch(source, /<div v-for="row in pickerRows"/)
  assert.match(source, /!row\.usable \|\| pickerSelecting \|\| pickerLoading/)
  assert.match(source, /v-show="composeExpanded"/)
})
test('resource mobile cards preserve existing action handlers and table selection', () => {
  for (const name of ['Pool','ProxyPool','Runs']) assert.match(read(`views/${name}.vue`), /v-if="mobileView"/)
  assert.match(read('views/Pool.vue'), /@selection-change="\(v\) => \(selected = v\)"/)
  for (const action of ['resetOne(row.email)','deleteOne(row.email)','useAccount(row)']) assert(read('views/Pool.vue').includes(action))
  assert(read('views/ProxyPool.vue').includes('testOne(row.proxy)'))
  assert(read('views/Runs.vue').includes('showProbes(row)'))
})
test('scroll reset distinguishes route navigation from filters and back navigation', () => {
  const source = read('router/index.js')
  assert.match(source, /if \(savedPosition\) return savedPosition/)
  assert.match(source, /to.path === from.path \? false : \{ left: 0, top: 0 \}/)
})
test('privacy masks text and 2FA tooltip without changing copy payloads', () => {
  const source = read('components/AccountCredentials.vue')
  assert.match(source, /:title="privacy.hidden \? 'Sao chép khóa 2FA' : secret"/)
  assert.match(source, /privacy.hidden \? '••••••' : otp/)
  assert.match(source, /@click.stop="copyText\(secret\)"/)
  assert.match(read('views/Upi.vue'), /privacy.hidden \? 'password' : 'text'/)
})

test('account metadata shares equal columns and border-box sizing across account and UPI views', () => {
  const css = read('styles/workspace.css')
  assert.match(css, /grid-template-columns: repeat\(var\(--account-badge-columns, 3\), minmax\(0, 1fr\)\)/)
  assert.match(css, /\.upi-account-meta\.account-meta-badges \{ --account-badge-columns: 2;/)
  assert.match(css, /:is\(\.app-frame \.app-content, \.el-dialog\) \.account-meta-badges/)
  assert.match(css, /\.account-meta-badge \{ box-sizing: border-box;.*height: var\(--account-badge-height\)/)
  assert.match(css, /@media \(max-width: 680px\), \(pointer: coarse\) \{\s+.*--account-badge-height: 44px/)
  const registered = read('views/Registered.vue')
  for (const name of ['account-identity-meta', 'mobile-account-meta']) {
    assert(registered.includes(`class="${name} account-meta-badges"`))
  }
  assert.equal([...registered.matchAll(/class="account-country account-meta-badge"/g)].length, 2)
  assert.equal([...registered.matchAll(/rowCountry\(row\) \|\| '—'/g)].length, 2)
  assert.equal([...registered.matchAll(/class="account-plan-badge account-meta-badge"/g)].length, 2)
  const upi = read('components/UpiAccount.vue')
  assert.match(upi, /class="upi-account-meta account-meta-badges"/)
  assert.match(upi, /class="upi-folder account-meta-badge"/)
  assert.match(upi, /<el-tag class="account-meta-badge"/)
  assert.match(upi, /\.upi-account \{ width: 100%; \}/)
})

test('long metadata labels retain full details without changing plan verification semantics', () => {
  const registered = read('views/Registered.vue')
  assert.match(registered, /:title="row.group_name"/)
  assert.match(registered, /<el-tooltip :content="row.group_name \|\| 'Chưa phân thư mục'" trigger="click">/)
  assert.equal([...registered.matchAll(/:title="plusOf\(row\)\?\.label \|\| 'Chưa kiểm tra'"/g)].length, 2)
  assert.equal([...registered.matchAll(/:class="row.plus_check\?\.membership_verified \? row.plus_check.status : 'unverified'"/g)].length, 2)
  assert.match(read('components/UpiAccount.vue'), /:title="`\$\{t\('Gói gần nhất'\)\}: \$\{t\(info.account.plan_label\)\}`"/)
})
