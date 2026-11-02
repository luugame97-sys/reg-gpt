const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path')
const source=fs.readFileSync(path.join(__dirname,'../webui/frontend/src/components/AccountFolders.vue'),'utf8')
const script=source.split('<script setup>')[1].split('</script>')[0].replace(/^import .*$/gm,'')
function harness(){
 const events=[],props={summary:{groups:['A','B','C','D'].map(name=>({name,count:1}))},savingOrder:false}
 let hovered=null
 const root={contains:row=>row.inside!==false,querySelector:()=>({scrollTop:100,getBoundingClientRect:()=>({top:0,bottom:200})})}
 const ctx={defineProps:()=>props,defineEmits:()=> (...args)=>events.push(args),ref:value=>({value}),computed:fn=>({get value(){return fn()}}),document:{elementFromPoint:()=>hovered},module:{exports:{}}}
 vm.runInNewContext(script+'\nmodule.exports={root,query,dragging,dropTarget,beginDrag,moveDrag,finishDrag,resetDrag,moveStep,keyReorder}',ctx)
 const m=ctx.module.exports;m.root.value=root
 return {...m,props,events,hover:name=>{hovered=name?{dataset:{folderName:name},getBoundingClientRect:()=>({top:80,height:40}),closest(){return this}}:null}}
}
const pointer=(x,y)=>({button:0,isPrimary:true,pointerId:1,clientX:x,clientY:y,currentTarget:{setPointerCapture(){}}})
test('a pointer drag submits one relative move after crossing the row midpoint',()=>{
 const h=harness();h.beginDrag(pointer(5,20),'A');h.hover('C');h.moveDrag(pointer(6,115));h.finishDrag(pointer(6,115))
 assert.equal(JSON.stringify(h.events),JSON.stringify([['reorder',{name:'A',target:'C',position:'after'}]]))
 assert.equal(h.dragging.value,null);assert.equal(h.dropTarget.value,null)
 h.finishDrag(pointer(6,115));assert.equal(h.events.length,1)
})
test('a tap, cancelled gesture, or drop outside never reorders',()=>{
 const h=harness();h.beginDrag(pointer(5,20),'A');h.hover('C');h.finishDrag(pointer(5,22));assert.equal(h.events.length,0)
 h.beginDrag(pointer(5,20),'A');h.moveDrag(pointer(5,90));h.resetDrag();h.finishDrag(pointer(5,90));assert.equal(h.events.length,0)
 h.beginDrag(pointer(5,20),'A');h.hover(null);h.finishDrag(pointer(5,180));assert.equal(h.events.length,0)
})
test('saving blocks another drag and keyboard movement; ordinary navigation keys remain free',()=>{
 const h=harness();h.props.savingOrder=true;h.beginDrag(pointer(0,0),'B');h.moveStep('B',1);assert.equal(h.dragging.value,null);assert.equal(h.events.length,0)
 h.props.savingOrder=false;let prevented=0
 h.keyReorder({key:'ArrowDown',altKey:false,preventDefault(){prevented++}},'B');assert.equal(prevented,0)
 h.keyReorder({key:'ArrowUp',altKey:true,preventDefault(){prevented++}},'B');assert.equal(prevented,1)
 assert.equal(JSON.stringify(h.events),JSON.stringify([['reorder',{name:'B',target:'A',position:'before'}]]))
})
test('filtered movement only refers to visible siblings while the server keeps hidden folders',()=>{
 const h=harness();h.props.summary.groups=[{name:'Alpha'},{name:'Hidden'},{name:'Alpine'}];h.query.value='Al'
 h.moveStep('Alpha',1)
 assert.equal(JSON.stringify(h.events),JSON.stringify([['reorder',{name:'Alpha',target:'Alpine',position:'after'}]]))
})
test('a late list response cannot replace a newly saved folder order',()=>{
 const source=fs.readFileSync(path.join(__dirname,'../webui/frontend/src/views/Registered.vue'),'utf8')
 const ctx={groupsSummary:{value:null},module:{exports:{}}}
 vm.runInNewContext(source.slice(source.indexOf('const latestFolderOrder'),source.indexOf('async function loadGroupsOnly'))+'\nmodule.exports=applyGroupsSummary',ctx)
 const groups=names=>names.map(name=>({name,count:1}))
 ctx.module.exports({groups:groups(['C','A','B']),order_revision:2,total:3})
 ctx.module.exports({groups:groups(['A','B','C','New']),order_revision:1,total:4})
 assert.equal(ctx.groupsSummary.value.groups.map(g=>g.name).join(','),'C,A,B,New')
 assert.equal(ctx.groupsSummary.value.total,4)
})
