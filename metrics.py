"""Image quality metrics.

All functions accept 2-D (grayscale) or 3-D (H x W x C, BGR uint8) numpy
arrays. For grayscale-only back-ends the input is converted to luma (BT.601
coefficients) before the computation.
"""
from __future__ import annotations

import logging
import math
from collections.abc import Callable, Iterable

import numpy as np
import sewar.full_ref as _sewar
from psnr_hvsm import psnr_hvs_hvsm as _psnr_hvs_hvsm

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional piq / torch import
# ---------------------------------------------------------------------------
try:
    import torch as _torch
    import piq as _piq
    _PIQ_AVAILABLE = True
except Exception:
    logger.warning(
        "piq / torch not available; haar_psi, fsim, vsi, mdsi, gmsd will be excluded from METRIC_FUNCS."
    )
    _PIQ_AVAILABLE = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _to_gray(image: np.ndarray) -> np.ndarray:
    """Convert BGR uint8 3-D array to grayscale using BT.601 luma."""
    if image.ndim == 3:
        import cv2
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image


def _to_piq_tensor(image: np.ndarray, require_rgb: bool = False) -> "_torch.Tensor":
    """Convert HxW or HxWxC uint8 numpy to 1xCxHxW float32 tensor in [0, 1].

    When *require_rgb* is True and the input is grayscale, the single channel
    is repeated three times so that colour-only piq metrics (fsim, vsi, mdsi)
    receive a valid 3-channel input.
    """
    arr = image.astype(np.float32) / 255.0
    if arr.ndim == 2:
        t = _torch.from_numpy(arr).unsqueeze(0).unsqueeze(0)  # 1x1xHxW
        if require_rgb:
            t = t.repeat(1, 3, 1, 1)  # 1x3xHxW — replicate luma to R, G, B
    else:
        t = _torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)  # 1xCxHxW
    return t


# piq metrics that internally assert the input has 3 channels
_PIQ_REQUIRES_RGB = {"fsim", "vsi", "mdsi"}


# ---------------------------------------------------------------------------
# Individual metric functions
# ---------------------------------------------------------------------------

def mse(ref: np.ndarray, test: np.ndarray) -> float:
    """Mean Squared Error between two images.

    For colour inputs the arrays are converted to grayscale luma before
    comparison.

    Parameters
    ----------
    ref : np.ndarray
        Reference image, uint8, 2-D or 3-D (BGR).
    test : np.ndarray
        Distorted image, same shape and dtype as *ref*.

    Returns
    -------
    float
        MSE value (0 for identical images).

    Examples
    --------
    >>> import numpy as np
    >>> img = np.zeros((64, 64), dtype=np.uint8)
    >>> mse(img, img)
    0.0
    """
    return float(_sewar.mse(_to_gray(ref), _to_gray(test)))


def psnr(ref: np.ndarray, test: np.ndarray) -> float:
    """Peak Signal-to-Noise Ratio.

    For colour inputs the arrays are converted to grayscale luma before
    comparison. Returns ``float('inf')`` for identical images.

    Parameters
    ----------
    ref : np.ndarray
        Reference image, uint8, 2-D or 3-D (BGR).
    test : np.ndarray
        Distorted image.

    Returns
    -------
    float
        PSNR in dB, or ``inf`` when MSE == 0.

    Examples
    --------
    >>> import numpy as np, math
    >>> img = np.zeros((64, 64), dtype=np.uint8)
    >>> math.isinf(psnr(img, img))
    True
    """
    r, t = _to_gray(ref), _to_gray(test)
    err = float(_sewar.mse(r, t))
    if err == 0.0:
        return float("inf")
    return float(10.0 * math.log10(255.0 ** 2 / err))


def ssim(ref: np.ndarray, test: np.ndarray) -> float:
    """Structural Similarity Index (SSIM).

    For colour inputs the arrays are converted to grayscale luma before
    comparison.

    Parameters
    ----------
    ref : np.ndarray
        Reference image, uint8, 2-D or 3-D (BGR).
    test : np.ndarray
        Distorted image.

    Returns
    -------
    float
        SSIM in [−1, 1]; 1.0 for identical images.

    Examples
    --------
    >>> import numpy as np
    >>> img = np.ones((64, 64), dtype=np.uint8) * 128
    >>> round(ssim(img, img), 4)
    1.0
    """
    # sewar.ssim returns (mean_ssim, mean_cs) — take the first element
    return float(_sewar.ssim(_to_gray(ref), _to_gray(test))[0])


def ms_ssim(ref: np.ndarray, test: np.ndarray) -> float:
    """Multi-Scale Structural Similarity Index (MS-SSIM).

    For colour inputs the arrays are converted to grayscale luma before
    comparison.

    Parameters
    ----------
    ref : np.ndarray
        Reference image, uint8, 2-D or 3-D (BGR). Minimum size 160×160.
    test : np.ndarray
        Distorted image.

    Returns
    -------
    float
        MS-SSIM value (absolute value taken to handle sewar sign convention).

    Examples
    --------
    >>> import numpy as np
    >>> img = np.random.randint(0, 256, (256, 256), dtype=np.uint8)
    >>> ms_ssim(img, img) >= 0.99
    True
    """
    return float(abs(_sewar.msssim(_to_gray(ref), _to_gray(test))))


def uqi(ref: np.ndarray, test: np.ndarray) -> float:
    """Universal Quality Index (UQI).

    For colour inputs the arrays are converted to grayscale luma before
    comparison.

    Parameters
    ----------
    ref : np.ndarray
        Reference image, uint8, 2-D or 3-D (BGR).
    test : np.ndarray
        Distorted image.

    Returns
    -------
    float
        UQI value in [−1, 1]; 1.0 for identical images.

    Examples
    --------
    >>> import numpy as np
    >>> img = np.ones((64, 64), dtype=np.uint8) * 100
    >>> round(uqi(img, img), 4)
    1.0
    """
    return float(_sewar.uqi(_to_gray(ref), _to_gray(test)))


def psnr_hvs(ref: np.ndarray, test: np.ndarray) -> float:
    """PSNR-HVS (Human Visual System weighted PSNR).

    Operates on grayscale float32 images normalised to [0, 1].
    For colour inputs the arrays are converted to grayscale luma.

    Parameters
    ----------
    ref : np.ndarray
        Reference image, uint8, 2-D or 3-D (BGR).
    test : np.ndarray
        Distorted image.

    Returns
    -------
    float
        PSNR-HVS value in dB.

    Examples
    --------
    >>> import numpy as np
    >>> img = np.random.randint(0, 256, (64, 64), dtype=np.uint8)
    >>> psnr_hvs(img, img) > 50
    True
    """
    r = _to_gray(ref).astype(np.float32) / 255.0
    t = _to_gray(test).astype(np.float32) / 255.0
    hvs_val, _ = _psnr_hvs_hvsm(r, t)
    return float(hvs_val)


def psnr_hvs_m(ref: np.ndarray, test: np.ndarray) -> float:
    """PSNR-HVS-M (modified HVS-weighted PSNR).

    Operates on grayscale float32 images normalised to [0, 1].
    For colour inputs the arrays are converted to grayscale luma.

    Parameters
    ----------
    ref : np.ndarray
        Reference image, uint8, 2-D or 3-D (BGR).
    test : np.ndarray
        Distorted image.

    Returns
    -------
    float
        PSNR-HVS-M value in dB.

    Examples
    --------
    >>> import numpy as np
    >>> img = np.random.randint(0, 256, (64, 64), dtype=np.uint8)
    >>> psnr_hvs_m(img, img) > 50
    True
    """
    r = _to_gray(ref).astype(np.float32) / 255.0
    t = _to_gray(test).astype(np.float32) / 255.0
    _, hvsm_val = _psnr_hvs_hvsm(r, t)
    return float(hvsm_val)


def _piq_metric(name: str, ref: np.ndarray, test: np.ndarray) -> float:
    """Generic wrapper for piq metrics returning a scalar float."""
    fn = getattr(_piq, name)
    rgb = name in _PIQ_REQUIRES_RGB
    r = _to_piq_tensor(ref, require_rgb=rgb)
    t = _to_piq_tensor(test, require_rgb=rgb)
    return float(fn(r, t).item())


def haar_psi(ref: np.ndarray, test: np.ndarray) -> float:
    """HaarPSI perceptual similarity via piq.

    Parameters
    ----------
    ref : np.ndarray
        Reference image, uint8, 2-D or 3-D (BGR).
    test : np.ndarray
        Distorted image.

    Returns
    -------
    float
        HaarPSI value in [0, 1].

    Examples
    --------
    >>> import numpy as np
    >>> img = np.random.randint(0, 256, (64, 64), dtype=np.uint8)
    >>> haar_psi(img, img) > 0.9
    True
    """
    return _piq_metric("haarpsi", ref, test)


def fsim(ref: np.ndarray, test: np.ndarray) -> float:
    """Feature Similarity Index (FSIM) via piq.

    Parameters
    ----------
    ref : np.ndarray
        Reference image, uint8, 2-D or 3-D (BGR).
    test : np.ndarray
        Distorted image.

    Returns
    -------
    float
        FSIM value in [0, 1].

    Examples
    --------
    >>> import numpy as np
    >>> img = np.random.randint(0, 256, (64, 64), dtype=np.uint8)
    >>> fsim(img, img) > 0.9
    True
    """
    return _piq_metric("fsim", ref, test)


def vsi(ref: np.ndarray, test: np.ndarray) -> float:
    """Visual Saliency-based Index (VSI) via piq.

    Parameters
    ----------
    ref : np.ndarray
        Reference image, uint8, 2-D or 3-D (BGR).
    test : np.ndarray
        Distorted image.

    Returns
    -------
    float
        VSI value in [0, 1].

    Examples
    --------
    >>> import numpy as np
    >>> img = np.random.randint(0, 256, (64, 64), dtype=np.uint8)
    >>> vsi(img, img) > 0.9
    True
    """
    return _piq_metric("vsi", ref, test)


def mdsi(ref: np.ndarray, test: np.ndarray) -> float:
    """Mean Deviation Similarity Index (MDSI) via piq.

    Parameters
    ----------
    ref : np.ndarray
        Reference image, uint8, 2-D or 3-D (BGR).
    test : np.ndarray
        Distorted image.

    Returns
    -------
    float
        MDSI value (lower is more similar).

    Examples
    --------
    >>> import numpy as np
    >>> img = np.random.randint(0, 256, (64, 64, 3), dtype=np.uint8)
    >>> mdsi(img, img) < 0.01
    True
    """
    return _piq_metric("mdsi", ref, test)


def gmsd(ref: np.ndarray, test: np.ndarray) -> float:
    """Gradient Magnitude Similarity Deviation (GMSD) via piq.

    Parameters
    ----------
    ref : np.ndarray
        Reference image, uint8, 2-D or 3-D (BGR).
    test : np.ndarray
        Distorted image.

    Returns
    -------
    float
        GMSD value (lower is more similar).

    Examples
    --------
    >>> import numpy as np
    >>> img = np.random.randint(0, 256, (64, 64), dtype=np.uint8)
    >>> gmsd(img, img) < 0.01
    True
    """
    return _piq_metric("gmsd", ref, test)


# ---------------------------------------------------------------------------
# Public registry
# ---------------------------------------------------------------------------

METRIC_FUNCS: dict[str, Callable] = {
    "mse": mse,
    "psnr": psnr,
    "ssim": ssim,
    "ms_ssim": ms_ssim,
    "uqi": uqi,
    "psnr_hvs": psnr_hvs,
    "psnr_hvs_m": psnr_hvs_m,
}

if _PIQ_AVAILABLE:
    METRIC_FUNCS.update(
        {
            "haar_psi": haar_psi,
            "fsim": fsim,
            "vsi": vsi,
            "mdsi": mdsi,
            "gmsd": gmsd,
        }
    )


def compute_metrics(
    ref: np.ndarray,
    test: np.ndarray,
    names: Iterable[str],
) -> dict[str, float]:
    """Compute a set of named metrics between two images.

    Parameters
    ----------
    ref : np.ndarray
        Reference image, uint8, 2-D or 3-D (BGR).
    test : np.ndarray
        Distorted image.
    names : Iterable[str]
        Metric names; must be keys of :data:`METRIC_FUNCS`.

    Returns
    -------
    dict[str, float]
        Mapping of metric name -> value.

    Raises
    ------
    KeyError
        If a requested metric name is not in :data:`METRIC_FUNCS`.

    Examples
    --------
    >>> import numpy as np
    >>> img = np.ones((64, 64), dtype=np.uint8) * 128
    >>> result = compute_metrics(img, img, ["psnr", "mse", "ssim"])
    >>> list(result.keys())
    ['psnr', 'mse', 'ssim']
    """
    results: dict[str, float] = {}
    for name in names:
        if name not in METRIC_FUNCS:
            raise KeyError(
                f"Unknown metric '{name}'. Available: {sorted(METRIC_FUNCS)}"
            )
        results[name] = METRIC_FUNCS[name](ref, test)
    return results
