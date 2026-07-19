'use client'

import * as React from 'react'
import { useFormStatus } from 'react-dom'
import { ArrowRight, Loader2 } from 'lucide-react'

import { signInWithGithub } from '@/app/actions/auth'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

function SubmitButton({ className }: { className?: string }) {
  const { pending } = useFormStatus()
  return (
    <Button
      type="submit"
      variant="gradient"
      size="lg"
      disabled={pending}
      className={cn('group', className)}
    >
      {pending ? (
        <>
          <Loader2 className="animate-spin" />
          Connecting to GitHub…
        </>
      ) : (
        <>
          Generate My Astra Score
          <ArrowRight className="transition-transform duration-200 group-hover:translate-x-0.5" />
        </>
      )}
    </Button>
  )
}

/**
 * Landing CTA. Submits to the `signInWithGithub` Server Action (Phase 1),
 * which redirects the browser into GitHub's OAuth consent screen.
 */
export function GenerateScoreButton({ className }: { className?: string }) {
  return (
    <form action={signInWithGithub}>
      <SubmitButton className={className} />
    </form>
  )
}
