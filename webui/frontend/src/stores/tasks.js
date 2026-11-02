import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { findTokenRefreshJobs, listRuns } from '@/api/register'
export const useTasksStore = defineStore('tasks', () => {
  const jobs = ref([]), runs = ref([]), error = ref(''), updatedAt = ref(0), loading = ref(false)
  const activeJobs = computed(() => jobs.value.filter(job => ['queued', 'running', 'stopping'].includes(job.state)))
  let pending = null, timer = null, enabled = false
  async function refresh() {
    if (pending) return pending
    loading.value = true
    pending = (async () => {
      const results = await Promise.allSettled([findTokenRefreshJobs({summary:true,limit:30}), listRuns(1000,{summary:true,active_only:true})])
      if (results[0].status === 'fulfilled') jobs.value = results[0].value.jobs || []
      if (results[1].status === 'fulfilled') runs.value = results[1].value.items || []
      error.value = results.some(result => result.status === 'rejected') ? 'Chưa cập nhật được đầy đủ trạng thái tác vụ.' : ''
      if (!error.value) updatedAt.value = Date.now()
    })().finally(() => { pending = null; loading.value = false })
    return pending
  }
  function schedule() {
    clearTimeout(timer)
    if (!enabled || document.hidden) return
    timer = setTimeout(async () => { await refresh(); schedule() }, activeJobs.value.length || runs.value.length ? 8000 : 20000)
  }
  function visibility() { clearTimeout(timer); if (!document.hidden && enabled) refresh().finally(schedule) }
  function start() { if (enabled) return; enabled = true; document.addEventListener('visibilitychange', visibility); refresh().finally(schedule) }
  function stop() { enabled = false; clearTimeout(timer); document.removeEventListener('visibilitychange', visibility) }
  return {jobs,runs,activeJobs,error,updatedAt,loading,refresh,start,stop}
})
