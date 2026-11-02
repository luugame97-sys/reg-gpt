export const TOTP_PERIOD_MS = 30_000

function decodeSecret(raw) {
  let secret = String(raw || '').trim()
  if (/^otpauth:\/\//i.test(secret)) {
    try { secret = new URL(secret).searchParams.get('secret') || '' }
    catch { throw new Error('Khóa 2FA không hợp lệ') }
  }
  secret = secret.replace(/[\s_-]/g, '').toUpperCase()
  if (!/^[A-Z2-7]+=*$/.test(secret)) throw new Error('Khóa 2FA không hợp lệ')
  const value = secret.replace(/=+$/, '')
  const padding = ({ 0: 0, 2: 6, 4: 4, 5: 3, 7: 1 })[value.length % 8]
  if (padding === undefined || (secret.includes('=') && secret.length - value.length !== padding)) {
    throw new Error('Khóa 2FA không hợp lệ')
  }
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'
  const bytes = []
  let buffer = 0, bits = 0
  for (const char of value) {
    buffer = (buffer << 5) | alphabet.indexOf(char)
    bits += 5
    if (bits >= 8) {
      bits -= 8
      bytes.push((buffer >>> bits) & 255)
      buffer &= (1 << bits) - 1
    }
  }
  if (bytes.length < 10) throw new Error('Khóa 2FA quá ngắn')
  return new Uint8Array(bytes)
}

// Keep the key in memory only. OTP generation never sends the secret to a server.
export async function createTotpGenerator(secret) {
  const bytes = decodeSecret(secret)
  if (!globalThis.crypto?.subtle) throw new Error('Cần HTTPS để tạo OTP')
  const key = await crypto.subtle.importKey('raw', bytes, { name: 'HMAC', hash: 'SHA-1' }, false, ['sign'])
  return async (now = Date.now()) => {
    if (!Number.isFinite(now) || now < 0) throw new Error('Thời gian OTP không hợp lệ')
    const message = new ArrayBuffer(8)
    new DataView(message).setBigUint64(0, BigInt(Math.floor(now / TOTP_PERIOD_MS)))
    const digest = new Uint8Array(await crypto.subtle.sign('HMAC', key, message))
    const offset = digest[digest.length - 1] & 15
    const code = new DataView(digest.buffer).getUint32(offset) & 0x7fffffff
    return String(code % 1_000_000).padStart(6, '0')
  }
}
