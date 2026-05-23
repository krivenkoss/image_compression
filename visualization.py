"""Visualization utilities for compression research results.

Each function saves a PNG file and returns its path.
"""
from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

logger = logging.getLogger(__name__)

plt.rcParams.update({"font.size": 20})

_DEFAULT_OUT = Path("output")

# Metrics expressed in decibels — axis labels get a ", dB" suffix.
DB_METRICS: frozenset[str] = frozenset({"psnr", "psnr_hvs", "psnr_hvs_m"})

# Pretty display names; falls back to metric.upper() when missing.
METRIC_LABELS: dict[str, str] = {
    "mse":        "MSE",
    "psnr":       "PSNR",
    "psnr_hvs":   "PSNR-HVS",
    "psnr_hvs_m": "PSNR-HVS-M",
    "ssim":       "SSIM",
    "ms_ssim":    "MS-SSIM",
    "uqi":        "UQI",
    "haar_psi":   "HaarPSI",
    "fsim":       "FSIM",
    "vsi":        "VSI",
    "mdsi":       "MDSI",
    "gmsd":       "GMSD",
    "cr":         "Compression ratio",
    "log_cr":     "log₁₀(CR)",   # rendered: log₁₀(CR)
}


def axis_label(metric: str) -> str:
    """Return a human-readable axis label, with ', dB' for dB-scale metrics.

    Parameters
    ----------
    metric : str
        Metric key (e.g. ``"psnr_hvs_m"``, ``"ssim"``, ``"cr"``).

    Returns
    -------
    str
        Display label, e.g. ``"PSNR-HVS-M, dB"`` or ``"SSIM"``.

    Examples
    --------
    >>> axis_label("psnr_hvs_m")
    'PSNR-HVS-M, dB'
    >>> axis_label("ssim")
    'SSIM'
    """
    pretty = METRIC_LABELS.get(metric, metric.upper())
    return f"{pretty}, dB" if metric in DB_METRICS else pretty


def plot_rd(
    df: pd.DataFrame,
    x: str = "cr",
    y: str = "psnr_hvs_m",
    out_path: Path = _DEFAULT_OUT / "rd_curve.png",
    dpi: int = 150,
    logx: bool = False,
    xmin: float | None = None,
    xmax: float | None = None,
    ymin: float | None = None,
    ymax: float | None = None,
    title: str | None = None,
) -> Path:
    """Plot rate-distortion curves (one line per coder).

    Parameters
    ----------
    df : pd.DataFrame
        Results frame with at least columns *x*, *y*, and ``coder``.
    x : str
        Column to use as the x-axis (default: ``"cr"``).
    y : str
        Column to use as the y-axis (default: ``"psnr_hvs_m"``).
    out_path : Path
        Destination PNG path.
    dpi : int
        Output resolution.
    logx : bool
        Use logarithmic x-axis when True.
    xmin, xmax : float or None
        X-axis limits; ``None`` means matplotlib autoscale for that bound.
    ymin, ymax : float or None
        Y-axis limits; ``None`` means matplotlib autoscale for that bound.

    Returns
    -------
    Path
        Absolute path of the saved PNG.

    Examples
    --------
    >>> import pandas as pd, numpy as np
    >>> df = pd.DataFrame({"cr": [2,3,4], "psnr_hvs_m": [30,35,40], "coder": ["JPEG"]*3})
    >>> p = plot_rd(df, out_path=Path("output/test_rd.png"))
    >>> p.suffix == ".png"
    True
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 5))
    for coder, sub in df.groupby("coder"):
        sub_sorted = sub.sort_values(x)
        ax.plot(sub_sorted[x], sub_sorted[y], marker=".", label=coder)
    ax.set_xlabel(axis_label(x))
    ax.set_ylabel(axis_label(y))
    if title:
        ax.set_title(title)
    else:
        ax.set_title(f"{axis_label(y)} vs {axis_label(x)}")
    if logx:
        ax.set_xscale("log")
    if xmin is not None or xmax is not None:
        ax.set_xlim(left=xmin, right=xmax)
    if ymin is not None or ymax is not None:
        ax.set_ylim(bottom=ymin, top=ymax)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=dpi)
    plt.close(fig)
    return out_path.resolve()


def plot_scatter(
    df: pd.DataFrame,
    x: str,
    y: str,
    hue: str = "coder",
    out_path: Path = _DEFAULT_OUT / "scatter.png",
    dpi: int = 150,
    xmin: float | None = None,
    xmax: float | None = None,
    ymin: float | None = None,
    ymax: float | None = None,
) -> Path:
    """Scatter plot of two metric columns coloured by a grouping variable.

    Parameters
    ----------
    df : pd.DataFrame
        Results frame containing columns *x*, *y*, and *hue*.
    x : str
        Column for the x-axis.
    y : str
        Column for the y-axis.
    hue : str
        Column used for colour coding (default: ``"coder"``).
    out_path : Path
        Destination PNG path.
    dpi : int
        Output resolution.
    xmin, xmax : float or None
        X-axis limits; ``None`` means matplotlib autoscale for that bound.
    ymin, ymax : float or None
        Y-axis limits; ``None`` means matplotlib autoscale for that bound.

    Returns
    -------
    Path
        Absolute path of the saved PNG.

    Examples
    --------
    >>> import pandas as pd
    >>> df = pd.DataFrame({"psnr": [30,35], "ssim": [0.9,0.95], "coder": ["JPEG","BPG"]})
    >>> p = plot_scatter(df, x="psnr", y="ssim", out_path=Path("output/test_sc.png"))
    >>> p.suffix == ".png"
    True
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 5))
    sns.scatterplot(data=df, x=x, y=y, hue=hue, alpha=0.7, ax=ax)
    ax.set_xlabel(axis_label(x))
    ax.set_ylabel(axis_label(y))
    ax.set_title(f"{axis_label(y)} vs {axis_label(x)}")
    if xmin is not None or xmax is not None:
        ax.set_xlim(left=xmin, right=xmax)
    if ymin is not None or ymax is not None:
        ax.set_ylim(bottom=ymin, top=ymax)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=dpi)
    plt.close(fig)
    return out_path.resolve()


def plot_image_grid(
    images: dict[str, np.ndarray],
    out_path: Path,
    dpi: int = 150,
) -> Path:
    """Save a side-by-side image grid (original / noised / decoded, etc.).

    Parameters
    ----------
    images : dict[str, np.ndarray]
        Ordered mapping of label -> uint8 numpy array (grayscale or BGR).
    out_path : Path
        Destination PNG path.
    dpi : int
        Output resolution.

    Returns
    -------
    Path
        Absolute path of the saved PNG.

    Examples
    --------
    >>> import numpy as np
    >>> imgs = {"original": np.zeros((64,64), dtype=np.uint8)}
    >>> p = plot_image_grid(imgs, Path("output/grid.png"))
    >>> p.suffix == ".png"
    True
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = len(images)
    fig, axes = plt.subplots(1, n, figsize=(4 * n, 4))
    if n == 1:
        axes = [axes]
    for ax, (label, arr) in zip(axes, images.items()):
        display = arr if arr.ndim == 2 else arr[:, :, ::-1]  # BGR -> RGB
        ax.imshow(display, cmap="gray" if arr.ndim == 2 else None)
        ax.set_title(label, fontsize=18)
        ax.axis("off")
    fig.tight_layout()
    fig.savefig(out_path, dpi=dpi)
    plt.close(fig)
    return out_path.resolve()
