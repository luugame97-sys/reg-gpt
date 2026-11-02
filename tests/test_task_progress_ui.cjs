const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const test = require('node:test')
const assert = require('node:assert/strict')
const sfc = fs.readFileSync(path.join(__dirname, '../webui/frontend/src/components/AccountTaskProgress.vue'), 'utf8')
const script = sfc.split('<script setup>')[1].split('</script>')[0].replace(/^import .*$/gm, '')
const presentation = fs.readFileSync(path.join(__dirname, '../webui/frontend/src/taskPresentation.js'), 'utf8').replace(/export /g, '')
function model(job, extra = {}) {
  const context = {defineProps: () => ({job, running: true, ...extra}), defineEmits: () => () => {}, ref: value => ({value}), computed: fn => ({get value() {return fn()}}), watch: () => {}, module: {exports: {}}}
  vm.runInNewContext(presentation + '\n' + script + '\nmodule.exports={percent,total,completed,remaining,attention,failures,segments,activeWorkers,trafficTotal,stateLabel}', context)
  return context.module.exports
}
test('global failure totals do not shrink to the recent result window', () => {
  const m = model({state: 'running', total: 4506, completed: 1668, succeeded: 772, failed: 896, remaining: 2838,
    results: Array.from({length: 122}, (_, index) => ({email: 'fixture-' + index, ok: false})), routing: {workers: 20, active_workers: 20}, traffic: {rx: 927000000, tx: 3000000}})
  assert.equal(m.attention.value, 896)
  assert.equal(m.failures.value.length, 122)
  assert.equal(m.percent.value, 37)
  assert.equal(m.activeWorkers.value, 20)
  assert.equal(m.trafficTotal.value, 930000000)
  assert(m.segments.value.reduce((n, item) => n + item.width, 0) < 38)
})
test('AT checks show expired and missing accounts as needing attention', () => {
  const m = model({operation: 'token_check', total: 300, completed: 205, succeeded: 40, failed: 2, skipped: 100,
    counts: {expired_401: 50, banned: 10, unknown: 2, missing: 3}})
  assert.equal(m.attention.value, 65)
  assert.equal(m.remaining.value, 95)
})
test('missing worker counters use the admitted email list', () => {
  const m = model({state: 'running', current_email: 'one@example.test, two@example.test', routing: {workers: 3}})
  assert.equal(m.activeWorkers.value, 2)
})
test('unknown traffic remains unknown and empty jobs have no invalid percentage', () => {
  const m = model(null)
  assert.equal(m.trafficTotal.value, null)
  assert.equal(m.percent.value, 0)
  assert.equal(m.stateLabel.value, 'Chưa kết nối')
})
