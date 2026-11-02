export const DEFAULT_LOCALE = 'vi'
export const LOCALE_CODES = ['vi', 'en', 'zh']
export function validLocale(code) { return LOCALE_CODES.includes(code) ? code : DEFAULT_LOCALE }
export function readStoredLocale() {
  try { return validLocale(localStorage.getItem('app_locale')) }
  catch { return DEFAULT_LOCALE }
}
export function saveLocale(code) {
  try { localStorage.setItem('app_locale', validLocale(code)) } catch { /* Storage may be disabled. */ }
}
export function localeTag(code = readStoredLocale()) { return ({vi:'vi-VN', en:'en-US', zh:'zh-CN'})[validLocale(code)] }
