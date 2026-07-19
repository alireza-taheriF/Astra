"""
Tests for the Astra capability engine.

These tests exercise the deterministic pipeline end-to-end without touching the
network: the GitHub client functions are monkeypatched with in-memory fakes so
``analyze_repository`` runs against fixture repositories. Unit-level tests cover
the individual parsers and the file selector.

Required scenarios (per spec) are all present:

* pure boilerplate detection            -> test_pure_boilerplate_detection
* triton kernel detection               -> test_triton_kernel_detection
* mixed-language repo                    -> test_mixed_language_repository
* syntactically broken file (no crash)  -> test_broken_file_does_not_crash_batch
* empty repo edge case                   -> test_empty_repository
"""

from __future__ import annotations

import asyncio

import pytest

from services import capability_engine
from services.ast_parser import PythonParser, TreeSitterParser, get_parser
from services.capability_engine import analyze_repository, analyze_source
from services.file_selector import (
    MAX_FILES_PER_REPO,
    select_analysis_targets,
)
from services.library_registry import detect_deep_usage


# ---------------------------------------------------------------------------
# Fake GitHub backend
# ---------------------------------------------------------------------------
class FakeRepo:
    """An in-memory repository: maps blob sha -> source text, builds a tree."""

    def __init__(self, files: dict[str, str]) -> None:
        # files: path -> source. sha is synthesized deterministically.
        self.files = files
        self.tree = []
        for path, source in files.items():
            sha = f"sha-{path}"
            self.tree.append(
                {
                    "path": path,
                    "sha": sha,
                    "size": len(source.encode("utf-8")),
                    "type": "blob",
                }
            )
        self._by_sha = {f"sha-{path}": source for path, source in files.items()}

    async def fetch_repo_tree(self, owner, repo, token):
        return list(self.tree)

    async def fetch_file_blob(self, owner, repo, sha, token):
        return self._by_sha[sha]


@pytest.fixture
def patch_github(monkeypatch):
    """Return a helper that wires a FakeRepo into the engine's client calls."""

    def _install(files: dict[str, str]) -> FakeRepo:
        fake = FakeRepo(files)
        monkeypatch.setattr(capability_engine, "fetch_repo_tree", fake.fetch_repo_tree)
        monkeypatch.setattr(capability_engine, "fetch_file_blob", fake.fetch_file_blob)
        return fake

    return _install


# ---------------------------------------------------------------------------
# Source fixtures
# ---------------------------------------------------------------------------
BOILERPLATE_INIT = '''"""Package init — pure re-export shim."""
from .core import thing
from .other import stuff

__all__ = ["thing", "stuff"]
'''

GENERATED_FILE = """# This file was automatically generated. DO NOT EDIT.
CONFIG = {"a": 1, "b": 2}
"""

TRITON_KERNEL = '''
import triton
import triton.language as tl
import torch


@triton.jit
def softmax_kernel(out_ptr, in_ptr, n_cols, BLOCK_SIZE: tl.constexpr):
    row = tl.program_id(0)
    offsets = tl.arange(0, BLOCK_SIZE)
    mask = offsets < n_cols
    x = tl.load(in_ptr + row * n_cols + offsets, mask=mask)
    if row > 0 and n_cols > 1:
        x = x - tl.max(x, axis=0)
    numerator = tl.exp(x)
    denom = tl.sum(numerator, axis=0)
    tl.store(out_ptr + row * n_cols + offsets, numerator / denom, mask=mask)


class SquareFn(torch.autograd.Function):
    @staticmethod
    def forward(ctx, x):
        ctx.save_for_backward(x)
        return x * x

    @staticmethod
    def backward(ctx, grad):
        (x,) = ctx.saved_tensors
        return grad * 2 * x
'''

TORCH_API_USAGE = '''
import torch
import torch.nn as nn


class MLP(nn.Module):
    def __init__(self, dim):
        super().__init__()
        self.fc1 = nn.Linear(dim, dim)
        self.fc2 = nn.Linear(dim, dim)

    def forward(self, x):
        x = torch.relu(self.fc1(x))
        if x.sum() > 0:
            x = torch.dropout(x, 0.1, self.training)
        return self.fc2(x)
'''

CUDA_KERNEL = """
#include <cuda_runtime.h>

__global__ void saxpy(int n, float a, float* x, float* y) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < n && a > 0.0f) {
        y[i] = a * x[i] + y[i];
    }
    for (int k = 0; k < n; ++k) {
        while (k > 0 || i < 0) { break; }
    }
}
"""

TS_SERVICE = """
import express from 'express';

export function build(): number {
    const app = express();
    let total = 0;
    for (let i = 0; i < 10; i++) {
        if (i % 2 === 0 && i > 0) {
            total += i;
        }
    }
    return total > 5 ? total : 0;
}
"""

BROKEN_PYTHON = """
import torch

def broken(:
    this is not valid python at all !!!
    for x in
"""

PLAIN_NUMPY = """
import numpy as np

def normalize(v):
    m = np.mean(v)
    s = np.std(v)
    return (v - m) / s
"""


# ---------------------------------------------------------------------------
# Parser / registry unit tests
# ---------------------------------------------------------------------------
def test_python_cyclomatic_complexity_mccabe():
    # base 1 + if(1) + for(1) + boolop `a and b`(+1) = 4
    src = "def f(x, a, b):\n    if a and b:\n        for i in x:\n            pass\n"
    p = PythonParser(src)
    assert p.cyclomatic_complexity() == 4


def test_boolop_counts_len_values_minus_one():
    # `a and b and c` => +2 over base 1 => 3
    assert PythonParser("y = a and b and c\n").cyclomatic_complexity() == 3


def test_file_selector_filters_and_caps():
    tree = [
        {"path": "src/main.py", "sha": "1", "size": 100, "type": "blob"},
        {"path": "node_modules/dep/index.js", "sha": "2", "size": 50, "type": "blob"},
        {"path": "vendor/lib.cpp", "sha": "3", "size": 50, "type": "blob"},
        {"path": "dist/bundle.js", "sha": "4", "size": 50, "type": "blob"},
        {"path": "tests/__fixtures__/big.py", "sha": "5", "size": 50, "type": "blob"},
        {"path": "huge.py", "sha": "6", "size": 300_000, "type": "blob"},
        {"path": "README.md", "sha": "7", "size": 10, "type": "blob"},
        {"path": "a/b/c/deep.py", "sha": "8", "size": 10, "type": "blob"},
        {"path": "docs", "sha": "9", "type": "tree"},
    ]
    selected = select_analysis_targets(tree)
    paths = [e["path"] for e in selected]
    assert "src/main.py" in paths
    assert "a/b/c/deep.py" in paths
    # excluded / oversized / unsupported / dirs are all gone
    for gone in (
        "node_modules/dep/index.js",
        "vendor/lib.cpp",
        "dist/bundle.js",
        "tests/__fixtures__/big.py",
        "huge.py",
        "README.md",
        "docs",
    ):
        assert gone not in paths
    # src/ file is prioritized ahead of the deeply-nested one
    assert paths.index("src/main.py") < paths.index("a/b/c/deep.py")


def test_file_selector_respects_cap():
    tree = [
        {"path": f"src/mod_{i}.py", "sha": str(i), "size": 100, "type": "blob"}
        for i in range(MAX_FILES_PER_REPO + 25)
    ]
    assert len(select_analysis_targets(tree)) == MAX_FILES_PER_REPO


# ---------------------------------------------------------------------------
# Required scenario 1: pure boilerplate detection
# ---------------------------------------------------------------------------
def test_pure_boilerplate_detection():
    assert PythonParser(BOILERPLATE_INIT).is_boilerplate() is True
    assert PythonParser(GENERATED_FILE).is_boilerplate() is True
    assert PythonParser("").is_boilerplate() is True
    # A file with real logic is NOT boilerplate.
    assert PythonParser(PLAIN_NUMPY).is_boilerplate() is False


# ---------------------------------------------------------------------------
# Required scenario 2: triton kernel detection
# ---------------------------------------------------------------------------
def test_triton_kernel_detection():
    parser = get_parser("kernels/softmax.py", TRITON_KERNEL)
    signals = detect_deep_usage(parser, TRITON_KERNEL)

    assert "triton" in signals
    assert signals["triton"]["depth"] == "kernel_authoring"
    # base 5.0 * 2x multiplier
    assert signals["triton"]["weight"] == pytest.approx(10.0)

    # torch.autograd.Function subclass also flags kernel authoring for torch.
    assert signals["torch"]["depth"] == "kernel_authoring"
    assert signals["torch"]["weight"] == pytest.approx(6.0)


def test_torch_api_usage_not_kernel():
    parser = get_parser("model.py", TORCH_API_USAGE)
    signals = detect_deep_usage(parser, TORCH_API_USAGE)
    assert signals["torch"]["depth"] == "api_usage"
    assert signals["torch"]["weight"] == pytest.approx(3.0)  # base * 1x


def test_import_only_downweighted():
    src = "import pandas\n\nx = 1\n"
    parser = get_parser("m.py", src)
    signals = detect_deep_usage(parser, src)
    assert signals["pandas"]["depth"] == "import_only"
    assert signals["pandas"]["weight"] == pytest.approx(0.2)  # 1.0 * 0.2


def test_cuda_kernel_authoring_detected():
    parser = get_parser("saxpy.cu", CUDA_KERNEL)
    signals = detect_deep_usage(parser, CUDA_KERNEL)
    assert signals["cuda"]["depth"] == "kernel_authoring"
    assert signals["cuda"]["weight"] == pytest.approx(8.0)  # base 4.0 * 2x


# ---------------------------------------------------------------------------
# Required scenario 4 (unit): a broken file must not crash analysis
# ---------------------------------------------------------------------------
def test_analyze_source_returns_none_on_syntax_error():
    assert analyze_source("broken.py", BROKEN_PYTHON) is None


# ---------------------------------------------------------------------------
# Engine-level async tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_empty_repository(patch_github):
    """Required scenario 5: empty repo edge case."""
    patch_github({})
    summary = await analyze_repository("acme", "empty", "token")

    assert summary["files_analyzed"] == 0
    assert summary["avg_cyclomatic_complexity"] == 0.0
    assert summary["max_ast_depth"] == 0
    assert summary["library_signals"] == {}
    assert summary["boilerplate_ratio"] == 0.0
    assert summary["subscore_contributions"] == {
        "ml_infra": 0.0,
        "systems": 0.0,
        "data": 0.0,
        "web": 0.0,
    }
    # Snapshot is JSON-serializable and carries a timestamp.
    assert isinstance(summary["analyzed_at"], str)


@pytest.mark.asyncio
async def test_repository_with_only_unsupported_files(patch_github):
    patch_github({"README.md": "# hi", "data.csv": "a,b,c"})
    summary = await analyze_repository("acme", "docs", "token")
    assert summary["files_analyzed"] == 0


@pytest.mark.asyncio
async def test_triton_repo_end_to_end(patch_github):
    patch_github(
        {
            "src/kernels/softmax.py": TRITON_KERNEL,
            "src/models/mlp.py": TORCH_API_USAGE,
        }
    )
    summary = await analyze_repository("acme", "ml", "token")

    assert summary["files_analyzed"] == 2
    assert summary["avg_cyclomatic_complexity"] > 1.0
    assert summary["max_ast_depth"] > 1

    signals = summary["library_signals"]
    assert signals["triton"]["depth"] == "kernel_authoring"
    assert signals["triton"]["file_count"] == 1
    # torch appears in both files; deepest usage (kernel_authoring) wins.
    assert signals["torch"]["depth"] == "kernel_authoring"
    assert signals["torch"]["file_count"] == 2

    # ml_infra category accumulates the weighted contributions.
    assert summary["subscore_contributions"]["ml_infra"] > 0.0
    assert summary["subscore_contributions"]["web"] == 0.0


@pytest.mark.asyncio
async def test_mixed_language_repository(patch_github):
    """Required scenario 3: a repo spanning Python, C++/CUDA, and TypeScript."""
    patch_github(
        {
            "src/model.py": TORCH_API_USAGE,
            "csrc/saxpy.cu": CUDA_KERNEL,
            "web/service.ts": TS_SERVICE,
            "pkg/__init__.py": BOILERPLATE_INIT,
        }
    )
    summary = await analyze_repository("acme", "mixed", "token")

    assert summary["files_analyzed"] == 4

    signals = summary["library_signals"]
    assert signals["torch"]["depth"] == "api_usage"
    assert signals["cuda"]["depth"] == "kernel_authoring"
    assert signals["express"]["file_count"] == 1

    contributions = summary["subscore_contributions"]
    assert contributions["ml_infra"] > 0.0   # torch
    assert contributions["systems"] > 0.0    # cuda
    assert contributions["web"] > 0.0        # express

    # Exactly one of the four files is boilerplate (the __init__.py).
    assert summary["boilerplate_ratio"] == pytest.approx(0.25)


@pytest.mark.asyncio
async def test_broken_file_does_not_crash_batch(patch_github):
    """Required scenario 4: a syntactically broken file is skipped, not fatal."""
    patch_github(
        {
            "src/good.py": TORCH_API_USAGE,
            "src/broken.py": BROKEN_PYTHON,
            "src/also_good.py": PLAIN_NUMPY,
        }
    )
    summary = await analyze_repository("acme", "flaky", "token")

    # Two parseable files survive; the broken one is skipped.
    assert summary["files_analyzed"] == 2
    assert "torch" in summary["library_signals"]
    assert "numpy" in summary["library_signals"]


@pytest.mark.asyncio
async def test_blob_fetch_failure_is_isolated(patch_github):
    fake = patch_github({"src/a.py": PLAIN_NUMPY, "src/b.py": TORCH_API_USAGE})

    original = fake.fetch_file_blob

    async def flaky_blob(owner, repo, sha, token):
        if sha == "sha-src/a.py":
            raise RuntimeError("simulated GitHub 502")
        return await original(owner, repo, sha, token)

    # Re-patch with the flaky wrapper.
    capability_engine.fetch_file_blob = flaky_blob
    try:
        summary = await analyze_repository("acme", "flaky-net", "token")
    finally:
        capability_engine.fetch_file_blob = original

    # Only the healthy blob is analyzed; the failing fetch is skipped.
    assert summary["files_analyzed"] == 1
    assert "torch" in summary["library_signals"]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
