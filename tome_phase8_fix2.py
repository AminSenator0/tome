#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tome_phase8_fix2.py - second repair pass
Run from the repo root:

    python tome_phase8_fix2.py           # dry-run
    python tome_phase8_fix2.py --apply   # apply (backs up to .tome_backup_*)

Fixes:
  1. Navbar.tsx -> corrected version (matches your App.tsx; only the two
     button tooltips go through i18n; no ThemeToggle/LanguageSwitcher deps)
  2. BookDetailView: >Original<, compiled-success message, chapter placeholder
  3. ToolsView: Available Tools / Upload Manuscript / Or Choose from Library /
     Clear (line-based) + tolerant metadata line
  4. SettingsView: Entity Extractor (GLiNER) header (idempotent)
"""
import base64
import gzip
import os
import re
import shutil
import sys
import time

ROOT = os.getcwd()
APPLY_MODE = '--apply' in sys.argv


def sep(rel):
    return rel.replace('/', os.sep)


NAVBAR_B64 = 'H4sIAHKYqmoC/8VWTY/bNhC9+1cMfIh3AdHyOutFatjOYYuiBZqkSBzkUPRASbTEWiIFivJHDP33DiXbS8raXQct0ItsksPhzHtPT+RZLpWGz4yGGlZKZjBQ5v+gx5uVA3xgovTgg5TCgy8lPn6X8adSe/CYsI2S4jOPExz9KjPmwdeCKaiOmdIy5BEj7YS4X55jhn7JfTNjBZQF++3unXiKGfopD3yOc4NejwvN1IqGDD7STUDVH0rmBRx6AFIsZRyn7AueigtTuLmF+QI2kke4youfqVpPIZAyZVRY8cuEZawVjTVgAir2dZwpsNStkLBUigm9pMFHavYXWnER4wKesF5ynbL358mq12O7ur1QikIfS582wA9/eZxZvSxgDjcd/XjnJrx28d6xYs+q1rso0bNr83pV3Yw5qKnpABohn5/gv7nt4ZJiulQCbvAvwCxhNEKCw5QWhck47xeah+s9aJmTEXwnkxFsyapMUwhiEtBwHStZisj/aQJmFGF/JEhLRXYpFCxloSZCCoZlKUxMgtOfrNQs8sej/qI+GI+O+MY+d5WyHSTk7gG4ZllBQmZkAX+XWNBqTwKmt4wJyHfkHopsir8P51zPZHMSxTQnb60duCcotZbCmgHQ+xx3Nwt9Z0WKxxSRmR9aJFZOlFUCFykXjNSVpPE04VGE9Xc2dxzmZAw1uixqINdspxvkyEoq1kAPidyglJGOgiHPEVX741QdbgVqRUXBNZeChDKVqrA7Wjh1z4wp2NUnZILET/pG73LNvvFIJ/PD3XBSge+A6DdgLXr2ZO0IBf/O5ofxuwq2XCdLLG5+0KpklXNOAwsCZIDqm+R2ohatCZK/JfnOiLHGBZ72B6kM15DtEESZ05DrPYr3IqGgm47js2jarZhxw0GRdXPRb6FoPPOy3vtzQQ+jVwHFLLYPu9neDg0r5nnKeN+06OwvcirsfW1drKTAVljEywxCmnNNU6Sqvzi47lLNfJPJTX44+w28eXN0EevoRWvi33fzwx2hxERINYOM7siW/DkejfLdX9jdufLOxoyU3ZnbytE5KsfyGx+VaSnrOv8ZDyeOYg7G4i9xvDKZcctRY4iOazjO0G0hJ1FbuPUv4Kg//R1i7n4TLnm7YM3Rmml9aB7iOakdMXYI+e/su/7MXmXeL1l2TcHWPH6Ugm7LPns7Dc0JL1s49mvkjK56M0B1DvVTYwNHvK1XuLlzwHuY4fWvg+Fuj4IpfiXw0nj1huq1z8Rz8u8g9iVqHXKbq1LVCvi/mI0YAlOGmm/YE7XWpH83eY3iNskFjwXe1l2C2xQ3n2AMu5qs1pt3YqvTDZ0X0xrM/OY6aUa3eEP+BzI0Yn6MDAAA'

FIX = {}


def T(path, *pairs):
    FIX.setdefault(path, []).extend(pairs)


FIXRE = {}


def R(path, *pairs):
    FIXRE.setdefault(path, []).extend(pairs)


T('web/src/views/BookDetailView.tsx',
  (">Original<", ">{t('book.original')}<"))

bd = 'web/src/views/BookDetailView.tsx'
R(bd,
  (r"'[^']{0,40}[Cc]ompiled[^']{0,60}successfully!'", "t('book.compileOk')"),
  (r'placeholder="[^"]*[Cc]hapter[^"]*"', "placeholder={t('book.selectChapter')}"))

tv = 'web/src/views/ToolsView.tsx'
R(tv,
  (r'(?m)^\s*Available Tools:?\s*$', "{t('tools.availableTools')}"),
  (r'(?m)^\s*Upload Manuscript:?\s*$', "{t('tools.uploadManuscript')}"),
  (r'(?m)^\s*Or Choose from Library:?\s*$', "{t('tools.orChooseFromLibrary')}"),
  (r'(?m)^\s*Clear:?\s*$', "{t('common.clear')}"),
  (r'>[^<]*Authors[^<]*\{metaResult\.reading_time\}[^<]*<',
   ">{t('tools.metaLine', { authors: metaResult.authors?.join(', ') || t('common.na'), year: metaResult.year || t('common.na'), reading: metaResult.reading_time })}<"))

sv = 'web/src/views/SettingsView.tsx'
R(sv,
  (r'(?m)^\s*Entity Extractor \(GLiNER\)\s*$', "{t('settings.glinerSection')}"),
  (r'(?<=">)Entity Extractor \(GLiNER\)(?=</)', "{t('settings.glinerSection')}"))


def backup(path, rel, backup_dir):
    dst = os.path.join(backup_dir, sep(rel))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(path, dst)


def main():
    if not os.path.isdir(os.path.join(ROOT, 'web', 'src')):
        print('[ERR] web/src not found. Run from the repo root, e.g. E:\\SITE\\tran')
        sys.exit(1)

    stamp = time.strftime('%Y%m%d_%H%M%S')
    backup_dir = os.path.join(ROOT, '.tome_backup_fix2_' + stamp)
    print('== Tome i18n phase 8 FIX 2 ==  mode: %s' % ('APPLY' if APPLY_MODE else 'DRY-RUN'))
    print()

    wrote = False

    # ---- 1. Navbar.tsx corrected full replacement ----
    rel = 'web/src/components/Navbar.tsx'
    path = os.path.join(ROOT, sep(rel))
    if not os.path.exists(path):
        print('[MISS] %s not found' % rel)
    else:
        old = open(path, encoding='utf-8').read()
        new = gzip.decompress(base64.b64decode(NAVBAR_B64)).decode('utf-8')
        if old == new:
            print('[ OK ] %s already corrected' % rel)
        else:
            broken = "from './ThemeToggle'" in old
            print('[WRT ] %s -> corrected i18n version%s'
                  % (rel, ' (replaces phase-8 broken version)' if broken else ''))
            if APPLY_MODE:
                os.makedirs(backup_dir, exist_ok=True)
                wrote = True
                backup(path, rel, backup_dir)
                open(path, 'w', encoding='utf-8', newline='').write(new)

    # ---- 2. remaining string fixes ----
    paths = list(dict.fromkeys(list(FIX.keys()) + list(FIXRE.keys())))
    for rel in paths:
        path = os.path.join(ROOT, sep(rel))
        if not os.path.exists(path):
            print('[MISS] %s not found' % rel)
            continue
        text = open(path, encoding='utf-8').read()
        matched, missed = 0, []
        for old, new in FIX.get(rel, []):
            n = text.count(old)
            if n == 0:
                missed.append('exact: ' + old.strip()[:70])
            else:
                text = text.replace(old, new)
                matched += 1
        for pat, repl in FIXRE.get(rel, []):
            text, n = re.subn(pat, repl, text)
            if n == 0:
                missed.append('regex: ' + pat[:70])
            else:
                matched += 1
        status = 'OK ' if not missed else 'WARN'
        print('[%s] %s  (%d fixes%s)' % (status, rel, matched,
              ', %d missed' % len(missed) if missed else ''))
        for m in missed:
            print('        missed -> ' + m)
        if APPLY_MODE and (matched or missed):
            if matched:
                if not wrote:
                    os.makedirs(backup_dir, exist_ok=True)
                    wrote = True
                backup(path, rel, backup_dir)
                open(path, 'w', encoding='utf-8', newline='').write(text)

    print()
    if not APPLY_MODE:
        print('Dry-run only. Re-run with --apply to write changes.')
    print('Next step:  cd web && npm run build')


if __name__ == '__main__':
    main()