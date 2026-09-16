#!/usr/bin/env python3
# Tome Phase 10a — bilingual foundation (fa/en).
#
# - New web/src/lib/i18n.tsx: provider + dictionaries + RTL direction handling.
# - main.tsx: wraps <App /> with <I18nProvider>.
# - Sidebar: translated menu labels + language switcher (bottom).
# - LoginView: translated strings.
#
# Views not covered yet (Bookshelf/Studio/Pipeline/Tools/Settings/Dashboard) keep
# English until phases 10b/10c — missing keys fall back to the key itself (English).
#
# Usage:  python tome_phase10a.py            (dry-run)
#         python tome_phase10a.py --apply    (+ npm run build)
import argparse, sys
from pathlib import Path

I18N_TSX = "import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'\n\nexport type Lang = 'en' | 'fa'\n\nconst DICT: Record<Lang, Record<string, string>> = {\n  en: {\n    'menu.label': 'Menu',\n    'nav.bookshelf': 'Overview & Library',\n    'nav.pipeline': 'Pipeline Studio',\n    'nav.tools': 'Standalone Lab',\n    'nav.prompts': 'Prompt Studio',\n    'nav.metrics': 'Cost Dashboard',\n    'nav.settings': 'System Settings',\n    'lang.switch': 'فارسی',\n    'login.title': 'Sign in to Tome',\n    'login.subtitle': 'Enter your credentials to access your library',\n    'login.username': 'Username',\n    'login.password': 'Password',\n    'login.signin': 'Sign In',\n    'login.error': 'Invalid username or password.',\n    'common.save': 'Save',\n    'common.cancel': 'Cancel',\n    'common.delete': 'Delete',\n    'common.retry': 'Retry',\n    'common.refresh': 'Refresh',\n    'common.loading': 'Loading...',\n  },\n  fa: {\n    'menu.label': 'منو',\n    'nav.bookshelf': 'کتابخانه',\n    'nav.pipeline': 'استودیوی پایپ\u200cلاین',\n    'nav.tools': 'ابزارهای مستقل',\n    'nav.prompts': 'استودیوی پرامپت',\n    'nav.metrics': 'داشبورد هزینه',\n    'nav.settings': 'تنظیمات سیستم',\n    'lang.switch': 'English',\n    'login.title': 'ورود به توم',\n    'login.subtitle': 'برای دسترسی به کتابخانه وارد شوید',\n    'login.username': 'نام کاربری',\n    'login.password': 'رمز عبور',\n    'login.signin': 'ورود',\n    'login.error': 'نام کاربری یا رمز عبور نامعتبر است.',\n    'common.save': 'ذخیره',\n    'common.cancel': 'لغو',\n    'common.delete': 'حذف',\n    'common.retry': 'تلاش مجدد',\n    'common.refresh': 'به\u200cروزرسانی',\n    'common.loading': 'در حال بارگذاری...',\n  },\n}\n\ninterface I18nCtx {\n  lang: Lang\n  setLang: (l: Lang) => void\n  t: (key: string) => string\n  isRtl: boolean\n}\n\nconst Ctx = createContext<I18nCtx>({\n  lang: 'en',\n  setLang: () => undefined,\n  t: (k: string) => k,\n  isRtl: false,\n})\n\nexport const I18nProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {\n  const [lang, setLangState] = useState<Lang>(() => {\n    try {\n      return localStorage.getItem('tome_lang') === 'fa' ? 'fa' : 'en'\n    } catch {\n      return 'en'\n    }\n  })\n\n  const setLang = useCallback((l: Lang) => {\n    setLangState(l)\n    try {\n      localStorage.setItem('tome_lang', l)\n    } catch {\n      /* ignore */\n    }\n  }, [])\n\n  const t = useCallback((key: string) => DICT[lang][key] ?? DICT.en[key] ?? key, [lang])\n  const isRtl = lang === 'fa'\n\n  useEffect(() => {\n    document.documentElement.lang = lang\n    document.documentElement.dir = isRtl ? 'rtl' : 'ltr'\n  }, [lang, isRtl])\n\n  return <Ctx.Provider value={{ lang, setLang, t, isRtl }}>{children}</Ctx.Provider>\n}\n\nexport const useI18n = () => useContext(Ctx)\n"


def patch_main(src: str) -> tuple[str, int]:
    n = 0
    old = "import App from './App'\n"
    if old in src and "I18nProvider" not in src:
        src = src.replace(old, old + "import { I18nProvider } from './lib/i18n'\n", 1)
        n += 1
    if "<App />" in src and "<I18nProvider>" not in src:
        src = src.replace("<App />", "<I18nProvider><App /></I18nProvider>", 1)
        n += 1
    return src, n


def patch_sidebar(src: str) -> tuple[str, int]:
    n = 0
    old = "import { Logo } from './ui/Logo'\n"
    if old in src and "useI18n" not in src:
        src = src.replace(old, old + "import { useI18n } from '../lib/i18n'\n", 1)
        n += 1
    old = "  Settings,\n  ChevronLeft,\n} from 'lucide-react'\n"
    if old in src and "Languages," not in src:
        src = src.replace(old, "  Settings,\n  Languages,\n  ChevronLeft,\n} from 'lucide-react'\n", 1)
        n += 1
    old = "}) => {\n  const menuItems = [\n"
    if old in src and "const { t, lang, setLang } = useI18n()" not in src:
        src = src.replace(old, "}) => {\n  const { t, lang, setLang } = useI18n()\n\n  const menuItems = [\n", 1)
        n += 1
    label_map = [
        ("label: 'Overview & Library'", "label: t('nav.bookshelf')"),
        ("label: 'Pipeline Studio'", "label: t('nav.pipeline')"),
        ("label: 'Standalone Lab'", "label: t('nav.tools')"),
        ("label: 'Prompt Studio'", "label: t('nav.prompts')"),
        ("label: 'System Settings'", "label: t('nav.settings')"),
        ("label: 'Cost Dashboard'", "label: t('nav.metrics')"),
    ]
    for o, nn in label_map:
        if o in src:
            src = src.replace(o, nn, 1)
            n += 1
    old = "              Menu\n"
    if old in src:
        src = src.replace(old, "              {t('menu.label')}\n", 1)
        n += 1
    old = "        </div>\n      </aside>\n    </>"
    new = (
        "        </div>\n"
        "        <div className=\"p-4 border-t border-border/40\">\n"
        "          <button\n"
        "            onClick={() => setLang(lang === 'fa' ? 'en' : 'fa')}\n"
        "            className=\"w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-full text-xs font-medium bg-secondary text-muted-foreground hover:text-foreground transition-colors border-0 cursor-pointer\"\n"
        "          >\n"
        "            <Languages className=\"h-4 w-4\" strokeWidth={1.5} />\n"
        "            <span>{t('lang.switch')}</span>\n"
        "          </button>\n"
        "        </div>\n"
        "      </aside>\n"
        "    </>"
    )
    if old in src and "setLang(lang === 'fa'" not in src:
        src = src.replace(old, new, 1)
        n += 1
    return src, n


def patch_login(src: str) -> tuple[str, int]:
    n = 0
    old = "import { Logo } from '../components/ui/Logo'\n"
    if old in src and "useI18n" not in src:
        src = src.replace(old, old + "import { useI18n } from '../lib/i18n'\n", 1)
        n += 1
    old = "export const LoginView: React.FC<LoginViewProps> = ({ onSuccess }) => {\n"
    if old in src and "const { t } = useI18n()" not in src:
        src = src.replace(old, old + "  const { t } = useI18n()\n", 1)
        n += 1
    pairs = [
        ("              Sign in to Tome\n", "              {t('login.title')}\n"),
        ("              Enter your credentials to access your library\n", "              {t('login.subtitle')}\n"),
        ("              Username\n", "              {t('login.username')}\n"),
        ("              Password\n", "              {t('login.password')}\n"),
        ('placeholder="Username"', 'placeholder={t(\'login.username\')}'),
        ('placeholder="Password"', 'placeholder={t(\'login.password\')}'),
        ("              <span>Sign In</span>", "              <span>{t('login.signin')}</span>"),
        ("err.message || 'Invalid username or password.'", "err.message || t('login.error')"),
    ]
    for o, nn in pairs:
        if o in src:
            src = src.replace(o, nn, 1)
            n += 1
    return src, n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--webdir", default="web/src")
    args = ap.parse_args()
    print(f"mode: {'APPLY' if args.apply else 'DRY-RUN'}")

    i18n_path = Path(args.webdir) / "lib" / "i18n.tsx"
    existing = i18n_path.read_text(encoding="utf-8") if i18n_path.is_file() else None
    if existing == I18N_TSX:
        print("  [already applied] lib/i18n.tsx")
    elif existing is not None:
        print("  [DIFFERS] lib/i18n.tsx exists with different content — refusing to overwrite")
        sys.exit(2)
    elif args.apply:
        i18n_path.parent.mkdir(parents=True, exist_ok=True)
        i18n_path.write_text(I18N_TSX, encoding="utf-8")
        print("  [OK] wrote lib/i18n.tsx")
    else:
        print("  [would write] lib/i18n.tsx")

    jobs = [
        ("main.tsx: I18nProvider wrapper", Path(args.webdir) / "main.tsx", patch_main, True),
        ("Sidebar.tsx: labels + switcher", Path(args.webdir) / "components" / "Sidebar.tsx", patch_sidebar, True),
        ("LoginView.tsx: translations", Path(args.webdir) / "views" / "LoginView.tsx", patch_login, True),
    ]
    for name, path, fn, required in jobs:
        if not path.is_file():
            print(f"  [MISSING] {name} — {path}")
            continue
        raw = path.read_bytes()
        src = raw.decode("utf-8")
        norm = src.replace("\r\n", "\n")
        new_norm, n = fn(norm)
        if n >= 1:
            status = "OK"
        elif new_norm == norm:
            status = "already applied"
        else:
            status = "NOT FOUND"
        print(f"  [{status:>16}] {name}")
        if new_norm != norm and n >= 1 and args.apply:
            out = new_norm.replace("\n", "\r\n") if b"\r\n" in raw else new_norm
            path.with_suffix(path.suffix + ".bak").write_bytes(raw)
            path.write_bytes(out.encode("utf-8"))
            print(f"         patched {path.name} (.bak saved)")
        elif new_norm != norm and n >= 1:
            print("         (dry-run)")
    if args.apply:
        print("\nDone. Rebuild:  cd web && npm run build")


if __name__ == "__main__":
    main()