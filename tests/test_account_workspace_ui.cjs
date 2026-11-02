const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path')
const source=fs.readFileSync(path.join(__dirname,'../webui/frontend/src/accountFilters.js'),'utf8').replace(/export /g,'')
function helpers(){const ctx={module:{exports:{}}};vm.runInNewContext(source+'\nmodule.exports={readSavedAccountViews}',ctx);return ctx.module.exports}
test('saved filter recovery rejects corrupt or unknown scopes',()=>{
 const {readSavedAccountViews}=helpers()
 const valid={id:'one',name:'Review Plus',plans:['plan_plus','plan_pro'],tokens:['token_invalid'],errors:[],group:'source',country:'all',keyword:'',dates:['2026-10-01','2026-10-26']}
 assert.equal(readSavedAccountViews(JSON.stringify([valid,{...valid,id:'bad',plans:['unknown-filter']}])).length,1)
 assert.equal(readSavedAccountViews('{invalid').length,0)
 assert.equal(readSavedAccountViews(JSON.stringify([{...valid,dates:['tomorrow','yesterday']}])).length,0)
})
test('legacy promotion checks never masquerade as unperformed checks or verified paid plans',()=>{
 const view=fs.readFileSync(path.join(__dirname,'../webui/frontend/src/views/Registered.vue'),'utf8')
 const ctx={module:{exports:{}}};vm.runInNewContext(view.slice(view.indexOf('function plusOf(row)'),view.indexOf('function planTooltip'))+'\nmodule.exports={plusOf,planEvidenceLabel}',ctx)
 const {plusOf,planEvidenceLabel}=ctx.module.exports
 assert.equal(plusOf({plus_check:{status:'free',label:'Free',checked_at:1,trial_eligible:false}}).label,'Đã dò ưu đãi')
 assert.equal(plusOf({plus_check:{status:'plus_eligible',checked_at:1,trial_eligible:true}}).label,'Có ưu đãi Plus')
 assert.equal(plusOf({plus_check:{status:'plus_active',label:'Plus',membership_verified:true}}).label,'Plus')
 assert.match(planEvidenceLabel({plus_check:{status:'free',checked_at:1,trial_eligible:false}}),/chưa xác minh gói/)
})
