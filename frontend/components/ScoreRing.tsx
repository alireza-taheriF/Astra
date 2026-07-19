'use client'

import * as React from 'react'
import { motion, useInView, useReducedMotion } from 'framer-motion'

import { cn } from '@/lib/utils'
import { tierForScore } from '@/lib/tiers'

export type ScoreRingSize = 'sm' | 'md' | 'lg'

export interface ScoreRingProps {
  /** Raw score (e.g. 2140). */
  score: number
  /** Denominator for the ring fill. Defaults to 3000. */
  maxScore?: number
  /** Tier label rendered under the score (e.g. "Distinguished Engineer"). */
  tier: string
  /** Preset diameter. */
  size?: ScoreRingSize
  /** When true, animate the stroke on scroll into view via Framer Motion. */
  animated?: boolean
  className?: string
}

interface SizeSpec {
  diameter: number
  stroke: number
  scoreClass: string
  tierClass: string
}

const SIZE_SPECS: Record<ScoreRingSize, SizeSpec> = {
  sm: {
    diameter: 96,
    stroke: 6,
    scoreClass: 'text-xl font-semibold',
    tierClass: 'text-[10px]',
  },
  md: {
    diameter: 160,
    stroke: 9,
    scoreClass: 'text-4xl font-bold',
    tierClass: 'text-xs',
  },
  lg: {
    diameter: 240,
    stroke: 12,
    scoreClass: 'text-6xl font-bold',
    tierClass: 'text-sm',
  },
}

/**
 * Circular score ring rendered as pure SVG.
 *
 * The track is a faint full circle; the value arc is a gradient stroke whose
 * `stroke-dashoffset` is animated from empty to its target when `animated` is
 * set and the ring scrolls into view. A unique gradient id per instance keeps
 * multiple rings on one page valid.
 */
export function ScoreRing({
  score,
  maxScore = 3000,
  tier,
  size = 'md',
  animated = false,
  className,
}: ScoreRingProps) {
  const spec = SIZE_SPECS[size]
  const { diameter, stroke } = spec
  const radius = (diameter - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const pct = Math.max(0, Math.min(1, score / maxScore))
  const targetOffset = circumference * (1 - pct)

  const tierColor = tierForScore(score).color

  // Stable unique id for this instance's gradient (no hydration mismatch).
  const gradientId = React.useId().replace(/:/g, '')

  const ref = React.useRef<SVGSVGElement>(null)
  const inView = useInView(ref, { once: true, amount: 0.5 })
  const prefersReduced = useReducedMotion()
  const shouldAnimate = animated && !prefersReduced

  const center = diameter / 2

  return (
    <div
      className={cn('relative inline-flex items-center justify-center', className)}
      style={{ width: diameter, height: diameter }}
    >
      <svg
        ref={ref}
        width={diameter}
        height={diameter}
        viewBox={`0 0 ${diameter} ${diameter}`}
        className="-rotate-90"
        role="img"
        aria-label={`Astra score ${score} of ${maxScore}, tier ${tier}`}
      >
        <defs>
          <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#6366F1" />
            <stop offset="100%" stopColor="#A855F7" />
          </linearGradient>
        </defs>

        {/* Track */}
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="hsl(var(--border))"
          strokeWidth={stroke}
        />

        {/* Value arc */}
        <motion.circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke={`url(#${gradientId})`}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: shouldAnimate ? circumference : targetOffset }}
          animate={{
            strokeDashoffset:
              !animated || inView || prefersReduced ? targetOffset : circumference,
          }}
          transition={{ duration: 1.4, ease: [0.16, 1, 0.3, 1] }}
        />
      </svg>

      {/* Centered label */}
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
        <span className={cn('leading-none tracking-tight text-foreground', spec.scoreClass)}>
          {Math.round(score)}
        </span>
        <span
          className={cn(
            'mt-1 max-w-[80%] font-medium uppercase tracking-tight',
            spec.tierClass
          )}
          style={{ color: tierColor }}
        >
          {tier}
        </span>
      </div>
    </div>
  )
}
