"""
Astra backend — Supabase service-role access for the badge route.

The badge endpoint performs a backend-only read, so it uses the *service_role*
key (which bypasses RLS), never the anon key. The client is lazily constructed
and cached at module level so a warm serverless instance reuses one connection
pool across requests.

The public surface is intentionally tiny: :func:`fetch_badge_record` returns the
minimal fields the route needs, or ``None`` when the slug does not exist.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from config import SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL

logger = logging.getLogger("astra.supabase")


@dataclass(frozen=True)
class BadgeRecord:
    """Minimal projection the badge route needs about a passport."""

    slug: str
    is_public: bool
    score: float | None
    score_version: str | None


@lru_cache(maxsize=1)
def _get_client():
    """Construct and cache the service-role Supabase client.

    Imported lazily so environments that never touch Supabase (e.g. the pure
    renderer tests) don't need the ``supabase`` package installed.
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set to read badges."
        )
    from supabase import create_client  # lazy: optional dependency

    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def _coerce_record(slug: str, row: dict[str, Any]) -> BadgeRecord:
    """Map a joined users/capability_scores row into a BadgeRecord."""
    is_public = bool(row.get("is_public", False))

    # capability_scores is embedded as a list (Supabase relationship expansion).
    scores = row.get("capability_scores") or []
    if isinstance(scores, dict):  # some client versions return a single object
        scores = [scores]

    score: float | None = None
    score_version: str | None = None
    if scores:
        current = scores[0]
        raw = current.get("astra_score")
        score = float(raw) if raw is not None else None
        score_version = current.get("score_version")

    return BadgeRecord(
        slug=slug,
        is_public=is_public,
        score=score,
        score_version=score_version,
    )


def fetch_badge_record(slug: str) -> BadgeRecord | None:
    """Look up a passport by slug, joining the current capability score.

    Returns ``None`` when no user has that ``passport_slug``. A user that exists
    but has no current score yields a record with ``score is None`` (the route
    treats a public user with no score as a rendered zero/unknown tier).
    """
    client = _get_client()

    # Join users -> capability_scores filtered to the current score. We request
    # only the columns the badge needs. The embedded resource is constrained to
    # is_current = true so at most one score row comes back.
    response = (
        client.table("users")
        .select(
            "passport_slug, is_public, "
            "capability_scores(astra_score, score_version, is_current)"
        )
        .eq("passport_slug", slug)
        .eq("capability_scores.is_current", True)
        .limit(1)
        .execute()
    )

    rows = response.data or []
    if not rows:
        return None
    return _coerce_record(slug, rows[0])
