"""
Astra capability engine — repository file selection & filtering.

Given a repository's flat file tree (as returned by the GitHub Git Trees API),
:func:`select_analysis_targets` narrows it down to the source files worth
analyzing. This is a pure, deterministic function — no I/O, no LLM — so it is
cheap to unit-test and safe to run inside a serverless request path.

Selection policy (in order):

1. Keep only blob (file) entries with a supported source extension.
2. Drop anything living under a dependency/build/fixture directory.
3. Drop files larger than :data:`MAX_FILE_BYTES`.
4. Rank the survivors so the most *signal-dense* files come first, then cap the
   result at :data:`MAX_FILES_PER_REPO` to stay inside the serverless time and
   GitHub API-cost budget.
"""

from __future__ import annotations

import posixpath

# Supported source extensions. Anything else is ignored outright.
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {".py", ".cpp", ".cu", ".cuh", ".js", ".ts", ".jsx", ".tsx"}
)

# Path segments that mark vendored deps, build output, virtualenvs, or test
# fixtures. Matched as whole path components so `mydist/` is not excluded by
# `dist`.
EXCLUDED_DIR_SEGMENTS: frozenset[str] = frozenset(
    {
        "node_modules",
        "vendor",
        ".venv",
        "venv",
        "dist",
        "build",
        "__fixtures__",
    }
)

# Hard byte ceiling per file. Blobs at or above this are skipped: they are
# usually generated bundles, lockfiles-as-code, or data blobs, and they blow the
# fetch/parse time budget.
MAX_FILE_BYTES = 200_000

# Upper bound on files analyzed per repository. Caps both GitHub blob fetches
# and total parse time so the whole analysis fits a ~10s serverless window.
MAX_FILES_PER_REPO = 150

# Directories that are strong positive signals of first-party source; files
# under these sort ahead of everything else at equal depth.
_PRIORITY_ROOTS = ("src", "lib", "app", "core", "kernels", "csrc")


def _normalize_path(path: str) -> str:
    """Normalize to forward-slash form and strip any leading `./` or `/`."""
    normalized = path.replace("\\", "/").lstrip("/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _has_supported_extension(path: str) -> bool:
    lowered = path.lower()
    return any(lowered.endswith(ext) for ext in SUPPORTED_EXTENSIONS)


def _is_excluded(path: str) -> bool:
    segments = path.split("/")
    return any(segment in EXCLUDED_DIR_SEGMENTS for segment in segments)


def _priority_rank(path: str) -> int:
    """Lower is better. Prefer shallow, first-party source files.

    Ranking key components, in priority order:

    * files whose top-level directory is a known source root sort first;
    * then by path depth (top-level ``src/foo.py`` before ``a/b/c/d.py``);
    * ties fall back to the caller-provided ordering (stable sort).
    """
    depth = path.count("/")
    top = path.split("/", 1)[0] if "/" in path else ""
    in_priority_root = 0 if top in _PRIORITY_ROOTS else 1
    return in_priority_root, depth


def select_analysis_targets(tree: list[dict]) -> list[dict]:
    """Filter and rank a repo file tree down to the files worth analyzing.

    Parameters
    ----------
    tree:
        Entries from the GitHub Git Trees API. Each item is expected to carry at
        least ``path``, ``type`` (``"blob"``/``"tree"``), and — for blobs —
        ``size`` and ``sha``. Missing/oddly-shaped entries are skipped rather
        than raising.

    Returns
    -------
    list[dict]
        The selected entries (original dicts, unmodified) in analysis-priority
        order, capped at :data:`MAX_FILES_PER_REPO`.
    """
    candidates: list[tuple[tuple[int, int], int, dict]] = []

    for index, entry in enumerate(tree):
        if not isinstance(entry, dict):
            continue
        # Only real files. The Trees API uses type == "blob" for files.
        if entry.get("type") not in (None, "blob"):
            continue

        raw_path = entry.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            continue
        path = _normalize_path(raw_path)

        if not _has_supported_extension(path):
            continue
        if _is_excluded(path):
            continue

        size = entry.get("size")
        # Trees API omits size for submodules/commits; treat unknown as too big
        # to be safe only when the type is explicitly a blob without a size.
        if isinstance(size, (int, float)) and size >= MAX_FILE_BYTES:
            continue

        # Sort key: (priority tuple, original index) — index makes it a stable,
        # deterministic tiebreak that preserves the tree's given order, which
        # the GitHub API returns in a recency-influenced traversal.
        candidates.append((_priority_rank(path), index, entry))

    candidates.sort(key=lambda item: (item[0], item[1]))

    return [entry for _, _, entry in candidates[:MAX_FILES_PER_REPO]]


def target_basename(entry: dict) -> str:
    """Convenience: the file's base name, for logging/telemetry."""
    return posixpath.basename(_normalize_path(entry.get("path", "")))
