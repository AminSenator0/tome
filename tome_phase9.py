#!/usr/bin/env python3
# Tome Phase 9 — automatic exchange rate (brsapi.ir) with manual fallback.
#
# avalai.py:
#   - fetch_auto_exchange_rate(): fetches USD/toman from the market API (schema-tolerant
#     parser: finds the "دلار"/USD entry anywhere in the JSON). 12s timeout, safe range check.
#   - resolve_exchange_rate() upgraded: when "exchange_rate_auto" is true in tome.json,
#     uses a cached value (6h) or fetches live; falls back to the manual rate, then default.
# server.py:  dashboard response gains "rate_info" (auto state, last value, last fetch time).
# api.ts/MetricsView: "Auto Rate" toggle + last-fetch display; manual input disabled in auto mode.
#
# Usage:  python tome_phase9.py            (dry-run)
#         python tome_phase9.py --apply
import argparse, sys
from pathlib import Path

NEW_RESOLVE = 'DEFAULT_EXCHANGE_RATE = 70000.0\n\nAUTO_RATE_CACHE_SECONDS = 21600\nDEFAULT_AUTO_RATE_URL = "https://api.brsapi.ir/Market/Gold_Currency.php?key=BTcbzt9hYhndeLvdDnDQxLRXGc8LTBh4"\n\n\ndef _extract_usd_rate(payload: Any) -> float | None:\n    """Find the USD price (toman) in a market API payload, tolerating schema changes."""\n    if isinstance(payload, dict):\n        if isinstance(payload.get("currency"), list):\n            for item in payload["currency"]:\n                with contextlib.suppress(Exception):\n                    name = str(item.get("name") or item.get("title") or "")\n                    if "دلار" in name or name.strip().upper() in {"USD", "US DOLLAR", "DOLLAR"}:\n                        for key in ("price", "sell", "buy", "value"):\n                            with contextlib.suppress(Exception):\n                                return float(item[key])\n        for key, value in payload.items():\n            if isinstance(key, str) and key.strip().upper() in {"USD", "DOLLAR"} and isinstance(value, dict):\n                for k in ("price", "sell", "buy", "value"):\n                    with contextlib.suppress(Exception):\n                        return float(value[k])\n        for value in payload.values():\n            found = _extract_usd_rate(value)\n            if found:\n                return found\n    elif isinstance(payload, list):\n        for item in payload:\n            if isinstance(item, dict):\n                name = str(item.get("name") or item.get("title") or item.get("symbol") or "")\n                if "دلار" in name or name.strip().upper() in {"USD", "US DOLLAR", "DOLLAR"}:\n                    for k in ("price", "sell", "buy", "value"):\n                        with contextlib.suppress(Exception):\n                            return float(item[k])\n        for item in payload:\n            found = _extract_usd_rate(item)\n            if found:\n                return found\n    return None\n\n\ndef fetch_auto_exchange_rate(config: Any = None) -> tuple[float, float] | None:\n    """Fetch USD/toman from the configured market API. Returns (rate, fetched_at) or None."""\n    import urllib.request\n\n    url = None\n    with contextlib.suppress(Exception):\n        url = getattr(config, "exchange_rate_auto_url", None)\n    if not url:\n        url = DEFAULT_AUTO_RATE_URL\n    try:\n        req = urllib.request.Request(url, headers={"User-Agent": "tome/1.0"})\n        with urllib.request.urlopen(req, timeout=12) as resp:\n            payload = json.loads(resp.read().decode("utf-8", errors="ignore"))\n        rate = _extract_usd_rate(payload)\n        if rate and 1000 < rate < 10_000_000:\n            return float(rate), time.time()\n    except Exception as err:\n        logger.warning("Auto exchange rate fetch failed: %s", err)\n    return None\n\n\ndef resolve_exchange_rate(config: Any = None) -> float:\n    """Toman per USD. Priority: auto mode (cached/fetched) -> manual tome.json -> default."""\n    try:\n        data = json.loads(Path("tome.json").read_text(encoding="utf-8"))\n    except Exception:\n        data = {}\n\n    if data.get("exchange_rate_auto"):\n        with contextlib.suppress(Exception):\n            cached = float(data.get("exchange_rate_auto_value") or 0)\n            fetched_at = float(data.get("exchange_rate_auto_at") or 0)\n            if cached and time.time() - fetched_at < AUTO_RATE_CACHE_SECONDS:\n                return cached\n        got = fetch_auto_exchange_rate(config)\n        if got:\n            rate, at = got\n            data["exchange_rate_auto_value"] = rate\n            data["exchange_rate_auto_at"] = at\n            with contextlib.suppress(Exception):\n                Path("tome.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")\n            return rate\n\n    manual = data.get("exchange_rate")\n    if manual:\n        return float(manual)\n    return DEFAULT_EXCHANGE_RATE\n\n\n'


OLD_RESOLVE = 'DEFAULT_EXCHANGE_RATE = 70000.0\n\n\ndef resolve_exchange_rate(config: Any = None) -> float:\n    """Toman per USD. Priority: config attr -> tome.json -> default."""\n    with contextlib.suppress(Exception):\n        val = getattr(config, "exchange_rate", None)\n        if val:\n            return float(val)\n    with contextlib.suppress(Exception):\n        data = json.loads(Path("tome.json").read_text(encoding="utf-8"))\n        val = data.get("exchange_rate")\n        if val:\n            return float(val)\n    return DEFAULT_EXCHANGE_RATE\n\n\n'


def patch_avalai(src: str) -> tuple[str, int]:
    n = 0
    if "import time" not in src:
        anchor = "DEFAULT_EXCHANGE_RATE = 70000.0\n"
        if anchor in src:
            src = src.replace(anchor, "import time\n\n" + anchor, 1)
            n += 1
    if OLD_RESOLVE in src:
        src = src.replace(OLD_RESOLVE, NEW_RESOLVE, 1)
        n += 1
    return src, (1 if n == 2 else 0)


def patch_server(src: str) -> tuple[str, int]:
    n = 0
    old = '    return {\n        "totals": totals,\n        "books": books,\n'
    new = (
        "    rate_info = {\"auto\": False, \"auto_value\": None, \"auto_at\": None}\n"
        "    with contextlib.suppress(Exception):\n"
        "        tj = json.loads(Path(\"tome.json\").read_text(encoding=\"utf-8\"))\n"
        "        rate_info = {\n"
        "            \"auto\": bool(tj.get(\"exchange_rate_auto\")),\n"
        "            \"auto_value\": tj.get(\"exchange_rate_auto_value\"),\n"
        "            \"auto_at\": tj.get(\"exchange_rate_auto_at\"),\n"
        "        }\n"
        + old
    )
    if old in src and "rate_info" not in src:
        src = src.replace(old, new, 1)
        n += 1
    old = '        "current_exchange_rate": current_rate,\n'
    new = old + '        "rate_info": rate_info,\n'
    if old in src and '"rate_info": rate_info' not in src:
        src = src.replace(old, new, 1)
        n += 1
    return src, (1 if n == 2 else 0)


def patch_api_ts(src: str) -> tuple[str, int]:
    old = "  current_exchange_rate: number\n  generated_at: number\n}\n"
    new = (
        "  current_exchange_rate: number\n"
        "  rate_info?: { auto: boolean; auto_value: number | null; auto_at: number | null }\n"
        "  generated_at: number\n}\n"
    )
    if old in src and "rate_info" not in src:
        return src.replace(old, new, 1), 1
    return src, 0


TOGGLE_FN = """  const toggleAutoRate = async () => {
    setSavingRate(true)
    try {
      await (Api.updateConfig as any)({ exchange_rate_auto: !data?.rate_info?.auto })
      await load()
    } catch (err: any) {
      alert(err?.message || 'Failed to toggle auto rate')
    } finally {
      setSavingRate(false)
    }
  }

"""


def patch_view(src: str) -> tuple[str, int]:
    n = 0
    old = "  const [savingRate, setSavingRate] = useState(false)\n\n  useEffect(() => {\n    if (data) setRateInput"
    new = "  const [savingRate, setSavingRate] = useState(false)\n\n" + TOGGLE_FN + "  useEffect(() => {\n    if (data) setRateInput"
    if old in src and "toggleAutoRate" not in src:
        src = src.replace(old, new, 1)
        n += 1
    old = '              value={rateInput}\n              onChange={(e) => setRateInput(e.target.value)}\n'
    new = '              disabled={Boolean(data?.rate_info?.auto)}\n' + old
    if old in src and "disabled={Boolean(data?.rate_info?.auto)}" not in src:
        src = src.replace(old, new, 1)
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
    ap.add_argument("--core", default="src/tome/core")
    ap.add_argument("--server", default="src/tome/web/server.py")
    ap.add_argument("--webdir", default="web/src")
    args = ap.parse_args()
    print(f"mode: {'APPLY' if args.apply else 'DRY-RUN'}")

    jobs = [
        ("avalai.py: auto rate fetch + resolver upgrade", Path(args.core) / "avalai.py", patch_avalai, True),
        ("server.py: dashboard rate_info", Path(args.server), patch_server, True),
        ("api.ts: rate_info type", Path(args.webdir) / "api.ts", patch_api_ts, True),
        ("MetricsView: auto toggle UI", Path(args.webdir) / "views" / "MetricsView.tsx", patch_view, False),
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
        print("\nDone. Rebuild:  cd web && npm run build")


if __name__ == "__main__":
    main()