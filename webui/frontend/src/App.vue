<script setup>
import { storeToRefs } from 'pinia'
import { useI18nStore } from '@/stores/i18n'
import AdminLayout from '@/layouts/AdminLayout.vue'

const i18n = useI18nStore()
const { elLocale } = storeToRefs(i18n)
</script>

<template>
  <el-config-provider :locale="elLocale">
    <AdminLayout />
  </el-config-provider>
</template>
