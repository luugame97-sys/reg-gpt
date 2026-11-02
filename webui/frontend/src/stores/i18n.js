import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import viVn from 'element-plus/es/locale/lang/vi'
import enUs from 'element-plus/es/locale/lang/en'
import { translateString } from '@/i18n/domTranslator'
import { LOCALE_CODES, localeTag, readStoredLocale, saveLocale } from '@/i18n/locale'

export const LOCALES = [
  { code: 'vi', label: 'Tiếng Việt', flag: '🇻🇳' },
  { code: 'zh', label: '简体中文', flag: '🇨🇳' },
  { code: 'en', label: 'English', flag: '🇺🇸' },
]

const elLocales = {
  vi: viVn,
  zh: zhCn,
  en: enUs,
}

export const useI18nStore = defineStore('i18n', () => {
  // Default is 'vi' (Vietnamese)
  const locale = ref(readStoredLocale())
  if (typeof document !== 'undefined') document.documentElement.lang = localeTag(locale.value)

  const elLocale = computed(() => elLocales[locale.value] || viVn)

  function setLocale(code) {
    if (LOCALE_CODES.includes(code)) {
      locale.value = code
      saveLocale(code)
      document.documentElement.lang = localeTag(code)
    }
  }

  function t(text, fallback) {
    if (!text || typeof text !== 'string') return text
    const translated = translateString(text, locale.value)
    return translated !== text || !fallback ? translated : translateString(fallback, locale.value)
  }

  return {
    locale,
    elLocale,
    setLocale,
    t,
  }
})

// Standalone t() helper for easy import in scripts
export function t(text, fallback) {
  try {
    const store = useI18nStore()
    return store.t(text, fallback)
  } catch (_) {
    const translated = translateString(text, readStoredLocale())
    return translated !== text || !fallback ? translated : translateString(fallback, readStoredLocale())
  }
}
