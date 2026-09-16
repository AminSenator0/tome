import React, { useState, useEffect, useCallback } from 'react'
import {
  RefreshCw,
  Wallet,
  Coins,
  BookOpen,
  Layers,
  BarChart3,
  TrendingUp,
  PieChart,
} from 'lucide-react'
import { Api, MetricsDashboard } from '../api'
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { useI18n } from '../lib/i18n'

const getLocale = () => {
  try { return localStorage.getItem('tome_lang') === 'fa' ? 'fa-IR' : 'en-US' } catch { return 'en-US' }
}
const fmtInt = (n: number) => new Intl.NumberFormat(getLocale(), { maximumFractionDigits: 0 }).format(n)

const fmtTokens = (n: number) => {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return fmtInt(n)
}

const fmtDuration = (sec: number) => {
  if (sec <= 0) return '—'
  const h = sec / 3600
  if (h >= 1) return `${h.toFixed(1)}h`
  return `${Math.round(sec / 60)}m`
}

const fmtDate = (ts: number) => {
  if (!ts) return '—'
  return new Date(ts * 1000).toLocaleString(getLocale(), {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const TOKEN_COLORS = ['#38bdf8', '#34d399', '#fbbf24']
const MODEL_COLORS = ['#818cf8', '#38bdf8', '#34d399', '#fbbf24', '#f472b6', '#a78bfa']

interface DonutSegment {
  label: string
  value: number
  color: string
}

const Donut: React.FC<{ segments: DonutSegment[]; size?: number; centerLabel: string; centerValue: string }> = ({
  segments,
  size = 150,
  centerLabel,
  centerValue,
}) => {
  const total = segments.reduce((a, s) => a + s.value, 0) || 1
  const r = size / 2 - 14
  const c = 2 * Math.PI * r
  let offset = 0
  return (
    <div className="flex items-center gap-6">
      <div className="relative shrink-0">
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" className="stroke-secondary" strokeWidth={14} />
          {segments.map((s) => {
            const frac = s.value / total
            const dash = Math.max(0, frac * c - 2)
            const el = (
              <circle
                key={s.label}
                cx={size / 2}
                cy={size / 2}
                r={r}
                fill="none"
                stroke={s.color}
                strokeWidth={14}
                strokeDasharray={`${dash} ${c - dash}`}
                strokeDashoffset={-offset}
                className="transition-all duration-700"
              />
            )
            offset += frac * c
            return el
          })}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-lg font-bold tabular-nums">{centerValue}</span>
          <span className="text-[10px] text-muted-foreground uppercase tracking-wide">{centerLabel}</span>
        </div>
      </div>
      <div className="space-y-2.5 min-w-0">
        {segments.map((s, i) => (
          <div key={s.label} className="flex items-center gap-2 text-xs">
            <span className="h-2.5 w-2.5 rounded-full shrink-0" style={{ background: s.color }} />
            <span className="text-muted-foreground w-20 truncate">{s.label}</span>
            <span className="font-semibold tabular-nums">{fmtTokens(s.value)}</span>
            <span className="text-muted-foreground tabular-nums">({((s.value / total) * 100).toFixed(1)}%)</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export const MetricsView: React.FC = () => {
  const { t: tx, formatNumber, formatDate } = useI18n()
  const [data, setData] = useState<MetricsDashboard | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [rateInput, setRateInput] = useState('')
  const [savingRate, setSavingRate] = useState(false)

  const toggleAutoRate = async () => {
    setSavingRate(true)
    try {
      await (Api.updateConfig as any)({ exchange_rate_auto: !data?.rate_info?.auto })
      await load()
    } catch (err: any) {
      alert(err?.message || tx('metrics.toggleFail'))
    } finally {
      setSavingRate(false)
    }
  }


  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await Api.getMetricsDashboard()
      setData(res)
    } catch (err: any) {
      setError(err?.message || tx('metrics.loadFail'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (data) setRateInput(String(Math.round(data.current_exchange_rate)))
  }, [data])

  const saveRate = async () => {
    const val = Number(rateInput)
    if (!val || val <= 0) return
    setSavingRate(true)
    try {
      await (Api.updateConfig as any)({ exchange_rate: val })
      await load()
    } catch (err: any) {
      alert(err?.message || tx('metrics.saveFail'))
    } finally {
      setSavingRate(false)
    }
  }

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center h-64 text-muted-foreground">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  if (error && !data) {
    return (
      <div className="space-y-4">
        <p className="text-destructive">{error}</p>
        <Button size="sm" onClick={load}>{tx('common.retry')}</Button>
      </div>
    )
  }

  if (!data) return null

  const t = data.totals
  const grandCost = t.cost_toman || 0
  const avgPerChapter = t.chapters > 0 ? grandCost / t.chapters : 0
  const avgTokensPerChapter = t.chapters > 0 ? t.tokens / t.chapters : 0
  const costPer1M = t.tokens > 0 ? (grandCost / t.tokens) * 1_000_000 : 0
  const completionShare = t.tokens > 0 ? ((t.completion_tokens + t.reasoning_tokens) / t.tokens) * 100 : 0
  const topBooks = data.books.slice(0, 8)
  const maxBookCost = topBooks.length > 0 ? topBooks[0].cost_toman : 1
  const grandTokens = t.tokens || 1

  const creditNumber = (() => {
    const c: any = data.credit
    if (!c || typeof c !== 'object') return null
    const keys = ['remaining_credit', 'credit', 'balance', 'remaining', 'amount', 'total_credit']
    for (const k of keys) {
      const v = c[k]
      if (typeof v === 'number') return v
      if (v && typeof v === 'object') {
        for (const k2 of keys) {
          if (typeof v[k2] === 'number') return v[k2] as number
        }
      }
    }
    return null
  })()

  const miniStat = (label: string, value: string, sub: string) => (
    <div className="rounded-2xl bg-secondary/30 p-4">
      <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">{label}</p>
      <p className="mt-1 text-lg font-bold tabular-nums">{value}</p>
      <p className="text-[11px] text-muted-foreground tabular-nums">{sub}</p>
    </div>
  )

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-primary" />
            {tx('nav.metrics')}
          </h1>
          <p className="text-sm text-muted-foreground">
            {tx('metrics.updated', { date: fmtDate(data.generated_at) })}
          </p>
        </div>
        <Button size="sm" className="gap-1.5" onClick={load} loading={loading}>
          <RefreshCw className="h-3.5 w-3.5" />
          <span>{tx('common.refresh')}</span>
        </Button>
      </div>

      {/* Hero + minis */}
      <Card className="rounded-3xl border-0 overflow-hidden">
        <CardContent className="p-0">
          <div className="bg-gradient-to-br from-primary/15 via-primary/5 to-transparent p-6 lg:p-8">
            <div className="flex flex-wrap items-end justify-between gap-6">
              <div>
                <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-widest flex items-center gap-1.5">
                  <Coins className="h-3.5 w-3.5" /> {tx('metrics.totalSpent')}
                </p>
                <p className="mt-2 text-4xl lg:text-5xl font-bold tabular-nums tracking-tight">
                  {fmtInt(grandCost)}
                  <span className="text-base font-medium text-muted-foreground ms-2">{tx('metrics.toman')}</span>
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground tabular-nums">
                  <span>{tx('metrics.usdAtTranslation', { usd: t.cost_usd.toFixed(2) })}</span>
                  <span className="inline-flex items-center gap-1 text-foreground">
                    <TrendingUp className="h-3.5 w-3.5 text-primary" />
                    {tx('metrics.todaysRate', { n: fmtInt(t.cost_toman_current) })}
                  </span>
                </div>
              </div>
              {creditNumber !== null && (
                <div className="rounded-2xl bg-background/70 backdrop-blur px-5 py-4">
                  <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-widest flex items-center gap-1.5">
                    <Wallet className="h-3.5 w-3.5" /> {tx('metrics.walletBalance')}
                  </p>
                  <p className="mt-1 text-2xl font-bold tabular-nums">{fmtInt(creditNumber)}</p>
                  <p className="text-[11px] text-muted-foreground">{tx('metrics.tomanRemaining')}</p>
                </div>
              )}
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3 p-5">
            {miniStat(tx('metrics.tokensProcessed'), fmtTokens(t.tokens), tx('metrics.output', { pct: completionShare.toFixed(0) }))}
            {miniStat(tx('metrics.books'), fmtInt(t.books), tx('metrics.translatedSub'))}
            {miniStat(tx('metrics.chapters'), fmtInt(t.chapters), tx('metrics.translatedSub'))}
            {miniStat(tx('metrics.avgCostPerChapter'), fmtInt(avgPerChapter), tx('metrics.toman'))}
            {miniStat(tx('metrics.avgTokensPerChapter'), fmtTokens(avgTokensPerChapter), tx('metrics.tokensLabel'))}
            {miniStat(tx('metrics.runtime'), fmtDuration(t.duration_seconds), tx('metrics.tPer1M', { n: fmtInt(costPer1M) }))}
          </div>
        </CardContent>
      </Card>

      {/* Charts row */}
      <div className="grid lg:grid-cols-3 gap-5">
        <Card className="rounded-3xl border-0">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <PieChart className="h-4 w-4 text-primary" /> {tx('metrics.tokenComposition')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Donut
              centerValue={fmtTokens(t.tokens)}
              centerLabel={tx('metrics.tokensLabel')}
              segments={[
                { label: tx('metrics.prompt'), value: t.prompt_tokens, color: TOKEN_COLORS[0] },
                { label: tx('metrics.completion'), value: t.completion_tokens, color: TOKEN_COLORS[1] },
                { label: tx('metrics.reasoning'), value: t.reasoning_tokens, color: TOKEN_COLORS[2] },
              ]}
            />
          </CardContent>
        </Card>

        <Card className="rounded-3xl border-0">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-primary" /> {tx('metrics.costByModel')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {data.models.length === 0 ? (
              <p className="text-sm text-muted-foreground py-8 text-center">{tx('metrics.noData')}</p>
            ) : (
              <div className="space-y-4">
                {data.models.map((m, i) => {
                  const share = grandCost > 0 ? (m.cost_toman / grandCost) * 100 : 0
                  const color = MODEL_COLORS[i % MODEL_COLORS.length]
                  return (
                    <div key={m.model} title={tx('metrics.modelTitle', { n: fmtInt(m.chapters), t: fmtTokens(m.tokens) })}>
                      <div className="flex items-center justify-between text-xs mb-1.5">
                        <span className="font-medium truncate max-w-[55%]">{m.model}</span>
                        <span className="text-muted-foreground tabular-nums">
                          {fmtInt(m.cost_toman)} <span className="text-muted-foreground/70">({share.toFixed(1)}%)</span>
                        </span>
                      </div>
                      <div className="h-2 rounded-full bg-secondary overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-700"
                          style={{ width: `${Math.max(2, share)}%`, background: color }}
                        />
                      </div>
                      <p className="text-[10px] text-muted-foreground mt-1 tabular-nums">
                        {tx('metrics.modelSub', { books: fmtInt(m.books), chapters: fmtInt(m.chapters), tokens: fmtTokens(m.tokens) })}
                      </p>
                    </div>
                  )
                })}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="rounded-3xl border-0">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Layers className="h-4 w-4 text-primary" /> {tx('metrics.topBooks')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {topBooks.length === 0 ? (
              <p className="text-sm text-muted-foreground py-8 text-center">{tx('metrics.noData')}</p>
            ) : (
              <div className="flex items-end gap-2 h-44 pt-2">
                {topBooks.map((b, i) => {
                  const h = Math.max(6, (b.cost_toman / maxBookCost) * 100)
                  return (
                    <div key={b.folder} className="flex-1 flex flex-col items-center gap-1.5 min-w-0 group">
                      <span className="text-[10px] tabular-nums text-muted-foreground opacity-0 group-hover:opacity-100 transition whitespace-nowrap">
                        {fmtInt(b.cost_toman)}
                      </span>
                      <div
                        className="w-full rounded-t-lg bg-primary/70 group-hover:bg-primary transition-all duration-500"
                        style={{ height: `${h}%` }}
                        title={tx('metrics.bookTitle', { title: b.title, cost: fmtInt(b.cost_toman) })}
                      />
                      <span className="text-[9px] text-muted-foreground truncate max-w-full w-full text-center" title={b.title}>
                        {b.title.length > 10 ? `${b.title.slice(0, 9)}…` : b.title}
                    </span>
                    </div>
                  )
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Books table */}
      <Card className="rounded-3xl border-0">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <BookOpen className="h-4 w-4 text-primary" /> {tx('metrics.booksTitle')} <span className="text-muted-foreground font-normal">({fmtInt(data.books.length)})</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          {data.books.length === 0 ? (
            <p className="text-sm text-muted-foreground py-10 text-center">
              {tx('metrics.noMetrics')}
            </p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted-foreground text-[11px] uppercase tracking-wider border-b border-border">
                  <th className="py-2.5 pr-3 font-medium w-8">#</th>
                  <th className="py-2.5 pr-4 font-medium">{tx('metrics.colBook')}</th>
                  <th className="py-2.5 pr-4 font-medium text-right">{tx('metrics.colChapters')}</th>
                  <th className="py-2.5 pr-4 font-medium text-right">{tx('metrics.colTokens')}</th>
                  <th className="py-2.5 pr-4 font-medium text-right">{tx('metrics.colShare')}</th>
                  <th className="py-2.5 pr-4 font-medium text-right">{tx('metrics.colCost')}</th>
                  <th className="py-2.5 pr-4 font-medium text-right">{tx('metrics.colCurrentRate')}</th>
                  <th className="py-2.5 font-medium text-right">{tx('metrics.colUpdated')}</th>
                </tr>
              </thead>
              <tbody>
                {data.books.map((b, i) => {
                  const share = grandCost > 0 ? (b.cost_toman / grandCost) * 100 : 0
                  const shareTokens = b.tokens / grandTokens
                  return (
                    <tr key={b.folder} className="border-b border-border/40 last:border-0 hover:bg-secondary/20 transition-colors">
                      <td className="py-3 pr-3 text-muted-foreground tabular-nums">{i + 1}</td>
                      <td className="py-3 pr-4 max-w-[280px]">
                        <p className="font-medium truncate">{b.title}</p>
                        <p className="text-[11px] text-muted-foreground truncate">{b.model}</p>
                      </td>
                      <td className="py-3 pr-4 text-right tabular-nums">{fmtInt(b.chapters)}</td>
                      <td className="py-3 pr-4 text-right tabular-nums">
                        {fmtTokens(b.tokens)}
                        <div className="h-1 w-16 rounded-full bg-secondary overflow-hidden ms-auto mt-1">
                          <div className="h-full bg-sky-400 rounded-full" style={{ width: `${Math.min(100, shareTokens * 100)}%` }} />
                        </div>
                      </td>
                      <td className="py-3 pr-4 text-right tabular-nums text-muted-foreground w-20">{share.toFixed(1)}%</td>
                      <td className="py-3 pr-4 text-right tabular-nums font-semibold">{fmtInt(b.cost_toman)}</td>
                      <td className="py-3 pr-4 text-right tabular-nums text-muted-foreground">{fmtInt(b.cost_toman_current)}</td>
                      <td className="py-3 text-right text-muted-foreground text-xs whitespace-nowrap">{fmtDate(b.updated_at)}</td>
                    </tr>
                  )
                })}
                <tr className="font-semibold bg-secondary/20">
                  <td className="py-3 pr-3 rounded-s-2xl" />
                  <td className="py-3 pr-4">{tx('metrics.total')}</td>
                  <td className="py-3 pr-4 text-right tabular-nums">{fmtInt(t.chapters)}</td>
                  <td className="py-3 pr-4 text-right tabular-nums">{fmtTokens(t.tokens)}</td>
                  <td className="py-3 pr-4" />
                  <td className="py-3 pr-4 text-right tabular-nums">{fmtInt(grandCost)}</td>
                  <td className="py-3 pr-4 text-right tabular-nums text-muted-foreground">{fmtInt(t.cost_toman_current)}</td>
                  <td className="py-3 rounded-e-2xl" />
                </tr>
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>

      {/* Rate editor */}
      <Card className="rounded-3xl border-0">
        <CardContent className="p-5 flex flex-wrap items-end gap-4">
          <div>
            <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">{tx('metrics.exchangeRate')}</p>
            <input
              type="number"
              className="mt-1.5 h-10 w-52 rounded-2xl bg-secondary/40 px-4 text-sm font-semibold tabular-nums outline-none focus:ring-2 ring-primary/40 transition"
              disabled={Boolean(data?.rate_info?.auto)}
              value={rateInput}
              onChange={(e) => setRateInput(e.target.value)}
            />
          </div>
          <Button size="sm" className="h-10 px-5" onClick={saveRate} loading={savingRate}>{tx('metrics.saveRate')}</Button>
          <Button
            size="sm"
            className="h-10 px-4"
            onClick={toggleAutoRate}
            loading={savingRate}
          >
            {data?.rate_info?.auto ? tx('metrics.autoRateOn') : tx('metrics.autoRateOff')}
          </Button>
          {data?.rate_info?.auto && data.rate_info.auto_at ? (
            <span className="text-[11px] text-muted-foreground self-center tabular-nums">
              {tx('metrics.lastFetch', { date: fmtDate(data.rate_info.auto_at) })}
            </span>
          ) : null}
          <p className="text-[11px] text-muted-foreground self-center max-w-md leading-relaxed">
            {tx('metrics.rateNote')}
          </p>
        </CardContent>
      </Card>

      {data.credit && creditNumber === null && (
        <Card className="rounded-3xl border-0">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Wallet className="h-4 w-4 text-primary" /> {tx('metrics.providerCredit')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="text-xs bg-secondary/40 rounded-2xl p-4 overflow-x-auto custom-scrollbar">
              {JSON.stringify(data.credit, null, 2)}
            </pre>
          </CardContent>
        </Card>
      )}

      <p className="text-[11px] text-muted-foreground leading-relaxed px-1">
        {tx('metrics.accuracyNote', { rate: fmtInt(data.current_exchange_rate) })}
      </p>
    </div>
  )
}
