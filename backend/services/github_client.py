"""
Astra capability engine — GitHub REST/Git-data client.

The capability engine consumes two functions from this module:

* :func:`fetch_repo_tree` — the repository file tree via the Git Trees API
  (recursive), returning ``[{path, sha, size, type}, ...]``.
* :func:`fetch_file_blob` — a single blob's decoded UTF-8 text via the Git Blobs
  API (base64 payload decoded here).

Both are ``async`` and use a shared :class:`httpx.AsyncClient` so the engine can
fan blob fetches out with :func:`asyncio.gather` under a concurrency semaphore.

Network access is optional at import time: ``httpx`` is imported lazily so the
pure-analysis modules and their tests do not require it to be installed.
"""

from __future__ import annotations

import base64
from typing import Any

_GITHUB_API = "https://api.github.com"
_API_VERSION = "2022-11-28"
_DEFAULT_TIMEOUT = 20.0


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": _API_VERSION,
        "User-Agent": "astra-capability-engine",
    }


def _decode_blob_content(payload: dict[str, Any]) -> str:
    """Decode a Git Blobs API payload to text.

    GitHub returns ``content`` base64-encoded (with embedded newlines) when
    ``encoding == "base64"``; other encodings are returned verbatim.
    """
    encoding = payload.get("encoding")
    content = payload.get("content", "")
    if encoding == "base64":
        raw = base64.b64decode(content)
        return raw.decode("utf-8", errors="replace")
    return content if isinstance(content, str) else ""


async def _get_json(url: str, token: str, params: dict | None = None) -> dict:
    import httpx

    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
        response = await client.get(url, headers=_headers(token), params=params)
        response.raise_for_status()
        return response.json()


async def fetch_repo_tree(owner: str, repo: str, token: str) -> list[dict]:
    """Return the recursive file tree for the repository's default branch.

    Each element is a dict with at least ``path``, ``sha``, ``size`` (blobs
    only), and ``type`` (``"blob"`` or ``"tree"``), matching the shape the file
    selector expects.
    """
    # Resolve the default branch, then its commit tree SHA, then the recursive
    # tree. Two hops keep us correct for repos whose default branch is not main.
    repo_meta = await _get_json(f"{_GITHUB_API}/repos/{owner}/{repo}", token)
    default_branch = repo_meta.get("default_branch", "main")

    branch = await _get_json(
        f"{_GITHUB_API}/repos/{owner}/{repo}/branches/{default_branch}", token
    )
    tree_sha = branch["commit"]["commit"]["tree"]["sha"]

    tree_payload = await _get_json(
        f"{_GITHUB_API}/repos/{owner}/{repo}/git/trees/{tree_sha}",
        token,
        params={"recursive": "1"},
    )
    return tree_payload.get("tree", [])


async def fetch_file_blob(owner: str, repo: str, sha: str, token: str) -> str:
    """Fetch and base64-decode a single blob's raw text by its git SHA."""
    payload = await _get_json(
        f"{_GITHUB_API}/repos/{owner}/{repo}/git/blobs/{sha}", token
    )
    return _decode_blob_content(payload)
