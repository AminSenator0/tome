#!/usr/bin/env python3
# Fix api_update_config to accept arbitrary top-level keys (e.g. exchange_rate).
# Usage: python tome_phase5d.py --apply
import argparse, sys
from pathlib import Path

OLD = """async def api_update_config(req: ConfigUpdateRequest, user: User = Depends(get_current_user)) -> dict[str, str]:
    tome_json = Path("tome.json")
    data: dict[str, Any] = {}
    if tome_json.exists():
        data = json.loads(tome_json.read_text(encoding="utf-8"))

    for section_name in ("general", "llm", "proxy", "nlp", "translation", "typography"):
        val = getattr(req, section_name, None)
        if val is not None:
            data.setdefault(section_name, {}).update(val)

    tome_json.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
"""

NEW = """async def api_update_config(req: dict[str, Any], user: User = Depends(get_current_user)) -> dict[str, str]:
    tome_json = Path("tome.json")
    data: dict[str, Any] = {}
    if tome_json.exists():
        data = json.loads(tome_json.read_text(encoding="utf-8"))

    section_names = ("general", "llm", "proxy", "nlp", "translation", "typography")
    for section_name in section_names:
        val = req.get(section_name)
        if val is not None:
            data.setdefault(section_name, {}).update(val)

    for key, value in req.items():
        if key not in section_names:
            data[key] = value

    tome_json.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--server", default="src/tome/web/server.py")
    args = ap.parse_args()
    p = Path(args.server)
    if not p.is_file():
        sys.exit(f"not found: {p}")
    src = p.read_text(encoding="utf-8")
    if "for key, value in req.items():" in src:
        print("already applied")
        return
    if src.count(OLD) != 1:
        print("pattern NOT FOUND — server.py differs from expected; paste your api_update_config")
        sys.exit(2)
    if not args.apply:
        print("dry-run: would patch api_update_config (accept arbitrary top-level keys)")
        return
    p.with_suffix(".py.bak").write_text(src, encoding="utf-8")
    p.write_text(src.replace(OLD, NEW, 1), encoding="utf-8")
    print("patched (backup: server.py.bak)")
    print("restart your local server, then save the rate again from the dashboard")

if __name__ == "__main__":
    main()