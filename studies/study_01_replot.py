"""Replot study_01 from an existing CSV or XLSX (no recomputation).

Reads an already-produced CSV (or XLSX), applies the anomaly filter
defensively, and regenerates the rate-distortion PNG in the same
directory as the source file.

Usage::

    python -m studies.study_01_replot
    python -m studies.study_01_replot --csv output/study_01_noisy_vs_compressed/<file>.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from anomalies import drop_coder_anomalies
from config_loader import load_ini
from visualization import plot_rd

CONFIG_PATH = Path("configs/study_01_noisy_vs_compressed.ini")
OUTPUT_DIR = Path("output/study_01_noisy_vs_compressed")


def _newest_csv(directory: Path) -> Path | None:
    csv_files = sorted(directory.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    return csv_files[0] if csv_files else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", type=Path, help="Explicit CSV file")
    ap.add_argument("--xlsx", type=Path, help="Explicit XLSX file")
    ap.add_argument("--config", type=Path, default=CONFIG_PATH)
    ap.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="K=V",
        help="Override INI value, e.g. output.plot_dpi=200",
    )
    args = ap.parse_args()

    if args.csv:
        source = args.csv
        df = pd.read_csv(source)
    elif args.xlsx:
        source = args.xlsx
        df = pd.read_excel(source)
    else:
        source = _newest_csv(OUTPUT_DIR)
        if source is None:
            print(f"No CSV found in {OUTPUT_DIR}/")
            sys.exit(1)
        df = pd.read_csv(source)

    print(f"Loaded: {source} ({len(df)} rows)")

    before = len(df)
    df = drop_coder_anomalies(df)
    n_dropped = before - len(df)
    if n_dropped:
        print(f"[anomalies] dropped {n_dropped} anomalous rows from AGU/AGUm/ADCT/ADCTm")

    cfg = load_ini(
        args.config,
        overrides=dict(kv.split("=", 1) for kv in args.set),
    )

    metric_cols = cfg["metrics"]["list"]
    preferred = "psnr_hvs_m"
    y_col = preferred if (preferred in metric_cols and preferred in df.columns) else metric_cols[0]

    plot_path = source.parent / (source.stem + f"__rd_{y_col}.png")
    plot_rd(
        df,
        x="cr",
        y=y_col,
        out_path=plot_path,
        dpi=cfg["output"]["plot_dpi"],
        xmin=cfg["output"].get("plot_xmin"),
        xmax=cfg["output"].get("plot_xmax"),
        ymin=cfg["output"].get("plot_ymin"),
        ymax=cfg["output"].get("plot_ymax"),
    )
    print(f"Plot: {plot_path}")


if __name__ == "__main__":
    main()
