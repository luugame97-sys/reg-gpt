import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { cancelTokenRefreshJob, findTokenRefreshJobs, getTokenRefreshJob, startTokenCheckJob, startTokenRefreshJob } from '@/api/register'

const JOB_KEY = 'token_refresh_job_id'
const REQUEST_KEY = 'token_refresh_request_id'
const CANCEL_KEY = 'token_refresh_cancel_job_id'
const isActive = (job) => ['queued', 'running', 'stopping'].includes(job?.state)

export const useTokenRefreshStore = defineStore('tokenRefresh', () => {
  const job = ref(null)
  const starting = ref(false)
  const cancelling = ref(false)
  const pendingCancelId = ref(localStorage.getItem(CANCEL_KEY) || '')
  const connectionError = ref('')
  const running = computed(() => starting.value || cancelling.value || isActive(job.value))
  const stopRequested = computed(() => Boolean(job.value?.cancel_requested || (pendingCancelId.value && pendingCancelId.value === job.value?.job_id)))
  let timer = null
  let pending = null
  let cancelPromise = null

  function clearPendingCancel() {
    pendingCancelId.value = ''
    localStorage.removeItem(CANCEL_KEY)
  }

  function accept(data) {
    if (job.value?.job_id === data.job_id && Number(job.value.updated_at || 0) > Number(data.updated_at || 0)) return
    job.value = data
    connectionError.value = ''
    localStorage.setItem(JOB_KEY, data.job_id)
    localStorage.removeItem(REQUEST_KEY)
    if (pendingCancelId.value === data.job_id) {
      if (data.cancel_requested || !isActive(data)) clearPendingCancel()
      else connectionError.value = 'Chưa xác nhận được lệnh dừng. Hệ thống đang tự gửi lại; tác vụ có thể vẫn chạy.'
    }
  }
  function schedule() {
    clearTimeout(timer)
    if (isActive(job.value) || (!job.value && localStorage.getItem(JOB_KEY))) {
      timer = setTimeout(poll, connectionError.value ? 5000 : 2000)
    }
  }
  function poll() {
    if (pending) return pending
    const jobId = job.value?.job_id || localStorage.getItem(JOB_KEY)
    if (!jobId) return Promise.resolve()
    pending = (async () => {
      try {
        if (pendingCancelId.value === jobId) {
          try { await sendCancel(jobId) } catch (_) { /* Read progress to recover a lost acknowledgement. */ }
        }
        const data = await getTokenRefreshJob(jobId)
        accept(data.job)
      } catch (error) {
        if (error.status === 404) {
          localStorage.removeItem(JOB_KEY)
          job.value = null
          if (pendingCancelId.value === jobId) clearPendingCancel()
          connectionError.value = error.message
        } else {
          connectionError.value = pendingCancelId.value === jobId
            ? 'Chưa xác nhận được lệnh dừng. Hệ thống sẽ gửi lại khi có kết nối; tác vụ có thể vẫn chạy.'
            : 'Chưa kết nối được để lấy tiến độ. Tác vụ trên máy chủ vẫn tiếp tục; hệ thống sẽ tự kết nối lại.'
        }
      } finally {
        pending = null
        schedule()
      }
    })()
    return pending
  }
  async function restore() {
    if (pending || starting.value) return pending
    if (!localStorage.getItem(JOB_KEY) && pendingCancelId.value) localStorage.setItem(JOB_KEY, pendingCancelId.value)
    if (job.value || localStorage.getItem(JOB_KEY)) {
      await poll()
      if (isActive(job.value) || pendingCancelId.value || connectionError.value) return
      // A remembered, finished job must not hide work started in another tab.
    }
    try {
      const requestId = localStorage.getItem(REQUEST_KEY)
      const { jobs } = await findTokenRefreshJobs(requestId ? { request_id: requestId } : { active_only: true })
      if (jobs?.length) { accept(jobs[0]); schedule() }
    } catch (_) {
      connectionError.value = 'Chưa lấy được trạng thái làm mới token. Có thể tải lại tiến độ khi kết nối ổn định.'
    }
  }
  async function follow(jobId) {
    if (!jobId || job.value?.job_id === jobId) return restore()
    if (pendingCancelId.value && pendingCancelId.value !== jobId) throw new Error('Đang xác nhận lệnh dừng. Hãy chờ xác nhận trước khi đổi tác vụ.')
    clearTimeout(timer)
    if (pending) await pending
    clearTimeout(timer)
    const { job: data } = await getTokenRefreshJob(jobId)
    accept(data)
    schedule()
  }
  function sendCancel(jobId) {
    if (cancelPromise) return cancelPromise
    cancelPromise = (async () => {
      const { job: data } = await cancelTokenRefreshJob(jobId)
      if (!job.value || job.value.job_id === jobId) accept(data)
      return data
    })().finally(() => { cancelPromise = null })
    return cancelPromise
  }
  async function cancel() {
    const jobId = job.value?.job_id || localStorage.getItem(JOB_KEY)
    if (!jobId || cancelling.value) return
    pendingCancelId.value = jobId
    localStorage.setItem(CANCEL_KEY, jobId)
    cancelling.value = true
    try {
      return await sendCancel(jobId)
    } catch (error) {
      if (error.status === 404) clearPendingCancel()
      connectionError.value = 'Chưa xác nhận được lệnh dừng. Hệ thống sẽ gửi lại khi có kết nối; tác vụ có thể vẫn chạy.'
      throw error
    } finally {
      cancelling.value = false
      schedule()
    }
  }
  async function start(emails, proxy = '', otpTimeout = 180, proxyMode = 'pool', onlyExpired = false, operation = 'token_refresh', workers = null, skipUsable = true, includeMissing = true, retrySourceJobId = '', smartRefresh = true, refreshUsable = false) {
    if (starting.value) return
    starting.value = true
    const requestId = localStorage.getItem(REQUEST_KEY) || crypto.randomUUID()
    localStorage.setItem(REQUEST_KEY, requestId)
    try {
      const payload = { emails, proxy: proxyMode === 'single' ? proxy : '', proxy_mode: proxyMode, request_id: requestId }
      if (workers !== null) payload.workers = workers
      if (operation === 'token_refresh') Object.assign(payload, { otp_timeout: otpTimeout, only_expired: onlyExpired, include_missing: onlyExpired && includeMissing, smart_refresh: smartRefresh })
      else payload.operation = operation
      if (operation === 'token_refresh' && refreshUsable) Object.assign(payload, { refresh_usable: true, smart_refresh: true, only_expired: false, include_missing: false })
      if (operation === 'token_check') payload.skip_usable = skipUsable
      if (operation === 'token_refresh' && retrySourceJobId) {
        payload.retry_source_job_id = retrySourceJobId
        payload.only_expired = false
        payload.include_missing = false
      }
      const { job: data } = await (operation !== 'token_refresh' ? startTokenCheckJob(payload) : startTokenRefreshJob(payload))
      accept(data)
      schedule()
      return data
    } catch (error) {
      // A lost submit response must not start the same refresh twice.
      const activeId = error.data?.detail?.job_id
      try {
        if (activeId) {
          const { job: data } = await getTokenRefreshJob(activeId)
          accept(data)
          schedule()
        } else {
          const { jobs } = await findTokenRefreshJobs({ request_id: requestId })
          if (jobs?.length) { accept(jobs[0]); schedule(); return jobs[0] }
        }
      } catch (_) { /* Keep the request id for a safe retry. */ }
      throw error
    } finally {
      starting.value = false
    }
  }
  return { job, running, starting, cancelling, stopRequested, connectionError, start, restore, poll, cancel, follow }
})
