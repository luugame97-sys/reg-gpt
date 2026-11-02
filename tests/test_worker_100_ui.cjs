const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path'),test=require('node:test'),assert=require('node:assert/strict')
const view=fs.readFileSync(path.join(__dirname,'../webui/frontend/src/views/Registered.vue'),'utf8')
function workerSettings(saved){
 const storage=new Map([['registered_task_workers',JSON.stringify(saved)]]),ctx={
  localStorage:{getItem:key=>storage.get(key),setItem:(key,value)=>storage.set(key,value)},ref:value=>({value}),
  computed:definition=>({get value(){return definition.get()},set value(value){definition.set(value)}}),tokenJobOperation:{value:'token_refresh'},module:{exports:{}}}
 vm.runInNewContext(view.slice(view.indexOf('let savedTaskWorkers'),view.indexOf('const tokenDialogIsCheck'))+'\nmodule.exports={taskWorkerSettings,tokenTaskWorkers}',ctx)
 return {...ctx.module.exports,storage}
}
test('saved concurrency above 20 survives reload and remains capped at 100',()=>{
 const m=workerSettings({token_refresh:80,token_check:100})
 assert.equal(m.tokenTaskWorkers.value,80)
 assert.equal(m.taskWorkerSettings.value.token_check,100)
 m.tokenTaskWorkers.value=100
 assert.equal(JSON.parse(m.storage.get('registered_task_workers')).token_refresh,100)
 m.tokenTaskWorkers.value=101
 assert.equal(m.tokenTaskWorkers.value,100)
 m.tokenTaskWorkers.value=0
 assert.equal(m.tokenTaskWorkers.value,1)
})
test('new task settings keep their existing defaults',()=>{
 const m=workerSettings({})
 assert.equal(m.tokenTaskWorkers.value,3)
 assert.equal(m.taskWorkerSettings.value.token_check,5)
 assert.equal(m.taskWorkerSettings.value.checkout_check,1)
})
