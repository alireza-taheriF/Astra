import Link from 'next/link'
import { AlertTriangle } from 'lucide-react'

import { signInWithGithub } from '@/app/actions/auth'
import { Button } from '@/components/ui/button'
import { GitHubMark } from '@/components/brand-icons'

/**
 * Auth failure surface. Renders a human-readable explanation based on the
 * `reason` query param and offers a re-authentication path. The `repo_scope_denied`
 * case is the primary one: it prompts the user to reconnect and grant repo access.
 */
const REASONS: Record<string, string> = {
  repo_scope_denied:
    'Astra needs the "repo" permission to analyze your repositories, but it was not granted. Please reconnect and approve repository access.',
  missing_provider_token:
    'GitHub did not return an access token, so we could not verify your permissions. Please try connecting again.',
  missing_code: 'The GitHub sign-in did not return an authorization code. Please try again.',
  no_user_after_exchange:
    'We could not load your account after sign-in. Please try connecting again.',
  missing_passport_slug:
    'Your profile was not fully provisioned. Please try connecting again.',
  no_oauth_url: 'We could not start the GitHub sign-in flow. Please try again.',
}

export default async function AuthCodeErrorPage({
  searchParams,
}: {
  searchParams: Promise<{ reason?: string }>
}) {
  const { reason } = await searchParams
  const message =
    (reason && REASONS[reason]) ??
    (reason
      ? `Sign-in failed: ${reason}`
      : 'Something went wrong during sign-in. Please try again.')

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 py-16">
      <div className="rounded-2xl border border-hairline bg-surface/60 p-8">
        <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-full bg-destructive/15">
          <AlertTriangle className="h-5 w-5 text-destructive" />
        </div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">
          Couldn&apos;t complete sign-in
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          {message}
        </p>

        <div className="mt-6 flex flex-col gap-3">
          <form action={signInWithGithub}>
            <Button type="submit" variant="gradient" className="w-full">
              <GitHubMark className="h-4 w-4" />
              Reconnect with GitHub
            </Button>
          </form>
          <Button asChild variant="ghost" className="w-full">
            <Link href="/">Return home</Link>
          </Button>
        </div>
      </div>
    </main>
  )
}
