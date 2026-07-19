import { createBrowserClient } from '@supabase/ssr'

/**
 * Browser-side Supabase client for Astra.
 *
 * Use this only in Client Components ('use client'). It reads the public
 * anon key and is safe to ship to the browser; all privileged access is
 * mediated by Row Level Security. Server Components, Server Actions, and
 * Route Handlers must use the server client in `./server` instead.
 */
export function createClient() {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

  if (!supabaseUrl || !supabaseAnonKey) {
    throw new Error(
      'Missing Supabase env vars: NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY must be set.'
    )
  }

  return createBrowserClient(supabaseUrl, supabaseAnonKey)
}
