#!/usr/bin/env python3
"""
Tome Web Hotfix v2 — functional fixes (no security changes, no logic redesign).

Usage:
    python tome_web_fix2.py              # dry-run
    python tome_web_fix2.py --apply      # apply patches + write .bak backups
"""

import argparse
import re
import sys
from pathlib import Path


def find_file(explicit: str | None, rel: str) -> Path | None:
    if explicit:
        p = Path(explicit)
        return p if p.is_file() else None
    p = Path(rel)
    return p if p.is_file() else None


# ---------------------------------------------------------------------------
# B1 (required): uploading a different book whose filename maps to an existing
#    book_slug silently overwrote the previous book. Make the slug unique.
# ---------------------------------------------------------------------------
def patch_upload_collision(src: str) -> tuple[str, int]:
    old = (
        "    book_slug = clean_filename_title(raw_name)\n"
        "    book_dir = config.output_dir / book_slug\n"
        "    orig_dir = book_dir / \"original\"\n"
    )
    new = (
        "    book_slug = clean_filename_title(raw_name)\n"
        "    book_dir = config.output_dir / book_slug\n"
        "    if book_dir.exists():\n"
        "        n = 2\n"
        "        while (config.output_dir / f\"{book_slug}_{n}\").exists():\n"
        "            n += 1\n"
        "        book_slug = f\"{book_slug}_{n}\"\n"
        "        book_dir = config.output_dir / book_slug\n"
        "    orig_dir = book_dir / \"original\"\n"
    )
    return src.replace(old, new), src.count(old)


# ---------------------------------------------------------------------------
# B2 (optional): prompt changes were written to tome.json but never reloaded,
#    so they only took effect after a restart. Reload config like the config
#    endpoint already does.
# ---------------------------------------------------------------------------
def patch_prompts_reload(src: str) -> tuple[str, int]:
    old = (
        "    tome_json.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding=\"utf-8\")\n"
        "    return {\"status\": \"ok\"}\n"
        "\n"
        "\n"
        "@app.get(\"/api/config\")\n"
    )
    new = (
        "    tome_json.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding=\"utf-8\")\n"
        "    TomeConfig.load_config()\n"
        "    return {\"status\": \"ok\"}\n"
        "\n"
        "\n"
        "@app.get(\"/api/config\")\n"
    )
    return src.replace(old, new), src.count(old)


# ---------------------------------------------------------------------------
# B3 (required): active_tasks / task_event_queues grew forever in memory.
#    Purge finished tasks older than 24h whenever a new pipeline run starts.
# ---------------------------------------------------------------------------
def patch_task_cleanup(src: str) -> tuple[str, int]:
    old = "    task_id = f\"task_{int(time.time())}_{secrets.token_hex(4)}\"\n"
    new = (
        "    cutoff = time.time() - 86400\n"
        "    for _tid in [t for t, i in active_tasks.items() if i.get(\"status\") in (\"completed\", \"failed\") and i.get(\"created_at\", 0) < cutoff]:\n"
        "        active_tasks.pop(_tid, None)\n"
        "        task_event_queues.pop(_tid, None)\n"
        "    task_id = f\"task_{int(time.time())}_{secrets.token_hex(4)}\"\n"
    )
    return src.replace(old, new), src.count(old)


# ---------------------------------------------------------------------------
# B4 (optional): the uploads/ folder filled up forever. Delete stale files.
# ---------------------------------------------------------------------------
def patch_uploads_cleanup(src: str) -> tuple[str, int]:
    helper_anchor = "@app.post(\"/api/tools/extract-metadata\")"
    helper = (
        "def _cleanup_stale_uploads(max_age_seconds: int = 86400) -> None:\n"
        "    upload_dir = Path(\"uploads\")\n"
        "    if not upload_dir.exists():\n"
        "        return\n"
        "    cutoff = time.time() - max_age_seconds\n"
        "    for f in upload_dir.iterdir():\n"
        "        with contextlib.suppress(Exception):\n"
        "            if f.is_file() and f.stat().st_mtime < cutoff:\n"
        "                f.unlink()\n"
        "\n"
        "\n"
    )
    n_helper = 0
    if helper_anchor in src and "_cleanup_stale_uploads" not in src:
        src = src.replace(helper_anchor, helper + helper_anchor, 1)
        n_helper = 1
    call_old = "    config = TomeConfig.load_config()\n    target_path = None\n"
    call_new = "    config = TomeConfig.load_config()\n    _cleanup_stale_uploads()\n    target_path = None\n"
    n_calls = src.count(call_old)
    src = src.replace(call_old, call_new)
    return src, (1 if (n_helper and n_calls) else 0)


# ---------------------------------------------------------------------------
# B5 (required): no way to delete a book from the web UI at all.
#    Add DELETE /api/books/{title} (backend). Frontend button is B7.
# ---------------------------------------------------------------------------
def patch_delete_endpoint(src: str) -> tuple[str, int]:
    n1 = 0
    if "import shutil" not in src:
        old_imp = "import secrets\nimport tempfile\n"
        new_imp = "import secrets\nimport shutil\nimport tempfile\n"
        n1 = src.count(old_imp)
        src = src.replace(old_imp, new_imp)
    anchor = "@app.get(\"/api/books\")\nasync def api_list_books"
    endpoint = (
        "@app.delete(\"/api/books/{title}\")\n"
        "async def api_delete_book(title: str, user: User = Depends(get_current_user)) -> dict[str, str]:\n"
        "    config = TomeConfig.load_config()\n"
        "    clean_title = Path(title).name\n"
        "    book_dir = config.output_dir / clean_title\n"
        "    if not book_dir.exists() or not book_dir.is_dir():\n"
        "        raise HTTPException(status_code=404, detail=\"Book not found\")\n"
        "    shutil.rmtree(book_dir)\n"
        "    return {\"status\": \"ok\", \"deleted\": clean_title}\n"
        "\n"
        "\n"
    )
    n2 = 0
    if anchor in src and "api_delete_book" not in src:
        src = src.replace(anchor, endpoint + anchor, 1)
        n2 = 1
    return src, (1 if (n1 and n2) else 0)


# ---------------------------------------------------------------------------
# B6 (optional, frontend api.ts): client method for the new delete endpoint.
# ---------------------------------------------------------------------------
def patch_frontend_api(src: str) -> tuple[str, int]:
    old = "  static async getBook(title: string): Promise<BookDetail> {"
    new = (
        "  static async deleteBook(title: string): Promise<void> {\n"
        "    await this.request(`/api/books/${encodeURIComponent(title)}`, { method: 'DELETE' })\n"
        "  }\n"
        "\n"
        "  static async getBook(title: string): Promise<BookDetail> {"
    )
    return src.replace(old, new), src.count(old)


# ---------------------------------------------------------------------------
# B7 (optional, frontend BookshelfView): delete button on each book card.
# ---------------------------------------------------------------------------
def patch_frontend_bookshelf(src: str) -> tuple[str, int]:
    n = 0
    fn_old = "  const filtered = books.filter((b) => {"
    fn_new = (
        "  const handleDelete = async (folder: string, title: string) => {\n"
        "    if (!window.confirm(`Delete \"${title}\" permanently?`)) return\n"
        "    try {\n"
        "      await Api.deleteBook(folder)\n"
        "      setBooks((prev) => prev.filter((b) => b.folder !== folder))\n"
        "    } catch (err: any) {\n"
        "      alert(err.message || 'Failed to delete book')\n"
        "    }\n"
        "  }\n"
        "\n"
        "  const filtered = books.filter((b) => {"
    )
    if fn_old in src and "handleDelete" not in src:
        src = src.replace(fn_old, fn_new, 1)
        n += 1
    btn_old = (
        "                    <button\n"
        "                      onClick={(e) => {\n"
        "                        e.stopPropagation()\n"
        "                        onSelectBook(b.folder)\n"
        "                      }}"
    )
    btn_new = (
        "                    <button\n"
        "                      onClick={(e) => {\n"
        "                        e.stopPropagation()\n"
        "                        handleDelete(b.folder, b.title)\n"
        "                      }}\n"
        "                      className=\"px-2.5 py-1 rounded-full bg-rose-500/15 text-rose-600 dark:text-rose-400 hover:bg-rose-500/25 transition-colors font-medium text-[11px]\"\n"
        "                    >\n"
        "                      Delete\n"
        "                    </button>\n"
        "                    <button\n"
        "                      onClick={(e) => {\n"
        "                        e.stopPropagation()\n"
        "                        onSelectBook(b.folder)\n"
        "                      }}"
    )
    if btn_old in src:
        src = src.replace(btn_old, btn_new, 1)
        n += 1
    return src, (1 if n == 2 else 0)


# ---------------------------------------------------------------------------
# B8 (optional, frontend App.tsx): stop disabling right-click globally.
# ---------------------------------------------------------------------------
def patch_frontend_app(src: str) -> tuple[str, int]:
    block = (
        "    // 2. Disable right click completely\n"
        "    const handleContextMenu = (e: MouseEvent) => {\n"
        "      e.preventDefault()\n"
        "    }\n"
        "    window.addEventListener('contextmenu', handleContextMenu)\n"
        "\n"
    )
    n1 = src.count(block)
    src = src.replace(block, "")
    cleanup = "      window.removeEventListener('contextmenu', handleContextMenu)\n"
    n2 = src.count(cleanup)
    src = src.replace(cleanup, "")
    return src, (1 if (n1 and n2) else 0)


def run_patch(path: Path, apply: bool, steps) -> bool:
    src = path.read_text(encoding="utf-8")
    new = src
    results = []
    for name, fn, required in steps:
        new, n = fn(new)
        results.append((name, n, required))
    print("-" * 70)
    print(f"file: {path}")
    ok = True
    for name, n, required in results:
        if n >= 1:
            status = "OK"
        elif required:
            status, ok = "NOT FOUND (required)", False
        else:
            status = "not found (optional, skipped)"
        print(f"  [{status:>32}] {name}")
    if new == src:
        print("  nothing to change.")
        return True
    if apply and ok:
        backup = path.with_suffix(path.suffix + ".bak")
        backup.write_text(src, encoding="utf-8")
        path.write_text(new, encoding="utf-8")
        print(f"  patched. backup: {backup}")
    elif apply:
        print("  ABORTED for this file — required pattern(s) missing, file untouched.")
        return False
    else:
        print("  (dry-run — re-run with --apply to write)")
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--server", default=None)
    ap.add_argument("--webdir", default="web/src")
    args = ap.parse_args()

    server = find_file(args.server, "src/tome/web/server.py")
    if not server:
        sys.exit("server.py not found — run from the project root or pass --server")

    backend_steps = [
        ("B1: unique book slug on name collision", patch_upload_collision, True),
        ("B2: reload config after prompt update", patch_prompts_reload, False),
        ("B3: purge finished pipeline tasks (memory)", patch_task_cleanup, True),
        ("B4: clean stale uploads/ files", patch_uploads_cleanup, False),
        ("B5: DELETE /api/books/{title} endpoint", patch_delete_endpoint, True),
    ]
    ok = run_patch(server, args.apply, backend_steps)

    webdir = Path(args.webdir)
    frontend_jobs = [
        (webdir / "api.ts", [("B6: Api.deleteBook() client method", patch_frontend_api, False)]),
        (webdir / "views/BookshelfView.tsx", [("B7: delete button on book cards", patch_frontend_bookshelf, False)]),
        (webdir / "App.tsx", [("B8: stop disabling right-click", patch_frontend_app, False)]),
    ]
    for fpath, steps in frontend_jobs:
        if fpath.is_file():
            run_patch(fpath, args.apply, steps)
        else:
            print(f"- {70}")
            print(f"file: {fpath}  (not found, skipped)")

    if args.apply and ok:
        print("\nDone. Restart the web server for backend changes.")
        print("Frontend changes need a rebuild:  cd web && npm run build")
    elif not args.apply:
        print("\nDry-run only. Re-run with --apply to write changes.")


if __name__ == "__main__":
    main()








