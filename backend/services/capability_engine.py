"""
Astra capability engine — repository aggregation into the JSONB snapshot.

:func:`analyze_repository` is the orchestrator. It runs the deterministic
pipeline ``fetch -> filter -> parse -> aggregate`` over every selected file in a
repository and produces one JSON-serializable dict — the value persisted into
``repositories.astra_capability_summary``.

Design constraints honored here:

* **No LLM anywhere.** Every number is derived from AST/tree-sitter analysis.
* **Serverless-friendly concurrency.** Blob fetches fan out via
  :func:`asyncio.gather` bounded by a semaphore (``max_concurrency=10``) to stay
  under GitHub's secondary rate limits.
* **Fault isolation.** A single file that fails to download or parse is logged
  and skipped; it never aborts the batch.

Output shape (exact)::

    {
      "analyzed_at": "<ISO8601 UTC>",
      "files_analyzed": int,
      "avg_cyclomatic_complexity": float,
      "max_ast_depth": int,
      "library_signals": {
        "torch": {"depth": "kernel_authoring", "weight": 6.0, "file_count": 3},
        ...
      },
      "boilerplate_ratio": float,          # 0.0 - 1.0
      "subscore_contributions": {
        "ml_infra": float, "systems": float, "data": float, "web": float
      }
    }
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from services.ast_parser import get_parser
from services.file_selector import select_analysis_targets, target_basename
from services.github_client import fetch_file_blob, fetch_repo_tree
from services.library_registry import (
    ADVANCED_LIBS,
    DEPTH_RANK,
    LIB_CATEGORY,
    detect_deep_usage,
)

logger = logging.getLogger("astra.capability_engine")

# Bound on concurrent GitHub blob fetches. Chosen to stay well under GitHub's
# secondary rate limits for a single token while keeping the batch fast.
MAX_CONCURRENCY = 10

# The four scoring categories, fixed so the output always has all keys present
# (zero-valued when a category contributes nothing).
_SCORE_CATEGORIES = ("ml_infra", "systems", "data", "web")


class _FileAnalysis:
    """Per-file analysis result carried through aggregation."""

    __slots__ = ("path", "complexity", "depth", "boilerplate", "signals")

    def __init__(
        self,
        path: str,
        complexity: int,
        depth: int,
        boilerplate: bool,
        signals: dict[str, dict],
    ) -> None:
        self.path = path
        self.complexity = complexity
        self.depth = depth
        self.boilerplate = boilerplate
        self.signals = signals


def _empty_summary() -> dict[str, Any]:
    """The canonical snapshot for a repo with nothing analyzable."""
    return {
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "files_analyzed": 0,
        "avg_cyclomatic_complexity": 0.0,
        "max_ast_depth": 0,
        "library_signals": {},
        "boilerplate_ratio": 0.0,
        "subscore_contributions": {category: 0.0 for category in _SCORE_CATEGORIES},
    }


def analyze_source(path: str, source: str) -> _FileAnalysis | None:
    """Parse and analyze a single source string. Returns None on failure.

    Isolated here (rather than inlined in the gather loop) so it is directly
    unit-testable and so all parse exceptions funnel through one place.
    """
    try:
        parser = get_parser(path, source)
    except SyntaxError as exc:
        logger.warning("Skipping %s: syntax error during parse: %s", path, exc)
        return None
    except ValueError as exc:
        # Unsupported extension slipped through selection — skip defensively.
        logger.warning("Skipping %s: %s", path, exc)
        return None
    except Exception as exc:  # noqa: BLE001 - tree-sitter can raise varied errors
        logger.warning("Skipping %s: unexpected parse failure: %s", path, exc)
        return None

    try:
        complexity = parser.cyclomatic_complexity()
        depth = parser.ast_depth()
        boilerplate = parser.is_boilerplate()
        signals = detect_deep_usage(parser, source)
    except Exception as exc:  # noqa: BLE001 - never let one file kill the batch
        logger.warning("Skipping %s: analysis failure: %s", path, exc)
        return None

    return _FileAnalysis(path, complexity, depth, boilerplate, signals)


async def _fetch_and_analyze(
    owner: str,
    repo: str,
    token: str,
    entry: dict,
    semaphore: asyncio.Semaphore,
) -> _FileAnalysis | None:
    """Fetch one blob and analyze it, guarded by the concurrency semaphore."""
    path = entry.get("path", "")
    sha = entry.get("sha")
    if not sha:
        logger.warning("Skipping %s: tree entry has no sha", path)
        return None

    async with semaphore:
        try:
            source = await fetch_file_blob(owner, repo, sha, token)
        except Exception as exc:  # noqa: BLE001 - network/HTTP errors are per-file
            logger.warning("Skipping %s: blob fetch failed: %s", path, exc)
            return None

    # Analysis is CPU-bound and synchronous; run it outside the semaphore so a
    # slow parse does not hold a fetch slot.
    return analyze_source(path or target_basename(entry), source)


def _aggregate(results: list[_FileAnalysis]) -> dict[str, Any]:
    """Fold per-file analyses into the final snapshot dict."""
    if not results:
        return _empty_summary()

    files_analyzed = len(results)
    total_complexity = sum(r.complexity for r in results)
    max_depth = max(r.depth for r in results)
    boilerplate_count = sum(1 for r in results if r.boilerplate)

    # Per-library rollup: deepest usage seen, summed weight, and file count.
    # `best_depth` tracks the deepest classification across files (kernel >
    # api > import); `weight` reports the weight at that deepest depth.
    lib_depth: dict[str, str] = {}
    lib_weight_at_depth: dict[str, float] = {}
    lib_file_count: dict[str, int] = {}
    # Category contribution sums every file's weighted signal.
    category_totals: dict[str, float] = {c: 0.0 for c in _SCORE_CATEGORIES}

    for result in results:
        for lib, signal in result.signals.items():
            lib_file_count[lib] = lib_file_count.get(lib, 0) + 1
            category_totals[signal["category"]] += signal["weight"]

            depth = signal["depth"]
            if lib not in lib_depth or DEPTH_RANK[depth] > DEPTH_RANK[lib_depth[lib]]:
                lib_depth[lib] = depth
                lib_weight_at_depth[lib] = signal["weight"]

    library_signals = {
        lib: {
            "depth": lib_depth[lib],
            "weight": round(lib_weight_at_depth[lib], 4),
            "file_count": lib_file_count[lib],
        }
        for lib in sorted(lib_file_count)
    }

    return {
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "files_analyzed": files_analyzed,
        "avg_cyclomatic_complexity": round(total_complexity / files_analyzed, 4),
        "max_ast_depth": max_depth,
        "library_signals": library_signals,
        "boilerplate_ratio": round(boilerplate_count / files_analyzed, 4),
        "subscore_contributions": {
            category: round(category_totals[category], 4)
            for category in _SCORE_CATEGORIES
        },
    }


async def analyze_repository(owner: str, repo: str, token: str) -> dict[str, Any]:
    """Analyze a repository end-to-end and return the capability snapshot.

    Orchestrates ``fetch -> filter -> parse -> aggregate``. Individual file
    failures are logged and skipped; only a failure to fetch the tree itself
    (which yields no analyzable files) results in the empty snapshot.
    """
    try:
        tree = await fetch_repo_tree(owner, repo, token)
    except Exception as exc:  # noqa: BLE001 - a tree failure means an empty repo view
        logger.error("Failed to fetch tree for %s/%s: %s", owner, repo, exc)
        return _empty_summary()

    targets = select_analysis_targets(tree or [])
    if not targets:
        return _empty_summary()

    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    tasks = [
        _fetch_and_analyze(owner, repo, token, entry, semaphore)
        for entry in targets
    ]
    # return_exceptions=True is belt-and-suspenders: _fetch_and_analyze already
    # swallows its own errors, but this guarantees gather never propagates.
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    results: list[_FileAnalysis] = []
    for item in raw_results:
        if isinstance(item, _FileAnalysis):
            results.append(item)
        elif isinstance(item, BaseException):
            logger.warning("Unhandled per-file exception was suppressed: %s", item)

    return _aggregate(results)


# Re-exported for callers that want the category list (e.g. scoring layer).
__all__ = [
    "analyze_repository",
    "analyze_source",
    "MAX_CONCURRENCY",
    "ADVANCED_LIBS",
    "LIB_CATEGORY",
]
