#!/usr/bin/env python3
# Tome Phase 6 FINAL — adds the title page to docx.py (the other two patches
# from the earlier run are already in place; this one only adds what is missing).
# Safe to re-run: exits with "already applied" once done.
# Usage: python tome_phase6_final.py --apply
import argparse, sys
from pathlib import Path

OLD = (
    "    merged_sections: list[str] = []\n"
    "    temp_files: list[Path] = []\n"
    "    try:\n"
    "        for idx, file_path in enumerate(files):\n"
)
NEW = (
    "    merged_sections: list[str] = []\n"
    "    temp_files: list[Path] = []\n"
    "    try:\n"
    "        with tempfile.NamedTemporaryFile(\"w\", suffix=\".md\", delete=False, encoding=\"utf-8\") as tf_title:\n"
    "            tf_title.write(f\"# {book_title}\\n\")\n"
    "            title_page_path = Path(tf_title.name)\n"
    "        temp_files.append(title_page_path)\n"
    "        batch_items.append({\"command\": \"add\", \"parent\": \"/\", \"type\": \"markdown\", \"props\": {\"src\": str(title_page_path.resolve())}})\n"
    "        if not cfg.heading1_pagebreak:\n"
    "            batch_items.append({\"command\": \"add\", \"parent\": \"/\", \"type\": \"pagebreak\"})\n"
    "\n"
    "        for idx, file_path in enumerate(files):\n"
)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--core", default="src/tome/core")
    args = ap.parse_args()
    p = Path(args.core) / "docx.py"
    if not p.is_file():
        sys.exit(f"not found: {p}")
    src = p.read_text(encoding="utf-8")
    if "title_page_path" in src:
        print("already applied")
        return
    if src.count(OLD) != 1:
        print("pattern NOT FOUND — docx.py differs; upload it again")
        sys.exit(2)
    if not args.apply:
        print("dry-run: would add title page to compile_book_to_docx")
        return
    p.with_suffix(".py.bak").write_text(src, encoding="utf-8")
    p.write_text(src.replace(OLD, NEW, 1), encoding="utf-8")
    print("patched (backup: docx.py.bak) — restart the server and test a DOCX compile")

if __name__ == "__main__":
    main()