"""
Astra capability engine — SVG badge renderer.

This module renders the README badge as a pure f-string SVG. There is no
headless browser, no rasterization, and no image library: rendering is a few
string operations so it stays sub-millisecond and cold-start friendly on a
serverless function.

The badge is a classic two-tone "shield": a fixed dark-navy left segment reading
``ASTRA`` and a right segment whose fill is color-coded by score tier (chess
rating psychology — gold/purple/blue/grey). Segment widths are computed from an
approximate per-character width so 3-digit and 4-digit scores never clip.

Every interpolated value (score, tier label, slug-derived text) is XML-escaped
before it touches the template, so a hostile value stored upstream cannot inject
markup or break out of an attribute.
"""

from __future__ import annotations

from dataclasses import dataclass
from xml.sax.saxutils import escape, quoteattr

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------
FONT_SIZE = 11
# Approximate advance width per character at FONT_SIZE (per the spec: 7px/char).
CHAR_WIDTH_PX = 7
# Horizontal padding inside each segment (left + right of the text).
SEGMENT_PADDING = 10
BADGE_HEIGHT = 20
# Vertical text baseline. Text is drawn twice (shadow + fill) for legibility.
TEXT_Y = 14
SHADOW_Y = 15

# Colors.
LEFT_BG = "#0F172A"          # dark navy
TEXT_FILL = "#FFFFFF"
SHADOW_FILL = "#010409"
GREY = "#64748B"             # also the "unknown"/"private" neutral tone

LEFT_LABEL = "ASTRA"

# ---------------------------------------------------------------------------
# Tier model
# ---------------------------------------------------------------------------
# Ordered high -> low; first threshold whose bound is met wins.
_TIERS: tuple[tuple[int, str, str], ...] = (
    (2400, "Grandmaster", "#FFD700"),  # gold
    (2000, "Master", "#A855F7"),       # purple
    (1600, "Expert", "#3B82F6"),       # blue
    (0, "Apprentice", GREY),           # grey (below 1600)
)


@dataclass(frozen=True)
class Tier:
    label: str
    color: str


def tier_for_score(score: float) -> Tier:
    """Return the color tier for a numeric score (chess-rating tiers)."""
    for threshold, label, color in _TIERS:
        if score >= threshold:
            return Tier(label=label, color=color)
    # Unreachable given the 0-bound sentinel, but keep it total.
    return Tier(label="Apprentice", color=GREY)


# ---------------------------------------------------------------------------
# Width math
# ---------------------------------------------------------------------------
def _text_width(text: str) -> int:
    """Approximate rendered width of *text* at FONT_SIZE, in px."""
    return len(text) * CHAR_WIDTH_PX


def _segment_width(text: str) -> int:
    """Segment width = text width + padding on both sides."""
    return _text_width(text) + SEGMENT_PADDING * 2


def _render_svg(left_text: str, right_text: str, right_color: str) -> str:
    """Assemble the two-tone SVG. All text args must be pre-trusted/escaped-safe.

    Escaping is applied here defensively regardless, so callers cannot forget.
    """
    # Escape element text and attribute values independently.
    left_esc = escape(left_text)
    right_esc = escape(right_text)
    # quoteattr returns a value *including* surrounding quotes.
    color_attr = quoteattr(right_color)

    left_w = _segment_width(left_text)
    right_w = _segment_width(right_text)
    total_w = left_w + right_w

    # Text is centered within each segment. Coordinates are scaled x10 in the
    # text group (textLength-free) — but we keep it simple with direct coords.
    left_text_x = left_w / 2
    right_text_x = left_w + right_w / 2

    # A short, deterministic gradient id keeps multiple inlined badges valid.
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{total_w}" height="{BADGE_HEIGHT}" '
        f'viewBox="0 0 {total_w} {BADGE_HEIGHT}" '
        f'role="img" aria-label={quoteattr(f"{left_text}: {right_text}")}>'
        f'<title>{left_esc}: {right_esc}</title>'
        f'<linearGradient id="s" x2="0" y2="100%">'
        f'<stop offset="0" stop-color="#FFFFFF" stop-opacity=".1"/>'
        f'<stop offset="1" stop-opacity=".1"/>'
        f'</linearGradient>'
        f'<clipPath id="r"><rect width="{total_w}" height="{BADGE_HEIGHT}" rx="3"/></clipPath>'
        f'<g clip-path="url(#r)">'
        f'<rect width="{left_w}" height="{BADGE_HEIGHT}" fill="{LEFT_BG}"/>'
        f'<rect x="{left_w}" width="{right_w}" height="{BADGE_HEIGHT}" fill={color_attr}/>'
        f'<rect width="{total_w}" height="{BADGE_HEIGHT}" fill="url(#s)"/>'
        f'</g>'
        f'<g fill="{TEXT_FILL}" text-anchor="middle" '
        f'font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="{FONT_SIZE}">'
        # left label: shadow then fill
        f'<text x="{left_text_x}" y="{SHADOW_Y}" fill="{SHADOW_FILL}" '
        f'fill-opacity=".3">{left_esc}</text>'
        f'<text x="{left_text_x}" y="{TEXT_Y}">{left_esc}</text>'
        # right label: shadow then fill
        f'<text x="{right_text_x}" y="{SHADOW_Y}" fill="{SHADOW_FILL}" '
        f'fill-opacity=".3">{right_esc}</text>'
        f'<text x="{right_text_x}" y="{TEXT_Y}">{right_esc}</text>'
        f'</g>'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# Public renderers
# ---------------------------------------------------------------------------
def render_score_badge(score: float) -> str:
    """Render a badge for a real, public score."""
    tier = tier_for_score(score)
    # Scores are integers in practice; render without a trailing ``.0``.
    score_text = str(int(score)) if float(score).is_integer() else str(score)
    right_text = f"{score_text} {tier.label}"
    return _render_svg(LEFT_LABEL, right_text, tier.color)


def render_unknown_badge() -> str:
    """Render the neutral 'Not Found' badge (still HTTP 200 at the route)."""
    return _render_svg(LEFT_LABEL, "Not Found", GREY)


def render_private_badge() -> str:
    """Render the neutral 'Private' badge for non-public users."""
    return _render_svg(LEFT_LABEL, "Private", GREY)
