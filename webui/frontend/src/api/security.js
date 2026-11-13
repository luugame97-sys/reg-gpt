import http from './request'

export const createSecurityJob = payload => http.post('/api/security/jobs', payload)
export const listSecurityJobs = () => http.get('/api/security/jobs')
export const getSecurityJob = (id, params = {}) => http.get(`/api/security/jobs/${encodeURIComponent(id)}`, { params })
export const stopSecurityJob = id => http.post(`/api/security/jobs/${encodeURIComponent(id)}/stop`, {})
export const resumeSecurityJob = (id, payload) => http.post(`/api/security/jobs/${encodeURIComponent(id)}/resume`, payload)
export const getSecurityRecovery = id => http.post(`/api/security/jobs/${encodeURIComponent(id)}/recovery`, {})
