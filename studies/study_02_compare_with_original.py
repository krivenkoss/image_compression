"""Study 02 — compare with original image.

Refined version analysing three classic grayscale standards of
increasing spatial complexity (Lena, Goldhill, Baboon) against
the original clean reference. Sweeps Gaussian noise variances
0, 25, 49, 100, 196 (std = 0, 5, 7, 10, 14) and the full coder
set JPEG / ADCT / BPG / HEIF / AVIF. Metrics: PSNR (for
comparison with classical results) and HaarPSI (for modern
perceptual comparison). Produces rate-distortion curves on
BOTH a linear CR axis and a log10(CR) axis — the log view
makes the parameter region where modern coders outperform
JPEG visible.

std = 0 means the original clean image is fed directly to the
coder (noise call is skipped to avoid spurious rounding artefacts).
Filenames are resolved case-insensitively from images/; if Lena.bmp
is absent, Peppers.bmp is used as a documented fallback.

Edit the matching INI for parameter changes — do not hard-code values here.

Usage::

    python -m studies.study_02_compare_with_original
    python -m studies.study_02_compare_with_original \\
           --config configs/study_02_compare_with_original.ini \\
           --set noise.std_values=0,10 --set coders.list=JPEG,BPG
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))
from config_loader import load_ini, informative_filename
from noise import apply_noise
from coders import compress
from metrics import compute_metrics
from visualization import plot_rd

CONFIG_PATH = Path("configs/study_02_compare_with_original.ini")


def noise_extras(cfg: dict, kind: str) -> dict:
    """Return only the noise-section keys consumed by *kind*."""
    n = cfg["noise"]
    if kind == "gaussian":
        return {"mean": n["mean"]}
    if kind == "mixed_poisson_gaussian":
        return {"k": n["k"], "sigma0": n["sigma0"]}
    if kind == "ar1":
        return {"rho_h": n["rho_h"], "rho_v": n["rho_v"]}
    if kind == "correlated_gaussian":
        return {"kernel": n["kernel"], "radius": n["radius"]}
    return {}


def _resolve_image(name: str, images_dir: Path) -> Path | None:
    """Return the actual on-disk path for *name* (case-insensitive),
    or None if no match exists."""
    target = name.lower()
    for p in images_dir.iterdir():
        if p.is_file() and p.name.lower() == target:
            return p
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, default=CONFIG_PATH)
    ap.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="K=V",
        help="Override INI value, e.g. noise.std_values=5,10,14",
    )
    args = ap.parse_args()
    cfg = load_ini(
        args.config,
        overrides=dict(kv.split("=", 1) for kv in args.set),
    )

    # Study 02 always compares the decoded image against the ORIGINAL,
    # regardless of what the INI says.  We warn if the INI disagrees so
    # the researcher does not get a silently wrong configuration.
    if cfg["study"].get("reference", "original") != "original":
        print(
            f"[WARNING] Study 02 forces reference='original' but INI has "
            f"reference='{cfg['study']['reference']}'. Overriding to 'original'."
        )
    reference = "original"  # noqa: F841 — documents intent; metric loop uses `image` directly

    rng_seed = cfg["study"]["random_seed"]
    images_dir = Path(cfg["paths"]["images_dir"])
    out_dir = Path(cfg["paths"]["output_dir"]) / cfg["study"]["name"]
    out_dir.mkdir(parents=True, exist_ok=True)

    # Resolve requested filenames case-insensitively; Lena → Peppers fallback.
    resolved: list[Path] = []
    for i, name in enumerate(cfg["images"]["filenames"]):
        p = _resolve_image(name, images_dir)
        if p is None and i == 0 and name.lower() == "lena.bmp":
            p = _resolve_image("Peppers.bmp", images_dir)
            if p:
                print(f"[INFO] Lena.bmp not found, using {p.name} as fallback.")
        if p is None:
            print(f"[WARNING] Image not found, skipping: {name}")
            continue
        resolved.append(p)

    rows: list[dict] = []

    for coder in cfg["coders"]["list"]:
        cr_range = np.arange(
            cfg["coder_ranges"][coder]["start"],
            cfg["coder_ranges"][coder]["stop"],
            cfg["coder_ranges"][coder]["step"],
        )
        for image_path in resolved:
            image = cv2.imread(str(image_path), 0)
            for noise_kind in cfg["noise"]["kinds"]:
                for std in cfg["noise"]["std_values"]:
                    if std == 0:
                        noised = image
                    else:
                        noised = apply_noise(
                            image,
                            noise_kind,
                            std=std,
                            seed=rng_seed,
                            **noise_extras(cfg, noise_kind),
                        )
                    # Reference is always the ORIGINAL clean image (study 02).
                    ref = image
                    for p in tqdm(
                        cr_range,
                        desc=f"{coder} | {image_path.name} | std={std}",
                    ):
                        try:
                            decoded, cr = compress(noised, coder, p)
                        except Exception as exc:
                            print(f"[WARNING] compress({coder}, {p}) failed: {exc}")
                            continue
                        m = compute_metrics(ref, decoded, cfg["metrics"]["list"])
                        rows.append(
                            {
                                "image": image_path.name,
                                "coder": coder,
                                "noise_kind": noise_kind,
                                "std": std,
                                "variance": std * std,
                                "pcc": float(p),
                                "cr": cr,
                                "log_cr": math.log10(cr) if cr > 0 else float("nan"),
                                **m,
                            }
                        )

    if not rows:
        print(
            "No results collected — check that images exist in images/ and "
            "coders are available."
        )
        return

    df = pd.DataFrame(rows)

    kind_tag = "-".join(cfg["noise"]["kinds"])
    std_tag = "-".join(map(str, cfg["noise"]["std_values"]))
    base = informative_filename(
        cfg["study"]["name"],
        "+".join(p.name for p in resolved),
        cfg["coders"]["list"],
        kind_tag,
        std_tag,
        "",
        out_dir,
    ).with_suffix("")

    if cfg["output"]["write_csv"]:
        csv_path = base.with_suffix(".csv")
        df.to_csv(csv_path, index=False)
        print(f"CSV: {csv_path}")

    if cfg["output"]["write_xlsx"]:
        xlsx_path = base.with_suffix(".xlsx")
        df.to_excel(
            xlsx_path,
            sheet_name=("-".join(cfg["coders"]["list"]))[:31],
            index=False,
        )
        print(f"XLSX: {xlsx_path}")

    if cfg["output"]["write_plots"]:
        plot_axes = [
            ("cr",     "psnr"),
            ("log_cr", "psnr"),
            ("cr",     "haar_psi"),
            ("log_cr", "haar_psi"),
        ]

        # Discover cells from the data, not from the config — robust to
        # missing images, --set overrides, and failed compressions.
        images_in_df = list(df["image"].unique())
        stds_in_df = sorted(df["std"].unique())

        for image_name in images_in_df:
            img_stem = Path(image_name).stem
            for std in stds_in_df:
                sub = df[(df["image"] == image_name) & (df["std"] == std)]
                if sub.empty:
                    continue
                var_val = int(std * std)
                title_base = f"{img_stem}  σ²={var_val} (σ={std})"
                for x_col, y_col in plot_axes:
                    if x_col not in sub.columns or y_col not in sub.columns:
                        continue
                    is_log = x_col == "log_cr"
                    plot_path = out_dir / (
                        f"{cfg['study']['name']}"
                        f"__{img_stem}__std{std}"
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

    print(f"Done. Results in: {out_dir}")


if __name__ == "__main__":
    main()
