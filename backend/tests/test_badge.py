"""
Tests for the Astra badge endpoint and renderer.

Covered per spec:
  * valid score renders the correct tier color        -> test_tier_colors_*
  * unknown slug returns a valid SVG, HTTP 200 not 404 -> test_unknown_slug_*
  * XML injection in a malicious score/label is escaped-> test_xml_injection_*
  * ETag changes when score changes, stable otherwise  -> test_etag_*

The Supabase layer is monkeypatched with an in-memory fake so the route runs
without network or the ``supabase`` package installed. Renderer tests are pure.
"""

from __future__ import annotations

import xml.dom.minidom as minidom

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import badge as badge_router
from services import badge_renderer
from services.badge_renderer import (
    GREY,
    render_score_badge,
    render_unknown_badge,
    tier_for_score,
)
from services.supabase_client import BadgeRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def client(monkeypatch):
    """A TestClient with the badge router mounted and a fake Supabase layer."""
    app = FastAPI()
    app.include_router(badge_router.router)

    # Reset per-test global state so tests are independent.
    badge_router._render_payload.cache_clear()
    badge_router.rate_limiter.reset()

    fake_db: dict[str, BadgeRecord] = {}

    def fake_fetch(slug: str):
        return fake_db.get(slug)

    # The route imports fetch_badge_record lazily from this module path.
    import services.supabase_client as sc

    monkeypatch.setattr(sc, "fetch_badge_record", fake_fetch)

    tc = TestClient(app)
    tc.fake_db = fake_db  # type: ignore[attr-defined]
    return tc


def _put(client, slug, *, is_public=True, score=1800.0, version="v1.0"):
    client.fake_db[slug] = BadgeRecord(
        slug=slug, is_public=is_public, score=score, score_version=version
    )


def _assert_well_formed_svg(svg: str) -> None:
    # Raises if not well-formed XML.
    minidom.parseString(svg)
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")


# ---------------------------------------------------------------------------
# Renderer: tier colors
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "score,color,label",
    [
        (2400, "#FFD700", "Grandmaster"),
        (2600, "#FFD700", "Grandmaster"),
        (2000, "#A855F7", "Master"),
        (2399, "#A855F7", "Master"),
        (1600, "#3B82F6", "Expert"),
        (1999, "#3B82F6", "Expert"),
        (1599, "#64748B", "Apprentice"),
        (0, "#64748B", "Apprentice"),
    ],
)
def test_tier_colors(score, color, label):
    tier = tier_for_score(score)
    assert tier.color == color
    assert tier.label == label
    svg = render_score_badge(score)
    _assert_well_formed_svg(svg)
    assert color in svg
    assert str(int(score)) in svg
    assert label in svg


def test_width_scales_with_digit_count():
    # A 4-digit score badge must be wider than a 1-digit one (no clipping).
    wide = render_score_badge(2400)
    narrow = render_score_badge(5)

    def svg_width(svg: str) -> int:
        import re

        return int(re.search(r'width="(\d+)"', svg).group(1))

    assert svg_width(wide) > svg_width(narrow)


# ---------------------------------------------------------------------------
# Route: unknown slug -> valid SVG, HTTP 200 (never 404)
# ---------------------------------------------------------------------------
def test_unknown_slug_returns_200_svg(client):
    resp = client.get("/api/v1/badge/does-not-exist.svg")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/svg+xml; charset=utf-8"
    _assert_well_formed_svg(resp.text)
    assert "Not Found" in resp.text
    assert GREY in resp.text


def test_private_user_returns_200_private_badge(client):
    _put(client, "shy", is_public=False, score=2500.0)
    resp = client.get("/api/v1/badge/shy.svg")
    assert resp.status_code == 200
    _assert_well_formed_svg(resp.text)
    assert "Private" in resp.text
    # Must not leak the actual score/tier of a private user.
    assert "2500" not in resp.text
    assert "Grandmaster" not in resp.text


def test_valid_slug_renders_score_tier(client):
    _put(client, "ada", is_public=True, score=2450.0)
    resp = client.get("/api/v1/badge/ada.svg")
    assert resp.status_code == 200
    _assert_well_formed_svg(resp.text)
    assert "#FFD700" in resp.text  # gold tier
    assert "2450" in resp.text


# ---------------------------------------------------------------------------
# XML injection safety
# ---------------------------------------------------------------------------
def test_xml_injection_in_score_label_is_escaped():
    # Simulate a hostile value flowing into the right-hand text. We render via
    # the internal template directly to inject an arbitrary label string.
    malicious = '"><script>alert(1)</script><rect fill="'
    svg = badge_renderer._render_svg("ASTRA", malicious, "#64748B")

    # Must remain well-formed and contain no live script element.
    _assert_well_formed_svg(svg)
    assert "<script>" not in svg
    assert "&lt;script&gt;" in svg


def test_xml_injection_in_color_is_escaped():
    malicious_color = '#000" onload="alert(1)'
    svg = badge_renderer._render_svg("ASTRA", "1800 Expert", malicious_color)
    _assert_well_formed_svg(svg)

    # The hostile string must land entirely inside the fill attribute value and
    # never materialize as a live `onload` attribute on any element.
    doc = minidom.parseString(svg)
    for rect in doc.getElementsByTagName("rect"):
        assert not rect.getAttribute("onload")
        for i in range(rect.attributes.length):
            assert rect.attributes.item(i).name != "onload"


def test_route_escapes_injection_end_to_end(client, monkeypatch):
    # Force the renderer to receive a hostile score label via a patched tier.
    _put(client, "evil", is_public=True, score=1800.0)

    def evil_render(score):
        return badge_renderer._render_svg(
            "ASTRA", '<script>bad()</script>', "#3B82F6"
        )

    monkeypatch.setattr(badge_router, "render_score_badge", evil_render)
    badge_router._render_payload.cache_clear()

    resp = client.get("/api/v1/badge/evil.svg")
    assert resp.status_code == 200
    _assert_well_formed_svg(resp.text)
    assert "<script>" not in resp.text


# ---------------------------------------------------------------------------
# ETag behavior
# ---------------------------------------------------------------------------
def test_etag_present_and_stable_when_score_unchanged(client):
    _put(client, "sam", is_public=True, score=1700.0)
    r1 = client.get("/api/v1/badge/sam.svg")
    r2 = client.get("/api/v1/badge/sam.svg")
    assert r1.headers["etag"]
    assert r1.headers["etag"] == r2.headers["etag"]


def test_etag_changes_when_score_changes(client):
    _put(client, "sam", is_public=True, score=1700.0)
    etag_low = client.get("/api/v1/badge/sam.svg").headers["etag"]

    # Bump the score into a new tier and bust the in-process cache.
    _put(client, "sam", is_public=True, score=2500.0)
    badge_router._render_payload.cache_clear()
    etag_high = client.get("/api/v1/badge/sam.svg").headers["etag"]

    assert etag_low != etag_high


def test_conditional_request_returns_304(client):
    _put(client, "sam", is_public=True, score=1700.0)
    first = client.get("/api/v1/badge/sam.svg")
    etag = first.headers["etag"]

    second = client.get(
        "/api/v1/badge/sam.svg", headers={"If-None-Match": etag}
    )
    assert second.status_code == 304
    # A 304 still carries the validators/caching headers.
    assert second.headers["etag"] == etag
    assert "max-age=3600" in second.headers["cache-control"]


# ---------------------------------------------------------------------------
# Caching headers (exact policy) + cache key
# ---------------------------------------------------------------------------
def test_cache_control_and_vary_headers_exact(client):
    _put(client, "sam", is_public=True, score=1700.0)
    resp = client.get("/api/v1/badge/sam.svg")
    assert resp.headers["cache-control"] == (
        "public, max-age=3600, s-maxage=86400, stale-while-revalidate=43200"
    )
    assert resp.headers["vary"] == "Accept-Encoding"
    assert resp.headers["content-type"] == "image/svg+xml; charset=utf-8"


def test_cache_key_includes_score_version():
    assert (
        badge_router._cache_key("ada", "v2.0") == "badge:ada:v2.0"
    )


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------
def test_rate_limiter_sliding_window():
    from routers.badge import SlidingWindowRateLimiter

    limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=1.0)
    # 3 allowed inside the window at a fixed instant.
    assert limiter.allow("1.2.3.4", now=100.0)
    assert limiter.allow("1.2.3.4", now=100.1)
    assert limiter.allow("1.2.3.4", now=100.2)
    # 4th within the window is rejected.
    assert not limiter.allow("1.2.3.4", now=100.3)
    # After the window slides past, allowed again.
    assert limiter.allow("1.2.3.4", now=101.5)
    # A different IP has its own budget.
    assert limiter.allow("9.9.9.9", now=100.3)


def test_route_rate_limit_returns_429_svg(client):
    _put(client, "sam", is_public=True, score=1700.0)
    # Shrink the limiter for a deterministic test.
    from routers.badge import SlidingWindowRateLimiter

    badge_router.rate_limiter = SlidingWindowRateLimiter(
        max_requests=2, window_seconds=100.0
    )
    ok1 = client.get("/api/v1/badge/sam.svg")
    ok2 = client.get("/api/v1/badge/sam.svg")
    limited = client.get("/api/v1/badge/sam.svg")
    assert ok1.status_code == 200
    assert ok2.status_code == 200
    assert limited.status_code == 429
    # Even the rejection is a valid SVG, and it is not cacheable.
    _assert_well_formed_svg(limited.text)
    assert limited.headers["cache-control"] == "no-store"


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
