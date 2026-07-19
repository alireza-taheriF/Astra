import * as React from 'react'

import { cn } from '@/lib/utils'

export interface SparklineProps {
  /** Ordered data points, oldest → newest. */
  points: number[]
  width?: number
  height?: number
  className?: string
}

/**
 * Lightweight trend sparkline drawn as an SVG polyline — no charting library.
 * Normalizes the series into the viewport and uses the accent gradient stroke.
 */
export function Sparkline({
  points,
  width = 96,
  height = 32,
  className,
}: SparklineProps) {
  const gradientId = React.useId().replace(/:/g, '')

  if (points.length < 2) {
    // Degenerate series: draw a flat midline so the card never looks broken.
    return (
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className={cn('overflow-visible', className)}
        aria-hidden
      >
        <line
          x1={0}
          y1={height / 2}
          x2={width}
          y2={height / 2}
          stroke="hsl(var(--border))"
          strokeWidth={2}
          strokeLinecap="round"
        />
      </svg>
    )
  }

  const min = Math.min(...points)
  const max = Math.max(...points)
  const range = max - min || 1
  const pad = 2

  const coords = points.map((p, i) => {
    const x = (i / (points.length - 1)) * (width - pad * 2) + pad
    const y = height - pad - ((p - min) / range) * (height - pad * 2)
    return [x, y] as const
  })

  const linePath = coords.map(([x, y]) => `${x},${y}`).join(' ')
  const areaPath =
    `${pad},${height - pad} ` +
    coords.map(([x, y]) => `${x},${y}`).join(' ') +
    ` ${width - pad},${height - pad}`
  const [lastX, lastY] = coords[coords.length - 1]

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={cn('overflow-visible', className)}
      role="img"
      aria-label="Score trend"
    >
      <defs>
        <linearGradient id={`stroke-${gradientId}`} x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#6366F1" />
          <stop offset="100%" stopColor="#A855F7" />
        </linearGradient>
        <linearGradient id={`fill-${gradientId}`} x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#A855F7" stopOpacity="0.25" />
          <stop offset="100%" stopColor="#A855F7" stopOpacity="0" />
        </linearGradient>
      </defs>

      <polygon points={areaPath} fill={`url(#fill-${gradientId})`} />
      <polyline
        points={linePath}
        fill="none"
        stroke={`url(#stroke-${gradientId})`}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx={lastX} cy={lastY} r={2.5} fill="#A855F7" />
    </svg>
  )
}
