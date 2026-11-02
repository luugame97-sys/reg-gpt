const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const test = require('node:test')
const assert = require('node:assert/strict')
const source = fs.readFileSync(path.join(__dirname,'../webui/frontend/src/stores/tasks.js'),'utf8').replace(/^import .*$/gm,'').replace('export const useTasksStore','const useTasksStore')
function harness(api = {}) {
  const timers = new Map(), listeners = new Map(), calls = []; let counter = 0
  const document = {hidden:false,addEventListener:(name,fn)=>listeners.set(name,fn),removeEventListener:name=>listeners.delete(name)}
  const ctx = {defineStore:(_,setup)=>setup,ref:value=>({value}),computed:fn=>({get value(){return fn()}}),document,
    setTimeout:(fn,ms)=>{const id=++counter;timers.set(id,{fn,ms});return id},clearTimeout:id=>timers.delete(id),
    findTokenRefreshJobs:params=>{calls.push(['jobs',params]);return (api.jobs || (async()=>({jobs:[]})))()},
    listRuns:(limit,params)=>{calls.push(['runs',params]);return (api.runs || (async()=>({items:[]})))()},module:{exports:{}}}
  vm.runInNewContext(source+'\nmodule.exports=useTasksStore()',ctx)
  return {store:ctx.module.exports,document,timers,listeners,calls}
}
test('overview requests only summaries and coalesces pending reads',async()=>{
  let resolve
  const h=harness({jobs:()=>new Promise(r=>{resolve=r})})
  const a=h.store.refresh(),b=h.store.refresh()
  assert.equal(h.calls.length,2)
  resolve({jobs:[{state:'running',job_id:'fixture'}]});await Promise.all([a,b])
  assert.equal(h.store.activeJobs.value.length,1)
  assert(h.calls.every(([,params])=>params.summary===true))
})
test('a failed refresh retains the last data and exposes an unknown state',async()=>{
  let fail=false
  const h=harness({jobs:async()=>{if(fail)throw Error('offline');return {jobs:[{state:'running'}]}},runs:async()=>({items:[{run_id:'one'}]})})
  await h.store.refresh();fail=true;await h.store.refresh()
  assert.equal(h.store.jobs.value.length,1)
  assert.equal(h.store.runs.value.length,1)
  assert(h.store.error.value)
})
test('global overview polling pauses in hidden tabs and cleans up on stop',async()=>{
  const h=harness();h.document.hidden=true;h.store.start();await h.store.refresh();await Promise.resolve()
  assert.equal(h.timers.size,0)
  h.document.hidden=false;h.listeners.get('visibilitychange')();await h.store.refresh();await Promise.resolve()
  assert.equal(h.timers.size,1)
  h.store.stop();assert.equal(h.timers.size,0);assert.equal(h.listeners.size,0)
})
test('task details keep verified plan and failure counts visible',()=>{
  const view=fs.readFileSync(path.join(__dirname,'../webui/frontend/src/views/Tasks.vue'),'utf8')
  const ctx={computed:fn=>({get value(){return fn()}}),detail:{value:{counts:{plus_active:3,go_active:2,free:1,plus_eligible:1,unknown:1,error:2}}},fmt:value=>String(value),module:{exports:{}}}
  vm.runInNewContext(view.slice(view.indexOf('const planLabels'),view.indexOf('async function loadDetail'))+'\nmodule.exports=detailPlanSummary',ctx)
  assert.equal(ctx.module.exports.value,'Plus 3 · Go 2 · Free 1 · Free có ưu đãi 1 · Chưa rõ 1 · Lỗi kiểm tra 2')
})
