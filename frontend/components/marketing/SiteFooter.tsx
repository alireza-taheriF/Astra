import * as React from 'react'

import { GitHubMark } from '@/components/brand-icons'

const REPO_URL = 'https://github.com/astra-dev/astra'

/**
 * Minimal dark footer: brand mark, tagline, and a GitHub repo link.
 */
export function SiteFooter() {
  return (
    <footer className="border-t border-hairline">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-6 py-10 sm:flex-row">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold tracking-tight text-foreground">
            Astra
          </span>
          <span className="text-sm text-muted-foreground">
            · Built for engineers who ship
          </span>
        </div>

        <a
          href={REPO_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <GitHubMark className="h-4 w-4" />
          GitHub
        </a>
      </div>
    </footer>
  )
}
