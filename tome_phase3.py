#!/usr/bin/env python3
"""
Tome Phase 3 — retry/translate-remaining chapters.

Frontend (BookDetailView.tsx):
  F1: fix broken file_path in chapter translation (folder name -> real manuscript path)
  F2: refactor to runChapterTranslation() + "Translate Remaining (N)" button
  F3: per-chapter "Retry" button for pending chapters

Backend (server.py, optional):
  B1: emit pipeline_complete in the translate-only branch so the UI
      (and Phase-2 monitor) get a clean terminal event.

Usage:  python tome_phase3.py            (dry-run)
        python tome_phase3.py --apply
"""

import argparse
import re
import sys
from pathlib import Path


def patch_book_detail(src: str) -> tuple[str, int]:
    n = 0

    # F1+F2: replace the whole handler with a reusable runner + remaining/retry handlers
    pat = re.compile(
        r"  const handleTranslateSelected = async \(\) => \{\n.*?\n  \}\n\n(  const loadBook = async)",
        re.S,
    )
    replacement = (
        "  const runChapterTranslation = async (slugs: string[]) => {\n"
        "    if (slugs.length === 0 || !book) return\n"
        "    setTranslatingChapters(true)\n"
        "    setTransStatusMsg(`Initiating translation for ${slugs.length} chapter(s)...`)\n"
        "    try {\n"
        "      const res = await Api.runPipeline({\n"
        "        file_path: `output/${bookFolder}/original/book.md`,\n"
        "        translate: true,\n"
        "        chapters: slugs.join(','),\n"
        "      })\n"
        "      setTransStatusMsg('Translation task launched in background...')\n"
        "      const ev = new EventSource(`/api/pipeline/events/${res.task_id}`)\n"
        "      ev.onmessage = (e) => {\n"
        "        try {\n"
        "          const d = JSON.parse(e.data)\n"
        "          if (d.event === 'chapter_translation_complete') {\n"
        "            const ch = d.data?.chapter || d.data?.slug || ''\n"
        "            setTransStatusMsg(`Translated: ${ch}`)\n"
        "          } else if (d.event === 'pipeline_complete' || d.status === 'completed' || d.data?.status === 'completed') {\n"
        "            ev.close()\n"
        "            setTranslatingChapters(false)\n"
        "            setTransStatusMsg('Chapters translated!')\n"
        "            loadBook()\n"
        "            setTimeout(() => setTransStatusMsg(null), 4000)\n"
        "          } else if (d.event === 'pipeline_cancelled') {\n"
        "            ev.close()\n"
        "            setTranslatingChapters(false)\n"
        "            setTransStatusMsg('Translation cancelled.')\n"
        "            loadBook()\n"
        "          } else if (d.event === 'error' || d.status === 'failed') {\n"
        "            ev.close()\n"
        "            setTranslatingChapters(false)\n"
        "            setTransStatusMsg(`Translation error: ${d.data?.error || d.error || 'Failed'}`)\n"
        "            loadBook()\n"
        "          }\n"
        "        } catch {}\n"
        "      }\n"
        "      ev.onerror = () => {\n"
        "        ev.close()\n"
        "        setTranslatingChapters(false)\n"
        "        loadBook()\n"
        "      }\n"
        "    } catch (err: any) {\n"
        "      setTranslatingChapters(false)\n"
        "      setTransStatusMsg(`Error: ${err.message}`)\n"
        "    }\n"
        "  }\n"
        "\n"
        "  const handleTranslateSelected = () => {\n"
        "    runChapterTranslation(Array.from(checkedChapters))\n"
        "  }\n"
        "\n"
        "  const handleTranslateRemaining = () => {\n"
        "    if (!book) return\n"
        "    const pending = book.chapters.filter((c) => !c.is_translated).map((c) => c.slug)\n"
        "    runChapterTranslation(pending)\n"
        "  }\n"
        "\n"
        "  const handleRetryChapter = (slug: string) => {\n"
        "    runChapterTranslation([slug])\n"
        "  }\n"
        "\n"
        r"\1"
    )
    src, cnt = pat.subn(replacement, src, count=1)
    if cnt == 1:
        n += 1

    # F2 button: "Translate Remaining" after the Translate Selected button
    old = (
        "                  <span>Translate Selected ({checkedChapters.size})</span>\n"
        "                </Button>\n"
    )
    new = (
        "                  <span>Translate Selected ({checkedChapters.size})</span>\n"
        "                </Button>\n"
        "                <Button\n"
        "                  size=\"sm\"\n"
        "                  variant=\"secondary\"\n"
        "                  disabled={translatingChapters || book.chapters.filter((c) => !c.is_translated).length === 0}\n"
        "                  onClick={handleTranslateRemaining}\n"
        "                  loading={translatingChapters}\n"
        "                  className=\"h-9 text-xs font-medium px-4 rounded-full w-full sm:w-auto justify-center whitespace-nowrap\"\n"
        "                >\n"
        "                  <span>Translate Remaining ({book.chapters.filter((c) => !c.is_translated).length})</span>\n"
        "                </Button>\n"
    )
    if old in src and "handleTranslateRemaining" in src:
        src = src.replace(old, new, 1)
        n += 1

    # F3: per-chapter Retry button before the Read button
    old = (
        "                        <Button\n"
        "                          size=\"sm\"\n"
        "                          variant=\"secondary\"\n"
        "                          onClick={() => {\n"
        "                            setSelectedChapterSlug(ch.slug)\n"
        "                            setActiveTab('reader')\n"
        "                          }}\n"
        "                          className=\"h-8 text-xs px-3.5 rounded-full\"\n"
        "                        >\n"
        "                          Read\n"
        "                        </Button>\n"
    )
    new = (
        "                        {!ch.is_translated && (\n"
        "                          <Button\n"
        "                            size=\"sm\"\n"
        "                            variant=\"primary\"\n"
        "                            disabled={translatingChapters}\n"
        "                            onClick={() => handleRetryChapter(ch.slug)}\n"
        "                            className=\"h-8 text-xs px-3.5 rounded-full\"\n"
        "                          >\n"
        "                            Retry\n"
        "                          </Button>\n"
        "                        )}\n"
        + old
    )
    if old in src and "handleRetryChapter" in src:
        src = src.replace(old, new, 1)
        n += 1

    return src, (1 if n == 3 else 0)


def patch_server_emit(src: str) -> tuple[str, int]:
    pat = re.compile(
        r"(            if req\.chapters or \(req\.translate and has_existing_chapters\):\n"
        r"                translate_book\(book_dir, runner_cfg, chapters=req\.chapters, observer=_runner_observer\)\n)"
        r"(?!\s*_observer\(\"pipeline_complete\")"
    )
    new_block = (
        "            if req.chapters or (req.translate and has_existing_chapters):\n"
        "                translate_book(book_dir, runner_cfg, chapters=req.chapters, observer=_runner_observer)\n"
        "                _observer(\"pipeline_complete\", {\"book_folder\": book_dir.name, \"status\": \"completed\"})\n"
    )
    return pat.subn(lambda m: new_block, src, count=1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--webdir", default="web/src")
    ap.add_argument("--server", default="src/tome/web/server.py")
    args = ap.parse_args()

    print(f"mode: {'APPLY' if args.apply else 'DRY-RUN'}")

    view_path = Path(args.webdir) / "views" / "BookDetailView.tsx"
    server_path = Path(args.server)
    for p in (view_path, server_path):
        if not p.is_file():
            sys.exit(f"required file missing: {p}")

    src = view_path.read_text(encoding="utf-8")
    new, n = patch_book_detail(src)
    if n >= 1:
        status = "OK"
    elif "handleTranslateRemaining" in src:
        status = "already applied"
    else:
        status = "NOT FOUND"
    print(f"  [{status:>16}] BookDetailView.tsx: remaining/retry + path fix")
    if new != src and n >= 1:
        if args.apply:
            view_path.with_suffix(".tsx.bak").write_text(src, encoding="utf-8")
            view_path.write_text(new, encoding="utf-8")
            print("         patched (backup: BookDetailView.tsx.bak)")
        else:
            print("         (dry-run)")

    src = server_path.read_text(encoding="utf-8")
    new, n = patch_server_emit(src)
    if n >= 1:
        status = "OK"
    elif re.search(r"if req\.chapters or \(req\.translate and has_existing_chapters\):", src):
        status = "already applied"
    else:
        status = "optional pattern not found (skipped)"
    print(f"  [{status:>16}] server.py: pipeline_complete in translate-only branch")
    if new != src and n >= 1:
        if args.apply:
            server_path.with_suffix(server_path.suffix + ".bak").write_text(src, encoding="utf-8")
            server_path.write_text(new, encoding="utf-8")
            print("         patched (backup: server.py.bak)")
        else:
            print("         (dry-run)")

    if args.apply:
        print("\nDone. Rebuild the frontend:  cd web && npm run build")
    else:
        print("\nDry-run only. Re-run with --apply.")


if __name__ == "__main__":
    main()