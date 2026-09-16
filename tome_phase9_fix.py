#!/usr/bin/env python3
# Fix for phase 9: ensures toggleAutoRate() exists in MetricsView.tsx and the
# Auto Rate button is present. Idempotent, tries multiple anchor variants.
# Usage: python tome_phase9_fix.py --apply   (+ npm run build)
import argparse, sys
from pathlib import Path

TOGGLE_FN = "  const toggleAutoRate = async () => {\n    setSavingRate(true)\n    try {\n      await (Api.updateConfig as any)({ exchange_rate_auto: !data?.rate_info?.auto })\n      await load()\n    } catch (err: any) {\n      alert(err?.message || 'Failed to toggle auto rate')\n    } finally {\n      setSavingRate(false)\n    }\n  }\n\n"


def patch_view(src: str) -> tuple[str, int]:
    n = 0
    if "const toggleAutoRate" not in src:
        inserted = False
        variants = [
            ("  const [savingRate, setSavingRate] = useState(false)\n\n  useEffect(() => {\n    if (data) setRateInput",
             "  const [savingRate, setSavingRate] = useState(false)\n\n" + TOGGLE_FN + "  useEffect(() => {\n    if (data) setRateInput"),
            ("  const [savingRate, setSavingRate] = useState(false)\n",
             "  const [savingRate, setSavingRate] = useState(false)\n\n" + TOGGLE_FN),
            ("  const saveRate = async () => {\n",
             TOGGLE_FN + "  const saveRate = async () => {\n"),
        ]
        for old, new in variants:
            if old in src:
                src = src.replace(old, new, 1)
                inserted = True
                break
        if inserted:
            n += 1
    old = '          <Button size="sm" className="h-10 px-5" onClick={saveRate} loading={savingRate}>Save Rate</Button>\n'
    new = (
        old
        + '          <Button\n'
        + '            size="sm"\n'
        + '            className="h-10 px-4"\n'
        + '            onClick={toggleAutoRate}\n'
        + '            loading={savingRate}\n'
        + '          >\n'
        + "            {data?.rate_info?.auto ? 'Auto Rate: ON' : 'Auto Rate: OFF'}\n"
        + '          </Button>\n'
        + "          {data?.rate_info?.auto && data.rate_info.auto_at ? (\n"
        + '            <span className="text-[11px] text-muted-foreground self-center tabular-nums">\n'
        + '              Last fetch: {fmtDate(data.rate_info.auto_at)}\n'
        + '            </span>\n'
        + '          ) : null}\n'
    )
    if old in src and "Auto Rate: ON" not in src:
        src = src.replace(old, new, 1)
        n += 1
    return src, n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--webdir", default="web/src")
    args = ap.parse_args()
    p = Path(args.webdir) / "views" / "MetricsView.tsx"
    if not p.is_file():
        sys.exit(f"not found: {p}")
    raw = p.read_bytes()
    src = raw.decode("utf-8")
    norm = src.replace("\r\n", "\n")
    new_norm, n = patch_view(norm)
    if "const toggleAutoRate" not in new_norm:
        print("[NOT FIXED] toggleAutoRate could not be inserted — paste the region around 'savingRate' from your MetricsView.tsx")
        sys.exit(2)
    if n == 0:
        print("already applied")
        return
    if not args.apply:
        print(f"dry-run: would insert {n} missing piece(s)")
        return
    out = new_norm.replace("\n", "\r\n") if b"\r\n" in raw else new_norm
    p.with_suffix(".tsx.bak").write_bytes(raw)
    p.write_bytes(out.encode("utf-8"))
    print(f"fixed ({n} piece(s)) — now run: cd web && npm run build")


if __name__ == "__main__":
    main()