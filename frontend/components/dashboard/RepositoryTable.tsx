import * as React from 'react'

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import type { LibrarySignal, RepositoryRow } from '@/lib/types'

export interface RepositoryTableProps {
  repositories: RepositoryRow[]
}

/**
 * Selects the top-N libraries from a repo's capability summary, ranked by the
 * engine's weight (heaviest signal first).
 */
function topLibraries(
  signals: Record<string, LibrarySignal> | undefined,
  n: number
): string[] {
  if (!signals) return []
  return Object.entries(signals)
    .sort(([, a], [, b]) => b.weight - a.weight)
    .slice(0, n)
    .map(([name]) => name)
}

export function RepositoryTable({ repositories }: RepositoryTableProps) {
  if (repositories.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-hairline bg-surface/40 px-6 py-12 text-center">
        <p className="text-sm text-muted-foreground">
          No repositories analyzed yet. They appear here once the capability
          engine has processed your connected GitHub account.
        </p>
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-hairline bg-surface/60">
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="pl-4">Repository</TableHead>
            <TableHead>Language</TableHead>
            <TableHead className="pr-4">Signals</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {repositories.map((repo) => {
            const libs = topLibraries(
              repo.astra_capability_summary?.library_signals,
              2
            )
            return (
              <TableRow key={repo.id}>
                <TableCell className="pl-4 font-medium text-foreground">
                  <span className="font-mono text-sm">{repo.repo_full_name}</span>
                  {repo.is_fork ? (
                    <Badge variant="outline" className="ml-2 align-middle">
                      fork
                    </Badge>
                  ) : null}
                </TableCell>
                <TableCell>
                  {repo.primary_language ? (
                    <span className="text-sm text-muted-foreground">
                      {repo.primary_language}
                    </span>
                  ) : (
                    <span className="text-sm text-muted-foreground/50">—</span>
                  )}
                </TableCell>
                <TableCell className="pr-4">
                  <div className="flex flex-wrap gap-1.5">
                    {libs.length > 0 ? (
                      libs.map((lib) => (
                        <Badge key={lib} variant="accent" className="font-mono">
                          {lib}
                        </Badge>
                      ))
                    ) : (
                      <span className="text-sm text-muted-foreground/50">—</span>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}
