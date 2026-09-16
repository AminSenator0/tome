#!/usr/bin/env python3
# Tome Phase 6 v2 — professional docx typography (CRLF/LF agnostic).
#
# docx.py:
#   1. Body text font size (default 14pt, override with "docx_body_size" in tome.json)
#   2. Paragraph spacing 4pt -> 6pt
#   3. Real title page: centered book title on its own page
#
# Usage:  python tome_phase6.py            (dry-run)
#         python tome_phase6.py --apply
import argparse, sys
from pathlib import Path


def patch_docx_py(src: str) -> tuple[str, int]:
    n = 0

    old = "    font_cs = font_eastern if is_rtl else font_western\n    font_latin = font_western\n"
    new = (
        old
        + "\n"
        + "    body_size = \"14\"\n"
        + "    with contextlib.suppress(Exception):\n"
        + "        _tome_size = json.loads(Path(\"tome.json\").read_text(encoding=\"utf-8\")).get(\"docx_body_size\")\n"
        + "        if _tome_size:\n"
        + "            body_size = str(_tome_size)\n"
    )
    if old in src and "body_size" not in src:
        src = src.replace(old, new, 1)
        n += 1

    old = (
        '                "align": align_body,\n'
        '                "lineSpacing": cfg.line_spacing,\n'
        '                "spaceAfter": "4pt",\n'
    )
    new = (
        '                "align": align_body,\n'
        '                "size": body_size,\n'
        '                "lineSpacing": cfg.line_spacing,\n'
        '                "spaceAfter": "6pt",\n'
    )
    if old in src:
        src = src.replace(old, new, 1)
        n += 1

    old = (
        "        merged_sections: list[str] = []\n"
        "        temp_files: list[Path] = []\n"
        "        try:\n"
        "            for idx, file_path in enumerate(files):\n"
    )
    new = (
        "        merged_sections: list[str] = []\n"
        "        temp_files: list[Path] = []\n"
        "        try:\n"
        "            with tempfile.NamedTemporaryFile(\"w\", suffix=\".md\", delete=False, encoding=\"utf-8\") as tf_title:\n"
        "                tf_title.write(f\"# {book_title}\\n\")\n"
        "                title_page_path = Path(tf_title.name)\n"
        "            temp_files.append(title_page_path)\n"
        "            batch_items.append({\"command\": \"add\", \"parent\": \"/\", \"type\": \"markdown\", \"props\": {\"src\": str(title_page_path.resolve())}})\n"
        "            if not cfg.heading1_pagebreak:\n"
        "                batch_items.append({\"command\": \"add\", \"parent\": \"/\", \"type\": \"pagebreak\"})\n"
        "\n"
        "            for idx, file_path in enumerate(files):\n"
    )
    if old in src and "title_page_path" not in src:
        src = src.replace(old, new, 1)
        n += 1

    return src, (1 if n == 3 else 0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--core", default="src/tome/core")
    args = ap.parse_args()
    p = Path(args.core) / "docx.py"
    if not p.is_file():
        sys.exit(f"not found: {p}")

    raw = p.read_bytes()
    has_crlf = b"\r\n" in raw
    src = raw.decode("utf-8")
    norm = src.replace("\r\n", "\n")

    new_norm, n = patch_docx_py(norm)
    if n >= 1:
        status = "OK"
    elif "title_page_path" in norm:
        status = "already applied"
    else:
        status = "NOT FOUND"
    print(f"[{status}] docx.py: professional typography (body size, spacing, title page)")

    if new_norm == norm:
        if n == 0 and "title_page_path" not in norm and not ap.__dict__.get("apply"):
            pass
        return
    if not args.__dict__.get("apply"):
        print("(dry-run — re-run with --apply)")
        return
    out = new_norm.replace("\n", "\r\n") if has_crlf else new_norm
    p.with_suffix(".py.bak").write_bytes(raw)
    p.write_bytes(out.encode("utf-8"))
    print("patched (backup: docx.py.bak)")


if __name__ == "__main__":
    main()