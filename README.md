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
- **12 metrics** — MSE, PSNR, SSIM, MS-SSIM, UQI, PSNR-HVS, PSNR-HVS-M, HaarPSI, FSIM, VSI, MDSI, GMSD
- **7 noise models** — Gaussian, uniform, speckle, Poisson, mixed Poisson-Gaussian, correlated Gaussian, AR-1
- **INI-driven configuration** — change parameters without touching Python
- **Two-file workflow** — one study file (loop) + one INI (parameters)
- **Offline replot** — separate per-study replot scripts rebuild all PNGs
  from an existing CSV without re-running compression
- **Anomaly filter** — drops decoder-bug spikes for the proprietary coders
  (AGU / AGUm / ADCT / ADCTm) before plots and tables

---

## Two-file workflow

For each study you edit exactly **two** files:

| File | Role |
|---|---|
| `studies/study_XX_<name>.py` | Experiment loop — visible top-to-bottom |
| `configs/study_XX_<name>.ini` | All numeric/list parameters |

Each study also has a paired `studies/study_XX_<name>_replot.py` script that
re-renders all PNGs from an already-saved CSV/XLSX (no recomputation).

Infrastructure modules (`metrics.py`, `coders.py`, `noise.py`,
`visualization.py`, `config_loader.py`, `anomalies.py`) expose stable APIs and
must **not** be edited for normal use. To re-run with new settings, edit only
the INI.

---

## Project structure

```
image_compression/
├── README.md
├── LICENSE                              MIT, 2026, Krivenko S.S.
├── CITATION.cff                         Academic citation metadata
├── .gitignore
├── pytest.ini                           pytest configuration
├── requirements.txt
├── requirements-dev.txt                 pytest only
├── xai_image_compression.code-workspace VS Code workspace file
├── .github/workflows/ci.yml             One-step pytest CI
├── images/                              Drop test images here
│   └── README.md                        Notes on the bundled test images
├── coders/                              Drop codec binaries here
│   └── README.md                        Where to find each binary
├── output/                              Results (gitignored except .gitkeep)
├── prompts/                             Saved Claude/LLM prompts used for the project
├── legacy/                              Original OOP reference scripts (not on the import path)
│   ├── oop.py
│   └── image_utils.py
├── configs/
│   ├── study_01_noisy_vs_compressed.ini
│   └── study_02_compare_with_original.ini
├── metrics.py                           Full-reference IQA metrics
├── coders.py                            Compress / decompress wrappers
├── noise.py                             Noise injection functions
├── visualization.py                     RD plots and image grids
├── config_loader.py                     INI loader + filename builder
├── anomalies.py                         Drops decoder-bug spikes from RD frames
├── tests/
│   ├── test_metrics.py
│   ├── test_noise.py
│   └── test_coders.py
└── studies/
    ├── study_01_noisy_vs_compressed.py  Decoded vs noisy reference
    ├── study_01_replot.py               Re-render study_01 PNG from CSV
    ├── study_02_compare_with_original.py  Decoded vs original; per-cell plots
    └── study_02_replot.py               Re-render study_02 PNGs from CSV
```

---

## Available studies

| Study | Reference | Plots | Notes |
|---|---|---|---|
| `study_01_noisy_vs_compressed` | configurable (`noisy` or `original`) | single combined RD plot | reproduces the legacy `Main OOP cycle (compare with noised image)` block |
| `study_02_compare_with_original` | always `original` (forced by the script) | per-cell PNGs: one per `(image, std)` × `(cr / log_cr, metric)` | sweeps Gaussian std ∈ {0, 5, 7, 10, 14}; std=0 skips the noise call; case-insensitive image lookup with `Lena.bmp → Peppers.bmp` fallback |

Each study has a paired `*_replot.py` that loads the existing CSV/XLSX and
regenerates plots — useful for retuning axis limits, fixing titles, or
re-applying the anomaly filter without recomputing the metrics.

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
python -m studies.study_02_compare_with_original

# Override noise std and coder list on the command line
python -m studies.study_02_compare_with_original \
       --config configs/study_02_compare_with_original.ini \
       --set noise.std_values=0,10 \
       --set coders.list=JPEG,BPG
```

Results land in `output/<study_name>/`.

### Replot (no recomputation)

To rebuild plots from an existing CSV — useful after retuning axis limits or
the anomaly filter — run the matching replot script. It auto-picks the newest
CSV in the study's output directory, or accepts an explicit path:

```bash
# Newest CSV in output/study_02_compare_with_original/
python -m studies.study_02_replot

# Specific file
python -m studies.study_02_replot --csv output/study_02_compare_with_original/<file>.csv

# Tweak only plot DPI for the rerun
python -m studies.study_02_replot --set output.plot_dpi=200
```

The replot scripts apply `drop_coder_anomalies(df)` defensively, so even an
older CSV that still contains decoder spikes will get a clean plot.

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
| `reference` | Reference for metrics: `noisy` or `original` (study_02 always forces `original`) |
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
> In `study_02`, `plot_xmin`/`plot_xmax` apply only to the linear-CR plots; the `log10(CR)` plots always autoscale so small CR values stay visible.

---

## Anomaly filter

The proprietary coders **AGU / AGUm / ADCT / ADCTm** occasionally produce a
catastrophically corrupted decoded image at an isolated parameter value: the
metric column collapses (PSNR drops to single digits, HaarPSI drops below 0.1)
while the neighbouring `pcc` values for the same `(coder, image, std)` slice
look smooth. This is a binary-coder bug, not a real measurement.

`anomalies.drop_coder_anomalies(df)` is applied automatically:

- inside both studies before CSV / XLSX / plots are written,
- and defensively inside both replot scripts.

For each `(coder, image, std, noise_kind)` group, rows are sorted by `pcc` and
a centred rolling median (default window = 5) is computed per metric column.
A row is dropped if, for **any** metric:

- dB metrics (`psnr`, `psnr_hvs`, `psnr_hvs_m`): `value < median − 5 dB`
- unit-scale perceptual metrics (`haar_psi`, `ssim`, `ms_ssim`, `uqi`, `fsim`, `vsi`): `value < median × 0.5`

Filtered rows are deleted from the frame entirely — no flag column is added,
and the CSV/XLSX schema stays unchanged. The function is idempotent (calling
it twice returns the same frame as calling it once) and operates only on the
four proprietary coders; JPEG, JPEG2000, BPG, HEIF, AVIF rows are never
touched.

Thresholds are keyword-only arguments of `drop_coder_anomalies` — tune them in
code if needed. Quick CSV check from the command line:

```bash
python -m anomalies output/study_02_compare_with_original/<file>.csv
```

---

## Adding a new study

1. Copy `studies/study_01_noisy_vs_compressed.py` → `studies/study_XX_<name>.py`
2. Copy `configs/study_01_noisy_vs_compressed.ini` → `configs/study_XX_<name>.ini`
3. Edit the loop in the `.py` file and the parameters in the `.ini` file.
4. (Optional) copy `studies/study_01_replot.py` → `studies/study_XX_<name>_replot.py`
   for offline plot rebuilding.
5. Run with `python -m studies.study_XX_<name>`.

---

## Adding a new coder

1. Implement a `_compress_<name>` function in `coders.py` following the pattern
   of `_compress_jpeg` or `_compress_agu_style`.
2. Add an entry to `DEFAULT_RANGES` with `start`, `stop`, `step`.
3. Register it in the `compress()` dispatch block.
4. Add the coder name to `_KNOWN_CODERS` in `config_loader.py`.

## Adding a new metric

1. Implement a `name(ref, test) -> float` function in `metrics.py`.
2. Register it by adding the name → function entry to `METRIC_FUNCS`.

That's it — `config_loader` validates the configured metric list against the
keys actually present in `METRIC_FUNCS` at import time, so no separate
allow-list edit is needed.

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
| `NOISE_FUNCS` | Public `{name: function}` registry consumed by `apply_noise`. |

### `visualization.py`

| Function | Description |
|---|---|
| `axis_label(metric)` | Human-readable label, adds ", dB" for dB-scale metrics. `axis_label("psnr_hvs_m")` → `'PSNR-HVS-M, dB'` |
| `plot_rd(df, x, y, out_path, dpi, logx, title=...)` | RD curve per coder. `plot_rd(df, x="cr", y="psnr_hvs_m", out_path=Path("output/rd.png"))` |
| `plot_scatter(df, x, y, hue, out_path, dpi)` | Scatter of two metrics. `plot_scatter(df, x="psnr", y="ssim", out_path=Path("output/sc.png"))` |
| `plot_image_grid(images, out_path, dpi)` | Side-by-side image grid. `plot_image_grid({"orig": img, "noised": n}, Path("output/grid.png"))` |

### `config_loader.py`

| Function | Description |
|---|---|
| `load_ini(path, overrides=None)` | Load INI → nested dict with auto-cast values. `load_ini(Path("configs/study_01_....ini"))` |
| `informative_filename(study, image, coders, noise_kind, std, ext, out_dir)` | Build timestamped output path. `informative_filename("s01", "img.bmp", ["JPEG"], "gaussian", 10, "csv", Path("output"))` |

### `anomalies.py`

| Function | Description |
|---|---|
| `drop_coder_anomalies(df, *, coders=..., psnr_drop_db=5.0, perceptual_drop_factor=0.5, window=5, ...)` | Pure function; returns a NEW DataFrame with decoder-bug spikes removed for `coders` (default: AGU, AGUm, ADCT, ADCTm). Idempotent. |

CLI usage:

```bash
python -m anomalies <csv-path>
```

prints `Rows before / Rows after / Dropped` counts.

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
- **AGU / AGUm / ADCT / ADCTm decoder spikes** are filtered out automatically
  by `anomalies.drop_coder_anomalies` (see the "Anomaly filter" section above).
- **AR-1 noise** uses a pure-Python nested loop which is slow for large images.
  For production use, replace the inner loop with a Numba JIT or scipy lfilter
  approach.
- **JPEG2000 CR** is controlled via the `quality_layers` rate parameter in
  Pillow, which may not exactly match the legacy OpenJPEG `opj_compress -r`
  behaviour. Adjust `step` in the INI accordingly.
