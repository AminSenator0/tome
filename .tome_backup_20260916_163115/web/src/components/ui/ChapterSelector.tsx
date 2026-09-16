import React, { useMemo } from 'react'
import { Check } from 'lucide-react'
import { Button } from './Button'
import { Input } from './Input'

export interface ChapterItem {
  slug: string
  title?: string
  index?: number
  word_count?: number
  is_translated?: boolean
}

interface ChapterSelectorProps {
  chapters: ChapterItem[]
  value: string
  onChange: (val: string) => void
}

export const ChapterSelector: React.FC<ChapterSelectorProps> = ({
  chapters,
  value,
  onChange,
}) => {
  const selectedSet = useMemo(() => {
    const set = new Set<string>()
    const trimmed = (value || '').trim().toLowerCase()
    if (!trimmed || trimmed === 'all') {
      chapters.forEach((c) => set.add(c.slug))
      return set
    }

    const parts = trimmed.split(/[,;\s]+/).filter(Boolean)
    for (const p of parts) {
      if (p.includes('-') || p.includes('to')) {
        const [startStr, endStr] = p.split(/-|\bto\b/)
        const s = parseInt(startStr, 10)
        const e = parseInt(endStr, 10)
        if (!isNaN(s) && !isNaN(e)) {
          for (let i = Math.min(s, e); i <= Math.max(s, e); i++) {
            if (i >= 1 && i <= chapters.length) {
              set.add(chapters[i - 1].slug)
            }
          }
        }
      } else {
        const num = parseInt(p, 10)
        if (!isNaN(num)) {
          if (num >= 1 && num <= chapters.length) {
            set.add(chapters[num - 1].slug)
          }
        } else {
          const match = chapters.find((c) => c.slug.toLowerCase().includes(p))
          if (match) set.add(match.slug)
        }
      }
    }
    return set
  }, [value, chapters])

  const toggleChapter = (slug: string) => {
    const nextSet = new Set(selectedSet)
    if (nextSet.has(slug)) {
      nextSet.delete(slug)
    } else {
      nextSet.add(slug)
    }

    if (nextSet.size === chapters.length || nextSet.size === 0) {
      onChange(nextSet.size === chapters.length ? 'all' : '')
      return
    }

    const indices: number[] = []
    chapters.forEach((c, idx) => {
      if (nextSet.has(c.slug)) indices.push(idx + 1)
    })

    const ranges: string[] = []
    let start: number | null = null
    let prev: number | null = null

    for (const num of indices) {
      if (start === null) {
        start = num
        prev = num
      } else if (num === prev! + 1) {
        prev = num
      } else {
        ranges.push(start === prev ? `${start}` : `${start}-${prev}`)
        start = num
        prev = num
      }
    }
    if (start !== null) {
      ranges.push(start === prev ? `${start}` : `${start}-${prev}`)
    }

    onChange(ranges.join(', '))
  }

  const selectAll = () => onChange('all')
  const selectFirstN = (n: number) => {
    const end = Math.min(n, chapters.length)
    if (end <= 1) onChange('1')
    else onChange(`1-${end}`)
  }
  const clearAll = () => onChange('')

  return (
    <div className="space-y-4 rounded-2xl border border-border bg-card/60 p-4 text-sm soft-shadow">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <label className="font-semibold text-foreground">
          Chapter Range Selection ({selectedSet.size}/{chapters.length} selected)
        </label>
        <div className="flex flex-wrap items-center gap-2">
          <Button type="button" variant="outline" size="sm" onClick={selectAll} className="h-7 text-xs px-3">
            All
          </Button>
          {chapters.length >= 3 && (
            <Button type="button" variant="outline" size="sm" onClick={() => selectFirstN(3)} className="h-7 text-xs px-3">
              First 3
            </Button>
          )}
          {chapters.length >= 5 && (
            <Button type="button" variant="outline" size="sm" onClick={() => selectFirstN(5)} className="h-7 text-xs px-3">
              First 5
            </Button>
          )}
          <Button type="button" variant="ghost" size="sm" onClick={clearAll} className="h-7 text-xs px-3 text-muted-foreground">
            Clear
          </Button>
        </div>
      </div>

      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Range e.g. all, 5, 1-10, 1,3,5"
        className="font-mono text-sm h-10 rounded-xl"
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 max-h-60 overflow-y-auto custom-scrollbar pt-2">
        {chapters.map((ch, idx) => {
          const isSelected = selectedSet.has(ch.slug)
          const chapterNum = idx + 1
          return (
            <button
              key={ch.slug}
              type="button"
              onClick={() => toggleChapter(ch.slug)}
              className={`flex items-center gap-3 p-2.5 rounded-xl text-left transition-all border ${
                isSelected
                  ? 'border-primary bg-primary/5 text-foreground font-medium'
                  : 'border-border/60 bg-card hover:bg-accent hover:border-border text-muted-foreground'
              }`}
            >
              <div
                className={`h-5 w-5 rounded-full flex items-center justify-center border shrink-0 transition-colors ${
                  isSelected ? 'border-primary bg-primary text-primary-foreground' : 'border-border'
                }`}
              >
                {isSelected && <Check className="h-3.5 w-3.5" />}
              </div>
              <span className="font-mono text-xs text-muted-foreground shrink-0">#{chapterNum}</span>
              <span className="truncate flex-1 text-sm">{ch.title || ch.slug}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
