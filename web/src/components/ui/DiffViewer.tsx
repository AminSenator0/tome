import React, { useState } from 'react'
import { Check, X, Copy, Columns, Rows, CheckCheck } from 'lucide-react'
import { Button } from './Button'
import { Badge } from './Badge'
import { useI18n } from '../../lib/i18n'

interface DiffItem {
  id: number
  oldText: string
  newText: string
  status: 'accepted' | 'rejected' | 'pending'
}

interface DiffViewerProps {
  original: string
  modified: string
  changes?: Record<string, number>
  onCommit?: (finalText: string) => void
}

interface WordDiffPart {
  value: string
  added?: boolean
  removed?: boolean
}

function computeWordDiff(
  oldStr: string,
  newStr: string
): { oldParts: WordDiffPart[]; newParts: WordDiffPart[]; changedWordsCount: number } {
  const tokenize = (s: string) => s.split(/(\s+|[،؛.؟!«»"':;()]+)/).filter(Boolean)
  const a = tokenize(oldStr)
  const b = tokenize(newStr)

  const m = a.length
  const n = b.length

  if (m > 500 || n > 500) {
    return {
      oldParts: [{ value: oldStr, removed: true }],
      newParts: [{ value: newStr, added: true }],
      changedWordsCount: 1,
    }
  }

  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0))
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (a[i - 1] === b[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1])
      }
    }
  }

  let i = m
  let j = n
  const aMatched = new Set<number>()
  const bMatched = new Set<number>()

  while (i > 0 && j > 0) {
    if (a[i - 1] === b[j - 1]) {
      aMatched.add(i - 1)
      bMatched.add(j - 1)
      i--
      j--
    } else if (dp[i - 1][j] >= dp[i][j - 1]) {
      i--
    } else {
      j--
    }
  }

  let changes = 0
  const oldParts: WordDiffPart[] = []
  for (let idx = 0; idx < m; idx++) {
    const isMatch = aMatched.has(idx)
    const isWhitespace = /^\s+$/.test(a[idx])
    if (!isMatch && !isWhitespace) changes++
    oldParts.push({
      value: a[idx],
      removed: !isMatch && !isWhitespace,
    })
  }

  const newParts: WordDiffPart[] = []
  for (let idx = 0; idx < n; idx++) {
    const isMatch = bMatched.has(idx)
    const isWhitespace = /^\s+$/.test(b[idx])
    newParts.push({
      value: b[idx],
      added: !isMatch && !isWhitespace,
    })
  }

  return { oldParts, newParts, changedWordsCount: changes }
}

export const DiffViewer: React.FC<DiffViewerProps> = ({
  original,
  modified,
  changes,
  onCommit,
}) => {
  const { t } = useI18n()
  const [copied, setCopied] = useState(false)

  // Parse lines into interactive diff segments
  const origLines = original.split('\n')
  const modLines = modified.split('\n')
  const maxLen = Math.max(origLines.length, modLines.length)

  const initialItems: DiffItem[] = []
  for (let i = 0; i < maxLen; i++) {
    const o = origLines[i] ?? ''
    const m = modLines[i] ?? ''
    if (o !== m) {
      initialItems.push({
        id: i,
        oldText: o,
        newText: m,
        status: 'pending',
      })
    }
  }

  const [items, setItems] = useState<DiffItem[]>(initialItems)

  const handleDecision = (id: number, decision: 'accepted' | 'rejected') => {
    setItems((prev) =>
      prev.map((it) => (it.id === id ? { ...it, status: decision } : it))
    )
  }

  const handleAcceptAll = () => {
    setItems((prev) => prev.map((it) => ({ ...it, status: 'accepted' })))
  }

  const handleRejectAll = () => {
    setItems((prev) => prev.map((it) => ({ ...it, status: 'rejected' })))
  }

  // Construct current combined text based on decisions
  const buildFinalText = () => {
    const lines = [...origLines]
    items.forEach((it) => {
      if (it.status === 'accepted') {
        lines[it.id] = it.newText
      } else {
        lines[it.id] = it.oldText
      }
    })
    return lines.join('\n')
  }

  const handleCopy = () => {
    const finalTxt = buildFinalText()
    navigator.clipboard.writeText(finalTxt)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
    if (onCommit) onCommit(finalTxt)
  }

  return (
    <div className="rounded-3xl bg-card overflow-hidden text-xs border-0">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 bg-secondary/50">
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold text-foreground">{t('diff.title')}</span>
          <Badge variant="success">
            {t('diff.changes', { n: items.length })}
          </Badge>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" variant="secondary" onClick={handleAcceptAll}>
            <CheckCheck className="h-3.5 w-3.5 mr-1" />
            <span>{t('diff.acceptAll')}</span>
          </Button>
          <Button size="sm" variant="secondary" onClick={handleRejectAll}>
            <X className="h-3.5 w-3.5 mr-1" />
            <span>{t('diff.rejectAll')}</span>
          </Button>
          <Button size="sm" variant="primary" onClick={handleCopy}>
            {copied ? <Check className="h-3.5 w-3.5 mr-1" /> : <Copy className="h-3.5 w-3.5 mr-1" />}
            <span>{copied ? t('diff.copied') : t('diff.copyFinal')}</span>
          </Button>
        </div>
      </div>

      <div className="p-4 space-y-2 max-h-[460px] overflow-y-auto custom-scrollbar">
        {items.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground text-xs">
            {t('diff.noDiff')}
          </div>
        ) : (
          items.map((item) => {
            const { oldParts, newParts, changedWordsCount } = computeWordDiff(item.oldText, item.newText)

            return (
              <div
                key={item.id}
                className={`p-3.5 rounded-2xl transition-all ${
                  item.status === 'accepted'
                    ? 'bg-success-light/60 ring-1 ring-success/30'
                    : item.status === 'rejected'
                    ? 'bg-destructive/10 opacity-60'
                    : 'bg-secondary/40'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-2 font-persian text-sm flex-1" dir="rtl">
                    {/* Before with highlighted changed words */}
                    {item.oldText && (
                      <div className="text-muted-foreground text-xs flex items-baseline gap-2 flex-wrap">
                        <span className="text-[10px] font-sans font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-destructive/15 text-destructive select-none shrink-0">
                          قبل
                        </span>
                        <div className="leading-relaxed flex-1">
                          {oldParts.map((p, pIdx) =>
                            p.removed ? (
                              <mark
                                key={pIdx}
                                className="bg-destructive/25 text-destructive line-through font-semibold px-1 py-0.5 rounded mx-0.5"
                                title="کلمه قبل از ویرایش"
                              >
                                {p.value}
                              </mark>
                            ) : (
                              <span key={pIdx} className="opacity-70">
                                {p.value}
                              </span>
                            )
                          )}
                        </div>
                      </div>
                    )}

                    {/* After with highlighted normalized words */}
                    {item.newText && (
                      <div className="text-foreground flex items-baseline gap-2 flex-wrap">
                        <span className="text-[10px] font-sans font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-success/20 text-success select-none shrink-0">
                          بعد
                        </span>
                        <div className="leading-relaxed font-medium flex-1">
                          {newParts.map((p, pIdx) =>
                            p.added ? (
                              <mark
                                key={pIdx}
                                className="bg-success/25 text-success font-bold px-1.5 py-0.5 rounded mx-0.5 shadow-2xs"
                                title="کلمه ویرایش‌شده"
                              >
                                {p.value}
                              </mark>
                            ) : (
                              <span key={pIdx}>{p.value}</span>
                            )
                          )}
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-1.5 shrink-0 pt-1">
                    <button
                      type="button"
                      onClick={() => handleDecision(item.id, 'accepted')}
                      className={`h-8 w-8 rounded-full flex items-center justify-center transition-colors cursor-pointer border-0 ${
                        item.status === 'accepted'
                          ? 'bg-success text-white'
                          : 'bg-secondary hover:bg-success-light text-success'
                      }`}
                      title={t('diff.acceptTitle')}
                    >
                      <Check className="h-4 w-4 stroke-[2]" />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDecision(item.id, 'rejected')}
                      className={`h-8 w-8 rounded-full flex items-center justify-center transition-colors cursor-pointer border-0 ${
                        item.status === 'rejected'
                          ? 'bg-destructive text-white'
                          : 'bg-secondary hover:bg-destructive/20 text-destructive'
                      }`}
                      title={t('diff.rejectTitle')}
                    >
                      <X className="h-4 w-4 stroke-[2]" />
                    </button>
                  </div>
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}

