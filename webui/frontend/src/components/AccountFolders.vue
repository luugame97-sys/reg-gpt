<script setup>
import { computed, ref } from 'vue'
import { Folder, FolderOpen, FolderPlus, Layers, Inbox, MoreHorizontal, Search, GripVertical } from 'lucide-vue-next'
const props=defineProps({summary:{type:Object,required:true},current:{type:String,default:'all'},saved:{type:Array,default:()=>[]},savingOrder:Boolean})
const emit=defineEmits(['select','create','rename','delete','move','saved','remove-saved','reorder'])
const query=ref('')
const root=ref(null),dragging=ref(null),dropTarget=ref(null)
const folders=computed(()=>props.summary.groups.filter(folder=>folder.name.toLocaleLowerCase().includes(query.value.trim().toLocaleLowerCase())))
const count=value=>Number(value||0).toLocaleString('vi-VN')
function beginDrag(event,name){
 if(props.savingOrder || event.button!==0 || event.isPrimary===false)return
 dragging.value={name,pointerId:event.pointerId,x:event.clientX,y:event.clientY,active:false}
 dropTarget.value=null
 try{event.currentTarget.setPointerCapture(event.pointerId)}catch{resetDrag()}
}
function moveDrag(event){
 const drag=dragging.value
 if(!drag || event.pointerId!==drag.pointerId)return
 if(!drag.active && Math.hypot(event.clientX-drag.x,event.clientY-drag.y)<6)return
 drag.active=true
 const row=document.elementFromPoint(event.clientX,event.clientY)?.closest('[data-folder-name]')
 if(!row || !root.value?.contains(row) || row.dataset.folderName===drag.name){dropTarget.value=null;return}
 const rect=row.getBoundingClientRect()
 dropTarget.value={name:row.dataset.folderName,position:event.clientY<rect.top+rect.height/2?'before':'after'}
 const scroll=root.value.querySelector('.folder-scroll'),bounds=scroll.getBoundingClientRect()
 if(event.clientY<bounds.top+28)scroll.scrollTop-=10
 else if(event.clientY>bounds.bottom-28)scroll.scrollTop+=10
}
function resetDrag(){dragging.value=null;dropTarget.value=null}
function finishDrag(event){
 const drag=dragging.value
 if(!drag || event.pointerId!==drag.pointerId)return
 moveDrag(event)
 const target=dropTarget.value
 resetDrag()
 if(drag.active && target && !props.savingOrder)emit('reorder',{name:drag.name,target:target.name,position:target.position})
}
function moveStep(name,direction){
 if(props.savingOrder)return
 const index=folders.value.findIndex(folder=>folder.name===name),target=folders.value[index+direction]
 if(index>=0 && target)emit('reorder',{name,target:target.name,position:direction<0?'before':'after'})
}
function keyReorder(event,name){
 if(!event.altKey || !['ArrowUp','ArrowDown'].includes(event.key))return
 event.preventDefault();moveStep(name,event.key==='ArrowUp'?-1:1)
}
function folderCommand(command,name){
 if(command==='up' || command==='down')moveStep(name,command==='up'?-1:1)
 else emit(command,name)
}
</script>
<template>
 <div ref="root" class="folder-rail" :class="{'is-reordering':dragging?.active}" aria-label="Thư mục tài khoản" :aria-busy="savingOrder">
  <div class="folder-rail-heading"><span>Thư mục</span><el-button text aria-label="Tạo thư mục" @click="emit('create')"><FolderPlus :size="17" /></el-button></div>
  <button type="button" class="folder-link" :class="{active:current==='all'}" @click="emit('select','all')"><Layers :size="17" /><span>Tất cả tài khoản</span><b>{{ count(summary.total) }}</b></button>
  <button type="button" class="folder-link" :class="{active:current==='__ungrouped__'}" @click="emit('select','__ungrouped__')"><Inbox :size="17" /><span>Chưa phân thư mục</span><b>{{ count(summary.ungrouped) }}</b></button>
  <div class="folder-divider" />
  <el-input v-model="query" clearable size="small" placeholder="Tìm thư mục…" aria-label="Tìm thư mục"><template #prefix><Search :size="13" /></template></el-input>
  <div class="folder-scroll"><div v-for="(folder,index) in folders" :key="folder.name" class="folder-item" :data-folder-name="folder.name" :class="{active:current===folder.name,'is-dragging':dragging?.active && dragging.name===folder.name,'drop-before':dropTarget?.name===folder.name && dropTarget.position==='before','drop-after':dropTarget?.name===folder.name && dropTarget.position==='after'}"><button type="button" class="folder-drag-handle" :disabled="savingOrder" :aria-label="`Sắp xếp thư mục ${folder.name}`" title="Kéo để sắp xếp · Alt + ↑ / ↓" @pointerdown.prevent="beginDrag($event,folder.name)" @pointermove="moveDrag" @pointerup="finishDrag" @pointercancel="resetDrag" @lostpointercapture="resetDrag" @keydown="keyReorder($event,folder.name)"><GripVertical :size="14"/></button><button type="button" class="folder-link" :title="folder.name" data-i18n-skip-title="true" :aria-label="`Mở thư mục ${folder.name}`" @click="emit('select',folder.name)"><FolderOpen v-if="current===folder.name" :size="17" /><Folder v-else :size="17" /><span translate="no">{{ folder.name }}</span><b>{{ count(folder.count) }}</b></button><el-dropdown trigger="click" @command="command=>folderCommand(command,folder.name)"><el-button text :aria-label="`Thao tác thư mục ${folder.name}`"><MoreHorizontal :size="15" /></el-button><template #dropdown><el-dropdown-menu><el-dropdown-item command="up" :disabled="savingOrder || index===0">Đưa lên</el-dropdown-item><el-dropdown-item command="down" :disabled="savingOrder || index===folders.length-1">Đưa xuống</el-dropdown-item><el-dropdown-item command="rename" divided>Đổi tên thư mục</el-dropdown-item><el-dropdown-item command="move" :disabled="!folder.count">Chuyển tài khoản trong thư mục…</el-dropdown-item><el-dropdown-item command="delete" divided class="danger-menu-item">Xóa thư mục…</el-dropdown-item></el-dropdown-menu></template></el-dropdown></div><p v-if="!folders.length" class="folder-empty">{{ query ? 'Không tìm thấy thư mục' : 'Tạo thư mục đầu tiên để sắp xếp tài khoản.' }}</p></div>
  <span v-if="savingOrder" class="folder-order-saving" role="status">Đang lưu thứ tự…</span>
  <div v-if="saved.length" class="saved-views"><div class="folder-rail-heading"><span>Bộ lọc đã lưu</span><b>{{ saved.length }}</b></div><div v-for="view in saved" :key="view.id" class="saved-view"><button type="button" translate="no" @click="emit('saved',view)">{{ view.name }}</button><el-button text size="small" :aria-label="`Bỏ bộ lọc đã lưu ${view.name}`" @click="emit('remove-saved',view.id)">×</el-button></div></div>
  <div class="folder-footnote">{{ summary.groups.length }} thư mục <span>·</span> {{ count(summary.grouped) }} tài khoản đã sắp xếp</div>
 </div>
</template>
<style scoped>
.folder-rail{display:flex;flex-direction:column;gap:5px;padding:18px 12px;color:var(--app-text-regular);min-width:0}.folder-rail-heading{display:flex;justify-content:space-between;align-items:center;min-height:28px;padding:0 8px;font-size:10px;letter-spacing:1.1px;font-weight:650;color:var(--app-text-dim)}.folder-rail-heading .el-button{padding:5px;width:28px;height:28px}.folder-link{display:flex;align-items:center;gap:9px;min-width:0;flex:1;width:100%;border:0;border-radius:8px;padding:10px 9px;background:transparent;color:var(--app-text-muted);font:inherit;font-size:12px;text-align:left;cursor:pointer}.folder-link>svg{flex-shrink:0;color:var(--folder-accent,var(--brand))}.folder-link>span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1}.folder-link b{font-size:10px;font-weight:550;font-variant-numeric:tabular-nums;opacity:.8}.folder-link:hover,.folder-item:hover{background:var(--app-card-hover)}.folder-link.active,.folder-item.active{background:var(--brand-bg);color:var(--brand)}.folder-item.active .folder-link{color:var(--brand);font-weight:600}.folder-item{display:flex;align-items:center;border-radius:8px}.folder-item>.el-dropdown{flex-shrink:0}.folder-item>.el-dropdown :deep(.el-button){padding:3px;width:25px;min-height:28px;margin-right:3px}.folder-divider{height:1px;background:var(--app-border);margin:10px 8px}.folder-scroll{max-height:calc(100dvh - 400px);min-height:80px;overflow:auto;margin-top:7px}.folder-rail>.el-input{padding:0 3px}.folder-empty{font-size:11px;line-height:1.7;padding:8px;color:var(--app-text-dim)}.folder-footnote{padding:16px 8px 0;font-size:10px;line-height:1.8;color:var(--app-text-dim);border-top:1px solid var(--app-border);margin-top:10px}.folder-footnote span{padding:0 4px}.saved-views{border-top:1px solid var(--app-border);padding-top:13px;margin-top:10px}.saved-view{display:flex;align-items:center;padding-left:8px}.saved-view>button{flex:1;border:0;background:none;text-align:left;color:var(--app-text-muted);font:inherit;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;cursor:pointer;padding:9px 0}.saved-view>button:hover{color:var(--brand)}
</style>
<style scoped>
.folder-item{position:relative}.folder-item>.folder-link{padding-left:3px;gap:6px}.folder-drag-handle{display:grid;place-items:center;align-self:stretch;flex:0 0 17px;padding:0;border:0;background:none;color:var(--app-text-dim);cursor:grab;touch-action:none;user-select:none;border-radius:5px;opacity:.65}.folder-item:hover>.folder-drag-handle,.folder-drag-handle:focus-visible{opacity:1;color:var(--brand)}.folder-drag-handle:active{cursor:grabbing}.folder-drag-handle:disabled{cursor:wait;opacity:.3}.is-reordering{user-select:none}.folder-item.is-dragging{opacity:.45}.folder-item.drop-before::before,.folder-item.drop-after::after{content:'';position:absolute;left:3px;right:3px;height:2px;background:var(--brand);border-radius:3px;pointer-events:none;z-index:2}.folder-item.drop-before::before{top:0}.folder-item.drop-after::after{bottom:0}.folder-order-saving{color:var(--app-text-muted);font-size:10px;padding:4px 8px}@media(pointer:coarse){.folder-drag-handle{flex-basis:27px;min-height:40px;opacity:1}}
</style>
