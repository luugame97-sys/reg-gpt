const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const test = require('node:test')
const assert = require('node:assert/strict')
const source = fs.readFileSync(path.join(__dirname, '../webui/frontend/src/stores/proxy.js'), 'utf8')
  .replace(/^import .*$/gm, '').replace(/export (const|function) /g, '$1 ')

function harness(options = {}) {
  let server = options.server ?? 'socks5h://original.invalid:1080'
  let failSave = false, mismatch = false
  const calls = [], timers = new Map()
  const context = {
    defineStore: (_, setup) => setup, ref: value => ({value}), computed: fn => ({get value() {return fn()}}), watch: () => {},
    localStorage: {getItem: () => null, setItem: () => {}},
    setTimeout: fn => {const id = timers.size + 1; timers.set(id, fn); return id}, clearTimeout: id => timers.delete(id),
    getProxyPool: async () => {if (options.failLoad) throw Error('offline');return {text: mismatch ? 'wrong.invalid:1' : server, cleared: !server}},
    saveProxyPool: async text => {calls.push(text);if(failSave) throw Error('offline');if(options.onSave) await options.onSave(text);server = text},
    module: {exports: {}},
  }
  vm.runInNewContext(source + '\nmodule.exports=useProxyStore()', context)
  return {store: context.module.exports, calls, timers, fail: value => {failSave=value}, mismatch: value => {mismatch=value}, server: () => server}
}

test('saving reports success only after server write and read-back', async () => {
  const h=harness();await h.store.loadFromServer()
  assert.equal(h.store.saveState.value, 'saved')
  h.store.setFromText('new.invalid:1080\nnew.invalid:1080')
  assert.equal(h.store.saveState.value, 'pending')
  await h.store.persist()
  assert.equal(h.store.saveState.value, 'saved')
  assert.equal(h.server(), 'new.invalid:1080')
  assert.equal(h.calls.length,1)
})

test('network error keeps the edited list and supports an explicit retry', async () => {
  const h=harness();await h.store.loadFromServer();h.fail(true)
  h.store.setFromText('edited.invalid:1080')
  await assert.rejects(h.store.persist())
  assert.equal(h.store.saveState.value, 'error')
  assert.equal(h.store.text.value,'edited.invalid:1080')
  assert.equal(h.server(),'socks5h://original.invalid:1080')
  await assert.rejects(h.store.loadFromServer())
  assert.equal(h.store.text.value,'edited.invalid:1080')
  h.fail(false);await h.store.persist()
  assert.equal(h.store.saveState.value,'saved')
  assert.equal(h.server(),'edited.invalid:1080')
})

test('a mismatching read-back cannot produce a saved status', async () => {
  const h=harness();await h.store.loadFromServer()
  h.store.setFromText('edited.invalid:1080');h.mismatch(true)
  await assert.rejects(h.store.persist())
  assert.equal(h.store.saveState.value,'error')
  h.mismatch(false);await h.store.persist()
  assert.equal(h.store.saveState.value,'saved')
})

test('overlapping edits are serialized and the latest snapshot reaches the server', async () => {
  let release, started
  const entered = new Promise(resolve=>{started=resolve})
  let first=true
  const h=harness({onSave:async()=>{if(first){first=false;started();await new Promise(resolve=>{release=resolve})}}})
  await h.store.loadFromServer()
  h.store.setFromText('first.invalid:1080')
  const pending=h.store.persist()
  await entered
  h.store.setFromText('second.invalid:1080')
  const second=h.store.persist()
  release();await Promise.all([pending,second])
  assert.deepEqual(h.calls,['first.invalid:1080','second.invalid:1080'])
  assert.equal(h.server(),'second.invalid:1080')
  assert.equal(h.store.saveState.value,'saved')
})

test('failed initial load does not masquerade as synchronized', async () => {
  const h=harness({failLoad:true})
  await assert.rejects(h.store.loadFromServer())
  assert.equal(h.store.serverReady.value,false)
  assert.equal(h.store.saveState.value,'error')
  assert.equal(h.calls.length,0)
})

test('deleting the last proxy persists an explicit empty pool', async () => {
  const h=harness();await h.store.loadFromServer()
  h.store.remove('socks5h://original.invalid:1080');await h.store.persist()
  assert.equal(h.server(),'')
  assert.equal(h.store.saveState.value,'saved')
})
