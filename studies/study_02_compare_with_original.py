"""Study 02 — compare with original image.

Replicates the legacy ``Main OOP cycle (compare with original image)`` block
from oop.py.  The noised image is fed to the coder, but the quality of the
decoded image is measured against the ORIGINAL (clean) image — not against
the noised one.  This is the lossy-compression + denoising scenario: a
coder that smooths some of the noise away can score better here than in
study 01.

Edit the matching INI for parameter changes — do not hard-code values here.

Usage::

    python -m studies.study_02_compare_with_original
    python -m studies.study_02_compare_with_original \\
           --config configs/study_02_compare_with_original.ini \\
           --set noise.std_values=5,10,14 --set coders.list=JPEG,BPG
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from tqdm import tqdm

# Flat import from project root (run as: python -m studies.study_02_...)
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
    reference = "original"

    rng_seed = cfg["study"]["random_seed"]
    images_dir = Path(cfg["paths"]["images_dir"])
    out_dir = Path(cfg["paths"]["output_dir"]) / cfg["study"]["name"]
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []

    for coder in cfg["coders"]["list"]:
        cr_range = np.arange(
            cfg["coder_ranges"][coder]["start"],
            cfg["coder_ranges"][coder]["stop"],
            cfg["coder_ranges"][coder]["step"],
        )
        for image_name in cfg["images"]["filenames"]:
            image_path = images_dir / image_name
            if not image_path.exists():
                print(f"[WARNING] Image not found, skipping: {image_path}")
                continue
            image = cv2.imread(str(image_path), 0)
            for noise_kind in cfg["noise"]["kinds"]:
                for std in cfg["noise"]["std_values"]:
                    noised = apply_noise(
                        image,
                        noise_kind,
                        std=std,
                        seed=rng_seed,
                        **noise_extras(cfg, noise_kind),
                    )
                    # Reference is the ORIGINAL clean image (the point of study 02).
                    ref = image
                    for p in tqdm(
                        cr_range,
                        desc=f"{coder} | {image_name} | std={std}",
                    ):
                        try:
                            decoded, cr = compress(noised, coder, p)
                        except Exception as exc:
                            print(f"[WARNING] compress({coder}, {p}) failed: {exc}")
                            continue
                        m = compute_metrics(ref, decoded, cfg["metrics"]["list"])
                        rows.append(
                            {
                                "image": image_name,
                                "coder": coder,
                                "noise_kind": noise_kind,
                                "std": std,
                                "pcc": float(p),
                                "cr": cr,
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
        "+".join(cfg["images"]["filenames"]),
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
        # Prefer psnr_hvs_m; fall back to the first available metric column.
        preferred = "psnr_hvs_m"
        metric_cols = cfg["metrics"]["list"]
        y_col = preferred if preferred in metric_cols else metric_cols[0]
        plot_path = base.with_name(base.name + f"__rd_{y_col}.png")
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

    print(f"Done. Results in: {out_dir}")


if __name__ == "__main__":
    main()
