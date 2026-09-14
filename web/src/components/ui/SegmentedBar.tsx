import React from 'react'

interface SegmentedBarProps {
  totalSegments?: number
  percent?: number
  activeCount?: number
  totalCount?: number
  className?: string
  color?: 'white' | 'amber' | 'emerald'
}

export const SegmentedBar: React.FC<SegmentedBarProps> = ({
  totalSegments = 26,
  percent,
  activeCount,
  totalCount,
  className = '',
  color = 'white',
}) => {
  let effectivePercent = 0
  if (percent !== undefined) {
    effectivePercent = Math.max(0, Math.min(100, percent))
  } else if (activeCount !== undefined && totalCount && totalCount > 0) {
    effectivePercent = Math.min(100, Math.max(0, (activeCount / totalCount) * 100))
  }

  const filledSegments = Math.round((effectivePercent / 100) * totalSegments)

  const activeBg =
    color === 'amber'
      ? 'bg-amber-400'
      : color === 'emerald'
      ? 'bg-emerald-400'
      : 'bg-zinc-200'

  return (
    <div className={`flex items-center gap-[3px] overflow-hidden ${className}`}>
      {Array.from({ length: totalSegments }).map((_, idx) => {
        const isFilled = idx < filledSegments
        return (
          <div
            key={idx}
            className={`h-3 w-2 rounded-[1.5px] transition-colors shrink-0 ${
              isFilled
                ? activeBg
                : 'bg-zinc-900 border border-zinc-800/80'
            }`}
          />
        )
      })}
    </div>
  )
}
