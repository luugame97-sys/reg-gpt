const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict')
const view=fs.readFileSync(path.join(__dirname,'../webui/frontend/src/views/Registered.vue'),'utf8')
function harness(){
 const context={ref:value=>({value}),computed:fn=>({get value(){return fn()}}),module:{exports:{}},
  refreshScope:{value:'filter'},refreshUsable:{value:false},singleTaskEmail:{value:''},tokenJobOperation:{value:'token_refresh'},
  planRetrySource:{value:''},planRetryInfo:{value:null},planRetryEmailOtp:{value:false},
  tokenDialogIsCheck:{value:false},selected:{value:[{email:'chosen@example.test'}]},rows:{value:[{email:'page@example.test'}]},
  total:{value:1},groupFilter:{value:'Folder A'},groupsSummary:{value:{total:900,ungrouped:20,groups:[{name:'Folder A',count:200}]}},
  accountFilterParams:()=>({filter:'token_valid',group:'Folder A',q:'specific',country:'VN'})}
 vm.runInNewContext(view.slice(view.indexOf('const refreshFolderCount'),view.indexOf('let candidatePreviewSequence'))+'\nmodule.exports={refreshCandidateParams,refreshScopeCount,refreshUsableActive}',context)
 return {context,...context.module.exports}
}
const plain=value=>JSON.parse(JSON.stringify(value))

test('plan retry uses the full failed-job scope even with an empty stale selection',async()=>{
 const h=harness(),ctx=h.context,started=[],navigated=[]
 Object.assign(ctx,{refreshProxyMode:{value:'pool'},form:{value:{otpTimeout:180}},proxyText:()=>'',refreshingTokens:{value:false},
  refreshFilterActive:{value:false},tokenDialogIsCheck:{value:true},refreshDialogVisible:{value:true},tokenTaskWorkers:{value:10},checkSkipUsable:{value:true},
  tokenDialogTitle:{value:'Kiểm tra gói'},ElMessage:{info:()=>{},warning:()=>{},error:message=>{throw Error(message)},success:()=>{}},
  getRefreshRetryCandidates:async(id,options)=>{assert.equal(id,'failed-job');assert.equal(options.retry_email_otp,true);return {emails:Array.from({length:231},(_,i)=>`fixture-${i}@example.test`)}},
  collectFilteredEmails:()=>{throw Error('Do not use current filters')},router:{replace:location=>navigated.push(location)},
  tokenRefresh:{start:async(...args)=>{started.push(args);return {job_id:'new-job'}}}})
 ctx.planRetrySource.value='failed-job';ctx.planRetryEmailOtp.value=true;ctx.planRetryInfo.value={total_candidates:231}
 ctx.tokenJobOperation.value='plus_check';ctx.refreshScope.value='selected';ctx.selected.value=[]
 const start=view.indexOf('async function submitBatchRefreshTokens()'),end=view.indexOf('// ── Kiểm tra AT theo hạn JWT',start)
 vm.runInNewContext(view.slice(start,end)+'\nmodule.exports={submitBatchRefreshTokens}',ctx)
 await ctx.module.exports.submitBatchRefreshTokens()
 assert.equal(started.length,1);assert.equal(started[0][0].length,231)
 assert.equal(started[0][5],'plus_check');assert.equal(started[0][9],'failed-job');assert.equal(started[0][12],true)
 assert.equal(navigated[0].query.job,'new-job');assert.equal(ctx.refreshDialogVisible.value,false)
})

test('folder and all scopes ignore visual filters and cannot inherit a manual refresh choice',()=>{
 const h=harness();h.context.refreshUsable.value=true
 h.context.refreshScope.value='folder'
 assert.deepEqual(plain(h.refreshCandidateParams()),{filter:'all',group:'Folder A',include_missing:true,smart_refresh:true,refresh_usable:false})
 assert.equal(h.refreshScopeCount.value,200)
 h.context.refreshScope.value='all'
 assert.deepEqual(plain(h.refreshCandidateParams()),{filter:'all',include_missing:true,smart_refresh:true,refresh_usable:false})
 assert.equal(h.refreshScopeCount.value,900)
 h.context.refreshScope.value='folder';h.context.groupFilter.value='__ungrouped__'
 assert.equal(h.refreshScopeCount.value,20)
})

test('filtered scope retains all filters while selected and single accounts retain only explicit emails',()=>{
 const h=harness()
 assert.equal(h.refreshCandidateParams().q,'specific')
 h.context.refreshScope.value='selected';h.context.refreshUsable.value=true
 const selected=plain(h.refreshCandidateParams())
 assert.deepEqual(selected.emails,['chosen@example.test'])
 assert.equal(selected.filter,'all');assert.equal(selected.group,undefined);assert.equal(selected.q,undefined)
 assert.equal(selected.refresh_usable,true)
 h.context.refreshScope.value='single';h.context.singleTaskEmail.value='single@example.test'
 assert.deepEqual(plain(h.refreshCandidateParams().emails),['single@example.test'])
 assert.equal(h.refreshScopeCount.value,1)
 h.context.refreshScope.value='page'
 assert.deepEqual(plain(h.refreshCandidateParams().emails),['page@example.test'])
 assert.equal(h.refreshCandidateParams().refresh_usable,false)
})

test('the individual refresh action enables manual mode without starting work',()=>{
 const h=harness(),ctx=h.context
 ctx.refreshDialogVisible={value:false};ctx.refreshProxyMode={value:'pool'}
 vm.runInNewContext(view.slice(view.indexOf('function openSingleTask('),view.indexOf('async function stopTokenRefresh('))+'\nmodule.exports={doSingleRefresh}',ctx)
 ctx.module.exports.doSingleRefresh({email:'single@example.test'})
 assert.equal(ctx.refreshScope.value,'single')
 assert.equal(ctx.refreshDialogVisible.value,true)
 assert.equal(h.refreshCandidateParams().refresh_usable,true)
})

test('submit sends the full eligible batch and manual choice only for an explicit selection',async()=>{
 const h=harness(),ctx=h.context,started=[]
 Object.assign(ctx,{refreshProxyMode:{value:'pool'},form:{value:{otpTimeout:180}},proxyText:()=>'',refreshingTokens:{value:false},
  refreshFilterActive:{value:true},refreshDialogVisible:{value:true},tokenTaskWorkers:{value:3},checkSkipUsable:{value:true},
  tokenDialogTitle:{value:'Làm mới AT'},ElMessage:{info:()=>{},warning:()=>{},error:message=>{throw Error(message)},success:()=>{}},
  requestRefreshCandidateInfo:async()=>({emails:Array.from({length:135},(_,i)=>`fixture-${i}@example.test`)}),tokenRefresh:{start:async(...args)=>started.push(args)}})
 const start=view.indexOf('async function submitBatchRefreshTokens()'),end=view.indexOf('// ── Kiểm tra AT theo hạn JWT',start)
 vm.runInNewContext(view.slice(start,end)+'\nmodule.exports={submitBatchRefreshTokens}',ctx)
 ctx.refreshScope.value='all';ctx.refreshUsable.value=true
 await ctx.module.exports.submitBatchRefreshTokens()
 assert.equal(started[0][0].length,135)
 assert.equal(started[0][4],true);assert.equal(started[0][11],false)
 ctx.refreshScope.value='selected'
 await ctx.module.exports.submitBatchRefreshTokens()
 assert.equal(started[1][4],false);assert.equal(started[1][11],true)
})
