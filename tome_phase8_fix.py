#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tome_phase8_fix.py - repair pass after tome_phase8.py
Run from the repo root:

    python tome_phase8_fix.py           # dry-run
    python tome_phase8_fix.py --apply   # apply (backs up to .tome_backup_*)

Fixes:
  1. i18n.tsx duplicate key book.translated  -> book.translatedMsg (+3 new alert keys)
  2. MetricsView broken </p> tag (<//p>) + missed donut labels + <th> headers
  3. SettingsView AVAILABLE_MODELS / GLINER_MODELS label -> labelKey (+generated dict keys)
  4. BookDetailView / ToolsView remaining English strings (fallback rules)
  5. final duplicate-key check + leftover scan
"""
import json
import os
import re
import shutil
import sys
import time

APPLY = '--apply' in sys.argv
ROOT = os.getcwd()


def sep(rel):
    return rel.replace('/', os.sep)


# ----------------------------- exact fixes ----------------------------------
FIX = {}

def T(path, *pairs):
    FIX.setdefault(path, []).extend(pairs)

# ---------------- i18n.tsx ----------------
T('web/src/lib/i18n.tsx',
  ("'book.translated': 'Translated: {ch}',", "'book.translatedMsg': 'Translated: {ch}',"),
  ("'book.translated': 'ترجمه شد: {ch}',", "'book.translatedMsg': 'ترجمه شد: {ch}',"),
  ("'tools.compileFail': 'Compilation failed',",
   "'tools.compileFail': 'Compilation failed',\n"
   "    'book.loadChapterFail': 'Failed to load chapter content',\n"
   "    'book.saveGlossaryFail': 'Failed to save glossary',\n"
   "    'book.compileFail': 'Failed to compile manuscript',"),
  ("'tools.compileFail': 'چیدمان ناموفق بود',",
   "'tools.compileFail': 'چیدمان ناموفق بود',\n"
   "    'book.loadChapterFail': 'بارگذاری محتوای فصل ناموفق بود',\n"
   "    'book.saveGlossaryFail': 'ذخیرهٔ واژه‌نامه ناموفق بود',\n"
   "    'book.compileFail': 'چیدمان کتاب ناموفق بود',"),
)

# ---------------- BookDetailView.tsx ----------------
T('web/src/views/BookDetailView.tsx',
  ("t('book.translated', { ch })", "t('book.translatedMsg', { ch })"),
  ("'Failed to load chapter content'", "t('book.loadChapterFail')"),
  ("'Failed to save glossary'", "t('book.saveGlossaryFail')"),
  ("'Failed to compile manuscript'", "t('book.compileFail')"),
)

# ---------------- MetricsView.tsx ----------------
T('web/src/views/MetricsView.tsx',
  ("{tx('metrics.noData')}<//p>", "{tx('metrics.noData')}</p>"),
  ("'Failed to save rate'", "tx('metrics.saveFail')"),
)

# ---------------- ToolsView.tsx ----------------
tv = 'web/src/views/ToolsView.tsx'
T(tv,
  (">Available Tools<", ">{t('tools.availableTools')}<"),
  (">Upload Manuscript<", ">{t('tools.uploadManuscript')}<"),
  (">Or Choose from Library<", ">{t('tools.orChooseFromLibrary')}<"),
  (">Clear<", ">{t('common.clear')}<"),
  (">Genre Detector<", ">{t('tools.toolGenre')}<"),
  (">Image Extractor<", ">{t('tools.toolImages')}<"),
  (">Metadata Refiner<", ">{t('tools.toolMetadata')}<"),
  (">Manuscript Converter<", ">{t('tools.toolConvert')}<"),
  (">Chapter Segmenter<", ">{t('tools.toolChapterize')}<"),
  (">Entity Extractor<", ">{t('tools.toolGliner')}<"),
  (">Character Graph<", ">{t('tools.toolGraph')}<"),
  (">Single Translator<", ">{t('tools.toolTranslate')}<"),
  (">NLP Copyeditor<", ">{t('tools.toolCopyedit')}<"),
  (">Word & PDF Compiler<", ">{t('tools.toolCompile')}<"),
  (">Compile Volume<", ">{t('tools.compileRun')}<"),
  (">Download DOCX<", ">{t('tools.downloadDocx')}<"),
  (">Download PDF<", ">{t('tools.downloadPdf')}<"),
)

# ---------------- regex fixes ------------------------------------------------
FIXRE = {}

def R(path, *pairs):
    FIXRE.setdefault(path, []).extend(pairs)

bd = 'web/src/views/BookDetailView.tsx'
R(bd, (r'(<CardTitle[^>]*>)\s*Original\s*(</CardTitle>)', r"\1{t('book.original')}\2"))
R(bd, (r'(<CardTitle[^>]*>)\s*Translation\s*(</CardTitle>)', r"\1{t('book.translation')}\2"))
R(bd, (r'>Preview<', ">{t('common.preview')}<"))
R(bd, (r'>Editor<', ">{t('common.editor')}<"))
R(bd, (r'>Raw Data<', ">{t('common.rawData')}<"))
R(bd, (r'>Download ZIP<', ">{t('book.downloadZip')}<"))
R(bd, (r'Page \{pNum\}', "{t('book.page', { n: pNum })}"))
R(bd, (r'(?m)^\s*Return to Library\s*$', "{t('book.returnToLibrary')}"))
R(bd, (r'(?m)^\s*Available Artifacts\s*$', "{t('book.availableArtifacts')}"))
R(bd, (r'(?m)^\s*Export Options\s*$', "{t('book.exportOptions')}"))
R(bd, (r"'Compiled[^']{0,60}successfully!'", "t('book.compileOk')"))
R(bd, (r'placeholder="[^"]*[Ss]elect[^"]*[Cc]hapter[^"]*"', "placeholder={t('book.selectChapter')}"))

mv = 'web/src/views/MetricsView.tsx'
R(mv, (r"(label: )'Prompt'(, value: t\.prompt_tokens)", r"\1tx('metrics.prompt')\2"))
R(mv, (r"(label: )'Completion'(, value: t\.completion_tokens)", r"\1tx('metrics.completion')\2"))
R(mv, (r"(label: )'Reasoning'(, value: t\.reasoning_tokens)", r"\1tx('metrics.reasoning')\2"))
R(mv, (r"(?m)^(\s*)'Prompt',(\s*value:)", r"\1tx('metrics.prompt'),\2"))
R(mv, (r"(?m)^(\s*)'Completion',(\s*value:)", r"\1tx('metrics.completion'),\2"))
R(mv, (r"(?m)^(\s*)'Reasoning',(\s*value:)", r"\1tx('metrics.reasoning'),\2"))
R(mv, (r'>Chapters</th>', ">{tx('metrics.colChapters')}</th>"))
R(mv, (r'>Tokens</th>', ">{tx('metrics.colTokens')}</th>"))
R(mv, (r'>Share</th>', ">{tx('metrics.colShare')}</th>"))
R(mv, (r'>Cost \(Toman\)</th>', ">{tx('metrics.colCost')}</th>"))
R(mv, (r'>At Current Rate</th>', ">{tx('metrics.colCurrentRate')}</th>"))
R(mv, (r'>Updated</th>', ">{tx('metrics.colUpdated')}</th>"))

sv = 'web/src/views/SettingsView.tsx'
R(sv, (r'(?m)^\s*Entity Extractor \(GLiNER\)\s*$', "{t('settings.glinerSection')}"))
R(sv, (r'(?<=">)Entity Extractor \(GLiNER\)(?=</)', "{t('settings.glinerSection')}"))

R(tv, (r">Authors: \{metaResult\.authors\?\.join\(', '\) \|\| [^}]*\} • Year: \{metaResult\.year \|\| [^}]*\}[^<{]*\{metaResult\.reading_time[^}]*\}<",
  ">{t('tools.metaLine', { authors: metaResult.authors?.join(', ') || t('common.na'), year: metaResult.year || t('common.na'), reading: metaResult.reading_time })}<"))

# ---------------- SettingsView model arrays -> labelKey ---------------------
MODEL_FA_MAP = [
    ('Custom Model (Specify identifier)', 'مدل سفارشی (شناسه را وارد کنید)'),
    ('Custom Model (Specify name)', 'مدل سفارشی (نام را وارد کنید)'),
    ('Large - High Accuracy', 'بزرگ - دقت بالا'),
    ('Medium - Default', 'متوسط - پیش‌فرض'),
    ('Small - Fast', 'کوچک - سریع'),
    ('Multilingual', 'چندزبانه'),
    ('[Default]', '[پیش‌فرض]'),
    ('Google', 'گوگل'),
    ('DeepSeek', 'دیپ‌سیک'),
    ('Anthropic', 'انترپیک'),
    ('OpenAI', 'اوپن‌ای‌دی'),
    ('Alibaba', 'علی‌بابا'),
    ('Zhipu', 'زیپو'),
]


def fa_model(value):
    s = value
    for a, b in MODEL_FA_MAP:
        s = s.replace(a, b)
    return s


def transform_model_arrays(text):
    generated = []

    def block_repl(m):
        body = m.group(2)

        def label_repl(lm):
            val = lm.group(1)
            key = 'settings.mdl.' + re.sub(r'[^A-Za-z0-9]+', '_', val).strip('_')[:48]
            if key not in [k for k, _ in generated]:
                generated.append((key, val))
            return "labelKey: '%s'," % key

        return m.group(1) + re.sub(r"label: '([^']*)'", label_repl, body) + m.group(3)

    new_text = re.sub(r'(const (?:AVAILABLE_MODELS|GLINER_MODELS) = \[)(\n.*?)(\n\])',
                      block_repl, text, flags=re.S)
    return new_text, generated


# ---------------- BookDetailView 'No ...' literal sweep ----------------------
def no_literal_sweep(text):
    def rep(m):
        s = m.group(1)
        low = s.lower()
        if 'glossary' in low:
            return "t('book.noGlossary')"
        if 'graph' in low or 'character' in low:
            return "t('book.noGraph')"
        if 'illustration' in low or 'image' in low:
            return "t('book.noImages')"
        if 'synopsis' in low:
            return "t('book.noSynopsis')"
        return m.group(0)

    return re.sub(r"'(No [^']{8,140})'", rep, text)


# ---------------- engine -----------------------------------------------------
def backup(path, rel, backup_dir):
    dst = os.path.join(backup_dir, sep(rel))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(path, dst)


def patch(rel, text):
    """Apply exact + regex fixes to one file's text. Returns (text, matched, missed)."""
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
    # global safety: repair any double-closing tags produced by earlier regexes
    if '<//' in text:
        text = text.replace('<//', '</')
        matched += 1
    return text, matched, missed


def main():
    if not os.path.isdir(os.path.join(ROOT, 'web', 'src')):
        print('[ERR] web/src not found. Run from the repo root, e.g. E:\\SITE\\tran')
        sys.exit(1)

    APPLY_MODE = '--apply' in sys.argv
    stamp = time.strftime('%Y%m%d_%H%M%S')
    backup_dir = os.path.join(ROOT, '.tome_backup_fix_' + stamp)
    print('== Tome i18n phase 8 FIX ==  mode: %s' % ('APPLY' if APPLY_MODE else 'DRY-RUN'))
    print()

    results = {}

    # ---- pass 1: SettingsView model arrays (generates dict keys) ----
    rel = sv
    path = os.path.join(ROOT, sep(rel))
    if os.path.exists(path):
        text = open(path, encoding='utf-8').read()
        new_text, generated = transform_model_arrays(text)
        changed = new_text != text
        print('[GEN ] %s: %d model labels -> labelKey' % (rel, len(generated)))
        results[rel] = new_text
        for key, val in generated:
            print('        + %s = %r' % (key, val))
    else:
        generated = []
        print('[MISS] %s not found' % rel)

    # ---- pass 2: all other files ----
    paths = list(dict.fromkeys(
        [p for p in list(FIX.keys()) + list(FIXRE.keys()) if p != sv]))
    for rel in paths:
        path = os.path.join(ROOT, sep(rel))
        if not os.path.exists(path):
            print('[MISS] %s not found' % rel)
            continue
        text = open(path, encoding='utf-8').read()
        text, matched, missed = patch(rel, text)
        if rel == bd:
            swept = no_literal_sweep(text)
            if swept != text:
                text = swept
                matched += 1
        results[rel] = text
        status = 'OK ' if not missed else 'WARN'
        print('[%s] %s  (%d fixes%s)' % (status, rel, matched,
              ', %d missed' % len(missed) if missed else ''))
        for mline in missed:
            print('        missed -> ' + mline)

    # ---- pass 3: insert generated model keys into i18n.tsx ----
    if generated:
        rel = 'web/src/lib/i18n.tsx'
        text = results.get(rel)
        if text is None:
            path = os.path.join(ROOT, sep(rel))
            text = open(path, encoding='utf-8').read()
        en_add = ''
        fa_add = ''
        for key, val in generated:
            if "'%s':" % key in text:
                continue
            en_add += "\n    '%s': %s," % (key, json.dumps(val, ensure_ascii=False))
            fa_add += "\n    '%s': %s," % (key, json.dumps(fa_model(val), ensure_ascii=False))
        if en_add:
            anchor_en = "'book.compileFail': 'Failed to compile manuscript',"
            anchor_fa = "'book.compileFail': 'چیدمان کتاب ناموفق بود',"
            if anchor_en in text:
                text = text.replace(anchor_en, anchor_en + en_add, 1)
            if anchor_fa in text:
                text = text.replace(anchor_fa, anchor_fa + fa_add, 1)
            results[rel] = text
            print('[GEN ] i18n.tsx: %d model keys inserted (en+fa)' % len(generated))

    # ---- duplicate key check on i18n.tsx ----
    rel = 'web/src/lib/i18n.tsx'
    if rel in results:
        text = results[rel]
        dstart = text.index('const DICT')
        ok = True
        for sec_name in ('en: {', 'fa: {'):
            sec = text[text.index(sec_name, dstart):]
            sec = sec[:sec.index('\n  },\n')]
            keys = re.findall(r"'([\w.]+)':", sec)
            dup = sorted({k for k in keys if keys.count(k) > 1})
            if dup:
                ok = False
                print('[ERR ] duplicate keys in %s dict: %s' % (sec_name, dup))
        if ok:
            print('[ OK ] i18n.tsx: no duplicate keys')

    # ---- write ----
    if APPLY_MODE:
        wrote = False
        for rel, text in results.items():
            path = os.path.join(ROOT, sep(rel))
            if not os.path.exists(path):
                continue
            old = open(path, encoding='utf-8').read()
            if old != text:
                if not wrote:
                    os.makedirs(backup_dir, exist_ok=True)
                    wrote = True
                backup(path, rel, backup_dir)
                open(path, 'w', encoding='utf-8', newline='').write(text)
                print('[WRT ] %s' % rel)
        if not wrote:
            print('(no changes needed)')
    else:
        print()
        print('Dry-run only. Re-run with --apply to write changes.')

    print()
    print('Next step:  cd web && npm run build')


if __name__ == '__main__':
    main()