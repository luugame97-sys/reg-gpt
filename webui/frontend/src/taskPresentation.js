export function taskAttentionCount(job) {
  const number = value => Math.max(0, Number(value) || 0)
  const checks = job?.operation === 'token_check'
    ? ['expired_401', 'banned', 'missing', 'unknown', 'error'].reduce((sum, key) => sum + number(job.counts?.[key]), 0) : 0
  return Math.max(number(job?.failed), checks)
}

export function taskDisplayState(job) {
  return job?.state === 'completed' && taskAttentionCount(job) > 0 ? 'completed_errors' : job?.state || 'connecting'
}
