const { test } = require('node:test')
const assert = require('node:assert/strict')
const { pathToFileURL } = require('node:url')
const path = require('node:path')
const source = pathToFileURL(path.resolve(__dirname, '../webui/frontend/src/upi.js')).href

test('account selection traverses all filtered pages and skips unusable ATs', async () => {
  const { collectUpiAccounts } = await import(source)
  const calls = [], progress = []
  const rows = Array.from({length:205}, (_,i) => ({email:`account-${i}@example.test`,usable:i%2===0}))
  const selected = await collectUpiAccounts(async params => {
    calls.push(params)
    return {total:rows.length,items:rows.slice(params.page*params.size,(params.page+1)*params.size)}
  }, {query:'account',group:'Folder'}, {onProgress:value=>progress.push(value.loaded)})
  assert.equal(selected.length,103)
  assert.equal(selected.at(-1),'account-204@example.test')
  assert.deepEqual(progress,[100,200,205])
  assert.ok(calls.every(x=>x.query==='account' && x.group==='Folder' && x.size===100))
})

test('account selection refuses partial, drifting, duplicate and excessive results', async () => {
  const { collectUpiAccounts } = await import(source)
  for (const load of [
    async ()=>({total:2,items:[]}),
    async p=>({total:p.page?3:2,items:[{email:`${p.page}@example.test`,usable:true}]}),
    async ()=>({total:2,items:[{email:'same@example.test',usable:true}]}),
    async ()=>({total:20001,items:[]}),
  ]) await assert.rejects(collectUpiAccounts(load,{}))
})

test('closing selection cancels without returning a partial list', async () => {
  const { collectUpiAccounts } = await import(source)
  let active=true
  await assert.rejects(collectUpiAccounts(async()=>{
    active=false
    return {total:1,items:[{email:'a@example.test',usable:true}]}
  },{}, {isActive:()=>active}), /hủy/)
  assert.deepEqual(await collectUpiAccounts(async()=>({total:0,items:[]}),{}),[])
})
