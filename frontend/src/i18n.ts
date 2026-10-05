import { createI18n } from 'vue-i18n'
import en from './locales/en.js'
import zh from './locales/zh.js'

const savedLocale = localStorage.getItem('relay-locale')

export const i18n = createI18n({
  legacy: false,
  locale: savedLocale === 'zh' ? 'zh' : 'en',
  fallbackLocale: 'en',
  messages: { en, zh },
})