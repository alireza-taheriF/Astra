import * as React from 'react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Sparkline } from '@/components/dashboard/Sparkline'
import type { DisplaySubscore } from '@/lib/types'

export interface SubscoreCardProps {
  subscore: DisplaySubscore
}

function ordinal(n: number): string {
  const v = n % 100
  if (v >= 11 && v <= 13) return `${n}th`
  switch (n % 10) {
    case 1:
      return `${n}st`
    case 2:
      return `${n}nd`
    case 3:
      return `${n}rd`
    default:
      return `${n}th`
  }
}

/**
 * A single subscore breakdown card: label, current value, percentile, and a
 * mini SVG sparkline of the recent trend.
 */
export function SubscoreCard({ subscore }: SubscoreCardProps) {
  const { label, value, percentile, trend } = subscore

  return (
    <Card className="transition-colors hover:border-primary/30">
      <CardHeader className="pb-2">
        <CardTitle>{label}</CardTitle>
      </CardHeader>
      <CardContent className="flex items-end justify-between gap-4">
        <div>
          <div className="text-3xl font-bold tracking-tight text-foreground tabular-nums">
            {Math.round(value)}
            <span className="ml-0.5 text-base font-normal text-muted-foreground">
              /100
            </span>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {percentile != null
              ? `${ordinal(Math.round(percentile))} percentile`
              : 'Percentile pending'}
          </p>
        </div>
        <Sparkline points={trend} className="shrink-0" />
      </CardContent>
    </Card>
  )
}
