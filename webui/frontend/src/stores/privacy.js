import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

const KEY = 'gpt_reg_hide_credentials'
export const usePrivacyStore = defineStore('privacy', () => {
  let saved = false
  try { saved = localStorage.getItem(KEY) === '1' } catch { /* private browsing */ }
  const hidden = ref(saved)
  watch(hidden, value => { try { localStorage.setItem(KEY, value ? '1' : '0') } catch { /* session only */ } })
  function toggle() { hidden.value = !hidden.value }
  return { hidden, toggle }
})
