"""Generate visual image examples for study_01 (noisy vs compressed).

For each image saves to OUTPUT_DIR:
  - clean original
  - noisy version at NOISE_STD
  - one decoded PNG per coder at its CODERS parameter (optimal working point)
  - side-by-side comparison panel

Edit the Settings block below to match your optimal working points from the RD
curves.  Image filenames are resolved case-insensitively from IMAGES_DIR.

Usage::

    python -m studies.study_01_image_examples
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).parent.parent))
from coders import compress
from noise import apply_noise
from visualization import plot_image_grid

# ── Settings ──────────────────────────────────────────────────────────────────

IMAGES_DIR = Path("images")
OUTPUT_DIR = Path("output/study_01_noisy_vs_compressed/image_examples")

IMAGES = ["goldhill.bmp", "lenna.bmp", "BABOON.BMP"]

NOISE_KIND = "gaussian"
NOISE_MEAN = 0
NOISE_STD  = 14     # Gaussian σ; set to 0 to skip noising
NOISE_SEED = 42

# Optimal working point parameter per coder.
# JPEG: quality 1-100 (higher = better quality / less compression)
# BPG:  QP 2-51      (lower  = better quality / less compression)
CODERS: dict[str, int | float] = {
    "JPEG": 75,
    "BPG":  30,
}

DPI = 150

# ── Helpers ───────────────────────────────────────────────────────────────────


def _resolve(name: str, directory: Path) -> Path | None:
    target = name.lower()
    for p in directory.iterdir():
        if p.is_file() and p.name.lower() == target:
            return p
    return None


def _save(arr, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), arr)


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for name in IMAGES:
        p = _resolve(name, IMAGES_DIR)
        if p is None:
            print(f"[WARNING] not found, skipping: {name}")
            continue

        stem = p.stem
        image = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)

        # Clean
        clean_path = OUTPUT_DIR / f"{stem}_clean.png"
        _save(image, clean_path)
        print(f"Saved: {clean_path.name}")

        panel: dict[str, object] = {"clean": image}

        # Noisy
        if NOISE_STD > 0:
            noisy = apply_noise(
                image, NOISE_KIND, std=NOISE_STD, seed=NOISE_SEED, mean=NOISE_MEAN
            )
            noisy_path = OUTPUT_DIR / f"{stem}_noisy_std{NOISE_STD}.png"
            _save(noisy, noisy_path)
            print(f"Saved: {noisy_path.name}")
            panel[f"noisy σ={NOISE_STD}"] = noisy
            source = noisy
        else:
            source = image

        # Compressed
        for coder, param in CODERS.items():
            try:
                decoded, cr = compress(source, coder, param)
            except Exception as exc:
                print(f"[WARNING] {coder} param={param} failed: {exc}")
                continue
            tag = f"{coder}_p{param}"
            comp_path = OUTPUT_DIR / f"{stem}_{tag}.png"
            _save(decoded, comp_path)
            print(f"Saved: {comp_path.name}  (CR={cr:.2f})")
            panel[f"{coder} p={param}\nCR={cr:.1f}"] = decoded

        # Panel
        panel_path = OUTPUT_DIR / f"{stem}_panel.png"
        plot_image_grid(panel, panel_path, dpi=DPI)
        print(f"Saved: {panel_path.name}")

    print(f"\nDone. Images in: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
