"""
Astra capability engine — deep library detection & weighting.

This module is intentionally free of any LLM calls. Every signal it produces is
derived from deterministic static analysis facts supplied by a
:class:`~services.ast_parser.BaseCodeParser`. The registry assigns *base weights*
to libraries that are meaningful signals of engineering capability, grouped into
four scoring categories, and :func:`detect_deep_usage` classifies how deeply a
given source file exercises each library.

The core idea: importing ``torch`` is cheap; *authoring* a ``triton`` kernel or a
``torch.autograd.Function`` is not. We therefore multiply the base weight by a
usage-depth multiplier:

===================  ==========  ================================================
depth classification multiplier  meaning
===================  ==========  ================================================
kernel_authoring      2.0        custom kernels / autograd extensions / JIT
api_usage             1.0        3+ genuine call sites into the library
import_only           0.2        imported but barely referenced (<3 call sites)
===================  ==========  ================================================
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids a runtime import cycle
    from services.ast_parser import BaseCodeParser


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
# Nested by scoring category so category rollups (subscore_contributions) stay
# trivial. Weights are hand-tuned signals of capability depth, not popularity.
ADVANCED_LIBS: dict[str, dict[str, float]] = {
    "ml_infra": {
        "torch": 3.0,
        "triton": 5.0,
        "jax": 3.5,
        "flax": 3.0,
        "deepspeed": 4.0,
        "vllm": 4.5,
        "xla": 4.0,
    },
    "systems": {
        "cuda": 4.0,
        "cython": 3.0,
        "asyncio": 1.5,
        "multiprocessing": 1.5,
    },
    "data": {
        "numpy": 1.0,
        "pandas": 1.0,
        "polars": 1.5,
    },
    "web": {
        "flask": 0.5,
        "fastapi": 0.8,
        "express": 0.5,
        "django": 0.7,
    },
}

# Flattened lookup tables, derived once at import time.
LIB_WEIGHTS: dict[str, float] = {
    lib: weight
    for category in ADVANCED_LIBS.values()
    for lib, weight in category.items()
}
LIB_CATEGORY: dict[str, str] = {
    lib: category
    for category, libs in ADVANCED_LIBS.items()
    for lib in libs
}

# Depth classification metadata.
DEPTH_MULTIPLIERS: dict[str, float] = {
    "kernel_authoring": 2.0,
    "api_usage": 1.0,
    "import_only": 0.2,
}
# Ordinal ranking so aggregation can pick the *deepest* usage seen across files.
DEPTH_RANK: dict[str, int] = {
    "import_only": 0,
    "api_usage": 1,
    "kernel_authoring": 2,
}

# A library is considered "used as an API" once it has at least this many
# genuine call sites; below this it is treated as an incidental import.
API_USAGE_MIN_CALL_SITES = 3


def classify_depth(*, kernel_authoring: bool, call_sites: int) -> str:
    """Map raw static-analysis facts to a depth classification label."""
    if kernel_authoring:
        return "kernel_authoring"
    if call_sites >= API_USAGE_MIN_CALL_SITES:
        return "api_usage"
    return "import_only"


def detect_deep_usage(parser: "BaseCodeParser", source: str) -> dict[str, dict]:
    """Classify how deeply *source* exercises each registry library.

    Returns a mapping of ``library -> signal`` where each signal is::

        {
            "depth": "kernel_authoring" | "api_usage" | "import_only",
            "category": "ml_infra" | "systems" | "data" | "web",
            "base_weight": float,   # registry weight before the depth multiplier
            "weight": float,        # base_weight * depth multiplier
            "call_sites": int,      # genuine references, excluding the import
            "kernel_authoring": bool,
        }

    Only libraries present in :data:`ADVANCED_LIBS` are reported. The ``source``
    argument is accepted per the engine's interface contract; the authoritative
    facts come from ``parser`` so detection stays AST-driven rather than textual.
    """
    # ``source`` is retained for interface stability and lets callers pass the
    # exact text the parser was built from; the parser is the source of truth.
    _ = source

    usage = parser.library_usage()
    signals: dict[str, dict] = {}

    for lib, facts in usage.items():
        base = LIB_WEIGHTS.get(lib)
        if base is None:
            # Defensive: parsers should only surface registry libraries.
            continue

        call_sites = int(facts.get("call_sites", 0))
        kernel = bool(facts.get("kernel_authoring", False))
        depth = classify_depth(kernel_authoring=kernel, call_sites=call_sites)
        weight = round(base * DEPTH_MULTIPLIERS[depth], 4)

        signals[lib] = {
            "depth": depth,
            "category": LIB_CATEGORY[lib],
            "base_weight": base,
            "weight": weight,
            "call_sites": call_sites,
            "kernel_authoring": kernel,
        }

    return signals
