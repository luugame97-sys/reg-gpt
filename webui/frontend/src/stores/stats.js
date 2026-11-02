import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getStats } from '@/api/accounts'

// One request at a time; background tabs retain data without polling.
export const useStatsStore = defineStore('stats', () => {
  const stats = ref({ total: 0, available: 0, in_use: 0, done: 0, failed: 0, plus_eligible: 0 })
  const refreshing = ref(false)
  const updatedAt = ref(0)
  let timer = null, pending = null, polling = false, pollInterval = 10000

  function refresh() {
    if (pending) return pending
    refreshing.value = true
    pending = getStats().then(({ stats: data }) => {
      if (data) { stats.value = data; updatedAt.value = Date.now() }
    }).catch((error) => { console.error('stats refresh:', error) }).finally(() => {
      refreshing.value = false
      pending = null
    })
    return pending
  }
  function schedule() {
    clearTimeout(timer)
    if (!polling || document.hidden) return
    timer = setTimeout(async () => { await refresh(); schedule() }, pollInterval)
  }
  function onVisibility() {
    clearTimeout(timer)
    if (!document.hidden && polling) refresh().finally(schedule)
  }
  function startPolling(interval = 10000) {
    pollInterval = interval
    if (polling) return
    polling = true
    document.addEventListener('visibilitychange', onVisibility)
    refresh().finally(schedule)
  }
  function stopPolling() {
    polling = false
    clearTimeout(timer)
    timer = null
    document.removeEventListener('visibilitychange', onVisibility)
  }
  return { stats, refreshing, updatedAt, refresh, startPolling, stopPolling }
})
