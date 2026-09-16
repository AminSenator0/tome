#!/usr/bin/env python3
"""
Tome Phase 5 — Cost Dashboard.

Backend:  GET /api/metrics/dashboard (accurate totals recomputed from
          chapter-level records in each book's metrics.json + live AvalAI credit)
Frontend: new MetricsView (summary cards, per-model breakdown, books table),
          wired into Sidebar + App routing.

Usage:  python tome_phase5.py            (dry-run)
        python tome_phase5.py --apply
"""

import argparse
import sys
from pathlib import Path

METRICS_VIEW = 'import React, { useState, useEffect, useCallback } from \'react\'\nimport {\n  RefreshCw,\n  Wallet,\n  Coins,\n  BookOpen,\n  Layers,\n  Timer,\n  BarChart3,\n} from \'lucide-react\'\nimport { Api, MetricsDashboard } from \'../api\'\nimport { Card, CardHeader, CardTitle, CardContent } from \'../components/ui/Card\'\nimport { Button } from \'../components/ui/Button\'\n\nconst fmtInt = (n: number) => new Intl.NumberFormat(\'en-US\', { maximumFractionDigits: 0 }).format(n)\n\nconst fmtTokens = (n: number) => {\n  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`\n  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`\n  return fmtInt(n)\n}\n\nconst fmtDuration = (sec: number) => {\n  if (sec <= 0) return \'—\'\n  const h = sec / 3600\n  if (h >= 1) return `${h.toFixed(1)}h`\n  const m = sec / 60\n  return `${m.toFixed(0)}m`\n}\n\nconst fmtDate = (ts: number) => {\n  if (!ts) return \'—\'\n  return new Date(ts * 1000).toLocaleString(\'en-US\', {\n    month: \'short\',\n    day: \'numeric\',\n    hour: \'2-digit\',\n    minute: \'2-digit\',\n  })\n}\n\nexport const MetricsView: React.FC = () => {\n  const [data, setData] = useState<MetricsDashboard | null>(null)\n  const [error, setError] = useState<string | null>(null)\n  const [loading, setLoading] = useState(true)\n\n  const load = useCallback(async () => {\n    setLoading(true)\n    setError(null)\n    try {\n      const res = await Api.getMetricsDashboard()\n      setData(res)\n    } catch (err: any) {\n      setError(err?.message || \'Failed to load metrics\')\n    } finally {\n      setLoading(false)\n    }\n  }, [])\n\n  useEffect(() => {\n    load()\n  }, [load])\n\n  if (loading && !data) {\n    return (\n      <div className="flex items-center justify-center h-64 text-muted-foreground">\n        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />\n      </div>\n    )\n  }\n\n  if (error && !data) {\n    return (\n      <div className="space-y-4">\n        <p className="text-destructive">{error}</p>\n        <Button size="sm" onClick={load}>Retry</Button>\n      </div>\n    )\n  }\n\n  if (!data) return null\n\n  const t = data.totals\n  const grandCost = t.cost_toman || 0\n  const avgPerChapter = t.chapters > 0 ? grandCost / t.chapters : 0\n\n  const creditNumber = (() => {\n    const c: any = data.credit\n    if (!c || typeof c !== \'object\') return null\n    const keys = [\'remaining_credit\', \'credit\', \'balance\', \'remaining\', \'amount\', \'total_credit\']\n    for (const k of keys) {\n      const v = c[k]\n      if (typeof v === \'number\') return v\n      if (v && typeof v === \'object\') {\n        for (const k2 of keys) {\n          if (typeof v[k2] === \'number\') return v[k2] as number\n        }\n      }\n    }\n    return null\n  })()\n\n  const statCard = (\n    icon: React.ReactNode,\n    label: string,\n    value: string,\n    sub?: string,\n  ) => (\n    <Card className="rounded-3xl border-0">\n      <CardContent className="p-5">\n        <div className="flex items-center gap-3">\n          <div className="p-2.5 rounded-2xl bg-primary/10 text-primary">{icon}</div>\n          <div className="min-w-0">\n            <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wide truncate">{label}</p>\n            <p className="text-xl font-semibold tabular-nums truncate">{value}</p>\n            {sub && <p className="text-[11px] text-muted-foreground tabular-nums">{sub}</p>}\n          </div>\n        </div>\n      </CardContent>\n    </Card>\n  )\n\n  return (\n    <div className="space-y-6">\n      <div className="flex flex-wrap items-center justify-between gap-3">\n        <div>\n          <h1 className="text-2xl font-semibold flex items-center gap-2">\n            <BarChart3 className="h-5 w-5 text-primary" />\n            Cost Dashboard\n          </h1>\n          <p className="text-sm text-muted-foreground">\n            All figures are recomputed from chapter-level records in each book\'s metrics.json\n          </p>\n        </div>\n        <Button size="sm" className="gap-1.5" onClick={load} loading={loading}>\n          <RefreshCw className="h-3.5 w-3.5" />\n          <span>Refresh</span>\n        </Button>\n      </div>\n\n      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3">\n        {statCard(<Coins className="h-5 w-5" />, \'Total Cost (Toman)\', fmtInt(grandCost), `$${t.cost_usd.toFixed(2)}`)}\n        {statCard(<Layers className="h-5 w-5" />, \'Tokens\', fmtTokens(t.tokens), `in ${fmtTokens(t.prompt_tokens)} / out ${fmtTokens(t.completion_tokens + t.reasoning_tokens)}`)}\n        {statCard(<BookOpen className="h-5 w-5" />, \'Books\', fmtInt(t.books), `${fmtInt(t.chapters)} chapters`)}\n        {statCard(<Coins className="h-5 w-5" />, \'Avg / Chapter\', fmtInt(avgPerChapter), \'toman\')}\n        {statCard(<Timer className="h-5 w-5" />, \'Compute Time\', fmtDuration(t.duration_seconds), \'translation runtime\')}\n        {statCard(<Wallet className="h-5 w-5" />, \'Wallet Credit\', creditNumber !== null ? fmtInt(creditNumber) : data.credit ? \'See details\' : \'N/A\', creditNumber !== null ? \'toman (live)\' : undefined)}\n      </div>\n\n      {data.credit && creditNumber === null && (\n        <Card className="rounded-3xl border-0">\n          <CardHeader className="pb-2">\n            <CardTitle className="text-sm flex items-center gap-2">\n              <Wallet className="h-4 w-4 text-primary" /> Provider Credit (raw)\n            </CardTitle>\n          </CardHeader>\n          <CardContent>\n            <pre className="text-xs bg-secondary/40 rounded-2xl p-4 overflow-x-auto custom-scrollbar">\n              {JSON.stringify(data.credit, null, 2)}\n            </pre>\n          </CardContent>\n        </Card>\n      )}\n\n      {data.models.length > 0 && (\n        <Card className="rounded-3xl border-0">\n          <CardHeader className="pb-2">\n            <CardTitle className="text-sm">Cost by Model</CardTitle>\n          </CardHeader>\n          <CardContent className="overflow-x-auto">\n            <table className="w-full text-sm">\n              <thead>\n                <tr className="text-left text-muted-foreground text-xs uppercase tracking-wide border-b border-border">\n                  <th className="py-2 pr-4 font-medium">Model</th>\n                  <th className="py-2 pr-4 font-medium text-right">Books</th>\n                  <th className="py-2 pr-4 font-medium text-right">Chapters</th>\n                  <th className="py-2 pr-4 font-medium text-right">Tokens</th>\n                  <th className="py-2 pr-4 font-medium text-right">Cost (Toman)</th>\n                  <th className="py-2 font-medium text-right">Share</th>\n                </tr>\n              </thead>\n              <tbody>\n                {data.models.map((m) => {\n                  const share = grandCost > 0 ? (m.cost_toman / grandCost) * 100 : 0\n                  return (\n                    <tr key={m.model} className="border-b border-border/50 last:border-0">\n                      <td className="py-2.5 pr-4 font-medium">{m.model}</td>\n                      <td className="py-2.5 pr-4 text-right tabular-nums">{fmtInt(m.books)}</td>\n                      <td className="py-2.5 pr-4 text-right tabular-nums">{fmtInt(m.chapters)}</td>\n                      <td className="py-2.5 pr-4 text-right tabular-nums">{fmtTokens(m.tokens)}</td>\n                      <td className="py-2.5 pr-4 text-right tabular-nums">{fmtInt(m.cost_toman)}</td>\n                      <td className="py-2.5 text-right tabular-nums">\n                        <div className="inline-flex items-center gap-2">\n                          <div className="w-20 h-1.5 rounded-full bg-secondary overflow-hidden">\n                            <div className="h-full bg-primary rounded-full" style={{ width: `${Math.min(100, share)}%` }} />\n                          </div>\n                          <span className="text-muted-foreground w-12">{share.toFixed(1)}%</span>\n                        </div>\n                      </td>\n                    </tr>\n                  )\n                })}\n              </tbody>\n            </table>\n          </CardContent>\n        </Card>\n      )}\n\n      <Card className="rounded-3xl border-0">\n        <CardHeader className="pb-2">\n          <CardTitle className="text-sm">Books ({fmtInt(data.books.length)})</CardTitle>\n        </CardHeader>\n        <CardContent className="overflow-x-auto">\n          {data.books.length === 0 ? (\n            <p className="text-sm text-muted-foreground py-8 text-center">\n              No metrics yet — translate a book and its costs will appear here.\n            </p>\n          ) : (\n            <table className="w-full text-sm">\n              <thead>\n                <tr className="text-left text-muted-foreground text-xs uppercase tracking-wide border-b border-border">\n                  <th className="py-2 pr-4 font-medium">#</th>\n                  <th className="py-2 pr-4 font-medium">Book</th>\n                  <th className="py-2 pr-4 font-medium">Model</th>\n                  <th className="py-2 pr-4 font-medium text-right">Chapters</th>\n                  <th className="py-2 pr-4 font-medium text-right">Tokens</th>\n                  <th className="py-2 pr-4 font-medium text-right">Duration</th>\n                  <th className="py-2 pr-4 font-medium text-right">Cost (Toman)</th>\n                  <th className="py-2 font-medium text-right">Updated</th>\n                </tr>\n              </thead>\n              <tbody>\n                {data.books.map((b, i) => (\n                  <tr key={b.folder} className="border-b border-border/50 last:border-0">\n                    <td className="py-2.5 pr-4 text-muted-foreground tabular-nums">{i + 1}</td>\n                    <td className="py-2.5 pr-4 font-medium max-w-[260px] truncate">{b.title}</td>\n                    <td className="py-2.5 pr-4 text-muted-foreground">{b.model}</td>\n                    <td className="py-2.5 pr-4 text-right tabular-nums">{fmtInt(b.chapters)}</td>\n                    <td className="py-2.5 pr-4 text-right tabular-nums">{fmtTokens(b.tokens)}</td>\n                    <td className="py-2.5 pr-4 text-right tabular-nums">{fmtDuration(b.duration_seconds)}</td>\n                    <td className="py-2.5 pr-4 text-right tabular-nums font-semibold">{fmtInt(b.cost_toman)}</td>\n                    <td className="py-2.5 text-right text-muted-foreground text-xs whitespace-nowrap">{fmtDate(b.updated_at)}</td>\n                  </tr>\n                ))}\n                <tr className="font-semibold">\n                  <td className="py-3 pr-4" />\n                  <td className="py-3 pr-4">Total</td>\n                  <td className="py-3 pr-4" />\n                  <td className="py-3 pr-4 text-right tabular-nums">{fmtInt(t.chapters)}</td>\n                  <td className="py-3 pr-4 text-right tabular-nums">{fmtTokens(t.tokens)}</td>\n                  <td className="py-3 pr-4 text-right tabular-nums">{fmtDuration(t.duration_seconds)}</td>\n                  <td className="py-3 pr-4 text-right tabular-nums">{fmtInt(grandCost)}</td>\n                  <td className="py-3" />\n                </tr>\n              </tbody>\n            </table>\n          )}\n        </CardContent>\n      </Card>\n\n      <p className="text-[11px] text-muted-foreground">\n        Accuracy note: totals are recomputed from chapter-level token/cost records stored in\n        each book\'s metrics.json (not from the stored book totals). USD figures use the\n        project\'s fixed exchange rate of {fmtInt(data.exchange_rate)} Toman/USD.\n      </p>\n    </div>\n  )\n}\n'

DASHBOARD_ENDPOINT = """@app.get("/api/metrics/dashboard")
async def api_metrics_dashboard(user: User = Depends(get_current_user)) -> dict[str, Any]:
    config = TomeConfig.load_config()
    books: list[dict[str, Any]] = []
    totals = {
        "books": 0, "chapters": 0, "tokens": 0, "prompt_tokens": 0,
        "completion_tokens": 0, "reasoning_tokens": 0,
        "cost_toman": 0.0, "cost_usd": 0.0, "duration_seconds": 0.0,
    }
    by_model: dict[str, dict[str, Any]] = {}
    output_root = Path(config.output_dir)
    if output_root.is_dir():
        for metrics_file in sorted(output_root.glob("*/metrics.json")):
            with contextlib.suppress(Exception):
                data = json.loads(metrics_file.read_text(encoding="utf-8"))
                folder = metrics_file.parent.name
                chapters = data.get("chapters") or []
                prompt_tokens = sum(int(c.get("prompt_tokens") or 0) for c in chapters)
                completion_tokens = sum(int(c.get("completion_tokens") or 0) for c in chapters)
                reasoning_tokens = sum(int(c.get("reasoning_tokens") or 0) for c in chapters)
                total_tokens = prompt_tokens + completion_tokens + reasoning_tokens
                cost_toman = round(sum(float(c.get("cost_toman") or c.get("cost_irt") or 0) for c in chapters), 2)
                if not chapters:
                    total_tokens = int(data.get("total_tokens") or 0)
                    cost_toman = float(data.get("total_cost_toman") or 0)
                cost_usd = round(cost_toman / 70000.0, 6)
                duration = float(data.get("total_duration_seconds") or 0)
                model = str(data.get("model") or "unknown")
                entry = {
                    "folder": folder,
                    "title": data.get("book_title") or folder,
                    "model": model,
                    "chapters": len(chapters) or int(data.get("total_chapters") or 0),
                    "tokens": total_tokens,
                    "cost_toman": cost_toman,
                    "cost_usd": cost_usd,
                    "duration_seconds": duration,
                    "updated_at": metrics_file.stat().st_mtime,
                }
                books.append(entry)
                totals["books"] += 1
                totals["chapters"] += entry["chapters"]
                totals["tokens"] += total_tokens
                totals["prompt_tokens"] += prompt_tokens
                totals["completion_tokens"] += completion_tokens
                totals["reasoning_tokens"] += reasoning_tokens
                totals["cost_toman"] = round(totals["cost_toman"] + cost_toman, 2)
                totals["cost_usd"] = round(totals["cost_usd"] + cost_usd, 6)
                totals["duration_seconds"] = round(totals["duration_seconds"] + duration, 2)
                m = by_model.setdefault(model, {"model": model, "books": 0, "chapters": 0, "tokens": 0, "cost_toman": 0.0})
                m["books"] += 1
                m["chapters"] += entry["chapters"]
                m["tokens"] += total_tokens
                m["cost_toman"] = round(m["cost_toman"] + cost_toman, 2)

    books.sort(key=lambda b: b["cost_toman"], reverse=True)
    credit = None
    with contextlib.suppress(Exception):
        from tome.core.avalai import get_avalai_credit, is_avalai_endpoint

        base_url = getattr(config, "llm_base_url", None) or ""
        api_key = getattr(config, "llm_api_key", None) or ""
        proxy_url = getattr(config, "proxy_url", None)
        if api_key and is_avalai_endpoint(base_url):
            credit = get_avalai_credit(api_key, proxy_url=proxy_url)
    return {
        "totals": totals,
        "books": books,
        "models": sorted(by_model.values(), key=lambda x: x["cost_toman"], reverse=True),
        "credit": credit,
        "exchange_rate": 70000.0,
        "generated_at": time.time(),
    }


"""

API_TYPES = """
export interface DashboardBookEntry {
  folder: string
  title: string
  model: string
  chapters: number
  tokens: number
  cost_toman: number
  cost_usd: number
  duration_seconds: number
  updated_at: number
}

export interface DashboardTotals {
  books: number
  chapters: number
  tokens: number
  prompt_tokens: number
  completion_tokens: number
  reasoning_tokens: number
  cost_toman: number
  cost_usd: number
  duration_seconds: number
}

export interface DashboardModelEntry {
  model: string
  books: number
  chapters: number
  tokens: number
  cost_toman: number
}

export interface MetricsDashboard {
  totals: DashboardTotals
  books: DashboardBookEntry[]
  models: DashboardModelEntry[]
  credit: any
  exchange_rate: number
  generated_at: number
}
"""


def patch_server(src: str) -> tuple[str, int]:
    if "api_metrics_dashboard" in src:
        return src, 0
    anchor = '@app.delete("/api/books/{title}")'
    if anchor not in src:
        anchor = '@app.get("/api/books")\nasync def api_list_books'
    if anchor in src:
        return src.replace(anchor, DASHBOARD_ENDPOINT + anchor, 1), 1
    return src, 0


def patch_api_ts(src: str) -> tuple[str, int]:
    n = 0
    type_anchor = "  logs: Array<{ event: string; data: any; timestamp: number }>\n}\n"
    if type_anchor in src and "MetricsDashboard" not in src:
        src = src.replace(type_anchor, type_anchor + API_TYPES, 1)
        n += 1
    method_anchor = "  static async getBook(title: string): Promise<BookDetail> {\n"
    method = (
        "  static async getMetricsDashboard(): Promise<MetricsDashboard> {\n"
        "    return this.request<MetricsDashboard>('/api/metrics/dashboard')\n"
        "  }\n"
        "\n"
    )
    if method_anchor in src and "getMetricsDashboard" not in src:
        src = src.replace(method_anchor, method + method_anchor, 1)
        n += 1
    return src, (1 if n == 2 else 0)


def patch_sidebar(src: str) -> tuple[str, int]:
    n = 0
    old = "  FileCode2,\n  Settings,\n  ChevronLeft,\n} from 'lucide-react'\n"
    new = "  FileCode2,\n  BarChart3,\n  Settings,\n  ChevronLeft,\n} from 'lucide-react'\n"
    if old in src and "BarChart3," not in src:
        src = src.replace(old, new, 1)
        n += 1
    old = "export type TabType = 'bookshelf' | 'pipeline' | 'tools' | 'prompts' | 'settings'"
    new = "export type TabType = 'bookshelf' | 'pipeline' | 'tools' | 'prompts' | 'metrics' | 'settings'"
    if old in src and "'metrics'" not in src:
        src = src.replace(old, new, 1)
        n += 1
    old = "    { id: 'pipeline' as TabType, label: 'Pipeline Studio', icon: Layers },\n"
    new = old + "    { id: 'metrics' as TabType, label: 'Cost Dashboard', icon: BarChart3 },\n"
    if old in src and "Cost Dashboard" not in src:
        src = src.replace(old, new, 1)
        n += 1
    return src, (1 if n == 3 else 0)


def patch_app(src: str) -> tuple[str, int]:
    n = 0
    old = "import { SettingsView } from './views/SettingsView'\n"
    new = old + "import { MetricsView } from './views/MetricsView'\n"
    if old in src and "import { MetricsView }" not in src:
        src = src.replace(old, new, 1)
        n += 1
    old = "              {currentTab === 'tools' && <ToolsView />}\n"
    new = old + "              {currentTab === 'metrics' && <MetricsView />}\n"
    if old in src and "currentTab === 'metrics'" not in src:
        src = src.replace(old, new, 1)
        n += 1
    return src, (1 if n == 2 else 0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--webdir", default="web/src")
    ap.add_argument("--server", default="src/tome/web/server.py")
    args = ap.parse_args()

    print(f"mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    webdir = Path(args.webdir)

    jobs = [
        ("server.py: GET /api/metrics/dashboard", Path(args.server), patch_server),
        ("api.ts: dashboard types + method", webdir / "api.ts", patch_api_ts),
        ("Sidebar.tsx: Cost Dashboard tab", webdir / "components" / "Sidebar.tsx", patch_sidebar),
        ("App.tsx: route + import", webdir / "App.tsx", patch_app),
    ]
    for name, path, fn in jobs:
        if not path.is_file():
            print(f"  [MISSING] {name} — {path}")
            continue
        src = path.read_text(encoding="utf-8")
        new, n = fn(src)
        if n >= 1:
            status = "OK"
        elif new == src:
            status = "already applied"
        else:
            status = "NOT FOUND"
        print(f"  [{status:>16}] {name}")
        if new != src and n >= 1:
            if args.apply:
                path.with_suffix(path.suffix + ".bak").write_text(src, encoding="utf-8")
                path.write_text(new, encoding="utf-8")
                print(f"         patched {path.name} (.bak saved)")
            else:
                print("         (dry-run)")

    view_path = webdir / "views" / "MetricsView.tsx"
    existing = view_path.read_text(encoding="utf-8") if view_path.is_file() else None
    if existing == METRICS_VIEW:
        print("  [already applied] MetricsView.tsx")
    elif existing is not None:
        print("  [DIFFERS] MetricsView.tsx exists with different content — refusing to overwrite.")
        sys.exit(2)
    elif args.apply:
        view_path.write_text(METRICS_VIEW, encoding="utf-8")
        print("  [OK] wrote MetricsView.tsx")
    else:
        print("  [would write] MetricsView.tsx")

    if args.apply:
        print("\nDone. Rebuild the frontend:  cd web && npm run build")
    else:
        print("\nDry-run only. Re-run with --apply.")


if __name__ == "__main__":
    main()
    