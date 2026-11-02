<script setup>
import { ref, watch } from 'vue'
import { filterOptions } from '@/accountFilters'
const props=defineProps({modelValue:Boolean,value:{type:Object,required:true},groups:{type:Array,default:()=>[]},countries:{type:Array,default:()=>[]}})
const emit=defineEmits(['update:modelValue','apply','save'])
const draft=ref({plans:[],tokens:[],errors:[],group:'all',country:'all',dates:null})
watch(()=>props.modelValue,open=>{if(open)draft.value=JSON.parse(JSON.stringify(props.value))})
function apply(save=false){emit(save?'save':'apply',JSON.parse(JSON.stringify(draft.value)));emit('update:modelValue',false)}
function reset(){draft.value={...draft.value,plans:[],tokens:[],errors:[],group:'all',country:'all',dates:null}}
</script>
<template>
 <el-drawer :model-value="modelValue" title="Lọc tài khoản" size="min(460px, 100vw)" class="account-filter-sheet" @update:model-value="emit('update:modelValue',$event)">
  <p class="filter-sheet-intro">Chọn nhiều giá trị trong một mục. Các mục khác nhau được kết hợp với nhau.</p>
  <el-form label-position="top" class="filter-sheet-form">
   <el-form-item label="Thư mục"><el-select v-model="draft.group" filterable aria-label="Lọc theo thư mục"><template #label="{ label, value }"><span :translate="['all','__ungrouped__'].includes(value) ? undefined : 'no'">{{ label }}</span></template><el-option label="Tất cả thư mục" value="all" /><el-option label="Chưa phân thư mục" value="__ungrouped__" /><el-option v-for="group in groups" translate="no" :key="group.name" :value="group.name" :label="`${group.name} (${group.count})`" /></el-select></el-form-item>
   <el-form-item v-for="[field,label] in [['plans','Gói tài khoản / Ưu đãi'],['tokens','Trạng thái AT'],['errors','Lỗi cần xử lý']]" :key="field" :label="label"><el-select v-model="draft[field]" multiple clearable filterable :aria-label="label" placeholder="Tất cả"><el-option v-for="[value,name] in filterOptions[field]" :key="value" :value="value" :label="name" /></el-select></el-form-item>
   <el-form-item label="Quốc gia"><el-select v-model="draft.country" filterable aria-label="Quốc gia trong bộ lọc"><el-option label="Tất cả quốc gia" value="all" /><el-option v-for="country in countries" :key="country.country" :value="country.country" :label="`${country.country} (${country.count})`" /></el-select></el-form-item>
   <el-form-item label="Ngày tạo"><el-date-picker v-model="draft.dates" type="daterange" unlink-panels value-format="YYYY-MM-DD" format="DD/MM/YYYY" start-placeholder="Từ ngày" end-placeholder="Đến ngày" style="width:100%" /></el-form-item>
  </el-form>
  <template #footer><div class="filter-sheet-actions"><el-button text @click="reset">Xóa điều kiện</el-button><el-button @click="apply(true)">Lưu bộ lọc…</el-button><el-button type="primary" @click="apply()">Áp dụng</el-button></div></template>
 </el-drawer>
</template>
<style scoped>
.filter-sheet-intro{margin:0 0 23px;font-size:12px;line-height:1.7;color:var(--app-text-muted)}.filter-sheet-form :deep(.el-select){width:100%}.filter-sheet-form :deep(.el-form-item){margin-bottom:21px}.filter-sheet-actions{display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap}.filter-sheet-actions .el-button{margin:0}
</style>
