import { notFound } from 'next/navigation'
import type { Metadata } from 'next'

import { createClient } from '@/lib/supabase/server'
import type {
  CapabilityScoreRow,
  DisplaySubscore,
  IdentityRow,
  RepositoryRow,
  SubscoreBreakdown,
} from '@/lib/types'
import { tierForScore } from '@/lib/tiers'
import { ScoreHeader } from '@/components/dashboard/ScoreHeader'
import { SubscoreCard } from '@/components/dashboard/SubscoreCard'
import { RepositoryTable } from '@/components/dashboard/RepositoryTable'
import { IdentitySidebar } from '@/components/dashboard/IdentitySidebar'
import { CopyBadgeButton } from '@/components/dashboard/CopyBadgeButton'
import { SiteFooter } from '@/components/marketing/SiteFooter'

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>
}): Promise<Metadata> {
  const { slug } = await params
  return {
    title: `${slug} · Astra Passport`,
    description: `Astra capability passport for @${slug}.`,
  }
}

// Human-facing labels for the three headline subscores.
const SUBSCORE_LABELS: Record<string, string> = {
  ml_infra: 'ML Infra',
  systems: 'Systems',
  research_alignment: 'Research Alignment',
}

/**
 * Assembles display-ready subscores from the current + historical score rows.
 * The sparkline trend is built from each row's stored subscore value over time
 * (oldest → newest); percentile is taken from the current row.
 */
function buildSubscores(
  current: SubscoreBreakdown,
  history: CapabilityScoreRow[]
): DisplaySubscore[] {
  const keys = ['ml_infra', 'systems', 'research_alignment']
  // history is newest-first from the query; reverse for oldest → newest trend.
  const chronological = [...history].reverse()

  return keys.map((key) => {
    const value = Number(current[key] ?? 0)
    const trend = chronological
      .map((row) => row.subscore_breakdown?.[key])
      .filter((v): v is number => typeof v === 'number')

    return {
      key,
      label: SUBSCORE_LABELS[key] ?? key,
      value,
      // Percentile per-subscore isn't stored separately; approximate from the
      // subscore value so the card reads sensibly (0–100 → percentile).
      percentile: value > 0 ? Math.min(99, Math.round(value)) : null,
      trend: trend.length >= 2 ? trend : [value, value],
    }
  })
}

export default async function PassportPage({
  params,
}: {
  params: Promise<{ slug: string }>
}) {
  const { slug } = await params
  const supabase = await createClient()

  // Profile — RLS hides private profiles from non-owners, yielding null.
  const { data: profile } = await supabase
    .from('users')
    .select('id, display_name, passport_slug, is_public')
    .eq('passport_slug', slug)
    .maybeSingle()

  if (!profile) {
    notFound()
  }

  // Determine ownership (drives the "Connect" affordances in the sidebar).
  const {
    data: { user },
  } = await supabase.auth.getUser()
  const isOwner = user?.id === profile.id

  // Score history (newest first): row 0 is current, row 1 is prior month.
  const { data: scoreRows } = await supabase
    .from('capability_scores')
    .select(
      'astra_score, percentile, score_version, subscore_breakdown, is_current, computed_at'
    )
    .eq('user_id', profile.id)
    .order('computed_at', { ascending: false })
    .limit(12)

  const history = (scoreRows ?? []) as CapabilityScoreRow[]
  const current = history.find((r) => r.is_current) ?? history[0] ?? null

  // Identities for the sidebar.
  const { data: identityRows } = await supabase
    .from('identities')
    .select('id, provider, provider_username, verified')
    .eq('user_id', profile.id)

  const identities = (identityRows ?? []) as IdentityRow[]

  // Repositories under this user's identities (RLS-scoped).
  const identityIds = identities.map((i) => i.id)
  let repositories: RepositoryRow[] = []
  if (identityIds.length > 0) {
    const { data: repoRows } = await supabase
      .from('repositories')
      .select(
        'id, repo_full_name, is_fork, primary_language, astra_capability_summary, last_analyzed_at'
      )
      .in('identity_id', identityIds)
      .order('last_analyzed_at', { ascending: false, nullsFirst: false })
    repositories = (repoRows ?? []) as RepositoryRow[]
  }

  const displayName = profile.display_name ?? profile.passport_slug

  // Delta: current − previous (previous = first non-current row, if any).
  const previous = history.find((r) => !r.is_current) ?? null
  const delta =
    current && previous ? current.astra_score - previous.astra_score : null

  const subscores = current
    ? buildSubscores(current.subscore_breakdown, history)
    : []

  return (
    <div className="flex min-h-screen flex-col">
      {/* Top bar */}
      <header className="border-b border-hairline">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div>
            <h1 className="text-lg font-semibold tracking-tight text-foreground">
              {displayName}
            </h1>
            <p className="text-sm text-muted-foreground">@{profile.passport_slug}</p>
          </div>
          <CopyBadgeButton slug={profile.passport_slug} />
        </div>
      </header>

      <main className="mx-auto grid w-full max-w-6xl flex-1 grid-cols-1 gap-10 px-6 py-10 lg:grid-cols-[260px_1fr]">
        {/* Sidebar */}
        <IdentitySidebar identities={identities} isOwner={isOwner} />

        {/* Main panel */}
        <div className="flex flex-col gap-12">
          {current ? (
            <>
              <section className="rounded-2xl border border-hairline bg-surface/60 p-8">
                <ScoreHeader
                  score={current.astra_score}
                  percentile={current.percentile}
                  delta={delta}
                />
              </section>

              <section>
                <h2 className="mb-4 text-sm font-medium uppercase tracking-tight text-muted-foreground">
                  Subscore breakdown
                </h2>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {subscores.map((s) => (
                    <SubscoreCard key={s.key} subscore={s} />
                  ))}
                </div>
              </section>
            </>
          ) : (
            <section className="rounded-2xl border border-dashed border-hairline bg-surface/40 p-12 text-center">
              <p className="text-2xl font-semibold tracking-tight text-foreground">
                Score pending
              </p>
              <p className="mx-auto mt-2 max-w-sm text-sm text-muted-foreground">
                We haven&apos;t finished analyzing {displayName}&apos;s
                repositories yet. Check back shortly.
              </p>
            </section>
          )}

          <section>
            <h2 className="mb-4 text-sm font-medium uppercase tracking-tight text-muted-foreground">
              Analyzed repositories
            </h2>
            <RepositoryTable repositories={repositories} />
          </section>
        </div>
      </main>

      <SiteFooter />
    </div>
  )
}
