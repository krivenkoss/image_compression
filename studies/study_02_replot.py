"""Replot study_02 from an existing CSV or XLSX (no recomputation).

Reads an already-produced CSV (or XLSX), applies the anomaly filter
defensively, and regenerates the per-cell rate-distortion PNGs in the
same directory as the source file (overwriting existing plots in place).

Usage::

    python -m studies.study_02_replot
    python -m studies.study_02_replot --csv output/study_02_compare_with_original/<file>.csv
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

CONFIG_PATH = Path("configs/study_02_compare_with_original.ini")
OUTPUT_DIR = Path("output/study_02_compare_with_original")


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

    out_dir = source.parent
    study_name = cfg["study"]["name"]

    plot_axes = [
        ("cr",     "psnr"),
        ("log_cr", "psnr"),
        ("cr",     "haar_psi"),
        ("log_cr", "haar_psi"),
    ]

    images_in_df = list(df["image"].unique())
    stds_in_df = sorted(df["std"].unique())

    for image_name in images_in_df:
        img_stem = Path(image_name).stem
        for std in stds_in_df:
            sub = df[(df["image"] == image_name) & (df["std"] == std)]
            if sub.empty:
                continue
            std_int = int(std)
            var_val = std_int * std_int
            title_base = f"{img_stem}  σ²={var_val} (σ={std_int})"
            for x_col, y_col in plot_axes:
                if x_col not in sub.columns or y_col not in sub.columns:
                    continue
                is_log = x_col == "log_cr"
                plot_path = out_dir / (
                    f"{study_name}"
                    f"__{img_stem}__std{std_int}"
                    f"__rd_{x_col}_vs_{y_col}.png"
                )
                plot_rd(
                    sub,
                    x=x_col,
                    y=y_col,
                    out_path=plot_path,
                    dpi=cfg["output"]["plot_dpi"],
                    xmin=None if is_log else cfg["output"].get("plot_xmin"),
                    xmax=None if is_log else cfg["output"].get("plot_xmax"),
                    ymin=cfg["output"].get("plot_ymin"),
                    ymax=cfg["output"].get("plot_ymax"),
                    title=title_base,
                )
                print(f"Plot: {plot_path.name}")

    print(f"Done. Plots in: {out_dir}")


if __name__ == "__main__":
    main()
