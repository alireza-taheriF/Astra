import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'

/**
 * Server-side Supabase client for Astra.
 *
 * Safe to use in Server Components, Server Actions, and Route Handlers. It
 * bridges Supabase's auth cookies to Next.js's async cookie store so that
 * sessions established via OAuth are read and refreshed on the server.
 *
 * Note: when called from a Server Component, cookie writes are not permitted
 * by Next.js. We swallow the resulting error — session refresh cookies will be
 * re-issued by middleware or the next Server Action / Route Handler that can
 * legally set them.
 */
export async function createClient() {
  const cookieStore = await cookies()

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

  if (!supabaseUrl || !supabaseAnonKey) {
    throw new Error(
      'Missing Supabase env vars: NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY must be set.'
    )
  }

  return createServerClient(supabaseUrl, supabaseAnonKey, {
    cookies: {
      getAll() {
        return cookieStore.getAll()
      },
      setAll(cookiesToSet) {
        try {
          cookiesToSet.forEach(({ name, value, options }) => {
            cookieStore.set(name, value, options)
          })
        } catch {
          // Called from a Server Component where mutating cookies is disallowed.
          // Safe to ignore: a middleware refresh or Route Handler will persist.
        }
      },
    },
  })
}
