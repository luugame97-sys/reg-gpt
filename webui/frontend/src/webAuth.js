export const AUTH_REQUIRED_EVENT = 'reg-web-auth-required'

export function handleWebAuthError(error) {
  if (error?.response?.status !== 401 || error?.response?.data?.code !== 'web_auth_required') return false
  window.dispatchEvent(new Event(AUTH_REQUIRED_EVENT))
  return true
}

export async function webAuthRequest(path, body) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 15000)
  try {
    const response = await fetch(`/api/auth/${path}`, {
      method: body === undefined ? 'GET' : 'POST',
      credentials: 'same-origin',
      cache: 'no-store',
      signal: controller.signal,
      headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    })
    const data = await response.json()
    if (!response.ok) {
      const error = new Error(data.code || 'web_auth_unavailable')
      error.code = data.code
      error.retryAfter = Number(data.retry_after || response.headers.get('Retry-After') || 0)
      throw error
    }
    return data
  } finally {
    clearTimeout(timer)
  }
}
