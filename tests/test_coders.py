"""Smoke tests for coders.py."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from coders import compress, DEFAULT_RANGES

RNG = np.random.default_rng(2)
IMG_GRAY = RNG.integers(0, 256, (64, 64), dtype=np.uint8)
IMG_COLOR = RNG.integers(0, 256, (64, 64, 3), dtype=np.uint8)


def test_jpeg_grayscale_shape_and_cr():
    decoded, cr = compress(IMG_GRAY, "JPEG", 75)
    assert decoded.shape == IMG_GRAY.shape
    assert decoded.dtype == np.uint8
    assert cr > 1.0


def test_jpeg_colour_shape():
    decoded, cr = compress(IMG_COLOR, "JPEG", 75)
    assert decoded.shape == IMG_COLOR.shape
    assert cr > 1.0


def test_jpeg2000_grayscale():
    decoded, cr = compress(IMG_GRAY, "JPEG2000", 10.0)
    assert decoded.shape == IMG_GRAY.shape
    assert cr > 1.0


def test_default_ranges_complete():
    required = {"AGU", "AGUm", "ADCT", "ADCTm", "BPG", "JPEG2000", "JPEG", "HEIF", "AVIF"}
    assert required.issubset(DEFAULT_RANGES)


def test_unknown_coder_raises():
    with pytest.raises(ValueError):
        compress(IMG_GRAY, "NONEXISTENT", 50)


# ---------------------------------------------------------------------------
# Proprietary coders — skipped when binary is absent
# ---------------------------------------------------------------------------

def _has_exe(name: str) -> bool:
    return shutil.which(name) is not None or (Path("coders") / name).exists()


@pytest.mark.skipif(not _has_exe("bpgenc.exe"), reason="bpgenc.exe not installed")
def test_bpg_grayscale():
    decoded, cr = compress(IMG_GRAY, "BPG", 30)
    assert decoded.shape == IMG_GRAY.shape
    assert cr > 1.0


# AGU / ADCT executables require exactly 512×512 input
_IMG_512 = np.random.default_rng(99).integers(0, 256, (512, 512), dtype=np.uint8)


@pytest.mark.skipif(not _has_exe("AGU.exe"), reason="AGU.exe not installed")
def test_agu_grayscale():
    decoded, cr = compress(_IMG_512, "AGU", 10)
    assert decoded.shape == _IMG_512.shape
    assert cr > 1.0


@pytest.mark.skipif(not _has_exe("ADCT.exe"), reason="ADCT.exe not installed")
def test_adct_grayscale():
    decoded, cr = compress(_IMG_512, "ADCT", 10)
    assert decoded.shape == _IMG_512.shape
    assert cr > 1.0


def test_heif_grayscale():
    """HEIF is handled in-memory via pillow_heif — no external binary needed."""
    pytest.importorskip("pillow_heif")
    decoded, cr = compress(IMG_GRAY, "HEIF", 50)
    assert decoded.shape == IMG_GRAY.shape
    assert decoded.dtype == np.uint8
    assert cr > 1.0


def test_avif_grayscale():
    """AVIF is handled in-memory via pillow_heif — no external binary needed."""
    pytest.importorskip("pillow_heif")
    decoded, cr = compress(IMG_GRAY, "AVIF", 50)
    assert decoded.shape == IMG_GRAY.shape
    assert decoded.dtype == np.uint8
    assert cr > 1.0
