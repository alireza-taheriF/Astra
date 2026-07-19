'use server'

import { headers } from 'next/headers'
import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'

/**
 * Initiates GitHub OAuth sign-in.
 *
 * Requests the `read:user` and `repo` scopes. `read:user` is needed to read the
 * authenticated profile (username -> passport_slug); `repo` is needed so the
 * backend can analyze the user's repositories for capability scoring.
 *
 * Supabase returns a URL to GitHub's consent screen; we redirect the browser
 * there. After consent, GitHub sends the user back to /auth/callback with a
 * code, which the callback route exchanges for a session.
 */
export async function signInWithGithub() {
  const supabase = await createClient()

  // Derive the origin from the incoming request so the redirect works across
  // local dev, Vercel preview deployments, and production without hardcoding.
  const headerStore = await headers()
  const origin = headerStore.get('origin') ?? headerStore.get('x-forwarded-host')
  const proto = headerStore.get('x-forwarded-proto') ?? 'https'
  const resolvedOrigin =
    origin && origin.startsWith('http') ? origin : `${proto}://${origin}`

  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: 'github',
    options: {
      scopes: 'read:user repo',
      redirectTo: `${resolvedOrigin}/auth/callback`,
    },
  })

  if (error) {
    redirect(
      `/auth/auth-code-error?reason=${encodeURIComponent(error.message)}`
    )
  }

  if (data.url) {
    redirect(data.url)
  }

  // No error and no URL should be unreachable, but fail closed rather than
  // silently returning to a page that assumes a session exists.
  redirect('/auth/auth-code-error?reason=no_oauth_url')
}

/**
 * Signs the current user out and returns them to the home page.
 */
export async function signOut() {
  const supabase = await createClient()
  await supabase.auth.signOut()
  redirect('/')
}
