#!/usr/bin/env python3
# Fix for phase 10a: ensures main.tsx imports I18nProvider (regex-tolerant) and
# wraps <App /> with it. Idempotent.
# Usage: python tome_phase10a_fix.py --apply   (+ npm run build)
import argparse, re, sys
from pathlib import Path

IMPORT_LINE = "import { I18nProvider } from './lib/i18n'\n"


def patch_main(src: str) -> tuple[str, int]:
    n = 0
    if "from './lib/i18n'" not in src and 'from "./lib/i18n"' not in src:
        m = re.search(r"import App from ['\"]\./App(\.tsx|\.ts|\.js)?['\"]\n", src)
        if m:
            src = src.replace(m.group(0), m.group(0) + IMPORT_LINE, 1)
            n += 1
        elif "import App from" in src:
            # fallback: insert right after any App import line
            m2 = re.search(r"import App from .*\n", src)
            if m2:
                src = src.replace(m2.group(0), m2.group(0) + IMPORT_LINE, 1)
                n += 1
    if "<I18nProvider>" not in src and "<App />" in src:
        src = src.replace("<App />", "<I18nProvider><App /></I18nProvider>", 1)
        n += 1
    return src, n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--webdir", default="web/src")
    args = ap.parse_args()
    p = Path(args.webdir) / "main.tsx"
    if not p.is_file():
        sys.exit(f"not found: {p}")
    raw = p.read_bytes()
    src = raw.decode("utf-8")
    norm = src.replace("\r\n", "\n")
    new_norm, n = patch_main(norm)
    if "from './lib/i18n'" not in new_norm and 'from "./lib/i18n"' not in new_norm:
        print("[NOT FIXED] could not find an App import in main.tsx — paste its content")
        sys.exit(2)
    if "<I18nProvider>" not in new_norm:
        print("[NOT FIXED] could not find <App /> in main.tsx — paste its content")
        sys.exit(2)
    if n == 0:
        print("already applied")
        return
    if not args.apply:
        print(f"dry-run: would add {n} missing piece(s) to main.tsx")
        return
    out = new_norm.replace("\n", "\r\n") if b"\r\n" in raw else new_norm
    p.with_suffix(".tsx.bak").write_bytes(raw)
    p.write_bytes(out.encode("utf-8"))
    print(f"fixed main.tsx ({n} piece(s)) — now run: cd web && npm run build")


if __name__ == "__main__":
    main()