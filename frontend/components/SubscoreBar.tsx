'use client'

import * as React from 'react'
import { motion, useInView, useReducedMotion } from 'framer-motion'

import { cn } from '@/lib/utils'

export interface SubscoreBarProps {
  /** Category label, e.g. "ML Infra". */
  label: string
  /** Fill value 0–100. */
  value: number
  /** Optional percentile shown on the right, e.g. 92 -> "92nd percentile". */
  percentile?: number | null
  /** Animate the fill on scroll into view. */
  animated?: boolean
  className?: string
}

function ordinalSuffix(n: number): string {
  const v = n % 100
  if (v >= 11 && v <= 13) return 'th'
  switch (n % 10) {
    case 1:
      return 'st'
    case 2:
      return 'nd'
    case 3:
      return 'rd'
    default:
      return 'th'
  }
}

/**
 * Horizontal gradient progress bar with a label and optional percentile text.
 */
export function SubscoreBar({
  label,
  value,
  percentile,
  animated = false,
  className,
}: SubscoreBarProps) {
  const clamped = Math.max(0, Math.min(100, value))
  const ref = React.useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true, amount: 0.6 })
  const prefersReduced = useReducedMotion()
  const fill = !animated || inView || prefersReduced ? clamped : 0

  return (
    <div className={cn('w-full', className)} ref={ref}>
      <div className="mb-1.5 flex items-baseline justify-between gap-2">
        <span className="text-sm font-medium text-foreground">{label}</span>
        {percentile != null ? (
          <span className="text-xs tabular-nums text-muted-foreground">
            {Math.round(percentile)}
            {ordinalSuffix(Math.round(percentile))} percentile
          </span>
        ) : (
          <span className="text-xs tabular-nums text-muted-foreground">
            {Math.round(clamped)}
            <span className="text-muted-foreground/60">/100</span>
          </span>
        )}
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-secondary">
        <motion.div
          className="h-full rounded-full bg-accent-gradient"
          initial={{ width: animated && !prefersReduced ? '0%' : `${fill}%` }}
          animate={{ width: `${fill}%` }}
          transition={{ duration: 1.1, ease: [0.16, 1, 0.3, 1] }}
        />
      </div>
    </div>
  )
}
