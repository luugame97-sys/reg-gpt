const { test } = require('node:test')
const assert = require('node:assert/strict')
const { pathToFileURL } = require('node:url')
const path = require('node:path')
const moduleUrl = pathToFileURL(path.join(__dirname, '../webui/frontend/src/webAuth.js')).href

test('login uses same-origin cookies, JSON and no browser Basic credentials', async () => {
  const { webAuthRequest } = await import(moduleUrl)
  const original = global.fetch
  let request
  global.fetch = async (url, options) => {
    request = { url, options }
    return { ok: true, json: async () => ({ authenticated: true }) }
  }
  try {
    assert.deepEqual(await webAuthRequest('login', { username: 'fixture', password: 'fixture-password' }), { authenticated: true })
    assert.equal(request.url, '/api/auth/login')
    assert.equal(request.options.credentials, 'same-origin')
    assert.equal(request.options.cache, 'no-store')
    assert.equal(request.options.method, 'POST')
    assert.equal(JSON.parse(request.options.body).password, 'fixture-password')
    assert.equal(request.options.headers.Authorization, undefined)
    await webAuthRequest('session')
    assert.equal(request.options.method, 'GET')
    assert.equal(request.options.body, undefined)
  } finally { global.fetch = original }
})

test('lockout preserves a retry countdown and login failure code', async () => {
  const { webAuthRequest } = await import(moduleUrl)
  const original = global.fetch
  global.fetch = async () => ({ ok: false, json: async () => ({ code: 'web_auth_rate_limited', retry_after: 900 }) })
  try {
    await assert.rejects(webAuthRequest('login', {}), (error) => error.code === 'web_auth_rate_limited' && error.retryAfter === 900)
  } finally { global.fetch = original }
})

test('network and invalid HTML responses fail visibly instead of succeeding', async () => {
  const { webAuthRequest } = await import(moduleUrl)
  const original = global.fetch
  try {
    global.fetch = async () => { throw new TypeError('fixture network error') }
    await assert.rejects(webAuthRequest('session'), /fixture network error/)
    global.fetch = async () => ({ ok: true, json: async () => { throw new SyntaxError('fixture HTML response') } })
    await assert.rejects(webAuthRequest('session'), /fixture HTML response/)
  } finally { global.fetch = original }
})

test('only our expired-session error requests the login interface', async () => {
  const { handleWebAuthError, AUTH_REQUIRED_EVENT } = await import(moduleUrl)
  const original = global.window
  const events = []
  global.window = { dispatchEvent: (event) => events.push(event.type) }
  try {
    assert.equal(handleWebAuthError({ response: { status: 401, data: { code: 'web_auth_required' } } }), true)
    for (const [status, code] of [[401, 'web_auth_invalid_credentials'], [401, 'provider_unauthorized'], [403, 'web_auth_required'], [503, 'web_auth_required']]) {
      assert.equal(handleWebAuthError({ response: { status, data: { code } } }), false)
    }
    assert.deepEqual(events, [AUTH_REQUIRED_EVENT])
  } finally { global.window = original }
})
