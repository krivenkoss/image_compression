"""Noise injection functions for image quality research.

Each function accepts a uint8 numpy array (2-D grayscale or 3-D H×W×C) and
returns a uint8 array of the same shape. Intensity range is always clipped to
[0, 255] after the noise is added.
"""
from __future__ import annotations

import logging
from collections.abc import Callable

import numpy as np
from skimage import img_as_float, img_as_ubyte
from skimage.util import random_noise

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _apply_per_channel(
    image: np.ndarray,
    fn: Callable[[np.ndarray], np.ndarray],
    per_channel: bool,
) -> np.ndarray:
    """Apply *fn* either jointly or independently per colour channel."""
    if image.ndim == 2 or not per_channel:
        return fn(image)
    channels = [fn(image[:, :, c]) for c in range(image.shape[2])]
    return np.stack(channels, axis=2)


def _clip_uint8(arr: np.ndarray) -> np.ndarray:
    return np.clip(arr, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# Noise functions
# ---------------------------------------------------------------------------

def gaussian(
    image: np.ndarray,
    std: float,
    mean: float = 0.0,
    seed: int | None = None,
    per_channel: bool = True,
) -> np.ndarray:
    """Additive Gaussian noise (ported from legacy ``noising_scimage``).

    Uses ``skimage.util.random_noise`` with ``mode='gaussian'``. The *std*
    parameter is expressed in the uint8 range [0, 255]; internally it is
    normalised to [0, 1] before calling skimage.

    Parameters
    ----------
    image : np.ndarray
        Input image, uint8, 2-D or 3-D.
    std : float
        Standard deviation in pixel intensity units [0, 255].
    mean : float
        Mean of the Gaussian distribution (default 0).
    seed : int or None
        Random seed for reproducibility.
    per_channel : bool
        Apply independently per colour channel when True (default).

    Returns
    -------
    np.ndarray
        Noisy image, uint8, same shape as *image*.

    Examples
    --------
    >>> import numpy as np
    >>> img = np.zeros((64, 64), dtype=np.uint8)
    >>> out = gaussian(img, std=10, seed=42)
    >>> out.dtype == np.uint8 and out.shape == img.shape
    True
    """
    std_norm = std / 255.0
    mean_norm = mean / 255.0

    def _add(ch: np.ndarray) -> np.ndarray:
        noisy = random_noise(
            img_as_float(ch),
            mode="gaussian",
            seed=seed,
            mean=mean_norm,
            var=std_norm ** 2,
        )
        return img_as_ubyte(noisy)

    return _apply_per_channel(image, _add, per_channel)


def uniform(
    image: np.ndarray,
    low: float,
    high: float,
    seed: int | None = None,
    per_channel: bool = True,
) -> np.ndarray:
    """Additive uniform noise in [low, high] (pixel intensity units).

    Parameters
    ----------
    image : np.ndarray
        Input image, uint8, 2-D or 3-D.
    low : float
        Lower bound of uniform noise amplitude.
    high : float
        Upper bound of uniform noise amplitude.
    seed : int or None
        Random seed.
    per_channel : bool
        Apply independently per colour channel when True (default).

    Returns
    -------
    np.ndarray
        Noisy image, uint8, same shape as *image*.

    Examples
    --------
    >>> import numpy as np
    >>> img = np.full((64, 64), 128, dtype=np.uint8)
    >>> out = uniform(img, low=-10, high=10, seed=0)
    >>> out.dtype == np.uint8 and out.shape == img.shape
    True
    """
    rng = np.random.default_rng(seed)

    def _add(ch: np.ndarray) -> np.ndarray:
        noise = rng.uniform(low, high, ch.shape)
        return _clip_uint8(ch.astype(np.float32) + noise)

    return _apply_per_channel(image, _add, per_channel)


def speckle(
    image: np.ndarray,
    std: float,
    seed: int | None = None,
    per_channel: bool = True,
) -> np.ndarray:
    """Multiplicative (speckle) noise: ``out = image * (1 + N(0, std))``.

    Parameters
    ----------
    image : np.ndarray
        Input image, uint8, 2-D or 3-D.
    std : float
        Standard deviation of the multiplicative noise in normalised [0, 1].
    seed : int or None
        Random seed.
    per_channel : bool
        Apply independently per colour channel when True (default).

    Returns
    -------
    np.ndarray
        Noisy image, uint8, same shape as *image*.

    Examples
    --------
    >>> import numpy as np
    >>> img = np.full((64, 64), 100, dtype=np.uint8)
    >>> out = speckle(img, std=0.1, seed=7)
    >>> out.dtype == np.uint8 and out.shape == img.shape
    True
    """
    def _add(ch: np.ndarray) -> np.ndarray:
        noisy = random_noise(img_as_float(ch), mode="speckle", seed=seed, var=std ** 2)
        return img_as_ubyte(noisy)

    return _apply_per_channel(image, _add, per_channel)


def poisson(
    image: np.ndarray,
    scale: float = 1.0,
    seed: int | None = None,
    per_channel: bool = True,
) -> np.ndarray:
    """Signal-dependent Poisson noise.

    Parameters
    ----------
    image : np.ndarray
        Input image, uint8, 2-D or 3-D.
    scale : float
        Scaling factor applied before Poisson sampling (default 1.0).
        Values < 1 reduce effective photon count and increase noise.
    seed : int or None
        Random seed.
    per_channel : bool
        Apply independently per colour channel when True (default).

    Returns
    -------
    np.ndarray
        Noisy image, uint8, same shape as *image*.

    Examples
    --------
    >>> import numpy as np
    >>> img = np.full((64, 64), 150, dtype=np.uint8)
    >>> out = poisson(img, scale=1.0, seed=3)
    >>> out.dtype == np.uint8 and out.shape == img.shape
    True
    """
    rng = np.random.default_rng(seed)

    def _add(ch: np.ndarray) -> np.ndarray:
        scaled = ch.astype(np.float32) * scale
        noisy = rng.poisson(scaled).astype(np.float32) / max(scale, 1e-9)
        return _clip_uint8(noisy)

    return _apply_per_channel(image, _add, per_channel)


def mixed_poisson_gaussian(
    image: np.ndarray,
    k: float,
    sigma0: float,
    seed: int | None = None,
    per_channel: bool = True,
) -> np.ndarray:
    """Mixed Poisson-Gaussian noise: ``var = k * I + sigma0^2``.

    Models the noise typical in scientific imaging sensors.

    Parameters
    ----------
    image : np.ndarray
        Input image, uint8, 2-D or 3-D.
    k : float
        Poisson gain (variance per intensity unit).
    sigma0 : float
        Gaussian read-noise standard deviation (intensity units).
    seed : int or None
        Random seed.
    per_channel : bool
        Apply independently per colour channel when True (default).

    Returns
    -------
    np.ndarray
        Noisy image, uint8, same shape as *image*.

    Examples
    --------
    >>> import numpy as np
    >>> img = np.full((64, 64), 128, dtype=np.uint8)
    >>> out = mixed_poisson_gaussian(img, k=0.271, sigma0=23.74, seed=42)
    >>> out.dtype == np.uint8 and out.shape == img.shape
    True
    """
    rng = np.random.default_rng(seed)

    def _add(ch: np.ndarray) -> np.ndarray:
        f = ch.astype(np.float32)
        var = k * f + sigma0 ** 2
        noise = rng.normal(0.0, np.sqrt(np.maximum(var, 0.0)))
        return _clip_uint8(f + noise)

    return _apply_per_channel(image, _add, per_channel)


def correlated_gaussian(
    image: np.ndarray,
    std: float,
    kernel: str = "gauss",
    radius: int = 2,
    seed: int | None = None,
    per_channel: bool = True,
) -> np.ndarray:
    """Spatially correlated Gaussian noise convolved with a smoothing kernel.

    Parameters
    ----------
    image : np.ndarray
        Input image, uint8, 2-D or 3-D.
    std : float
        Target standard deviation of the correlated noise (pixel units).
    kernel : str
        Kernel type: ``"gauss"`` (Gaussian blur) or ``"box"`` (box blur).
    radius : int
        Kernel half-size in pixels (full kernel = 2*radius+1 per side).
    seed : int or None
        Random seed.
    per_channel : bool
        Apply independently per colour channel when True (default).

    Returns
    -------
    np.ndarray
        Noisy image, uint8, same shape as *image*.

    Examples
    --------
    >>> import numpy as np
    >>> img = np.zeros((64, 64), dtype=np.uint8)
    >>> out = correlated_gaussian(img, std=10, kernel="gauss", radius=2, seed=0)
    >>> out.dtype == np.uint8 and out.shape == img.shape
    True
    """
    import cv2

    ksize = 2 * radius + 1
    rng = np.random.default_rng(seed)

    def _add(ch: np.ndarray) -> np.ndarray:
        white = rng.standard_normal(ch.shape).astype(np.float32)
        if kernel == "gauss":
            blurred = cv2.GaussianBlur(white, (ksize, ksize), sigmaX=radius / 2.0)
        else:
            blurred = cv2.blur(white, (ksize, ksize))
        # Re-normalise to requested std
        s = blurred.std()
        if s > 1e-9:
            blurred = blurred * (std / s)
        return _clip_uint8(ch.astype(np.float32) + blurred)

    return _apply_per_channel(image, _add, per_channel)


def ar1(
    image: np.ndarray,
    std: float,
    rho_h: float = 0.7,
    rho_v: float = 0.7,
    seed: int | None = None,
    per_channel: bool = True,
) -> np.ndarray:
    """First-order autoregressive (AR-1) noise with horizontal and vertical correlation.

    Parameters
    ----------
    image : np.ndarray
        Input image, uint8, 2-D or 3-D.
    std : float
        Driving white-noise standard deviation (pixel units).
    rho_h : float
        Horizontal AR coefficient in (−1, 1).
    rho_v : float
        Vertical AR coefficient in (−1, 1).
    seed : int or None
        Random seed.
    per_channel : bool
        Apply independently per colour channel when True (default).

    Returns
    -------
    np.ndarray
        Noisy image, uint8, same shape as *image*.

    Examples
    --------
    >>> import numpy as np
    >>> img = np.zeros((64, 64), dtype=np.uint8)
    >>> out = ar1(img, std=10, rho_h=0.7, rho_v=0.7, seed=1)
    >>> out.dtype == np.uint8 and out.shape == img.shape
    True
    """
    rng = np.random.default_rng(seed)

    def _add(ch: np.ndarray) -> np.ndarray:
        H, W = ch.shape
        white = rng.standard_normal((H, W)).astype(np.float64) * std
        field = np.zeros((H, W), dtype=np.float64)
        # row-by-row AR-1 sweep (horizontal then vertical correlation)
        for r in range(H):
            for c in range(W):
                v_term = rho_v * field[r - 1, c] if r > 0 else 0.0
                h_term = rho_h * field[r, c - 1] if c > 0 else 0.0
                field[r, c] = v_term + h_term - rho_h * rho_v * (
                    field[r - 1, c - 1] if (r > 0 and c > 0) else 0.0
                ) + white[r, c]
        return _clip_uint8(ch.astype(np.float32) + field.astype(np.float32))

    return _apply_per_channel(image, _add, per_channel)


# ---------------------------------------------------------------------------
# Public registry
# ---------------------------------------------------------------------------

NOISE_FUNCS: dict[str, Callable] = {
    "gaussian": gaussian,
    "uniform": uniform,
    "speckle": speckle,
    "poisson": poisson,
    "mixed_poisson_gaussian": mixed_poisson_gaussian,
    "correlated_gaussian": correlated_gaussian,
    "ar1": ar1,
}


def apply_noise(image: np.ndarray, kind: str, **params) -> np.ndarray:
    """Apply a named noise type to an image.

    Parameters
    ----------
    image : np.ndarray
        Input image, uint8, 2-D or 3-D.
    kind : str
        Noise type; must be a key of :data:`NOISE_FUNCS`.
    **params
        Keyword arguments forwarded to the underlying noise function.

    Returns
    -------
    np.ndarray
        Noisy image, uint8, same shape as *image*.

    Raises
    ------
    KeyError
        If *kind* is not in :data:`NOISE_FUNCS`.

    Examples
    --------
    >>> import numpy as np
    >>> img = np.zeros((64, 64), dtype=np.uint8)
    >>> out = apply_noise(img, "gaussian", std=10, seed=0)
    >>> out.shape == img.shape
    True
    """
    if kind not in NOISE_FUNCS:
        raise KeyError(f"Unknown noise kind '{kind}'. Available: {sorted(NOISE_FUNCS)}")
    return NOISE_FUNCS[kind](image, **params)
