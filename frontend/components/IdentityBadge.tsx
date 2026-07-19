'use client'

import * as React from 'react'
import { BadgeCheck, Plus } from 'lucide-react'

import { cn } from '@/lib/utils'
import type { IdentityProvider } from '@/lib/types'
import { GitHubMark, ArxivMark, HuggingFaceMark } from '@/components/brand-icons'

export interface IdentityBadgeProps {
  provider: IdentityProvider
  /** Handle to show when connected (e.g. GitHub username). */
  username?: string | null
  /** Verification / connection state. */
  verified: boolean
  /** Whether an identity row exists at all. When false, render a Connect CTA. */
  connected: boolean
  /** Invoked when the user clicks Connect on an unlinked provider. */
  onConnect?: (provider: IdentityProvider) => void
  className?: string
}

const PROVIDER_META: Record<
  IdentityProvider,
  { label: string; Icon: React.ComponentType<{ className?: string }> }
> = {
  github: { label: 'GitHub', Icon: GitHubMark },
  arxiv: { label: 'arXiv', Icon: ArxivMark },
  huggingface: { label: 'Hugging Face', Icon: HuggingFaceMark },
}

/**
 * A connected external identity row: provider icon + handle with a verified
 * checkmark, or a "Connect" affordance when the provider is not yet linked.
 */
export function IdentityBadge({
  provider,
  username,
  verified,
  connected,
  onConnect,
  className,
}: IdentityBadgeProps) {
  const { label, Icon } = PROVIDER_META[provider]

  return (
    <div
      className={cn(
        'flex items-center justify-between gap-3 rounded-lg border border-hairline bg-surface/60 px-3 py-2.5 transition-colors',
        connected ? 'hover:border-primary/40' : 'opacity-90',
        className
      )}
    >
      <div className="flex min-w-0 items-center gap-2.5">
        <span
          className={cn(
            'flex h-8 w-8 shrink-0 items-center justify-center rounded-md',
            connected ? 'bg-secondary text-foreground' : 'bg-secondary/50 text-muted-foreground'
          )}
        >
          <Icon className="h-4 w-4" />
        </span>
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-foreground">{label}</p>
          {connected && username ? (
            <p className="truncate text-xs text-muted-foreground">@{username}</p>
          ) : (
            <p className="truncate text-xs text-muted-foreground">Not connected</p>
          )}
        </div>
      </div>

      {connected ? (
        verified ? (
          <span className="flex shrink-0 items-center gap-1 text-xs font-medium text-emerald-400">
            <BadgeCheck className="h-4 w-4" />
            Verified
          </span>
        ) : (
          <span className="shrink-0 text-xs font-medium text-amber-400">Pending</span>
        )
      ) : (
        <button
          type="button"
          onClick={() => onConnect?.(provider)}
          className="flex shrink-0 items-center gap-1 rounded-md border border-hairline px-2.5 py-1 text-xs font-medium text-foreground transition-colors hover:border-primary/50 hover:bg-secondary/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Plus className="h-3.5 w-3.5" />
          Connect
        </button>
      )}
    </div>
  )
}
