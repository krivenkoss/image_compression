"""Smoke tests for metrics.py."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from metrics import compute_metrics, psnr, mse, ssim, METRIC_FUNCS
from visualization import axis_label

RNG = np.random.default_rng(0)
IMG_A = RNG.integers(0, 256, (64, 64), dtype=np.uint8)
IMG_B = RNG.integers(0, 256, (64, 64), dtype=np.uint8)


def test_psnr_identical_is_inf():
    assert math.isinf(psnr(IMG_A, IMG_A))


def test_mse_identical_is_zero():
    assert mse(IMG_A, IMG_A) == 0.0


def test_compute_metrics_keys_and_finite():
    names = ["psnr", "mse", "ssim"]
    result = compute_metrics(IMG_A, IMG_A, names)
    assert set(result.keys()) == set(names)
    for k, v in result.items():
        if k == "psnr":
            assert math.isinf(v)
        else:
            assert math.isfinite(v), f"{k} is not finite"


def test_compute_metrics_unknown_raises():
    with pytest.raises(KeyError):
        compute_metrics(IMG_A, IMG_B, ["nonexistent_metric"])


def test_metric_funcs_not_empty():
    assert len(METRIC_FUNCS) >= 7


def test_axis_label_db_units():
    assert axis_label("psnr") == "PSNR, dB"
    assert axis_label("psnr_hvs_m") == "PSNR-HVS-M, dB"
    assert axis_label("ssim") == "SSIM"
    assert axis_label("cr") == "Compression ratio"


def test_axis_label_fallback():
    assert axis_label("some_new_metric") == "SOME_NEW_METRIC"
