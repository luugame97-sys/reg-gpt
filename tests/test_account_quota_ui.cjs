const test = require('node:test')
const assert = require('node:assert/strict')
const { pathToFileURL } = require('node:url')
const path = require('node:path')
const mod = import(pathToFileURL(path.join(__dirname, '../webui/frontend/src/accountQuota.js')).href)
const snapshot = (used = 0) => ({ status: 'quota_ok', buckets: [{key:'rate_limit', label:'Codex / Work', windows:[{key:'primary', used_percent:used, remaining_percent:100-used, reset_at:2000, limit_window_seconds:18000}]}] })

test('zero is valid usage; null, NaN and absent usage never become zero', async () => {
  const { quotaSummary, quotaPercent } = await mod
  assert.equal(quotaSummary(snapshot(), 1000).windows[0].remaining_percent, 100)
  assert.equal(quotaSummary(null).success, false)
  assert.equal(quotaPercent(null), '—')
  assert.equal(quotaPercent(NaN), '—')
  assert.equal(quotaPercent(0), '0%')
  assert.equal(quotaPercent(87.65), '87.7%')
  assert.equal(quotaSummary(snapshot(null)).success, false)
})
test('reset expiration and token changes require a recheck without resetting the saved usage', async () => {
  const { quotaSummary } = await mod
  for (const check of [snapshot(42), {...snapshot(42), stale:true}]) {
    const result = quotaSummary(check, 2000001)
    assert.equal(result.stale, true)
    assert.equal(result.windows[0].remaining_percent, 58)
  }
})
test('failed retry preserves the last result; a failed first attempt has no usable percentage', async () => {
  const { quotaSummary } = await mod
  const failed = {status:'error',message:'HTTP 403'}
  const result = quotaSummary({...snapshot(30),last_error:failed}, 1000)
  assert.equal(result.previous, true)
  assert.equal(result.error, failed)
  assert.equal(result.windows[0].remaining_percent, 70)
  assert.equal(quotaSummary(failed).success, false)
})
test('different returned windows and code review stay separate; durations are not hardcoded', async () => {
  const { quotaSummary, quotaWindows, quotaDuration } = await mod
  const check=snapshot(20)
  check.buckets[0].windows.push({key:'secondary',used_percent:80,remaining_percent:20,limit_window_seconds:604800})
  check.buckets.push({key:'code_review_rate_limit',label:'Code review',windows:[{key:'primary',used_percent:100,remaining_percent:0}]})
  assert.equal(quotaSummary(check, 1000).windows.length,2)
  assert.equal(quotaWindows(check).length,3)
  assert.deepEqual(quotaDuration(18000),{value:5,unit:'giờ'})
  assert.deepEqual(quotaDuration(2592000),{value:30,unit:'ngày'})
  assert.equal(quotaDuration(null),null)
})

test('remaining quota drives the bar and low quota colors; missing data stays unknown', async () => {
  const { quotaBar } = await mod
  assert.deepEqual(quotaBar({remaining_percent:100}), {known:true,width:100,tone:'good'})
  assert.deepEqual(quotaBar({remaining_percent:3}), {known:true,width:3,tone:'danger'})
  assert.equal(quotaBar({remaining_percent:25}).tone, 'warning')
  assert.equal(quotaBar({remaining_percent:0}).width, 0)
  for (const value of [null, undefined, NaN, -1, '3', true]) {
    assert.deepEqual(quotaBar({remaining_percent:value}), {known:false,width:0,tone:'unknown'})
  }
})

test('reset countdown shows server snapshot time and never invents a reset or 100% remaining', async () => {
  const { quotaResetCountdown, quotaSummary } = await mod
  const now = 100000000
  const at = seconds => (now / 1000 + seconds)
  assert.deepEqual(quotaResetCountdown(at(4*3600+26*60), now), {state:'future',text:'4h 26m'})
  assert.deepEqual(quotaResetCountdown(at(3*86400+20*3600), now), {state:'future',text:'3d 20h'})
  assert.equal(quotaResetCountdown(at(59),now).text, '<1m')
  assert.equal(quotaResetCountdown(at(0),now).state, 'passed')
  assert.equal(quotaResetCountdown(null,now).state, 'unknown')
  assert.equal(quotaSummary(snapshot(97),now).windows[0].remaining_percent,3)
})

test('subscription expiry requires verified paid plan evidence and never uses quota reset', async () => {
  const { quotaSubscriptionExpiry } = await mod
  const now = Date.UTC(2026,9,31,10)
  const expires = Date.UTC(2026,11,1,10)
  const plan = {membership_verified:true,plan_type:'plus',expires_at:new Date(expires).toISOString()}
  assert.deepEqual(quotaSubscriptionExpiry(plan,now), {expiresAt:expires/1000,days:31,expired:false})
  assert.equal(quotaSubscriptionExpiry({...plan,expires_at:expires/1000},now).days,31)
  assert.equal(quotaSubscriptionExpiry({...plan,expires_at:expires},now).days,31)
  assert.equal(quotaSubscriptionExpiry({...plan,expires_at:now/1000},now).expired,true)
  for (const input of [null, {...plan,membership_verified:false}, {...plan,plan_type:'free'}, {...plan,expires_at:'invalid'}, {membership_verified:true,plan_type:'plus',reset_at:expires/1000}]) {
    assert.equal(quotaSubscriptionExpiry(input,now),null)
  }
})
