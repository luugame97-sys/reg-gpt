const {test}=require('node:test')
const assert=require('node:assert/strict')
const {pathToFileURL}=require('node:url')
const path=require('node:path')
const moduleUrl=pathToFileURL(path.resolve(__dirname,'../webui/frontend/src/upiAudio.js')).href

test('UPI audio needs activation and uses distinct scan and success motifs',async()=>{
  const {createUpiSounds}=await import(moduleUrl)
  const notes=[]
  let closed=false
  const context={state:'suspended',currentTime:10,destination:{},resume:async()=>{context.state='running'},close:async()=>{closed=true},
    createGain:()=>({gain:{setValueAtTime(){},linearRampToValueAtTime(){},exponentialRampToValueAtTime(){}},connect(){},disconnect(){}}),
    createOscillator:()=>{const note={frequency:{value:0},connect(){},disconnect(){},start(at){notes.push({frequency:note.frequency.value,type:note.type,at})},stop(){}};return note}}
  const sounds=createUpiSounds(()=>context)
  assert.equal(sounds.play('scanning'),false)
  assert.equal(await sounds.enable(),true)
  assert.equal(sounds.play('scanning'),true)
  assert.equal(notes.length,2);assert.equal(notes[0].type,'triangle');assert.ok(notes[1].frequency>notes[0].frequency)
  assert.equal(sounds.play('completed'),true)
  assert.equal(notes.length,6);assert.equal(notes[2].type,'sine');assert.ok(notes[5].frequency>notes[2].frequency)
  assert.ok(notes[2].at>notes[1].at+.16)
  sounds.close();assert.equal(closed,true);assert.equal(sounds.play('completed'),false)
})

test('unavailable audio never blocks UPI',async()=>{
  const {createUpiSounds}=await import(moduleUrl)
  const sounds=createUpiSounds(()=>{throw new Error('Audio blocked')})
  assert.equal(await sounds.enable(),false)
  assert.equal(sounds.play('completed'),false)
  assert.doesNotThrow(()=>sounds.close())
})

test('saved sound preferences unlock automatically on page interaction and detach on leaving',async()=>{
  const {createUpiSounds}=await import(moduleUrl)
  let wanted=false,created=0,resumed=0
  const target=new EventTarget()
  const context={state:'suspended',resume:async()=>{resumed++;context.state='running'},close:async()=>{}}
  const sounds=createUpiSounds(()=>{created++;return context})
  const stop=sounds.listen(target,()=>wanted)
  target.dispatchEvent(new Event('pointerdown'))
  assert.equal(created,0)
  wanted=true
  target.dispatchEvent(new Event('keydown'))
  await Promise.resolve()
  assert.equal(created,1);assert.equal(resumed,1)
  stop();sounds.close()
  target.dispatchEvent(new Event('pointerdown'))
  assert.equal(created,1)
})

function suspendedSounds(createUpiSounds) {
  const resumes=[]
  const context={state:'suspended',resume:()=>new Promise(resolve=>resumes.push(resolve)),close:async()=>{}}
  const sounds=createUpiSounds(()=>context)
  const played=[]
  sounds.play=kind=>{if(context.state!=='running')return false;played.push(kind);return true}
  return {sounds,played,unlock(){context.state='running';for(const resolve of resumes)resolve()}}
}

test('blocked autoplay queues one recent notification per kind without asking again',async()=>{
  const {createUpiSounds}=await import(moduleUrl)
  const h=suspendedSounds(createUpiSounds)
  const first=h.sounds.notify('completed',()=>true)
  assert.equal(await h.sounds.notify('completed',()=>true),false)
  const scan=h.sounds.notify('scanning',()=>true)
  h.unlock()
  assert.equal(await first,true);assert.equal(await scan,true)
  assert.deepEqual(h.played,['completed','scanning'])
})

test('notifications respect disabled settings, provider/visibility changes, expiry and closing',async()=>{
  const {createUpiSounds}=await import(moduleUrl)
  for(const reason of ['disabled','expired','closed']){
    const h=suspendedSounds(createUpiSounds)
    let allowed=true,now=1000
    const pending=h.sounds.notify('completed',()=>allowed,()=>now)
    if(reason==='disabled')allowed=false
    if(reason==='expired')now+=30001
    if(reason==='closed')h.sounds.close()
    h.unlock()
    assert.equal(await pending,false,reason)
    assert.equal(h.played.length,0)
  }
  const h=suspendedSounds(createUpiSounds)
  assert.equal(await h.sounds.notify('scanning',()=>false),false)
  assert.equal(await h.sounds.notify('unknown',()=>true),false)
})

test('saving sound preferences does not wait for autoplay permission and UPI has no extra unlock button',()=>{
  const fs=require('node:fs')
  const source=fs.readFileSync(path.resolve(__dirname,'../webui/frontend/src/views/Upi.vue'),'utf8')
  const save=source.slice(source.indexOf('async function saveAutomation()'),source.indexOf('function openConfig()'))
  assert.match(save,/void sounds.enable\(\)/)
  assert.doesNotMatch(save,/await (?:sounds\.enable|enableSounds)/)
  assert.doesNotMatch(source,/Bật âm thanh trong tab này|soundReady/)
  assert.match(source,/sounds\.listen\(document/)
})
