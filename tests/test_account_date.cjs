const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const test = require('node:test')
const assert = require('node:assert/strict')
const source = fs.readFileSync(path.join(__dirname,'../webui/frontend/src/api/request.js'),'utf8')
const formatter = source.slice(source.indexOf('export function fmtDate(')).replace('export function','function')

test('account creation dates contain the calendar date in every supported locale',()=>{
  for (const locale of ['vi-VN','en-US','zh-CN']) {
    const context={localeTag:()=>locale,module:{exports:{}}}
    vm.runInNewContext(formatter+'\nmodule.exports=fmtDate',context)
    const timestamp=Date.UTC(2026,9,31,2,45,19)/1000
    const actual=context.module.exports(timestamp)
    assert.equal(actual,new Date(timestamp*1000).toLocaleDateString(locale))
    assert(!actual.includes(':'))
  }
})
