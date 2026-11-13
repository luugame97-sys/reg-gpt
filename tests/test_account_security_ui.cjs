const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { pathToFileURL } = require('node:url')
const root = path.resolve(__dirname, '../webui/frontend/src')
const read = file => fs.readFileSync(path.join(root, file), 'utf8')

test('security selection deduplicates explicit emails without retaining credentials', async () => {
  const { securityEmails, securityActive } = await import(pathToFileURL(path.join(root, 'accountSecurity.js')))
  assert.deepEqual(securityEmails(' A@EXAMPLE.TEST\nb@example.test;A@example.test '), ['a@example.test','b@example.test'])
  assert(securityActive({ state: 'stopping' }))
  assert(!securityActive({ state: 'completed', counts: { attention: 1 } }))
  for (const file of ['views/AccountSecurity.vue','components/AccountSecurityDialog.vue','components/AccountSecurityProgress.vue']) {
    assert.doesNotMatch(read(file), /localStorage|sessionStorage|v-html/)
  }
})
test('one security route, plus account shortcuts on desktop, mobile and selected scope', () => {
  assert.equal((read('router/index.js').match(/path: '\/security'/g) || []).length, 1)
  assert.match(read('navigation.js'), /path: '\/security'.*ShieldCheck/)
  for (const mode of ['change_2fa','change_password','logout_all']) {
    assert.equal((read('views/Registered.vue').match(new RegExp(`command="security:${mode}"`, 'g')) || []).length, 2)
    assert(read('components/AccountToolbar.vue').includes(`security:${mode}`))
  }
  assert.match(read('views/Registered.vue'), /selected\.value\.map\(item => item\.email\)/)
})
test('security requests stop polling when cached views deactivate and preserve paging', () => {
  const progress = read('components/AccountSecurityProgress.vue')
  assert.match(progress, /onDeactivated.*clearTimeout\(timer\)/)
  assert.match(progress, /offset: \(page\.value - 1\) \* 50/)
  assert.match(progress, /offset < job\.value\.total; offset \+= 100/)
  assert.match(progress, /getSecurityRecovery\(props\.jobId\)/)
  assert.match(read('views/AccountSecurity.vue'), /onDeactivated.*importText\.value = ''/)
})
