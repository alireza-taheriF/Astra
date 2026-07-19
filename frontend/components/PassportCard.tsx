'use client'

import * as React from 'react'
import { motion } from 'framer-motion'

import { cn } from '@/lib/utils'
import { ScoreRing } from '@/components/ScoreRing'
import { SubscoreBar } from '@/components/SubscoreBar'
import { Card } from '@/components/ui/card'

export interface PassportCardSubscore {
  label: string
  value: number
  percentile?: number | null
}

export interface PassportCardProps {
  displayName: string
  handle: string
  score: number
  maxScore?: number
  tier: string
  subscores: PassportCardSubscore[]
  /** Animate ring + bars on scroll into view. */
  animated?: boolean
  className?: string
}

/**
 * The showcase Astra Passport card. Used with dummy data on the landing page
 * and reusable anywhere a compact passport summary is needed.
 */
export function PassportCard({
  displayName,
  handle,
  score,
  maxScore = 3000,
  tier,
  subscores,
  animated = false,
  className,
}: PassportCardProps) {
  return (
    <motion.div
      initial={animated ? { opacity: 0, y: 24 } : false}
      whileInView={animated ? { opacity: 1, y: 0 } : undefined}
      viewport={{ once: true, amount: 0.3 }}
      transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
      className={cn('w-full', className)}
    >
      <Card className="relative overflow-hidden p-6 sm:p-8">
        {/* Ambient accent glow */}
        <div
          aria-hidden
          className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-accent-gradient opacity-20 blur-3xl"
        />

        <div className="flex flex-col items-center gap-8 sm:flex-row sm:items-center sm:gap-10">
          <div className="flex shrink-0 flex-col items-center gap-3">
            <ScoreRing
              score={score}
              maxScore={maxScore}
              tier={tier}
              size="md"
              animated={animated}
            />
          </div>

          <div className="w-full min-w-0 flex-1">
            <div className="mb-5 text-center sm:text-left">
              <h3 className="text-xl font-semibold tracking-tight text-foreground">
                {displayName}
              </h3>
              <p className="text-sm text-muted-foreground">@{handle}</p>
            </div>

            <div className="flex flex-col gap-4">
              {subscores.map((s) => (
                <SubscoreBar
                  key={s.label}
                  label={s.label}
                  value={s.value}
                  percentile={s.percentile}
                  animated={animated}
                />
              ))}
            </div>
          </div>
        </div>
      </Card>
    </motion.div>
  )
}
