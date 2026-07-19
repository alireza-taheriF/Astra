import { NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'

/**
 * GitHub OAuth callback for Astra.
 *
 * Flow:
 *   1. Exchange the `code` query param for a Supabase session (sets auth cookies).
 *   2. Verify GitHub actually granted the `repo` scope. GitHub lets users
 *      deselect scopes on the consent screen, and the OAuth exchange still
 *      succeeds — so we probe the granted scopes directly and bounce the user
 *      to a re-auth prompt if `repo` is missing.
 *   3. Resolve the user's passport_slug and redirect to /passport/[slug].
 */
export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url)
  const code = searchParams.get('code')

  // GitHub can return an error directly (e.g. user cancelled consent).
  const oauthError = searchParams.get('error')
  if (oauthError) {
    const description =
      searchParams.get('error_description') ?? oauthError
    return NextResponse.redirect(
      `${origin}/auth/auth-code-error?reason=${encodeURIComponent(description)}`
    )
  }

  if (!code) {
    return NextResponse.redirect(
      `${origin}/auth/auth-code-error?reason=missing_code`
    )
  }

  const supabase = await createClient()

  const { data, error } = await supabase.auth.exchangeCodeForSession(code)
  if (error) {
    return NextResponse.redirect(
      `${origin}/auth/auth-code-error?reason=${encodeURIComponent(error.message)}`
    )
  }

  const providerToken = data.session?.provider_token

  // Verify the `repo` scope was actually granted. GitHub exposes the scopes
  // bound to a token via the `X-OAuth-Scopes` response header on any API call.
  if (providerToken) {
    const granted = await getGithubTokenScopes(providerToken)
    const hasRepoScope =
      granted.includes('repo') ||
      // A granted parent scope implies its children; `repo` has no broader
      // parent, but guard against GitHub returning only fine-grained aliases.
      granted.some((s) => s === 'repo' || s.startsWith('repo:'))

    if (!hasRepoScope) {
      // Sign the partial session out so the next attempt starts clean, then
      // send the user to a page that re-initiates OAuth with correct perms.
      await supabase.auth.signOut()
      return NextResponse.redirect(
        `${origin}/auth/auth-code-error?reason=repo_scope_denied`
      )
    }
  } else {
    // No provider token means we cannot verify or use GitHub on the user's
    // behalf. Treat as a failed connection rather than proceeding blindly.
    await supabase.auth.signOut()
    return NextResponse.redirect(
      `${origin}/auth/auth-code-error?reason=missing_provider_token`
    )
  }

  // Resolve the passport slug created by the handle_new_user() trigger.
  const {
    data: { user },
  } = await supabase.auth.getUser()

  if (!user) {
    return NextResponse.redirect(
      `${origin}/auth/auth-code-error?reason=no_user_after_exchange`
    )
  }

  const { data: profile, error: profileError } = await supabase
    .from('users')
    .select('passport_slug')
    .eq('id', user.id)
    .single()

  if (profileError || !profile?.passport_slug) {
    return NextResponse.redirect(
      `${origin}/auth/auth-code-error?reason=missing_passport_slug`
    )
  }

  return NextResponse.redirect(`${origin}/passport/${profile.passport_slug}`)
}

/**
 * Returns the OAuth scopes bound to a GitHub token by inspecting the
 * `X-OAuth-Scopes` header GitHub attaches to authenticated REST responses.
 */
async function getGithubTokenScopes(token: string): Promise<string[]> {
  const response = await fetch('https://api.github.com/user', {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
    },
    // Never cache an authenticated identity probe.
    cache: 'no-store',
  })

  const scopeHeader = response.headers.get('x-oauth-scopes')
  if (!scopeHeader) {
    return []
  }

  return scopeHeader
    .split(',')
    .map((s) => s.trim())
    .filter((s) => s.length > 0)
}
