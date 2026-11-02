const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const test = require('node:test')
const assert = require('node:assert/strict')
const source = fs.readFileSync(path.join(__dirname, '../webui/frontend/src/stores/tokenRefresh.js'), 'utf8')
  .replace(/^import .*$/gm, '').replace('export const useTokenRefreshStore', 'const useTokenRefreshStore')
const queued = {job_id: 'job-1', state: 'queued', total: 1, completed: 0, emails: ['fixture@example.test'], results: []}

function harness(api = {}, stored = {}) {
  const storage = new Map(Object.entries(stored)), timers = new Map(), posted = [], cancelled = [], checks = []
  let nextTimer = 0
  const context = {
    defineStore: (_, setup) => setup, ref: value => ({value}), computed: fn => ({get value() {return fn()}}),
    localStorage: {getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key)},
    crypto: {randomUUID: () => 'request-unique'},
    setTimeout: (fn, ms) => {const id = ++nextTimer;timers.set(id, {fn, ms});return id}, clearTimeout: id => timers.delete(id),
    startTokenRefreshJob: async payload => {posted.push(payload);return (api.start || (async () => ({job: {...queued}})))(payload)},
    startTokenCheckJob: async payload => {checks.push(payload);return {job: {...queued, operation: 'token_check', total: payload.emails.length}}},
    getTokenRefreshJob: api.get || (async () => ({job: {...queued, state: 'completed', completed: 1}})),
    findTokenRefreshJobs: api.find || (async () => ({jobs: []})), module: {exports: {}},
    cancelTokenRefreshJob: async jobId => {cancelled.push(jobId);return (api.cancel || (async () => ({job: {...queued, state: 'stopping', cancel_requested: true}})))(jobId)},
  }
  vm.runInNewContext(source + '\nmodule.exports = useTokenRefreshStore()', context)
  return {store: context.module.exports, storage, timers, posted, cancelled, checks}
}

test('submit stores a receipt and polls until completion without retaining proxy credentials', async () => {
  const h = harness()
  await h.store.start(['fixture@example.test'], 'socks5h://private-user:private-pass@proxy.invalid:1080', 180, 'single')
  assert.equal(h.store.running.value, true)
  assert.equal(h.posted[0].request_id, 'request-unique')
  assert.equal(h.posted[0].proxy_mode, 'single')
  assert.equal(h.storage.get('token_refresh_job_id'), 'job-1')
  assert(!JSON.stringify([...h.storage]).includes('private-pass'))
  await h.store.poll()
  assert.equal(h.store.job.value.state, 'completed')
  assert.equal(h.store.running.value, false)
  assert.equal(h.timers.size, 0)
})
test('reload restores progress without submitting any account work', async () => {
  const h = harness({}, {token_refresh_job_id: 'job-1'})
  await h.store.restore()
  assert.equal(h.store.job.value.state, 'completed')
  assert.equal(h.posted.length, 0)
})
test('a lost submit response recovers the same job by request id', async () => {
  const h = harness({start: async () => {throw new Error('connection lost')}, find: async () => ({jobs: [{...queued}]})})
  const result = await h.store.start(['fixture@example.test'])
  assert.equal(result.job_id, 'job-1')
  assert.equal(h.posted.length, 1)
  assert.equal(h.store.running.value, true)
})
test('retry after an unconfirmed request reuses the idempotency key', async () => {
  let calls = 0
  const h = harness({start: async () => {if (++calls === 1) throw new Error('offline');return {job: {...queued}}}})
  await assert.rejects(h.store.start(['fixture@example.test']))
  assert.equal(h.store.starting.value, false)
  await h.store.start(['fixture@example.test'])
  assert.equal(h.posted[0].request_id, h.posted[1].request_id)
})
test('poll failure keeps the server job running and schedules reconnection', async () => {
  const h = harness({get: async () => {throw new Error('offline')}})
  await h.store.start(['fixture@example.test'])
  await h.store.poll()
  assert.equal(h.store.running.value, true)
  assert.equal(h.store.job.value.state, 'queued')
  assert(h.store.connectionError.value)
  assert.equal([...h.timers.values()][0].ms, 5000)
})
test('restoring while offline retries automatically instead of silently losing the job', async () => {
  const h = harness({get: async () => {throw new Error('offline')}}, {token_refresh_job_id: 'job-1'})
  await h.store.restore()
  assert.equal(h.storage.get('token_refresh_job_id'), 'job-1')
  assert.equal(h.timers.size, 1)
})
test('polling without a receipt does not prevent a subsequent restore', async () => {
  const h = harness({}, {})
  await h.store.poll()
  h.storage.set('token_refresh_job_id', 'job-1')
  await h.store.restore()
  assert.equal(h.store.job.value.state, 'completed')
})
test('new refresh uses the server proxy pool by default and omits a stale selected proxy', async () => {
  const h = harness()
  await h.store.start(['fixture@example.test'], 'socks5h://stale:secret@proxy.invalid:1080')
  assert.equal(h.posted[0].proxy_mode, 'pool')
  assert.equal(h.posted[0].proxy, '')
})
test('explicit direct mode never transmits the selected proxy', async () => {
  const h = harness()
  await h.store.start(['fixture@example.test'], 'socks5h://stale:secret@proxy.invalid:1080', 180, 'direct')
  assert.equal(h.posted[0].proxy_mode, 'direct')
  assert.equal(h.posted[0].proxy, '')
})
test('expired-only selection is carried to the background task', async () => {
  const h = harness()
  await h.store.start(['fixture@example.test'], '', 180, 'pool', true)
  assert.equal(h.posted[0].proxy_mode, 'pool')
  assert.equal(h.posted[0].only_expired, true)
})

test('manual refresh explicitly includes usable AT while retaining smart account guards', async () => {
  const h = harness()
  await h.store.start(['fixture@example.test'], '', 180, 'pool', true, 'token_refresh', 3, true, true, '', false, true)
  assert.equal(h.posted[0].refresh_usable, true)
  assert.equal(h.posted[0].smart_refresh, true)
  assert.equal(h.posted[0].only_expired, false)
  const normal = harness()
  await normal.store.start(['fixture@example.test'], '', 180, 'pool', true)
  assert(!normal.posted[0].refresh_usable)
  assert.equal(normal.posted[0].smart_refresh, true)
  assert.equal(normal.posted[0].only_expired, true)
})

test('stop is sent for the exact server job and keeps polling while its account finishes', async () => {
  const h = harness({get: async () => ({job: {...queued, state: 'cancelled', completed: 0, cancel_requested: true}})})
  await h.store.start(['fixture@example.test'])
  await h.store.cancel()
  assert.deepEqual(h.cancelled, ['job-1'])
  assert.equal(h.store.running.value, true)
  assert.equal(h.store.stopRequested.value, true)
  assert.equal(h.storage.has('token_refresh_cancel_job_id'), false)
  await h.store.poll()
  assert.equal(h.store.running.value, false)
  assert.equal(h.timers.size, 0)
})

test('lost stop acknowledgement survives reload and is retried without starting account work', async () => {
  const h = harness({cancel: async () => {throw new Error('offline')}})
  await h.store.start(['fixture@example.test'])
  await assert.rejects(h.store.cancel())
  assert.equal(h.storage.get('token_refresh_cancel_job_id'), 'job-1')
  assert.equal(h.store.stopRequested.value, true)
  const restored = harness({get: async () => ({job: {...queued, state: 'stopping', cancel_requested: true}})}, Object.fromEntries(h.storage))
  await restored.store.restore()
  assert.deepEqual(restored.cancelled, ['job-1'])
  assert.equal(restored.posted.length, 0)
  assert.equal(restored.storage.has('token_refresh_cancel_job_id'), false)
  assert.equal(restored.store.job.value.state, 'stopping')
})

test('an older progress response cannot erase an acknowledged stop', async () => {
  let resolveGet
  const h = harness({
    get: () => new Promise(resolve => {resolveGet = resolve}),
    cancel: async () => ({job: {...queued, state: 'stopping', cancel_requested: true, updated_at: 20}}),
  })
  await h.store.start(['fixture@example.test'])
  const poll = h.store.poll()
  await h.store.cancel()
  resolveGet({job: {...queued, state: 'running', updated_at: 10}})
  await poll
  assert.equal(h.store.job.value.state, 'stopping')
  assert.equal(h.store.stopRequested.value, true)
})

test('repeated stop clicks share one pending request', async () => {
  let resolveCancel
  const h = harness({cancel: () => new Promise(resolve => {resolveCancel = resolve})})
  await h.store.start(['fixture@example.test'])
  const pending = h.store.cancel()
  await h.store.cancel()
  assert.deepEqual(h.cancelled, ['job-1'])
  resolveCancel({job: {...queued, state: 'stopping', cancel_requested: true}})
  await pending
})

test('a readback can confirm stop after both POST responses were lost', async () => {
  const h = harness({cancel: async () => {throw new Error('response lost')}, get: async () => ({job: {...queued, state: 'stopping', cancel_requested: true}})})
  await h.store.start(['fixture@example.test'])
  await assert.rejects(h.store.cancel())
  await h.store.poll()
  assert.equal(h.store.job.value.state, 'stopping')
  assert.equal(h.storage.has('token_refresh_cancel_job_id'), false)
  assert.equal(h.store.connectionError.value, '')
})

test('restoring a remembered terminal job discovers the active task from another tab', async () => {
  const h = harness({find: async () => ({jobs: [{...queued, job_id: 'job-active', state: 'stopping', cancel_requested: true}]})}, {token_refresh_job_id: 'job-old'})
  await h.store.restore()
  assert.equal(h.store.job.value.job_id, 'job-active')
  assert.equal(h.store.running.value, true)
  assert.equal(h.store.stopRequested.value, true)
  assert.equal(h.storage.get('token_refresh_job_id'), 'job-active')
})

test('a scan sends every selected email to the background check API and never submits login', async () => {
  const h = harness()
  const emails = Array.from({length: 8547}, (_, i) => `fixture-${i}@example.test`)
  await h.store.start(emails, 'stale:proxy', 180, 'pool', true, 'token_check')
  assert.equal(h.checks.length, 1)
  assert.equal(h.checks[0].emails.length, 8547)
  assert.equal(h.checks[0].proxy_mode, 'pool')
  assert.equal(h.checks[0].proxy, '')
  assert.equal(h.checks[0].only_expired, undefined)
  assert.equal(h.posted.length, 0)
  assert.equal(h.store.job.value.operation, 'token_check')
  await h.store.cancel()
  assert.deepEqual(h.cancelled, ['job-1'])
})

test('Plus and checkout use the same durable queue without a total-account cap', async () => {
  for (const operation of ['plus_check', 'checkout_check']) {
    const h = harness()
    await h.store.start(Array.from({length:10001}, (_, i) => `fixture-${i}@example.test`), '', 180, 'pool', false, operation)
    assert.equal(h.checks.length, 1)
    assert.equal(h.checks[0].emails.length, 10001)
    assert.equal(h.checks[0].operation, operation)
    assert.equal(h.posted.length, 0)
  }
})

test('worker count is sent for refresh and every check operation', async () => {
  for (const operation of ['token_refresh', 'token_check', 'plus_check', 'checkout_check']) {
    const h = harness()
    await h.store.start(['one@example.test','two@example.test','three@example.test'], '', 180, 'pool', false, operation, 7)
    assert.equal((operation === 'token_refresh' ? h.posted : h.checks)[0].workers, 7)
  }
})

test('AT scan defaults to skipping usable tokens and allows an explicit full recheck', async () => {
  const first = harness()
  await first.store.start(['fixture@example.test'], '', 180, 'pool', false, 'token_check', 5)
  assert.equal(first.checks[0].skip_usable, true)
  const forced = harness()
  await forced.store.start(['fixture@example.test'], '', 180, 'pool', false, 'token_check', 5, false)
  assert.equal(forced.checks[0].skip_usable, false)
  const refresh = harness()
  await refresh.store.start(['fixture@example.test'], '', 180, 'pool', false, 'token_refresh', 3, true)
  assert.equal(refresh.posted[0].skip_usable, undefined)
})

test('filtered refresh includes both expired and missing AT without changing scan payloads', async () => {
  const refresh=harness()
  await refresh.store.start(['missing@example.test'],'',180,'pool',true,'token_refresh',3)
  assert.equal(refresh.posted[0].only_expired,true)
  assert.equal(refresh.posted[0].include_missing,true)
  const scan=harness()
  await scan.store.start(['missing@example.test'],'',180,'pool',false,'token_check',5)
  assert.equal(scan.checks[0].include_missing,undefined)
})

test('explicit retry links to its source job and cannot silently apply another expiry filter', async () => {
  const h=harness()
  await h.store.start(['temporary@example.test'],'',180,'pool',true,'token_refresh',3,true,true,'a'.repeat(32))
  assert.equal(h.posted[0].retry_source_job_id,'a'.repeat(32))
  assert.equal(h.posted[0].only_expired,false)
  assert.equal(h.posted[0].include_missing,false)
  assert.equal(h.posted[0].emails.length,1)
})

test('normal refresh automatically requests smart filtering while scan keeps its own policy', async () => {
  const refresh=harness()
  await refresh.store.start(['fixture@example.test'],'',180,'pool',true,'token_refresh',3)
  assert.equal(refresh.posted[0].smart_refresh,true)
  const scan=harness()
  await scan.store.start(['fixture@example.test'],'',180,'pool',false,'token_check',5)
  assert.equal(scan.checks[0].smart_refresh,undefined)
  assert.equal(scan.checks[0].skip_usable,true)
})

test('following a task from history only loads that exact job and never starts work', async () => {
  const seen=[]
  const h=harness({get:async id=>{seen.push(id);return {job:{...queued,job_id:id,state:'running'}}}})
  await h.store.follow('history-job')
  assert.deepEqual(seen,['history-job'])
  assert.equal(h.storage.get('token_refresh_job_id'),'history-job')
  assert.equal(h.posted.length+h.checks.length+h.cancelled.length,0)
  assert.equal(h.timers.size,1)
})

test('following history cannot discard an unacknowledged stop for another job', async () => {
  const h=harness({}, {token_refresh_cancel_job_id:'stopping-job'})
  await assert.rejects(h.store.follow('other-job'))
  assert.equal(h.storage.get('token_refresh_cancel_job_id'),'stopping-job')
  assert.equal(h.posted.length+h.checks.length+h.cancelled.length,0)
})
