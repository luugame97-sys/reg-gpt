const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const test = require('node:test')
const assert = require('node:assert/strict')
const source = fs.readFileSync(path.join(__dirname, '../webui/frontend/src/views/Registered.vue'), 'utf8')
const functions = source.slice(source.indexOf('function atLife(row)'), source.indexOf('const PLUS_TYPE'))
const now = 1800000000000
class Clock extends Date { static now() { return now } }
function status(row, meta = {}) {
  const context = {Date: Clock, metaOf: () => meta, row, result: null}
  vm.runInNewContext(functions + '\nresult = tokenStatus(row)', context)
  return context.result
}

test('a previously valid token becomes expired when its actual date passes', () => {
  const result = status({at_exp: now / 1000 - 86400, token_check: {status: 'valid', checked_at: 1}})
  assert.equal(result.type, 'danger')
  assert.match(result.text, /^Hết hạn \d{2}\/\d{2}\/\d{4}$/)
  assert.match(result.detail, /Quá 1,0 ngày/)
})
test('future tokens show actual expiry and remaining days instead of HTTP 200', () => {
  const result = status({at_exp: now / 1000 + 10 * 86400, token_state: {status: 'unexpired', check_status: 'valid'}})
  assert.match(result.text, /^Hạn \d{2}\/\d{2}\/\d{4}$/)
  assert.match(result.detail, /Còn 10,0 ngày/)
  assert(!result.text.includes('200'))
})
test('current list expiry takes precedence over stale page metadata', () => {
  const result = status({at_exp: now / 1000 + 86400, token_check: {status: 'valid'}}, {at_exp: now / 1000 - 86400})
  assert.equal(result.type, 'success')
  assert.match(result.detail, /Còn/)
})
test('an opaque replacement token does not inherit an old expiry', () => {
  const result = status({at_exp: 0, token_state: {status: 'unknown'}, token_check: {at_exp: now / 1000 - 86400}}, {at_exp: now / 1000 - 86400})
  assert.equal(result.text, 'Chưa rõ hạn')
})
test('a stale raw 401 cannot override the current server classification', () => {
  const result = status({at_exp: now / 1000 + 86400, token_state: {status: 'unexpired'}, token_check: {status: 'expired_401'}})
  assert.match(result.text, /^Hạn /)
})
test('a current 401 is distinguished from a future JWT expiry date', () => {
  const result = status({at_exp: now / 1000 + 86400, token_state: {status: 'rejected'}})
  assert.equal(result.text, 'AT bị từ chối (401)')
  assert.match(result.detail, /^Hạn /)
})
test('missing, opaque usable and locked tokens keep their distinct states', () => {
  assert.equal(status({at_exp: 0, token_state: {status: 'missing'}}).text, 'Chưa có AT')
  assert.equal(status({at_exp: 0, token_state: {status: 'usable'}}).text, 'Dùng được · chưa rõ hạn')
  assert.equal(status({at_exp: now / 1000 - 86400, token_state: {status: 'banned'}}).text, 'Tài khoản bị khóa')
})
