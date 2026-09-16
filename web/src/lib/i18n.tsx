import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'

export type Lang = 'en' | 'fa'

const DICT: Record<Lang, Record<string, string>> = {
  en: {
    'menu.label': 'Menu',
    'nav.bookshelf': 'Overview & Library',
    'nav.pipeline': 'Pipeline Studio',
    'nav.tools': 'Standalone Lab',
    'nav.prompts': 'Prompt Studio',
    'nav.metrics': 'Cost Dashboard',
    'nav.settings': 'System Settings',
    'lang.switch': 'فارسی',
    'login.title': 'Sign in to Tome',
    'login.subtitle': 'Enter your credentials to access your library',
    'login.username': 'Username',
    'login.password': 'Password',
    'login.signin': 'Sign In',
    'login.error': 'Invalid username or password.',
    'common.save': 'Save',
    'common.cancel': 'Cancel',
    'common.delete': 'Delete',
    'common.retry': 'Retry',
    'common.refresh': 'Refresh',
    'common.loading': 'Loading...',
  },
  fa: {
    'menu.label': 'منو',
    'nav.bookshelf': 'کتابخانه',
    'nav.pipeline': 'استودیوی پایپ‌لاین',
    'nav.tools': 'ابزارهای مستقل',
    'nav.prompts': 'استودیوی پرامپت',
    'nav.metrics': 'داشبورد هزینه',
    'nav.settings': 'تنظیمات سیستم',
    'lang.switch': 'English',
    'login.title': 'ورود به توم',
    'login.subtitle': 'برای دسترسی به کتابخانه وارد شوید',
    'login.username': 'نام کاربری',
    'login.password': 'رمز عبور',
    'login.signin': 'ورود',
    'login.error': 'نام کاربری یا رمز عبور نامعتبر است.',
    'common.save': 'ذخیره',
    'common.cancel': 'لغو',
    'common.delete': 'حذف',
    'common.retry': 'تلاش مجدد',
    'common.refresh': 'به‌روزرسانی',
    'common.loading': 'در حال بارگذاری...',
  },
}

interface I18nCtx {
  lang: Lang
  setLang: (l: Lang) => void
  t: (key: string) => string
  isRtl: boolean
}

const Ctx = createContext<I18nCtx>({
  lang: 'en',
  setLang: () => undefined,
  t: (k: string) => k,
  isRtl: false,
})

export const I18nProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [lang, setLangState] = useState<Lang>(() => {
    try {
      return localStorage.getItem('tome_lang') === 'fa' ? 'fa' : 'en'
    } catch {
      return 'en'
    }
  })

  const setLang = useCallback((l: Lang) => {
    setLangState(l)
    try {
      localStorage.setItem('tome_lang', l)
    } catch {
      /* ignore */
    }
  }, [])

  const t = useCallback((key: string) => DICT[lang][key] ?? DICT.en[key] ?? key, [lang])
  const isRtl = lang === 'fa'

  useEffect(() => {
    document.documentElement.lang = lang
    document.documentElement.dir = isRtl ? 'rtl' : 'ltr'
  }, [lang, isRtl])

  return <Ctx.Provider value={{ lang, setLang, t, isRtl }}>{children}</Ctx.Provider>
}

export const useI18n = () => useContext(Ctx)
