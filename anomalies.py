"""Anomaly filter for coder-bug spikes in rate-distortion data.

Usage (command-line quick-check)::

    python -m anomalies <csv-path>

Doctests::

    >>> import pandas as pd
    >>> df = pd.DataFrame({
    ...     "coder": ["ADCT"]*5,
    ...     "image": ["a.bmp"]*5,
    ...     "std":   [0]*5,
    ...     "noise_kind": ["gaussian"]*5,
    ...     "pcc":   [1, 2, 3, 4, 5],
    ...     "psnr":  [35.0, 34.5, 5.0, 35.5, 36.0],
    ...     "haar_psi": [0.9, 0.91, 0.05, 0.92, 0.93],
    ... })
    >>> out = drop_coder_anomalies(df)
    >>> list(out["pcc"])
    [1, 2, 4, 5]
    >>> # Idempotent:
    >>> list(drop_coder_anomalies(out)["pcc"])
    [1, 2, 4, 5]
"""
from __future__ import annotations

import sys

import pandas as pd


def drop_coder_anomalies(
    df: pd.DataFrame,
    *,
    coders: tuple[str, ...] = ("AGU", "AGUm", "ADCT", "ADCTm"),
    group_cols: tuple[str, ...] = ("coder", "image", "std", "noise_kind"),
    sort_col: str = "pcc",
    psnr_drop_db: float = 5.0,
    perceptual_drop_factor: float = 0.5,
    window: int = 5,
    psnr_cols: tuple[str, ...] = ("psnr", "psnr_hvs", "psnr_hvs_m"),
    perceptual_cols: tuple[str, ...] = (
        "haar_psi", "ssim", "ms_ssim", "uqi", "fsim", "vsi",
    ),
) -> pd.DataFrame:
    """Drop coder-bug anomaly rows. Returns a NEW DataFrame.

    Operates only on rows whose `coder` is in `coders`. All other
    rows pass through unchanged.

    For each group defined by `group_cols`, rows are sorted by
    `sort_col` and a centred rolling median of size `window` is
    computed over each metric column present in the frame. A row
    is flagged anomalous if, for ANY metric:
        - dB metric (in `psnr_cols`):
            value < rolling_median - psnr_drop_db
        - unit-scale perceptual metric (in `perceptual_cols`):
            value < rolling_median * perceptual_drop_factor
    (other columns are ignored). Flagged rows are dropped.

    The OR-across-metrics rule reflects the bug behaviour: when the
    decode is corrupted, every quality metric collapses
    simultaneously, so a single flag is enough.

    Idempotent: calling twice yields the same result as calling once.
    """
    if "coder" not in df.columns or df.empty:
        return df.copy()

    present_psnr = [c for c in psnr_cols if c in df.columns]
    present_perceptual = [c for c in perceptual_cols if c in df.columns]
    all_metric_cols = present_psnr + present_perceptual

    if not all_metric_cols:
        return df.copy()

    valid_group_cols = [c for c in group_cols if c in df.columns]
    is_suspected = df["coder"].isin(coders)

    if not is_suspected.any():
        return df.copy()

    suspected = df[is_suspected]
    anomalous_idx: set = set()

    for _, group in suspected.groupby(valid_group_cols, sort=False):
        if len(group) < 3:
            continue
        sorted_group = group.sort_values(sort_col)
        for col in all_metric_cols:
            s = sorted_group[col]
            med = s.rolling(window, center=True, min_periods=1).median()
            if col in present_psnr:
                bad = s < med - psnr_drop_db
            else:
                bad = s < med * perceptual_drop_factor
            anomalous_idx.update(sorted_group.index[bad].tolist())

    return df.drop(index=list(anomalous_idx)).reset_index(drop=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m anomalies <csv-path>")
        sys.exit(1)

    path = sys.argv[1]
    data = pd.read_csv(path)
    before = len(data)
    filtered = drop_coder_anomalies(data)
    dropped = before - len(filtered)
    print(f"Rows before: {before}")
    print(f"Rows after:  {len(filtered)}")
    print(f"Dropped:     {dropped}")
