"""
Astra badge endpoint — GET /api/v1/badge/{slug}.svg

This route is embedded in thousands of README files and proxied through
``camo.githubusercontent.com``. Camo caches our origin response according to the
``Cache-Control`` header we send on first fetch and then serves that copy to all
subsequent viewers until it expires — so the headers below are the primary
defense against load. The in-process caches and rate limiter are secondary
protection for the small slice of traffic that hits the origin directly.

Design priorities, in order:

1. **Never 404 an image.** A 404 renders as a broken-image glyph in GitHub. All
   states (found / unknown / private) return HTTP 200 with a valid SVG.
2. **Maximize cache hits.** Long ``s-maxage`` for camo/CDN, short ``max-age``
   for browsers, plus a strong ``ETag`` so conditional requests get a cheap 304.
3. **Cold-start friendly.** Pure string templating, lazy Supabase import, and a
   module-level LRU cache that a warm instance reuses.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from collections import defaultdict, deque
from functools import lru_cache

from fastapi import APIRouter, Request, Response

from config import (
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW_SECONDS,
    SCORE_VERSION,
    SLUG_CACHE_MAXSIZE,
)
from services.badge_renderer import (
    render_private_badge,
    render_score_badge,
    render_unknown_badge,
    tier_for_score,
)

logger = logging.getLogger("astra.badge")

router = APIRouter(prefix="/api/v1", tags=["badge"])

# Exact caching policy (see module docstring). Short browser cache, long CDN/camo
# cache, with a generous stale-while-revalidate window.
CACHE_CONTROL = (
    "public, max-age=3600, s-maxage=86400, stale-while-revalidate=43200"
)
CONTENT_TYPE = "image/svg+xml; charset=utf-8"


# ---------------------------------------------------------------------------
# Cache layer (TASK 4)
# ---------------------------------------------------------------------------
# A "badge payload" is the fully rendered SVG plus its ETag. We cache it keyed by
# f"badge:{slug}:{score_version}" so a score-version bump busts stale entries.
# lru_cache gives us bounded, O(1), thread-safe memoization with no new infra.
class _BadgePayload:
    __slots__ = ("svg", "etag", "state")

    def __init__(self, svg: str, etag: str, state: str) -> None:
        self.svg = svg
        self.etag = etag
        self.state = state  # "score" | "unknown" | "private"


def _make_etag(slug: str, tier_label: str, score_repr: str) -> str:
    """Strong ETag from the identity of the rendered content.

    md5 of score + tier + slug: stable while those are unchanged, different the
    moment the score (and thus tier) changes. Not used for security, only cache
    validation, so md5 is appropriate and fast.
    """
    digest = hashlib.md5(
        f"{slug}:{score_repr}:{tier_label}".encode("utf-8")
    ).hexdigest()
    return f'"{digest}"'


@lru_cache(maxsize=SLUG_CACHE_MAXSIZE)
def _render_payload(cache_key: str, state: str, score_bits: str) -> _BadgePayload:
    """Render + memoize a badge payload for a cache key.

    ``cache_key`` is ``f"badge:{slug}:{score_version}"``. ``state`` and
    ``score_bits`` are folded into the key by the caller-visible wrapper so that
    two slugs that collide in state but differ in score never share an entry.
    """
    # cache_key is "badge:{slug}:{version}"; recover the slug for the ETag.
    _, slug, _version = cache_key.split(":", 2)

    if state == "unknown":
        svg = render_unknown_badge()
        etag = _make_etag(slug, "unknown", "none")
        return _BadgePayload(svg, etag, state)

    if state == "private":
        svg = render_private_badge()
        etag = _make_etag(slug, "private", "none")
        return _BadgePayload(svg, etag, state)

    # state == "score": score_bits is the exact score repr used for rendering.
    score = float(score_bits)
    svg = render_score_badge(score)
    tier = tier_for_score(score)
    etag = _make_etag(slug, tier.label, score_bits)
    return _BadgePayload(svg, etag, state)


def _cache_key(slug: str, score_version: str) -> str:
    return f"badge:{slug}:{score_version}"


# ---------------------------------------------------------------------------
# Rate limiter (TASK 5)
# ---------------------------------------------------------------------------
class SlidingWindowRateLimiter:
    """In-memory per-IP sliding-window limiter.

    Tracks request timestamps per client IP in a bounded deque and rejects once
    more than ``max_requests`` fall inside ``window_seconds``. This only guards
    direct hits that bypass camo; the vast majority of traffic never reaches it.
    A lock keeps it correct under the threadpool FastAPI uses for sync routes.
    """

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, client_ip: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        cutoff = now - self.window_seconds
        with self._lock:
            bucket = self._hits[client_ip]
            # Drop timestamps that have aged out of the window.
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.max_requests:
                return False
            bucket.append(now)
            # Opportunistic cleanup: forget empty buckets to bound memory.
            if not bucket:
                del self._hits[client_ip]
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


rate_limiter = SlidingWindowRateLimiter(
    max_requests=RATE_LIMIT_REQUESTS,
    window_seconds=RATE_LIMIT_WINDOW_SECONDS,
)


def _client_ip(request: Request) -> str:
    """Best-effort client IP, honoring the first X-Forwarded-For hop.

    Behind Vercel/camo the real client is in X-Forwarded-For; fall back to the
    socket peer for direct/local requests.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    client = request.client
    return client.host if client else "unknown"


# ---------------------------------------------------------------------------
# Data lookup
# ---------------------------------------------------------------------------
def _lookup_state(slug: str) -> tuple[str, str, str]:
    """Resolve a slug to (state, score_version, score_bits).

    Returns one of:
      * ("unknown", SCORE_VERSION, "none")   — slug not found
      * ("private", SCORE_VERSION, "none")   — user is not public
      * ("score", <version>, "<score>")      — public user with a score

    A lookup failure degrades to the "unknown" badge rather than raising, so a
    transient Supabase error still returns a valid image (never a broken embed).
    """
    try:
        # Imported lazily so the renderer/tests don't require the supabase pkg.
        from services.supabase_client import fetch_badge_record

        record = fetch_badge_record(slug)
    except Exception as exc:  # noqa: BLE001 - degrade to a valid badge, never 500
        logger.warning("Badge lookup failed for %s: %s", slug, exc)
        return ("unknown", SCORE_VERSION, "none")

    if record is None:
        return ("unknown", SCORE_VERSION, "none")
    if not record.is_public:
        return ("private", SCORE_VERSION, "none")

    version = record.score_version or SCORE_VERSION
    # A public user with no current score renders as a real 0-score badge.
    score = record.score if record.score is not None else 0.0
    return ("score", version, repr(float(score)))


# ---------------------------------------------------------------------------
# Route (TASK 1 + TASK 3)
# ---------------------------------------------------------------------------
@router.get("/badge/{slug}.svg")
def get_badge(slug: str, request: Request) -> Response:
    # -- rate limit direct abuse (camo traffic essentially never lands here) --
    if not rate_limiter.allow(_client_ip(request)):
        # 429 with Retry-After. This path is only hit by scripted direct abuse;
        # legitimate camo/browser traffic is served from cache.
        return Response(
            content=render_unknown_badge(),
            status_code=429,
            media_type=CONTENT_TYPE,
            headers={
                "Cache-Control": "no-store",
                "Retry-After": "1",
                "Content-Type": CONTENT_TYPE,
            },
        )

    state, score_version, score_bits = _lookup_state(slug)
    key = _cache_key(slug, score_version)
    payload = _render_payload(key, state, score_bits)

    # -- conditional request: cheap 304 when the client already has this ETag --
    inm = request.headers.get("if-none-match")
    if inm and _etag_matches(inm, payload.etag):
        return Response(
            status_code=304,
            headers=_response_headers(payload.etag),
        )

    return Response(
        content=payload.svg,
        status_code=200,
        media_type=CONTENT_TYPE,
        headers=_response_headers(payload.etag),
    )


def _response_headers(etag: str) -> dict[str, str]:
    """The exact header set for a badge response (TASK 3)."""
    return {
        "Cache-Control": CACHE_CONTROL,
        "ETag": etag,
        "Content-Type": CONTENT_TYPE,
        "Vary": "Accept-Encoding",
    }


def _etag_matches(if_none_match: str, etag: str) -> bool:
    """RFC 7232 weak-comparison-friendly membership test for If-None-Match."""
    if if_none_match.strip() == "*":
        return True
    candidates = {token.strip() for token in if_none_match.split(",")}
    # Normalize weak validators (W/"...") to their strong form for comparison.
    normalized = {c[2:] if c.startswith("W/") else c for c in candidates}
    return etag in candidates or etag in normalized
