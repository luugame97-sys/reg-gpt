const test = require('node:test')
const assert = require('node:assert/strict')
const { pathToFileURL } = require('node:url')
const path = require('node:path')

const modulePromise = import(pathToFileURL(path.join(__dirname, '../webui/frontend/src/totp.js')).href)
const secret = 'GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ'

test('TOTP matches RFC 6238 SHA-1 vectors with six digits, including leading zeroes', async () => {
  const { createTotpGenerator } = await modulePromise
  const generate = await createTotpGenerator(secret)
  for (const [seconds, code] of [[59, '287082'], [1111111109, '081804'], [1111111111, '050471'], [1234567890, '005924'], [2000000000, '279037'], [20000000000, '353130']]) {
    assert.equal(await generate(seconds * 1000), code, `time=${seconds}`)
  }
})

test('OTP remains stable for a 30-second window and changes at its boundary', async () => {
  const { createTotpGenerator } = await modulePromise
  const generate = await createTotpGenerator(secret)
  assert.equal(await generate(30_000), '287082')
  assert.equal(await generate(59_999), '287082')
  assert.equal(await generate(60_000), '359152')
})

test('accepts the same formatted secrets and otpauth secret parameter as account editing', async () => {
  const { createTotpGenerator } = await modulePromise
  for (const formatted of ['gezd gnbv-gy3t_qojq gezdgnbvgy3tqojq', `otpauth://totp/Fixture?secret=${secret}&issuer=Fixture`, 'GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOI=']) {
    const generate = await createTotpGenerator(formatted)
    assert.match(await generate(59_000), /^\d{6}$/)
  }
  const formatted = await createTotpGenerator('gezd gnbv-gy3t_qojq gezdgnbvgy3tqojq')
  assert.equal(await formatted(59_000), '287082')
})

test('rejects empty, malformed, incorrectly padded, and short secrets without generating an OTP', async () => {
  const { createTotpGenerator } = await modulePromise
  for (const invalid of ['', 'invalid!key', '123456', 'A'.repeat(17), 'A'.repeat(32) + '=', 'GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOI==', 'otpauth://totp/Fixture?issuer=Fixture', 'JBSWY3DP']) {
    await assert.rejects(createTotpGenerator(invalid), /Khóa 2FA/)
  }
  const generate = await createTotpGenerator(secret)
  await assert.rejects(generate(-1), /Thời gian/)
  await assert.rejects(generate(NaN), /Thời gian/)
})
