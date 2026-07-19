import * as React from 'react'
import { ArrowUpRight, Minus } from 'lucide-react'

import { cn } from '@/lib/utils'
import { ScoreRing } from '@/components/ScoreRing'
import { tierForScore } from '@/lib/tiers'

export interface ScoreHeaderProps {
  score: number
  maxScore?: number
  percentile: number | null
  /** current − previous; null when there is no prior score to compare. */
  delta: number | null
}

/**
 * Large score display with the animated ring and a month-over-month delta
 * indicator (green when up, greyed when flat/unknown).
 */
export function ScoreHeader({
  score,
  maxScore = 3000,
  percentile,
  delta,
}: ScoreHeaderProps) {
  const tier = tierForScore(score)
  const isPositive = delta != null && delta > 0
  const isNegative = delta != null && delta < 0

  return (
    <div className="flex flex-col items-center gap-6 sm:flex-row sm:items-center sm:gap-10">
      <ScoreRing
        score={score}
        maxScore={maxScore}
        tier={tier.label}
        size="lg"
        animated
      />

      <div className="text-center sm:text-left">
        <p className="text-xs font-medium uppercase tracking-tight text-muted-foreground">
          Astra Capability Score
        </p>
        <div className="mt-1 flex items-center justify-center gap-3 sm:justify-start">
          <span
            className="text-lg font-semibold tracking-tight"
            style={{ color: tier.color }}
          >
            {tier.label}
          </span>
        </div>

        <div className="mt-3 flex items-center justify-center gap-3 sm:justify-start">
          {/* Delta chip */}
          <span
            className={cn(
              'inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium tabular-nums',
              isPositive && 'bg-emerald-500/15 text-emerald-400',
              isNegative && 'bg-destructive/15 text-destructive',
              !isPositive && !isNegative && 'bg-secondary text-muted-foreground'
            )}
          >
            {isPositive ? (
              <ArrowUpRight className="h-3.5 w-3.5" />
            ) : (
              <Minus className="h-3.5 w-3.5" />
            )}
            {delta != null && delta !== 0
              ? `${isPositive ? '+' : ''}${Math.round(delta)} this month`
              : 'No change this month'}
          </span>

          {percentile != null ? (
            <span className="text-xs text-muted-foreground">
              Top {Math.max(1, Math.round(100 - percentile))}% of engineers
            </span>
          ) : null}
        </div>
      </div>
    </div>
  )
}
