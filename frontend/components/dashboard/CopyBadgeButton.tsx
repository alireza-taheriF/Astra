'use client'

import * as React from 'react'
import { Check, Copy } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'

export interface CopyBadgeButtonProps {
  slug: string
}

/**
 * Copies the exact README badge markdown to the clipboard and confirms with a
 * Sonner toast. The markdown format is fixed by the badge contract.
 */
export function CopyBadgeButton({ slug }: CopyBadgeButtonProps) {
  const [copied, setCopied] = React.useState(false)

  const markdown = `[![Astra Score](https://astra.dev/api/v1/badge/${slug}.svg)](https://astra.dev/passport/${slug})`

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(markdown)
      setCopied(true)
      toast.success('Badge markdown copied', {
        description: 'Paste it into your README to show your Astra Score.',
      })
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      toast.error('Could not copy to clipboard', {
        description: 'Your browser blocked clipboard access. Copy it manually.',
      })
    }
  }

  return (
    <Button variant="outline" size="sm" onClick={handleCopy} aria-live="polite">
      {copied ? <Check className="text-emerald-400" /> : <Copy />}
      {copied ? 'Copied' : 'Copy Badge Markdown'}
    </Button>
  )
}
