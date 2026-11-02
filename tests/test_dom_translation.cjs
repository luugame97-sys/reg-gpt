const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const test = require('node:test')
const assert = require('node:assert/strict')
const root = path.resolve(__dirname, '../webui/frontend/src')
function dict(lang) {
  const context = { module: { exports: {} } }
  vm.runInNewContext(fs.readFileSync(path.join(root, `locales/${lang}.js`), 'utf8').replace('export default', 'module.exports ='), context)
  return context.module.exports
}
const context = { viDict: dict('vi'), enDict: dict('en'), zhDict: dict('zh'), uiPhrases: dict('ui'), readStoredLocale: () => 'vi', validLocale: lang => ['vi','en','zh'].includes(lang) ? lang : 'vi', localStorage: {getItem: () => 'vi'}, Node: {TEXT_NODE: 3, ELEMENT_NODE: 1}, module: {exports: {}} }
const source = fs.readFileSync(path.join(root, 'i18n/domTranslator.js'), 'utf8').replace(/^import .*$/gm, '').replace(/export function /g, 'function ')
vm.runInNewContext(source + '\nmodule.exports = {translateNode, translateString, installMessageInterceptor, initDomTranslator}', context)
const {translateNode} = context.module.exports

test('Free stays a plan name while a zero price retains its own translation', () => {
  const {translateString} = context.module.exports
  for (const lang of ['vi','en','zh']) assert.equal(translateString('Free',lang),'Free')
  assert.equal(translateString('0đ','vi'),'0đ')
  assert.equal(translateString('0đ','en'),'No charge')
  assert.equal(translateString('No charge','vi'),'0đ')
})

test('live numbers are updated instead of restoring a cached zero', () => {
  const node = { nodeType: 3, nodeValue: ' (0 nhóm)' }
  translateNode(node, 'vi')
  node.nodeValue = ' (4 nhóm)'
  translateNode(node, 'vi')
  assert.equal(node.nodeValue, ' (4 nhóm)')
  translateNode(node, 'vi')
  assert.equal(node.nodeValue, ' (4 nhóm)')
})
test('Chinese dynamic counters preserve fresh values when switching languages', () => {
  const node = { nodeType: 3, nodeValue: '共 2 条' }
  translateNode(node, 'vi')
  assert.equal(node.nodeValue, 'Tổng cộng 2 mục')
  node.nodeValue = '共 9 条'
  translateNode(node, 'vi')
  assert.equal(node.nodeValue, 'Tổng cộng 9 mục')
  translateNode(node, 'en')
  assert.equal(node.nodeValue, 'Total 9 items')
  translateNode(node, 'zh')
  assert.equal(node.nodeValue, '共 9 条')
})
test('Vue updates to a translated label become the current source', () => {
  const node = {nodeType: 3, nodeValue: '成功'}
  translateNode(node, 'vi')
  node.nodeValue = 'Thành công: 12'
  translateNode(node, 'vi')
  assert.equal(node.nodeValue, 'Thành công: 12')
})
test('updated accessibility labels are not restored from stale attributes', () => {
  const attrs = {'aria-label': 'Đã chọn 0 mục'}
  const node = {nodeType: 1, tagName: 'BUTTON', childNodes: [], classList: {contains: () => false}, getAttribute: (name) => attrs[name] || null, setAttribute: (name, value) => {attrs[name] = value}}
  translateNode(node, 'vi')
  attrs['aria-label'] = 'Đã chọn 3 mục'
  translateNode(node, 'vi')
  assert.equal(attrs['aria-label'], 'Đã chọn 3 mục')
})
const statsSource = fs.readFileSync(path.join(root, 'stores/stats.js'), 'utf8').replace(/^import .*$/gm, '').replace('export const useStatsStore', 'const useStatsStore')
function statsHarness() {
  let calls = 0, resolveRequest
  const listeners = new Map(), timers = new Map()
  const document = {hidden: false, addEventListener: (name, fn) => listeners.set(name, fn), removeEventListener: (name) => listeners.delete(name)}
  const context = {defineStore: (_name, setup) => setup, ref: (value) => ({value}), getStats: () => { calls++; return new Promise(resolve => {resolveRequest=resolve}) }, document, console, Date, setTimeout: (fn) => {const id=timers.size+1;timers.set(id,fn);return id}, clearTimeout: (id) => timers.delete(id), module: {exports: {}}}
  vm.runInNewContext(statsSource+'\nmodule.exports = useStatsStore()',context)
  return {store:context.module.exports,document,timers,listeners,calls:()=>calls,resolve:(stats)=>resolveRequest({stats})}
}
test('statistics refresh shares an in-flight request', async () => {
  const h=statsHarness(), first=h.store.refresh(), second=h.store.refresh()
  assert.equal(first,second);assert.equal(h.calls(),1)
  h.resolve({total:42});await first
  assert.equal(h.store.stats.value.total,42);assert.equal(h.store.refreshing.value,false)
})
test('hidden tabs stop polling and disposal removes the listener', async () => {
  const h=statsHarness();h.store.startPolling();h.document.hidden=true;h.listeners.get('visibilitychange')();h.resolve({total:1})
  await new Promise(resolve=>setImmediate(resolve))
  assert.equal(h.timers.size,0)
  h.store.stopPolling();assert.equal(h.listeners.size,0)
})
const phrases = dict('ui')
const {translateString, installMessageInterceptor} = context.module.exports
const fill = text => text.replace(/\{(\d+)\}/g, (_slot,index) => String(113+Number(index)))
test('all UI catalog phrases and dynamic placeholders translate to all three languages', () => {
  for (const phrase of phrases) for (const lang of ['vi','en','zh']) {
    assert.equal(translateString(fill(phrase.source),lang).trim(),fill(phrase[lang]).trim(), `${lang}: ${phrase.source}`)
  }
})
test('catalog translations preserve placeholder counts and contain no mixed Chinese or Vietnamese', () => {
  const slots = text => (text.match(/\{\d+\}/g)||[]).sort().join(',')
  for (const phrase of phrases) {
    for (const lang of ['vi','en','zh']) assert.equal(slots(phrase.source),slots(phrase[lang]),phrase.source)
    assert.doesNotMatch(phrase.en,/\p{Script=Han}|[\u00c0-\u024f\u1e00-\u1eff]/u,phrase.source)
    assert.doesNotMatch(phrase.vi,/\p{Script=Han}/u,phrase.source)
    assert.doesNotMatch(phrase.zh,/[\u00c0-\u024f\u1e00-\u1eff]/u,phrase.source)
  }
})
test('repeated language switches keep fresh counts and original source', () => {
  const node={nodeType:3,nodeValue:'Đang chạy (8)'}
  for(const lang of ['en','zh','vi','en','vi','zh']){
    translateNode(node,lang)
    assert.equal(node.nodeValue,fill(phrases.find(p=>p.source==='Đang chạy ({0})')[lang]).replace('113','8'))
  }
  node.nodeValue='Đang chạy (21)';translateNode(node,'en');assert.equal(node.nodeValue,'Running (21)')
})
test('secret values and user folder names marked translate=no stay byte-for-byte unchanged', () => {
  for (const value of ['Mật khẩu','成功','Copy','DATA@中文.test']) {
    const node={nodeType:3,nodeValue:value,parentElement:{closest:()=>({})}}
    translateNode(node,'en');assert.equal(node.nodeValue,value)
  }
})
test('dynamic attributes and textarea placeholders translate while textarea data is untouched', () => {
  const attrs={placeholder:'Tìm email hoặc tên miền…'}
  const text={nodeType:3,nodeValue:'Mật khẩu',parentElement:{closest:s=>s.includes('textarea')?{}:null}}
  const node={nodeType:1,tagName:'TEXTAREA',childNodes:[text],getAttribute:name=>attrs[name]||null,setAttribute:(name,value)=>attrs[name]=value,closest:()=>null}
  translateNode(node,'en');assert.equal(attrs.placeholder,'Search email or domain…');assert.equal(text.nodeValue,'Mật khẩu')
  attrs.placeholder='Tìm thư mục…';translateNode(node,'zh');assert.equal(attrs.placeholder,'搜索文件夹…')
})
test('message prompt, alert and confirmation translate without mutating caller options', () => {
  const calls=[];const message={success:value=>calls.push(value)}
  const boxes=Object.fromEntries(['prompt','alert','confirm'].map(method=>[method,(...args)=>calls.push(args)]))
  installMessageInterceptor(message,boxes,{locale:'en'})
  const options={confirmButtonText:'Lưu',cancelButtonText:'Hủy',inputPlaceholder:'Tên thư mục'}
  for(const method of ['prompt','alert','confirm'])boxes[method]('Tạo thư mục',options)
  assert.equal(options.confirmButtonText,'Lưu');assert.equal(calls.length,3)
  assert.equal(calls[0][0],'Create folder');assert.equal(calls[0][1].confirmButtonText,'Save')
  assert.equal(calls[0][1].inputPlaceholder,'Folder name')
})
const localeSource=fs.readFileSync(path.join(root,'i18n/locale.js'),'utf8').replace(/export /g,'')
function localeHarness(value,blocked=false){
  const storage={value};const c={localStorage:{getItem:()=>{if(blocked)throw Error('denied');return storage.value},setItem:(_key,value)=>{if(blocked)throw Error('denied');storage.value=value}},module:{exports:{}}}
  vm.runInNewContext(localeSource+'\nmodule.exports={readStoredLocale,saveLocale,validLocale,localeTag}',c)
  return {...c.module.exports,storage}
}
test('first visit and invalid or inaccessible storage default to Vietnamese',()=>{
  for(const value of [null,'','fr','__proto__'])assert.equal(localeHarness(value).readStoredLocale(),'vi')
  assert.equal(localeHarness('en',true).readStoredLocale(),'vi')
})
test('last valid locale is saved per browser and survives initialization',()=>{
  const h=localeHarness(null)
  for(const lang of ['en','zh','vi']){h.saveLocale(lang);assert.equal(h.readStoredLocale(),lang)}
  assert.equal(h.localeTag('zh'),'zh-CN');assert.equal(h.localeTag('en'),'en-US');assert.equal(h.localeTag('vi'),'vi-VN')
})

test('nested status phrases translate while data and technical header names remain intact',()=>{
 assert.equal(translateString('Quản lý hàng loạt · 12 đã chọn','en'),'Bulk management · 12 selected')
 assert.equal(translateString('Outlook 接码池 不需要在这里配置，去「导入邮箱」页把号导进来即可。','en'),'Outlook OTP pool needs no configuration here. Import its accounts on the Import Mail page.')
 assert.equal(translateString('Sai mã 2FA','zh'),'2FA验证码错误')
 assert.equal(translateString('Accept-Language','zh'),'Accept-Language')
 assert.equal(translateString('Đã tạo thư mục «Tài khoản»','en'),'Created folder «Tài khoản»')
 assert.equal(translateString('Đã xóa 7 tài khoản. Giữ lại 2 acc đang chờ hoặc đang xử lý.','en'),'Deleted 7 accounts. Kept 2 queued or active accounts.')
})

test('legacy dynamic messages can switch languages after message interception',()=>{
 const english=translateString('共 19 条','en')
 assert.equal(translateString(english,'zh'),'共 19 条')
 assert.equal(translateString(english,'vi'),'Tổng cộng 19 mục')
})

test('mutation translation deduplicates inserted subtrees and limits attribute work to the target', () => {
  let notify, reads=0
  const element = () => ({nodeType:1,tagName:'DIV',isConnected:true,childNodes:[],closest:()=>null,
    getAttribute:()=>{reads++;return null},setAttribute:()=>{},hasAttribute:()=>false})
  const parent=element(), child=element()
  child.parentNode=parent;parent.childNodes=[child]
  const text={nodeType:3,nodeValue:'Tạo thư mục',isConnected:true,parentNode:child,parentElement:child}
  child.childNodes=[text]
  context.window={};context.document={body:null}
  context.MutationObserver=class {constructor(fn){notify=fn} observe(){} disconnect(){}}
  context.module.exports.initDomTranslator({locale:'en',$subscribe:()=>{}})
  notify([{type:'childList',addedNodes:[parent]},{type:'childList',addedNodes:[child,text]},{type:'attributes',target:child}])
  assert.equal(text.nodeValue,'Create folder')
  assert.equal(reads,14) // seven translatable attributes, each element visited once
  reads=0; text.nodeValue='Tài khoản'
  notify([{type:'attributes',target:parent},{type:'attributes',target:parent}])
  assert.equal(reads,7)
  assert.equal(text.nodeValue,'Tài khoản')
  notify([{type:'characterData',target:text}])
  assert.equal(text.nodeValue,'Accounts')
})
