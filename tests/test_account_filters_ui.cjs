const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const test = require('node:test')
const assert = require('node:assert/strict')
const source = fs.readFileSync(path.join(__dirname, '../webui/frontend/src/views/Registered.vue'), 'utf8')
function models() {
  const context = {ref: value => ({value}), computed: definition => ({get value() {return definition.get()}, set value(v) {definition.set(v)}}), result: null}
  vm.runInNewContext(source.slice(source.indexOf('const PLAN_FILTERS'), source.indexOf('const groupFilter')) + '\nresult = {planFilter,tokenFilter,errorFilter,filter}', context)
  return context.result
}
test('plan, token and error filters compose independently using AND syntax', () => {
  const m = models()
  m.planFilter.value = 'plan_plus'
  m.tokenFilter.value = 'token_invalid'
  m.errorFilter.value = 'refresh_network'
  assert.equal(m.filter.value, 'plan_plus|token_invalid|refresh_network')
  m.tokenFilter.value = 'all'
  assert.equal(m.filter.value, 'plan_plus|refresh_network')
})
test('clearing the common filter resets all three groups', () => {
  const m = models()
  m.filter.value = 'plan_plus|auth_2fa'
  assert.equal(m.planFilter.value, 'plan_plus')
  assert.equal(m.errorFilter.value, 'auth_2fa')
  m.filter.value = 'all'
  assert.equal(m.filter.value, 'all')
  assert.equal(m.planFilter.value, 'all')
  assert.equal(m.tokenFilter.value, 'all')
  assert.equal(m.errorFilter.value, 'all')
})
test('invalid filters do not silently clear an existing scope', () => {
  const m = models()
  m.filter.value = 'auth_2fa'
  assert.throws(() => {m.filter.value = 'not-a-filter'})
  assert.equal(m.filter.value, 'auth_2fa')
})
test('row loading is limited to accounts in flight, not all accounts in a large job', () => {
  const context = {computed: fn => ({get value() {return fn()}}), refreshJobRunning: {value: true},
    refreshJob: {value: {emails: Array.from({length: 4506}, (_, index) => `fixture-${index}@example.test`), current_email: 'fixture-1@example.test, fixture-2@example.test'}}, module: {exports: {}}}
  const block = source.slice(source.indexOf('const refreshingRow = computed'), source.indexOf('const planCheckSummary'))
  vm.runInNewContext(block + '\nmodule.exports=refreshingRow', context)
  assert.deepEqual(Object.keys(context.module.exports.value), ['fixture-1@example.test', 'fixture-2@example.test'])
  context.refreshJobRunning.value = false
  assert.equal(Object.keys(context.module.exports.value).length, 0)
})
test('background loads clear selections if the scope changed, while page changes retain them', async () => {
  let scope = {filter: 'all'}
  const context = {
    accountFilterParams: () => ({...scope}), page: {value: 1}, pageSize: {value: 50}, selected: {value: []},
    loading: {value: false}, rows: {value: []}, total: {value: 0}, requests: [],
    listRegistered: async params => {context.requests.push(params);return {items: [], total: 100, groups_summary: {}, countries_summary: []}},
    applyGroupsSummary: () => {}, applyCountriesSummary: () => {}, loadMeta: () => {}, loadZeroSummary: () => {},
    clearAccountSelection: () => {context.selected.value = []},
    module: {exports: {}},
  }
  const block = source.slice(source.indexOf('let loadSequence = 0'), source.indexOf('// 勾选了就用勾选的'))
  vm.runInNewContext(block + '\nmodule.exports = load', context)
  await context.module.exports(false)
  context.selected.value = [{email: 'fixture@example.test'}]
  context.page.value = 2
  await context.module.exports()
  assert.equal(context.selected.value.length, 1)
  scope = {filter: 'all', q: 'different-account'}
  await context.module.exports(false)
  assert.equal(context.selected.value.length, 0)
  assert.equal(context.page.value, 1)
  await context.module.exports()
  assert.equal(context.requests.at(-1).q, 'different-account')
})
