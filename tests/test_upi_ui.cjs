const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { pathToFileURL } = require('node:url')
const moduleUrl = pathToFileURL(path.resolve(__dirname, '../webui/frontend/src/upi.js')).href

test('only an eligible failed Camellia task offers a new link', async () => {
  const {canRenewUpiTask:can}=await import(moduleUrl)
  const eligible={provider:'local',phase:'failed',renewal:{eligible:true}}
  assert.equal(can(eligible),true)
  for(const row of [null,{}, {...eligible,provider:'ytc'},{...eligible,phase:'uncertain'}, {...eligible,phase:'scanning'}, {...eligible,renewal:{eligible:false}}]) assert.equal(can(row),false)
})

test('new link API is scoped to Camellia and never calls submit with an old payment link', () => {
  const vm=require('node:vm'),calls=[]
  const source=fs.readFileSync(path.resolve(__dirname,'../webui/frontend/src/api/upi.js'),'utf8')
  const h={http:{get:(...args)=>calls.push(['GET',...args]),post:(...args)=>calls.push(['POST',...args])},module:{exports:{}}}
  vm.runInNewContext(source.replace(/^import .*$/m,'').replaceAll('export const ','const ')+'\nmodule.exports={previewUpiNewLink,createUpiNewLink}',h)
  h.module.exports.previewUpiNewLink('a/b')
  h.module.exports.createUpiNewLink('a/b',{confirmed:true,request_id:'same-id',unit_points:5})
  assert.ok(calls.every(c=>c[1].endsWith('/a%2Fb/new-link') && c.at(-1).params.provider==='local'))
  assert.equal(calls[1][2].confirmed,true)
  assert.equal(calls[1][2].payment_url,undefined)
})

test('new link confirmation blocks duplicate clicks and keeps the request ID after a lost response', async () => {
  const vm=require('node:vm'),calls=[],messages=[]
  const source=fs.readFileSync(path.resolve(__dirname,'../webui/frontend/src/views/Upi.vue'),'utf8')
  const h={provider:{value:'local'},active:true,renewalSending:{value:false},renewalConsent:{value:false},renewalOpen:{value:true},
    renewalQuote:{value:{source_task_id:'old',unit_points:5}},renewalRequest:{value:'persistent-uuid'},renewalToken:{value:''},
    detail:{value:null},detailOpen:{value:false},filter:{value:'failed'},page:{value:2},clearTaskSelection:()=>{},refresh:async()=>{},
    ElMessage:{success:x=>messages.push(x),error:x=>messages.push(x)},errorText:e=>e.message,t:x=>x,module:{exports:{}},
    createUpiNewLink:(...args)=>new Promise((resolve,reject)=>calls.push({args,resolve,reject}))}
  vm.runInNewContext(source.slice(source.indexOf('async function submitRenewal()'),source.indexOf('async function act('))+'\nmodule.exports=submitRenewal',h)
  const submit=h.module.exports
  await submit();assert.equal(calls.length,0)
  h.renewalConsent.value=true
  const first=submit();await submit();assert.equal(calls.length,1)
  calls[0].reject(new Error('lost response'));await first
  assert.equal(h.renewalOpen.value,true);assert.equal(h.renewalSending.value,false)
  const second=submit();assert.equal(calls[1].args[1].request_id,calls[0].args[1].request_id)
  calls[1].resolve({task:{id:'child'}});await second
  assert.equal(h.renewalOpen.value,false);assert.equal(h.detail.value.id,'child');assert.equal(h.page.value,1)
  h.provider.value='ytc';await submit();assert.equal(calls.length,2)
})

test('NEW scan marker survives reloads without expiry and contains no account data', async () => {
  const { upiScanBatch } = await import(moduleUrl)
  const first = upiScanBatch(null, 1000)
  assert.deepEqual(first, {version:1,requestId:'',startedAt:1000})
  assert.deepEqual(upiScanBatch(JSON.stringify(first), 500000), first)
  assert.deepEqual(upiScanBatch({...first,email:'private',access_token:'secret'}), first)
  for (const raw of ['invalid', 'null', '{"version":1}', {version:1,requestId:'x',startedAt:NaN}, {version:1,requestId:'x',startedAt:-1}]) {
    assert.deepEqual(upiScanBatch(raw, 2000), {version:1,requestId:'',startedAt:2000})
  }
})

test('each UPI action carries an explicit provider and defaults preserve YTC callers', () => {
  const vm=require('node:vm'),calls=[]
  const source=fs.readFileSync(path.resolve(__dirname,'../webui/frontend/src/api/upi.js'),'utf8')
  const h={http:{get:(...args)=>calls.push(['GET',...args]),post:(...args)=>calls.push(['POST',...args])},module:{exports:{}}}
  vm.runInNewContext(source.replace(/^import .*$/m,'').replaceAll('export const ','const ')+'\nmodule.exports={submitUpi,controlUpiTask,reconcileUpiScan,getUpiTask}',h)
  h.module.exports.submitUpi('original-batch','local')
  h.module.exports.controlUpiTask('original-task','stop','local')
  h.module.exports.reconcileUpiScan('original-task','local')
  h.module.exports.getUpiTask('ytc-task')
  assert.deepEqual(calls.map(c=>c.at(-1).params.provider),['local','local','local','ytc'])
  assert.equal(calls[0][2].request_id,'original-batch')
  assert.equal(calls[1][2].confirmed,true)
})

test('late balances and pending requests from the previous provider cannot replace current data', async () => {
  const vm=require('node:vm'),source=fs.readFileSync(path.resolve(__dirname,'../webui/frontend/src/views/Upi.vue'),'utf8')
  const pending=[]
  const h={provider:{value:'ytc'},active:true,summary:{value:{account:'current'}},pending:{value:['current']},taskError:{value:''},errorText:e=>e.message,module:{exports:{}},
    getUpiSummary:()=>new Promise(resolve=>pending.push(resolve)),getUpiRequests:()=>new Promise(resolve=>pending.push(resolve))}
  vm.runInNewContext(source.slice(source.indexOf('async function loadSummary('),source.indexOf('async function refresh('))+'\nmodule.exports={loadSummary,loadPending}',h)
  const balance=h.module.exports.loadSummary(),requests=h.module.exports.loadPending()
  h.provider.value='local'
  pending[0]({account:'old-ytc'});pending[1]({items:['old-ytc']})
  await Promise.all([balance,requests])
  assert.equal(h.summary.value.account,'current');assert.deepEqual(h.pending.value,['current'])
})

test('NEW requires successful scanning after the current batch marker, never only a checkout link', async () => {
  const { isNewUpiScan } = await import(moduleUrl)
  const batch={version:1,requestId:'batch-a',startedAt:1000}
  assert.equal(isNewUpiScan({phase:'completed',scan_succeeded_at:1000},batch),true)
  assert.equal(isNewUpiScan({phase:'completed',scan_succeeded_at:1001},batch),true)
  assert.equal(isNewUpiScan({phase:'completed',scan_succeeded_at:999},batch),false)
  for (const phase of ['queued','running','scanning','link_ready','uncertain','failed','stopped']) {
    assert.equal(isNewUpiScan({phase,scan_succeeded_at:1001},batch),false)
  }
  for (const at of [undefined,null,'1001',NaN,Infinity]) {
    assert.equal(isNewUpiScan({phase:'completed',scan_succeeded_at:at},batch),false)
  }
})

test('submitting a new batch clears previous NEW labels while retrying its request preserves them', async () => {
  const { upiScanBatch,beginUpiScanBatch,isNewUpiScan }=await import(moduleUrl)
  const initial=upiScanBatch(null,1000),first=beginUpiScanBatch(initial,'batch-a',1100)
  const done={phase:'completed',scan_succeeded_at:1150}
  assert.equal(isNewUpiScan(done,first),true)
  assert.equal(beginUpiScanBatch(first,'batch-a',1200),first)
  assert.equal(beginUpiScanBatch(first,'',1200),first)
  const second=beginUpiScanBatch(first,'batch-b',1300)
  assert.equal(isNewUpiScan(done,second),false)
  assert.equal(isNewUpiScan({...done,scan_succeeded_at:1301},second),true)
  assert.deepEqual(upiScanBatch(JSON.stringify(second)),second)
})

test('browser persistence stores only the NEW marker and storage errors never block UPI', async () => {
  const vm=require('node:vm'),{upiScanBatch,beginUpiScanBatch,UPI_NEW_SCAN_KEY}=await import(moduleUrl)
  const source=fs.readFileSync(path.resolve(__dirname,'../webui/frontend/src/views/Upi.vue'),'utf8')
  const writes=[],current={version:1,requestId:'old',startedAt:1000}
  const context={upiScanBatch,beginUpiScanBatch,UPI_NEW_SCAN_KEY,newScanBatch:{value:current},module:{exports:{}},
    localStorage:{getItem:()=>JSON.stringify({...current,access_token:'must-not-store',email:'private@example.test'}),setItem:(key,value)=>writes.push({key,value})}}
  vm.runInNewContext(source.slice(source.indexOf('function readScanBatch('),source.indexOf('const accountFor ='))+'\nmodule.exports={readScanBatch,startScanBatch,syncScanBatch}',context)
  assert.deepEqual(context.module.exports.readScanBatch(),current)
  context.module.exports.startScanBatch('new-request')
  assert.equal(writes.length,2)
  for (const {key,value} of writes) {
    assert.equal(key,UPI_NEW_SCAN_KEY)
    assert.deepEqual(Object.keys(JSON.parse(value)).sort(),['requestId','startedAt','version'])
    assert.equal(value.includes('must-not-store'),false);assert.equal(value.includes('@'),false)
  }
  const marker=context.newScanBatch.value
  context.localStorage.getItem=()=>{throw new Error('Storage unavailable')}
  context.localStorage.setItem=()=>{throw new Error('Storage unavailable')}
  assert.equal(context.module.exports.readScanBatch(marker),marker)
  assert.doesNotThrow(()=>context.module.exports.startScanBatch('another-request'))
  context.module.exports.syncScanBatch({key:UPI_NEW_SCAN_KEY,newValue:JSON.stringify(current)})
  assert.deepEqual(context.newScanBatch.value,current)
})

test('status polling reuses unchanged rows and replaces only actual changes or order', async () => {
  const { reuseUpiTasks } = await import(moduleUrl)
  const a={id:'a',phase:'queued',control:{pending:false}},b={id:'b',phase:'completed'},previous=[a,b]
  assert.equal(reuseUpiTasks(previous,JSON.parse(JSON.stringify(previous))),previous)
  const changed=reuseUpiTasks(previous,[{...a,phase:'running'},{...b}])
  assert.notEqual(changed,previous);assert.notEqual(changed[0],a);assert.equal(changed[1],b)
  const reordered=reuseUpiTasks(previous,[{...b},{...a}])
  assert.equal(reordered[0],b);assert.equal(reordered[1],a)
  assert.deepEqual(reuseUpiTasks(previous,[]),[])
})

async function pollingModel() {
  const vm=require('node:vm'),{reuseUpiTasks}=await import(moduleUrl)
  const source=fs.readFileSync(path.resolve(__dirname,'../webui/frontend/src/views/Upi.vue'),'utf8')
  const context={config:{value:{api_key_set:true}},configured:{value:true},provider:{value:'ytc'},taskSequence:0,active:true,loading:{value:false},syncing:{value:false},
    controlBusy:{value:''},rowBusy:{value:''},page:{value:1},pageSize:{value:25},filter:{value:''},search:{value:''},date:{value:''},
    rows:{value:[{id:'a',email:'fixture@example.test',phase:'queued',control:{pending:false}}]},total:{value:1},counts:{value:{}},
    selectedTaskIds:{value:['a']},selectedTaskCache:{value:{}},controlResult:{value:null},updatedAt:{value:0},taskError:{value:''},requests:[],accountReads:[],reuseUpiTasks,
    errorText:error=>error.message,module:{exports:{}}}
  context.selectableTasks={get value(){return context.rows.value}}
  context.getUpiTasks=()=>new Promise((resolve,reject)=>context.requests.push({resolve,reject}))
  context.loadAccounts=async force=>{context.accountReads.push(force)}
  vm.runInNewContext(source.slice(source.indexOf('async function loadTasks('),source.indexOf('async function loadSummary('))+'\nmodule.exports=loadTasks',context)
  return context
}

test('automatic status reads never cover the table, disable controls or reload cached credentials', async () => {
  const h=await pollingModel(),old=h.rows.value,job=h.module.exports({background:true})
  assert.equal(h.loading.value,false);assert.equal(h.syncing.value,true)
  h.requests[0].resolve({items:JSON.parse(JSON.stringify(old)),total:1,filter_counts:{ACTIVE:1}})
  await job
  assert.equal(h.rows.value,old);assert.equal(h.syncing.value,false);assert.equal(h.loading.value,false)
  assert.deepEqual(h.accountReads,[false]);assert.deepEqual(Array.from(h.selectedTaskIds.value),['a'])
  assert.ok(h.updatedAt.value>0)
})

test('polling is skipped while busy and cannot overwrite commands started during a slow read', async () => {
  const h=await pollingModel()
  h.loading.value=true;await h.module.exports({background:true});assert.equal(h.requests.length,0)
  h.loading.value=false
  const old=h.rows.value,job=h.module.exports({background:true})
  await h.module.exports({background:true});assert.equal(h.requests.length,1)
  h.controlBusy.value='pause'
  h.requests[0].resolve({items:[{id:'a',phase:'queued'}],total:1,filter_counts:{}})
  await job
  assert.equal(h.rows.value,old);assert.equal(h.accountReads.length,0);assert.equal(h.syncing.value,false)
})

test('explicit refresh stays busy until account reads finish and older responses never replace newer results', async () => {
  const h=await pollingModel()
  let finishAccounts;h.loadAccounts=()=>new Promise(resolve=>{finishAccounts=resolve})
  const manual=h.module.exports({reloadAccounts:true})
  assert.equal(h.loading.value,true)
  h.requests[0].resolve({items:h.rows.value,total:1,filter_counts:{}})
  await new Promise(resolve=>setImmediate(resolve));assert.equal(h.loading.value,true)
  finishAccounts();await manual;assert.equal(h.loading.value,false)
  h.loadAccounts=async()=>{}
  const older=h.module.exports({background:true}),newer=h.module.exports()
  h.requests[2].resolve({items:[{id:'new',control:{pending:false}}],total:1,filter_counts:{}});await newer
  h.requests[1].resolve({items:[{id:'old',control:{pending:false}}],total:1,filter_counts:{}});await older
  assert.equal(h.rows.value[0].id,'new');assert.equal(h.loading.value,false);assert.equal(h.syncing.value,false)
})

test('failed background reads retain the list, report the error and release their busy state', async () => {
  const h=await pollingModel(),old=h.rows.value,job=h.module.exports({background:true})
  h.requests[0].reject(new Error('Fixture read timed out'));await job
  assert.equal(h.rows.value,old);assert.equal(h.taskError.value,'Fixture read timed out')
  assert.equal(h.syncing.value,false);assert.equal(h.loading.value,false)
})

test('slow polls coalesce and an explicit refresh waits before reading current data', async () => {
  const vm=require('node:vm'),source=fs.readFileSync(path.resolve(__dirname,'../webui/frontend/src/views/Upi.vue'),'utf8')
  const context={active:true,refreshing:null,calls:[],pending:[],loadPending:async()=>{},loadAutomation:async()=>{},loadSummary:async()=>{},module:{exports:{}}}
  context.loadTasks=args=>{context.calls.push(args);return new Promise(resolve=>context.pending.push(resolve))}
  vm.runInNewContext(source.slice(source.indexOf('async function refresh('),source.indexOf('async function loadAutomation('))+'\nmodule.exports=refresh',context)
  const poll=context.module.exports(false,{background:true})
  await context.module.exports(false,{background:true})
  const manual=context.module.exports(true)
  assert.equal(context.calls.length,1)
  context.pending[0]();await poll;await new Promise(resolve=>setImmediate(resolve))
  assert.equal(context.calls.length,2)
  assert.deepEqual(JSON.parse(JSON.stringify(context.calls)),[{reloadAccounts:false,background:true},{reloadAccounts:true,background:false}])
  context.pending[1]();await manual;assert.equal(context.refreshing,null)
})

test('returning to the tab updates status silently without forcing account credential reads', () => {
  const vm=require('node:vm'),source=fs.readFileSync(path.resolve(__dirname,'../webui/frontend/src/views/Upi.vue'),'utf8')
  const context={active:true,document:{hidden:false},credentialClock:()=>{},calls:[],refresh:(...args)=>context.calls.push(args),module:{exports:{}}}
  vm.runInNewContext(source.slice(source.indexOf('function visibilityChanged()'),source.indexOf('function stop()'))+'\nmodule.exports=visibilityChanged',context)
  context.module.exports();assert.deepEqual(JSON.parse(JSON.stringify(context.calls)),[[false,{background:true}]])
  context.document.hidden=true;context.module.exports();assert.equal(context.calls.length,1)
})

test('UPI account links preserve the target email without credentials', async () => {
  const { upiAccountRoute, upiAccountEmail } = await import(moduleUrl)
  assert.deepEqual(upiAccountRoute(' A.Tag+upi@example.test '), {path:'/registered',query:{email:'a.tag+upi@example.test'}})
  assert.deepEqual(upiAccountRoute(' A.Tag+upi@example.test ',true), {path:'/registered',query:{email:'a.tag+upi@example.test',refresh:'force'}})
  for (const input of ['', null, ['a@example.test'], 'bad\n@example.test', 'not-email', 'a'.repeat(255)+'@example.test']) {
    assert.equal(upiAccountEmail(input),'')
    assert.deepEqual(upiAccountRoute(input),{path:'/registered'})
  }
})

test('UPI account display keeps only login fields and verified membership, never provider/payment evidence', async () => {
  const { upiAccountFields } = await import(moduleUrl)
  const raw={email:'A@example.test',password:'fixture-password',totp_secret:'fixture-secret',group_name:'Done',
    access_token:'must-not-retain-at',refresh_token:'must-not-retain-rt',session_token:'must-not-retain-session',
    extra:{other_secret:'must-not-retain-extra',plus_check:{label:'Plus',membership_verified:false}}}
  const account=upiAccountFields(raw,'a@example.test')
  assert.equal(account.plan_label,'Chưa xác minh gói')
  assert.deepEqual(Object.keys(account).sort(),['email','group_name','password','plan_checked_at','plan_label','plan_verified','totp_secret'])
  assert.equal(JSON.stringify(account).includes('must-not-retain'),false)
  raw.extra.plus_check.membership_verified=true
  assert.equal(upiAccountFields(raw,'a@example.test').plan_label,'Plus')
  assert.throws(()=>upiAccountFields(raw,'b@example.test'),/email/)
})

test('UPI account reads deduplicate canonical emails and isolate missing, failing and mismatched rows', async () => {
  const { loadUpiAccounts } = await import(moduleUrl)
  const calls=[],results={}
  await loadUpiAccounts(['A@example.test','a@example.test','missing@example.test','failed@example.test','wrong@example.test','invalid'],async email=>{
    calls.push(email)
    if(email==='missing@example.test')throw Object.assign(new Error('missing'),{status:404})
    if(email==='failed@example.test')throw Object.assign(new Error('private provider response'),{status:503})
    return {data:{email:email==='wrong@example.test'?'other@example.test':email,password:'fixture'}}
  },{onResult:(email,result)=>{results[email]=result}})
  assert.equal(calls.length,4)
  assert.equal(results['a@example.test'].state,'ready')
  assert.deepEqual(results['missing@example.test'],{state:'missing'})
  assert.deepEqual(results['failed@example.test'],{state:'error'})
  assert.deepEqual(results['wrong@example.test'],{state:'error'})
  assert.equal(JSON.stringify(results).includes('private provider response'),false)
})

test('UPI limits account reads to four in flight and discards results after leaving the page', async () => {
  const { loadUpiAccounts } = await import(moduleUrl)
  const emails=Array.from({length:12},(_,i)=>`fixture-${i}@example.test`)
  let inFlight=0,peak=0,total=0
  await loadUpiAccounts(emails,async email=>{
    total++;inFlight++;peak=Math.max(peak,inFlight)
    await new Promise(setImmediate);inFlight--
    return {data:{email}}
  })
  assert.equal(total,12);assert.equal(peak,4)
  let active=true,calls=0,delivered=0
  await loadUpiAccounts(emails,async email=>{
    calls++;await new Promise(setImmediate);active=false;return {data:{email}}
  },{isActive:()=>active,onResult:()=>{delivered++}})
  assert.equal(calls,4);assert.equal(delivered,0)
})

test('UPI account navigation clears old account filters while keeping job restoration', () => {
  const vm=require('node:vm')
  const source=fs.readFileSync(path.resolve(__dirname,'../webui/frontend/src/views/Registered.vue'),'utf8')
  const block=source.slice(source.indexOf('function openRouteContext()'),source.indexOf('watch(() => route.query'))
  const context={route:{query:{email:' A+upi@example.test ',view:'paid'}},filter:{value:'at_needs_refresh'},
    groupFilter:{value:'Old folder'},countryFilter:{value:'US'},dateRange:{value:['2026-10-01','2026-10-31']},
    keyword:{value:'old-search'},ERROR_FILTERS:[],restored:0,tokenRefresh:{restore:()=>{context.restored++}},module:{exports:null}}
  vm.runInNewContext(block+'\nmodule.exports=openRouteContext',context)
  assert.equal(context.module.exports(),true)
  for(const name of ['filter','groupFilter','countryFilter'])assert.equal(context[name].value,'all')
  assert.equal(context.dateRange.value,null);assert.equal(context.keyword.value,'a+upi@example.test');assert.equal(context.restored,1)
  const opened=[];context.doSingleRefresh=row=>opened.push(row.email)
  context.route.query={email:' Unexpired@example.test ',refresh:'force'}
  assert.equal(context.module.exports(),true);assert.deepEqual(opened,['unexpired@example.test'])
  context.route.query={email:['invalid@example.test'],view:'paid'}
  assert.equal(context.module.exports(),false);assert.equal(context.filter.value,'plan_paid')
  context.route.query={email:'bad\n@example.test',refresh:'force'}
  assert.equal(context.module.exports(),false);assert.equal(opened.length,1)
})

test('LS export preserves passwords, deduplicates emails and includes completed task accounts', async () => {
  const { upiLsExport } = await import(moduleUrl)
  const info={state:'ready',account:{email:'Sale@example.test',password:' pass word ',totp_secret:'BASE32',access_token:'never-export',refresh_token:'never-export'}}
  const result=upiLsExport([{email:'sale@example.test',phase:'completed',info},{email:' SALE@example.test ',info}])
  assert.equal(result.text,'sale@example.test--- pass word ---BASE32\r\n')
  assert.equal(result.count,1);assert.equal(result.duplicates,1);assert.equal(result.skippedCount,0)
  assert.deepEqual(result.emails,['sale@example.test'])
  assert.equal(JSON.stringify(result).includes('never-export'),false)
})

test('LS export reports unavailable, mismatched, empty and ambiguous fields without leaking them', async () => {
  const { upiLsExport } = await import(moduleUrl)
  const record=(email,fields={},state='ready')=>({email,info:{state,account:{email,password:'fixture',totp_secret:'SECRET',...fields}}})
  const rows=[record('missing@example.test',{},'missing'),record('wrong@example.test',{email:'other@example.test'}),
    record('empty@example.test',{password:''}),record('no2fa@example.test',{totp_secret:''}),
    record('line@example.test',{password:'do\nnot\rexport'}),record('delimiter@example.test',{password:'do---not-export'}),
    record('nul@example.test',{totp_secret:'do\x00not-export'}),record('valid@example.test')]
  const strict=upiLsExport(rows)
  assert.deepEqual(strict.skipped,{unavailable:2,password:1,twofa:1,unsafe:3})
  assert.equal(strict.count,1);assert.equal(strict.skippedCount,7)
  assert.equal(strict.text.includes('do'),false)
  const optional=upiLsExport(rows,{require2fa:false})
  assert.equal(optional.count,2);assert.equal(optional.missing2fa,1)
  assert.equal(optional.text.startsWith('no2fa@example.test---fixture---\r\n'),true)
  assert.equal(upiLsExport([]).text,'')
})

test('completed tasks remain selectable for export and absent provider emails cannot block other logins', async () => {
  const vm=require('node:vm'),{upiAccountEmail,upiLsExport,canControlUpiTask}=await import(moduleUrl)
  const source=fs.readFileSync(path.resolve(__dirname,'../webui/frontend/src/views/Upi.vue'),'utf8')
  const block=source.slice(source.indexOf('const selectableTasks'),source.indexOf('const controlLabel'))
  const context={computed:fn=>({get value(){return fn()}}),rows:{value:[{id:'done',phase:'completed',email:'ready@example.test'},{id:'no-email',email:''}]},
    selectedTaskIds:{value:['done']},loading:{value:false},controlBusy:{value:''},accountMoving:{value:''},taskError:{value:''},
    lsRecords:{value:[]},lsScope:{value:'page'},lsRequire2fa:{value:true},upiAccountEmail,upiLsExport,canControlUpiTask,
    accountFor:()=>({state:'ready'}),module:{exports:{}}}
  vm.runInNewContext(block+'\nmodule.exports={selectableTasks,selectedTasks,controlTargets,lsBusy}',context)
  const h=context.module.exports
  assert.equal(h.selectedTasks.value[0].id,'done');assert.equal(h.selectableTasks.value.length,2)
  assert.equal(h.controlTargets('stop').length,0);assert.equal(h.lsBusy.value,false)
  context.accountFor=()=>undefined
  assert.equal(h.lsBusy.value,true)
  context.rows.value=[{id:'no-email',email:''}]
  assert.equal(h.lsBusy.value,false)
})

function accountMoveModel(updated, failReadback = false) {
  const vm=require('node:vm')
  const source=fs.readFileSync(path.resolve(__dirname,'../webui/frontend/src/views/Upi.vue'),'utf8')
  const block=source.slice(source.indexOf('async function moveAccount('),source.indexOf('function credentialClock()'))
  const context={accountInfo:{value:{'a@example.test':{state:'ready',account:{group_name:'Old'}}}},
    accountMoving:{value:''},controlBusy:{value:''},accountGroups:{value:[]},active:true,calls:[],messages:[],bumps:0,
    upiAccountEmail:email=>email.toLowerCase(),upiAccountFields:data=>data,t:text=>text,errorText:error=>error.message,
    assignRegisteredGroup:async(...args)=>{context.calls.push(args);return {updated,groups:[{name:'New'}]}},
    getRegistered:async()=>{if(failReadback)throw new Error('Readback unavailable');return {data:{email:'a@example.test',group_name:updated?'New':'Concurrent folder'}}},
    runtime:{bumpData:()=>{context.bumps++}},ElMessage:Object.fromEntries(['success','error','warning'].map(tone=>[tone,text=>context.messages.push({tone,text})])),module:{exports:null}}
  vm.runInNewContext(block+'\nmodule.exports=moveAccount',context)
  return context
}

test('UPI folder changes target one account with the previous folder as a guard and read back the result', async () => {
  const m=accountMoveModel(1)
  await m.module.exports('a@example.test','New')
  assert.deepEqual(JSON.parse(JSON.stringify(m.calls)),[[['a@example.test'],'New',{filter:'all',group:'Old'}]])
  assert.equal(m.accountInfo.value['a@example.test'].account.group_name,'New')
  assert.equal(m.messages.at(-1).tone,'success');assert.equal(m.bumps,1);assert.equal(m.accountMoving.value,'')
})

test('UPI stale folder conflicts do not claim a successful move or overwrite the current folder', async () => {
  const m=accountMoveModel(0)
  await m.module.exports('a@example.test','New')
  assert.equal(m.accountInfo.value['a@example.test'].account.group_name,'Concurrent folder')
  assert.equal(m.messages.at(-1).tone,'error');assert.equal(m.bumps,0);assert.equal(m.calls.length,1)
})

test('UPI accepted folder changes with failed readback are unconfirmed and are never retried automatically', async () => {
  const m=accountMoveModel(1,true)
  await m.module.exports('a@example.test','New')
  assert.equal(m.accountInfo.value['a@example.test'].state,'error')
  assert.equal(m.messages.at(-1).tone,'warning');assert.equal(m.bumps,1);assert.equal(m.calls.length,1)
})

test('UPI accepts AT text, JSON arrays and existing account exports without persisting input', async () => {
  const { parseUpiTokens } = await import(moduleUrl)
  assert.deepEqual(parseUpiTokens('Bearer a.b.c\nx.y.z'), ['a.b.c', 'x.y.z'])
  assert.deepEqual(parseUpiTokens('[{"access_token":"a.b.c"},{"accessToken":"x.y.z"}]'), ['a.b.c', 'x.y.z'])
  assert.deepEqual(parseUpiTokens('{"tokens":["a.b.c"]}'), ['a.b.c'])
  assert.deepEqual(parseUpiTokens('mail@example.test----password----a.b.c'), ['a.b.c'])
  assert.throws(() => parseUpiTokens('{broken'), /JSON/)
  assert.throws(() => parseUpiTokens(Array(20001).fill('a.b.c').join('\n')), /20.000/)
})
test('UPI results never label a created link as completed payment', async () => {
  const { upiPhase } = await import(moduleUrl)
  assert.equal(upiPhase('link_ready').label, 'Đã tạo link')
  assert.equal(upiPhase('completed').label, 'Đã quét')
  assert.equal(upiPhase('not-documented').label, 'Chưa rõ trạng thái')
})
test('UPI CSV export escapes spreadsheet formulas and quotes, without token columns', async () => {
  const { upiCsv } = await import(moduleUrl)
  const csv = upiCsv([{ id: '=cmd()', email: '+mail@example.test', status: 'SUCCEEDED', scan_status: 'completed', access_token: 'must-not-export' }])
  assert.match(csv, /'=cmd\(\)/)
  assert.match(csv, /'\+mail/)
  assert.equal(csv.includes('must-not-export'), false)
})
test('UPI owns a separate route and submits only after a consent dialog', () => {
  const view = fs.readFileSync(path.resolve(__dirname, '../webui/frontend/src/views/Upi.vue'), 'utf8')
  const api = fs.readFileSync(path.resolve(__dirname, '../webui/frontend/src/api/upi.js'), 'utf8')
  assert.match(view, /if \(!consent\.value/)
  assert.match(view, /onDeactivated\(stop\)/)
  assert.match(view, /activeTasks\.value/)
  const markerFunctions = view.slice(view.indexOf('function readScanBatch('), view.indexOf('const accountFor ='))
  assert.equal(view.replace(markerFunctions, '').includes('localStorage'), false)
  assert.equal(api.includes('ytc.xxsyun.xyz'), false)
})

const task = (id, phase = 'queued', control = {}) => ({ id, phase, control: { state: phase === 'paused' ? 'PAUSED' : 'RUNNING', ...control } })
const ack = (id, action, pending = false) => ({ task: task(id, action === 'stop' ? 'stopped' : action === 'pause' ? 'paused' : 'running', { state: {pause:'PAUSED',resume:'RUNNING',stop:'STOPPED'}[action], pending }) })

test('select all reads every matching page before bulk controls, with provider and filters frozen', async () => {
  const { collectUpiTasks, runUpiControls } = await import(moduleUrl)
  const all = Array.from({length:205}, (_,i)=>task(String(i))), calls=[], progress=[]
  const selected = await collectUpiTasks(async params => {
    calls.push(params)
    return {total:all.length,items:all.slice(params.page*params.size,(params.page+1)*params.size)}
  }, {provider:'local',query:'match',status:'QUEUED',date:'2026-11-02'}, {onProgress:x=>progress.push(x.loaded)})
  assert.equal(selected.length,205)
  assert.deepEqual(progress,[100,200,205])
  assert.deepEqual(calls.map(x=>x.page),[0,1,2])
  assert.ok(calls.every(x=>x.provider==='local'&&x.query==='match'&&x.status==='QUEUED'&&x.date==='2026-11-02'))
  const sent=[]
  const result=await runUpiControls(selected,'pause',async(id,action)=>{sent.push(id);return ack(id,action)})
  assert.equal(result.accepted,205);assert.equal(new Set(sent).size,205)
})

test('select all fails without returning a partial selection after errors, drift, duplicates or limits', async () => {
  const { collectUpiTasks } = await import(moduleUrl)
  for (const next of [()=>{throw new Error('Network failed')},()=>({total:3,items:[task('c')]}),()=>({total:2,items:[task('a')]}),()=>({total:2,items:[]})]) {
    let calls=0
    await assert.rejects(()=>collectUpiTasks(async()=>++calls===1?{total:2,items:[task('a')]}:next(),{}))
    assert.equal(calls,2)
  }
  await assert.rejects(()=>collectUpiTasks(async()=>({total:20001,items:[]}),{}),/20.000/)
  let active=true
  await assert.rejects(()=>collectUpiTasks(async()=>{active=false;return{total:1,items:[task('a')]}},{},{isActive:()=>active}),/hủy/)
})

test('individual and page selection preserve accounts selected on other pages', async () => {
  const vm=require('node:vm')
  const source=fs.readFileSync(path.resolve(__dirname,'../webui/frontend/src/views/Upi.vue'),'utf8')
  const context={selectedTaskIds:{value:['old']},selectedTaskCache:{value:{old:task('old')}},rows:{value:[task('new'),task('next')]},
    selectableTasks:{value:[task('new'),task('next')]},module:{exports:{}}}
  vm.runInNewContext(source.slice(source.indexOf('function clearTaskSelection()'),source.indexOf('async function selectAllTasks()'))+'\nmodule.exports={selectTask,selectTaskPage,clearTaskSelection}',context)
  const h=context.module.exports
  h.selectTaskPage(true)
  assert.deepEqual([...context.selectedTaskIds.value],['old','new','next'])
  h.selectTask('new',false)
  assert.deepEqual([...context.selectedTaskIds.value],['old','next'])
  h.selectTaskPage(false)
  assert.deepEqual([...context.selectedTaskIds.value],['old'])
  h.clearTaskSelection()
  assert.equal(context.selectedTaskIds.value.length,0);assert.equal(Object.keys(context.selectedTaskCache.value).length,0)
})

test('UPI only resumes paused tasks and never controls terminal or pending tasks', async () => {
  const { canControlUpiTask: can } = await import(moduleUrl)
  assert.equal(can(task('a'), 'pause'), true)
  assert.equal(can(task('a'), 'resume'), false)
  assert.equal(can(task('a', 'paused'), 'resume'), true)
  assert.equal(can(task('a', 'paused'), 'pause'), false)
  assert.equal(can(task('a', 'link_ready'), 'stop'), true)
  for (const row of [task('a','completed'), task('a','failed'), task('a','stopped'), task('a','unknown',{state:'STOPPED'}), task('a','queued',{pending:true}), task('')]) {
    for (const action of ['pause','resume','stop']) assert.equal(can(row,action),false)
  }
})

test('UPI bulk controls send each eligible selected task once and preserve pending acknowledgements', async () => {
  const { runUpiControls } = await import(moduleUrl)
  const calls = [], progress = []
  const result = await runUpiControls([task('a'), task('a'), task('b','paused'), task('done','completed')], 'stop',
    async (id, action) => { calls.push([id,action]); return ack(id,action,id==='b') }, { onProgress: x => progress.push(x) })
  assert.deepEqual(calls,[['a','stop'],['b','stop']])
  assert.equal(result.total,2); assert.equal(result.accepted,2); assert.equal(result.pending,1)
  assert.equal(result.failed,0); assert.equal(result.not_sent,0)
  assert.deepEqual(progress.map(x=>x.items.length),[1,2])
})

test('UPI state conflicts are reported per task while later selected tasks still receive commands', async () => {
  const { runUpiControls } = await import(moduleUrl)
  const result = await runUpiControls([task('a'),task('b')],'pause',async(id,action)=>{
    if(id==='a')throw Object.assign(new Error('State changed'),{status:409})
    return ack(id,action)
  })
  assert.equal(result.failed,1);assert.equal(result.accepted,1);assert.equal(result.not_sent,0)
  assert.equal(result.items[0].message,'State changed')
})

for (const status of [undefined,401,429,503]) test(`UPI bulk commands halt after ${status || 'network uncertainty'} without retrying`, async () => {
  const { runUpiControls } = await import(moduleUrl)
  let calls=0
  const result=await runUpiControls([task('a'),task('b'),task('c')],'pause',async()=>{
    calls++;throw Object.assign(new Error('Not confirmed'),{status})
  })
  assert.equal(calls,1);assert.equal(result.failed,1);assert.equal(result.accepted,0);assert.equal(result.not_sent,2)
})

test('UPI malformed or mismatched acknowledgements never appear as successful stops', async () => {
  const { runUpiControls } = await import(moduleUrl)
  for(const response of [{},ack('other','stop'),ack('a','resume')]) {
    let calls=0
    const result=await runUpiControls([task('a'),task('b')],'stop',async()=>{calls++;return response})
    assert.equal(calls,1);assert.equal(result.accepted,0);assert.equal(result.failed,1);assert.equal(result.not_sent,1)
  }
})

test('leaving UPI stops sending remaining commands without cancelling the already accepted command', async () => {
  const { runUpiControls } = await import(moduleUrl)
  let active=true,calls=0
  const result=await runUpiControls([task('a'),task('b')],'stop',async(id,action)=>{calls++;return ack(id,action)},
    {isActive:()=>active,onProgress:()=>{active=false}})
  assert.equal(calls,1);assert.equal(result.accepted,1);assert.equal(result.not_sent,1)
  await assert.rejects(()=>runUpiControls([task('a')],'delete',()=>assert.fail()),/UPI/)
})
