#!/usr/bin/env python3
# Tome Phase 7c — Quality Score (per-chapter 1-10 grading).
#
# translator.py:
#   - score_chapter_quality(): cheap grading call, parses "SCORE: x / REASON: ...".
#   - _save_quality(): thread-safe writer for <book>/quality_scores.json.
#   - Wired after the consistency check in both batch and sequential paths.
#   - Toggle: translation.quality_score in tome.json (default ON).
# server.py:  GET /api/books/{title}/quality
# api.ts:     Api.getBookQuality()
# BookDetailView: score badge next to each translated chapter (optional patch).
#
# Usage:  python tome_phase7c.py            (dry-run)
#         python tome_phase7c.py --apply
import argparse, sys
from pathlib import Path

QUALITY_FNS = 'def score_chapter_quality(\n    config: TomeConfig,\n    client: OpenAI,\n    chapter_name: str,\n    translated_text: str,\n    observer: Callable[[str, Any], None] | None = None,\n) -> tuple[int, str]:\n    """Grade translation quality 1-10. Returns (score, reason); (0, \'\') on failure."""\n    prompt = (\n        f"You are a strict literary translation grader. The target language is {config.target_language}.\\n"\n        f"Chapter ({chapter_name}):\\n{translated_text.strip()[:12000]}\\n\\n"\n        "Grade the translation quality: fidelity to meaning, fluency, and internal consistency. "\n        "Reply in exactly this format:\\nSCORE: <integer 1-10>\\nREASON: <one short sentence>"\n    )\n    try:\n        raw = execute_llm_completion(\n            client,\n            config,\n            [{"role": "user", "content": prompt}],\n            observer=None,\n            identifier=f"quality_{Path(chapter_name).stem}",\n            book_title=None,\n        )\n        m = re.search(r"SCORE:\\s*(\\d+)", raw)\n        score = int(m.group(1)) if m else 0\n        if score:\n            score = max(1, min(10, score))\n        rm = re.search(r"REASON:\\s*(.+)", raw)\n        reason = rm.group(1).strip()[:300] if rm else ""\n        if score and observer:\n            observer("chapter_quality_scored", {"chapter": chapter_name, "score": score, "reason": reason})\n        return score, reason\n    except Exception as err:\n        logger.warning("Quality scoring failed for %s: %s", chapter_name, err)\n        return 0, ""\n\n\ndef _save_quality(path: Path, lock: threading.Lock, chapter_name: str, score: int, reason: str) -> None:\n    """Append/overwrite a chapter quality record in <book>/quality_scores.json (thread-safe)."""\n    with lock:\n        data: dict[str, Any] = {}\n        if path.exists():\n            with contextlib.suppress(Exception):\n                data = json.loads(path.read_text(encoding="utf-8"))\n        data[chapter_name] = {"score": score, "reason": reason}\n        with contextlib.suppress(Exception):\n            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")\n\n\n'


def patch_translator(src: str) -> tuple[str, int]:
    n = 0

    if "def score_chapter_quality" not in src:
        anchor = "    return translated_text, len(issues), 0\n\n\ndef translate_book(\n"
        if anchor in src:
            src = src.replace(anchor, "    return translated_text, len(issues), 0\n\n\n" + QUALITY_FNS + "def translate_book(\n", 1)
            n += 1

    old = '    consistency_enabled = _translation_flag(config, "consistency_check", True) and bool(glossary_content)\n'
    new = (
        old
        + '    quality_enabled = _translation_flag(config, "quality_score", True)\n'
        + '    quality_path = book_dir / "quality_scores.json"\n'
        + "    quality_lock = threading.Lock()\n"
    )
    if old in src and "quality_enabled" not in src:
        src = src.replace(old, new, 1)
        n += 1

    old = (
        "                if consistency_enabled:\n"
        "                    t_text, _cons_issues, _cons_fixed = check_chapter_consistency(config, client, glossary_content, c_file.name, t_text, observer)\n"
        "                c_out = translation_dir / c_file.name\n"
    )
    new = (
        "                if consistency_enabled:\n"
        "                    t_text, _cons_issues, _cons_fixed = check_chapter_consistency(config, client, glossary_content, c_file.name, t_text, observer)\n"
        "                if quality_enabled:\n"
        "                    _q_score, _q_reason = score_chapter_quality(config, client, c_file.name, t_text, observer)\n"
        "                    if _q_score:\n"
        "                        _save_quality(quality_path, quality_lock, c_file.name, _q_score, _q_reason)\n"
        "                c_out = translation_dir / c_file.name\n"
    )
    if old in src and "_q_score" not in src:
        src = src.replace(old, new, 1)
        n += 1

    old = (
        "            if consistency_enabled:\n"
        "                translated_text, _cons_issues, _cons_fixed = check_chapter_consistency(config, client, glossary_content, chap_file.name, translated_text, observer)\n"
        "\n"
        "            out_file.write_text(translated_text, encoding=\"utf-8\")\n"
    )
    new = (
        "            if consistency_enabled:\n"
        "                translated_text, _cons_issues, _cons_fixed = check_chapter_consistency(config, client, glossary_content, chap_file.name, translated_text, observer)\n"
        "\n"
        "            if quality_enabled:\n"
        "                _q_score, _q_reason = score_chapter_quality(config, client, chap_file.name, translated_text, observer)\n"
        "                if _q_score:\n"
        "                    _save_quality(quality_path, quality_lock, chap_file.name, _q_score, _q_reason)\n"
        "\n"
        "            out_file.write_text(translated_text, encoding=\"utf-8\")\n"
    )
    if old in src and "score_chapter_quality(config, client, chap_file.name" not in src:
        src = src.replace(old, new, 1)
        n += 1

    return src, (1 if n == 4 else 0)


QUALITY_ENDPOINT = '@app.get("/api/books/{title}/quality")\nasync def api_book_quality(title: str, user: User = Depends(get_current_user)) -> dict[str, Any]:\n    config = TomeConfig.load_config()\n    clean_title = Path(title).name\n    qpath = config.output_dir / clean_title / "quality_scores.json"\n    data: dict[str, Any] = {}\n    with contextlib.suppress(Exception):\n        if qpath.exists():\n            data = json.loads(qpath.read_text(encoding="utf-8"))\n    return {"book": clean_title, "scores": data}\n\n\n'


def patch_server(src: str) -> tuple[str, int]:
    if "api_book_quality" in src:
        return src, 0
    anchor = '@app.get("/api/metrics/dashboard")'
    if anchor in src:
        return src.replace(anchor, QUALITY_ENDPOINT + anchor, 1), 1
    return src, 0


def patch_api_ts(src: str) -> tuple[str, int]:
    anchor = "  static async getMetricsDashboard(): Promise<MetricsDashboard> {\n"
    method = (
        "  static async getBookQuality(title: string): Promise<Record<string, { score: number; reason: string }>> {\n"
        "    const res = await this.request<{ scores: Record<string, { score: number; reason: string }> }>(\n"
        "      `/api/books/${encodeURIComponent(title)}/quality`,\n"
        "    )\n"
        "    return res.scores || {}\n"
        "  }\n"
        "\n"
    )
    if anchor in src and "getBookQuality" not in src:
        return src.replace(anchor, method + anchor, 1), 1
    return src, 0


def patch_book_detail(src: str) -> tuple[str, int]:
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
    old = "            setTransStatusMsg('Chapters translated!')\n            loadBook()\n"
    new = (
        "            setTransStatusMsg('Chapters translated!')\n"
        "            loadBook()\n"
        "            Api.getBookQuality(bookFolder).then(setQuality).catch(() => {})\n"
    )
    if old in src:
        src = src.replace(old, new, 1)
        n += 1
    badge_old = (
        "                          <Badge\n"
        "                            variant={ch.is_translated ? \"success-light\" : \"secondary\"}\n"
        "                            className=\"text-[10px] px-2 py-0.5\"\n"
        "                          >\n"
        "                            {ch.is_translated ? 'Translated' : 'Pending'}\n"
        "                          </Badge>\n"
    )
    badge_new = badge_old + (
        "                          {ch.is_translated && (quality[ch.slug] || quality[`${ch.slug}.md`]) && (\n"
        "                            (() => {\n"
        "                              const q = quality[ch.slug] || quality[`${ch.slug}.md`]\n"
        "                              return (\n"
        "                                <span\n"
        "                                  title={q.reason || `Quality: ${q.score}/10`}\n"
        "                                  className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${\n"
        "                                    q.score >= 8\n"
        "                                      ? 'bg-success-light text-success'\n"
        "                                      : q.score >= 6\n"
        "                                        ? 'bg-amber-500/15 text-amber-600 dark:text-amber-400'\n"
        "                                        : 'bg-destructive/15 text-destructive'\n"
        "                                  }`}\n"
        "                                >\n"
        "                                  {q.score}/10\n"
        "                                </span>\n"
        "                              )\n"
        "                            })()\n"
        "                          )}\n"
    )
    if badge_old in src:
        src = src.replace(badge_old, badge_new, 1)
        n += 1
    return src, n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--core", default="src/tome/core")
    ap.add_argument("--server", default="src/tome/web/server.py")
    ap.add_argument("--webdir", default="web/src")
    args = ap.parse_args()

    print(f"mode: {'APPLY' if args.apply else 'DRY-RUN'}")

    jobs = [
        ("translator.py: quality scoring wiring", Path(args.core) / "translator.py", patch_translator, True),
        ("server.py: GET /api/books/{title}/quality", Path(args.server), patch_server, True),
        ("api.ts: getBookQuality()", Path(args.webdir) / "api.ts", patch_api_ts, True),
        ("BookDetailView: score badges", Path(args.webdir) / "views" / "BookDetailView.tsx", patch_book_detail, False),
    ]
    for name, path, fn, required in jobs:
        if not path.is_file():
            print(f"  [MISSING] {name}")
            continue
        raw = path.read_bytes()
        src = raw.decode("utf-8")
        norm = src.replace("\r\n", "\n")
        new_norm, n = fn(norm)
        if n >= 1:
            status = "OK"
        elif new_norm == norm:
            status = "already applied"
        else:
            status = "NOT FOUND"
        print(f"  [{status:>16}] {name}")
        if new_norm != norm and n >= 1 and args.apply:
            out = new_norm.replace("\n", "\r\n") if b"\r\n" in raw else new_norm
            path.with_suffix(path.suffix + ".bak").write_bytes(raw)
            path.write_bytes(out.encode("utf-8"))
            print(f"         patched {path.name} (.bak saved)")
        elif new_norm != norm and n >= 1:
            print("         (dry-run)")

    if args.apply:
        print("\nDone. Rebuild the frontend:  cd web && npm run build")


if __name__ == "__main__":
    main()