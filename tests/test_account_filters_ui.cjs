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
    AbortController, onDeactivated: () => {}, onUnmounted: () => {}, toolsOpen: {value: false},
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

function loadHarness() {
  let time = 100000
  const h = { accountFilterParams: () => ({}), page: {value:1}, pageSize: {value:50},
    rows:{value:[]}, total:{value:0}, loading:{value:false}, toolsOpen:{value:false},
    AbortController, onDeactivated:()=>{}, onUnmounted:()=>{}, Date:{now:()=>time},
    clearAccountSelection:()=>{}, applyGroupsSummary:()=>{}, applyCountriesSummary:()=>{},
    loadGroupsOnly:()=>{throw Error('unexpected summary fallback')}, loadCountriesOnly:()=>{throw Error('unexpected summary fallback')},
    loadMeta:()=>{}, loadZeroSummary:()=>{h.offerCalls++}, offerCalls:0, requests:[], errors:[],
    ElMessage:{error: message=>h.errors.push(message)}, module:{exports:{}} }
  h.listRegistered = async (params, options) => {h.requests.push({params, options});return {items:[],total:0,groups_summary:params.include_summary?{}:null,countries_summary:params.include_summary?[]:null}}
  const block=source.slice(source.indexOf('let loadSequence = 0'),source.indexOf('// 勾选了就用勾选的'))
  vm.runInNewContext(block+'\nmodule.exports=load',h)
  h.load=h.module.exports; h.advance=ms=>{time+=ms}; return h
}

test('folder/page navigation reuses global summaries, with TTL and explicit refresh after mutations', async () => {
  const h=loadHarness()
  await h.load(false,false); await h.load(false,false)
  assert.deepEqual(h.requests.map(r=>r.params.include_summary),[true,false])
  assert.equal(h.offerCalls,0)
  h.advance(30001); await h.load(false,false)
  assert.equal(h.requests.at(-1).params.include_summary,true)
  await h.load(false,true)
  assert.equal(h.requests.at(-1).params.include_summary,true)
  h.toolsOpen.value=true; await h.load(false,false)
  assert.equal(h.offerCalls,1)
})

test('rapid navigation aborts the old request and ignores its late response', async () => {
  const h=loadHarness(), pending=[]
  h.listRegistered=(params,options)=>new Promise(resolve=>pending.push({resolve,options}))
  const first=h.load(false,false), second=h.load(false,false)
  assert.equal(pending[0].options.signal.aborted,true)
  pending[1].resolve({items:[{email:'new@example.test'}],total:1,groups_summary:{},countries_summary:[]})
  await second
  pending[0].resolve({items:[{email:'old@example.test'}],total:1,groups_summary:{},countries_summary:[]})
  await first
  assert.equal(h.rows.value[0].email,'new@example.test')
  assert.equal(h.loading.value,false)
  assert.deepEqual(h.errors,[])
})

test('mobile and page selection preserve off-page accounts without a hidden desktop table', () => {
  const a={email:'a@example.test'},b={email:'b@example.test'},c={email:'c@example.test'}
  let synchronize
  const h={selected:{value:[]},rows:{value:[a,b]},accountTable:{value:null},computed:fn=>({get value(){return fn()}}),watch:(_deps,fn)=>{synchronize=fn},module:{exports:{}}}
  const block=source.slice(source.indexOf('function toggleAccountSelection('),source.indexOf('function handleRowAction('))
  vm.runInNewContext(block+'\nmodule.exports={toggleAccountSelection,togglePageSelection}',h)
  const {toggleAccountSelection,togglePageSelection}=h.module.exports
  toggleAccountSelection(a,true);h.rows.value=[c];togglePageSelection([c])
  assert.deepEqual(Array.from(h.selected.value,row=>row.email),[a.email,c.email])
  togglePageSelection([]);assert.equal(h.selected.value[0].email,a.email)
  h.rows.value=[a,b];const checked=[]
  h.accountTable.value={getSelectionRows:()=>[],toggleRowSelection:(row,value)=>checked.push([row.email,value])}
  synchronize();assert.deepEqual(checked,[[a.email,true]])
  toggleAccountSelection(a,false);assert.equal(h.selected.value.length,0)
})
