
#!/usr/bin/env python3
# Tome Phase 8 — Glossary Editor + quality-score badge fix.
#
# BookDetailView.tsx:
#   - New "Editor" mode in the Glossary tab: searchable table with inline editing,
#     add row, delete row, and one-click merge of duplicate canonical terms.
#   - "Raw Data" mode becomes a real editable textarea (the orphaned save handler
#     is finally wired to a Save button).
#   - Bonus: adds the phase-7c quality score badge next to chapter status pills
#     (the 7c badge anchor missed because the status pill is a plain div).
#
# Usage:  python tome_phase8.py            (dry-run)
#         python tome_phase8.py --apply   (+ rebuild frontend)
import argparse, sys
from pathlib import Path

STATE_OLD = "  const [glossaryDraft, setGlossaryDraft] = useState('')\n  const [glossaryMode, setGlossaryMode] = useState<'preview' | 'edit'>('preview')\n"
STATE_NEW = "  const [glossaryDraft, setGlossaryDraft] = useState('')\n  const [glossaryMode, setGlossaryMode] = useState<'preview' | 'editor' | 'edit'>('preview')\n  const [glossaryRows, setGlossaryRows] = useState<Array<{ canonical: string; aliases: string; translation: string; confidence: string }>>([])\n  const [glossarySearch, setGlossarySearch] = useState('')\n"
HELPERS_JS = "  const parseGlossaryRows = (text: string) => {\n    const rows: Array<{ canonical: string; aliases: string; translation: string; confidence: string }> = []\n    for (const line of text.split('\\n')) {\n      if (!line.startsWith('|') || /^[|\\s:-]+$/.test(line)) continue\n      const cols = line.split('|').slice(1, -1).map((c) => c.trim())\n      if (cols.length < 3 || !cols[0] || /canonical/i.test(cols[0])) continue\n      rows.push({ canonical: cols[0], aliases: cols[1] || '', translation: cols[2] || '', confidence: cols[3] || '' })\n    }\n    return rows\n  }\n\n  const serializeGlossaryRows = (rows: Array<{ canonical: string; aliases: string; translation: string; confidence: string }>) => {\n    const lines = glossaryDraft.split('\\n')\n    const headerIdx = lines.findIndex((l) => l.startsWith('|') && /canonical/i.test(l))\n    const header = headerIdx >= 0 ? lines[headerIdx] : '| Canonical Term | Aliases | Term Translation | Confidence |'\n    const sep = headerIdx >= 0 && (lines[headerIdx + 1] || '').startsWith('|') ? lines[headerIdx + 1] : '| --- | --- | --- | --- |'\n    const prefix = headerIdx >= 0 ? lines.slice(0, headerIdx) : []\n    const body = rows\n      .filter((r) => r.canonical.trim())\n      .map((r) => `| ${r.canonical.trim()} | ${r.aliases} | ${r.translation} | ${r.confidence} |`)\n    return [...prefix, header, sep, ...body].join('\\n')\n  }\n\n  const mergeDuplicateRows = () => {\n    const seen = new Map<string, { canonical: string; aliases: string; translation: string; confidence: string }>()\n    for (const r of glossaryRows) {\n      const key = r.canonical.trim().toLowerCase()\n      if (!key) continue\n      const existing = seen.get(key)\n      if (!existing) {\n        seen.set(key, { ...r })\n        continue\n      }\n      const aliasSet = new Set([...existing.aliases.split(','), ...r.aliases.split(',')].map((a) => a.trim()).filter(Boolean))\n      seen.set(key, {\n        canonical: existing.canonical,\n        aliases: Array.from(aliasSet).join(', '),\n        translation: existing.translation || r.translation,\n        confidence: existing.confidence || r.confidence,\n      })\n    }\n    setGlossaryRows(Array.from(seen.values()))\n  }\n\n  const handleEditorSave = async () => {\n    const md = serializeGlossaryRows(glossaryRows)\n    setGlossaryDraft(md)\n    setSavingGlossary(true)\n    try {\n      await Api.saveGlossary(bookFolder, md)\n      setGlossarySaved(true)\n      setTimeout(() => setGlossarySaved(false), 2000)\n    } catch (err: any) {\n      alert(err.message || 'Failed to save glossary')\n    } finally {\n      setSavingGlossary(false)\n    }\n  }\n\n"
TOGGLE_OLD = '            <div className="w-full sm:w-auto grid grid-cols-2 sm:flex items-center p-1 rounded-full bg-secondary text-xs font-medium shrink-0">\n              <button\n                type="button"\n                onClick={() => setGlossaryMode(\'preview\')}\n'
TOGGLE_NEW = '            <div className="w-full sm:w-auto grid grid-cols-3 sm:flex items-center p-1 rounded-full bg-secondary text-xs font-medium shrink-0">\n              <button\n                type="button"\n                onClick={() => { setGlossaryMode(\'preview\') }}\n'
EDITOR_BUTTON_OLD = '              <button\n                type="button"\n                onClick={() => setGlossaryMode(\'edit\')}\n                className={`flex items-center justify-center gap-1.5 h-8 px-4 rounded-full transition-all duration-200 border-0 cursor-pointer ${\n                  glossaryMode === \'edit\'\n                    ? \'bg-foreground text-background shadow-xs font-medium\'\n                    : \'text-muted-foreground hover:text-foreground\'\n                }`}\n              >\n                <Code className="h-3.5 w-3.5" />\n                <span>Raw Data</span>\n              </button>\n'
EDITOR_BUTTON_NEW = '              <button\n                type="button"\n                onClick={() => { setGlossaryMode(\'editor\'); setGlossaryRows(parseGlossaryRows(glossaryDraft)) }}\n                className={`flex items-center justify-center gap-1.5 h-8 px-4 rounded-full transition-all duration-200 border-0 cursor-pointer ${\n                  glossaryMode === \'editor\'\n                    ? \'bg-foreground text-background shadow-xs font-medium\'\n                    : \'text-muted-foreground hover:text-foreground\'\n                }`}\n              >\n                <Edit3 className="h-3.5 w-3.5" />\n                <span>Editor</span>\n              </button>\n              <button\n                type="button"\n                onClick={() => setGlossaryMode(\'edit\')}\n                className={`flex items-center justify-center gap-1.5 h-8 px-4 rounded-full transition-all duration-200 border-0 cursor-pointer ${\n                  glossaryMode === \'edit\'\n                    ? \'bg-foreground text-background shadow-xs font-medium\'\n                    : \'text-muted-foreground hover:text-foreground\'\n                }`}\n              >\n                <Code className="h-3.5 w-3.5" />\n                <span>Raw Data</span>\n              </button>\n'
RAW_OLD = '            ) : (\n              <div className="rounded-3xl bg-secondary/30 p-4 overflow-hidden">\n                <pre className="font-mono text-xs max-h-[500px] overflow-y-auto custom-scrollbar select-text text-foreground leading-relaxed">\n                  {glossaryDraft}\n                </pre>\n              </div>\n            )}\n'
RAW_NEW = '            ) : glossaryMode === \'editor\' ? (\n              <div className="space-y-3">\n                <div className="flex flex-wrap items-center gap-2">\n                  <Input\n                    placeholder="Search terms..."\n                    value={glossarySearch}\n                    onChange={(e) => setGlossarySearch(e.target.value)}\n                    className="h-9 w-64 text-xs"\n                  />\n                  <Button size="sm" variant="secondary" onClick={() => setGlossaryRows((prev) => [...prev, { canonical: \'\', aliases: \'\', translation: \'\', confidence: \'\' }])}>\n                    + Add Row\n                  </Button>\n                  <Button size="sm" variant="secondary" onClick={mergeDuplicateRows}>\n                    Merge Duplicates\n                  </Button>\n                  <span className="text-[11px] text-muted-foreground ms-auto tabular-nums">{glossaryRows.length} rows</span>\n                </div>\n                <div className="rounded-2xl overflow-hidden bg-secondary/30 max-h-[520px] overflow-y-auto custom-scrollbar">\n                  <table className="w-full text-xs">\n                    <thead className="bg-secondary sticky top-0">\n                      <tr className="text-left text-muted-foreground">\n                        <th className="p-2.5 font-medium">Canonical Term</th>\n                        <th className="p-2.5 font-medium">Aliases</th>\n                        <th className="p-2.5 font-medium">Term Translation</th>\n                        <th className="p-2.5 font-medium w-24">Confidence</th>\n                        <th className="p-2.5 w-10" />\n                      </tr>\n                    </thead>\n                    <tbody className="divide-y divide-secondary/40">\n                      {glossaryRows.map((r, i) => {\n                        if (glossarySearch && !`${r.canonical} ${r.aliases} ${r.translation}`.toLowerCase().includes(glossarySearch.toLowerCase())) return null\n                        return (\n                          <tr key={i} className="hover:bg-secondary/40">\n                            {([\'canonical\', \'aliases\', \'translation\', \'confidence\'] as const).map((field) => (\n                              <td key={field} className="p-1.5">\n                                <input\n                                  value={r[field]}\n                                  onChange={(e) => {\n                                    const val = e.target.value\n                                    setGlossaryRows((prev) => prev.map((row, j) => (j === i ? { ...row, [field]: val } : row)))\n                                  }}\n                                  className="w-full h-8 px-2 rounded-lg bg-background/60 border-0 text-xs outline-none focus:ring-1 ring-primary/40"\n                                />\n                              </td>\n                            ))}\n                            <td className="p-1.5 text-center">\n                              <button\n                                type="button"\n                                onClick={() => setGlossaryRows((prev) => prev.filter((_, j) => j !== i))}\n                                className="h-7 w-7 rounded-full bg-destructive/10 text-destructive hover:bg-destructive/20 border-0 cursor-pointer inline-flex items-center justify-center"\n                                title="Delete row"\n                              >\n                                <X className="h-3.5 w-3.5" />\n                              </button>\n                            </td>\n                          </tr>\n                        )\n                      })}\n                    </tbody>\n                  </table>\n                </div>\n                <div className="flex items-center gap-2">\n                  <Button size="sm" onClick={handleEditorSave} loading={savingGlossary}>\n                    {glossarySaved ? \'Saved!\' : \'Save Glossary\'}\n                  </Button>\n                  <span className="text-[11px] text-muted-foreground">Edits apply to the pipeline glossary used in translation.</span>\n                </div>\n              </div>\n            ) : (\n              <div className="rounded-3xl bg-secondary/30 p-4 overflow-hidden space-y-3">\n                <Textarea\n                  value={glossaryDraft}\n                  onChange={(e) => setGlossaryDraft(e.target.value)}\n                  className="font-mono text-xs min-h-[400px] bg-background/60"\n                />\n                <div className="flex items-center gap-2">\n                  <Button size="sm" onClick={handleSaveGlossary} loading={savingGlossary}>\n                    {glossarySaved ? \'Saved!\' : \'Save Raw Glossary\'}\n                  </Button>\n                </div>\n              </div>\n            )}\n'
PILL_OLD = "                        <div\n                          className={`h-8 px-3 rounded-full flex items-center justify-center text-xs font-medium ${\n                            ch.is_translated\n                              ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'\n                              : 'bg-secondary text-muted-foreground'\n                          }`}\n                        >\n                          {ch.is_translated ? 'Translated' : 'Pending'}\n                        </div>\n"
PILL_NEW = "                        <div\n                          className={`h-8 px-3 rounded-full flex items-center justify-center text-xs font-medium ${\n                            ch.is_translated\n                              ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'\n                              : 'bg-secondary text-muted-foreground'\n                          }`}\n                        >\n                          {ch.is_translated ? 'Translated' : 'Pending'}\n                        </div>\n                        {ch.is_translated && (quality[ch.slug] || quality[`${ch.slug}.md`]) && (\n                          (() => {\n                            const q = quality[ch.slug] || quality[`${ch.slug}.md`]\n                            return (\n                              <span\n                                title={q.reason || `Quality: ${q.score}/10`}\n                                className={`h-8 px-2.5 rounded-full flex items-center justify-center text-[11px] font-semibold ${\n                                  q.score >= 8\n                                    ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'\n                                    : q.score >= 6\n                                      ? 'bg-amber-500/15 text-amber-600 dark:text-amber-400'\n                                      : 'bg-rose-500/15 text-rose-600 dark:text-rose-400'\n                                }`}\n                              >\n                                {q.score}/10\n                              </span>\n                            )\n                          })()\n                        )}\n"


def patch_view(src: str) -> tuple[str, int]:
    n = 0

    if STATE_OLD in src and "glossaryRows" not in src:
        src = src.replace(STATE_OLD, STATE_NEW, 1)
        n += 1

    if "parseGlossaryRows" not in src:
        anchor = "  const handleSaveGlossary = async () => {\n"
        if anchor in src:
            src = src.replace(anchor, HELPERS_JS + anchor, 1)
            n += 1

    if TOGGLE_OLD in src and "grid grid-cols-3 sm:flex" not in src:
        src = src.replace(TOGGLE_OLD, TOGGLE_NEW, 1)
        n += 1

    if EDITOR_BUTTON_OLD in src and "setGlossaryMode('editor')" not in src:
        src = src.replace(EDITOR_BUTTON_OLD, EDITOR_BUTTON_NEW, 1)
        n += 1

    if RAW_OLD in src and "Save Raw Glossary" not in src:
        src = src.replace(RAW_OLD, RAW_NEW, 1)
        n += 1

    # bonus: quality badge (7c used a Badge anchor that never matched)
    if PILL_OLD in src and "q.score}/10" not in src:
        src = src.replace(PILL_OLD, PILL_NEW, 1)
        n += 1

    return src, n


def patch_quality_state(src: str) -> tuple[str, int]:
    n = 0
    old = "  const [translatingChapters, setTranslatingChapters] = useState(false)\n"
    new = (
        old
        + "  const [quality, setQuality] = useState<Record<string, { score: number; reason: string }>>({})\n"
        + "\n"
        + "  useEffect(() => {\n"
        + "    Api.getBookQuality(bookFolder)\n"
        + "      .then(setQuality)\n"
        + "      .catch(() => {})\n"
        + "  }, [bookFolder])\n"
    )
    if old in src and "getBookQuality" not in src:
        src = src.replace(old, new, 1)
        n += 1
    old2 = "            setTransStatusMsg('Chapters translated!')\n            loadBook()\n"
    new2 = old2 + "            Api.getBookQuality(bookFolder).then(setQuality).catch(() => {})\n"
    if old2 in src and "getBookQuality(bookFolder).then" not in src:
        src = src.replace(old2, new2, 1)
        n += 1
    return src, n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--webdir", default="web/src")
    args = ap.parse_args()
    p = Path(args.webdir) / "views" / "BookDetailView.tsx"
    if not p.is_file():
        sys.exit(f"not found: {p}")
    raw = p.read_bytes()
    src = raw.decode("utf-8")
    norm = src.replace("\r\n", "\n")

    norm, n1 = patch_quality_state(norm)
    norm, n2 = patch_view(norm)
    n = n1 + n2

    if "parseGlossaryRows" in norm:
        status = "OK" if n2 >= 5 else "PARTIAL"
    else:
        status = "NOT FOUND"
    print(f"[{status}] BookDetailView.tsx: glossary editor ({n2} patches) + quality badge ({n1} state patches)")

    if n == 0:
        print("already applied" if "parseGlossaryRows" in norm else "nothing matched")
        return
    if not args.apply:
        print("(dry-run — re-run with --apply)")
        return
    out = norm.replace("\n", "\r\n") if b"\r\n" in raw else norm
    p.with_suffix(".tsx.bak").write_bytes(raw)
    p.write_bytes(out.encode("utf-8"))
    print("patched (backup: BookDetailView.tsx.bak)")
    print("now run: cd web && npm run build")


if __name__ == "__main__":
    main()