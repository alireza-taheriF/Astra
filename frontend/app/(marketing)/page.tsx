import type { Metadata } from 'next'

import { GenerateScoreButton } from '@/components/marketing/GenerateScoreButton'
import { SocialProofRow } from '@/components/marketing/SocialProofRow'
import { SiteFooter } from '@/components/marketing/SiteFooter'
import { PassportCard } from '@/components/PassportCard'

export const metadata: Metadata = {
  title: 'Astra — Your code is your resume',
  description:
    'Astra turns your real engineering work into a verifiable capability score. Skip the LinkedIn noise.',
}

// Static showcase data for the example passport (no real user).
const DEMO_SUBSCORES = [
  { label: 'ML Infra', value: 88, percentile: 94 },
  { label: 'Systems', value: 76, percentile: 89 },
  { label: 'Research Alignment', value: 71, percentile: 82 },
]

export default function MarketingPage() {
  return (
    <div className="flex min-h-screen flex-col">
      {/* ---- Hero ---- */}
      <section className="relative mx-auto flex w-full max-w-6xl flex-col items-center px-6 pb-20 pt-28 text-center sm:pt-36">
        <span className="mb-6 inline-flex items-center gap-2 rounded-full border border-hairline bg-surface/60 px-3 py-1 text-xs font-medium text-muted-foreground">
          <span className="h-1.5 w-1.5 rounded-full bg-accent-gradient" />
          Capability verification for engineers
        </span>

        <h1 className="max-w-3xl text-balance text-5xl font-bold tracking-tighter text-foreground sm:text-7xl">
          Your code is your{' '}
          <span className="text-gradient">resume.</span>
        </h1>

        <p className="mt-6 max-w-xl text-pretty text-lg leading-relaxed text-muted-foreground">
          Recruiters skim keywords. Astra reads your commits. We analyze the
          real engineering signal in your repositories and turn it into a
          verifiable score — so you can bypass the LinkedIn noise and let your
          work speak.
        </p>

        <div className="mt-9">
          <GenerateScoreButton />
        </div>

        <p className="mt-4 text-xs text-muted-foreground">
          Connects via GitHub OAuth · read-only analysis
        </p>

        {/* ---- Live example passport ---- */}
        <div className="mt-20 w-full max-w-2xl">
          <PassportCard
            displayName="Distinguished Engineer"
            handle="astra-demo"
            score={2140}
            tier="Distinguished Engineer"
            subscores={DEMO_SUBSCORES}
            animated
          />
        </div>
      </section>

      {/* ---- Social proof ---- */}
      <section className="mx-auto w-full max-w-6xl px-6 py-16">
        <p className="mb-8 text-center text-sm font-medium uppercase tracking-tight text-muted-foreground">
          Trusted by engineers who let the work talk
        </p>
        <SocialProofRow />
      </section>

      {/* ---- Value strip ---- */}
      <section className="mx-auto grid w-full max-w-5xl grid-cols-1 gap-6 px-6 py-16 sm:grid-cols-3">
        {[
          {
            title: 'Signal, not keywords',
            body: 'AST-level analysis of real code — library depth, complexity, and craft. No self-reported skills.',
          },
          {
            title: 'Verifiable by anyone',
            body: 'Every passport is backed by public repositories and an embeddable badge you can drop in any README.',
          },
          {
            title: 'Yours to share',
            body: 'A single link and an SVG badge. Recruiters see the score; you keep control of what stays private.',
          },
        ].map((f) => (
          <div
            key={f.title}
            className="rounded-xl border border-hairline bg-surface/60 p-6 text-left"
          >
            <h3 className="text-base font-semibold tracking-tight text-foreground">
              {f.title}
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              {f.body}
            </p>
          </div>
        ))}
      </section>

      {/* ---- Closing CTA ---- */}
      <section className="mx-auto w-full max-w-3xl px-6 py-24 text-center">
        <h2 className="text-balance text-3xl font-bold tracking-tighter text-foreground sm:text-4xl">
          Ready to see your score?
        </h2>
        <p className="mx-auto mt-4 max-w-md text-pretty text-muted-foreground">
          It takes one click. We analyze your public repositories and generate
          your Astra Passport in minutes.
        </p>
        <div className="mt-8 flex justify-center">
          <GenerateScoreButton />
        </div>
      </section>

      <SiteFooter />
    </div>
  )
}
