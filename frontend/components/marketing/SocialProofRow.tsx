import * as React from 'react'

import { cn } from '@/lib/utils'
import { tierForScore } from '@/lib/tiers'

interface PlaceholderPassport {
  score: number
  tier: string
}

// Anonymized placeholders implying scale. No real user data.
const PLACEHOLDERS: PlaceholderPassport[] = [
  { score: 2610, tier: 'Grandmaster' },
  { score: 2180, tier: 'Master' },
  { score: 1740, tier: 'Expert' },
  { score: 2440, tier: 'Grandmaster' },
  { score: 1980, tier: 'Expert' },
  { score: 2260, tier: 'Master' },
  { score: 1560, tier: 'Apprentice' },
  { score: 2090, tier: 'Master' },
]

function PlaceholderBadge({ score, tier }: PlaceholderPassport) {
  const color = tierForScore(score).color
  return (
    <div className="flex w-56 shrink-0 items-center gap-3 rounded-xl border border-hairline bg-surface/70 px-4 py-3">
      {/* Blurred avatar placeholder */}
      <div className="relative h-11 w-11 shrink-0">
        <div className="h-full w-full rounded-full bg-gradient-to-br from-secondary to-hairline blur-[1px]" />
        <div
          className="absolute inset-0 rounded-full ring-2"
          style={{ boxShadow: `inset 0 0 0 2px ${color}55` }}
        />
      </div>
      <div className="min-w-0 flex-1">
        {/* Skeleton name line */}
        <div className="mb-2 h-2.5 w-24 rounded-full bg-secondary" />
        <div className="flex items-center gap-2">
          <span
            className="text-sm font-semibold tabular-nums"
            style={{ color }}
          >
            {score}
          </span>
          <span className="truncate text-xs text-muted-foreground">{tier}</span>
        </div>
      </div>
    </div>
  )
}

/**
 * Horizontally scrolling row of anonymized passport badges implying scale.
 * The track is duplicated so the CSS marquee loops seamlessly.
 */
export function SocialProofRow({ className }: { className?: string }) {
  const track = [...PLACEHOLDERS, ...PLACEHOLDERS]
  return (
    <div className={cn('relative w-full overflow-hidden', className)}>
      {/* Edge fades */}
      <div className="pointer-events-none absolute inset-y-0 left-0 z-10 w-24 bg-gradient-to-r from-background to-transparent" />
      <div className="pointer-events-none absolute inset-y-0 right-0 z-10 w-24 bg-gradient-to-l from-background to-transparent" />

      <div className="flex w-max gap-4 animate-marquee hover:[animation-play-state:paused]">
        {track.map((p, i) => (
          <PlaceholderBadge key={i} score={p.score} tier={p.tier} />
        ))}
      </div>
    </div>
  )
}
