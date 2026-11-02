<script setup>
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { navigation, matchesNavigation } from '@/navigation'
import { t } from '@/stores/i18n'
const props = defineProps({ compact: Boolean })
const emit = defineEmits(['navigate', 'expand'])
const route = useRoute()
const opened = ref({})
const matches = item => matchesNavigation(item, route.path)
const childActive = item => item.children?.some(matches)
watch(() => route.path, () => { for (const item of navigation) if (childActive(item)) opened.value[item.id] = true }, { immediate: true })
function toggle(item) { if (props.compact) emit('expand'); opened.value[item.id] = !opened.value[item.id] }
</script>
<template>
  <nav class="workspace-nav" :aria-label="t('主导航')">
    <div v-for="item in navigation" :key="item.id || item.path" class="nav-entry">
      <router-link v-if="item.path" :to="item.path" class="nav-item" :class="{active:matches(item), compact}" :aria-current="matches(item) ? 'page' : undefined" :title="t(item.label)" @click="emit('navigate')"><el-icon :size="18"><component :is="item.icon" /></el-icon><span v-if="!compact">{{ t(item.label) }}</span></router-link>
      <template v-else>
        <button type="button" class="nav-item nav-group" :class="{active:childActive(item),compact}" :aria-expanded="!compact && !!opened[item.id]" :aria-controls="`nav-${item.id}`" :title="t(item.label)" @click="toggle(item)"><el-icon :size="19"><component :is="item.icon" /></el-icon><span v-if="!compact">{{ t(item.label) }}</span><el-icon v-if="!compact" class="nav-chevron" :class="{open:opened[item.id]}" :size="14"><ChevronDown /></el-icon></button>
        <div v-if="!compact && opened[item.id]" :id="`nav-${item.id}`" class="nav-children"><router-link v-for="child in item.children" :key="child.path" :to="child.path" class="nav-item" :class="{active:matches(child)}" :aria-current="matches(child) ? 'page' : undefined" @click="emit('navigate')"><el-icon :size="16"><component :is="child.icon" /></el-icon><span>{{ t(child.label) }}</span></router-link></div>
      </template>
    </div>
  </nav>
</template>
<style scoped>
.workspace-nav{display:flex;flex-direction:column;gap:4px;flex:1;overflow-y:auto;min-height:0}.nav-item{position:relative;width:100%;display:flex;align-items:center;gap:12px;min-height:36px;padding:8px 12px;border:1px solid transparent;border-radius:8px;background:transparent;text-decoration:none;color:var(--app-text-muted);font:inherit;font-size:13px;text-align:left;cursor:pointer;white-space:nowrap;transition:color .25s var(--workspace-ease),background-color .25s var(--workspace-ease),border-color .25s var(--workspace-ease)}.nav-item:hover{background:var(--app-card-surface);color:var(--app-title)}.nav-item.active{background:var(--app-card-hover);border-color:var(--app-border-subtle);color:var(--app-title);font-weight:500}.nav-item.active::before{content:'';position:absolute;left:0;top:50%;width:3px;height:18px;border-radius:3px;background:var(--brand);box-shadow:0 0 13px var(--brand-glow);transform:translateY(-50%);pointer-events:none}.nav-item.active>.el-icon:first-child{color:var(--brand)}.nav-item .el-icon{flex-shrink:0;width:18px;height:18px}.nav-chevron{margin-left:auto;transition:transform .35s var(--workspace-spring)}.nav-chevron.open{transform:rotate(180deg)}.nav-children{margin:4px 0 12px 20px;padding-left:12px;border-left:1px solid var(--app-border);display:flex;flex-direction:column;gap:4px}.nav-children .nav-item{font-size:12px;min-height:36px;padding:8px}.nav-item.compact{justify-content:center;padding-inline:8px}@media(pointer:coarse){.nav-item,.nav-children .nav-item{min-height:44px}}
</style>
