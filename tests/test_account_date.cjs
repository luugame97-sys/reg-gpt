const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const test = require('node:test')
const assert = require('node:assert/strict')
const source = fs.readFileSync(path.join(__dirname,'../webui/frontend/src/api/request.js'),'utf8')
const formatter = source.slice(source.indexOf('const dateFormatters')).replaceAll('export function','function')

test('account creation dates contain the calendar date in every supported locale',()=>{
  for (const locale of ['vi-VN','en-US','zh-CN']) {
    const context={localeTag:()=>locale,getActivePinia:()=>null,module:{exports:{}}}
    vm.runInNewContext(formatter+'\nmodule.exports=fmtDate',context)
    const timestamp=Date.UTC(2026,9,31,2,45,19)/1000
    const actual=context.module.exports(timestamp)
    assert.equal(actual,new Date(timestamp*1000).toLocaleDateString(locale))
    assert(!actual.includes(':'))
  }
})

test('cached date/time formatters preserve all supported locales after switching language', () => {
  let locale = 'vi-VN', created = 0
  const context = {localeTag: () => locale, getActivePinia:()=>null, module: {exports:{}}, Intl: {DateTimeFormat: function(...args) { created++; return new Intl.DateTimeFormat(...args) }}}
  vm.runInNewContext(formatter+'\nmodule.exports={fmtTime,fmtDate}', context)
  const {fmtTime,fmtDate} = context.module.exports, ts = Date.UTC(2026,9,31,2,45,19)/1000
  for (locale of ['vi-VN','en-US','zh-CN','vi-VN']) {
    for (let i=0; i<3; i++) {
      assert.equal(fmtTime(ts+i), new Date((ts+i)*1000).toLocaleString(locale,{hour12:false}))
      assert.equal(fmtDate(ts+i), new Date((ts+i)*1000).toLocaleDateString(locale))
    }
  }
  assert.equal(created, 6)
  assert.equal(fmtTime(0), '-')
  assert.equal(fmtDate('bad'), 'Invalid Date')
})
