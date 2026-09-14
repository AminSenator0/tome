#!/usr/bin/env python3
"""
Tome Web Hotfix — fixes the IsADirectoryError flood on GET /api/books/<name>
and the upload/convert path bugs in src/tome/web/server.py.

Usage:
    python tome_web_fix.py                 # dry-run: show planned changes only
    python tome_web_fix.py --apply         # patch server.py + repair legacy data
    python tome_web_fix.py --apply --server /opt/tome/src/tome/web/server.py --output /opt/tome/output
"""

import argparse
import re
import shutil
import sys
from pathlib import Path


def find_server(explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit)
        if not p.is_file():
            sys.exit(f"server.py not found at: {p}")
        return p
    for cand in [Path("src/tome/web/server.py"), Path("server.py")]:
        if cand.is_file():
            return cand
    sys.exit("Could not locate src/tome/web/server.py — pass --server /path/to/server.py")


# ---------------------------------------------------------------------------
# Patch 1: api_upload passed a FILE path (orig_dir/"book.md") as the converter's
#          output DIRECTORY. converter.py does output_dir.mkdir() + output_dir/"book.md",
#          so every uploaded PDF/EPUB/MOBI got:  original/book.md/  (a directory!)
#          with the real markdown hidden inside at original/book.md/book.md.
#          => IsADirectoryError on read_text() -> the 500 flood in your logs.
# ---------------------------------------------------------------------------
def patch_upload(src: str) -> tuple[str, int]:
    new, n = re.subn(
        r"convert_pdf_to_markdown\((target_orig|pdf_path), book_md\)",
        r"convert_pdf_to_markdown(\1, orig_dir)",
        src,
    )
    return new, n


# ---------------------------------------------------------------------------
# Patch 2: api_extract_metadata passed tmp_p/"conv.pdf" (a file path) as the
#          converter output dir -> same class of bug in a temp folder.
# ---------------------------------------------------------------------------
def patch_extract_metadata(src: str) -> tuple[str, int]:
    old = 'convert_pdf_to_markdown(active_pdf, tmp_p / "conv.pdf")'
    new = "convert_pdf_to_markdown(active_pdf, tmp_p)"
    n = src.count(old)
    return src.replace(old, new), n


# ---------------------------------------------------------------------------
# Patch 3: api_get_book checked target_candidate.exists() — True for the
#          poisoned directory — then read_text() crashed. Require is_file(),
#          and auto-recover the legacy nested layout (book.md/book.md).
# ---------------------------------------------------------------------------
def patch_get_book(src: str) -> tuple[str, int]:
    pat = re.compile(
        r"(?P<ind>[ ]+)if target_candidate\.exists\(\):\n"
        r'(?P=ind)    book_md_content = target_candidate\.read_text\(encoding="utf-8", errors="ignore"\)'
    )

    def repl(m: re.Match) -> str:
        i = m.group("ind")
        return (
            f"{i}if target_candidate.is_file():\n"
            f'{i}    book_md_content = target_candidate.read_text(encoding="utf-8", errors="ignore")\n'
            f"{i}elif target_candidate.is_dir():\n"
            f'{i}    # Legacy repair: books uploaded by the buggy uploader have a DIRECTORY\n'
            f'{i}    # named "book.md" with the real markdown nested inside it.\n'
            f"{i}    nested = target_candidate / candidate_name\n"
            f"{i}    nested_files = [nested] if nested.is_file() else sorted(target_candidate.glob('*.md'))\n"
            f"{i}    if nested_files:\n"
            f'{i}        book_md_content = nested_files[0].read_text(encoding="utf-8", errors="ignore")'
        )

    return pat.subn(repl, src)


# ---------------------------------------------------------------------------
# Patch 4: frontend sends file_path values like "output/<slug>/original/book.md"
#          (already containing the output/ prefix). The endpoint then built
#          Path(f"output/{file_path}") -> "output/output/..." which never exists,
#          so pipeline runs on freshly uploaded/existing books failed with
#          "Could not resolve manuscript path" unless state got reset.
#          Make the resolution prefix-tolerant.
# ---------------------------------------------------------------------------
def patch_path_resolution(src: str) -> tuple[str, int]:
    pat = re.compile(r'([ ]+)p = Path\(f"output/\{req\.file_path\}"\)\.resolve\(\)')

    def repl(m: re.Match) -> str:
        i = m.group(1)
        return (
            f'{i}_fp = req.file_path.replace("\\\\", "/")\n'
            f'{i}if _fp.startswith("./"):\n'
            f"{i}    _fp = _fp[2:]\n"
            f'{i}p = Path(_fp if (Path(_fp).is_absolute() or _fp.startswith("output/")) else f"output/{{_fp}}").resolve()'
        )

    return pat.subn(repl, src)


# ---------------------------------------------------------------------------
# Data repair: fix already-poisoned books on disk.
#   output/<Book>/original/book.md/   (dir)  ->  output/<Book>/original/book.md (file)
# ---------------------------------------------------------------------------
def repair_output(output_root: Path, apply: bool) -> list[str]:
    log: list[str] = []
    if not output_root.is_dir():
        log.append(f"output dir not found, skipped: {output_root}")
        return log
    for book_md in sorted(output_root.glob("*/original/book.md")) + sorted(output_root.glob("*/original/full_book.md")):
        if not book_md.is_dir():
            continue
        inner = book_md / book_md.name
        if not inner.is_file():
            md_files = sorted(book_md.glob("*.md"))
            inner = md_files[0] if md_files else None
        if inner is None:
            log.append(f"!! no markdown inside {book_md} — manual check needed")
            continue
        if apply:
            tmp = book_md.with_name(book_md.name + ".tmpfix")
            shutil.move(str(inner), str(tmp))
            shutil.rmtree(book_md)
            shutil.move(str(tmp), str(book_md))
        log.append(f"{'FIXED' if apply else 'WOULD FIX'}: {book_md}  <- nested {inner.name}")
    if not log:
        log.append("no poisoned book.md directories found — data is clean")
    return log


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually write changes (default: dry-run)")
    ap.add_argument("--server", default=None, help="path to src/tome/web/server.py")
    ap.add_argument("--output", default="output", help="path to the books output dir")
    args = ap.parse_args()

    server = find_server(args.server)
    src = server.read_text(encoding="utf-8")

    steps = [
        ("upload converter arg (api_upload)", patch_upload, 3, True),
        ("extract_metadata converter arg", patch_extract_metadata, 1, False),
        ("api_get_book candidate check + legacy recovery", patch_get_book, 1, True),
        ("file_path prefix-tolerant resolution", patch_path_resolution, 1, False),
    ]

    new = src
    plan: list[tuple[str, int, int, bool]] = []
    for name, fn, expected, required in steps:
        new, n = fn(new)
        plan.append((name, n, expected, required))

    print("=" * 70)
    print(f"server.py : {server}")
    print(f"mode      : {'APPLY' if args.apply else 'DRY-RUN'}")
    print("=" * 70)
    ok = True
    for name, n, expected, required in plan:
        if n >= expected:
            status = "OK"
        elif required:
            status, ok = "NOT FOUND (required)", False
        else:
            status = "NOT FOUND (optional, skipped)"
        print(f"[{status:>28}] {name}: {n} replacement(s), expected >= {expected}")
    if new == src:
        print("\nNothing to change — server.py may already be patched.")
        sys.exit(0)

    if args.apply and ok:
        backup = server.with_suffix(server.suffix + ".bak")
        backup.write_text(src, encoding="utf-8")
        server.write_text(new, encoding="utf-8")
        print(f"\nPatched. Backup written to: {backup}")
    elif args.apply:
        print("\nABORTED: some patches did not match — server.py left untouched.")
        print("The deployed file may differ from the repo. Send me your server.py")
        print("and I will adjust the patch.")
        sys.exit(2)
    else:
        print("\nDry-run only. Re-run with --apply to write changes.")

    print("\n--- data repair (legacy book.md directories) ---")
    for line in repair_output(Path(args.output), apply=args.apply):
        print("  " + line)

    if args.apply and ok:
        print("\nDone. Restart the web server to load the patched code.")


if __name__ == "__main__":
    main()