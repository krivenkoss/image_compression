"""Smoke tests for noise.py."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from noise import NOISE_FUNCS, apply_noise

RNG = np.random.default_rng(1)
IMG = RNG.integers(0, 256, (64, 64), dtype=np.uint8)

# Parameters required by each noise kind
_PARAMS: dict[str, dict] = {
    "gaussian":              {"std": 10},
    "uniform":               {"low": -10, "high": 10},
    "speckle":               {"std": 0.1},
    "poisson":               {"scale": 1.0},
    "mixed_poisson_gaussian": {"k": 0.271, "sigma0": 23.74},
    "correlated_gaussian":   {"std": 10, "kernel": "gauss", "radius": 2},
    "ar1":                   {"std": 10, "rho_h": 0.7, "rho_v": 0.7},
}


@pytest.mark.parametrize("kind", list(NOISE_FUNCS))
def test_shape_and_dtype_preserved(kind: str):
    params = _PARAMS.get(kind, {})
    out = NOISE_FUNCS[kind](IMG, **params, seed=0)
    assert out.shape == IMG.shape, f"{kind}: shape mismatch"
    assert out.dtype == np.uint8, f"{kind}: dtype is {out.dtype}"


def test_gaussian_reproducible():
    a = apply_noise(IMG, "gaussian", std=10, seed=42)
    b = apply_noise(IMG, "gaussian", std=10, seed=42)
    np.testing.assert_array_equal(a, b)


def test_gaussian_different_seeds():
    a = apply_noise(IMG, "gaussian", std=10, seed=1)
    b = apply_noise(IMG, "gaussian", std=10, seed=2)
    assert not np.array_equal(a, b)


def test_unknown_kind_raises():
    with pytest.raises(KeyError):
        apply_noise(IMG, "nonexistent_noise", std=5)
