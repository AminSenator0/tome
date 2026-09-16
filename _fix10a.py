from pathlib import Path
p = Path(r"E:\SITE\tran\web\src\main.tsx")
src = p.read_text(encoding="utf-8")
old = "import { App } from './App'\n"
new = old + "import { I18nProvider } from './lib/i18n'\n"
assert src.count(old) == 1, "App import not found"
assert "I18nProvider" in src
p.write_text(src.replace(old, new), encoding="utf-8")
print("import added OK")
