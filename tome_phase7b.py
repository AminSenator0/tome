#!/usr/bin/env python3
# Tome Phase 7b — Consistency Check (glossary deviation detection + one-pass fix).
#
# translator.py:
#   - New helper check_chapter_consistency(): scans the translated chapter against
#     glossary.md (source-name leakage + missing target forms). If deviations exist,
#     one corrective LLM pass rewrites ONLY the names. Length-ratio guard keeps
#     output sane; failures never break translation.
#   - Wired into both batch and sequential paths, after translation and before the
#     rolling summary update (so the summary reflects corrected text).
#   - Toggle: translation.consistency_check in tome.json (default ON).
#
# Usage:  python tome_phase7b.py            (dry-run)
#         python tome_phase7b.py --apply
import argparse, sys
from pathlib import Path

CONSISTENCY_FN = 'def check_chapter_consistency(\n    config: TomeConfig,\n    client: OpenAI,\n    glossary_content: str,\n    chapter_name: str,\n    translated_text: str,\n    observer: Callable[[str, Any], None] | None = None,\n) -> tuple[str, int, int]:\n    """Detect glossary deviations in a translated chapter and fix them with one LLM pass.\n\n    Returns (final_text, issues_found, fixes_applied). Never raises.\n    """\n    issues: list[str] = []\n    try:\n        for line in glossary_content.splitlines():\n            if not line.startswith("|") or line.startswith("|---"):\n                continue\n            cols = [c.strip() for c in line.split("|")[1:-1]]\n            if len(cols) < 3 or not cols[0] or cols[0] == "Canonical Term":\n                continue\n            canonical, aliases, term_translation = cols[0], cols[1], cols[2]\n            target = term_translation.strip()\n            if len(target) < 2:\n                continue\n            source_forms = [canonical.strip()] + [a.strip() for a in aliases.split(",") if a.strip()]\n            lower_text = translated_text.lower()\n            leaked = [\n                f for f in source_forms\n                if len(f) >= 4 and re.search(rf"(?<!\\w){re.escape(f.lower())}(?!\\w)", lower_text)\n            ]\n            missing = target.lower() not in lower_text\n            if leaked or missing:\n                issues.append(\n                    f"{canonical} -> {target}" + (f" (source leaked: {\', \'.join(leaked)})" if leaked else " (target missing)")\n                )\n    except Exception as err:\n        logger.warning("Consistency scan failed for %s: %s", chapter_name, err)\n        return translated_text, 0, 0\n\n    if not issues:\n        return translated_text, 0, 0\n\n    if observer:\n        observer("consistency_issues", {"chapter": chapter_name, "count": len(issues), "issues": issues[:20]})\n\n    relevant_rows = "\\n".join(\n        line for line in glossary_content.splitlines() if line.startswith("|")\n    )[:6000]\n    prompt = (\n        f"You are a terminology enforcer for a literary translation into {config.target_language}.\\n"\n        f"Glossary (authoritative):\\n{relevant_rows}\\n\\n"\n        f"Translated chapter ({chapter_name}):\\n{translated_text.strip()[:14000]}\\n\\n"\n        "Some entity names in the chapter deviate from the glossary. Rewrite the chapter so that EVERY "\n        "entity name exactly matches its \'Term Translation\' in the glossary. Change names only; do not alter "\n        "style, dialogue, or anything else. Output ONLY the full corrected chapter."\n    )\n    try:\n        fixed = execute_llm_completion(\n            client,\n            config,\n            [{"role": "user", "content": prompt}],\n            observer=None,\n            identifier=f"consistency_{Path(chapter_name).stem}",\n            book_title=None,\n        ).strip()\n        src_len = max(1, len(translated_text))\n        if fixed and 0.6 <= len(fixed) / src_len <= 1.6:\n            if observer:\n                observer("consistency_fixed", {"chapter": chapter_name, "issues": len(issues)})\n            return fixed, len(issues), 1\n        logger.warning("Consistency fix rejected for %s (length ratio out of range)", chapter_name)\n    except Exception as err:\n        logger.warning("Consistency fix failed for %s: %s", chapter_name, err)\n    return translated_text, len(issues), 0\n\n\n'


def patch_translator(src: str) -> tuple[str, int]:
    n = 0

    # 1) helper after update_rolling_summary
    if "def check_chapter_consistency" not in src:
        anchor = "        return previous_summary\n\n\ndef translate_book(\n"
        if anchor in src:
            src = src.replace(anchor, "        return previous_summary\n\n\n" + CONSISTENCY_FN + "def translate_book(\n", 1)
            n += 1

    # 2) setup flag
    old = (
        "    rolling_enabled = _translation_flag(config, \"context_rolling\", True)\n"
        "    rolling_path = book_dir / \"context_rolling.md\"\n"
        "    rolling_summary = rolling_path.read_text(encoding=\"utf-8\").strip() if rolling_path.exists() else \"\"\n"
        "    rolling_lock = threading.Lock()\n"
    )
    new = old + "    consistency_enabled = _translation_flag(config, \"consistency_check\", True) and bool(glossary_content)\n"
    if old in src and "consistency_enabled" not in src:
        src = src.replace(old, new, 1)
        n += 1

    # 3) batch worker: consistency before rolling summary
    old = (
        "                    rolling_summary=rolling_summary,\n"
        "                )\n"
        "                c_out = translation_dir / c_file.name\n"
    )
    new = (
        "                    rolling_summary=rolling_summary,\n"
        "                )\n"
        "                if consistency_enabled:\n"
        "                    t_text, _cons_issues, _cons_fixed = check_chapter_consistency(config, client, glossary_content, c_file.name, t_text, observer)\n"
        "                c_out = translation_dir / c_file.name\n"
    )
    if old in src and "check_chapter_consistency(config, client, glossary_content, c_file.name" not in src:
        src = src.replace(old, new, 1)
        n += 1

    # 4) sequential path
    old = (
        "                rolling_summary=rolling_summary,\n"
        "            )\n"
        "\n"
        "            out_file.write_text(translated_text, encoding=\"utf-8\")\n"
    )
    new = (
        "                rolling_summary=rolling_summary,\n"
        "            )\n"
        "\n"
        "            if consistency_enabled:\n"
        "                translated_text, _cons_issues, _cons_fixed = check_chapter_consistency(config, client, glossary_content, chap_file.name, translated_text, observer)\n"
        "\n"
        "            out_file.write_text(translated_text, encoding=\"utf-8\")\n"
    )
    if old in src and "check_chapter_consistency(config, client, glossary_content, chap_file.name" not in src:
        src = src.replace(old, new, 1)
        n += 1

    return src, (1 if n == 4 else 0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--core", default="src/tome/core")
    args = ap.parse_args()
    p = Path(args.core) / "translator.py"
    if not p.is_file():
        sys.exit(f"not found: {p}")
    raw = p.read_bytes()
    has_crlf = b"\r\n" in raw
    src = raw.decode("utf-8")
    norm = src.replace("\r\n", "\n")

    new_norm, n = patch_translator(norm)
    if n >= 1:
        status = "OK"
    elif "def check_chapter_consistency" in norm:
        status = "already applied"
    else:
        status = "NOT FOUND"
    print(f"[{status}] translator.py: consistency check (glossary deviation fix)")

    if new_norm == norm:
        return
    if not args.apply:
        print("(dry-run — re-run with --apply)")
        return
    out = new_norm.replace("\n", "\r\n") if has_crlf else new_norm
    p.with_suffix(".py.bak").write_bytes(raw)
    p.write_bytes(out.encode("utf-8"))
    print("patched (backup: translator.py.bak)")


if __name__ == "__main__":
    main()