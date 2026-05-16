# image_compression

A lossy image compression research framework for benchmarking codec performance under noise.

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![tests](https://github.com/krivenkoss/image_compression/actions/workflows/ci.yml/badge.svg)

---

## What it is

`image_compression` is a Python script repository for evaluating how well
standard and proprietary lossy image codecs compress noisy images. Each
experiment compares decoded images against a reference (either the original
or the noised version) using a configurable set of full-reference image quality
metrics. Results are saved as CSV, XLSX, and rate-distortion plots.

---

## Features

- **9 codecs** — JPEG, JPEG2000, HEIF, AVIF, BPG, AGU, AGUm, ADCT, ADCTm
- **13 metrics** — MSE, PSNR, SSIM, MS-SSIM, UQI, PSNR-HVS, PSNR-HVS-M, HaarPSI, FSIM, VSI, MDSI, GMSD
- **7 noise models** — Gaussian, uniform, speckle, Poisson, mixed Poisson-Gaussian, correlated Gaussian, AR-1
- **INI-driven configuration** — change parameters without touching Python
- **Two-file workflow** — one study file (loop) + one INI (parameters)

---

## Two-file workflow

For each study you edit exactly **two** files:

| File | Role |
|---|---|
| `studies/study_XX_<name>.py` | Experiment loop — visible top-to-bottom |
| `configs/study_XX_<name>.ini` | All numeric/list parameters |

Infrastructure modules (`metrics.py`, `coders.py`, `noise.py`,
`visualization.py`, `config_loader.py`) expose stable APIs and must **not**
be edited for normal use.  To re-run with new settings, edit only the INI.

---

## Project structure

```
image_compression/
├── README.md
├── LICENSE                            MIT, 2026, Krivenko S.S.
├── CITATION.cff                       Academic citation metadata
├── .gitignore
├── requirements.txt
├── requirements-dev.txt               pytest only
├── .github/workflows/ci.yml          One-step pytest CI
├── images/                            Drop test images here
├── coders/                            Drop codec binaries here
├── output/                            Results (gitignored except .gitkeep)
├── configs/
│   └── study_01_noisy_vs_compressed.ini
├── metrics.py                         Full-reference IQA metrics
├── coders.py                          Compress / decompress wrappers
├── noise.py                           Noise injection functions
├── visualization.py                   RD plots and image grids
├── config_loader.py                   INI loader + filename builder
├── tests/
│   ├── test_metrics.py
│   ├── test_noise.py
│   └── test_coders.py
└── studies/
    └── study_01_noisy_vs_compressed.py
```

---

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # Linux / macOS
pip install -r requirements.txt -r requirements-dev.txt
```

---

## Codec binaries

JPEG, JPEG2000, HEIF, and AVIF are handled entirely in-memory via Pillow /
pillow_heif — no binaries needed.

For BPG and the proprietary coders, place the following executables in the
`coders/` directory:

| File | Source |
|---|---|
| `bpgenc.exe` / `bpgdec.exe` | https://bellard.org/bpg/ |
| `AGU.exe` | Contact the authors |
| `AGUm.exe` | Contact the authors |
| `ADCT.exe` | Contact the authors |
| `ADCTm.exe` | Contact the authors |

The code raises `FileNotFoundError` with an informative message if a binary is
missing.

---

## Quickstart

```python
import cv2, numpy as np
from noise import apply_noise
from coders import compress
from metrics import psnr

img = cv2.imread("images/fr02.bmp", 0)        # grayscale
noised = apply_noise(img, "gaussian", std=10, seed=42)
decoded, cr = compress(noised, "JPEG", 75)
print(f"CR={cr:.2f}  PSNR={psnr(noised, decoded):.2f} dB")
```

---

## Running a study

```bash
# Default settings from the INI
python -m studies.study_01_noisy_vs_compressed

# Override noise std and coder list on the command line
python -m studies.study_01_noisy_vs_compressed \
       --config configs/study_01_noisy_vs_compressed.ini \
       --set noise.std_values=5,10,14 \
       --set coders.list=JPEG,BPG
```

Results land in `output/study_01_noisy_vs_compressed/`.

---

## INI reference

### `[paths]`

| Key | Description |
|---|---|
| `images_dir` | Directory containing source images |
| `coders_dir` | Directory containing codec binaries |
| `output_dir` | Root directory for result files |

### `[study]`

| Key | Description |
|---|---|
| `name` | Unique study identifier (used in output filenames) |
| `reference` | Reference for metrics: `noisy` or `original` |
| `random_seed` | Integer seed for all RNGs |

### `[images]`

| Key | Description |
|---|---|
| `filenames` | Comma-separated list of image filenames in `images_dir` |

### `[coders]`

| Key | Description |
|---|---|
| `list` | Comma-separated coder names, e.g. `JPEG, BPG, HEIF` |

### `[coder.X]` — per-coder parameter range

| Key | Description |
|---|---|
| `start` | First compression parameter value |
| `stop` | Exclusive upper bound (passed to `numpy.arange`) |
| `step` | Step between parameter values |

### `[noise]`

| Key | Description |
|---|---|
| `kinds` | Comma-separated noise types, e.g. `gaussian` |
| `std_values` | Comma-separated std values to sweep |
| `mean` | Mean for Gaussian noise |
| `k` | Poisson gain for mixed Poisson-Gaussian |
| `sigma0` | Read-noise std for mixed Poisson-Gaussian |
| `rho_h` | Horizontal AR-1 coefficient |
| `rho_v` | Vertical AR-1 coefficient |
| `kernel` | Kernel type for correlated Gaussian: `gauss` or `box` |
| `radius` | Kernel half-size for correlated Gaussian |

### `[metrics]`

| Key | Description |
|---|---|
| `list` | Comma-separated metric names, e.g. `psnr, ssim, psnr_hvs_m` |

### `[output]`

| Key | Description |
|---|---|
| `write_csv` | Save results as CSV when `true` |
| `write_xlsx` | Save results as Excel when `true` |
| `write_plots` | Save RD plots when `true` |
| `plot_dpi` | Plot resolution in DPI |
| `plot_xmin` | Left X-axis limit for RD plots; leave blank for autoscale |
| `plot_xmax` | Right X-axis limit for RD plots; leave blank for autoscale |
| `plot_ymin` | Bottom Y-axis limit for RD plots; leave blank for autoscale |
| `plot_ymax` | Top Y-axis limit for RD plots; leave blank for autoscale |

> Axis labels for PSNR / PSNR-HVS / PSNR-HVS-M automatically get a ", dB" suffix. All other metrics are dimensionless.

---

## Adding a new study

1. Copy `studies/study_01_noisy_vs_compressed.py` → `studies/study_02_<name>.py`
2. Copy `configs/study_01_noisy_vs_compressed.ini` → `configs/study_02_<name>.ini`
3. Edit the loop in the `.py` file and the parameters in the `.ini` file.
4. Run with `python -m studies.study_02_<name>`.

---

## Adding a new coder

1. Implement a `_compress_<name>` function in `coders.py` following the pattern
   of `_compress_jpeg` or `_compress_agu_style`.
2. Add an entry to `DEFAULT_RANGES` with `start`, `stop`, `step`.
3. Register it in the `compress()` dispatch block.
4. Add the coder name to `_KNOWN_CODERS` in `config_loader.py`.

## Adding a new metric

1. Implement a `name(ref, test) -> float` function in `metrics.py`.
2. Add it to `METRIC_FUNCS`.
3. Add the name string to `_KNOWN_METRICS` in `config_loader.py`.

## Adding a new noise type

1. Implement `name(image, ..., seed=None) -> np.ndarray` in `noise.py`.
2. Add it to `NOISE_FUNCS`.
3. Add the name string to `_KNOWN_NOISE` in `config_loader.py`.

---

## Function index

### `metrics.py`

| Function | Description |
|---|---|
| `mse(ref, test)` | Mean Squared Error. `mse(img, img)` → `0.0` |
| `psnr(ref, test)` | PSNR in dB; returns `inf` for identical images. `psnr(img, img)` → `inf` |
| `ssim(ref, test)` | SSIM in [−1, 1]. `ssim(img, img)` → `1.0` |
| `ms_ssim(ref, test)` | Multi-Scale SSIM. `ms_ssim(img, img)` → near `1.0` |
| `uqi(ref, test)` | Universal Quality Index. `uqi(img, img)` → `1.0` |
| `psnr_hvs(ref, test)` | PSNR-HVS. `psnr_hvs(img, img)` → large dB value |
| `psnr_hvs_m(ref, test)` | PSNR-HVS-M. `psnr_hvs_m(img, img)` → large dB value |
| `haar_psi(ref, test)` | HaarPSI via piq. `haar_psi(img, img)` → near `1.0` |
| `fsim(ref, test)` | FSIM via piq. `fsim(img, img)` → near `1.0` |
| `vsi(ref, test)` | VSI via piq. `vsi(img, img)` → near `1.0` |
| `mdsi(ref, test)` | MDSI via piq (lower = more similar). `mdsi(img, img)` → near `0.0` |
| `gmsd(ref, test)` | GMSD via piq (lower = more similar). `gmsd(img, img)` → near `0.0` |
| `compute_metrics(ref, test, names)` | Batch compute named metrics. `compute_metrics(img, img, ["psnr", "ssim"])` → `{"psnr": inf, "ssim": 1.0}` |

### `coders.py`

| Function / Object | Description |
|---|---|
| `DEFAULT_RANGES` | Per-coder parameter ranges dict. `DEFAULT_RANGES["JPEG"]` → `{"start":1, "stop":100, "step":1}` |
| `compress(image, coder, param)` | Compress + decompress once; returns `(decoded, cr)`. `compress(img, "JPEG", 75)` → `(ndarray, float)` |

### `noise.py`

| Function | Description |
|---|---|
| `gaussian(image, std, mean=0, seed=None)` | Additive Gaussian. `gaussian(img, std=10, seed=42)` |
| `uniform(image, low, high, seed=None)` | Additive uniform. `uniform(img, low=-10, high=10, seed=0)` |
| `speckle(image, std, seed=None)` | Multiplicative speckle. `speckle(img, std=0.1, seed=7)` |
| `poisson(image, scale=1.0, seed=None)` | Signal-dependent Poisson. `poisson(img, scale=1.0, seed=3)` |
| `mixed_poisson_gaussian(image, k, sigma0, seed=None)` | Mixed model. `mixed_poisson_gaussian(img, k=0.271, sigma0=23.74, seed=0)` |
| `correlated_gaussian(image, std, kernel, radius, seed=None)` | Spatially correlated Gaussian. `correlated_gaussian(img, std=10, kernel="gauss", radius=2, seed=0)` |
| `ar1(image, std, rho_h=0.7, rho_v=0.7, seed=None)` | AR-1 correlated noise. `ar1(img, std=10, rho_h=0.7, rho_v=0.7, seed=1)` |
| `apply_noise(image, kind, **params)` | Registry dispatcher. `apply_noise(img, "gaussian", std=10, seed=42)` |

### `visualization.py`

| Function | Description |
|---|---|
| `plot_rd(df, x, y, out_path, dpi, logx)` | RD curve per coder. `plot_rd(df, x="cr", y="psnr_hvs_m", out_path=Path("output/rd.png"))` |
| `plot_scatter(df, x, y, hue, out_path, dpi)` | Scatter of two metrics. `plot_scatter(df, x="psnr", y="ssim", out_path=Path("output/sc.png"))` |
| `plot_image_grid(images, out_path, dpi)` | Side-by-side image grid. `plot_image_grid({"orig": img, "noised": n}, Path("output/grid.png"))` |

### `config_loader.py`

| Function | Description |
|---|---|
| `load_ini(path, overrides=None)` | Load INI → nested dict with auto-cast values. `load_ini(Path("configs/study_01....ini"))` |
| `informative_filename(study, image, coders, noise_kind, std, ext, out_dir)` | Build timestamped output path. `informative_filename("s01", "img.bmp", ["JPEG"], "gaussian", 10, "csv", Path("output"))` |

---

## Tests

```bash
pytest -q
```

All tests use a synthesised 64×64 image. Tests for proprietary coders are
skipped automatically when the binaries are not present.

---

## Citation

```bibtex
@software{krivenko2026imagecompression,
  author  = {Krivenko, S. S.},
  title   = {image\_compression: a lossy image compression research framework},
  year    = {2026},
  version = {0.1.0},
  license = {MIT},
  url     = {https://github.com/krivenkoss/image_compression}
}
```

See `CITATION.cff` for full metadata.

---

## License

MIT — see [LICENSE](LICENSE).

---

## Notes

- **Colour input for AGU / ADCT / BPG:** the compression is applied
  independently per channel and the CR is reported as the mean across channels.
  This matches the per-channel design of the original executables.
- **AR-1 noise** uses a pure-Python nested loop which is slow for large images.
  For production use, replace the inner loop with a Numba JIT or scipy lfilter
  approach.
- **JPEG2000 CR** is controlled via the `quality_layers` rate parameter in
  Pillow, which may not exactly match the legacy OpenJPEG `opj_compress -r`
  behaviour. Adjust `step` in the INI accordingly.
