"""
Astra backend configuration.

Values are read from the environment so the same code runs locally, in CI, and
on Vercel. Nothing here imports heavy dependencies, so it is safe to import from
anywhere including cold-start paths.
"""

from __future__ import annotations

import os

# Supabase project URL, e.g. https://xxxx.supabase.co
SUPABASE_URL = os.environ.get("SUPABASE_URL") or os.environ.get(
    "NEXT_PUBLIC_SUPABASE_URL", ""
)

# Service-role key. SERVER ONLY — bypasses RLS. The badge route reads with this
# because it is a backend-only read; the anon key is never used here.
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

# Current score version. Used to build the cache key so a version bump busts the
# in-process LRU cache automatically.
SCORE_VERSION = os.environ.get("ASTRA_SCORE_VERSION", "v1.0")

# Per-IP rate limit for direct (non-camo) hits.
RATE_LIMIT_REQUESTS = int(os.environ.get("ASTRA_BADGE_RATE_LIMIT", "10"))
RATE_LIMIT_WINDOW_SECONDS = float(os.environ.get("ASTRA_BADGE_RATE_WINDOW", "1.0"))

# In-process slug cache size.
SLUG_CACHE_MAXSIZE = int(os.environ.get("ASTRA_BADGE_CACHE_SIZE", "5000"))
