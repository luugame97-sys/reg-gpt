const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const test = require('node:test')
const assert = require('node:assert/strict')
const sfc = fs.readFileSync(path.join(__dirname, '../webui/frontend/src/components/AccountToolbar.vue'), 'utf8')
const script = sfc.split('<script setup>')[1].split('</script>')[0].replace(/^import .*$/gm, '')
function toolbar() {
  const events = []
  const context = {defineProps: () => ({keyword: 'existing'}), defineEmits: () => (name, value) => events.push([name, value]), ref: value => ({value}), watch: () => {}, module: {exports: {}}}
  vm.runInNewContext(script + '\nmodule.exports={searchDraft,commitSearch,clearSearch,resetFilters}', context)
  return {...context.module.exports, events}
}
test('typing does not change the committed scope during background refreshes', () => {
  const m = toolbar()
  m.searchDraft.value = 'new-address'
  assert.equal(m.events.length, 0)
  m.commitSearch()
  assert.deepEqual(m.events, [['update:keyword', 'new-address'], ['apply', undefined]])
})
test('clearing and resetting also discard uncommitted search text', () => {
  const m = toolbar()
  m.searchDraft.value = 'draft'
  m.clearSearch()
  assert.equal(m.searchDraft.value, '')
  assert.deepEqual(m.events[0], ['update:keyword', ''])
  m.searchDraft.value = 'another-draft'
  m.resetFilters()
  assert.equal(m.searchDraft.value, '')
  assert.deepEqual(m.events.at(-1), ['reset-filters', undefined])
})
