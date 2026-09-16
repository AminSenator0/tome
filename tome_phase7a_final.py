#!/usr/bin/env python3
# Tome Phase 7a FINAL — applies the one missing piece: context rolling inside the
# batch-mode worker (the other 8 sub-patches are already in place).
# Idempotent: reports "already applied" once done.
# Usage: python tome_phase7a_final.py --apply
import argparse, sys
from pathlib import Path

OLD = (
    "                t_text, _ = translate_chapter(\n"
    "                    chapter_path=c_file,\n"
    "                    config=config,\n"
    "                    client=client,\n"
    "                    glossary_content=glossary_content,\n"
    "                    graph_context=graph_context,\n"
    "                    observer=observer,\n"
    "                    content_override=c_content,\n"
    "                    metrics_out=worker_metrics,\n"
    "                    genre=book_genre,\n"
    "                )\n"
    "                c_out = translation_dir / c_file.name\n"
    "                c_out.write_text(t_text, encoding=\"utf-8\")\n"
)
NEW = (
    "                t_text, _ = translate_chapter(\n"
    "                    chapter_path=c_file,\n"
    "                    config=config,\n"
    "                    client=client,\n"
    "                    glossary_content=glossary_content,\n"
    "                    graph_context=graph_context,\n"
    "                    observer=observer,\n"
    "                    content_override=c_content,\n"
    "                    metrics_out=worker_metrics,\n"
    "                    genre=book_genre,\n"
    "                    rolling_summary=rolling_summary,\n"
    "                )\n"
    "                c_out = translation_dir / c_file.name\n"
    "                c_out.write_text(t_text, encoding=\"utf-8\")\n"
    "                if rolling_enabled:\n"
    "                    with rolling_lock:\n"
    "                        prev_sum = rolling_path.read_text(encoding=\"utf-8\").strip() if rolling_path.exists() else \"\"\n"
    "                        new_sum = update_rolling_summary(config, client, prev_sum, c_file.name, t_text, observer)\n"
    "                        if new_sum and new_sum != prev_sum:\n"
    "                            rolling_path.write_text(new_sum, encoding=\"utf-8\")\n"
)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--core", default="src/tome/core")
    args = ap.parse_args()
    p = Path(args.core) / "translator.py"
    if not p.is_file():
        sys.exit(f"not found: {p}")
    src = p.read_text(encoding="utf-8")
    if src.count("rolling_summary=rolling_summary") >= 2:
        print("already applied")
        return
    if src.count(OLD) != 1:
        print("pattern NOT FOUND — upload translator.py again")
        sys.exit(2)
    if not args.apply:
        print("dry-run: would add context rolling to the batch worker")
        return
    p.with_suffix(".py.bak").write_text(src, encoding="utf-8")
    p.write_text(src.replace(OLD, NEW, 1), encoding="utf-8")
    print("patched (backup: translator.py.bak) — restart the server and test")

if __name__ == "__main__":
    main()