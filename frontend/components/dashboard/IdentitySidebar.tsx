'use client'

import * as React from 'react'
import { Menu } from 'lucide-react'
import { toast } from 'sonner'

import { cn } from '@/lib/utils'
import type { IdentityProvider, IdentityRow } from '@/lib/types'
import { IdentityBadge } from '@/components/IdentityBadge'
import { signInWithGithub } from '@/app/actions/auth'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'

// The full set of providers Astra supports; identities present in the DB are
// merged over this list so unlinked providers render a "Connect" affordance.
const ALL_PROVIDERS: IdentityProvider[] = ['github', 'arxiv', 'huggingface']

export interface IdentitySidebarProps {
  identities: IdentityRow[]
  /** Whether the passport viewer owns this profile (can connect identities). */
  isOwner: boolean
}

function IdentityList({ identities, isOwner }: IdentitySidebarProps) {
  const byProvider = new Map(identities.map((i) => [i.provider, i]))

  function handleConnect(provider: IdentityProvider) {
    if (!isOwner) return
    if (provider === 'github') {
      // Re-run GitHub OAuth (also (re)links the identity server-side).
      void signInWithGithub()
      return
    }
    toast('Connection coming soon', {
      description: `Linking ${provider} isn't available yet.`,
    })
  }

  return (
    <div className="flex flex-col gap-2.5">
      {ALL_PROVIDERS.map((provider) => {
        const row = byProvider.get(provider)
        return (
          <IdentityBadge
            key={provider}
            provider={provider}
            username={row?.provider_username}
            verified={row?.verified ?? false}
            connected={Boolean(row)}
            onConnect={isOwner ? handleConnect : undefined}
          />
        )
      })}
      {!isOwner ? (
        <p className="mt-1 px-1 text-xs text-muted-foreground">
          Connected identities are managed by the profile owner.
        </p>
      ) : null}
    </div>
  )
}

/**
 * Connected-identities panel. Static on desktop (left rail); collapses into a
 * Shadcn Sheet triggered by a menu button on mobile.
 */
export function IdentitySidebar(props: IdentitySidebarProps) {
  return (
    <>
      {/* Desktop: static sidebar */}
      <aside className="hidden w-full lg:block">
        <div className="sticky top-8">
          <h2 className="mb-4 text-xs font-medium uppercase tracking-tight text-muted-foreground">
            Connected identities
          </h2>
          <IdentityList {...props} />
        </div>
      </aside>

      {/* Mobile: Sheet trigger */}
      <div className="lg:hidden">
        <Sheet>
          <SheetTrigger
            className={cn(
              'inline-flex items-center gap-2 rounded-lg border border-hairline bg-surface px-3 py-2 text-sm font-medium text-foreground transition-colors hover:border-primary/40'
            )}
          >
            <Menu className="h-4 w-4" />
            Identities
          </SheetTrigger>
          <SheetContent side="left">
            <SheetHeader>
              <SheetTitle>Connected identities</SheetTitle>
            </SheetHeader>
            <div className="mt-6">
              <IdentityList {...props} />
            </div>
          </SheetContent>
        </Sheet>
      </div>
    </>
  )
}
